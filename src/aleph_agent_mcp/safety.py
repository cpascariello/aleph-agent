"""Pure safety-check functions — no SDK imports."""

from __future__ import annotations

from .types import SafetyCheckResult


def check_ttl_range(ttl_hours: float, max_ttl_hours: float) -> SafetyCheckResult:
    if ttl_hours <= 0:
        return SafetyCheckResult(passed=False, reason="TTL must be positive.")
    if ttl_hours > max_ttl_hours:
        return SafetyCheckResult(
            passed=False,
            reason=f"TTL {ttl_hours}h exceeds max {max_ttl_hours}h.",
        )
    return SafetyCheckResult(passed=True)


def check_balance_guard(
    balance: float, estimated_cost: float, guard_percent: float
) -> SafetyCheckResult:
    """Reject if spending would leave balance below guard_percent of current balance."""
    floor = balance * (guard_percent / 100.0)
    remaining = balance - estimated_cost
    if remaining < floor:
        return SafetyCheckResult(
            passed=False,
            reason=(
                f"Provisioning would leave {remaining:.2f} credits, "
                f"below {guard_percent}% guard ({floor:.2f}). "
                f"Current balance: {balance:.2f}, estimated cost: {estimated_cost:.2f}."
            ),
        )
    return SafetyCheckResult(passed=True)


def check_concurrent_limit(
    active_count: int, max_concurrent: int
) -> SafetyCheckResult:
    if active_count >= max_concurrent:
        return SafetyCheckResult(
            passed=False,
            reason=f"Already at {active_count}/{max_concurrent} concurrent VMs.",
        )
    return SafetyCheckResult(passed=True)


def check_session_spend(
    session_spent: float, additional_cost: float, max_session_spend: float | None
) -> SafetyCheckResult:
    if max_session_spend is None:
        return SafetyCheckResult(passed=True)
    if session_spent + additional_cost > max_session_spend:
        return SafetyCheckResult(
            passed=False,
            reason=(
                f"Session spend would be {session_spent + additional_cost:.2f}, "
                f"exceeding limit of {max_session_spend:.2f}."
            ),
        )
    return SafetyCheckResult(passed=True)


def check_cost_threshold(
    estimated_cost: float, threshold: float
) -> SafetyCheckResult:
    """Returns passed=False when cost exceeds threshold (requires confirmation)."""
    if estimated_cost > threshold:
        return SafetyCheckResult(
            passed=False,
            reason=(
                f"Estimated cost {estimated_cost:.2f} credits exceeds "
                f"confirmation threshold ({threshold:.2f}). "
                f"Call again with confirmation to proceed."
            ),
        )
    return SafetyCheckResult(passed=True)


def run_pre_create_checks(
    *,
    ttl_hours: float,
    max_ttl_hours: float,
    balance: float,
    estimated_cost: float,
    guard_percent: float,
    active_vm_count: int,
    max_concurrent: int,
    session_spent: float,
    max_session_spend: float | None,
    cost_threshold: float,
    confirmed: bool = False,
) -> SafetyCheckResult:
    """Run the full safety chain. Returns first failure or pass."""
    for check in [
        check_ttl_range(ttl_hours, max_ttl_hours),
        check_balance_guard(balance, estimated_cost, guard_percent),
        check_concurrent_limit(active_vm_count, max_concurrent),
        check_session_spend(session_spent, estimated_cost, max_session_spend),
    ]:
        if not check.passed:
            return check

    if not confirmed:
        threshold_check = check_cost_threshold(estimated_cost, cost_threshold)
        if not threshold_check.passed:
            return threshold_check

    return SafetyCheckResult(passed=True)
