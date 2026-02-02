# aleph-agent-mcp

MCP server that lets AI agents provision and manage VMs on [Aleph Cloud](https://aleph.im) using the credit payment system.

Wraps the `aleph-sdk-python` directly (no CLI subprocesses). Built with [FastMCP](https://github.com/jlowin/fastmcp).

## Prerequisites

- Python 3.11+
- An Aleph account with a private key at `~/.aleph-im/private-keys/ethereum.key`
- An SSH public key at `~/.ssh/id_ed25519.pub`
- Credits on your account (buy at https://credits.app.aleph.im)

For delegated mode (recommended): grant INSTANCE permission from your human account to the agent account using `aleph authorizations add <agent_address>`.

## Install

```bash
pip install aleph-agent-mcp
```

Or from source:

```bash
git clone https://github.com/anthropics/aleph-agent.git
cd aleph-agent
pip install -e .
```

## Usage

### Claude Code

```bash
claude mcp add \
  --env ALEPH_AGENT_HUMAN_ADDRESS=0xYourHumanAddress \
  aleph-agent -- python3.11 -m aleph_agent_mcp
```

Then in a Claude Code session, the agent can call tools like `aleph_check_balance`, `aleph_create_vm`, etc.

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "aleph-agent": {
      "command": "python3.11",
      "args": ["-m", "aleph_agent_mcp"],
      "env": {
        "ALEPH_AGENT_HUMAN_ADDRESS": "0xYourHumanAddress"
      }
    }
  }
}
```

### Standalone

```bash
python3.11 -m aleph_agent_mcp
```

Starts the MCP server on stdio.

## Tools

| Tool | Description |
|------|-------------|
| `aleph_check_balance` | Credit balance, burn rate, runway, active VMs. Triggers orphan detection on first call. |
| `aleph_list_crns` | List active Compute Resource Nodes with optional filters. |
| `aleph_create_vm` | Provision a VM. Runs a full safety chain before execution. Supports `dry_run`. |
| `aleph_destroy_vm` | Erase VM on CRN, delete port forwards, forget message, clean inventory. |
| `aleph_list_my_vms` | Local inventory reconciled with the network. Flags orphans and expired TTLs. |
| `aleph_extend_vm` | Extend a VM's TTL (local tracking — Aleph has no native TTL). |

## Sample Prompts

Once the MCP server is connected, try these in Claude Code or Claude Desktop:

### Check your account

> "Check my Aleph credit balance and tell me how many VMs I can afford."

> "How long can I keep running my current VMs before I run out of credits?"

### Browse infrastructure

> "List available CRNs on the Aleph network."

> "Find me a CRN with GPU support."

### Provision a VM

> "Spin up a small Ubuntu VM on Aleph for 2 hours so I can test a deployment script."

> "Create a VM with 2 compute units on CRN NtS9 to run a build job. Show me the cost first."

> "Do a dry run for a 4-CU Debian VM — I just want to see what it would cost."

### Manage running VMs

> "List all my running VMs and show me how much each one has cost so far."

> "Extend my VM's TTL by 3 hours."

> "Destroy all expired VMs."

### Multi-step workflows

> "I need to compile a Rust project. Find a CRN, spin up a 2-CU Ubuntu VM, give me the SSH command, and remind me to destroy it when I'm done."

> "Check my balance, then create the cheapest possible VM for running a Python script. Destroy it after you confirm it's working."

## Safety Controls

All enforced automatically before provisioning:

| Control | Default | Env var |
|---------|---------|---------|
| Max concurrent VMs | 3 | `ALEPH_AGENT_MAX_CONCURRENT_VMS` |
| Default TTL | 4 hours | `ALEPH_AGENT_DEFAULT_TTL_HOURS` |
| Max TTL | 24 hours | `ALEPH_AGENT_MAX_TTL_HOURS` |
| Balance guard | 20% | `ALEPH_AGENT_BALANCE_GUARD_PERCENT` |
| Cost confirmation threshold | 10 credits | `ALEPH_AGENT_COST_THRESHOLD` |
| Max session spend | disabled | `ALEPH_AGENT_MAX_SESSION_SPEND` |

When `aleph_create_vm` is called:

1. TTL must be within allowed range
2. Cost estimate is computed from live pricing
3. Balance guard ensures you keep at least 20% of your balance
4. Concurrent VM limit is checked
5. Session spend circuit breaker is checked
6. If cost exceeds threshold, the tool returns `requires_confirmation: true` — the agent must call again with `confirmed=true`

## Configuration

All settings are read from `ALEPH_AGENT_*` environment variables:

| Env var | Default | Description |
|---------|---------|-------------|
| `ALEPH_AGENT_HUMAN_ADDRESS` | none | Payer address for delegated mode |
| `ALEPH_AGENT_PRIVATE_KEY_PATH` | `~/.aleph-im/private-keys/ethereum.key` | Path to private key |
| `ALEPH_AGENT_SSH_PUBKEY_PATH` | `~/.ssh/id_ed25519.pub` | SSH public key for VM access |
| `ALEPH_AGENT_INVENTORY_PATH` | `~/.aleph-agent-inventory.json` | Local VM inventory file |
| `ALEPH_AGENT_DEFAULT_OS_IMAGE` | `ubuntu22` | Default OS (`ubuntu22`, `ubuntu24`, `debian12`) |

## Compute Unit Tiers

| CUs | vCPUs | RAM | Disk | Credits/hour |
|-----|-------|-----|------|-------------|
| 1 | 1 | 2 GiB | 20 GiB | 1.425 |
| 2 | 2 | 4 GiB | 40 GiB | 2.85 |
| 4 | 4 | 8 GiB | 80 GiB | 5.70 |
| 6 | 6 | 12 GiB | 120 GiB | 8.55 |
| 8 | 8 | 16 GiB | 160 GiB | 11.40 |
| 12 | 12 | 24 GiB | 240 GiB | 17.10 |

## Architecture

```
server.py          ← FastMCP tool registrations (thin handlers)
  ├── safety.py    ← Pure functions: spending guards, limits
  ├── cost.py      ← Pure functions: cost math, burn rate
  ├── inventory.py ← ~/.aleph-agent-inventory.json CRUD
  ├── config.py    ← Pydantic settings from env vars
  ├── types.py     ← All dataclasses (SDK-independent)
  └── aleph_ops.py ← All SDK calls (only module importing aleph.sdk)
      └── account.py ← Account loading
```

`aleph_ops.py` is the only module that imports from `aleph.sdk`. Everything else is pure business logic. This separation is intentional — for a future TypeScript rewrite, only `aleph_ops.py` needs to be ported.

## Key Safety Feature: Signing Address Tracking

Every VM inventory record stores the `signing_address` of the key that created it. On `aleph_destroy_vm`, the server verifies the current key matches before attempting destruction. This prevents silent failures where the SDK call succeeds but has no effect because the wrong key is loaded.

## Development

```bash
pip install -e ".[dev]"

# Unit tests
python3.11 -m pytest tests/ --ignore=tests/integration/

# Integration tests (hits real Aleph network)
ALEPH_AGENT_RUN_INTEGRATION=1 \
ALEPH_AGENT_HUMAN_ADDRESS=0xYourAddress \
python3.11 -m pytest tests/integration/ -v -s
```

## License

MIT
