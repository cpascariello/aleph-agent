"""Tests for safety.py — pure functions, no mocking needed."""

from aleph_agent_mcp.safety import (
    check_balance_guard,
    check_concurrent_limit,
    check_cost_threshold,
    check_session_spend,
    check_ttl_range,
    run_pre_create_checks,
)


class TestTtlRange:
    def test_valid(self):
        assert check_ttl_range(4.0, 24.0).passed is True

    def test_zero(self):
        assert check_ttl_range(0, 24.0).passed is False

    def test_negative(self):
        assert check_ttl_range(-1, 24.0).passed is False

    def test_exceeds_max(self):
        r = check_ttl_range(25.0, 24.0)
        assert r.passed is False
        assert "exceeds max" in r.reason

    def test_at_max(self):
        assert check_ttl_range(24.0, 24.0).passed is True


class TestBalanceGuard:
    def test_sufficient(self):
        # balance=100, cost=10, guard=20% → floor=20, remaining=90 → pass
        assert check_balance_guard(100.0, 10.0, 20.0).passed is True

    def test_insufficient(self):
        # balance=100, cost=85, guard=20% → floor=20, remaining=15 → fail
        r = check_balance_guard(100.0, 85.0, 20.0)
        assert r.passed is False
        assert "guard" in r.reason

    def test_exactly_at_guard(self):
        # balance=100, cost=80, guard=20% → floor=20, remaining=20 → pass
        assert check_balance_guard(100.0, 80.0, 20.0).passed is True


class TestConcurrentLimit:
    def test_under_limit(self):
        assert check_concurrent_limit(2, 3).passed is True

    def test_at_limit(self):
        assert check_concurrent_limit(3, 3).passed is False

    def test_over_limit(self):
        assert check_concurrent_limit(5, 3).passed is False


class TestSessionSpend:
    def test_no_limit(self):
        assert check_session_spend(100.0, 50.0, None).passed is True

    def test_within_limit(self):
        assert check_session_spend(10.0, 20.0, 50.0).passed is True

    def test_exceeds_limit(self):
        r = check_session_spend(40.0, 20.0, 50.0)
        assert r.passed is False
        assert "limit" in r.reason


class TestCostThreshold:
    def test_under_threshold(self):
        assert check_cost_threshold(5.0, 10.0).passed is True

    def test_over_threshold(self):
        r = check_cost_threshold(15.0, 10.0)
        assert r.passed is False
        assert "confirmation" in r.reason.lower()


class TestRunPreCreateChecks:
    def test_all_pass(self):
        r = run_pre_create_checks(
            ttl_hours=4.0,
            max_ttl_hours=24.0,
            balance=100.0,
            estimated_cost=5.0,
            guard_percent=20.0,
            active_vm_count=0,
            max_concurrent=3,
            session_spent=0.0,
            max_session_spend=None,
            cost_threshold=10.0,
        )
        assert r.passed is True

    def test_ttl_fails_first(self):
        r = run_pre_create_checks(
            ttl_hours=30.0,
            max_ttl_hours=24.0,
            balance=100.0,
            estimated_cost=5.0,
            guard_percent=20.0,
            active_vm_count=0,
            max_concurrent=3,
            session_spent=0.0,
            max_session_spend=None,
            cost_threshold=10.0,
        )
        assert r.passed is False
        assert "TTL" in r.reason

    def test_threshold_bypassed_when_confirmed(self):
        r = run_pre_create_checks(
            ttl_hours=4.0,
            max_ttl_hours=24.0,
            balance=100.0,
            estimated_cost=15.0,
            guard_percent=20.0,
            active_vm_count=0,
            max_concurrent=3,
            session_spent=0.0,
            max_session_spend=None,
            cost_threshold=10.0,
            confirmed=True,
        )
        assert r.passed is True

    def test_threshold_blocks_when_not_confirmed(self):
        r = run_pre_create_checks(
            ttl_hours=4.0,
            max_ttl_hours=24.0,
            balance=100.0,
            estimated_cost=15.0,
            guard_percent=20.0,
            active_vm_count=0,
            max_concurrent=3,
            session_spent=0.0,
            max_session_spend=None,
            cost_threshold=10.0,
            confirmed=False,
        )
        assert r.passed is False
        assert "confirmation" in r.reason.lower()
