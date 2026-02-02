"""Local JSON inventory CRUD + reconciliation — no SDK imports."""

from __future__ import annotations

import fcntl
import json
from datetime import datetime, timezone
from pathlib import Path

from .types import VmRecord


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_raw(path: Path) -> list[dict]:
    if not path.exists():
        return []
    text = path.read_text()
    if not text.strip():
        return []
    return json.loads(text)


def _save_raw(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            json.dump(records, f, indent=2)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _record_to_dict(r: VmRecord) -> dict:
    return {
        "item_hash": r.item_hash,
        "name": r.name,
        "crn_hash": r.crn_hash,
        "crn_url": r.crn_url,
        "compute_units": r.compute_units,
        "created_at": r.created_at,
        "ttl_expires_at": r.ttl_expires_at,
        "hourly_cost": r.hourly_cost,
        "signing_address": r.signing_address,
        "purpose": r.purpose,
        "ssh_user": r.ssh_user,
        "ipv4_host": r.ipv4_host,
        "ssh_port": r.ssh_port,
        "ipv6": r.ipv6,
    }


def _dict_to_record(d: dict) -> VmRecord:
    return VmRecord(
        item_hash=d["item_hash"],
        name=d.get("name", ""),
        crn_hash=d.get("crn_hash", ""),
        crn_url=d.get("crn_url", ""),
        compute_units=d.get("compute_units", 1),
        created_at=d["created_at"],
        ttl_expires_at=d.get("ttl_expires_at"),
        hourly_cost=d.get("hourly_cost") or d.get("estimated_hourly_cost", 0.0),
        signing_address=d.get("signing_address"),
        purpose=d.get("purpose"),
        ssh_user=d.get("ssh_user", "root"),
        ipv4_host=d.get("ipv4_host"),
        ssh_port=d.get("ssh_port") or d.get("ssh_port_mapped"),
        ipv6=d.get("ipv6"),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_inventory(path: Path) -> list[VmRecord]:
    return [_dict_to_record(d) for d in _load_raw(path)]


def save_inventory(path: Path, records: list[VmRecord]) -> None:
    _save_raw(path, [_record_to_dict(r) for r in records])


def add_vm(path: Path, record: VmRecord) -> None:
    records = load_inventory(path)
    records.append(record)
    save_inventory(path, records)


def remove_vm(path: Path, item_hash: str) -> VmRecord | None:
    records = load_inventory(path)
    removed = None
    kept = []
    for r in records:
        if r.item_hash == item_hash:
            removed = r
        else:
            kept.append(r)
    save_inventory(path, kept)
    return removed


def find_vm(path: Path, item_hash: str) -> VmRecord | None:
    for r in load_inventory(path):
        if r.item_hash == item_hash:
            return r
    return None


def update_vm(path: Path, item_hash: str, **updates: object) -> VmRecord | None:
    records = load_inventory(path)
    target = None
    for r in records:
        if r.item_hash == item_hash:
            target = r
            for k, v in updates.items():
                setattr(r, k, v)
            break
    if target is not None:
        save_inventory(path, records)
    return target


def check_expired_ttls(path: Path) -> list[VmRecord]:
    """Return VMs whose TTL has passed."""
    now = datetime.now(timezone.utc)
    expired = []
    for vm in load_inventory(path):
        if vm.ttl_expires_at is None:
            continue
        expires = datetime.fromisoformat(vm.ttl_expires_at)
        if now >= expires:
            expired.append(vm)
    return expired


def reconcile(
    local: list[VmRecord], network_hashes: set[str]
) -> tuple[list[str], list[VmRecord]]:
    """Compare local inventory against network state.

    Returns:
        orphans: hashes on network but not in local inventory
        stale: local records not found on network
    """
    local_hashes = {vm.item_hash for vm in local}
    orphans = sorted(network_hashes - local_hashes)
    stale = [vm for vm in local if vm.item_hash not in network_hashes]
    return orphans, stale
