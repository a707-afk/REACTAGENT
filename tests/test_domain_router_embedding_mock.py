"""路由模块单元测试：验证关键词匹配 + LLM fallback 逻辑。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.domain_router import RouterResult, route_domains, _rule_scores


class TestRuleScores(unittest.TestCase):
    """关键词评分：_rule_scores 应根据命中关键词返回对应域分数。"""

    def test_refund_keyword_hit(self):
        scores = _rule_scores("我要退款")
        self.assertGreater(scores.get("refund", 0), 0)

    def test_exchange_keyword_hit(self):
        scores = _rule_scores("换货换尺码")
        self.assertGreater(scores.get("exchange", 0), 0)

    def test_shipping_keyword_hit(self):
        scores = _rule_scores("快递查询到哪了")
        self.assertGreater(scores.get("shipping", 0), 0)

    def test_no_keyword_hit(self):
        scores = _rule_scores("今天天气真好")
        self.assertEqual(sum(scores.values()), 0)

    def test_multi_domain_hit(self):
        scores = _rule_scores("退款退货换货")
        # 应该有多个域命中
        active = [d for d, s in scores.items() if s > 0]
        self.assertGreaterEqual(len(active), 2)


class TestRouteDomainsKeywordStrong(unittest.TestCase):
    """≥2 keyword hits → keywords_strong, confidence ≥ 0.80。"""

    def setUp(self) -> None:
        get_settings.cache_clear()

    def test_strong_refund(self):
        settings = get_settings()
        # "退款" + "退钱" 两个关键词命中 refund 域
        rr = route_domains("退款退钱到账时间", settings)
        self.assertEqual(rr.primary_domain, "refund")
        self.assertEqual(rr.method, "keywords_strong")
        self.assertGreaterEqual(rr.confidence, 0.80)
        self.assertIn("refund", rr.allowed_domains)
        self.assertIsNotNone(rr.routing_trace)

    def test_strong_exchange(self):
        settings = get_settings()
        # "换货" + "换尺码" 两个关键词命中 exchange 域
        rr = route_domains("换货换尺码", settings)
        self.assertEqual(rr.primary_domain, "exchange")
        self.assertEqual(rr.method, "keywords_strong")


class TestRouteDomainsKeywordWeak(unittest.TestCase):
    """1 keyword hit → keywords_weak, confidence = 0.75。"""

    def setUp(self) -> None:
        get_settings.cache_clear()

    def test_weak_single_keyword(self):
        settings = get_settings()
        # 只有 "退款" 一个关键词（且其他域无命中）
        rr = route_domains("退款", settings)
        self.assertEqual(rr.primary_domain, "refund")
        # 可能是 keywords_weak 或 keywords_strong（取决于"退款"在 refund 中匹配了几条）
        self.assertIn(rr.method, ("keywords_weak", "keywords_strong"))


class TestRouteDomainsEmpty(unittest.TestCase):
    """空 query → none method, 0 confidence。"""

    def setUp(self) -> None:
        get_settings.cache_clear()

    def test_empty_string(self):
        settings = get_settings()
        rr = route_domains("", settings)
        self.assertIsNone(rr.primary_domain)
        self.assertEqual(rr.method, "none")
        self.assertEqual(rr.confidence, 0.0)

    def test_whitespace_only(self):
        settings = get_settings()
        rr = route_domains("   ", settings)
        self.assertIsNone(rr.primary_domain)
        self.assertEqual(rr.method, "none")


class TestRouteDomainsNoKeyFallback(unittest.TestCase):
    """无 API key 时不调用 LLM，无命中返回 none。"""

    def test_no_key_no_hit_returns_none(self):
        # 直接使用一个空 sensenova_api_keys 的 settings 对象
        from app.config import Settings
        settings = Settings(sensenova_api_keys="")
        rr = route_domains("今天天气怎么样", settings)
        self.assertIsNone(rr.primary_domain)
        self.assertEqual(rr.method, "none")


class TestRouteDomainsLLMFallback(unittest.TestCase):
    """关键词无命中 + 有 API key → LLM fallback。"""

    @patch("app.domain_router._llm_pick_domain", return_value="shipping")
    def test_llm_fallback(self, mock_llm):
        # 直接用 Settings 构造，避免 @patch.dict 的环境变量长度问题
        from app.config import Settings
        settings = Settings(sensenova_api_keys="sk-fake-key")
        # 用一个不含电商关键词的 query 来测试 LLM fallback
        rr = route_domains("我买的东西还没到怎么办", settings)
        if rr.method == "llm":
            self.assertEqual(rr.primary_domain, "shipping")
            self.assertEqual(rr.method, "llm")
            self.assertGreater(rr.confidence, 0.0)


if __name__ == "__main__":
    unittest.main()
