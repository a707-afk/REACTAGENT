from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class UserContext(BaseModel):
    """调用方身份；不传则不做租户/角色过滤（仍可走领域路由）。"""

    user_id: str | None = None
    tenant_id: str | None = None
    roles: list[str] = Field(default_factory=list)
    department: str | None = None
    security_clearance: int = Field(
        default=1,
        ge=0,
        le=10,
        description="数值越大权限越高，用于匹配 security_level 文档密级",
    )


class RetrieveRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=30)
    use_query_rewrite: bool | None = Field(
        default=None,
        description="是否改写检索句：False=禁用；True=强制智谱改写；None=沿用 query_rewrite_mode",
    )
    user_context: UserContext | None = None
    skip_domain_router: bool = Field(
        default=False,
        description=(
            "为 True 时不调用领域路由推断（响应无 router_trace）。"
            "生产默认 False；硬性按域收窄由 DOMAIN_ROUTER_HARD_FILTER（默认 false）控制。"
        ),
    )


class ChunkHit(BaseModel):
    text: str
    score: float | None = None
    file_path: str | None = None
    file_name: str | None = None
    heading: str | None = None
    node_id: str | None = None
    domain: str | None = Field(
        default=None,
        description="文档 front matter 中的 domain",
    )


class RetrieveResponse(BaseModel):
    query: str
    retrieval_query: str | None = Field(
        default=None,
        description="实际用于检索/重排的查询；与 query 相同时为 null",
    )
    chunks: list[ChunkHit]
    gate_passed: bool = True
    error_code: str | None = None
    behavior: str | None = Field(
        default=None,
        description="behavior guard：human_review 表示未走完整检索",
    )
    refusal_reason_code: str | None = Field(
        default=None,
        description="策略护栏原因码（如 POLICY_*），与 error_code 可一致",
    )
    ranked_quality_scores: list[float] = Field(
        default_factory=list,
        description="门控用的分数降序（rerank 开启时为重排分）",
    )
    router_trace: dict | None = Field(
        default=None,
        description="领域路由：allowed_domains, primary_domain, method, confidence",
    )
    trace_id: str | None = None
    policy_risk_level: str | None = Field(
        default=None,
        description="策略引擎综合风险档：high / medium / low",
    )
    policy_action: str | None = Field(
        default=None,
        description="intercept | warn | allow_log",
    )
    policy_warnings: list[str] = Field(
        default_factory=list,
        description="warn 动作时附带的提示（MVP 仍允许继续检索）",
    )
    policy_hits: list[dict[str, Any]] = Field(
        default_factory=list,
        description="规则/向量/LLM 命中明细，供审计与调试",
    )
    requires_human_review: bool | None = Field(
        default=None,
        description="是否需要人工复核（warn / intercept / 向量或 LLM 命中时为 True）",
    )


class ChatRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=30)
    use_query_rewrite: bool | None = Field(default=None, description="同 RetrieveRequest")
    user_context: UserContext | None = None
    skip_domain_router: bool = Field(
        default=False,
        description="同 RetrieveRequest：True 则跳过推断且无 router_trace",
    )


class CitationBlock(BaseModel):
    index: int
    file_path: str | None = None
    file_name: str | None = None
    heading: str | None = None
    excerpt: str


class ChatResponse(BaseModel):
    query: str
    retrieval_query: str | None = Field(
        default=None,
        description="实际用于检索的查询；与 query 相同时为 null",
    )
    answer: str
    citations: list[CitationBlock]
    chunks_used: int
    refused: bool = False
    error_code: str | None = None
    behavior: str | None = Field(
        default=None,
        description="normal | human_review：护栏命中时为 human_review",
    )
    refusal_reason_code: str | None = Field(
        default=None,
        description="策略护栏原因码；与 error_code 对齐时可相同",
    )
    ranked_quality_scores: list[float] = Field(
        default_factory=list,
        description="门控分数降序（rerank 开启时为重排分）",
    )
    router_trace: dict | None = None
    trace_id: str | None = None
    citation_overlap_ratio: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="答案与引用资料的简易字符重叠度（非严格事实校验）",
    )
    grounding: dict[str, Any] | None = Field(
        default=None,
        description="句级溯源报告（GroundingReport.to_dict）；拒绝/无 chunk 时为 null",
    )
    policy_risk_level: str | None = Field(default=None, description="同 RetrieveResponse")
    policy_action: str | None = Field(default=None, description="同 RetrieveResponse")
    policy_warnings: list[str] = Field(default_factory=list)
    policy_hits: list[dict[str, Any]] = Field(default_factory=list)
    requires_human_review: bool | None = Field(default=None)


class TicketAgentRequest(BaseModel):
    ticket_id: str = Field(min_length=1)
    user_query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=30)
    user_context: UserContext | None = None
    customer_id: str | None = None
    customer_tier: str | None = None
    session_id: str | None = None


class TicketAgentResponse(BaseModel):
    ticket_id: str
    user_query: str
    final_action: str
    human_review_required: bool
    draft_reply: str | None = None
    ticket_note: str | None = None
    retrieval_query: str | None = None
    routed_domains: list[str] = Field(default_factory=list)
    retrieved_chunks: list[dict[str, Any]] = Field(default_factory=list)
    gate_passed: bool | None = None
    gate_error_code: str | None = None
    router_trace: dict | None = None
    policy_result: dict[str, Any] | None = None
    audit_trace: list[dict[str, Any]] = Field(default_factory=list)
    trace_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_results: list[dict[str, Any]] | None = None
