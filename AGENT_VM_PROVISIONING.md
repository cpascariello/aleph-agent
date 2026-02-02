# Agent-Driven VM Provisioning on Aleph Cloud

> **Document Type**: Project Concept & Technical Write-up
> **Source**: Internal meeting transcript (2026-02-02)
> **Author**: Cleaned and structured from conversation between Speaker A (project lead), Speaker C (developer), and Speaker D (business/community)
> **Status**: Draft — Reviewed (Architecture + Business/Marketing)

---

## 1. Executive Summary

This document captures a proposed system that enables **AI agents to autonomously provision and manage virtual machines on the Aleph Cloud network**. The core idea: give AI coding assistants (Claude Code, OpenCode, OpenCloud, and similar tools) the knowledge and credentials to spin up decentralized compute resources on demand, pay for them via Aleph's credit system (the sole payment model going forward — the legacy pay-as-you-go/holding models are being deprecated), and tear them down when no longer needed.

The system targets a gap in the current AI agent ecosystem: agents can write code and orchestrate workflows, but they lack the ability to **self-provision infrastructure**. By packaging Aleph Cloud's VM management capabilities into agent-consumable formats (plugins, MCP servers, markdown instruction files), agents gain the ability to replicate themselves, deploy workloads, and manage their own compute lifecycle.

---

## 2. Problem Statement

AI agents today operate within the confines of whatever machine they're running on. When an agent needs more compute — to run a parallel workload, deploy a service, or replicate itself — it has no standardized way to acquire infrastructure. The human must manually provision servers, configure access, and hand credentials back to the agent.

This creates friction at exactly the point where agents should be most autonomous: scaling their own capacity.

**Specific pain points:**

- Agents cannot programmatically request new VMs
- No standard interface exists between AI coding tools and cloud provisioning
- Credit card-based cloud billing is poorly suited for agent-driven spending (no granular limits, security concerns)
- Agents lack instructions for key management and secure credential handling

---

## 3. Proposed Solution

### 3.1 Overview

Build a set of **agent instruction profiles** — structured documentation and tooling that teaches AI agents how to:

1. **List available CRNs** (Compute Resource Nodes) on the Aleph network
2. **Select a CRN** based on resource requirements (CPU, RAM, disk)
3. **Start a VM** on the chosen CRN
4. **Replenish credits** from an on-chain wallet to fund the VM
5. **Generate and manage private keys** securely
6. **Replicate** by spinning up additional agent instances on new VMs

### 3.2 Delivery Formats

The instructions will be packaged in multiple formats to reach agents across different platforms:

| Format | Target Platform | Description |
|--------|----------------|-------------|
| **Claude Code Plugin / MCP Server** | Claude Code | Native integration that adds Aleph VM tooling to Claude Code's capabilities |
| **OpenCode Plugin** | OpenCode | Plugin that registers Aleph operations as available tools |
| **Markdown Instruction File** | OpenCloud / any LLM | A standalone reference document the agent ingests into its context ("read this and add it to your toolbox") |

### 3.3 Core Workflow

```
Agent receives task requiring compute
        │
        ▼
Agent reads Aleph instruction profile
        │
        ▼
Agent checks credit balance
        │
        ├── Insufficient ──▶ Replenish from on-chain wallet
        │
        ▼
Agent lists available CRNs
        │
        ▼
Agent selects CRN (by specs, availability, latency)
        │
        ▼
Agent provisions VM via Aleph API
        │
        ▼
Agent deploys workload / replicates itself
        │
        ▼
Agent monitors and tears down when done
```

---

## 4. Account & Key Management

Two account models were discussed, each with different security and UX trade-offs:

### Model A: Agent's Own Account

The agent generates its own private key, creates its own Aleph account, and manages its own credit balance.

**Pros:**
- Clean separation between human and agent funds
- Agent is fully autonomous

**Cons:**
- The private key must be backed up — if lost, funds are lost
- Someone must fund the agent's account initially
- Key storage becomes a security concern (where does the agent keep it?)

### Model B: Delegated Permissions on Human's Account

The agent generates a keypair and gives the public key to the human. The human adds the agent's public key to their account's permission system, granting the agent spending rights on the human's balance.

**Pros:**
- Human retains control over funds
- No separate backup needed for agent keys
- Human can revoke permissions at any time

**Cons:**
- Requires the human to perform a setup step (adding permissions)
- The agent operates under the human's spending limits
- Permission management adds complexity

**Recommendation from the meeting**: Support both models. Let the user choose based on their trust level and use case.

---

## 5. Credit System & Spending Controls

### 5.1 How Credits Work

Aleph Cloud is consolidating on a single **credit system** as its only payment model. The legacy payment models (token holding and pay-as-you-go) are being deprecated in favor of credits.

Credits are denominated in USD. Users top up credits using on-chain transactions (ALEPH tokens or potentially other assets via the credit console). The agent's VMs consume credits at a rate determined by the VM's resource allocation.

**Credit Console (live):** [https://credits.app.aleph.im](https://credits.app.aleph.im) — first version is currently available for managing credit balances, top-ups, and usage.

> **Important**: All agent tooling must target the credit system exclusively. Do not build against the legacy pay-as-you-go or holding payment models — they will be removed.

### 5.2 Fiat On-Ramping

If Aleph Cloud implements fiat on-ramping (credit card payments), users can replenish credits without holding crypto. This simplifies the experience but introduces the concern raised in the meeting: **an agent with access to a credit card number could spend without limits**.

### 5.3 Proposed Spending Safeguards

Speaker D raised an important UX concern: agents need spending limits.

**Proposed controls:**

- **Per-hour credit burn rate limit**: Cap how many credits the agent can consume per hour
- **Absolute balance ceiling**: Agent can only spend up to X credits before requiring human re-authorization
- **Automatic stop on limit breach**: VM provisioning halts when the limit is reached, not after
- **Burn rate estimation**: Before provisioning, the agent estimates ongoing costs and presents them to the user

These controls are not optional nice-to-haves. Without them, an agent could theoretically provision hundreds of VMs and drain an account. **This is the most critical safety feature in the entire system.**

---

## 6. Technical Architecture

### 6.1 Aleph Cloud Primitives

| Concept | Description |
|---------|-------------|
| **CRN** (Compute Resource Node) | Physical or virtual machine in the Aleph network that runs user VMs |
| **CCN** (Core Channel Node) | Backbone node managing data propagation and integrity |
| **Instance** | A persistent VM running on a CRN |
| **Credits** | USD-denominated balance consumed by running instances. The sole payment model going forward (managed via [credits.app.aleph.im](https://credits.app.aleph.im)). Legacy pay-as-you-go and holding models are deprecated. |
| **ALEPH Token** | Network token used for staking and converting to credits via on-chain transactions |

### 6.2 Agent Instruction Profile Structure

The instruction profile (whether plugin or markdown) must cover:

```
1. AUTHENTICATION
   - How to generate a keypair (ed25519 or secp256k1)
   - How to derive an Aleph account address
   - How to store the private key securely
   - How to set up delegated permissions (Model B)

2. CREDIT MANAGEMENT
   - How to check current balance
   - How to estimate costs for a given VM spec
   - How to top up credits from on-chain (via credits.app.aleph.im or API)
   - How to monitor burn rate
   - Note: credit system is the ONLY payment model (holding/pay-as-you-go deprecated)

3. CRN DISCOVERY
   - How to list available CRNs
   - How to filter by resource capacity (CPU, RAM, disk)
   - How to check CRN health/status
   - How to select based on latency or region

4. VM LIFECYCLE
   - How to create an instance on a specific CRN
   - How to configure the VM (OS, specs, networking)
   - How to monitor VM health
   - How to SSH into the VM
   - How to stop/destroy the VM

5. SELF-REPLICATION
   - How to deploy another agent instance on a new VM
   - How to pass context/state to the new instance
   - How to coordinate between agent instances
```

### 6.3 Integration Points

```
┌─────────────────────────────────────────────────────┐
│                  AI Coding Tool                       │
│          (Claude Code / OpenCode / OpenCloud)          │
│                                                       │
│   ┌───────────────────────────────────────────┐      │
│   │        Aleph VM Plugin / Instructions      │      │
│   │                                            │      │
│   │   ┌──────────┐  ┌──────────┐  ┌────────┐ │      │
│   │   │  Key     │  │  Credit  │  │  VM    │ │      │
│   │   │  Mgmt    │  │  Mgmt    │  │  Ops   │ │      │
│   │   └────┬─────┘  └────┬─────┘  └───┬────┘ │      │
│   └────────┼─────────────┼─────────────┼──────┘      │
│            │             │             │              │
└────────────┼─────────────┼─────────────┼──────────────┘
             │             │             │
             ▼             ▼             ▼
┌─────────────────────────────────────────────────────┐
│                 Aleph Cloud Network                    │
│                                                       │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐      │
│   │   CCN    │    │   CCN    │    │   CCN    │      │
│   │  (API)   │    │  (API)   │    │  (API)   │      │
│   └────┬─────┘    └────┬─────┘    └────┬─────┘      │
│        │               │               │             │
│   ┌────┴────┐     ┌────┴────┐     ┌────┴────┐      │
│   │CRN CRN │     │CRN CRN │     │CRN CRN │      │
│   │CRN CRN │     │CRN CRN │     │CRN CRN │      │
│   └─────────┘     └─────────┘     └─────────┘      │
│                                                       │
│   Target: 300-500 CRNs globally                       │
└─────────────────────────────────────────────────────┘
```

---

## 7. Competitive Advantages

Why Aleph Cloud instead of AWS/GCP/Azure for agent-driven provisioning:

| Factor | Traditional Cloud | Aleph Cloud |
|--------|------------------|-------------|
| **Payment** | Credit card required, hard to scope | Credit system only — top up via ALEPH tokens, spend in USD credits ([credits.app.aleph.im](https://credits.app.aleph.im)) |
| **Agent autonomy** | Requires IAM setup, billing alerts | Native wallet-based auth, agent can self-fund |
| **Censorship resistance** | Provider can terminate at will | Decentralized, no single kill switch |
| **Spending limits** | Complex billing alerts, after-the-fact | On-chain balance is a hard cap by design |
| **Identity** | Tied to a corporate/personal account | Pseudonymous, keypair-based |
| **Setup friction** | Account creation, KYC, billing setup | Generate a key, fund it, go |

The credit-based payment model is actually a **better fit for autonomous agents** than traditional cloud billing. A credit balance of $20 is a self-enforcing spending limit — the agent literally cannot spend more than what's in the account. The human tops up credits via ALEPH tokens through the credit console ([credits.app.aleph.im](https://credits.app.aleph.im)), and the agent operates within that ceiling. This is a natural safety mechanism that credit card billing lacks.

---

## 8. Risks & Open Questions

### 8.1 Technical Risks

- **Private key security**: Where does an agent store a private key? Environment variables? Encrypted file? Hardware security module? This needs a clear recommendation — getting it wrong means lost funds or compromised accounts.
- **API stability**: The credit system ([credits.app.aleph.im](https://credits.app.aleph.im)) has a first version live, but the API surface may still evolve as the legacy payment models are fully deprecated. Building agent tooling against a stabilizing but not yet frozen API risks some breakage.
- **CRN reliability**: Decentralized nodes may have variable uptime. Agents need retry logic and the ability to migrate workloads between CRNs.
- **Network size**: With a target of 300-500 CRNs, capacity constraints could emerge if agent-driven provisioning becomes popular.

### 8.2 UX Risks

- **Complexity of dual account model**: Supporting both "agent's own account" and "delegated permissions" doubles the documentation and testing surface.
- **Fiat on-ramp dependency**: If users expect to pay with credit cards but that feature isn't ready, the crypto-only path creates adoption friction.
- **Trust threshold**: Giving an AI agent control over real money (even small amounts) is a psychological barrier many users won't cross without strong safety guarantees.

### 8.3 Open Questions

1. **What's the minimum viable instruction set?** Can we ship with just "create VM, destroy VM, check balance" and add features incrementally?
2. **How does the agent handle VM failures?** If a CRN goes down, does the agent automatically reprovision, or does it alert the human?
3. **What about GPU instances?** The transcript doesn't mention GPU compute, but Aleph Cloud is rolling out a GPU marketplace. Should the agent profile include GPU provisioning from day one?
4. **Multi-agent coordination**: If an agent replicates itself across multiple VMs, how do the instances coordinate? Is there a built-in message bus, or does the agent need to set that up?
5. **Rate limiting**: Does the Aleph API rate-limit VM creation? An agent in a loop could hammer the API.

---

## 9. Suggested Implementation Phases

### Phase 1: Documentation & Markdown Profile
- Write the comprehensive instruction file (markdown)
- Cover: key generation, credit management, CRN listing, VM create/destroy
- Test with OpenCloud by feeding it the markdown and verifying it can follow the instructions
- **Deliverable**: One `.md` file that any LLM can consume

### Phase 2: Claude Code MCP Server
- Build an MCP server that wraps the Aleph Python SDK
- Expose tools: `list_crns`, `create_vm`, `destroy_vm`, `check_balance`, `top_up_credits`
- Include safety: spending limits, confirmation prompts before provisioning
- **Deliverable**: Installable MCP server for Claude Code

### Phase 3: OpenCode Plugin
- Port the MCP server logic to OpenCode's plugin format
- Same tool surface, different packaging
- **Deliverable**: OpenCode plugin

### Phase 4: Spending Controls & UX
- Implement per-hour burn rate limits
- Add balance notifications and automatic shutdowns
- Build a simple dashboard showing agent spending history
- **Deliverable**: Safety layer on top of Phases 1-3

---

## 10. Cleaned Transcript

Below is the cleaned, de-fragmented version of the original conversation for reference.

**Speaker A** (Project Lead):
> The goal is to create instructions for agents on how to create virtual machines on the Aleph network using the credit system. Specifically: how to list CRNs, how to choose a CRN, how to start a VM on a CRN, and how to replenish the agent's own credit account from on-chain. Also, best practices for generating a private key and using that private key. This way, agents can replenish their balance and start as many VMs as they want and need, and how to replicate, et cetera.
>
> Basically, a profile with all the instructions — one that can be used inside agents as an agent tool. Or even a Claude Code plugin that can work. And another one for OpenCloud, which is just a markdown file that you can reference and send to your OpenCloud instance: "Read that and add it to your toolbox," and it does it.
>
> Perhaps we could also add something else: letting the user set up their own account and use the permission system. Tell the agent, "Generate a private key, give me the public key," and you add it to the permissions — giving permission on your account with your money. Then the agent replenishes credits using your account with permissions. Either that, or its own account — but then you need to back up the private key. So, both options.
>
> So: documentation on all of that, a nice page on how to do it. Plugin for Claude Code, plugin for OpenCode, and a way for OpenCloud to reference it — either as a plugin or just as a markdown file.

**Speaker C** (Developer):
> Okay. I will make a first draft and then we can share it and you guys can review. Shouldn't be that difficult.
>
> Well, the thing is, if we have the on-ramping with fiat and credit cards, then the user can just replenish the credits over time. So it still has a limit on it, unless the agent knows the credit card number, of course.

**Speaker D** (Business/Community):
> And this is going to give users that use OpenCloud, for example, better capabilities — they can deploy the work they do, rent machines, extend their agent fleet.
>
> It's amazing how the industry is going there. It's good for us because you don't need to use a credit card, which a lot of people will be scared to use, but with wallets you can adjust the amount and open a new wallet, which is easier than banking.
>
> If you can make, in the UX, kind of like a limit — an amount of credit burn per hour estimation — and then the user can put limits on it, and it stops when the limit is exceeded. That can be a safe security mechanism.

---

## Addendum A: Architecture Review

### Reviewer Context
Review conducted from the perspective of a senior distributed systems architect. Focus: production-readiness, security posture, failure modes, and gaps between the described system and what would be required to ship it safely.

---

### 1. Architecture Gaps

**1.1 No State Management Model**
The document describes a stateless workflow (list, select, provision, destroy) but ignores that VM provisioning is inherently stateful. Critical questions are unaddressed:

- Where does the agent persist its inventory of running VMs? If the agent's context window resets (common in Claude Code, OpenCode sessions), it loses track of what it provisioned. This creates **orphaned VMs** that continue burning credits with no owner.
- There is no reconciliation mechanism. The agent needs a way to query "what VMs am I currently responsible for?" on startup, not just "what CRNs are available?"
- The instruction profile (Section 6.2) lists VM creation but not **VM inventory management**. This is a first-class requirement, not an afterthought.

**Recommendation:** Define an explicit state layer. Options: (a) agent writes VM records to an Aleph aggregate/post message tied to its account, creating an on-chain inventory; (b) a local state file the agent maintains; (c) the MCP server maintains a persistent registry. Option (a) is most resilient since it survives agent restarts.

**1.2 No Defined Failure Modes or Recovery Paths**
The workflow diagram (Section 3.3) is a happy path only. Missing:

- What happens when `create_vm` succeeds on the CRN but the agent crashes before recording the VM ID?
- What happens when a CRN accepts the provisioning request but the VM never becomes healthy?
- What happens when credit replenishment fails mid-provisioning (insufficient on-chain balance, network congestion)?
- What is the timeout for each API call? Decentralized networks have high tail latency.

**Recommendation:** Define a state machine for VM lifecycle: `REQUESTED -> PROVISIONING -> HEALTHY -> STOPPING -> TERMINATED -> FAILED`. Each transition needs a timeout and a rollback path. The agent instruction profile must include idempotent retry logic for every operation.

**1.3 Network Topology Assumptions**
The diagram shows agents talking to CCNs, which route to CRNs. But:

- Is CRN selection performed client-side or server-side? If client-side, the agent needs real-time CRN capacity data, which may be stale.
- What is the consistency model for CRN availability data? If two agents query simultaneously and both select the same CRN with one remaining slot, one will fail. This is a classic **thundering herd** problem.
- Are CCNs load-balanced? Is there a discovery mechanism, or does the agent hardcode CCN endpoints?

**Recommendation:** Document the CRN selection protocol explicitly. Consider server-side CRN assignment (the API returns an assigned CRN based on requirements) rather than client-side selection to avoid race conditions.

---

### 2. Security Concerns

**2.1 Private Key Storage is Under-Specified to the Point of Being Dangerous**
Section 8.1 acknowledges this as a risk but offers no concrete mitigation. This needs to be resolved before any implementation begins.

Current agent runtimes have severely constrained secure storage options:
- **Claude Code**: Runs in a sandboxed environment. Writing a private key to a `.env` file means it sits in plaintext on the user's filesystem, accessible to any process.
- **OpenCode/OpenCloud**: Similar constraints. No access to OS keychains, HSMs, or secure enclaves.
- **Environment variables**: Visible via `/proc`, logged by many tools, persisted in shell history.

The document says "how to store the private key securely" is part of the instruction profile, but **there is no secure option available to an LLM agent** in current runtimes. This is not a documentation problem; it is a fundamental architectural constraint.

**Recommendation:** For Model A (agent's own account), accept that the key will be stored insecurely and design around it: the account should hold minimal funds (a "hot wallet" pattern), refilled in small increments from a human-controlled cold wallet. For Model B (delegated), the delegation should include **operation-scoped permissions** (e.g., "can only create VMs with <= 4 CPU, <= 8GB RAM") and **time-bounded tokens** that expire, not indefinite key-based access.

**2.2 Delegated Permissions (Model B) Needs Fine-Grained Scoping**
The document describes delegation as "giving permission on your account with your money." This is far too broad. Delegation must be scoped to:

- Maximum single-VM cost
- Maximum total concurrent VMs
- Maximum hourly/daily spend
- Allowed VM specifications (prevent agent from provisioning a 128-core machine)
- Allowed operations (create/destroy only, no account settings changes)
- Time-to-live on the delegation itself

Without these, Model B is effectively "give the agent your credit card with no limit," which is exactly the problem the document claims to solve.

**2.3 Self-Replication is a Serious Attack Surface**
Section 6.2 item 5 ("Self-Replication") is described casually but represents the highest-risk capability in the system. An agent that can replicate itself can:

- Fork-bomb the network (exponential VM creation)
- Exfiltrate data by replicating to a VM it controls, then sending data out
- Persist beyond the user's session by creating VMs the user doesn't know about

**Recommendation:** Self-replication should be a separately gated capability, not included in the base instruction profile. It requires: (a) explicit human approval per replication event, (b) a maximum replication depth (agent A can create agent B, but B cannot create agent C), and (c) mandatory registration of child agents in the parent's inventory, visible to the human.

---

### 3. Scalability & Reliability

**3.1 CRN Selection at Scale**
With 300-500 CRNs and potentially thousands of agents:

- **Race conditions**: Two agents select the same CRN simultaneously. The document mentions no locking, reservation, or optimistic concurrency mechanism. At scale, this produces a high failure rate on provisioning attempts.
- **Stale capacity data**: If CRN availability is propagated through CCNs, there is inherent propagation delay. Agents will make decisions on stale data.
- **Hot-spotting**: Without randomization or load-aware routing, popular CRNs (low latency, high specs) will be over-selected while others sit idle.

**Recommendation:** Implement a reservation-based protocol: agent requests a VM spec, the network assigns a CRN (server-side), agent confirms or releases within a TTL. This eliminates client-side race conditions entirely.

**3.2 VM Migration on CRN Failure**
The document asks "does the agent automatically reprovision?" but the answer has significant architectural implications:

- Live migration requires shared storage or state snapshotting, which decentralized CRNs likely do not support.
- Cold migration (destroy + recreate elsewhere) loses all VM state.
- The agent needs a health-check loop, which means a long-running process. But LLM agents are typically request-response, not long-running.

**Recommendation:** Do not promise VM migration. Instead, document that VMs on Aleph are **ephemeral by design**. Workloads must externalize state (to Aleph storage, IPFS, or external databases). If a CRN dies, the agent provisions a new VM and redeploys. This is simpler, more honest, and architecturally sound.

**3.3 Credit System as a Bottleneck**
If credits are checked and debited synchronously on every VM operation:

- What is the consistency model? Can an agent overdraw by issuing parallel create requests?
- If credit checks go through CCNs, a CCN outage blocks all provisioning.
- On-chain top-ups have confirmation latency (block times).

**Recommendation:** Use an optimistic credit model with periodic reconciliation: pre-authorize a credit block for the estimated session, debit incrementally, settle on-chain asynchronously.

---

### 4. API Design Suggestions

The MCP server should expose the following tool interface. Every mutating operation must include a `dry_run` mode and cost estimation.

```
Tools:
  aleph_list_crns
    params: min_cpu, min_ram_gb, min_disk_gb, region, gpu
    returns: list of {crn_id, specs, availability, latency_ms, score}
    safety: read-only, no side effects

  aleph_create_vm
    params: crn_id (optional), cpu, ram_gb, disk_gb, os_image,
            ssh_pubkey, max_hourly_cost, ttl_hours (default 4), dry_run
    returns: {vm_id, crn_id, ssh_host, ssh_port, estimated_hourly_cost, expires_at}
    safety:
      - MUST display cost estimate and request human confirmation
      - MUST check against session spending limit
      - MUST set a TTL to prevent orphaned VMs
      - MUST reject if estimated cost exceeds max_hourly_cost

  aleph_destroy_vm
    params: vm_id
    returns: {status, final_cost, runtime_minutes}

  aleph_list_my_vms
    params: none
    returns: list of {vm_id, crn_id, status, uptime, cost_so_far, expires_at}

  aleph_check_balance
    params: none
    returns: {balance_usd, burn_rate_per_hour, estimated_runway_hours, active_vms}

  aleph_extend_vm
    params: vm_id, additional_hours
    returns: {new_expires_at, additional_cost}
```

**Critical safety defaults:**
- All VMs have a mandatory TTL. No indefinite VMs from agent provisioning.
- Every mutating call returns cost impact before executing.
- The MCP server maintains a local session ledger of all VMs created, queryable even if the network is unreachable.
- A `max_session_spend` parameter at MCP server startup acts as an absolute circuit breaker.

---

### 5. Missing Components

| Component | Why It's Needed |
|-----------|----------------|
| **Observability** | Structured logging of every API call (tool, params, result, latency, cost). Spending audit trail that persists beyond agent sessions. |
| **Circuit Breakers** | Exponential backoff with jitter. Halt provisioning after N consecutive failures. Surface errors to humans, don't retry indefinitely. |
| **VM Health Monitoring** | Lightweight pings between agent invocations. Auto-teardown if VM unreachable for > N minutes. Alerting to the human. |
| **Concurrency Control** | Multiple agent sessions may run simultaneously. Shared ledger for global spend limit enforcement. |
| **Garbage Collection** | Agent provisions VMs, session ends, VMs keep running. Mandatory TTL + cleanup daemon + orphan detection on MCP startup. |
| **Client-Side Rate Limiting** | Max N VM creation requests per minute. Cooldown after failure. Max concurrent VMs per session (default: 3). |

---

### 6. Critical Assessment

**6.1 Self-Replication**: Described as a feature, designed as an afterthought. It should be removed from initial scope entirely or elevated to its own section with full threat modeling.

**6.2 The Markdown Instruction File is Fragile**: LLMs hallucinate API parameters, forget steps, and handle errors poorly when working from prose. The MCP server is the only architecturally sound approach. Ship it first, not the markdown file.

**6.3 Spending Controls in Phase 4 Should Be Phase 0**: The document calls them "the most critical safety feature" then schedules them last. No agent should provision a VM without enforced spending limits from day one.

**6.4 Dual Account Model Doubles Complexity**: For the MVP, pick one. Model B (delegated permissions) is strictly safer and should be the default.

**6.5 No Discussion of Decentralized Failure Modes**: CCN split-brain, malicious CRNs, on-chain transaction delays, inconsistent network state across CCNs — none addressed.

**6.6 GPU Compute Is Absent**: Given AI workloads are the primary driver for agent-provisioned compute, GPU support should be in scope from Phase 1.

---

### Summary of Priority Actions

| Priority | Action |
|----------|--------|
| **P0** | Move spending controls to Phase 1 |
| **P0** | Define VM state management and orphan cleanup |
| **P0** | Specify private key storage recommendation concretely |
| **P1** | Ship MCP server before markdown instructions |
| **P1** | Implement mandatory TTL on all agent-provisioned VMs |
| **P1** | Add `aleph_list_my_vms` to core tool set |
| **P1** | Defer self-replication to a later phase with threat model |
| **P2** | Pick one account model for MVP (recommend Model B) |
| **P2** | Add observability and audit logging |
| **P2** | Document decentralized network failure modes |

*Review conducted 2026-02-02.*

---

## Addendum B: Business & Marketing Review

---

### 1. Market Positioning

This product occupies the intersection of two fast-moving but still-nascent markets — AI agent infrastructure and decentralized compute. That is both an opportunity and a risk. The opportunity: you can define the category. The risk: the category may not materialize the way you expect.

| Competitor | Strengths | Weaknesses vs. This Proposal |
|---|---|---|
| **AWS / GCP / Azure** | Massive scale, mature APIs, GPU availability, brand trust | IAM complexity, credit card billing poorly suited for agent autonomy, no crypto-native payment |
| **Akash Network** | Decentralized compute, crypto-native, operational marketplace | No agent-specific tooling, focuses on containers over VMs |
| **Fleek** | Web3-native deployment, good developer branding | Focused on web hosting/edge functions, not general VM provisioning |
| **Render / Railway / Fly.io** | Excellent developer UX, fast deploys | Centralized, credit-card dependent, no agent autonomy story |
| **E2B** | Purpose-built sandboxed environments for AI agents | Narrow use case (code execution), not general compute |
| **Modal** | Serverless GPU/CPU for AI, Python-native | Centralized, no crypto angle |

**Recommendation**: Do not position this as "decentralized AWS." Position it as **"the safest way to give your AI agent a compute budget."** The safety/spending-limit story is more compelling than the decentralization story for 90% of potential users.

---

### 2. Target Audience

| Segment | Size | Crypto Comfort | Conversion Potential |
|---------|------|----------------|---------------------|
| **A: Crypto-native AI builders** | Hundreds to low thousands | High | High, but cannot sustain growth alone |
| **B: AI agent power users** (Claude Code, Cursor, OpenCode) | Tens of thousands, growing fast | Low to medium | Medium — crypto requirement filters out 80-90% |
| **C: Agent fleet operators / companies** | Very small today (hundreds of teams) | Variable | Low near-term — need SLAs and reliability guarantees |

**Recommendation**: Launch targeting Segment A to prove the product. Build fiat on-ramp before pursuing Segment B. Do not pitch to Segment C until CRN count exceeds 1,000 and uptime data exists.

---

### 3. Go-to-Market Strategy

The mention of sharing with an "Israeli group" is a partnership play, not a distribution strategy. What's missing:

- **Developer content strategy**: Blog posts, tutorials, demo videos, conference talks. The AI agent community is content-driven.
- **Quick-start experience**: No "run this one command and see it work in 30 seconds" moment. The multi-step setup is too long for a first impression.
- **Integration-first distribution**: The Claude Code MCP server is the best distribution channel. Ship it first.

**Recommended GTM sequence**:

1. Ship the Claude Code MCP server (built-in distribution via MCP ecosystem)
2. Produce a 3-minute demo video: agent provisions VM, deploys code, tears it down
3. Post to AI agent communities (r/ClaudeAI, AI Twitter, relevant Discords)
4. Write "Why crypto wallets are better than credit cards for AI agents" — the contrarian take that gets attention
5. Partner with 2-3 other MCP server creators for cross-promotion
6. Then pursue OpenCloud/OpenCode integrations

---

### 4. Pricing & Value Proposition

The USD-denominated credit system paid with crypto is a double-edged sword. It abstracts token volatility but adds a conversion step that creates friction.

**"Credit balance as natural spending limit" vs. AWS budget alert**: Rhetorically appealing but misleading in practice. AWS budget alerts can trigger automated shutdowns proactively. Meanwhile, acquiring ALEPH on an exchange, transferring to a wallet, and converting to credits via [credits.app.aleph.im](https://credits.app.aleph.im) is three friction points before a single VM boots. (Note: the credit console is live, which reduces this to two steps if the user already holds ALEPH.)

**The honest value prop**: The spending limit story works for users already in crypto. For everyone else, the overhead exceeds the benefit.

**Recommendation**: Lead with the autonomy story, not the spending limit story: *"Your agent can provision its own infrastructure with a keypair and a balance — no AWS account, no IAM roles, no credit card on file."*

---

### 5. Adoption Barriers (Blunt Assessment)

In order of severity:

1. **Crypto wallet requirement**: Single largest barrier. Most AI agent developers don't hold ALEPH tokens. Until fiat on-ramping exists, you are limited to the crypto-native audience. This is a market-size constraint, not a UX issue.
2. **Trust deficit**: "Let my AI agent control real money" makes most people uncomfortable. Three layers of trust simultaneously: the agent's judgment, key security, and an unfamiliar network.
3. **No quick-start experience**: Time-to-first-VM is too long. Compare to `fly launch` (one command).
4. **CRN count and reliability**: 300-500 CRNs is thin. If 10% are unhealthy, agent provisioning hits failures frequently, creating a bad first experience.
5. **Platform lock-in concern**: Developers will ask "what if Aleph goes away?" The small CRN count undercuts the decentralization reassurance.

---

### 6. Messaging Recommendations

**Developer one-liner**:
> "Give your AI agent its own compute budget — no AWS account, no credit card, just a keypair and a balance."

**Investor pitch**:
> "Every AI agent that provisions infrastructure through Aleph creates recurring demand for ALEPH tokens and CRN capacity — turning autonomous AI workloads into a sustainable driver of network economics."

**Lead with**: Safety/spending control, simplicity of keypair identity, agent autonomy.

**Avoid leading with**: "Decentralized compute" (most devs don't care), "self-replicating agents" (triggers fear), "censorship resistance" (niche).

---

### 7. Revenue & Sustainability

- **Token demand**: Every agent-provisioned VM requires ALEPH tokens. Agent workloads could create persistent buy pressure.
- **CRN utilization**: More VMs = better node operator economics = more CRNs = more capacity. The virtuous cycle.
- **Concern**: Agent VMs are likely short-lived (minutes to hours). Per-transaction revenue is small. Volume needs to be very high.
- **No SaaS layer**: Only revenue mechanism is token-mediated consumption. No recurring subscription or premium tier.

**Recommendation**: Consider a premium tier — managed agent accounts, enhanced dashboards, priority CRN access, SLA-backed compute. This creates revenue independent of token economics.

---

### 8. What Needs Market Validation

| Claim | Assessment | Validation |
|---|---|---|
| "Agents lack ability to self-provision infrastructure" | Partially true, rapidly changing (Terraform/CDK via agents exists) | Build MVP, see if devs choose this over `terraform apply` |
| "Crypto payment is better for agents" | True in theory, unproven in practice | Beta with 20 devs. Do they ask for credit card support in week 1? |
| "Credit balance = self-enforcing limit" | True but incomplete without software-layer controls | Ship spending controls before marketing this claim |
| "300-500 CRNs globally" | Optimistic framing. State current count. | Publish real-time CRN count and uptime stats |
| "Lower friction than traditional cloud" | False for non-crypto users | Measure time-to-first-VM honestly |

**Bottom line**: The core insight — crypto wallets are a natural fit for agent spending autonomy — is sound. But the document overestimates market readiness and underestimates adoption friction. Recommended path: (1) ship minimal MCP server for crypto-native Claude Code users, (2) measure usage, (3) build fiat on-ramp, (4) go after broader market. Do not invest in later phases until Phase 1 has live users.

*End of Business & Marketing Review*
