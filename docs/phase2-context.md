# Phase 2 Context: MCP Server Build

> This document captures findings from Phase 1 testing and SDK exploration. Load this into context when starting any Phase 2 implementation session.

## Current State

- **Phase 1**: Complete. Instruction profile at `docs/plans/aleph-cloud-agent-instructions.md` — tested end-to-end (create VM, SSH, destroy).
- **Phase 2**: Plan written at `.claude/plans/elegant-cooking-clock.md`. No code yet.
- **Active test VM**: May still be running — check `~/.aleph-agent-inventory.json` and `aleph instance list --json` on session start.

## Account Setup (already done)

- Agent keypair exists at `~/.aleph-im/private-keys/ethereum.key`
- Agent address: `0xD572F0E1FeB93995816280200e55B1739Cd2989b`
- Human address (delegated): `0x08ef886626648443Cc39FCd6700646f5b37E3871`
- Delegation: INSTANCE permission granted from human → agent
- Human credit balance: ~1,000 credits
- SSH key: `~/.ssh/id_ed25519.pub`

## CLI Issues Found During Testing (MCP server must solve these)

1. **`aleph account create` is interactive** — prompts for key name. `echo "ethereum" | aleph account create --chain ETH` works as workaround.
2. **`aleph instance create` has 2 interactive prompts** — rootfs selection and rootfs size. Cannot be piped. Requires pty wrapper. SDK direct avoids this entirely.
3. **`--crn-url` fails silently** — "Provided CRN not found" even with correct URL. `--crn-hash` works. SDK uses `NodeRequirements(node_hash=...)`.
4. **`--json` output has broken JSON** — `instance list --json` embeds `item_content` with literal control characters that break `json.loads()`. SDK returns Python objects.
5. **`instance list --address <PAYER>` returns nothing for delegated instances** — instances created via delegation are listed under the agent's signing key, not the payer's address.
6. **CRN `address` field is a URL, not a wallet** — `owner` is the wallet. The field naming is confusing.
7. **SSH host key conflicts** — CRNs reuse IP:port across VMs. Need `ssh-keygen -R "[host]:port"` or `StrictHostKeyChecking=no`.

## SDK API Surface (verified against aleph-sdk-python 2.3.0)

### Key Imports

```python
from aleph.sdk import AlephHttpClient, AuthenticatedAlephHttpClient
from aleph.sdk.account import _load_account
from aleph.sdk.client.vm_client import VmClient
from aleph.sdk.conf import settings
from aleph.sdk.types import StorageEnum, VmResources, Ports, PortFlags
from aleph.sdk.client.services.pricing import PricingEntity
from aleph_message.models import ItemHash
from aleph_message.models.execution.base import Payment, PaymentType
from aleph_message.models.execution.environment import HostRequirements, NodeRequirements, HypervisorType
```

### Account Loading

```python
from aleph.sdk.account import _load_account
account = _load_account(private_key_path=Path("~/.aleph-im/private-keys/ethereum.key").expanduser())
```

### Balance Check

```python
async with AlephHttpClient() as client:
    balance = await client.get_balances(address)
    # balance.credit_balance: int — this is what matters
    # balance.balance: Decimal — legacy ALEPH tokens, ignore
```

### CRN Discovery

```python
async with AlephHttpClient() as client:
    crn_list = await client.crn.get_crns_list(only_active=True)
    # Filter
    filtered = crn_list.filter_crn(stream_address=True, vm_resources=VmResources(vcpus=1, memory=2048, disk_mib=20480))
    # Find specific
    crn = crn_list.find_crn(crn_hash="d02cc93b...")
```

### Pricing

```python
async with AlephHttpClient() as client:
    pricing = await client.pricing.get_pricing_aggregate()
    instance_pricing = pricing[PricingEntity.INSTANCE]
    credit_per_cu_hour = instance_pricing.price["compute_unit"].credit  # Decimal("1.425")
    tier = instance_pricing.get_closest_tier(compute_unit=2)
```

### OS Image Rootfs Hashes

```python
settings.UBUNTU_22_QEMU_ROOTFS_ID = "4a0f62da42f4478544616519e6f5d58adb1096e069b392b151d47c3609492d0c"
settings.UBUNTU_24_QEMU_ROOTFS_ID = "5330dcefe1857bcd97b7b7f24d1420a7d46232d53f27be280c8a7071d88bd84e"
settings.DEBIAN_12_QEMU_ROOTFS_ID = "b6ff5c3a8205d1ca4c7c3369300eeafff498b558f71b851aa2114afd0a532717"
settings.DEFAULT_ROOTFS_SIZE = 20_480  # MiB
```

### Create Instance (full flow)

```python
payment = Payment(type=PaymentType.credit, chain=None, receiver=None)
requirements = HostRequirements(node=NodeRequirements(node_hash=ItemHash(crn_hash)))

async with AuthenticatedAlephHttpClient(account=account) as client:
    message, status = await client.create_instance(
        rootfs=settings.UBUNTU_22_QEMU_ROOTFS_ID,
        rootfs_size=20480,
        payment=payment,
        memory=2048, vcpus=1,
        ssh_keys=[ssh_pubkey_content],
        metadata={"name": "my-vm"},
        hypervisor=HypervisorType.qemu,
        requirements=requirements,
        address=human_address,  # for delegated mode, or None for direct
        channel=settings.DEFAULT_CHANNEL,
        storage_engine=StorageEnum.storage,
        sync=True,
    )
    # Port forwarding for SSH
    await client.port_forwarder.create_ports(
        item_hash=message.item_hash,
        ports=Ports(root={22: PortFlags(tcp=True, udp=False)})
    )

# Notify CRN to boot the VM
async with VmClient(account, crn_url) as vm:
    status_code, response = await vm.start_instance(vm_id=message.item_hash)

# Then poll for networking info (IPv4 host + mapped SSH port)
```

### Delete Instance (full flow)

```python
# 1. Erase on CRN
async with VmClient(account, crn_url) as vm:
    await vm.erase_instance(vm_id=ItemHash(item_hash))

# 2. Delete port forwards
async with AuthenticatedAlephHttpClient(account=account) as client:
    await client.port_forwarder.delete_ports(item_hash=ItemHash(item_hash))

# 3. Forget the instance message
    await client.forget(hashes=[ItemHash(item_hash)], reason="Agent cleanup")
```

### Listing Instances

```python
async with AlephHttpClient() as client:
    # instances = await client.instance.get_instances(address)
    # allocations = await client.instance.get_instances_allocations(instances)
    # executions = await client.instance.get_instance_executions_info(instances)
```

Note: For delegated instances, query using the agent's address (the signer), not the human's address.

## Key SDK Gotchas

1. **`Ports` uses `root` not `ports`**: `Ports(root={22: PortFlags(tcp=True, udp=False)})`
2. **`credit_balance` is `int`, not `Decimal`** on `BalanceResponse`
3. **`_load_account` is a private function** — import path is `aleph.sdk.account._load_account`
4. **Networking info is not in create response** — must poll `get_instance_executions_info` after start to get IPv4/port
5. **CRN T&C**: Pass `terms_and_conditions=ItemHash(crn.terms_and_conditions)` in `NodeRequirements` to auto-accept
6. **`VmClient` is an async context manager** — always use `async with VmClient(account, url) as vm:`

## Test CRNs (known working)

| Name | URL | Hash | Score |
|------|-----|------|-------|
| NtS9 | https://crn9.nodetoself.org | d02cc93b18e23f62556cc574fa3696b350cae36e760c43186cbb866c6677c628 | 0.969 |
| AlephVision5 | https://vm5.alephvision.eu | d6afd8807356ab9e953316a8cd62235aeef3dfaa9c193ed4f52e1803b4731415 | 0.969 |

## Dependencies (installed versions)

- `aleph-client==1.9.0`
- `aleph-sdk-python==2.3.0`
- FastMCP: needs `fastmcp>=2.0` (to be installed)
- Python 3.11+ required
