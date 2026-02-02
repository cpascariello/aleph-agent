"""Tests for aleph_ops.py — SDK wrappers with mocked clients."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aleph_agent_mcp import aleph_ops


@pytest.mark.asyncio
class TestGetBalance:
    async def test_returns_float(self):
        mock_balance = MagicMock()
        mock_balance.credit_balance = 500

        mock_client = AsyncMock()
        mock_client.get_balances = AsyncMock(return_value=mock_balance)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("aleph_agent_mcp.aleph_ops.AlephHttpClient", return_value=mock_client):
            result = await aleph_ops.get_balance("0xtest")
            assert result == 500.0
            assert isinstance(result, float)


@pytest.mark.asyncio
class TestGetCreditPerCuHour:
    async def test_returns_float(self):
        from decimal import Decimal

        mock_price = MagicMock()
        mock_price.credit = Decimal("1.425")

        mock_pricing = MagicMock()
        mock_pricing.price = {"compute_unit": mock_price}

        mock_client = AsyncMock()
        mock_client.pricing = MagicMock()
        mock_client.pricing.get_pricing_aggregate = AsyncMock(
            return_value={MagicMock(): mock_pricing}
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        # We need to mock PricingEntity to match the dict key
        with patch("aleph_agent_mcp.aleph_ops.AlephHttpClient", return_value=mock_client), \
             patch("aleph_agent_mcp.aleph_ops.PricingEntity") as mock_pe:
            # Make the dict lookup work by using the same key
            mock_client.pricing.get_pricing_aggregate.return_value = {
                mock_pe.INSTANCE: mock_pricing
            }
            result = await aleph_ops.get_credit_per_cu_hour()
            assert result == 1.425


class TestResolveTier:
    def test_valid_tiers(self):
        assert aleph_ops._resolve_tier(1) == (1, 2048, 20_480)
        assert aleph_ops._resolve_tier(2) == (2, 4096, 40_960)
        assert aleph_ops._resolve_tier(12) == (12, 24_576, 245_760)

    def test_invalid_tier(self):
        with pytest.raises(ValueError, match="Invalid compute_units"):
            aleph_ops._resolve_tier(5)


@pytest.mark.asyncio
class TestListInstances:
    async def test_returns_set(self):
        mock_inst1 = MagicMock()
        mock_inst1.item_hash = "hash1"
        mock_inst2 = MagicMock()
        mock_inst2.item_hash = "hash2"

        mock_client = AsyncMock()
        mock_client.instance = MagicMock()
        mock_client.instance.get_instances = AsyncMock(return_value=[mock_inst1, mock_inst2])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("aleph_agent_mcp.aleph_ops.AlephHttpClient", return_value=mock_client):
            result = await aleph_ops.list_instances("0xtest")
            assert result == {"hash1", "hash2"}
