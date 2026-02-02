"""Pure cost math — no SDK imports."""

from __future__ import annotations

from .types import CostEstimate, VmRecord

# Default from Aleph pricing aggregate (can be overridden at runtime).
DEFAULT_CREDIT_PER_CU_HOUR: float = 1.425


def estimate_cost(
    compute_units: int,
    ttl_hours: float,
    credit_per_cu_hour: float = DEFAULT_CREDIT_PER_CU_HOUR,
) -> CostEstimate:
    hourly = compute_units * credit_per_cu_hour
    return CostEstimate(
        hourly_cost=hourly,
        total_cost=hourly * ttl_hours,
        ttl_hours=ttl_hours,
        compute_units=compute_units,
    )


def burn_rate(vms: list[VmRecord], credit_per_cu_hour: float = DEFAULT_CREDIT_PER_CU_HOUR) -> float:
    """Total credits/hour burned by all active VMs."""
    return sum(vm.compute_units * credit_per_cu_hour for vm in vms)


def runway_hours(balance: float, current_burn_rate: float) -> float | None:
    """Hours until balance hits zero at current burn rate. None if no burn."""
    if current_burn_rate <= 0:
        return None
    return balance / current_burn_rate


def cost_since_creation(vm: VmRecord, uptime_minutes: float) -> float:
    """Estimated credits consumed by a single VM."""
    return vm.hourly_cost * (uptime_minutes / 60.0)
