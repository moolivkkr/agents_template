---
skill: board-hat-sre
description: Board review hat — SRE. Failure modes built and tested, idempotent-only retries, timeouts, readiness semantics, graceful shutdown, metric cardinality, pool budgets, safe migrations and rollback, measured NFRs
version: "1.0"
tags:
  - review
  - board-review
  - reliability
---

# Hat: SRE

Follow `protocol.md` in this directory (format, severity, evidence, report-everything). Prefix: `SRE`.

**Your question:** when something these agents built (or these agents themselves) meets a slow
dependency, a restart, a bad deploy or load, what happens? And is anyone measuring it?

## Read

- every target agent
- the reliability, observability and resiliency packs they load (and the per-language archetypes
  that exist but may not be loaded)
- the k8s or deploy templates
- `/rollback` and `/deploy`

## Checklist

1. **Failure is built in.** Check whether the coding agents are told about:
   - timeouts on every outbound call
   - retries only for idempotent operations, with backoff and a cap
   - circuit breakers where a dependency can hang
   - graceful degradation when an optional dependency is down
2. **Failure is tested.** Look for a test tier that exercises a dependency that's down or slow, a
   timeout firing, SIGTERM under load, a pod kill, or a DB restart. If none does, that's a finding.
3. **Health semantics.**
   - **Liveness:** no dependency checks.
   - **Readiness:** required dependencies only. An optional cache inside readiness is a finding.
   - **Shutdown:** stop accepting, drain, then exit, with a preStop delay where the platform needs it.
4. **Resource budgets.** Check connection pools against database limits across replicas, memory
   limits against the runtime, and per-tenant pools.
5. **Telemetry.**
   - Metric labels must have bounded cardinality: no `tenant_id` and no raw URL path as labels.
   - Logs must be structured and must not leak secrets.
   - Traces need a collector that actually exists.
6. **Migrations and rollback.**
   - Migrations use expand/contract and stay N-1 compatible.
   - Rollback must not depend on DOWN migrations against live data, and must not contradict a
     forward-only deploy model.
   - Advice that is invalid SQL for the target engine is a finding.
7. **Measured NFRs.**
   - Performance and availability targets must be run as tests on the certified environment, with
     thresholds that fail the gate.
   - Text that merely recommends a load test doesn't count.
8. **Agent operations.** For agents that orchestrate others, check:
   - **Hand-back:** what happens when a child returns early or with a progress note?
   - **Limits:** are concurrency and depth bounded by real caps rather than prose?
   - **Stalls:** can one stuck child stall the run silently?

## Defect classes the 2026-09-30 run found (check they're still fixed)

- `/rollback` running DOWN migrations before redeploying
- retries on timeouts and 5xx with no idempotency condition
- `tenant_id` on every metric
- `reliability_agent` never spawned
- `performance_agent` recommending rather than running load tests
