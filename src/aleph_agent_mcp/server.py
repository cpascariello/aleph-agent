"""FastMCP server — 6 tool registrations wired to business logic + aleph_ops."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastmcp import FastMCP

from . import aleph_ops, inventory, safety, cost as cost_mod
from .account import load_account, resolve_payer_address, resolve_sender_address
from .config import settings
from .types import (
    BalanceResult,
    CreateVmResult,
    DestroyVmResult,
    ExtendVmResult,
    VmRecord,
    VmSummary,
)

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "aleph-agent",
    instructions="Provision and manage VMs on Aleph Cloud decentralized network.",
)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

_session_spend: float = 0.0
_orphan_check_done: bool = False
_credit_per_cu_hour: float | None = None


async def _get_price() -> float:
    global _credit_per_cu_hour
    if _credit_per_cu_hour is None:
        _credit_per_cu_hour = await aleph_ops.get_credit_per_cu_hour()
    return _credit_per_cu_hour


def _account():
    return load_account(settings.private_key_path)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ssh_command(host: str | None, port: int | None, user: str = "root") -> str | None:
    if not host or not port:
        return None
    return f"ssh -o StrictHostKeyChecking=no {user}@{host} -p {port}"


# ---------------------------------------------------------------------------
# Tool handlers (plain async functions — testable without MCP)
# ---------------------------------------------------------------------------


async def _check_balance() -> dict:
    """Check credit balance, burn rate, runway, and active VMs.

    On first call per session, also runs orphan detection and TTL expiry check.
    """
    global _orphan_check_done

    account = _account()
    address = resolve_sender_address(account, settings.human_address)
    payer = settings.human_address or address

    balance = await aleph_ops.get_balance(payer)
    price = await _get_price()

    vms = inventory.load_inventory(settings.inventory_path)
    rate = cost_mod.burn_rate(vms, price)
    runway = cost_mod.runway_hours(balance, rate)

    # TTL expiry check
    expired = inventory.check_expired_ttls(settings.inventory_path)

    # Orphan detection (once per session)
    warnings: list[str] = []
    if not _orphan_check_done:
        _orphan_check_done = True
        try:
            network_hashes = await aleph_ops.list_instances(address)
            orphans, stale = inventory.reconcile(vms, network_hashes)
            if orphans:
                warnings.append(
                    f"Orphaned VMs on network (not in local inventory): {orphans}"
                )
            if stale:
                hashes = [vm.item_hash for vm in stale]
                warnings.append(
                    f"Stale local records (not found on network): {hashes}. "
                    "Use aleph_destroy_vm to clean up, or verify the signing key matches."
                )
        except Exception as e:
            warnings.append(f"Orphan detection failed: {e}")

    if expired:
        warnings.append(
            f"Expired TTL on VMs: {[vm.item_hash for vm in expired]}. "
            "Consider destroying them."
        )

    now = _now()
    summaries = []
    for vm in vms:
        created = datetime.fromisoformat(vm.created_at)
        uptime = (now - created).total_seconds() / 60.0
        summaries.append(VmSummary(
            item_hash=vm.item_hash,
            name=vm.name,
            status="expired" if vm in expired else "running",
            crn_url=vm.crn_url,
            uptime_minutes=round(uptime, 1),
            cost_so_far=round(cost_mod.cost_since_creation(vm, uptime), 2),
            ttl_expires_at=vm.ttl_expires_at,
            ssh_command=_ssh_command(vm.ipv4_host, vm.ssh_port, vm.ssh_user),
            expired=vm in expired,
        ))

    result = BalanceResult(
        balance_credits=balance,
        burn_rate_per_hour=round(rate, 3),
        runway_hours=round(runway, 1) if runway is not None else None,
        active_vm_count=len(vms),
        active_vms=summaries,
    )

    out = result.__dict__.copy()
    out["active_vms"] = [s.__dict__ for s in result.active_vms]
    if warnings:
        out["warnings"] = warnings
    return out


async def _list_crns(
    min_compute_units: int = 1,
    gpu: bool = False,
) -> list[dict]:
    """List active Compute Resource Nodes (CRNs) on the Aleph network.

    Args:
        min_compute_units: Minimum compute units the CRN must support (default 1).
        gpu: If true, filter for CRNs with GPU support.
    """
    crns = await aleph_ops.list_crns(min_compute_units=min_compute_units, gpu=gpu)
    if gpu:
        crns = [c for c in crns if c.has_gpu]
    return [c.__dict__ for c in crns]


async def _create_vm(
    name: str,
    crn_hash: str,
    compute_units: int = 1,
    ttl_hours: float | None = None,
    os_image: str = "ubuntu22",
    dry_run: bool = False,
    purpose: str | None = None,
    confirmed: bool = False,
) -> dict:
    """Provision a new VM on Aleph Cloud.

    Args:
        name: Human-readable name for the VM.
        crn_hash: Hash of the CRN to deploy on (from aleph_list_crns).
        compute_units: Number of compute units (1-12). 1 CU = 1 vCPU, 2 GiB RAM.
        ttl_hours: Time-to-live in hours (default from config, max from config).
        os_image: OS image — "ubuntu22", "ubuntu24", or "debian12".
        dry_run: If true, return cost estimate without provisioning.
        purpose: Optional description of why this VM is needed.
        confirmed: Set true to bypass cost confirmation threshold.
    """
    global _session_spend

    ttl = ttl_hours if ttl_hours is not None else settings.default_ttl_hours
    price = await _get_price()
    estimate = cost_mod.estimate_cost(compute_units, ttl, price)

    account = _account()
    payer = settings.human_address or resolve_sender_address(account, settings.human_address)
    balance = await aleph_ops.get_balance(payer)

    expired = inventory.check_expired_ttls(settings.inventory_path)
    vms = inventory.load_inventory(settings.inventory_path)
    active_count = len(vms)

    check = safety.run_pre_create_checks(
        ttl_hours=ttl,
        max_ttl_hours=settings.max_ttl_hours,
        balance=balance,
        estimated_cost=estimate.total_cost,
        guard_percent=settings.balance_guard_percent,
        active_vm_count=active_count,
        max_concurrent=settings.max_concurrent_vms,
        session_spent=_session_spend,
        max_session_spend=settings.max_session_spend,
        cost_threshold=settings.cost_threshold,
        confirmed=confirmed,
    )

    if not check.passed:
        is_threshold = (
            not confirmed
            and not safety.check_cost_threshold(
                estimate.total_cost, settings.cost_threshold
            ).passed
        )
        if is_threshold:
            return CreateVmResult(
                item_hash="",
                ssh_command=None,
                ipv4_host=None,
                ssh_port=None,
                ipv6=None,
                hourly_cost=estimate.hourly_cost,
                total_cost_estimate=estimate.total_cost,
                ttl_expires_at=None,
                requires_confirmation=True,
                confirmation_message=check.reason,
                dry_run=False,
            ).__dict__
        return {"error": check.reason}

    ttl_expires = (_now() + timedelta(hours=ttl)).isoformat()

    if dry_run:
        return CreateVmResult(
            item_hash="(dry run)",
            ssh_command=None,
            ipv4_host=None,
            ssh_port=None,
            ipv6=None,
            hourly_cost=estimate.hourly_cost,
            total_cost_estimate=estimate.total_cost,
            ttl_expires_at=ttl_expires,
            dry_run=True,
        ).__dict__

    crn_info = await aleph_ops.find_crn(crn_hash)
    if crn_info is None:
        return {"error": f"CRN {crn_hash} not found or inactive."}

    ssh_pubkey = settings.ssh_pubkey_path.read_text().strip()

    item_hash, ipv4_host, ssh_port, ipv6 = await aleph_ops.create_instance(
        account,
        crn_hash=crn_hash,
        crn_url=crn_info.url,
        ssh_pubkey=ssh_pubkey,
        compute_units=compute_units,
        os_image=os_image,
        name=name,
        payer_address=resolve_payer_address(settings.human_address),
        terms_and_conditions=crn_info.terms_and_conditions,
    )

    record = VmRecord(
        item_hash=item_hash,
        name=name,
        crn_hash=crn_hash,
        crn_url=crn_info.url,
        compute_units=compute_units,
        created_at=_now().isoformat(),
        ttl_expires_at=ttl_expires,
        hourly_cost=estimate.hourly_cost,
        signing_address=account.get_address(),
        purpose=purpose,
        ipv4_host=ipv4_host,
        ssh_port=ssh_port,
        ipv6=ipv6,
    )
    inventory.add_vm(settings.inventory_path, record)

    _session_spend += estimate.total_cost

    warnings = []
    if expired:
        warnings.append(
            f"Note: {len(expired)} VM(s) have expired TTLs. Consider destroying them."
        )

    result = CreateVmResult(
        item_hash=item_hash,
        ssh_command=_ssh_command(ipv4_host, ssh_port),
        ipv4_host=ipv4_host,
        ssh_port=ssh_port,
        ipv6=ipv6,
        hourly_cost=estimate.hourly_cost,
        total_cost_estimate=estimate.total_cost,
        ttl_expires_at=ttl_expires,
    ).__dict__
    if warnings:
        result["warnings"] = warnings
    return result


async def _destroy_vm(item_hash: str) -> dict:
    """Destroy a VM and clean up all resources.

    Args:
        item_hash: The instance item_hash (from aleph_create_vm or aleph_list_my_vms).
    """
    record = inventory.find_vm(settings.inventory_path, item_hash)
    if record is None:
        return {"error": f"VM {item_hash} not found in local inventory."}

    account = _account()
    current_address = account.get_address()

    # Key-match guard: prevent silent no-op when the wrong key is loaded
    if record.signing_address and current_address.lower() != record.signing_address.lower():
        return {
            "error": (
                f"Key mismatch: this VM was created by {record.signing_address}, "
                f"but the current key signs as {current_address}. "
                f"Load the original key to destroy this VM."
            )
        }

    await aleph_ops.destroy_instance(
        account,
        item_hash=item_hash,
        crn_url=record.crn_url,
    )

    inventory.remove_vm(settings.inventory_path, item_hash)

    now = _now()
    created = datetime.fromisoformat(record.created_at)
    runtime = (now - created).total_seconds() / 60.0
    estimated_cost = cost_mod.cost_since_creation(record, runtime)

    return DestroyVmResult(
        status="destroyed",
        runtime_minutes=round(runtime, 1),
        estimated_cost_incurred=round(estimated_cost, 2),
    ).__dict__


async def _list_my_vms() -> list[dict]:
    """List all VMs in local inventory, reconciled with the network.

    Flags orphans (on network but not tracked) and expired TTLs.
    """
    account = _account()
    address = resolve_sender_address(account, settings.human_address)

    vms = inventory.load_inventory(settings.inventory_path)
    price = await _get_price()
    expired_set = {vm.item_hash for vm in inventory.check_expired_ttls(settings.inventory_path)}

    stale_set: set[str] = set()
    try:
        network_hashes = await aleph_ops.list_instances(address)
        orphans, stale = inventory.reconcile(vms, network_hashes)
        stale_set = {vm.item_hash for vm in stale}
    except Exception:
        orphans, stale = [], []

    now = _now()
    results = []
    for vm in vms:
        created = datetime.fromisoformat(vm.created_at)
        uptime = (now - created).total_seconds() / 60.0
        results.append(VmSummary(
            item_hash=vm.item_hash,
            name=vm.name,
            status=(
                "expired" if vm.item_hash in expired_set
                else "stale" if vm.item_hash in stale_set
                else "running"
            ),
            crn_url=vm.crn_url,
            uptime_minutes=round(uptime, 1),
            cost_so_far=round(cost_mod.cost_since_creation(vm, uptime), 2),
            ttl_expires_at=vm.ttl_expires_at,
            ssh_command=_ssh_command(vm.ipv4_host, vm.ssh_port, vm.ssh_user),
            expired=vm.item_hash in expired_set,
        ).__dict__)

    for h in orphans:
        results.append({
            "item_hash": h,
            "name": "(orphan — not in local inventory)",
            "status": "orphan",
            "crn_url": None,
            "uptime_minutes": None,
            "cost_so_far": None,
            "ttl_expires_at": None,
            "ssh_command": None,
            "expired": False,
        })

    return results


async def _extend_vm(item_hash: str, additional_hours: float) -> dict:
    """Extend a VM's TTL (local tracking only — Aleph has no native TTL).

    Args:
        item_hash: The instance item_hash.
        additional_hours: Hours to add to the current TTL.
    """
    global _session_spend

    record = inventory.find_vm(settings.inventory_path, item_hash)
    if record is None:
        return {"error": f"VM {item_hash} not found in local inventory."}

    price = await _get_price()
    additional_cost = record.compute_units * price * additional_hours

    account = _account()
    payer = settings.human_address or resolve_sender_address(account, settings.human_address)
    balance = await aleph_ops.get_balance(payer)

    guard = safety.check_balance_guard(balance, additional_cost, settings.balance_guard_percent)
    if not guard.passed:
        return {"error": guard.reason}

    spend_check = safety.check_session_spend(
        _session_spend, additional_cost, settings.max_session_spend
    )
    if not spend_check.passed:
        return {"error": spend_check.reason}

    if record.ttl_expires_at:
        current_expiry = datetime.fromisoformat(record.ttl_expires_at)
    else:
        current_expiry = _now()

    new_expiry = current_expiry + timedelta(hours=additional_hours)

    created = datetime.fromisoformat(record.created_at)
    total_ttl_hours = (new_expiry - created).total_seconds() / 3600.0
    ttl_check = safety.check_ttl_range(total_ttl_hours, settings.max_ttl_hours)
    if not ttl_check.passed:
        return {"error": ttl_check.reason}

    inventory.update_vm(
        settings.inventory_path, item_hash, ttl_expires_at=new_expiry.isoformat()
    )
    _session_spend += additional_cost

    return ExtendVmResult(
        new_ttl_expires_at=new_expiry.isoformat(),
        additional_cost_estimate=round(additional_cost, 2),
    ).__dict__


# ---------------------------------------------------------------------------
# Register tools on the MCP server (thin wrappers preserve docstrings)
# ---------------------------------------------------------------------------


@mcp.tool()
async def aleph_check_balance() -> dict:
    """Check credit balance, burn rate, runway, and active VMs.

    On first call per session, also runs orphan detection and TTL expiry check.
    """
    return await _check_balance()


@mcp.tool()
async def aleph_list_crns(
    min_compute_units: int = 1,
    gpu: bool = False,
) -> list[dict]:
    """List active Compute Resource Nodes (CRNs) on the Aleph network.

    Args:
        min_compute_units: Minimum compute units the CRN must support (default 1).
        gpu: If true, filter for CRNs with GPU support.
    """
    return await _list_crns(min_compute_units=min_compute_units, gpu=gpu)


@mcp.tool()
async def aleph_create_vm(
    name: str,
    crn_hash: str,
    compute_units: int = 1,
    ttl_hours: float | None = None,
    os_image: str = "ubuntu22",
    dry_run: bool = False,
    purpose: str | None = None,
    confirmed: bool = False,
) -> dict:
    """Provision a new VM on Aleph Cloud.

    Args:
        name: Human-readable name for the VM.
        crn_hash: Hash of the CRN to deploy on (from aleph_list_crns).
        compute_units: Number of compute units (1-12). 1 CU = 1 vCPU, 2 GiB RAM.
        ttl_hours: Time-to-live in hours (default from config, max from config).
        os_image: OS image — "ubuntu22", "ubuntu24", or "debian12".
        dry_run: If true, return cost estimate without provisioning.
        purpose: Optional description of why this VM is needed.
        confirmed: Set true to bypass cost confirmation threshold.
    """
    return await _create_vm(
        name=name,
        crn_hash=crn_hash,
        compute_units=compute_units,
        ttl_hours=ttl_hours,
        os_image=os_image,
        dry_run=dry_run,
        purpose=purpose,
        confirmed=confirmed,
    )


@mcp.tool()
async def aleph_destroy_vm(item_hash: str) -> dict:
    """Destroy a VM and clean up all resources.

    Args:
        item_hash: The instance item_hash (from aleph_create_vm or aleph_list_my_vms).
    """
    return await _destroy_vm(item_hash=item_hash)


@mcp.tool()
async def aleph_list_my_vms() -> list[dict]:
    """List all VMs in local inventory, reconciled with the network.

    Flags orphans (on network but not tracked) and expired TTLs.
    """
    return await _list_my_vms()


@mcp.tool()
async def aleph_extend_vm(item_hash: str, additional_hours: float) -> dict:
    """Extend a VM's TTL (local tracking only — Aleph has no native TTL).

    Args:
        item_hash: The instance item_hash.
        additional_hours: Hours to add to the current TTL.
    """
    return await _extend_vm(item_hash=item_hash, additional_hours=additional_hours)
