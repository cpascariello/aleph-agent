"""SDK-independent data types for tool inputs and outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


# ---------------------------------------------------------------------------
# CRN
# ---------------------------------------------------------------------------

@dataclass
class CrnInfo:
    hash: str
    name: str
    url: str
    score: float
    version: str | None = None
    has_gpu: bool = False
    terms_and_conditions: str | None = None


# ---------------------------------------------------------------------------
# VM / Instance
# ---------------------------------------------------------------------------

@dataclass
class VmRecord:
    """Local inventory record for a provisioned VM."""

    item_hash: str
    name: str
    crn_hash: str
    crn_url: str
    compute_units: int
    created_at: str  # ISO-8601
    ttl_expires_at: str | None  # ISO-8601 or None
    hourly_cost: float
    signing_address: str | None = None  # address of the key that created this VM
    purpose: str | None = None
    ssh_user: str = "root"
    ipv4_host: str | None = None
    ssh_port: int | None = None
    ipv6: str | None = None


# ---------------------------------------------------------------------------
# Tool return types
# ---------------------------------------------------------------------------

@dataclass
class BalanceResult:
    balance_credits: float
    burn_rate_per_hour: float
    runway_hours: float | None
    active_vm_count: int
    active_vms: list[VmSummary] = field(default_factory=list)


@dataclass
class VmSummary:
    item_hash: str
    name: str
    status: str
    crn_url: str
    uptime_minutes: float
    cost_so_far: float
    ttl_expires_at: str | None
    ssh_command: str | None
    expired: bool = False


@dataclass
class CreateVmResult:
    item_hash: str
    ssh_command: str | None
    ipv4_host: str | None
    ssh_port: int | None
    ipv6: str | None
    hourly_cost: float
    total_cost_estimate: float
    ttl_expires_at: str | None
    requires_confirmation: bool = False
    confirmation_message: str | None = None
    dry_run: bool = False


@dataclass
class DestroyVmResult:
    status: str
    runtime_minutes: float
    estimated_cost_incurred: float


@dataclass
class ExtendVmResult:
    new_ttl_expires_at: str
    additional_cost_estimate: float


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------

@dataclass
class SafetyCheckResult:
    passed: bool
    reason: str | None = None


@dataclass
class CostEstimate:
    hourly_cost: float
    total_cost: float
    ttl_hours: float
    compute_units: int
