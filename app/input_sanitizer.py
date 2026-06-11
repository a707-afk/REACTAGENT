"""Input Sanitizer: InputGuard + DocumentSanitizer for prompt injection protection.

Covers the 6 injection categories from the audit guide:
1. 忽略系统指令 (Ignore system instructions)
2. 要求导出系统 prompt (Export system prompt)
3. 要求绕过权限 (Bypass permissions)
4. 文档内恶意指令 (Malicious instructions in documents)
5. 工具参数注入 (Tool parameter injection)
6. 多轮上下文注入 (Multi-turn context injection)

Protection layers:
    Input guard → Retrieval document sanitizer → Tool permission gate → Output guard
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ── Injection patterns ─────────────────────────────────────────────

_SYSTEM_OVERRIDE_PATTERNS = [
    r"忽略.*(?:之前的|以上|所有).*(?:指令|规则|限制)",
    r"ignore\s+(?:all\s+)?(?:previous|above)\s+(?:instructions?|rules?)",
    r"forget\s+(?:everything|all\s+rules?)",
    r"你现在.*(?:角色|身份).*是",
    r"you\s+are\s+now\s+(?:a\s+)?",
    r"act\s+as\s+(?:if\s+you\s+are\s+)?",
    r"从现在开始",
    r"不要.*?(?:拒绝|限制|检查|审核)",
    r"do\s+not\s+(?:refuse|reject|check|filter)",
]

_PROMPT_EXPORT_PATTERNS = [
    r"(?:输出|打印|显示|告诉我).*(?:系统\s*)?prompt",
    r"(?:output|print|show|display|tell\s+me).*(?:system\s*)?prompt",
    r"(?:重复|复述)(?:一下)?(?:你的)?.*(?:指令|规则|设置)",
    r"what\s+(?:are\s+)?(?:your\s+)?instructions",
    r"你的.*(?:配置|设定|规则).*是什么",
]

_PERMISSION_BYPASS_PATTERNS = [
    r"(?:绕过|跳过|无视).*(?:权限|审核|检查|审批)",
    r"bypass\s+(?:permission|check|approval|security)",
    r"(?:不用|不需要|别).*(?:检查|审核|审批|确认)",
    r"skip\s+(?:the\s+)?(?:permission|approval|check)",
    r"sudo\s+",
    r"(?:直接|马上|立刻).*(?:退款|转帐|发券|删除|导出)",
]

_DOCUMENT_INJECTION_PATTERNS = [
    r"<script",
    r"javascript\s*:",
    r"onerror\s*=",
    r"onload\s*=",
    r"<iframe",
    r"<img.*on\w+\s*=",
    r"```\s*(?:system|prompt|instruction)",
]

_TOOL_PARAM_INJECTION_PATTERNS = [
    r"ignore\s+previous\s+instructions",
    r"ignore\s+all\s+instructions",
    r"sudo\s+",
    r"you\s+are\s+now",
    r"act\s+as",
    r"pretend",
]

_MULTI_TURN_INJECTION_PATTERNS = [
    r".*刚才说的是错的.*重新.*",
    r"实际上.*真正的.*(?:指令|规则).*是",
    r"actually.*(?:the\s+)?real.*(?:instruction|rule)",
]


@dataclass
class SanitizerResult:
    clean: bool
    original: str
    sanitized: str
    threats: list[str] = field(default_factory=list)
    blocked: bool = False


class InputGuard:
    """Guard for user input (query, chat messages)."""

    @staticmethod
    def check(text: str) -> SanitizerResult:
        """Check user input for injection patterns.

        Returns a SanitizerResult. If blocked=True, the input should be rejected.
        If threats are found, they are cleaned but the input may pass with a warning.
        """
        threats = []
        blocked = False
        lower = text.lower()

        # Check each category
        for pattern in _SYSTEM_OVERRIDE_PATTERNS:
            if re.search(pattern, lower, re.IGNORECASE):
                threats.append(f"system_override: matched '{pattern[:30]}...'")
                blocked = True
                break

        for pattern in _PROMPT_EXPORT_PATTERNS:
            if re.search(pattern, lower, re.IGNORECASE):
                threats.append(f"prompt_export: matched '{pattern[:30]}...'")
                blocked = True
                break

        for pattern in _PERMISSION_BYPASS_PATTERNS:
            if re.search(pattern, lower, re.IGNORECASE):
                threats.append(f"permission_bypass: matched '{pattern[:30]}...'")
                blocked = True
                break

        for pattern in _TOOL_PARAM_INJECTION_PATTERNS:
            if re.search(pattern, lower, re.IGNORECASE):
                threats.append(f"tool_param_injection: matched '{pattern[:30]}...'")
                blocked = True
                break

        # Multi-turn injection check (less aggressive — only flag, don't block)
        for pattern in _MULTI_TURN_INJECTION_PATTERNS:
            if re.search(pattern, lower, re.IGNORECASE):
                threats.append(f"multi_turn_injection: matched '{pattern[:30]}...'")

        if threats and blocked:
            logger.warning("INPUT_GUARD_BLOCKED threats=%s text_len=%d", threats, len(text))

        return SanitizerResult(
            clean=len(threats) == 0,
            original=text,
            sanitized=text,  # For now, pass through (future: clean the suspicious parts)
            threats=threats,
            blocked=blocked,
        )

    @staticmethod
    def check_params(params: dict[str, Any]) -> SanitizerResult:
        """Check tool parameters for injection."""
        params_str = str(params)
        return InputGuard.check(params_str)


class DocumentSanitizer:
    """Sanitizer for document content ingested into the knowledge base."""

    @staticmethod
    def sanitize(text: str) -> SanitizerResult:
        """Sanitize document content.

        Removes:
        - Script tags and event handlers
        - Hidden prompt injection markers
        - Malicious formatting
        """
        threats = []
        sanitized = text

        for pattern in _DOCUMENT_INJECTION_PATTERNS:
            matches = re.findall(pattern, sanitized, re.IGNORECASE)
            if matches:
                threats.append(f"document_injection: found {len(matches)} matches of '{pattern[:30]}...'")
                sanitized = re.sub(pattern, "[REMOVED]", sanitized, flags=re.IGNORECASE)

        # Also check for prompt injection patterns embedded in documents
        for pattern in _SYSTEM_OVERRIDE_PATTERNS + _PROMPT_EXPORT_PATTERNS:
            if re.search(pattern, sanitized, re.IGNORECASE):
                threats.append(f"embedded_injection: matched '{pattern[:30]}...'")
                sanitized = re.sub(pattern, "[REMOVED]", sanitized, flags=re.IGNORECASE)

        if threats:
            logger.warning("DOCUMENT_SANITIZER threats=%s", threats)

        return SanitizerResult(
            clean=len(threats) == 0,
            original=text,
            sanitized=sanitized,
            threats=threats,
            blocked=len(threats) > 0,
        )


class OutputGuard:
    """Guard for generated output (before sending to user)."""

    @staticmethod
    def check(text: str) -> SanitizerResult:
        """Check generated output for unintended information leakage.

        Checks for:
        - System prompt fragments
        - Internal configuration strings
        - API keys / tokens
        """
        threats = []

        # Check for internal strings
        if "system prompt" in text.lower() or "系统提示" in text:
            threats.append("output: system prompt reference detected")

        # Check for API key patterns
        if re.search(r'sk-[a-zA-Z0-9]{20,}', text):
            threats.append("output: potential API key exposure")

        # Check for internal URLs
        if "token.sensenova.cn" in text and "api" in text:
            threats.append("output: internal API endpoint reference")

        return SanitizerResult(
            clean=len(threats) == 0,
            original=text,
            sanitized=text,
            threats=threats,
            blocked=len(threats) > 0,
        )
