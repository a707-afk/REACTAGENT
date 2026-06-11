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

# Budget defaults
DEFAULT_BUDGET = {
    "max_steps": 10,
    "max_tool_calls": 20,
    "max_latency_ms": 120_000,
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
        # ── Step 1: Policy pre-check ──
        _add_step("plan", {"action": "policy_pre_check"}, {"risk_level": run.risk_level})
        audit.append({"step": "policy_pre_check", "risk_level": run.risk_level})

        # ── Step 2: Understand & Plan ──
        plan = _build_plan(objective, run.risk_level)
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

                # Execute tool
                t0 = time.perf_counter()
                try:
                    result = await registry.execute(
                        tool_name, params,
                        user_context=user_context, tenant_id=tenant_id,
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
                    _add_step("execute", {"tool": tool_name, "params": params}, {},
                              tool_name=tool_name, tool_params=params,
                              permission="allowed", latency=latency, error=str(e))
                    errors.append({"step": i, "tool": tool_name, "error": str(e)})
                    audit.append({"step": "execute", "tool": tool_name, "error": str(e)})

            # Validate observation
            _add_step("observe", {"observations": all_observations[-3:] if all_observations else []},
                      {"count": len(all_observations)})

        # ── Step 4: Draft answer ──
        draft = _generate_draft(objective, all_observations, errors)
        _add_step("evaluate", {"action": "draft"}, {"draft": draft})
        audit.append({"step": "draft", "length": len(draft)})

        # ── Step 5: Evaluate ──
        eval_result = _evaluate_result(draft, all_observations, errors)
        _add_step("evaluate", {"action": "evaluate"}, eval_result)
        audit.append({"step": "evaluate", "passed": eval_result.get("passed", True)})

        # ── Step 6: HITL check ──
        needs_human = run.risk_level in ("high", "critical") or bool(approvals) or not eval_result.get("passed", True)
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


def _build_plan(objective: str, risk_level: str) -> list[dict]:
    """Build an execution plan based on objective and risk.

    This is a rule-based planner. In production, this would use LLM-based planning.
    """
    plan = []
    plan.append({"type": "retrieve", "description": "Search knowledge base for relevant policies"})

    low = objective.lower()
    if any(w in low for w in ["退款", "refund"]):
        plan.append({"type": "execute", "tool": "order_lookup", "params": {"user_id": "u001", "keyword": objective[:10]}})
        plan.append({"type": "execute", "tool": "policy_check", "params": {"order_id": "TBD", "return_reason": "申请退款"}})
    elif any(w in low for w in ["换货", "exchange", "尺码"]):
        plan.append({"type": "execute", "tool": "order_lookup", "params": {"user_id": "u001"}})
        plan.append({"type": "execute", "tool": "inventory_query", "params": {"sku": "DEFAULT", "size": "L"}})
        plan.append({"type": "execute", "tool": "create_pickup", "params": {"order_id": "TBD", "address": "default"}})
    elif any(w in low for w in ["物流", "track", "快递", "包裹"]):
        plan.append({"type": "execute", "tool": "order_lookup", "params": {"user_id": "u001"}})
        plan.append({"type": "execute", "tool": "track_shipment", "params": {"order_id": "TBD"}})
    elif any(w in low for w in ["投诉", "complaint"]):
        plan.append({"type": "execute", "tool": "order_lookup", "params": {"user_id": "u001"}})

    return plan


def _generate_draft(objective: str, observations: list[dict], errors: list[dict]) -> str:
    """Generate a draft answer from observations."""
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
    """Evaluate the result: grounding, completeness, safety."""
    passed = len(errors) == 0 and len(draft) > 10
    return {
        "passed": passed,
        "observations_count": len(observations),
        "error_count": len(errors),
        "draft_length": len(draft),
        "issues": errors if not passed else [],
    }
