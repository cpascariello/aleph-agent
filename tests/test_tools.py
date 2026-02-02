"""Tests for server.py tool handlers with mocked aleph_ops."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from aleph_agent_mcp import server
from aleph_agent_mcp.types import CrnInfo, VmRecord


@pytest.fixture(autouse=True)
def reset_session_state():
    """Reset server session state between tests."""
    server._session_spend = 0.0
    server._orphan_check_done = False
    server._credit_per_cu_hour = None
    yield


@pytest.fixture(autouse=True)
def mock_settings(tmp_path: Path):
    """Override settings to use temp paths."""
    inv_path = tmp_path / "inventory.json"
    ssh_path = tmp_path / "id_ed25519.pub"
    ssh_path.write_text("ssh-ed25519 AAAA testkey")
    key_path = tmp_path / "ethereum.key"
    key_path.write_text("0x" + "ab" * 32)

    with patch.object(server.settings, "inventory_path", inv_path), \
         patch.object(server.settings, "ssh_pubkey_path", ssh_path), \
         patch.object(server.settings, "private_key_path", key_path), \
         patch.object(server.settings, "human_address", None), \
         patch.object(server.settings, "max_concurrent_vms", 3), \
         patch.object(server.settings, "default_ttl_hours", 4.0), \
         patch.object(server.settings, "max_ttl_hours", 24.0), \
         patch.object(server.settings, "balance_guard_percent", 20.0), \
         patch.object(server.settings, "cost_threshold", 10.0), \
         patch.object(server.settings, "max_session_spend", None):
        yield inv_path


def _mock_account():
    acc = MagicMock()
    acc.get_address.return_value = "0xagent"
    return acc


@pytest.mark.asyncio
class TestCheckBalance:
    async def test_basic(self, mock_settings):
        with patch.object(server, "_account", return_value=_mock_account()), \
             patch.object(server.aleph_ops, "get_balance", new_callable=AsyncMock, return_value=500.0), \
             patch.object(server.aleph_ops, "get_credit_per_cu_hour", new_callable=AsyncMock, return_value=1.425), \
             patch.object(server.aleph_ops, "list_instances", new_callable=AsyncMock, return_value=set()):
            result = await server._check_balance()
            assert result["balance_credits"] == 500.0
            assert result["active_vm_count"] == 0
            assert result["burn_rate_per_hour"] == 0.0
            assert result["runway_hours"] is None


@pytest.mark.asyncio
class TestListCrns:
    async def test_returns_crns(self):
        crns = [
            CrnInfo(hash="h1", name="CRN-1", url="https://crn1.example.com", score=0.9),
            CrnInfo(hash="h2", name="CRN-2", url="https://crn2.example.com", score=0.8, has_gpu=True),
        ]
        with patch.object(server.aleph_ops, "list_crns", new_callable=AsyncMock, return_value=crns):
            result = await server._list_crns()
            assert len(result) == 2
            assert result[0]["hash"] == "h1"

    async def test_gpu_filter(self):
        crns = [
            CrnInfo(hash="h1", name="CRN-1", url="u", score=0.9, has_gpu=False),
            CrnInfo(hash="h2", name="CRN-2", url="u", score=0.8, has_gpu=True),
        ]
        with patch.object(server.aleph_ops, "list_crns", new_callable=AsyncMock, return_value=crns):
            result = await server._list_crns(gpu=True)
            assert len(result) == 1
            assert result[0]["hash"] == "h2"


@pytest.mark.asyncio
class TestCreateVm:
    async def test_dry_run(self, mock_settings):
        with patch.object(server, "_account", return_value=_mock_account()), \
             patch.object(server.aleph_ops, "get_balance", new_callable=AsyncMock, return_value=500.0), \
             patch.object(server.aleph_ops, "get_credit_per_cu_hour", new_callable=AsyncMock, return_value=1.425):
            result = await server._create_vm(
                name="test", crn_hash="crn1", dry_run=True
            )
            assert result["dry_run"] is True
            assert result["item_hash"] == "(dry run)"
            assert result["hourly_cost"] == 1.425
            assert result["total_cost_estimate"] == 5.7  # 1.425 * 4h default

    async def test_concurrent_limit(self, mock_settings):
        from aleph_agent_mcp import inventory
        # Add 3 VMs to hit the limit
        for i in range(3):
            inventory.add_vm(mock_settings, VmRecord(
                item_hash=f"vm{i}", name=f"vm-{i}", crn_hash="c", crn_url="u",
                compute_units=1, created_at="2099-01-01T00:00:00+00:00",
                ttl_expires_at="2099-01-01T04:00:00+00:00", hourly_cost=1.425,
            ))

        with patch.object(server, "_account", return_value=_mock_account()), \
             patch.object(server.aleph_ops, "get_balance", new_callable=AsyncMock, return_value=500.0), \
             patch.object(server.aleph_ops, "get_credit_per_cu_hour", new_callable=AsyncMock, return_value=1.425):
            result = await server._create_vm(name="test", crn_hash="crn1")
            assert "error" in result
            assert "concurrent" in result["error"].lower()

    async def test_balance_guard(self, mock_settings):
        with patch.object(server, "_account", return_value=_mock_account()), \
             patch.object(server.aleph_ops, "get_balance", new_callable=AsyncMock, return_value=6.0), \
             patch.object(server.aleph_ops, "get_credit_per_cu_hour", new_callable=AsyncMock, return_value=1.425):
            # 1 CU * 4h = 5.7 credits, balance=6, guard=20% → floor=1.2, remaining=0.3 → fail
            result = await server._create_vm(name="test", crn_hash="crn1")
            assert "error" in result
            assert "guard" in result["error"].lower()


@pytest.mark.asyncio
class TestDestroyVm:
    async def test_not_found(self, mock_settings):
        result = await server._destroy_vm(item_hash="nonexistent")
        assert "error" in result

    async def test_success(self, mock_settings):
        from aleph_agent_mcp import inventory
        now = datetime.now(timezone.utc)
        vm = VmRecord(
            item_hash="vm1", name="test", crn_hash="c",
            crn_url="https://crn.example.com",
            compute_units=1, created_at=(now - timedelta(hours=1)).isoformat(),
            ttl_expires_at=(now + timedelta(hours=3)).isoformat(),
            hourly_cost=1.425,
        )
        inventory.add_vm(mock_settings, vm)

        with patch.object(server, "_account", return_value=_mock_account()), \
             patch.object(server.aleph_ops, "destroy_instance", new_callable=AsyncMock):
            result = await server._destroy_vm(item_hash="vm1")
            assert result["status"] == "destroyed"
            assert result["runtime_minutes"] > 0
            # Should be removed from inventory
            assert inventory.find_vm(mock_settings, "vm1") is None


@pytest.mark.asyncio
class TestExtendVm:
    async def test_not_found(self, mock_settings):
        result = await server._extend_vm(item_hash="nope", additional_hours=2.0)
        assert "error" in result

    async def test_success(self, mock_settings):
        from aleph_agent_mcp import inventory
        now = datetime.now(timezone.utc)
        vm = VmRecord(
            item_hash="vm1", name="test", crn_hash="c",
            crn_url="https://crn.example.com",
            compute_units=1, created_at=now.isoformat(),
            ttl_expires_at=(now + timedelta(hours=2)).isoformat(),
            hourly_cost=1.425,
        )
        inventory.add_vm(mock_settings, vm)

        with patch.object(server, "_account", return_value=_mock_account()), \
             patch.object(server.aleph_ops, "get_balance", new_callable=AsyncMock, return_value=500.0), \
             patch.object(server.aleph_ops, "get_credit_per_cu_hour", new_callable=AsyncMock, return_value=1.425):
            result = await server._extend_vm(item_hash="vm1", additional_hours=2.0)
            assert "new_ttl_expires_at" in result
            assert result["additional_cost_estimate"] == 2.85
