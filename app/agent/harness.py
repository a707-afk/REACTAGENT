"""Agent Harness: Coordinator-based Agent execution with full observability.

Each run follows the standard loop:
    Start → Policy pre-check → Understand → Plan → [Execute per step] → Draft → Evaluate → HITL → Finalize

Every step is written to agent_steps table for audit replay.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ── JSON extraction helpers ──────────────────────────────────────

def _extract_json_object(text: str) -> dict[str, Any] | None:
    """Robustly extract a JSON object from LLM output.

    Tries multiple strategies: fenced code blocks, brace matching,
    and full-text parsing.
    """
    import re
    # Strategy 1: code fence
    m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Strategy 2: outermost braces
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return None


def _extract_json_array(text: str) -> list | None:
    """Robustly extract a JSON array from LLM output."""
    import re
    # Strategy 1: code fence
    m = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Strategy 2: outermost brackets
    start = text.find('[')
    end = text.rfind(']')
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return None

# Budget defaults
DEFAULT_BUDGET = {
    "max_steps": 10,
    "max_tool_calls": 20,
    "max_latency_ms": 120_000,
    "step_timeout_seconds": 30.0,
    "max_transitions": 30,
    "max_rewrite_attempts": 2,
}


@dataclass
class AgentHarnessResult:
    """Complete result of an agent run."""
    run_id: str
    status: str  # completed | failed | terminated
    final_answer: str | None = None
    final_action: str | None = None
    human_review_required: bool = False
    total_steps: int = 0
    total_tool_calls: int = 0
    total_latency_ms: float = 0.0
    tool_error_count: int = 0
    permission_deny_count: int = 0
    errors: list[dict] = field(default_factory=list)
    approvals: list[dict] = field(default_factory=list)
    audit_trace: list[dict] = field(default_factory=list)


async def run_agent_harness(
    *,
    objective: str,
    tenant_id: str,
    user_id: str = "anonymous",
    user_context: dict[str, Any] | None = None,
    session_id: str | None = None,
    ticket_id: str | None = None,
    budget: dict[str, Any] | None = None,
) -> AgentHarnessResult:
    """Execute an agent run with full observability.

    Args:
        objective: The task objective / user query
        tenant_id: Tenant scope
        user_id: User identifier
        user_context: User roles, scopes, department
        session_id: Optional session for multi-turn
        ticket_id: Optional ticket reference
        budget: Step/tool budget limits
    """
    from app.agent.tool_registry import get_tool_registry
    from app.db.models.agent_run import AgentRun
    from app.db.models.agent_step import AgentStep
    from app.db.engine import get_sessionmaker

    t_start = time.perf_counter()
    budget = budget or DEFAULT_BUDGET
    max_steps = budget.get("max_steps", 10)
    max_tool_calls = budget.get("max_tool_calls", 20)
    max_latency_ms = budget.get("max_latency_ms", 120_000)
    step_timeout = budget.get("step_timeout_seconds", 30.0)
    max_transitions = budget.get("max_transitions", 30)
    max_rewrite_attempts = budget.get("max_rewrite_attempts", 2)

    run_id = str(uuid.uuid4())
    user_context = user_context or {}

    # ── Create AgentRun record ──
    run = AgentRun(
        id=run_id,
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        ticket_id=ticket_id,
        objective=objective,
        user_query=objective,
        status="running",
        risk_level=_assess_risk(objective),
        budget_json=json.dumps(budget, ensure_ascii=False),
    )

    errors: list[dict] = []
    approvals: list[dict] = []
    audit: list[dict] = []
    total_tool_calls = 0
    tool_error_count = 0
    perm_deny_count = 0
    transition_count = 0

    steps: list[AgentStep] = []
    step_index = 0

    def _add_step(step_type: str, input_data: dict, output_data: dict, tool_name: str | None = None,
                   tool_params: dict | None = None, tool_result: dict | None = None,
                   permission: str | None = None, latency: float = 0.0, error: str | None = None) -> AgentStep:
        nonlocal step_index
        step = AgentStep(
            id=str(uuid.uuid4()),
            run_id=run_id,
            tenant_id=tenant_id,
            step_index=step_index,
            step_type=step_type,
            input_json=json.dumps(input_data, ensure_ascii=False) if input_data else None,
            output_json=json.dumps(output_data, ensure_ascii=False) if output_data else None,
            tool_name=tool_name,
            tool_params_json=json.dumps(tool_params, ensure_ascii=False) if tool_params else None,
            tool_result_json=json.dumps(tool_result, ensure_ascii=False) if tool_result else None,
            permission_check=permission,
            latency_ms=latency,
            error_message=error,
        )
        step_index += 1
        steps.append(step)
        return step

    try:
        # Step 0.5: Input injection detection
        injection_check = _input_injection_detection(objective)
        if injection_check["blocked"]:
            _add_step("plan", {"action": "input_sanitize"}, {"blocked": True, "reason": injection_check["reason"]})
            audit.append({"step": "input_sanitize", "blocked": True, "reason": injection_check["reason"]})
            draft = "您的请求因安全原因被拦截：" + injection_check["reason"]
            _add_step("evaluate", {"action": "draft"}, {"draft": draft})
            run.status = "completed"
            run.final_answer = draft
            run.final_action = "input_blocked"
            total_latency = (time.perf_counter() - t_start) * 1000
            async with get_sessionmaker()() as session:
                run.total_steps = len(steps)
                run.total_latency_ms = total_latency
                run.audit_trace_json = json.dumps(audit, ensure_ascii=False)
                session.add(run)
                for s in steps: session.add(s)
                await session.commit()
            return AgentHarnessResult(run_id=run_id, status="completed", final_answer=draft, total_steps=len(steps), audit_trace=audit)
        # ── Step 1: Policy pre-check ──
        _add_step("plan", {"action": "policy_pre_check"}, {"risk_level": run.risk_level})
        audit.append({"step": "policy_pre_check", "risk_level": run.risk_level})

        # ── Step 1.5: Intent classification (pre-plan routing) ──
        intent_info = _classify_intent(objective)
        _add_step("plan", {"action": "intent_classify"}, intent_info)
        audit.append({"step": "intent_classify", **intent_info})

        # ── Step 2: Understand & Plan ──
        plan = _build_plan(objective, run.risk_level, intent_info=intent_info)
        _add_step("plan", {"action": "build_plan", "objective": objective}, {"plan": plan})
        run.plan_json = json.dumps(plan, ensure_ascii=False)
        audit.append({"step": "plan", "steps": len(plan)})

        # ── Step 3: Execute each plan step ──
        registry = get_tool_registry()
        all_observations: list[dict] = []
        plan_success = True

        for i, step_def in enumerate(plan):
            if step_index >= max_steps:
                errors.append({"step": i, "error": "max_steps_exceeded"})
                plan_success = False
                break

            # Budget enforcement: max latency check
            elapsed_ms = (time.perf_counter() - t_start) * 1000
            if elapsed_ms > max_latency_ms:
                errors.append({"step": i, "error": "max_latency_exceeded", "elapsed_ms": elapsed_ms})
                plan_success = False
                break

            # Budget enforcement: max transitions
            transition_count += 1
            if transition_count > max_transitions:
                errors.append({"step": i, "error": "max_transitions_exceeded"})
                plan_success = False
                break

            step_type = step_def.get("type", "execute")
            tool_name = step_def.get("tool")

            if step_type == "retrieve":
                # Retrieval step — handled by existing RAG pipeline
                _add_step("observe", {"action": "retrieve"}, {"status": "delegated_to_rag"})
                audit.append({"step": "retrieve", "delegated": True})
                continue

            if step_type == "execute" and tool_name:
                if total_tool_calls >= max_tool_calls:
                    errors.append({"step": i, "error": "max_tool_calls_exceeded"})
                    break

                tool = registry.get(tool_name)
                if tool is None:
                    _add_step("execute", {"tool": tool_name}, {}, tool_name=tool_name,
                              error=f"Unknown tool: {tool_name}")
                    tool_error_count += 1
                    audit.append({"step": "execute", "tool": tool_name, "error": "unknown_tool"})
                    continue

                # Permission gate
                from app.agent.permission_gate import check_permission
                params = step_def.get("params", {})
                perm = check_permission(tool, user_context, params, tenant_id)

                if not perm.allowed:
                    perm_deny_count += 1
                    _add_step("execute", {"tool": tool_name, "params": params}, {},
                              tool_name=tool_name, tool_params=params,
                              permission="denied" if not perm.requires_approval else "needs_approval",
                              error=perm.reason)
                    if perm.requires_approval:
                        approvals.append({"tool": tool_name, "params": params, "reason": perm.reason})
                    audit.append({"step": "execute", "tool": tool_name, "permission": "denied", "reason": perm.reason})
                    continue

                # Execute tool (with step-level timeout as safety net)
                t0 = time.perf_counter()
                try:
                    import asyncio
                    result = await asyncio.wait_for(
                        registry.execute(
                            tool_name, params,
                            user_context=user_context, tenant_id=tenant_id,
                        ),
                        timeout=step_timeout,
                    )
                    latency = (time.perf_counter() - t0) * 1000

                    _add_step("execute", {"tool": tool_name, "params": params},
                              {"success": result.success, "data": result.data},
                              tool_name=tool_name, tool_params=params,
                              tool_result={"success": result.success, "data": result.data},
                              permission="allowed", latency=latency,
                              error=result.error if not result.success else None)

                    if result.success:
                        all_observations.append({"tool": tool_name, "result": result.data})
                        audit.append({"step": "execute", "tool": tool_name, "success": True})
                    else:
                        tool_error_count += 1
                        errors.append({"step": i, "tool": tool_name, "error": result.error})
                        audit.append({"step": "execute", "tool": tool_name, "error": result.error})
                        if tool.max_retries > 0 and total_tool_calls < max_tool_calls - 1:
                            audit.append({"step": "retry", "tool": tool_name, "attempt": 1})

                    total_tool_calls += 1

                except Exception as e:
                    latency = (time.perf_counter() - t0) * 1000
                    tool_error_count += 1
                    error_msg = str(e)
                    # Distinguish timeout from other errors
                    import asyncio
                    if isinstance(e, asyncio.TimeoutError):
                        error_msg = f"harness_step_timeout ({step_timeout}s)"
                    _add_step("execute", {"tool": tool_name, "params": params}, {},
                              tool_name=tool_name, tool_params=params,
                              permission="allowed", latency=latency, error=error_msg)
                    errors.append({"step": i, "tool": tool_name, "error": error_msg})
                    audit.append({"step": "execute", "tool": tool_name, "error": error_msg})

            # Validate observation
            _add_step("observe", {"observations": all_observations[-3:] if all_observations else []},
                      {"count": len(all_observations)})

        # ── Step 4: Draft answer ──
        draft = _generate_draft(objective, all_observations, errors)
        _add_step("evaluate", {"action": "draft"}, {"draft": draft})
        audit.append({"step": "draft", "length": len(draft)})

        # ── Step 4.5: OutputGuard check (between draft and evaluate) ──
        try:
            from app.input_sanitizer import OutputGuard
            output_check = OutputGuard.check(draft)
            if output_check.blocked:
                draft = output_check.sanitized
                audit.append({"step": "output_guard", "blocked": True, "threats": output_check.threats})
        except Exception as e:
            logger.debug("OutputGuard check failed (non-critical): %s", e)

        # ── Step 5: Evaluate (with rewrite loop) ──
        rewrite_count = 0
        eval_result = _evaluate_result(draft, all_observations, errors)
        _add_step("evaluate", {"action": "evaluate"}, eval_result)
        audit.append({"step": "evaluate", "passed": eval_result.get("passed", True)})

        # Rewrite loop: if evaluation fails, augment query and retry
        while (
            not eval_result.get("passed", True)
            and rewrite_count < max_rewrite_attempts
            and "no_observations" not in eval_result.get("issues", [])
        ):
            rewrite_count += 1
            augmented = f"{objective} (补充查询第{rewrite_count}次，请提供更多详情)"
            draft = _generate_draft(augmented, all_observations, errors)
            # Re-check OutputGuard
            try:
                output_check = OutputGuard.check(draft)
                if output_check.blocked:
                    draft = output_check.sanitized
            except Exception:
                pass
            eval_result = _evaluate_result(draft, all_observations, errors)
            _add_step("evaluate", {"action": f"rewrite_evaluate_{rewrite_count}"}, eval_result)
            audit.append({"step": f"rewrite_{rewrite_count}", "passed": eval_result.get("passed", True)})

        # If still not passed after rewrites, flag for human review
        if not eval_result.get("passed", True) and rewrite_count >= max_rewrite_attempts:
            audit.append({"step": "rewrite_exhausted", "forced_pass": True})

        # ── Step 6: HITL check ──
        needs_human = (
            run.risk_level in ("high", "critical")
            or bool(approvals)
            or not eval_result.get("passed", True)
            or (rewrite_count >= max_rewrite_attempts and not eval_result.get("passed", True))
        )
        if needs_human:
            _add_step("approve", {"action": "request_approval"}, {"approvals": approvals})
            audit.append({"step": "hitl", "required": True, "approvals": len(approvals)})
        else:
            audit.append({"step": "hitl", "required": False})

        # ── Step 7: Finalize ──
        total_latency = (time.perf_counter() - t_start) * 1000

        async with get_sessionmaker()() as session:
            run.status = "waiting_approval" if needs_human else "completed"
            run.final_answer = draft
            run.final_action = "human_review_required" if needs_human else "completed"
            run.human_review_required = needs_human
            run.total_steps = len(steps)
            run.total_tool_calls = total_tool_calls
            run.total_latency_ms = total_latency
            run.tool_error_count = tool_error_count
            run.permission_deny_count = perm_deny_count
            run.errors_json = json.dumps(errors, ensure_ascii=False) if errors else None
            run.approvals_json = json.dumps(approvals, ensure_ascii=False) if approvals else None
            run.audit_trace_json = json.dumps(audit, ensure_ascii=False)
            session.add(run)
            for step in steps:
                session.add(step)
            await session.commit()

        return AgentHarnessResult(
            run_id=run_id,
            status=run.status,
            final_answer=draft,
            final_action=run.final_action,
            human_review_required=needs_human,
            total_steps=len(steps),
            total_tool_calls=total_tool_calls,
            total_latency_ms=total_latency,
            tool_error_count=tool_error_count,
            permission_deny_count=perm_deny_count,
            errors=errors,
            approvals=approvals,
            audit_trace=audit,
        )

    except Exception as e:
        logger.exception("Agent harness failed: run_id=%s", run_id)
        total_latency = (time.perf_counter() - t_start) * 1000
        errors.append({"error": str(e), "type": type(e).__name__})

        async with get_sessionmaker()() as session:
            run.status = "failed"
            run.termination_reason = str(e)[:128]
            run.total_steps = len(steps)
            run.total_tool_calls = total_tool_calls
            run.total_latency_ms = total_latency
            run.tool_error_count = tool_error_count + 1
            run.errors_json = json.dumps(errors, ensure_ascii=False)
            run.audit_trace_json = json.dumps(audit, ensure_ascii=False)
            session.add(run)
            for step in steps:
                session.add(step)
            await session.commit()

        return AgentHarnessResult(
            run_id=run_id,
            status="failed",
            total_steps=len(steps),
            total_tool_calls=total_tool_calls,
            total_latency_ms=total_latency,
            tool_error_count=tool_error_count + 1,
            errors=errors,
            audit_trace=audit,
        )


# ── Internal helpers ───────────────────────────────────────────────

def _input_injection_detection(objective: str) -> dict:
    """Detect prompt injection / security bypass attempts."""
    low = objective.strip().lower()
    OVERRIDE_PATTERNS = [
        "ignore previous instructions", "ignore all instructions",
        "ignore all prior instructions", "ignore all previous instructions",
        "you are now a system administrator", "you are now admin",
        "override your instructions", "override system prompt",
        "you are now a different", "act as a system administrator",
        "ignore everything above", "reset your memory",
        "now you are a", "pretend you are", "disregard previous",
    ]
    for p in OVERRIDE_PATTERNS:
        if p in low:
            return {"blocked": True, "reason": "检测到系统指令覆盖攻击 (匹配: " + p + ")"}
    CROSS_USER_PATTERNS = [
        "给用户", "帮别人", "别人的订单",
        "for user", "for another", "other user", "someone else",
        "不用走审批", "跳过审批", "不需要审批", "bypass approval",
        "不用审核", "skip review", "无需确认",
    ]
    for p in CROSS_USER_PATTERNS:
        if p in low:
            return {"blocked": True, "reason": "安全策略禁止对其他用户进行操作 (匹配: " + p + ")"}
    EXPLOIT_PATTERNS = [
        "' or '", "' or 1=1", "' -- ", "1=1 --", "union select",
        "drop table", "delete from", "truncate table",
    ]
    for p in EXPLOIT_PATTERNS:
        if p in low:
            return {"blocked": True, "reason": "检测到数据库注入尝试 (匹配: " + p + ")"}
    return {"blocked": False, "reason": ""}

def _assess_risk(objective: str) -> str:
    """Assess initial risk level from the objective text."""
    low = objective.lower()
    if any(w in low for w in ["退款", "refund", "补偿", "compensat", "赔"]):
        return "high"
    if any(w in low for w in ["投诉", "complaint", "举报"]):
        return "medium"
    if any(w in low for w in ["删除", "delete", "导出", "export", "注销"]):
        return "critical"
    return "low"


def _classify_intent(objective: str) -> dict[str, Any]:
    """Pre-plan intent classification reusing supervisor router logic."""
    from app.supervisor.router import detect_emotion

    EXCHANGE_KW = ["换货", "换个", "换成", "换一件", "换尺码", "换码", "太小", "太大", "尺寸不对", "尺码不合适", "想换"]
    REFUND_KW = ["退款", "退货", "退钱", "不想要", "取消订单", "申请退"]
    TRACKING_KW = ["物流", "快递", "到哪了", "几天到", "发货了吗", "运输", "签收", "查一下", "查快递", "查物流"]
    COMPLAINT_KW = ["投诉", "差评", "举报", "骗子", "假货", "质量问题", "态度差", "要投诉", "太差了", "气死", "骗人"]

    query = objective.strip()
    def match(kw_list):
        return any(kw in query for kw in kw_list)

    if match(EXCHANGE_KW):
        intent, confidence = "exchange", 0.95
    elif match(REFUND_KW):
        intent, confidence = "refund", 0.95
    elif match(TRACKING_KW):
        intent, confidence = "tracking", 0.95
    elif match(COMPLAINT_KW):
        intent, confidence = "complaint", 0.95
    else:
        intent, confidence = "unknown", 0.30

    emotion = detect_emotion(query) if intent == "complaint" else None

    # Extract product keyword
    PRODUCT_KW = ["T恤", "衬衫", "裤子", "裙子", "卫衣", "外套", "鞋", "运动鞋", "包", "手机", "耳机", "手表"]
    order_hint = next((kw for kw in PRODUCT_KW if kw in query), "")

    return {
        "intent": intent,
        "confidence": confidence,
        "emotion": emotion,
        "order_hint": order_hint,
    }


def _build_plan(objective: str, risk_level: str, intent_info: dict[str, Any] | None = None) -> list[dict]:
    """Build an execution plan using LLM-based planning.

    The LLM receives the available tools and the objective, then produces
    a structured plan (list of steps with tool names and params).
    Falls back to rule-based planning if LLM is unavailable.
    """
    try:
        from app.llm import chat_completion
        from app.agent.tool_registry import get_tool_registry

        registry = get_tool_registry()
        tools_desc = []
        for t in registry.list_tools():
            tools_desc.append(f"- {t.name}: {t.description} (risk: {t.risk_level.value}, side_effect: {t.side_effect.value})")
        tools_text = "\n".join(tools_desc)

        system = (
            "你是一个电商售后 Agent 规划器。根据用户目标，生成一个执行计划。\n"
            "计划是一个 JSON 数组，每个步骤包含 type、tool、params。\n"
            "type 可以是 'retrieve'（检索知识库）或 'execute'（调用工具）。\n"
            "只使用下面列出的可用工具，不要发明不存在的工具。\n"
            "params 中的值应基于用户请求推断，不要用占位符。\n"
            "返回纯 JSON，不要包含其他文字。"
        )
        user = (
            f"风险等级: {risk_level}\n"
            f"可用工具:\n{tools_text}\n\n"
            f"用户目标: {objective}\n\n"
            "请生成执行计划 (JSON array):"
        )

        raw = chat_completion(system, user)
        # Parse JSON from LLM response (robust extraction)
        plan = _extract_json_array(raw)
        if plan:
            logger.info("LLM plan generated: %d steps for '%s'", len(plan), objective[:50])
            return plan

        logger.warning("LLM plan parse failed, falling back to rule-based")
    except Exception as e:
        logger.warning("LLM planning failed, falling back: %s", e)

    # Fallback: rule-based planning
    return _build_plan_rule_based(objective, risk_level)


def _build_plan_rule_based(objective: str, risk_level: str) -> list[dict]:
    """Rule-based fallback planner using composite tools."""
    low = objective.lower()
    # Use composite tools for known intents
    if any(w in low for w in ["退款", "refund", "退货", "退钱", "不想要"]):
        return [{"type": "execute", "tool": "process_refund", "params": {"user_id": "current_user", "keyword": objective[:15]}}]
    elif any(w in low for w in ["换货", "exchange", "尺码", "太小", "太大", "想换"]):
        return [{"type": "execute", "tool": "process_exchange", "params": {"user_id": "current_user", "keyword": objective[:15], "query_text": objective}}]
    elif any(w in low for w in ["物流", "track", "快递", "包裹", "到哪了"]):
        return [{"type": "execute", "tool": "process_tracking", "params": {"user_id": "current_user", "keyword": objective[:15]}}]
    elif any(w in low for w in ["投诉", "complaint", "举报", "骗子"]):
        from app.supervisor.router import detect_emotion
        emotion = detect_emotion(objective)
        return [{"type": "execute", "tool": "process_complaint", "params": {"user_id": "current_user", "keyword": objective[:15], "emotion": emotion, "query_text": objective}}]
    else:
        # Fallback: retrieve from knowledge base
        return [{"type": "retrieve", "description": "Search knowledge base for relevant policies"}]


def _generate_draft(objective: str, observations: list[dict], errors: list[dict]) -> str:
    """Generate a draft answer using LLM with tool observations as context."""
    # Build context from observations
    context_parts = []
    for obs in observations[-10:]:
        tool = obs.get("tool", "unknown")
        result = obs.get("result", {})
        if isinstance(result, dict):
            result_summary = json.dumps(result, ensure_ascii=False)[:500]
        else:
            result_summary = str(result)[:500]
        context_parts.append(f"[{tool}]: {result_summary}")

    context = "\n".join(context_parts) if context_parts else "无工具调用结果"
    error_text = json.dumps(errors[-5:], ensure_ascii=False)[:300] if errors else "无错误"

    try:
        from app.llm import chat_completion
        system = (
            "你是一个专业的电商售后客服 Agent。根据用户问题和工具查询结果，生成一个专业、友好的回复。\n"
            "规则：\n"
            "1. 只基于提供的工具结果回答，不要编造信息\n"
            "2. 如果信息不足，明确告知用户需要更多信息或建议联系人工客服\n"
            "3. 对于退款/补偿类问题，说明处理时效和流程\n"
            "4. 回复要简洁、专业、有温度\n"
            "5. 不要暴露内部系统名称或技术细节"
        )
        user = (
            f"用户问题: {objective}\n\n"
            f"工具查询结果:\n{context}\n\n"
            f"执行过程中的错误: {error_text}\n\n"
            "请生成回复:"
        )
        draft = chat_completion(system, user)
        if draft and len(draft) > 10:
            logger.info("LLM draft generated: %d chars", len(draft))
            return draft
    except Exception as e:
        logger.warning("LLM draft generation failed: %s", e)

    # Fallback: template-based draft
    if not observations:
        return f"根据您的请求「{objective}」，我暂时无法获取完整信息，建议联系人工客服处理。"
    parts = []
    for obs in observations[-5:]:
        result = obs.get("result", {})
        if isinstance(result, dict):
            for k, v in result.items():
                if isinstance(v, str) and len(v) < 200:
                    parts.append(f"{k}: {v}")
    if parts:
        return f"处理结果（{objective}）：\n" + "\n".join(f"  - {p}" for p in parts[:10])
    return f"已根据「{objective}」查询相关信息，请查看工单详情。"


def _evaluate_result(draft: str, observations: list[dict], errors: list[dict]) -> dict:
    """Evaluate the result using LLM-based grounding verification.

    Checks:
    1. Does the draft reference the observations?
    2. Are there unsupported claims?
    3. Is the response safe (no PII, no injection)?
    """
    issues = []

    # Basic structural checks
    if len(draft) < 10:
        issues.append("draft_too_short")
    if len(errors) > 0:
        issues.append(f"{len(errors)}_tool_errors")
    if not observations:
        issues.append("no_observations")

    # LLM-based grounding check
    try:
        from app.llm import chat_completion
        obs_text = json.dumps([{"tool": o.get("tool"), "result_keys": list(o.get("result", {}).keys()) if isinstance(o.get("result"), dict) else []} for o in observations[-5:]], ensure_ascii=False)

        system = (
            "你是一个回复质量审查员。检查客服回复是否基于工具查询结果。\n"
            "返回 JSON: {\"grounded\": true/false, \"unsupported_claims\": [...], \"safe\": true/false}\n"
            "grounded=true 表示回复的所有信息都来自工具结果。\n"
            "safe=true 表示没有暴露内部系统名、API key、个人信息。\n"
            "只返回 JSON，不要其他文字。"
        )
        user = (
            f"客服回复:\n{draft[:800]}\n\n"
            f"工具查询结果摘要:\n{obs_text}\n\n"
            "请评估 (JSON):"
        )
        raw = chat_completion(system, user)
        eval_data = _extract_json_object(raw)
        if eval_data:
            grounded = eval_data.get("grounded", False)
            safe = eval_data.get("safe", True)
            unsupported = eval_data.get("unsupported_claims", [])
            if not grounded:
                issues.append("not_grounded")
            if not safe:
                issues.append("unsafe_content")
            if unsupported:
                issues.append(f"unsupported: {unsupported[:3]}")
    except Exception as e:
        logger.warning("LLM evaluation failed: %s", e)

    passed = len(issues) == 0
    return {
        "passed": passed,
        "observations_count": len(observations),
        "error_count": len(errors),
        "draft_length": len(draft),
        "issues": issues,
    }
