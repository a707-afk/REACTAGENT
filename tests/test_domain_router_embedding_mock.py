"""路由模块单元测试：mock Embedding，验证关键词 query → domain 融合。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.domain_router import RouterResult, _legacy_route, route_domains


class TestLegacyRoute(unittest.TestCase):
    def setUp(self) -> None:
        get_settings.cache_clear()

    def test_rule_ticket(self):
        settings = get_settings()
        rr = _legacy_route("工单 SL P1 SLA 怎么处理", settings)
        self.assertEqual(rr.primary_domain, "ticket_workflow")
        self.assertEqual(rr.method, "legacy_rules")

    def test_rule_customer_service(self):
        settings = get_settings()
        rr = _legacy_route("客户登录验证码问题", settings)
        self.assertEqual(rr.primary_domain, "customer_service")


class TestEnhancedEmbeddingMock(unittest.TestCase):
    @patch.dict(
        "os.environ",
        {
            "DOMAIN_ROUTER_USE_EMBEDDING": "true",
            "DOMAIN_ROUTER_LLM_FALLBACK_ENABLED": "false",
            "ZHIPUAI_API_KEY": "",
        },
        clear=False,
    )
    def test_customer_fusion_with_fake_embedding_scores(self):
        get_settings.cache_clear()
        embedding_scores = {
            "customer_service": 0.92,
            "security": 0.05,
            "ticket_workflow": 0.02,
            "operations": 0.01,
            "product": 0.01,
            "internal_policy": 0.01,
            "ai_governance": 0.01,
            "agent_design": 0.01,
            "case": 0.01,
        }

        fake_ret = (
            embedding_scores,
            {"skipped": False, "reason": None},
        )
        with patch("app.domain_router.score_domains_via_embedding", return_value=fake_ret):
            settings = get_settings()
            rr = route_domains(
                "客户账号密码重置与发票退款怎么操作",
                settings,
            )
        self.assertIsInstance(rr, RouterResult)
        self.assertEqual(rr.primary_domain, "customer_service")
        self.assertIn("customer_service", rr.allowed_domains)
        self.assertIsNotNone(rr.routing_trace)


if __name__ == "__main__":
    unittest.main()
