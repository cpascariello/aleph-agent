# Aleph Cloud VM Provisioning — Agent Instruction Profile

> **Purpose**: This document teaches an AI agent how to provision and manage **standard instances** (virtual machines) on the Aleph Cloud decentralized network using the credit payment system. GPU instances are supported but not the primary focus — see the GPU appendix at the end.
>
> **How to use**: Ingest this entire document into your context. It contains every command, API endpoint, and expected output you need to create, manage, and destroy VMs on Aleph Cloud. Follow the instructions exactly — do not guess parameters or invent API endpoints.
>
> **Payment model**: Aleph Cloud uses a **credit system only**. Credits are denominated in USD. The legacy "hold" and "superfluid" payment types are deprecated. Always use `--payment-type credit`.
>
> **Console**: https://credits.app.aleph.im — for buying credits (manual step by the human).

---

## 1. Prerequisites

### 1.1 Install aleph-client

The `aleph-client` CLI is the primary interface. Install it via pip:

```bash
pip install aleph-client
```

**System dependencies** (Linux only):

```bash
apt-get install -y python3-pip libsecp256k1-dev squashfs-tools
```

**macOS**:

```bash
brew tap cuber/homebrew-libsecp256k1
brew install libsecp256k1
```

Verify installation:

```bash
aleph about version
```

### 1.2 SSH Key

You need an SSH public key to access VMs. If one doesn't exist:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""
```

The default key path `~/.ssh/id_ed25519.pub` is used automatically by `aleph instance create`.

---

## 2. Account Setup

### 2.1 Create a New Account (Keypair)

Generate a new Ethereum-based private key:

```bash
aleph account create --chain ETH
```

**Interactive prompt**: The CLI will ask `Enter a name or path for your private key:`. Type `ethereum` and press Enter (this stores the key with the default name). For non-interactive/automated usage, pipe the key name:

```bash
echo "ethereum" | aleph account create --chain ETH
```

This creates a private key file at `~/.aleph-im/private-keys/ethereum.key`.

**IMPORTANT — Security rules:**
- Never print, log, or transmit the contents of the private key file.
- Never include the private key in command output shown to the user unless they explicitly request it.
- The private key file location is: `~/.aleph-im/private-keys/ethereum.key`
- If an existing key is present, do NOT overwrite it without explicit human approval. Use `--replace` only when instructed.

### 2.2 Display Your Address

```bash
aleph account address
```

**Expected output**: An Ethereum address like `0x1234...abcd`.

Save this address — you need it to check balances and receive credits.

### 2.3 Import an Existing Key

If the human provides a private key:

```bash
aleph account create --private-key <HEX_KEY> --chain ETH
```

Or from a file:

```bash
aleph account create --private-key-file /path/to/key --chain ETH
```

---

## 3. Credit Management

### 3.1 Check Credit Balance

**Via CLI:**

```bash
aleph credits show --json
```

**Via REST API** (no authentication required):

```
GET https://api2.aleph.im/api/v0/addresses/{wallet_address}/balance
```

**Example response:**

```json
{
  "address": "0xb6b5358493af8159b17506c5cc85df69193444bc",
  "balance": 0.0,
  "details": {},
  "locked_amount": 0.0,
  "credit_balance": 10000
}
```

**Key field**: `credit_balance` — this is the number of credits available for spending. This is the number that matters.

The `balance` field refers to legacy ALEPH token holdings, NOT credits. Ignore it for payment purposes.

### 3.2 Check Credit History

**Via CLI:**

```bash
aleph credits history --json
```

**Via REST API** (no authentication required):

```
GET https://api2.aleph.im/api/v0/addresses/{wallet_address}/credit_history
```

**Example response:**

```json
{
  "address": "0xB6B5358493AF8159B17506C5cC85df69193444BC",
  "credit_history": [
    {
      "amount": 390,
      "price": "0.307049...",
      "bonus_amount": 65,
      "tx_hash": "0xe6b253...",
      "token": "ALEPH",
      "chain": "ethereum",
      "provider": "WALLET",
      "payment_method": "token_transfer",
      "message_timestamp": "2026-01-22T01:49:16.487000Z"
    }
  ],
  "pagination_page": 1,
  "pagination_total": 8,
  "pagination_per_page": 0
}
```

**Key fields per entry:**
- `amount`: Credits purchased
- `bonus_amount`: Bonus credits received
- `price`: Price per credit in ALEPH tokens at time of purchase
- `payment_method`: How credits were acquired (`token_transfer` or `credit_transfer`)
- `expiration_date`: If non-null, credits expire on this date

### 3.3 Buy Credits

**This cannot be done programmatically.** The human must buy credits manually via:

- **Credit console**: https://credits.app.aleph.im
- **Method**: Transfer ALEPH tokens, which are converted to USD-denominated credits

When the agent needs more credits, inform the human:

```
Your credit balance is {credit_balance}. The estimated cost for this operation
is {estimated_cost} credits. Please top up your credits at:
https://credits.app.aleph.im
```

### 3.4 Check Pricing

Get credit pricing for standard instances:

```bash
aleph pricing instance --payment-type credit --json
```

**Response structure:**

```json
{
  "price": {
    "compute_unit": {
      "credit": "1.425"
    }
  },
  "compute_unit": {
    "vcpus": 1,
    "memory_mib": 2048,
    "disk_mib": 20480
  },
  "tiers": [
    {"id": "tier-1", "compute_units": 1},
    {"id": "tier-2", "compute_units": 2},
    {"id": "tier-3", "compute_units": 4},
    {"id": "tier-4", "compute_units": 6},
    {"id": "tier-5", "compute_units": 8},
    {"id": "tier-6", "compute_units": 12}
  ]
}
```

**How to read this:**
- 1 compute unit = 1 vCPU, 2048 MiB RAM, 20480 MiB disk
- 1 compute unit costs **1.425 credits/hour**
- Tiers are bundles: tier-2 = 2 compute units = 2 vCPUs, 4096 MiB RAM, 40960 MiB disk = **2.85 credits/hour**

**Cost estimation formula:**

```
hourly_cost = compute_units × 1.425 credits
daily_cost  = hourly_cost × 24
```

**Quick reference table (credit prices):**

| Tier | Compute Units | vCPUs | RAM    | Disk     | Credits/Hour | Credits/Day |
|------|--------------|-------|--------|----------|-------------|------------|
| 1    | 1            | 1     | 2 GiB  | 20 GiB   | 1.43        | 34.20      |
| 2    | 2            | 2     | 4 GiB  | 40 GiB   | 2.85        | 68.40      |
| 3    | 4            | 4     | 8 GiB  | 80 GiB   | 5.70        | 136.80     |
| 4    | 6            | 6     | 12 GiB | 120 GiB  | 8.55        | 205.20     |
| 5    | 8            | 8     | 16 GiB | 160 GiB  | 11.40       | 273.60     |
| 6    | 12           | 12    | 24 GiB | 240 GiB  | 17.10       | 410.40     |

**GPU pricing** is available but out of scope for most agent tasks. If needed, see **Appendix A** at the end of this document, or run:

```bash
aleph pricing gpu --payment-type credit --json
```

### 3.5 Cost Check Before Provisioning

**MANDATORY**: Before creating any instance, always:

1. Check the current credit balance
2. Calculate the estimated cost for the requested duration
3. Present the cost to the human and get confirmation if cost exceeds 10 credits

Example:

```
Provisioning a tier-2 instance (2 vCPUs, 4 GiB RAM):
- Hourly cost: 2.85 credits
- Your balance: 10000 credits
- Estimated runway: ~3,508 hours (~146 days)

Proceed? [y/n]
```

---

## 4. CRN Discovery

### 4.1 List Active Compute Resource Nodes

```bash
aleph node compute --active --json
```

This returns a JSON array of all active CRNs on the network. Each entry contains node metadata including URL, hash, status, and linked CCN.

**Key fields per CRN:**
- `hash`: Unique identifier for the CRN (used with `--crn-hash` in instance create — **preferred method**)
- `address`: CRN's base URL (e.g., `"https://crn9.nodetoself.org"`) — despite the field name, this is a URL, not a wallet address
- `owner`: Node operator's wallet address
- `status`: Node status (the field value is `"linked"` for active nodes; use the `--active` flag to filter)
- `score`: Node reliability score (higher is better, max ~1.0)

### 4.2 Filter CRNs

By specific CRN URL:

```bash
aleph node compute --crn-url "https://crn-example.aleph.cloud" --json
```

By specific CRN hash:

```bash
aleph node compute --crn-hash "abc123..." --json
```

By linked CCN:

```bash
aleph node compute --ccn-hash "def456..." --json
```

### 4.3 CRN Selection Strategy

When selecting a CRN for deployment:

1. Always use `--active` to filter for online nodes only
2. Prefer nodes with higher `score` values
3. If the human has a geographic preference, filter by known CRN URLs
4. For credit-based instances, the CRN must support pay-as-you-go (most active CRNs do)
5. If a specific CRN is not required, you can omit `--crn-hash` and `--crn-url` and let the network assign one during interactive instance creation

---

## 5. VM Lifecycle

### 5.1 Create an Instance

**Basic command (credit payment):**

```bash
aleph instance create \
  --payment-type credit \
  --name "my-instance" \
  --compute-units 2 \
  --ssh-pubkey-file ~/.ssh/id_ed25519.pub \
  --crn-hash "d02cc93b18e23f62556cc574fa3696b350cae36e760c43186cbb866c6677c628" \
  --crn-auto-tac \
  --skip-volume
```

**Interactive prompts**: The CLI will prompt for two values during creation:

1. **Rootfs selection**: `[ubuntu22/ubuntu24/debian12/custom]` — press Enter to accept the default (`ubuntu22`), or type a choice.
2. **Rootfs size**: `Custom Rootfs Size (MiB)` — press Enter to accept the default (determined by your compute-units tier).

**Non-interactive/automated usage**: The CLI rejects piped stdin (`printf` / `echo` won't work). You must use a pseudo-terminal (pty) to send keystrokes. Here is a Python helper that handles both prompts:

```python
import subprocess, pty, os, select, time

def create_instance(args: list[str], timeout: int = 120) -> tuple[str, int]:
    """Run aleph instance create with args, auto-answering interactive prompts.
    Returns (output_text, exit_code)."""
    cmd = ["aleph", "instance", "create"] + args
    master, slave = pty.openpty()
    proc = subprocess.Popen(cmd, stdin=slave, stdout=slave, stderr=slave, close_fds=True)
    os.close(slave)

    output = b""
    prompts_handled = set()
    try:
        while proc.poll() is None:
            r, _, _ = select.select([master], [], [], 10)
            if r:
                output += os.read(master, 4096)
                text = output.decode("utf-8", errors="replace")
                if "ubuntu22/ubuntu24" in text and "rootfs" not in prompts_handled:
                    time.sleep(0.3)
                    os.write(master, b"\n")  # accept default ubuntu22
                    prompts_handled.add("rootfs")
                elif "Custom Rootfs Size" in text and "size" not in prompts_handled:
                    time.sleep(0.3)
                    os.write(master, b"\n")  # accept default size
                    prompts_handled.add("size")
    except OSError:
        pass
    finally:
        try:
            output += os.read(master, 65536)
        except OSError:
            pass
        os.close(master)
        proc.wait(timeout=timeout)
    return output.decode("utf-8", errors="replace"), proc.returncode
```

**Example call:**

```python
output, code = create_instance([
    "--payment-type", "credit",
    "--name", "my-instance",
    "--compute-units", "2",
    "--crn-hash", "CRN_HASH_HERE",
    "--crn-auto-tac",
    "--skip-volume",
])
```

**Parameter reference:**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--payment-type credit` | **YES** | Always use `credit`. Never use `hold` or `superfluid`. |
| `--name` | No | Human-readable name for the instance |
| `--compute-units` | Yes (or individual specs) | Number of compute units (see pricing tiers) |
| `--vcpus` | No | Override vCPU count (overrides compute-units for CPU only) |
| `--memory` | No | Override RAM in MiB (overrides compute-units for RAM only) |
| `--rootfs-size` | No | Override disk in MiB (max 1953125) |
| `--ssh-pubkey-file` | No (defaults to ~/.ssh/id_ed25519.pub) | Path to SSH public key |
| `--crn-hash` | **Recommended** | Hash of the target CRN (from the `hash` field in `aleph node compute --active --json`). Preferred over `--crn-url` which may fail on URL resolution. |
| `--crn-url` | Alternative to --crn-hash | URL of the target CRN. **Known issue**: URL-based lookup can fail even with correct URLs. Use `--crn-hash` instead. |
| `--crn-auto-tac` | Recommended | Auto-accept CRN Terms & Conditions |
| `--skip-volume` | Recommended for basic VMs | Skip the interactive volume attachment prompt |
| `--gpu` | No | Attach a GPU to the instance |
| `--premium` | No | Use premium GPU (VRAM > 48 GiB) |
| `--confidential` | No | Launch confidential VM (out of scope for v1) |
| `--private-key-file` | No (defaults to ~/.aleph-im/private-keys/ethereum.key) | Path to private key |

**On success**, the command outputs the instance details including the **item_hash** — this is the unique identifier you need for all subsequent operations (list, delete, SSH).

**IMPORTANT**: Record the item_hash immediately after creation. If you lose it, use `aleph instance list` to recover it.

### 5.2 Create with GPU (Optional)

GPU instances follow the same pattern but add the `--gpu` flag (and `--premium` for A100/H100/H200). See **Appendix A** for full GPU tiers, pricing, and examples.

### 5.3 List Your Instances

```bash
aleph instance list --json
```

This returns all instances created by the current account's key. Use this to:
- Verify instance creation succeeded
- Get item_hash values for instances
- Monitor what's running
- Detect orphaned instances that should be cleaned up

**Without `--json`**, the output is a formatted table. With `--json`, it's machine-parseable.

**Delegated instances**: When you create instances using `--address <HUMAN_ADDRESS>` (delegated permissions), those instances are listed under **the agent's account** (the key that signed the creation message), NOT under the human's address. Always use `aleph instance list --json` without `--address` to see instances you created via delegation. Using `--address <HUMAN_ADDRESS>` will return nothing for delegated instances.

### 5.4 Delete an Instance

```bash
aleph instance delete <ITEM_HASH>
```

Where `<ITEM_HASH>` is the hash returned during creation or from `aleph instance list`.

Optional parameters:
- `--reason "description"` — reason for deletion (default: "User deletion")
- `--domain "crn-url.aleph.cloud"` — ensures the VM is stopped on the CRN before the message is deleted. **Recommended** to include this for clean shutdown.

**Example:**

```bash
aleph instance delete abc123def456 --domain "crn-example.aleph.cloud"
```

### 5.5 SSH into an Instance

After creation, get the connection details from `aleph instance list --json`. The `execution.networking` section contains both IPv6 and IPv4 access methods.

**Method 1 — IPv4 with mapped port (recommended)**:

The JSON output includes `mapped_ports` with an SSH port mapping. Use the `host_ipv4` address and the mapped port:

```bash
ssh -p <MAPPED_PORT> root@<HOST_IPv4>
```

Example (from instance list JSON):

```json
"networking": {
  "host_ipv4": "213.246.45.218",
  "mapped_ports": { "22": { "host": 24000 } }
}
```

```bash
ssh -p 24000 root@213.246.45.218
```

**Method 2 — IPv6 direct**:

```bash
ssh root@<IPv6_ADDRESS>
```

The IPv6 address is in the `execution.networking.ipv6_ip` field. This requires your local network to support IPv6.

**Tip**: Use `-o StrictHostKeyChecking=no` on first connection to avoid the host key prompt, and `-o ConnectTimeout=15` to fail fast if the VM isn't ready yet.

### 5.6 Instance Inventory Management

**CRITICAL RULE**: Every time you create an instance, record the following in a local inventory:

```json
{
  "item_hash": "abc123...",
  "name": "my-instance",
  "crn_url": "https://crn-example.aleph.cloud",
  "compute_units": 2,
  "created_at": "2026-02-02T10:00:00Z",
  "estimated_hourly_cost": 2.85,
  "purpose": "Running deployment task X",
  "ipv4_host": "213.246.45.218",
  "ssh_port_mapped": 24000,
  "ipv6": "fc00:1:2:3:...",
  "delegated_from": "0xHUMAN_ADDRESS_IF_DELEGATED"
}
```

Store this inventory in a file at `~/.aleph-agent-inventory.json` (create it if it doesn't exist).

**On every new session**, run `aleph instance list --json` and reconcile against the local inventory. If instances exist that aren't in the inventory, flag them to the human:

```
WARNING: Found instance {item_hash} not in local inventory.
This may be an orphaned instance still consuming credits.
Delete it? [y/n]
```

---

## 6. Authorization (Delegated Permissions)

This section covers **Model B** from the project design: the human grants the agent permission to operate on their behalf.

### 6.1 How It Works

1. The agent creates its own keypair (Section 2.1)
2. The agent tells the human its public address (Section 2.2)
3. The human adds the agent's address as an authorized delegate on their account
4. The agent can now create instances charged to the human's credit balance using `--address`

### 6.2 Human Grants Permission

The **human** runs this command (not the agent):

```bash
aleph authorizations add <AGENT_ADDRESS> --chain ETH
```

Optional scope restrictions:
- `--channels "ALEPH-CLOUDSOLUTIONS"` — restrict to instance operations only
- `--message-types "INSTANCE"` — restrict to instance message types

### 6.3 Agent Uses Delegated Permissions

When creating instances on behalf of the human:

```bash
aleph instance create \
  --payment-type credit \
  --address <HUMAN_ADDRESS> \
  --name "delegated-instance" \
  --compute-units 2 \
  --ssh-pubkey-file ~/.ssh/id_ed25519.pub \
  --crn-hash "CRN_HASH_HERE" \
  --crn-auto-tac \
  --skip-volume
```

The `--address <HUMAN_ADDRESS>` flag tells the network to charge the human's credit balance, not the agent's.

### 6.4 List Current Authorizations

```bash
aleph authorizations list --json
```

To check if a specific agent address is authorized:

```bash
aleph authorizations list --delegate <AGENT_ADDRESS> --json
```

### 6.5 Revoke Authorization

The **human** runs:

```bash
aleph authorizations revoke <AGENT_ADDRESS>
```

### 6.6 Setup Flow (Agent Guides the Human)

When the human wants to use delegated permissions, guide them through this sequence:

```
1. I will generate a new keypair for myself.
   > aleph account create --chain ETH

2. My public address is: 0xAGENT_ADDRESS

3. Please authorize me to operate on your behalf by running:
   > aleph authorizations add 0xAGENT_ADDRESS --chain ETH

4. Please tell me your wallet address so I can use --address when creating instances.

5. Done. I will now create instances charged to your credit balance.
   You can revoke my access at any time with:
   > aleph authorizations revoke 0xAGENT_ADDRESS
```

---

## 7. Self-Replication

Self-replication means the agent provisions a new VM, sets it up, and starts another agent instance on it. This is useful for:
- Running parallel workloads across multiple VMs
- Deploying services that the agent manages
- Scaling compute capacity dynamically

### 7.1 Safety Rules

**These rules are non-negotiable. Violating them is a critical failure.**

1. **Maximum concurrent VMs**: Never have more than **3** agent-provisioned VMs running simultaneously unless the human explicitly raises this limit.
2. **Human approval**: Before creating a VM that will cost more than **10 credits**, present the cost and get explicit confirmation.
3. **Inventory**: Every VM must be recorded in `~/.aleph-agent-inventory.json` (see Section 5.6).
4. **No recursive replication**: An agent deployed on a VM must NOT create additional VMs that themselves create VMs. Maximum depth is 1 (parent agent creates child VMs, children do not create grandchildren).
5. **Cleanup obligation**: When the task is complete, the agent MUST delete all VMs it created. Leaving orphaned VMs running is a spending leak.
6. **Balance guard**: Before provisioning, check the credit balance. If the balance would drop below **20% of current level** after accounting for all running VMs for the next hour, do NOT provision and inform the human.

### 7.2 Replication Procedure

**Step 1 — Provision the VM**

Follow Section 5.1. Use at least tier-2 (2 compute units) for a VM that will run an agent.

**Step 2 — Wait for VM to boot**

After creation, wait 30-60 seconds for the VM to become reachable. Get the SSH connection details from `aleph instance list --json` (see Section 5.5). Then verify:

```bash
ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 -p <MAPPED_PORT> root@<HOST_IPv4> "echo ok"
```

Retry up to 5 times with 15-second intervals. If unreachable after all retries, delete the instance and report failure.

**Step 3 — Set up the VM**

SSH in and install prerequisites:

```bash
ssh -p <MAPPED_PORT> root@<HOST_IPv4> << 'SETUP'
apt-get update && apt-get install -y python3-pip libsecp256k1-dev curl
pip install aleph-client
SETUP
```

**Step 4 — Transfer the agent's identity (optional)**

If the child VM needs to operate under the same Aleph account:

```bash
scp -P <MAPPED_PORT> ~/.aleph-im/private-keys/ethereum.key root@<HOST_IPv4>:~/.aleph-im/private-keys/ethereum.key
```

**CAUTION**: This copies the private key to another machine. Only do this if:
- The VM is trusted (non-confidential VMs have unencrypted disk)
- The key controls a limited-funds account (hot wallet pattern)
- The human has approved this

**Step 5 — Deploy the workload**

Transfer whatever scripts, code, or instructions the child agent needs:

```bash
scp -P <MAPPED_PORT> ./task-script.sh root@<HOST_IPv4>:/root/task-script.sh
ssh -p <MAPPED_PORT> root@<HOST_IPv4> "chmod +x /root/task-script.sh && nohup /root/task-script.sh &"
```

**Step 6 — Monitor and cleanup**

Periodically check if the workload is complete:

```bash
ssh -p <MAPPED_PORT> root@<HOST_IPv4> "cat /root/task-status.txt"
```

When done:

```bash
aleph instance delete <ITEM_HASH> --domain "crn-example.aleph.cloud"
```

Remove the entry from `~/.aleph-agent-inventory.json`.

### 7.3 Multi-VM Coordination

When running multiple VMs:
- Use SSH to check status of each VM
- Maintain the inventory file as the single source of truth
- If one VM fails, decide whether to reprovision or redistribute the work
- Always clean up ALL VMs when the overall task is complete

---

## 8. Reference

### 8.1 REST API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `https://api2.aleph.im/api/v0/addresses/{address}/balance` | GET | None | Get credit balance and token holdings |
| `https://api2.aleph.im/api/v0/addresses/{address}/credit_history` | GET | None | Get credit purchase history |

### 8.2 CLI Command Quick Reference

| Command | Description |
|---------|-------------|
| `aleph account create --chain ETH` | Generate new keypair |
| `aleph account address` | Show your wallet address |
| `aleph account show` | Show current account config |
| `aleph credits show --json` | Check credit balance |
| `aleph credits history --json` | Check credit purchase history |
| `aleph pricing instance --payment-type credit --json` | Instance pricing |
| `aleph pricing gpu --payment-type credit --json` | GPU instance pricing |
| `aleph node compute --active --json` | List active CRNs |
| `aleph instance create ...` | Create a new VM |
| `aleph instance list --json` | List your instances |
| `aleph instance delete <HASH>` | Delete an instance |
| `aleph authorizations list --json` | List delegated permissions |
| `aleph authorizations add <ADDR>` | Grant permissions to an address |

### 8.3 Key File Locations

| File | Path | Description |
|------|------|-------------|
| Private key | `~/.aleph-im/private-keys/ethereum.key` | Account private key (NEVER expose) |
| SSH public key | `~/.ssh/id_ed25519.pub` | Used for VM access |
| Agent inventory | `~/.aleph-agent-inventory.json` | Local record of provisioned VMs |

### 8.4 Important Constants

| Constant | Value | Description |
|----------|-------|-------------|
| Default payment type | `credit` | Always use this. `hold` and `superfluid` are deprecated. |
| Default chain | `ETH` | Ethereum-based accounts |
| Default hypervisor | `qemu` | QEMU (Firecracker is deprecated for instances) |
| Default SSH key | `~/.ssh/id_ed25519.pub` | Auto-detected by CLI |
| Credit console | https://credits.app.aleph.im | Where humans buy credits |
| Max concurrent VMs (agent default) | 3 | Self-imposed safety limit |
| Cost confirmation threshold | 10 credits | Ask human before exceeding |
| Balance guard | 20% | Don't provision if balance drops below this |

### 8.5 Supported Chains for Accounts

ARB, AURORA, AVAX, BASE, BLAST, BOB, BSC, CSDK, CYBER, DOT, ES, ETH, ETHERLINK, FRAX, HYPE, INK, LENS, LINEA, LISK, METIS, MODE, NEO, NULS, NULS2, OP, POL, SOL, STT, SONIC, TEZOS, UNICHAIN, WLD, ZORA. Use `--chain ETH` as default unless the human specifies otherwise.

---

## 9. Error Handling

### 9.1 Common Errors and Recovery

**"Insufficient credits"**
- Check balance: `aleph credits show --json`
- Inform the human to top up at https://credits.app.aleph.im
- Do NOT retry the operation until balance is confirmed sufficient

**"CRN unavailable" / connection timeout**
- The selected CRN may be down. Try a different CRN.
- Re-run `aleph node compute --active --json` to get a fresh list.
- Select a different CRN and retry.

**"Not authorized" when using `--address`**
- The human has not granted you delegation permission.
- Guide them through Section 6.6.

**Instance creation succeeds but SSH fails**
- Wait 60 seconds and retry (VM may still be booting).
- After 5 retries, the CRN or VM may be faulty. Delete the instance and try on a different CRN.

**"REMOTE HOST IDENTIFICATION HAS CHANGED" / host key verification failed**
- CRNs reuse the same IP and mapped port across different VMs. If you previously connected to a different VM on the same CRN, the old host key in `~/.ssh/known_hosts` will conflict.
- Remove the stale entry before connecting:
  ```bash
  ssh-keygen -R "[<HOST_IPv4>]:<MAPPED_PORT>"
  ```
- Then retry SSH. To avoid this entirely, use `-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null` when connecting to Aleph VMs (acceptable because these are ephemeral machines you provisioned yourself).

**"Private key file not found"**
- Run `aleph account create --chain ETH` to generate one.
- Or specify the path explicitly with `--private-key-file`.

### 9.2 General Rules

- Never retry a failed operation more than 3 times.
- Always include `--json` in commands when you need to parse the output.
- If something unexpected happens, describe the error to the human and ask for guidance rather than guessing.

---

## Appendix A: GPU Instances

GPU instances use the same `aleph instance create` command with the `--gpu` flag. Premium GPUs (VRAM > 48 GiB) additionally require `--premium`.

### GPU Pricing

Run `aleph pricing gpu --payment-type credit --json` for current prices. Reference tables below:

**Standard GPUs (credit price per compute unit: 4.3125/hour):**

| Tier | CUs | GPU Model       | VRAM    | Credits/Hour |
|------|-----|-----------------|---------|-------------|
| 1    | 3   | RTX 4000 ADA    | 20 GiB  | 12.94       |
| 2    | 4   | RTX 3090        | 24 GiB  | 17.25       |
| 3    | 6   | RTX 4090        | 24 GiB  | 25.88       |
| 3    | 8   | RTX 5090        | 32 GiB  | 34.50       |
| 4    | 12  | L40S            | 48 GiB  | 51.75       |
| 5    | 3   | RTX A5000       | 24 GiB  | 12.94       |
| 6    | 4   | RTX A6000       | 48 GiB  | 17.25       |
| 4    | 11  | RTX 6000 ADA    | 48 GiB  | 47.44       |

**Premium GPUs (credit price per compute unit: 8.625/hour):**

| Tier | CUs | GPU Model       | VRAM     | Credits/Hour |
|------|-----|-----------------|----------|-------------|
| 1    | 16  | A100            | 80 GiB   | 138.00      |
| 1    | 14  | RTX PRO 6000    | 96 GiB   | 120.75      |
| 2    | 24  | H100            | 80 GiB   | 207.00      |
| 2    | 32  | H200            | 141 GiB  | 276.00      |

### GPU Instance Creation Example

```bash
aleph instance create \
  --payment-type credit \
  --name "gpu-instance" \
  --compute-units 6 \
  --gpu \
  --ssh-pubkey-file ~/.ssh/id_ed25519.pub \
  --crn-hash "CRN_HASH_HERE" \
  --crn-auto-tac \
  --skip-volume
```

For premium GPUs (A100, H100, H200):

```bash
aleph instance create \
  --payment-type credit \
  --name "premium-gpu" \
  --compute-units 16 \
  --gpu \
  --premium \
  --ssh-pubkey-file ~/.ssh/id_ed25519.pub \
  --crn-hash "CRN_HASH_HERE" \
  --crn-auto-tac \
  --skip-volume
```

**Note**: Not all CRNs have GPUs. Use `aleph pricing gpu --payment-type credit --with-current-availability --json` to see which GPU models are currently available on the network.
