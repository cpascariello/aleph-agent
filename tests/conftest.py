"""Shared fixtures for tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aleph_agent_mcp.types import VmRecord


@pytest.fixture
def tmp_inventory(tmp_path: Path) -> Path:
    return tmp_path / "inventory.json"


@pytest.fixture
def sample_vm() -> VmRecord:
    return VmRecord(
        item_hash="abc123",
        name="test-vm",
        crn_hash="crn-hash-1",
        crn_url="https://crn1.example.com",
        compute_units=1,
        created_at="2025-01-01T00:00:00+00:00",
        ttl_expires_at="2025-01-01T04:00:00+00:00",
        hourly_cost=1.425,
        purpose="testing",
        ipv4_host="1.2.3.4",
        ssh_port=31222,
    )


@pytest.fixture
def sample_vm_2() -> VmRecord:
    return VmRecord(
        item_hash="def456",
        name="test-vm-2",
        crn_hash="crn-hash-2",
        crn_url="https://crn2.example.com",
        compute_units=2,
        created_at="2025-01-01T01:00:00+00:00",
        ttl_expires_at="2025-01-01T05:00:00+00:00",
        hourly_cost=2.85,
    )
