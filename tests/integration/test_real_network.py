"""Integration tests against real Aleph network.

Run with: ALEPH_AGENT_RUN_INTEGRATION=1 python3.11 -m pytest tests/integration/ -v
These tests are skipped by default.
"""

from __future__ import annotations

import os

import pytest

from aleph_agent_mcp import server

pytestmark = pytest.mark.skipif(
    os.environ.get("ALEPH_AGENT_RUN_INTEGRATION") != "1",
    reason="Set ALEPH_AGENT_RUN_INTEGRATION=1 to run integration tests",
)


@pytest.mark.asyncio
async def test_check_balance():
    result = await server._check_balance()
    assert "balance_credits" in result
    assert isinstance(result["balance_credits"], (int, float))
    print(f"\nBalance: {result['balance_credits']} credits")
    print(f"Active VMs: {result['active_vm_count']}")
    print(f"Burn rate: {result['burn_rate_per_hour']} credits/hour")
    if result.get("warnings"):
        print(f"Warnings: {result['warnings']}")


@pytest.mark.asyncio
async def test_list_crns():
    result = await server._list_crns()
    assert isinstance(result, list)
    assert len(result) > 0
    assert "hash" in result[0]
    print(f"\nFound {len(result)} active CRNs")
    for crn in result[:5]:
        print(f"  {crn['name']}: score={crn['score']} url={crn['url']}")


@pytest.mark.asyncio
async def test_create_vm_dry_run():
    """Dry run against a known CRN — no real provisioning."""
    result = await server._create_vm(
        name="integration-test",
        crn_hash="d02cc93b18e23f62556cc574fa3696b350cae36e760c43186cbb866c6677c628",
        dry_run=True,
    )
    assert result["dry_run"] is True
    assert result["hourly_cost"] > 0
    print(f"\nDry run result:")
    print(f"  Hourly cost: {result['hourly_cost']} credits")
    print(f"  Total estimate: {result['total_cost_estimate']} credits")
    print(f"  TTL expires: {result['ttl_expires_at']}")


@pytest.mark.asyncio
async def test_list_my_vms():
    result = await server._list_my_vms()
    assert isinstance(result, list)
    print(f"\nInventory: {len(result)} VMs")
    for vm in result:
        print(f"  {vm.get('name', 'unknown')}: status={vm.get('status')} hash={vm['item_hash'][:16]}...")
