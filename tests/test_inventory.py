"""Tests for inventory.py — file-based CRUD + reconciliation."""

from __future__ import annotations

from pathlib import Path

from aleph_agent_mcp import inventory
from aleph_agent_mcp.types import VmRecord


class TestCrud:
    def test_add_and_load(self, tmp_inventory: Path, sample_vm: VmRecord):
        inventory.add_vm(tmp_inventory, sample_vm)
        vms = inventory.load_inventory(tmp_inventory)
        assert len(vms) == 1
        assert vms[0].item_hash == "abc123"
        assert vms[0].name == "test-vm"

    def test_add_multiple(self, tmp_inventory: Path, sample_vm: VmRecord, sample_vm_2: VmRecord):
        inventory.add_vm(tmp_inventory, sample_vm)
        inventory.add_vm(tmp_inventory, sample_vm_2)
        vms = inventory.load_inventory(tmp_inventory)
        assert len(vms) == 2

    def test_remove(self, tmp_inventory: Path, sample_vm: VmRecord, sample_vm_2: VmRecord):
        inventory.add_vm(tmp_inventory, sample_vm)
        inventory.add_vm(tmp_inventory, sample_vm_2)
        removed = inventory.remove_vm(tmp_inventory, "abc123")
        assert removed is not None
        assert removed.item_hash == "abc123"
        vms = inventory.load_inventory(tmp_inventory)
        assert len(vms) == 1
        assert vms[0].item_hash == "def456"

    def test_remove_nonexistent(self, tmp_inventory: Path, sample_vm: VmRecord):
        inventory.add_vm(tmp_inventory, sample_vm)
        removed = inventory.remove_vm(tmp_inventory, "nonexistent")
        assert removed is None
        assert len(inventory.load_inventory(tmp_inventory)) == 1

    def test_find(self, tmp_inventory: Path, sample_vm: VmRecord):
        inventory.add_vm(tmp_inventory, sample_vm)
        found = inventory.find_vm(tmp_inventory, "abc123")
        assert found is not None
        assert found.name == "test-vm"

    def test_find_missing(self, tmp_inventory: Path):
        assert inventory.find_vm(tmp_inventory, "nope") is None

    def test_update(self, tmp_inventory: Path, sample_vm: VmRecord):
        inventory.add_vm(tmp_inventory, sample_vm)
        updated = inventory.update_vm(tmp_inventory, "abc123", ipv4_host="5.6.7.8")
        assert updated is not None
        assert updated.ipv4_host == "5.6.7.8"
        # Verify persisted
        found = inventory.find_vm(tmp_inventory, "abc123")
        assert found.ipv4_host == "5.6.7.8"

    def test_empty_inventory(self, tmp_inventory: Path):
        assert inventory.load_inventory(tmp_inventory) == []


class TestExpiredTtls:
    def test_expired(self, tmp_inventory: Path, sample_vm: VmRecord):
        # ttl_expires_at is 2025-01-01T04:00:00 — in the past
        inventory.add_vm(tmp_inventory, sample_vm)
        expired = inventory.check_expired_ttls(tmp_inventory)
        assert len(expired) == 1

    def test_no_ttl(self, tmp_inventory: Path, sample_vm: VmRecord):
        sample_vm.ttl_expires_at = None
        inventory.add_vm(tmp_inventory, sample_vm)
        expired = inventory.check_expired_ttls(tmp_inventory)
        assert len(expired) == 0


class TestReconcile:
    def test_all_synced(self, sample_vm: VmRecord):
        orphans, stale = inventory.reconcile(
            [sample_vm], {"abc123"}
        )
        assert orphans == []
        assert stale == []

    def test_orphan_on_network(self, sample_vm: VmRecord):
        orphans, stale = inventory.reconcile(
            [sample_vm], {"abc123", "xyz789"}
        )
        assert orphans == ["xyz789"]
        assert stale == []

    def test_stale_local(self, sample_vm: VmRecord):
        orphans, stale = inventory.reconcile(
            [sample_vm], set()
        )
        assert orphans == []
        assert len(stale) == 1
        assert stale[0].item_hash == "abc123"

    def test_both(self, sample_vm: VmRecord, sample_vm_2: VmRecord):
        orphans, stale = inventory.reconcile(
            [sample_vm, sample_vm_2], {"abc123", "new-one"}
        )
        assert orphans == ["new-one"]
        assert len(stale) == 1
        assert stale[0].item_hash == "def456"
