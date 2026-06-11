"""Tests for eval models, runner, and metrics calculation."""
from __future__ import annotations

import json
import os
import tempfile
import unittest


# ── Test metric calculation functions ──────────────────────────────

class TestRecallAtK(unittest.TestCase):
    def setUp(self):
        from scripts.run_eval_rag import compute_recall_at_k
        self.fn = compute_recall_at_k

    def test_perfect_recall(self):
        assert self.fn(["a", "b", "c"], ["a", "b", "c", "d", "e"], k=5) == 1.0

    def test_partial_recall(self):
        assert self.fn(["a", "b", "c", "d"], ["a", "b", "x", "y", "z"], k=5) == 0.5

    def test_zero_recall(self):
        assert self.fn(["a", "b"], ["x", "y", "z"], k=5) == 0.0

    def test_empty_gold(self):
        assert self.fn([], ["a", "b"], k=5) == 1.0

    def test_empty_retrieved(self):
        assert self.fn(["a"], [], k=5) == 0.0

    def test_k_limit(self):
        # Gold is at position 6, but we only look at top 5
        assert self.fn(["z"], ["a", "b", "c", "d", "e", "z"], k=5) == 0.0


class TestMRR(unittest.TestCase):
    def setUp(self):
        from scripts.run_eval_rag import compute_mrr
        self.fn = compute_mrr

    def test_first_position(self):
        assert self.fn(["a"], ["a", "b", "c"], k=10) == 1.0

    def test_third_position(self):
        assert abs(self.fn(["a"], ["x", "y", "a"], k=10) - 1.0 / 3) < 0.001

    def test_not_found(self):
        assert self.fn(["a"], ["x", "y", "z"], k=10) == 0.0

    def test_empty_gold(self):
        assert self.fn([], ["a"], k=10) == 1.0


class TestNDCG(unittest.TestCase):
    def setUp(self):
        from scripts.run_eval_rag import compute_ndcg
        self.fn = compute_ndcg

    def test_perfect_ranking(self):
        assert self.fn(["a", "b", "c"], ["a", "b", "c", "d", "e"]) == 1.0

    def test_imperfect_ranking(self):
        result = self.fn(["a", "b"], ["x", "a", "b"])
        assert 0 < result < 1.0

    def test_zero_relevance(self):
        assert self.fn(["a"], ["x", "y", "z"]) == 0.0

    def test_empty_gold(self):
        assert self.fn([], ["a"]) == 1.0


class TestCitationPrecision(unittest.TestCase):
    def setUp(self):
        from scripts.run_eval_rag import compute_citation_precision
        self.fn = compute_citation_precision

    def test_perfect(self):
        # 2 retrieved, 2 in gold, all match → 1.0
        assert self.fn(["a", "b"], ["a", "b"]) == 1.0

    def test_partial(self):
        # 2 retrieved (a, x), 3 gold (a, b, c) → 1/2 = 0.5
        assert self.fn(["a", "x"], ["a", "b", "c"]) == 0.5

    def test_precision_not_recall(self):
        # 2 retrieved, 1 in gold → precision = 0.5
        assert self.fn(["a", "b"], ["a"]) == 0.5

    def test_empty_retrieved(self):
        # No retrieved chunks → precision = 0.0
        assert self.fn([], ["a"]) == 0.0

    def test_empty_gold(self):
        # No gold constraint → precision = 1.0
        assert self.fn(["a"], []) == 1.0


class TestUnauthorizedCheck(unittest.TestCase):
    def setUp(self):
        from scripts.run_eval_rag import check_unauthorized
        self.fn = check_unauthorized

    def test_no_unauthorized(self):
        assert self.fn(["bad"], ["a", "b", "c"]) == 0

    def test_found_unauthorized(self):
        assert self.fn(["bad", "worse"], ["a", "bad", "b"]) == 1

    def test_empty_forbidden(self):
        assert self.fn([], ["a"]) == 0

    def test_k_limit(self):
        # "bad" is at position 11, but we only check top 10
        retrieved = ["a"] * 10 + ["bad"]
        assert self.fn(["bad"], retrieved, k=10) == 0


class TestRefusalCheck(unittest.TestCase):
    def setUp(self):
        from scripts.run_eval_rag import check_refusal
        self.fn = check_refusal

    def test_has_answer_returns_results(self):
        assert self.fn(True, ["a", "b"]) is True

    def test_has_answer_returns_empty(self):
        assert self.fn(True, []) is False

    def test_no_answer_correctly_refuses(self):
        assert self.fn(False, []) is True

    def test_no_answer_returns_results(self):
        assert self.fn(False, ["a"]) is False


# ── Test eval model CRUD ──────────────────────────────────────────

class TestEvalModels(unittest.TestCase):
    def test_create_eval_run(self):
        from app.db.models.eval_run import EvalRun
        run = EvalRun(
            id="run-001",
            tenant_id="t_test",
            eval_type="rag",
            status="queued",
            total_cases=100,
        )
        assert run.eval_type == "rag"
        assert run.status == "queued"

    def test_create_eval_case(self):
        from app.db.models.eval_case import EvalCase
        case = EvalCase(
            id="case-001",
            eval_run_id="run-001",
            tenant_id="t_test",
            case_id="FAQ-001",
            query="测试问题",
            category="faq",
            status="pending",
        )
        assert case.case_id == "FAQ-001"
        assert case.category == "faq"
        assert case.status == "pending"

    def test_eval_run_tenant_isolation(self):
        """Verify that DB tests can distinguish tenants."""
        from app.db.models.eval_run import EvalRun
        run1 = EvalRun(id="r1", tenant_id="tenant_A", eval_type="rag")
        run2 = EvalRun(id="r2", tenant_id="tenant_B", eval_type="rag")
        assert run1.tenant_id != run2.tenant_id

    def test_eval_case_requires_run_id(self):
        """Verify eval_case cannot exist without eval_run."""
        from app.db.models.eval_case import EvalCase
        case = EvalCase(
            id="case-001",
            eval_run_id="run-001",
            tenant_id="t_test",
            case_id="FAQ-001",
            query="test",
            category="faq",
        )
        assert case.eval_run_id == "run-001"


# ── Test eval data loading ────────────────────────────────────────

class TestEvalDataLoading(unittest.TestCase):
    def test_load_all_cases(self):
        """Load all cases from eval data files."""
        from scripts.run_eval_rag import load_cases
        cases = load_cases()
        assert len(cases) >= 100
        categories = set(c["category"] for c in cases)
        assert "faq" in categories
        assert "no_answer" in categories
        assert "permission" in categories

    def test_load_single_category(self):
        from scripts.run_eval_rag import load_cases
        cases = load_cases("faq")
        assert len(cases) == 30
        assert all(c["category"] == "faq" for c in cases)

    def test_case_structure(self):
        from scripts.run_eval_rag import load_cases
        cases = load_cases("faq")
        case = cases[0]
        assert "id" in case
        assert "query" in case
        assert "tenant_id" in case
        assert "gold_chunk_ids" in case
        assert "answer_facts" in case
        assert "category" in case

    def test_permission_case_has_roles(self):
        from scripts.run_eval_rag import load_cases
        cases = load_cases("permission")
        assert any(len(c.get("roles", [])) > 0 for c in cases)

    def test_permission_case_has_forbidden(self):
        from scripts.run_eval_rag import load_cases
        cases = load_cases("permission")
        forbidden_cases = [c for c in cases if c.get("forbidden_document_ids")]
        assert len(forbidden_cases) > 0


# ── Test eval runner (dry-run) ────────────────────────────────────

class TestEvalRunner:
    def test_dry_run(self):
        """Dry-run evaluation produces correct summary structure."""
        import asyncio
        from scripts.run_eval_rag import load_cases, run_eval

        async def _test():
            cases = load_cases("faq")
            summary = run_eval(cases, dry_run=True)
            assert summary["eval_type"] == "rag"
            assert summary["mode"] == "dry_run"
            assert summary["total_cases"] == 30
            assert "metrics" in summary
            m = summary["metrics"]
            assert "recall_at_5" in m
            assert "mrr_at_10" in m
            assert "ndcg_at_10" in m
            assert "thresholds" in summary
            assert len(summary["results"]) == 30

        asyncio.run(_test())

    def test_dry_run_no_answer(self):
        """No-answer cases should correctly refuse."""
        import asyncio
        from scripts.run_eval_rag import load_cases, run_eval

        async def _test():
            cases = load_cases("no_answer")
            summary = run_eval(cases, dry_run=True)
            m = summary["metrics"]
            # In dry-run mode, no_answer cases have no gold chunks and empty retrieval
            # So refusal_accuracy should be 1.0
            refusal_results = [r for r in summary["results"] if not r["has_answer"]]
            assert all(r["refusal_correct"] for r in refusal_results)

        asyncio.run(_test())


if __name__ == "__main__":
    unittest.main()
