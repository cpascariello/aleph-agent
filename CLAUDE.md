# CLAUDE.md

## Project Overview

This project builds tooling that enables AI agents to autonomously provision and manage virtual machines on the Aleph Cloud decentralized network using the credit payment system.

## Key Documents

- `AGENT_VM_PROVISIONING.md` — Project concept, technical write-up, and review addendums (architecture + business/marketing). This is the design document derived from an internal meeting transcript.
- `docs/plans/aleph-cloud-agent-instructions.md` — **Phase 1 deliverable**: A markdown instruction profile optimized for LLM consumption. Teaches an agent how to create accounts, manage credits, discover CRNs, provision/destroy VMs, handle delegated permissions, and self-replicate safely.
- `docs/phase2-context.md` — **Phase 2 build context**: SDK API surface, CLI issues found during testing, account setup, verified SDK call patterns, and gotchas.
- `README.md` — Install, usage, tool reference, safety controls, sample prompts.

## Project Context

- **Payment model**: Aleph Cloud credit system ONLY. The legacy "hold" and "superfluid/pay-as-you-go" payment types are deprecated. Always use `--payment-type credit`.
- **Credit console**: https://credits.app.aleph.im (buying credits is manual; the agent cannot do it programmatically)
- **Credit balance API**: `GET https://api2.aleph.im/api/v0/addresses/{address}/balance` — the `credit_balance` field is what matters
- **Credit history API**: `GET https://api2.aleph.im/api/v0/addresses/{address}/credit_history`
- **Primary interface**: `aleph-agent-mcp` MCP server wrapping `aleph-sdk-python` directly (no CLI)
- **Focus**: Standard instances (CPU VMs). GPU is documented in an appendix but not the priority.

## Implementation Phases

1. **Phase 1 (DONE)**: Markdown instruction profile for LLM agents — `docs/plans/aleph-cloud-agent-instructions.md`
2. **Phase 2 (DONE)**: Python MCP Server (FastMCP) wrapping the Aleph Python SDK directly (not CLI). 6 tools, safety controls, inventory management. Code: `src/aleph_agent_mcp/`
3. **Phase 3**: OpenCode plugin (same tool surface, different packaging)
4. **Phase 4**: Spending controls dashboard and UX

## Technical Notes

- Private keys stored at `~/.aleph-im/private-keys/ethereum.key`
- Agent VM inventory tracked at `~/.aleph-agent-inventory.json`
- 1 compute unit = 1 vCPU, 2048 MiB RAM, 20480 MiB disk = 1.425 credits/hour
- Instance tiers range from 1 to 12 compute units
- Instance creation via SDK: `AuthenticatedAlephHttpClient.create_instance()` with `Payment(type=PaymentType.credit)`
- Delegated permissions via `aleph authorizations add <address>`

## Safety Defaults for Agents

- Max concurrent VMs: 3 (unless human raises limit)
- Cost confirmation threshold: 10 credits
- Balance guard: don't provision if balance drops below 20%
- No recursive self-replication (max depth 1)
- Mandatory cleanup of all VMs when task completes
