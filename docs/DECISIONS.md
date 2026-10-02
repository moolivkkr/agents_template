# DECISIONS — Durable Decision Ledger (Tier 0.5)

> **Why this file exists.** Runtime decisions — debate verdicts, ADRs, reconciler resolutions,
> gray-area picks — used to die inside a run's artifacts (`agent_state/debates/*.json`,
> `docs/adr/`, gate files). A new session or subagent never saw them, so it would re-litigate or
> contradict a settled call. This ledger is the **one durable, always-surfaced place** where every
> significant decision and its rationale lives. It sits between Tier 0 facts (immutable ground
> truth) and Tier 1 lessons (queried on demand): decisions are loaded/surfaced like facts but can
> be reversed like lessons.
>
> **Relationship to Tier 0.** A decision that hardens into an inviolable constraint (e.g. "graph DB
> is NebulaGraph, never Neo4j") should be promoted to `docs/PROJECT_FACTS.md` via `/remember`. Most
> decisions stay here: they are contextual ("we chose X for phase 2 because Y"), not universal laws.
>
> **How it's populated.** Every entry is written by `.claude/hooks/remember.sh decide` — the guard denies
> direct edits to this file, so the ledger can't be rewritten by a stray tool call:
> - `adr_agent` appends a `D-NNN` line when it writes an ADR (links to the ADR file).
> - `debate_arbitrator` appends a `D-NNN` line when it renders a verdict (links to the verdict JSON).
> - `/develop-orchestrator` Post-Gate appends decisions captured in `decision-log.md` for the phase.
> - Humans and agents record a notable gray-area pick with `remember.sh decide` (`--source human:/remember`
>   or `agent:<name>`).
>
> **How it reaches new work:**
> - The `SessionStart` hook (`inject-ground-truth.sh`) surfaces active decision titles into every
>   new session alongside Tier 0 facts.
> - The orchestrator ground-truth injection line names this file, so every spawned subagent reads it.
> - It is Required-Reading item 0b in every agent (after `PROJECT_FACTS.md`).

## How to read this file
- Act on decisions with `status: active`. Treat them as settled — do not re-open without cause.
- `reversed` decisions are kept for history; ignore them for current work (but they explain *why*
  the current active decision exists — useful context).
- If new evidence contradicts an `active` decision, don't silently diverge: append a reversing
  decision (`remember.sh decide … --reverses D-NNN`) with rationale, or escalate to `debate_moderator`.

## Entry format
(Real entries live under "Active Decisions" below. This is the shape — note the placeholder status
so this example is not parsed as a live entry by the SessionStart hook.)
```
### D-<NNN> — <one-line decision title>
- status: <active | reversed>
- scope: <global | phase-N | component:name>
- date: <YYYY-MM-DD>
- source: <debate | adr | reconciler | human | planner>
- reverses: —            # or D-MMM if this overturns a prior decision
- reversed_by: —         # set when a later decision overturns this one
- link: <artifact path — ADR file, verdict JSON, decision-log anchor>
- decision: >
    <what was decided>
- rationale: >
    <why — the tradeoff, the alternatives rejected, the evidence>
```

---

## Active Decisions

_None yet. The first `/plan` (ADR) or `/develop` (debate) run will populate this._

---

## Reversed Decisions (history — do not act on these)

_None yet._

### D-001 — RDS migrator: per-table migrator-only RLS policy (no BYPASSRLS on managed Postgres)
- status: active
- scope: global
- date: 2026-10-01
- source: human:/remember
- confidence: confirmed
- reverses: —
- reversed_by: —
- link: .claude/skills/infrastructure/eks.md
- decision: > On managed Postgres (RDS/Aurora) the migrator role is NOBYPASSRLS, because the RDS master user is not a superuser and cannot grant BYPASSRLS. Every migration that creates a tenant table with FORCE ROW LEVEL SECURITY also creates a permissive policy TO the migrator role only (USING (true) WITH CHECK (true)), so cross-tenant migrations and seeds work while the runtime role stays confined by RLS. The lab/self-hosted path keeps BYPASSRLS for the migrator.
- rationale: > Keeps FORCE RLS (the table owner cannot silently bypass isolation) and the same runtime isolation as the lab. Runner-up ENABLE-instead-of-FORCE on RDS rejected: the owner role would bypass RLS, which is weaker.

### D-002 — Graph TC gate: warning-first rollout of the stricter checks
- status: active
- scope: global
- date: 2026-10-01
- source: human:/remember
- confidence: confirmed
- reverses: —
- reversed_by: —
- link: .claude/hooks/sdlc-graph.py
- decision: > verify-gate check (h) (sdlc-graph gate) reports its NEW stricter findings (malformed TC ID cells, range-defined IDs, results mode required, base_sha required) as WARNINGS until a project opts into enforcement; everything the previous tc-inventory gate blocked on still blocks.
- rationale: > Existing projects (rera 275, brand-intelligence 87, ai-security 10 malformed rows) must first align to the new agent design; the owner expects a learning and fine-tuning period. Runner-up immediate enforcement rejected: it would block every in-flight phase at once.

### D-003 — EKS compute: EKS Auto Mode
- status: active
- scope: global
- date: 2026-10-01
- source: human:/remember
- confidence: confirmed
- reverses: —
- reversed_by: —
- link: .claude/templates/k8s/eks/infra/terraform/modules/platform
- decision: > EKS clusters use EKS Auto Mode (AWS-managed compute, ALB, EBS CSI, Pod Identity agent, network policy) via the terraform-aws-eks module.
- rationale: > Fewer controllers for us to install and upgrade; AWS manages node lifecycle. Runner-up managed node groups + Karpenter + self-installed AWS Load Balancer Controller rejected for operational load; accepted cost: Auto Mode's per-instance management fee.
