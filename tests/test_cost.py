"""Tests for cost.py — pure math."""

from aleph_agent_mcp.cost import burn_rate, cost_since_creation, estimate_cost, runway_hours
from aleph_agent_mcp.types import VmRecord


def _make_vm(compute_units: int = 1, hourly_cost: float = 1.425) -> VmRecord:
    return VmRecord(
        item_hash="h",
        name="n",
        crn_hash="c",
        crn_url="u",
        compute_units=compute_units,
        created_at="2025-01-01T00:00:00+00:00",
        ttl_expires_at=None,
        hourly_cost=hourly_cost,
    )


class TestEstimateCost:
    def test_one_cu_four_hours(self):
        est = estimate_cost(1, 4.0, 1.425)
        assert est.hourly_cost == 1.425
        assert est.total_cost == 5.7
        assert est.compute_units == 1
        assert est.ttl_hours == 4.0

    def test_two_cu(self):
        est = estimate_cost(2, 1.0, 1.425)
        assert est.hourly_cost == 2.85
        assert est.total_cost == 2.85


class TestBurnRate:
    def test_no_vms(self):
        assert burn_rate([]) == 0.0

    def test_single_vm(self):
        assert burn_rate([_make_vm(1)]) == 1.425

    def test_multiple_vms(self):
        rate = burn_rate([_make_vm(1), _make_vm(2)])
        assert abs(rate - 4.275) < 0.001


class TestRunway:
    def test_normal(self):
        r = runway_hours(100.0, 2.0)
        assert r == 50.0

    def test_no_burn(self):
        assert runway_hours(100.0, 0.0) is None

    def test_negative_burn(self):
        assert runway_hours(100.0, -1.0) is None


class TestCostSinceCreation:
    def test_one_hour(self):
        vm = _make_vm(1, 1.425)
        assert cost_since_creation(vm, 60.0) == 1.425

    def test_half_hour(self):
        vm = _make_vm(1, 1.425)
        assert abs(cost_since_creation(vm, 30.0) - 0.7125) < 0.001
