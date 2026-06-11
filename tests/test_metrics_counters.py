"""Tests for metrics.py counters — verify no UnboundLocalError crash (M4 fix)."""
from __future__ import annotations

from app.metrics import record_agent_step, record_rate_limit_hit, _stub_agent_steps, _stub_rate_limit_hits


def test_record_agent_step_no_crash():
    """record_agent_step must not raise UnboundLocalError when prometheus is unavailable."""
    # Call multiple times to ensure += works
    record_agent_step("policy")
    record_agent_step("reason")
    record_agent_step("retrieve")


def test_record_rate_limit_hit_no_crash():
    """record_rate_limit_hit must not raise UnboundLocalError when prometheus is unavailable."""
    record_rate_limit_hit()
    record_rate_limit_hit()


def test_record_agent_step_increments():
    """Verify the stub counter actually increments."""
    import app.metrics as m
    before = m._stub_agent_steps
    record_agent_step("test_step")
    assert m._stub_agent_steps == before + 1


def test_record_rate_limit_increments():
    """Verify the stub counter actually increments."""
    import app.metrics as m
    before = m._stub_rate_limit_hits
    record_rate_limit_hit()
    assert m._stub_rate_limit_hits == before + 1
