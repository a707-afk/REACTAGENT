from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 默认指向本机 ModelScope 缓存路径；其他机器请设置环境变量 QWEN_EMBEDDING_MODEL_PATH
_DEFAULT_QWEN_EMBED_PATH = (
    "models/Qwen/Qwen3-Embedding-0___6B"
)
_DEFAULT_QWEN_RERANK_PATH = (
    r"C:\Users\Lenovo\.cache\modelscope\hub\models\Qwen\Qwen3-Reranker-0___6B"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ecom-agent"
    debug: bool = False

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/ecom_agent.db",
        validation_alias=AliasChoices("DATABASE_URL"),
        description="Async DB URL: sqlite+aiosqlite:///... or postgresql+asyncpg://...",
    )
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=10, ge=0, le=100)

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias=AliasChoices("REDIS_URL"),
        description="Redis URL for task queue, distributed cache, rate limiting",
    )
    redis_password: str | None = Field(
        default=None,
        validation_alias=AliasChoices("REDIS_PASSWORD"),
        description="Redis password (if required)",
    )

    # LLM：SenseNova (商汤) DeepSeek-V4-Flash via OpenAI 兼容端点
    sensenova_api_keys: str = Field(default="", description="SenseNova API keys, comma-separated for rotation")

    # VLM：SenseNova (商汤) sensenova-6.7-flash-lite for OCR/multimodal
    vlm_model: str = Field(
        default="sensenova-6.7-flash-lite",
        validation_alias=AliasChoices("VLM_MODEL"),
        description="Vision-Language Model for OCR and image understanding",
    )

    qwen_embedding_model_path: str = Field(default=_DEFAULT_QWEN_EMBED_PATH)

    # 本地 Embedding / Reranker（torch）：auto=有 NVIDIA CUDA 用 GPU，否则 CPU
    inference_device: Literal["auto", "cuda", "cpu"] = Field(
        default="auto",
        description="auto | cuda | cpu：与核显/独显切换时建议 auto",
    )

    # 知识库与向量库（相对运行 cwd，一般为 rag-kb-project）
    docs_dir: str = Field(default="data/docs")
    qdrant_collection_name: str = Field(default="rag_kb")
    vector_backend: Literal["qdrant"] = Field(
        default="qdrant",
        validation_alias=AliasChoices("VECTOR_BACKEND"),
        description="向量后端（仅 qdrant 可用）",
    )
    qdrant_url: str = Field(
        default="http://localhost:6333",
        validation_alias=AliasChoices("QDRANT_URL"),
    )
    qdrant_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("QDRANT_API_KEY"),
    )
    qdrant_path: str | None = Field(
        default=None,
        validation_alias=AliasChoices("QDRANT_PATH"),
        description="本地嵌入式 Qdrant 目录（设此项则不用 Docker / qdrant_url）；未设时默认 data/qdrant_local",
    )

    # 中文知识库 Collection（双 Collection 架构）
    qdrant_collection_name_cn: str = Field(
        default="kb_cn_general",
        validation_alias=AliasChoices("QDRANT_COLLECTION_NAME_CN"),
        description="中文通用售后 FAQ 知识库 Collection",
    )
    docs_dir_cn: str = Field(
        default="data/docs_cn",
        validation_alias=AliasChoices("DOCS_DIR_CN"),
        description="中文 FAQ 知识库文档目录",
    )
    bm25_corpus_path_cn: str = Field(
        default="data/bm25_cn_corpus.jsonl",
        validation_alias=AliasChoices("BM25_CORPUS_PATH_CN"),
        description="中文 BM25 语料路径",
    )

    # 切片：P0 = markdown_heading_overlap；heading_only = 仅按标题不切二次
    chunk_strategy: str = Field(default="markdown_heading_overlap")
    chunk_size_tokens: int = Field(default=512, ge=64)
    chunk_overlap_tokens: int = Field(default=64, ge=0)

    # 检索前 Query Rewrite（LLM）：off=关；on=每次检索必改写；auto=启发式决定是否调用改写
    query_rewrite_mode: Literal["off", "on", "auto"] = Field(default="auto")

    # 混合检索：BM25 + 向量召回合并后再 Rerank（BM25 语料在 reindex 时生成）
    hybrid_bm25_enabled: bool = Field(default=True)
    hybrid_score_normalize: bool = Field(
        default=True,
        validation_alias=AliasChoices("HYBRID_SCORE_NORMALIZE"),
        description="混合召回合并前将向量分与 BM25 分各自 min-max 归一化到 [0,1]，避免 BM25 压过向量",
    )
    hybrid_fusion: Literal["max", "rrf"] = Field(
        default="max",
        validation_alias=AliasChoices("HYBRID_FUSION"),
        description="混合召回融合策略：max=历史分数归一化取最大值；rrf=Reciprocal Rank Fusion",
    )
    hybrid_rrf_k: int = Field(
        default=60,
        ge=1,
        le=1000,
        validation_alias=AliasChoices("HYBRID_RRF_K"),
        description="RRF 融合公式中的 k：score += 1 / (k + rank)",
    )
    bm25_candidate_top_k: int = Field(default=20, ge=1, le=200)
    bm25_corpus_path: str = Field(default="data/bm25_corpus.jsonl")

    # 访问控制：有 user_context 时在向量/BM25 检索前按元数据预筛候选 ID（默认开启）
    access_post_filter_safety_net: bool = Field(
        default=False,
        validation_alias=AliasChoices("ACCESS_POST_FILTER_SAFETY_NET"),
        description="True 时在 merge 后再做一次 Post-filter 兜底；正常仅 Pre-filter",
    )

    # 重排序：`qwen3_causal` 用于 Qwen3-Reranker；`cross_encoder` 用于 BGE 等；`auto` 根据本地 config.json 推断
    rerank_enabled: bool = Field(default=True)
    rerank_backend: str = Field(
        default="auto",
        description="auto | qwen3_causal | cross_encoder",
    )
    rerank_model: str = Field(default=_DEFAULT_QWEN_RERANK_PATH)
    rerank_candidate_top_k: int = Field(default=20, ge=1, le=100)
    qwen_rerank_max_length: int = Field(default=8192, ge=512, le=32768)
    qwen_rerank_batch_size: int = Field(default=4, ge=1, le=32)
    qwen_rerank_instruction: str | None = Field(
        default=None,
        description="可选；与 Qwen 官方 Instruct 一致时不填则用默认英文 instruction",
    )

    # 领域路由：关键词优先 + LLM fallback（见 app/domain_router.py）
    domain_router_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("DOMAIN_ROUTER_ENABLED"),
        description="False 时不调用路由推断（无 router_trace）",
    )
    domain_router_hard_filter: bool = Field(
        default=False,
        validation_alias=AliasChoices("DOMAIN_ROUTER_HARD_FILTER"),
        description="True 时在 rerank 前按 allowed_domains 淘汰候选；默认 False：路由结果仅作 trace",
    )
    domain_router_strict: bool = Field(
        default=False,
        description="仅当 domain_router_hard_filter=True：按域收窄时丢弃无 domain 元数据的 chunk",
    )
    domain_router_fallback_all: bool = Field(
        default=True,
        description="仅当 domain_router_hard_filter=True：按域过滤若无候选是否回退为全库候选",
    )
    domain_router_profiles_path: str = Field(
        default="data/domain_router_profiles.json",
        description="客服领域路由配置文件路径（relative cwd）",
    )

# 检索意图加权：case vs workflow / runbook vs 案例 / 话术 vs 抽检（rerank 前）
    retrieval_intent_boost_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("RETRIEVAL_INTENT_BOOST_ENABLED"),
    )
    retrieval_intent_boost_delta: float = Field(
        default=0.08,
        ge=0.0,
        le=0.5,
        validation_alias=AliasChoices("RETRIEVAL_INTENT_BOOST_DELTA"),
    )
    retrieval_intent_penalty: float = Field(
        default=0.05,
        ge=0.0,
        le=0.5,
        validation_alias=AliasChoices("RETRIEVAL_INTENT_PENALTY"),
    )
    retrieval_intent_boost_max_chunks: int = Field(
        default=8,
        ge=1,
        le=50,
        validation_alias=AliasChoices("RETRIEVAL_INTENT_BOOST_MAX_CHUNKS"),
    )

    # K2（产品语义）：Rerank 之后的门控；最优重排分低于阈值则拒答（见 retrieval_gates）。
    retrieval_gate_enabled: bool = Field(default=True)
    retrieval_similarity_threshold: float = Field(default=0.3, ge=0.0, le=1.0)
    retrieval_score_higher_is_better: bool = Field(
        default=True,
        description="对重排分：True 表示分数越大越相关。False：视为距离类，内部取反后再与阈值比；阈值仍按「越大越好」校准。",
    )
    retrieval_gate_strict_mode: bool = Field(
        default=False,
        description="True 时严格 gate，False 时 relax gate（允许弱匹配通过）",
    )
    retrieval_min_chunks_threshold: int = Field(
        default=1, ge=0, le=10,
        description="至少需要多少个 chunk 才通过 gate",
    )
    refusal_no_results: str = Field(default="知识库中无相关内容")
    refusal_gate_fail: str = Field(default="知识库中无相关内容")

    # 上线前演示：高风险 / 合规短语命中则短路与 RAG（见 app/behavior_guard.py）
    behavior_guard_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("BEHAVIOR_GUARD_ENABLED"),
    )
    behavior_guard_rules_path: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "BEHAVIOR_GUARD_RULES_PATH", "BEHAVIOR_GUARD_RULES"
        ),
        description="可选 JSON 规则包；未设或文件不存在则用 data/behavior_rules.default.json",
    )

    # 策略引擎扩展：向量相似度 / LLM 分类（app/policy/engine.py）
    policy_embedding_guard_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("POLICY_EMBEDDING_GUARD"),
    )
    policy_embedding_threshold: float = Field(
        default=0.72,
        ge=0.0,
        le=1.0,
        validation_alias=AliasChoices("POLICY_EMBEDDING_THRESHOLD"),
    )
    policy_llm_guard_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("POLICY_LLM_GUARD"),
    )
    policy_llm_confidence_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        validation_alias=AliasChoices("POLICY_LLM_CONFIDENCE"),
    )

    # OPA 外部策略（可选，默认 fail-open）
    opa_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("OPA_ENABLED"),
    )
    opa_url: str = Field(
        default="http://localhost:8181",
        validation_alias=AliasChoices("OPA_URL"),
    )
    opa_policy_path: str = Field(
        default="rag/allow",
        validation_alias=AliasChoices("OPA_POLICY_PATH"),
    )
    opa_fail_open: bool = Field(
        default=True,
        validation_alias=AliasChoices("OPA_FAIL_OPEN"),
    )

    # 多 Agent 图（supervisor + escalation 骨架）
    agent_multi_agent_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("AGENT_MULTI_AGENT_ENABLED"),
    )
    agent_grader_mode: str = Field(
        default="auto",
        validation_alias=AliasChoices("AGENT_GRADER_MODE"),
        description="auto | llm | heuristic：Agent grader 模式",
    )
    agent_grader_min_query_overlap: float = Field(
        default=0.12,
        ge=0.0,
        le=1.0,
        validation_alias=AliasChoices("AGENT_GRADER_MIN_QUERY_OVERLAP"),
        description="grader 通过的最小 query-chunk n-gram 重叠率",
    )
    agent_max_draft_attempts: int = Field(
        default=2,
        ge=1,
        le=5,
        validation_alias=AliasChoices("AGENT_MAX_DRAFT_ATTEMPTS"),
        description="grounding 失败后重试 draft 的最大次数",
    )
    agent_rewrite_use_llm: bool = Field(
        default=True,
        validation_alias=AliasChoices("AGENT_REWRITE_USE_LLM"),
        description="Agent 回环中是否使用 LLM 做 query rewrite",
    )
    agent_graph_recursion_limit: int = Field(
        default=20,
        ge=8,
        le=100,
        validation_alias=AliasChoices("AGENT_GRAPH_RECURSION_LIMIT"),
        description="LangGraph invoke recursion_limit 最大步数",
    )
    api_agent_timeout_seconds: float = Field(
        default=120.0,
        ge=10.0,
        le=600.0,
        validation_alias=AliasChoices("API_AGENT_TIMEOUT_SECONDS"),
        description="POST /agent/ticket 的最大等待时间（秒）",
    )
    grounding_strip_unsupported: bool = Field(
        default=True,
        validation_alias=AliasChoices("GROUNDING_STRIP_UNSUPPORTED"),
        description="grounding 检测后是否自动删除无支撑的句子",
    )
    llm_max_retries: int = Field(
        default=2,
        ge=0,
        le=5,
        validation_alias=AliasChoices("LLM_MAX_RETRIES"),
    )
    llm_timeout_seconds: float = Field(
        default=60.0,
        ge=5.0,
        le=300.0,
        validation_alias=AliasChoices("LLM_TIMEOUT_SECONDS"),
    )

    agent_graph_mode: Literal["linear", "multi"] = Field(
        default="linear",
        validation_alias=AliasChoices("AGENT_GRAPH_MODE"),
    )

    # OpenTelemetry / Langfuse（未配置时 no-op）
    otel_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("OTEL_ENABLED"),
    )
    otel_service_name: str = Field(
        default="ecom-agent",
        validation_alias=AliasChoices("OTEL_SERVICE_NAME"),
    )
    otel_exporter_endpoint: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OTEL_EXPORTER_OTLP_ENDPOINT"),
    )
    langfuse_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("LANGFUSE_ENABLED"),
    )
    langfuse_public_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LANGFUSE_PUBLIC_KEY"),
    )
    langfuse_secret_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LANGFUSE_SECRET_KEY"),
    )
    langfuse_host: str = Field(
        default="https://cloud.langfuse.com",
        validation_alias=AliasChoices("LANGFUSE_HOST"),
    )

    # 检索结果缓存（L1 精确 LRU + 可选 L2 语义；进程内，reindex 后 cache_clear）
    # HTTP ???????????? IP ? API Key ???
    api_auth_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("API_AUTH_ENABLED"),
    )
    api_keys: str = Field(
        default="",
        validation_alias=AliasChoices("API_KEYS"),
        description="API 认证密钥，逗号分隔多个 key",
    )
    input_guard_endpoint_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("INPUT_GUARD_ENDPOINT_ENABLED"),
        description="端点级 InputGuard 检查（defense-in-depth，与 HTTP middleware 共存）",
    )
    api_rate_limit_rpm: int = Field(
        default=120,
        ge=0,
        le=10_000,
        validation_alias=AliasChoices("API_RATE_LIMIT_RPM"),
        description="API 速率限制（每分钟请求数），0=不限制",
    )
    api_max_body_bytes: int = Field(
        default=65536,
        ge=0,
        le=10_000_000,
        validation_alias=AliasChoices("API_MAX_BODY_BYTES"),
        description="JSON 请求体最大字节数（Content-Length），0=不限制",
    )

    cache_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("CACHE_ENABLED"),
    )
    cache_max_entries: int = Field(
        default=256,
        ge=8,
        le=10_000,
        validation_alias=AliasChoices("CACHE_MAX_ENTRIES"),
        description="L1 LRU 最大条目数",
    )
    cache_redis_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("CACHE_REDIS_ENABLED"),
        description="L2-Redis 分布式缓存（跨进程共享，Redis 不可用时自动降级到 L1-only）",
    )
    cache_redis_ttl_seconds: int = Field(
        default=600,
        ge=60,
        le=3600,
        validation_alias=AliasChoices("CACHE_REDIS_TTL_SECONDS"),
        description="L2-Redis 缓存 TTL（秒）",
    )
    cache_semantic_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("CACHE_SEMANTIC_ENABLED"),
        description="L3：query embedding 余弦相似度命中（需加载 embedding 模型）",
    )
    cache_semantic_threshold: float = Field(
        default=0.92,
        ge=0.5,
        le=1.0,
        validation_alias=AliasChoices("CACHE_SEMANTIC_THRESHOLD"),
        description="L2 命中阈值；建议在评测集上画 PR 曲线标定",
    )
    cache_semantic_max_entries: int = Field(
        default=128,
        ge=8,
        le=5000,
        validation_alias=AliasChoices("CACHE_SEMANTIC_MAX_ENTRIES"),
    )

    # ── Agent Harness 统一配置 ─────────────────────────────────
    agent_harness_unified: bool = Field(
        default=False,
        validation_alias=AliasChoices("AGENT_HARNESS_UNIFIED"),
        description="/agent/ticket 是否统一走 Harness（True=Harness, False=LangGraph）",
    )
    agent_harness_shadow: bool = Field(
        default=False,
        validation_alias=AliasChoices("AGENT_HARNESS_SHADOW"),
        description="Shadow 模式：并行跑 Harness 但不返回结果，仅日志对比",
    )
    agent_refund_hitl_threshold: float = Field(
        default=500.0,
        ge=0,
        validation_alias=AliasChoices("AGENT_REFUND_HITL_THRESHOLD"),
        description="退款金额超过此阈值触发 HITL 审批",
    )
    agent_max_rewrite_attempts: int = Field(
        default=2,
        ge=0,
        le=5,
        validation_alias=AliasChoices("AGENT_MAX_REWRITE_ATTEMPTS"),
        description="Harness 评估失败后最大 rewrite 重试次数",
    )
    agent_step_timeout_seconds: float = Field(
        default=30.0,
        ge=5,
        le=120,
        validation_alias=AliasChoices("AGENT_STEP_TIMEOUT_SECONDS"),
        description="Harness 单步工具执行超时（秒）",
    )

    @model_validator(mode="after")
    def _default_qdrant_path(self) -> "Settings":
        if self.qdrant_path is None:
            object.__setattr__(self, "qdrant_path", "data/qdrant_local")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
