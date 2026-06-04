"""OPA 外部策略集成（可选，fail-open）。"""
from app.opa.client import query_opa_allow

__all__ = ["query_opa_allow"]
