from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request

from app.metrics import metrics_text, record_http_request

from app.api_guard import ApiGuardMiddleware
from app.config import get_settings
from app.logging_config import setup_logging
from app.routes_agent import router as agent_router
from app.routes_rag import router as rag_router

setup_logging()
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
APP_STATIC_DIR = STATIC_DIR / "app"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    from app.telemetry import setup_telemetry

    setup_telemetry(settings)
    logger.info("Starting %s (debug=%s)", settings.app_name, settings.debug)
    yield
    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(ApiGuardMiddleware)

    @app.middleware("http")
    async def trace_middleware(request: Request, call_next):
        tid = request.headers.get("X-Trace-ID") or request.headers.get(
            "x-trace-id"
        ) or str(uuid.uuid4())
        request.state.trace_id = tid
        response = await call_next(request)
        response.headers["X-Trace-ID"] = tid
        return response

    @app.middleware("http")
    async def metrics_latency_middleware(request: Request, call_next):
        t0 = time.perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        endpoint = getattr(route, "path", None) or request.url.path
        record_http_request(
            request.method,
            endpoint,
            response.status_code,
            time.perf_counter() - t0,
        )
        return response

    app.include_router(rag_router)
    app.include_router(agent_router)

    @app.get("/health")
    def health():
        return {"status": "ok", "app": settings.app_name}

    @app.get("/metrics")
    def metrics():
        return PlainTextResponse(
            metrics_text(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    @app.get("/health/config")
    def health_config():
        """不加载大模型；用于确认路径与密钥是否已配置。"""
        p = Path(settings.qwen_embedding_model_path)
        from app.inference_device import cuda_device_info, resolve_inference_device

        resolved_dev = resolve_inference_device(settings)
        cuda_info = cuda_device_info()

        return {
            "qwen_embedding_model_path": str(p.resolve()),
            "qwen_model_dir_exists": p.is_dir(),
            "zhipu_api_key_configured": bool(settings.zhipuai_api_key),
            "query_rewrite_mode": settings.query_rewrite_mode,
            "inference_device": settings.inference_device,
            "inference_device_resolved": resolved_dev,
            "cuda_device_name": cuda_info.get("device_name"),
            "torch_version": cuda_info.get("torch_version"),
            "torch_cuda_built": cuda_info.get("torch_cuda_built"),
            "torch_cuda_version_built": cuda_info.get("cuda_version_built"),
            "cuda_available": cuda_info.get("cuda_available"),
            "cuda_device_capability": cuda_info.get("device_capability"),
            "zhipu_chat_model": settings.zhipu_chat_model,
            "docs_dir": settings.docs_dir,
                "vector_backend": settings.vector_backend,
            "qdrant_url": settings.qdrant_url,
            "qdrant_path": settings.qdrant_path,
            "chunk_strategy": settings.chunk_strategy,
            "chunk_size_tokens": settings.chunk_size_tokens,
            "chunk_overlap_tokens": settings.chunk_overlap_tokens,
            "domain_router_enabled": settings.domain_router_enabled,
            "domain_router_profiles_path": settings.domain_router_profiles_path,
            "domain_router_enhanced": settings.domain_router_enhanced,
            "domain_router_embedding_enabled": settings.domain_router_embedding_enabled,
            "domain_router_hard_filter": settings.domain_router_hard_filter,
            "domain_router_strict": settings.domain_router_strict,
            "domain_router_fallback_all": settings.domain_router_fallback_all,
            "domain_router_soft_boost_enabled": settings.domain_router_soft_boost_enabled,
            "domain_router_soft_boost_delta": settings.domain_router_soft_boost_delta,
            "behavior_guard_enabled": settings.behavior_guard_enabled,
            "behavior_guard_rules_path": settings.behavior_guard_rules_path,
            "policy_embedding_guard_enabled": settings.policy_embedding_guard_enabled,
            "policy_embedding_threshold": settings.policy_embedding_threshold,
            "policy_llm_guard_enabled": settings.policy_llm_guard_enabled,
            "policy_llm_confidence_threshold": settings.policy_llm_confidence_threshold,
        }

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # 阶段 K：React 构建产物（npm run build → static/app/）
    if APP_STATIC_DIR.is_dir():
        app.mount("/app", StaticFiles(directory=str(APP_STATIC_DIR), html=True), name="app_ui")

        @app.get("/")
        def index_redirect():
            return RedirectResponse(url="/app/")

    elif STATIC_DIR.is_dir():

        @app.get("/")
        def index_redirect_legacy():
            """旧版静态页：static/index.html（Gradio 时代简易 UI）。"""
            return RedirectResponse(url="/static/index.html")

    @app.get("/health/ready", include_in_schema=False)
    async def health_ready():
        """就绪探针：检查 BM25 语料和向量索引是否可用。"""
        try:
            from app.bm25_store import _get_bm25
            _get_bm25(get_settings())
            from app.vector_index import get_vector_index
            idx = get_vector_index()
            if idx is None:
                return {"status": "unhealthy", "reason": "vector index not loaded"}
            return {"status": "ok"}
        except Exception as e:
            return {"status": "unhealthy", "reason": str(e)}

    return app


app = create_app()


@app.get("/health/ready", include_in_schema=False)
async def health_ready():
    """就绪探针：检查 BM25 语料和向量索引是否可用。"""
    try:
        from app.bm25_store import _get_bm25
        _get_bm25(get_settings())
        from app.vector_index import get_vector_index
        idx = get_vector_index()
        if idx is None:
            return {"status": "unhealthy", "reason": "vector index not loaded"}
        return {"status": "ok"}
    except Exception as e:
        return {"status": "unhealthy", "reason": str(e)}
