"""All Aleph SDK calls. This is the only module that imports from aleph.sdk.

Designed to be the single module rewritten for a future TypeScript port.
"""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal

from aleph.sdk import AlephHttpClient, AuthenticatedAlephHttpClient
from aleph.sdk.client.services.pricing import PricingEntity
from aleph.sdk.client.vm_client import VmClient
from aleph.sdk.conf import settings as sdk_settings
from aleph.sdk.types import Ports, PortFlags, StorageEnum
from aleph_message.models import ItemHash
from aleph_message.models.execution.base import Payment, PaymentType
from aleph_message.models.execution.environment import (
    HostRequirements,
    HypervisorType,
    NodeRequirements,
)

from .types import CrnInfo

logger = logging.getLogger(__name__)

# Map friendly names to rootfs hashes
OS_IMAGE_MAP: dict[str, str] = {
    "ubuntu22": sdk_settings.UBUNTU_22_QEMU_ROOTFS_ID,
    "ubuntu24": sdk_settings.UBUNTU_24_QEMU_ROOTFS_ID,
    "debian12": sdk_settings.DEBIAN_12_QEMU_ROOTFS_ID,
}

# Compute-unit tiers: units → (vcpus, memory_mib, disk_mib)
CU_TIERS: dict[int, tuple[int, int, int]] = {
    1: (1, 2048, 20_480),
    2: (2, 4096, 40_960),
    3: (3, 6144, 61_440),
    4: (4, 8192, 81_920),
    6: (6, 12_288, 122_880),
    8: (8, 16_384, 163_840),
    12: (12, 24_576, 245_760),
}


def _resolve_tier(compute_units: int) -> tuple[int, int, int]:
    """Return (vcpus, memory_mib, disk_mib) for a compute-unit count."""
    if compute_units in CU_TIERS:
        return CU_TIERS[compute_units]
    raise ValueError(
        f"Invalid compute_units={compute_units}. "
        f"Valid: {sorted(CU_TIERS.keys())}"
    )


# ---------------------------------------------------------------------------
# Balance
# ---------------------------------------------------------------------------


async def get_balance(address: str) -> float:
    async with AlephHttpClient() as client:
        balance = await client.get_balances(address)
        return float(balance.credit_balance)


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------


async def get_credit_per_cu_hour() -> float:
    async with AlephHttpClient() as client:
        pricing = await client.pricing.get_pricing_aggregate()
        instance_pricing = pricing[PricingEntity.INSTANCE]
        return float(instance_pricing.price["compute_unit"].credit)


# ---------------------------------------------------------------------------
# CRN Discovery
# ---------------------------------------------------------------------------


async def list_crns(
    min_compute_units: int = 1,
    gpu: bool = False,
) -> list[CrnInfo]:
    vcpus, memory, disk = _resolve_tier(min_compute_units)
    async with AlephHttpClient() as client:
        crn_list = await client.crn.get_crns_list(only_active=True)

    results = []
    for crn in crn_list.crns:
        results.append(_crn_to_info(crn))

    return results


def _crn_to_info(crn) -> CrnInfo:
    """Convert an SDK CRN object to our CrnInfo dataclass."""
    return CrnInfo(
        hash=crn.hash,
        name=crn.name or "",
        url=crn.address,  # 'address' is the URL, per SDK gotcha
        score=0.0,  # not available from SDK CRN object
        version=getattr(crn, "version", None),
        has_gpu=bool(getattr(crn, "gpu_support", False)),
        terms_and_conditions=getattr(crn, "terms_and_conditions", None),
    )


async def find_crn(crn_hash: str) -> CrnInfo | None:
    async with AlephHttpClient() as client:
        crn_list = await client.crn.get_crns_list(only_active=True)
        crn = crn_list.find_crn(crn_hash=crn_hash)
        if crn is None:
            return None
        return _crn_to_info(crn)


# ---------------------------------------------------------------------------
# Instance Lifecycle
# ---------------------------------------------------------------------------


async def create_instance(
    account,
    *,
    crn_hash: str,
    crn_url: str,
    ssh_pubkey: str,
    compute_units: int = 1,
    os_image: str = "ubuntu22",
    name: str = "agent-vm",
    payer_address: str | None = None,
    terms_and_conditions: str | None = None,
) -> tuple[str, str | None, int | None, str | None]:
    """Create an instance and start it.

    Returns (item_hash, ipv4_host, ssh_port, ipv6).
    Networking info may be None if polling fails.
    """
    vcpus, memory, disk = _resolve_tier(compute_units)
    rootfs = OS_IMAGE_MAP.get(os_image)
    if rootfs is None:
        raise ValueError(f"Unknown os_image={os_image!r}. Valid: {list(OS_IMAGE_MAP)}")

    payment = Payment(type=PaymentType.credit, chain=None, receiver=None)

    node_req = NodeRequirements(node_hash=ItemHash(crn_hash))
    if terms_and_conditions:
        node_req.terms_and_conditions = ItemHash(terms_and_conditions)
    requirements = HostRequirements(node=node_req)

    async with AuthenticatedAlephHttpClient(account=account) as client:
        message, status = await client.create_instance(
            rootfs=rootfs,
            rootfs_size=disk,
            payment=payment,
            memory=memory,
            vcpus=vcpus,
            ssh_keys=[ssh_pubkey],
            metadata={"name": name},
            hypervisor=HypervisorType.qemu,
            requirements=requirements,
            address=payer_address,
            channel=sdk_settings.DEFAULT_CHANNEL,
            storage_engine=StorageEnum.storage,
            sync=True,
        )

        item_hash = str(message.item_hash)

        # Set up port forwarding for SSH
        await client.port_forwarder.create_ports(
            item_hash=message.item_hash,
            ports=Ports(root={22: PortFlags(tcp=True, udp=False)}),
        )

    # Notify CRN to boot the VM
    async with VmClient(account, crn_url) as vm:
        await vm.start_instance(vm_id=message.item_hash)

    # Poll for networking info
    ipv4_host, ssh_port, ipv6 = await _poll_networking(account, item_hash)

    return item_hash, ipv4_host, ssh_port, ipv6


async def _poll_networking(
    account, item_hash: str, retries: int = 10, delay: float = 3.0
) -> tuple[str | None, int | None, str | None]:
    """Poll for IPv4 host and SSH port after VM start."""
    for attempt in range(retries):
        try:
            async with AlephHttpClient() as client:
                # Try to get execution info to find networking details
                instances = await client.instance.get_instances(
                    address=account.get_address()
                )
                for inst in instances:
                    if str(inst.item_hash) == item_hash:
                        executions = await client.instance.get_instance_executions_info(
                            [inst]
                        )
                        if executions and item_hash in executions:
                            exec_info = executions[item_hash]
                            ipv4 = getattr(exec_info, "ipv4", None)
                            port = getattr(exec_info, "ssh_port", None)
                            ipv6 = getattr(exec_info, "ipv6", None)
                            if ipv4 or port:
                                return ipv4, port, ipv6
        except Exception as e:
            logger.debug("Polling attempt %d failed: %s", attempt, e)

        if attempt < retries - 1:
            await asyncio.sleep(delay)

    logger.warning("Could not retrieve networking info for %s after %d attempts", item_hash, retries)
    return None, None, None


async def destroy_instance(
    account,
    *,
    item_hash: str,
    crn_url: str,
) -> None:
    """Erase instance on CRN, delete port forwards, forget message."""
    # 1. Erase on CRN
    async with VmClient(account, crn_url) as vm:
        await vm.erase_instance(vm_id=ItemHash(item_hash))

    # 2. Delete port forwards + forget message
    async with AuthenticatedAlephHttpClient(account=account) as client:
        await client.port_forwarder.delete_ports(item_hash=ItemHash(item_hash))
        await client.forget(hashes=[ItemHash(item_hash)], reason="Agent cleanup")


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


async def list_instances(address: str) -> set[str]:
    """Return set of item_hashes for instances associated with address."""
    async with AlephHttpClient() as client:
        instances = await client.instance.get_instances(address=address)
        return {str(inst.item_hash) for inst in instances}
