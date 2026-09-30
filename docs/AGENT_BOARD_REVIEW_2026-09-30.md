# Board review: coding and testing agents (2026-09-30)

Six reviewers, each wearing one hat — **architect, senior developer, tester, SRE, DevOps, cyber
security** — critically reviewed the framework's 22 coding and testing agents. Every finding had to cite
the file and line it came from. Three independent verifiers then re-checked every CRITICAL and HIGH
finding: they tried to refute each one and reproduced runtime claims (the gate, grep, Go, Docker, Postgres,
the permission guard) outside the repo.

**Result:** 145 findings. After verification: **1 CRITICAL, 52 HIGH**, about 82 MEDIUM and 10 LOW. The
verifiers confirmed 42 of the 77 serious findings as rated, lowered 23 and marked 12 partial. **They
refuted none.** The 145 findings collapse into 14 root causes (below); most show up under several hats.

**In one paragraph:** the agents are good at *describing* the right behaviour and weak at *proving* it.
- **The gate can't see a failed test run.** It passed a phase whose e2e and acceptance reports said FAIL
  and BLOCKED.
- **The evidence it reads predates the last fixes.** Test results come from before the Wave 4/5 changes.
- **Test coverage is counted by the presence of an ID string.** A skipped test or a TODO comment counts.
- **Coding agents don't know the contracts their code must meet.** The API envelope is defined eight
  ways, and nobody gives the runtime contract to the agents that write the code.
- **Security and reliability are inspected after the code is written, not given to the writers.**

The React Native agents, the newest, are the model to copy: they scored highest under every hat.

Full evidence: [the six hat reports and three verification reports](board-review-2026-09-30/). IDs such as
`TEST-01` or `SEC-03` refer to rows in those reports.

---

## Scores (1 = would block, 5 = would ship as-is)

| Agent | Arch | Dev | Test | SRE | Ops | Sec | Avg |
|---|---|---|---|---|---|---|---|
| e2e_orchestrator | 1 | 2 | 2 | 2 | 1 | 2 | **1.7** |
| performance_agent | 2 | 2 | 1 | 1 | 1 | 3 | **1.7** |
| code_optimizer | 2 | 1 | 2 | 2 | 2 | 2 | **1.8** |
| system_test_agent | 2 | 1 | 1 | 2 | 2 | 3 | **1.8** |
| api_developer | 2 | 2 | 2 | 2 | 2 | 2 | 2.0 |
| backend_developer | 2 | 2 | 2 | 2 | 2 | 2 | 2.0 |
| migration_agent | 2 | 2 | 2 | 1 | 2 | 3 | 2.0 |
| ui_code_optimizer | 1 | 1 | 2 | 3 | 3 | 2 | 2.0 |
| ui_developer | 2 | 3 | 3 | 2 | 2 | 1 | 2.2 |
| unit_test_agent | 2 | 2 | 2 | 2 | 2 | 3 | 2.2 |
| ui_test_agent | 2 | 2 | 2 | 3 | 2 | 2 | 2.2 |
| database_agent | 2 | 3 | 3 | 2 | 3 | 2 | 2.5 |
| integration_test_agent | 2 | 3 | 3 | 2 | 2 | 3 | 2.5 |
| acceptance_test_agent | 2 | 3 | 3 | 3 | 2 | 2 | 2.5 |
| spec_test_reconciler | 3 | 3 | 2 | 2 | 3 | 2 | 2.5 |
| test_runner | 3 | 3 | 2 | 3 | 2 | 3 | 2.7 |
| manual_test_agent | 3 | 3 | 2 | 2 | 3 | 3 | 2.7 |
| solution_selector | 3 | 3 | 4 | 2 | 3 | 2 | 2.8 |
| accessibility_auditor | 3 | 4 | 4 | 3 | 2 | 3 | 3.2 |
| mobile_test_agent | 3 | 4 | 4 | 3 | 3 | 3 | 3.3 |
| mobile_developer | 3 | 4 | 4 | 3 | 3 | 4 | 3.5 |
| mobile_e2e_orchestrator | 4 | 4 | 4 | 4 | 4 | 3 | **3.8** |

**Why the mobile agents lead:** they have an explicit anti-shortcut table, and "flaky" does not count
as a pass. Evidence is kept per platform (JUnit XML, screenshots, device logs), and they have a real
Definition of Done. Those are the patterns to port to the web and backend agents.

---

## The 14 root causes, ranked

Severity is the verified one. The IDs listed under each are the duplicates the verifiers merged.

### 1. The gate can't see test failures, and it gates code nobody re-tested — CRITICAL
`TEST-01` (C) · `TEST-03` · `TEST-04` · `TEST-05` · `OPS-03` · `DEV-08` · `SEC-07`
- **Reproduced by two verifiers:** `verify-gate.sh` returned PASS on the normal base roster for a phase
  whose e2e failed, whose acceptance report said FAIL with a CONTRACT_VIOLATION BLOCKER, and for one
  saying "BLOCKED / UNTESTED".
  - Its markdown fallback only looks for `total: 0`, `SKIPPED` and `BLOCKING`.
  - Only `test_runner` writes a `failed` count, and the deterministic floor doesn't require
    `test_runner`.
- **The LLM-scored layer passes partial failure by design.** 1 of 8 acceptance cases failing still
  scores 0.98.
- **The evidence predates the final code.**
  - `test_runner` runs once (Wave 3v). Wave 4/5 fixes are checked by the agent that made them.
  - The parent's re-run is LLM-executed, not tied to a commit, and piped through `tee`, which hides the
    exit code.
  - Nothing redeploys, so e2e and acceptance evidence describes an older build.
  - Check (e), the execution-grounded one, never runs because nothing creates `sdlc-verify.json`.
  - `deploy_verification.json` is written but the gate never reads it.

**Fix (M):**
1. Every test tier writes a JSON sidecar `{total, passed, failed, skipped, git_sha}`. Acceptance writes
   a per-use-case verdict list. The gate BLOCKs on any `failed > 0`, and on any HIGH acceptance case that
   is FAIL, BLOCKED or UNTESTED.
2. Add `test_runner` and `spec_test_reconciler` to the deterministic floor, plus `acceptance_test_agent`
   whenever the phase has FRs.
3. Add a final verification step after Wave 5:
   - redeploy dev → qa if any code changed since Wave 3.5;
   - `test_runner` re-runs every tier at HEAD;
   - e2e and acceptance re-run against qa;
   - the gate compares every sidecar's `git_sha` to HEAD.
4. A HIGH failure caps the graded score below the pass threshold.
5. Log the deploy to `execution.jsonl` so the gate reads `deploy_verification.json`.
6. Add gate tests for a markdown report with failures, and for a BLOCKED acceptance report.

### 2. Tests are counted, not proven — HIGH
`TEST-02` · `DEV-13` · `TEST-06` · `TEST-08` · `TEST-10` · `TEST-11` · `SRE-11` · `TEST-07` (M)
- **TC coverage means "the ID string appears somewhere in the repo"** (reproduced). IDs recycled from
  phase 1, `t.Skip` tests, TODO comments and the two ends of a range comment all count as covered. Any
  `*.yaml` file counts, pytest `test_*.py` files don't, and scanner errors turn into "skip the check".
- **Nothing ever observes a test failing against broken code.** There is no mutation testing, and no
  red-first step for feature tests.
- **Tests can be weakened unnoticed.** The same agent writes, fixes and runs a tier. Deleted assertions,
  new skips and `.only` go undetected.
- **Flakes are retried to green,** and `t.Skip` quarantine never lifts. Nothing runs `-race`.
- **Acceptance tests are ad-hoc runs, never committed.** `TC-ACC` means "accessibility" in one skill and
  "acceptance" in another.

**Fix (M–L):**
- Replace the grep-based TC inventory with a small parser. It should count an ID only on a non-skipped
  test case in the current phase's test files, and IDs should be phase-scoped (`TC-P3-API-001`).
- Add a test-diff check at the gate: removed assertions, new skips or `.only` since phase start BLOCK
  unless listed with a reason.
- Run mutation testing on changed files (Stryker, gremlins/go-mutesting, mutmut): advisory first, then a
  floor.
- Treat pass-on-retry as a FLAKY failure. Use Playwright `failOnFlakyTests` (available since v1.52) and
  Go `-race -count=1`. Quarantine needs an issue and an expiry.
- Commit acceptance tests as runnable specs and rename accessibility IDs to `TC-A11Y`.

### 3. The API contract is defined eight ways — HIGH
`ARCH-01` · `DEV-03` · `ARCH-04` · `DEV-18` (M) · `ARCH-05` (M)
- **Eight incompatible definitions.** The success envelope, pagination and error shape are defined
  differently across `api_developer`, its own skill pack, `spec_writer`, the type-generation and
  error-handling skills, and both UI and integration test templates.
  - `ui_test_agent`'s mock labelled "✅ CORRECT" contradicts `api_developer`.
  - The check proving as-built API = planned contract before UI work isn't executed on the canonical
    path.
- **Why HIGH rather than CRITICAL:** `data-contracts.md` is designated the source of truth and drift is
  a blocker, so the usual result is fix churn rather than silent breakage.

**Fix (M):**
- One canonical envelope skill, referenced by every agent; delete or replace every contradicting example.
- `spec_writer` emits OpenAPI. Integration tests validate responses against it, and UI mocks (MSW) are
  generated from it.
- Run the contract check before any UI work starts.

### 4. The k8s runtime contract has no owner, and the tests don't target qa — HIGH
`OPS-01` · `ARCH-10` (M) · `DEV-10` (M) · `SRE-16`→H · `OPS-07` · `OPS-02` · `ARCH-09` · `TEST-09` · `OPS-11` · `DEV-24`

*Most of this is in the dev/qa deploy layer added earlier the same day.*

- **The coding agents don't know the runtime contract.** It lives only in `deployment_agent` §3g and
  the templates:
  - `serve`/`migrate`/`seed` subcommands;
  - `/healthz`, `/readyz` and `/api/version`;
  - a numeric USER and a read-only filesystem;
  - DB connection retry.

  §3g adapts the layer when it runs, but it doesn't run in `/develop`.
- **Health paths drift:** `/health` vs `/healthz` + `/readyz`, and environment names differ too.
- **The test tiers don't target qa.**
  - Web e2e (Wave 3c) runs *before* the deploy (Wave 3.5).
  - `APP_BASE_URL` is exported in a throwaway shell and never reaches an agent.
  - Acceptance, accessibility and mobile hard-code `localhost:8080`.
  - So the artifact promoted to qa gets only `smoke.sh`.
- **Builds from the repo root are always `-dirty`,** because `agent_state/` is inside the build context
  and not ignored.

**Fix (M):**
- Add a runtime-contract section to the IMPLEMENTATION_GUIDELINES template; backend, api and migration
  agents read it.
- Use one health-path convention everywhere.
- Move Wave 3.5 before Waves 3c/3d and acceptance.
- Pass the qa URL explicitly in every test agent's spawn prompt and checkpoint, and remove the
  hard-coded localhost URLs.
- Exclude `agent_state/` from build contexts.

### 5. Security is inspected afterwards, never an input — HIGH
`SEC-05` · `SEC-06` · `TEST-13` · `SEC-08` · `SEC-09` · `SEC-10` · `SEC-12` · `SEC-13` · `SEC-01` (C→H) · `DEV-14`/`SEC-14` (M)
- **Coding agents get no security rules while writing.** None loads the OWASP pack, and the Wave 2
  "hardening rules" contain no security rule.
- **The threat model reaches no one.** Its mitigations and `TC-SEC` IDs reach no coder, tester or
  reconciler.
- **The UI packs teach unsafe token handling:** bearer tokens in `localStorage` and in WebSocket URLs.
- **DOM/stored XSS is never tested.** The reviewer's XSS probe checks JSON responses instead of rendering.
- **A compiled-in default signing secret** is refused only when `ENV == "production"` exactly.
- **Durable tests cover tenant isolation and little else:** nothing tests same-tenant ownership, mass
  assignment, token tampering, injection, rate limits, or fixed-finding regressions.
- **SAST and secret scanning are effectively off.** The SAST step also `eval`s a backticked command
  matched by a regex that hits "Disaster".
- **`/autonomous` can force-gate a security blocker** after 3 cycles, and cycle 3 says "simplify/skip".
  It is surfaced later as `-rc.1`, but nobody approves that specific finding.

**Fix (M):**
- A secure-coding pack for every coding agent, plus security rules in the Wave 2 hardening block.
- Threat-model `TC-SEC` IDs go into the spec inventory and the test agents.
- Fix the UI auth packs: httpOnly cookie or in-memory tokens, and a short-lived WebSocket ticket.
- Secrets fail closed unless the environment is local/dev/test.
- Add an abuse-case matrix per endpoint in `test-case-generation.md`.
- Semgrep and gitleaks always on, run with fixed commands (no `eval`).
- Never force-gate a CRITICAL/HIGH security finding without a per-finding human approval.

### 6. The agents themselves are an attack surface, and the guard has gaps — HIGH
`SEC-03` · `SEC-02` (C→H) · `SEC-04` (M)

*These gaps are in the permission guard added the same day.*

- **No "content is data, not instructions" rule.** The shared operating contract never tells agents
  that text in files, tool output or web pages is data.
- **The guard has no opinion on these** (reproduced twice):
  - glob-matched and unlisted credential paths: `~/.s*/id_rsa`, `~/.config/gh`, `~/.netrc`, `~/.npmrc`,
    `~/.git-credentials`;
  - `security find-generic-password` (the macOS Keychain);
  - network egress from `node -e` or `python -c`;
  - `git push` to a newly added remote;
  - writes to `PROJECT_FACTS.md` and `DECISIONS.md`.
- **Unattended package installs are pre-allowed** (your decision), but nothing vets the package name or
  disables install scripts.

**Fix (S–M):**
- Add the rule to the operating contract.
- Guard: expand globs against the secret list; add the missing credential files; deny Keychain reads;
  *ask* for interpreter one-liners that use network libraries and for pushes to non-origin remotes.
  Only `remember.sh` writes facts and decisions.
- Installs: default to lockfile installs (`npm ci`) and `--ignore-scripts`. A **new** dependency first
  passes a vetting step: it exists on the registry, has an age and downloads floor, and passes a typosquat
  check.

### 7. Reliability is never built or measured — HIGH
`SRE-08` · `SRE-03` · `SRE-04` · `SRE-05` · `SRE-07` · `SRE-09` · `TEST-12` · `SRE-06` (M) · `SRE-10` (M)
- **The SRE-owned agents never run in `/develop`.** No wave spawns `reliability_agent` or
  `observability_agent`, and no agent reads the SLOs.
- **The skill packs the coders load teach anti-patterns:**
  - retrying timed-out calls with no idempotency condition. Inbound `Idempotency-Key` does exist in
    `api-excellence.md`.
  - raw URL path plus `tenant_id` as metric labels, a cardinality explosion;
  - an optional cache inside readiness, so one Redis blip marks every pod unready;
  - no preStop/drain on SIGTERM (preStop sleep is GA in Kubernetes 1.34);
  - no connection-pool budget against Postgres `max_connections`.
- **NFR-PERF is never measured.** `performance_agent` is optional and told to *recommend* a load test.
- **No tier tests a slow or failing dependency,** apart from external-service timeouts.

**Fix (M–L):**
- Correct the packs, and load the per-language resilience and observability archetypes that exist but
  go unused.
- Run reliability checks against code in Wave 4.
- Make a qa load test a gated tier (k6 open model, NFR thresholds, JSON sidecar).
- Add toxiproxy failure-mode tests in integration, and a chaos smoke on qa (pod kill, Postgres restart).

### 8. Rollback and migrations fight the forward-only model — HIGH
`SRE-01` (C→H) · `SRE-02`/`OPS-12`/`ARCH-11`/`DEV-17`/`DEV-19` (M)
- **Rollback reverses the schema before the code.** For local, staging and prod, `/rollback` runs DOWN
  migrations before redeploying the old build, and lists `prisma migrate reset` (which drops the database)
  as an example.
  - The k8s path does this correctly: it rolls back code only.
  - Prod requires `--confirm`, and recent Prisma refuses reset without consent. It is still HIGH.
- **Expand/contract and N-1 compatibility** are known only to `migration_safety_reviewer`.
  `migration_agent` makes DOWN mandatory.
- **`migration_agent` recommends `ADD CONSTRAINT IF NOT EXISTS`,** which Postgres rejects (reproduced on
  17.10).

**Fix (S):**
- Redeploy the previous build first. Never run DOWN migrations automatically. Delete the
  `migrate reset` line.
- Make expand/contract and N-1 the migration author's default, with DOWN optional.
- Fix the invalid SQL.

### 9. Coding agents act as if the repo were empty, with no build gate between them — HIGH
`DEV-04` · `ARCH-03` · `DEV-02` (M) · `DEV-05` (M) · `DEV-09` (M) · `DEV-12` (M)
- **Implementers don't work from the existing code.** They never read the Wave 1 audit, and no agent
  has a read-before-edit, minimal-diff or follow-existing-conventions rule.
- **The canonical Wave 2 has no compile, typecheck, lint or test gate.** The legacy step file had one.
- **Handlers, middleware and migrations each have two or three authors.**
- **The Go test layout** (`tests/unit`) gives 0% per-package coverage (reproduced).

**Fix (M):**
- A build/typecheck/lint/unit gate after each implementer, using commands from one command table
  (see #13).
- Definition-of-Done items name those commands.
- Implementers read the audit and the codebase map first, and keep diffs minimal.
- One writer per artifact type.
- Colocate Go tests with their packages.

### 10. Fix agents and candidate mode skip the discipline — HIGH
`DEV-08` · `DEV-11` · `ARCH-06` · *new: acceptance spawn has no agent type*
- **Fix agents are untyped.** Wave 4/5 fixes go to general-purpose agents with a five-line prompt, no
  skill packs and no guardrails.
- **Candidate mode bypasses the role agents.** It is automatic for PLATFORM phases and produces no
  `api-contracts.md` or manifests, while the roster still demands the role agents.
- **The Wave 4 acceptance spawn names no `subagent_type`,** so `acceptance_test_agent`'s own
  instructions may never load.

**Fix (S–M):**
- Fixes are spawned as the owning role agent, with the finding and the guardrails.
- Security re-reviews every file changed in Wave 5.
- The candidate-mode winner must produce the same artifacts.
- Add a lint that every spawn in the orchestrator names `subagent_type`.

### 11. The optimizers can break behaviour (limited reach) — HIGH
`DEV-01` (C→H) · `DEV-06` · `DEV-07` · `TEST-14` · `ARCH-15`/`ARCH-16` (M)
- **They're told to edit tests until they pass:** "update test expectation to match new behavior" and
  "update mock to match optimized component".
- **They treat green tests as proof code is dead,** and they target error handlers for removal.
- **Their scope lock uses a tag nothing creates,** so it falls back to `HEAD~50`.
- **Limited reach:** they run only via `/optimize` and the legacy step 3f, not the canonical `/develop`.

**Fix (S):**
- Forbid test and mock edits: a failing test after an optimization means revert.
- Find dead code by static reachability (knip, Go `deadcode`, vulture), never by test pass.
- Never remove error handling.
- Scope from the phase's recorded start commit.

### 12. Hand-off artifacts that nobody produces — HIGH
`ARCH-07` · `ARCH-08` · `ARCH-19` (M)
- **Two inputs have no producer:**
  - `e2e_workflows_unlocked`, `e2e_orchestrator`'s only input;
  - `ui_developer/manifest.json`, required by `ui_test_agent` and `ui_code_optimizer`.
- **The dependency-graph test that should catch this can't** (reproduced). In its `fnmatch`, `*` also
  matches `/`, so `agent_state/phases/*/manifest.json` "produces" every per-agent manifest.
- Two of these were already open from the morning review (C1, C3 in `FRAMEWORK_REVIEW_2026-09-30.md`).

**Fix (S):**
- Produce the missing inputs, or change the consumers.
- Use a segment-aware glob in `tests/lib/depgraph.py`, with a regression case.

### 13. Commands and versions drift between agents, CI and environments — HIGH
`OPS-06` · `OPS-05` (M) · `OPS-08`/`OPS-09`/`OPS-10` (M) · `TEST-15` · *new: CI Postgres service has no ports*
- **No shared command table.** IMPLEMENTATION_GUIDELINES doesn't define build, test and lint commands,
  so writers, `test_runner`, CI and the orchestrator each infer their own.
- **Reproduced breakages:**
  - `test_runner`'s Go run hits the test cache (no `-count=1`) and prints no counts.
  - Its Jest fallback `--run` and its pytest `--integration` both fail.
  - Go `1.22` with `GOTOOLCHAIN=local` fails against a newer `go.mod`.
  - The `docker.md` USER line with an inline comment won't start a container.
  - `find -perm +111` fails on Linux.
- **Other drift:** the CI skill's Postgres service has no `ports:`, and Postgres is 16 in tests/CI but
  17 in k8s.

**Fix (M):**
- `/init` writes a *Commands and versions* table. It covers build, test per tier, lint, migrate and seed
  commands, plus runtime and DB versions, and every agent, `test_runner` and CI read it.
- Fix the listed skill bugs.

### 14. Stack and project leakage in the templates — MEDIUM
From the architect's verdict:
- The templates are hard-wired to React, Go and one earlier project (Vertix), even though the agent
  factory offers Vue, Angular and other stacks.
- Some instructions are too long, or contradict each other, for a model to follow reliably.

**Fix (M):**
- Move stack specifics into skill packs selected by `{{LANG}}`/`{{FRAMEWORK}}`.
- Delete project-specific sections.

---

## Per-agent feedback

"C/H" lists the verified CRITICAL/HIGH findings that name the agent. Details are in the linked reports.

| Agent | Avg | C/H findings | First change for this agent |
|---|---|---|---|
| e2e_orchestrator | 1.7 | TEST-01, ARCH-07, ARCH-09, OPS-02, OPS-03, SRE-11, TEST-03, TEST-08, TEST-09, SEC-09, SEC-12, SEC-03 | Run after deploy against the qa URL. Scope from spec workflows, not a missing input. Write a JSON sidecar. Treat retries as failures. Stop grading its own fixes. |
| performance_agent | 1.7 | SRE-09, TEST-12 | Run a real open-model load test on qa with NFR-PERF thresholds, as a gated tier, instead of recommending one. |
| code_optimizer | 1.8 | DEV-01, DEV-06, DEV-07, TEST-14, SEC-07 | Never edit tests. Find dead code by static reachability. Keep error handling. Fix the scope lock. |
| system_test_agent | 1.8 | — | It has no method, no environment and is never scheduled; it duplicates acceptance. Merge it into acceptance or give it a procedure and a slot. |
| api_developer | 2.0 | ARCH-01, ARCH-03, ARCH-04, DEV-03, DEV-04, DEV-11, OPS-01, SEC-02, SEC-05, SRE-03, SRE-04 | Use one canonical envelope. Follow the runtime contract and secure-coding rules. Keep minimal diffs over existing code. |
| backend_developer | 2.0 | ARCH-03, DEV-04, DEV-11, OPS-01, OPS-07, SEC-02, SEC-05, SEC-10, SRE-03, SRE-04, SRE-05, SRE-07 | Stop writing migrations and handlers others own. Default secrets fail closed. Retry only idempotent calls; keep readiness without optional deps; budget connection pools. |
| migration_agent | 2.0 | ARCH-03, OPS-01, SRE-01 | Default to expand/contract and N-1 compatibility. Fix the invalid SQL. Don't make DOWN migrations mandatory. |
| ui_code_optimizer | 2.0 | ARCH-08, DEV-01, DEV-06, DEV-07, TEST-14, SEC-02 | Never edit mocks. It requires a manifest nobody produces; fix that together with #12. |
| ui_developer | 2.2 | ARCH-01, ARCH-04, ARCH-08, DEV-03, DEV-04, DEV-14, SEC-02, SEC-05, SEC-08, SEC-09 | Keep tokens out of `localStorage` and URLs. Use safe rendering, and no browser-side LLM calls. Bind to the as-built contract. Write its manifest. |
| unit_test_agent | 2.2 | TEST-01, OPS-06, SEC-12, SRE-11, TEST-06 | Write tests from the spec, not the source. Mock less, observe a failing test, colocate Go tests. Write a JSON sidecar. |
| ui_test_agent | 2.2 | TEST-01, ARCH-01, ARCH-08, ARCH-09, DEV-03, OPS-02, SEC-08, SEC-09, SEC-12, TEST-06, TEST-08, TEST-09 | Split its five tiers. Fix the axe API (`@axe-core/playwright` has no `injectAxe`). Drop contrast checks in jsdom. Use contract-generated mocks. |
| database_agent | 2.5 | ARCH-03, SRE-07 | Own the schema and connection budget; hand migrations to one owner. |
| integration_test_agent | 2.5 | TEST-01, ARCH-01, ARCH-04, DEV-03, OPS-06, OPS-07, SEC-12, SRE-03, SRE-11, TEST-06, TEST-08 | Fix the envelope rule. Add the abuse-case matrix and failure-mode tests. Treat a DB outage as a test result, not "environment". |
| acceptance_test_agent | 2.5 | TEST-01, ARCH-01, ARCH-09, DEV-03, OPS-02, OPS-03, OPS-07, SEC-03, SEC-12, TEST-03, TEST-05, TEST-09, TEST-11 | Be spawned by its agent type. Target qa. Commit runnable acceptance specs. Write per-use-case verdicts the gate reads. |
| spec_test_reconciler | 2.5 | DEV-13, SEC-06, SRE-09, TEST-02, TEST-04, TEST-05, TEST-13 | Replace the grep inventory with a parser (non-skipped tests, current phase). Include TC-SEC and NFR-PERF. |
| test_runner | 2.7 | OPS-03, OPS-06, SEC-03, SEC-13, SRE-11, TEST-03, TEST-04, TEST-06 | Be in the mandatory floor and run again at HEAD after fixes. Use `-count=1`/`-race`, and read commands from the command table. |
| manual_test_agent | 2.7 | — | Record env, URL and `git_sha`. Add game-day/DR scripts (SRE). Never write credentials into scripts. |
| solution_selector | 2.8 | ARCH-06, DEV-11 | Its winner must produce the same artifacts as the role agents (contracts, manifests, migrations). |
| accessibility_auditor | 3.2 | ARCH-09, OPS-02, TEST-09 | Target the qa URL; state the WCAG version consistently. |
| mobile_test_agent | 3.3 | TEST-01, ARCH-01, OPS-11, SEC-12, TEST-08 | Use the canonical envelope for mocks, and the qa URL. Otherwise it's the best writer prompt; port its anti-shortcut table to the web agents. |
| mobile_developer | 3.5 | DEV-04, OPS-06, OPS-11, SEC-02, SEC-05 | Follow the runtime and API contracts, and vet new dependencies. |
| mobile_e2e_orchestrator | 3.8 | ARCH-09, OPS-02, OPS-07, OPS-11, SEC-03, TEST-09 | Target qa on k8s projects (its preflight assumes compose). Use it as the template for `e2e_orchestrator`. |

---

## What the verifiers cut or corrected

- **Nothing was refuted, but 35 claims were overstated in severity or scope.** The main corrections:
  - **The gate case is narrower than the tester's example.** It passes a phase with 10 failing *unit*
    tests only when `test_runner` is missing from the roster. With it present, its sidecar blocks.
  - **"Nothing re-runs tests" is too strong.** The parent's re-run exists; it just isn't
    commit-bound or exit-code safe.
  - **The runtime-contract crash loop isn't deterministic.** `deployment_agent` §3g adapts the k8s layer
    to the app's real commands when it runs.
  - **Expand/contract is enforced,** as a HIGH/BLOCKING rule, by `migration_safety_reviewer`.
  - **Inbound idempotency keys exist** (`api-excellence.md`), and external-service timeout tests exist
    (`external-service-mocks.md`).
  - **The package-hallucination figure was misquoted.** It is 19.7% of generated package *references*,
    measured on 2024-era models.
  - **preStop sleep is GA in Kubernetes 1.34,** not 1.32.
  - **The auth model does have an owner:** IMPLEMENTATION_GUIDELINES §4.1/§4.5.
  - **The optimizers' damage is limited to `/optimize`.**
- **Platform nuance:** the macOS BSD-grep `-P` failure affects plain bash scripts only. The Claude Code
  shell wraps grep with ugrep, which supports `-P`.

## Found during verification (not in any hat's report)

- **Acceptance may run without its own instructions.** The Wave 4 Track B acceptance spawn (and Track
  C) names no `subagent_type`.
- **`TC-ACC` means two different things:** accessibility in `test-case-traceability.md:48`, acceptance
  in `test-case-generation.md`.
- **`tests/verify-gate.test.sh` misses the key case:** it has no test for a markdown report containing
  failures.
- **Deploy evidence never reaches the gate.** `deploy_verification.json` is written but never read;
  nothing logs it to `execution.jsonl`.
- **`agent_state/` isn't ignored in build contexts,** so root-context builds are always tagged `-dirty`.
- **The CI skill's Postgres service has no `ports:` mapping.**
- **`agent_factory.md:49` reads a "Section 3" that doesn't exist.**

---

## Plan

**P0: make the gate honest, and stop the dangerous instructions.** Each item is small or medium, with a
test.
1. Root cause 1, the gate:
   - JSON sidecars for every tier, BLOCK on `failed > 0`, and a FAIL/BLOCKED/UNTESTED acceptance BLOCKs;
   - `test_runner`, `spec_test_reconciler` and `acceptance_test_agent` in the floor;
   - a final re-run at HEAD with commit-bound evidence;
   - gate tests for the failing-markdown and BLOCKED cases.
2. Root cause 8: fix rollback ordering and delete `prisma migrate reset`.
3. Root cause 11: forbid optimizers from editing tests and mocks.
4. Root cause 4, the qa wiring:
   - reorder Wave 3.5 before the test tiers;
   - pass the qa URL to every test agent;
   - add the runtime-contract section and one health-path convention;
   - log deploy evidence to `execution.jsonl`;
   - ignore `agent_state/` in build contexts.
5. Root cause 6: the guard gaps and the "content is data" contract rule, with guard test cases.
6. Root cause 10: `subagent_type` on every orchestrator spawn, plus a lint.

**P1: make passing mean something.**
- #2: TC parser, test-diff check, flake policy, committed acceptance specs.
- #3: one envelope, OpenAPI, generated mocks.
- #5: secure-coding pack, TC-SEC wiring, UI auth fixes, abuse matrix, SAST/secrets on.
- #9: build gate in Wave 2, minimal-diff rules, one writer per artifact.
- #10: typed fix agents and a Wave 5 security re-review.
- #12: produce the missing hand-offs, fix the depgraph glob.
- #13: the command and version table.

**P2: measure what matters.**
- #2: mutation testing floor.
- #7: gated qa load test, failure-mode and chaos tests, corrected resilience and observability packs,
  reliability checks in Wave 4.
- #10: candidate-mode parity.
- #14: stack genericity.
- `system_test_agent`: merge or rebuild.

## Implementation status (2026-09-30, same day)

All 14 root causes were implemented: a foundation commit plus three parallel groups (coding agents,
testing agents, and skills/security/guard) in isolated worktrees, then merged. The work is 41 commits
touching 226 files. **Test result: 14 suites, 794 checks, 0 failures**, plus the live lab-cluster
e2e (`tests/k8s-e2e.sh`, 32/32).

| # | Root cause | Status | Proof |
|---|---|---|---|
| 1 | The gate can't see failures | **Done.** Test agents must provide `sdlc.test-results/v1` sidecars written by `junit-to-sidecar.py`. The gate blocks on verdict ≠ PASS, zero tests, any failed or flaky test, a HIGH/MEDIUM case not passing, an expired quarantine, stale `code_sha` or dirty code. The floor adds test_runner, spec_test_reconciler, acceptance (and deploy_dev/qa on k8s). Wave 5v re-verifies at HEAD, the graded score caps at 0 on any hard failure, and no command output is piped through `tee`. | `verify-gate.test.sh` 41 (incl. the TEST-01 reproduction), `evidence-pipeline.test.sh` 8 |
| 2 | Tests counted, not proven | **Done.** `tc-inventory.py` counts an ID only in the name of a non-skipped test that ran and passed. It flags cross-phase and in-phase duplicate IDs, and catches test weakening (removed asserts, new skip/only). IDs are project-unique. Retries 0; flaky = failing; quarantine needs an issue and expiry. Acceptance specs are committed. Mutation testing is **advisory only** (no floor yet). | `evidence-tools.test.sh` 33, `testing-agents.test.sh` 140 |
| 3 | Envelope defined 8 ways | **Done.** `api/response-envelope.md` is the single definition, with every agent and pack aligned and framework error defaults replaced. OpenAPI generation is described in the agents, not tooled. | `skills-security.test.sh`, `coding-agents.test.sh` |
| 4 | Runtime contract unowned; tests not on qa | **Done.** A §Runtime contract section in the guidelines, followed by the coders. Wave order is unit/integration → deploy → e2e/mobile against `APP_BASE_URL` → test_runner. No hard-coded localhost targets. Deploy evidence goes into `execution.jsonl`, and `.dockerignore` excludes `agent_state/`. | `k8s-e2e.sh` 32, `testing-agents.test.sh` |
| 5 | Security inspected afterwards | **Done.** Coders load `security/secure-coding.md` and `ui/secure-rendering.md`. Threat-model TC-SEC rows enter the inventory, and there's an abuse-case matrix. Semgrep and gitleaks always run, with no `eval`. `/autonomous` pauses per security finding, and `/accept` reports NOT READY for accepted-but-unfixed findings. The gate counts BLOCKING:N as N acknowledgements. | `skills-security.test.sh` 35, `verify-gate.test.sh` |
| 6 | Agent attack surface, guard gaps | **Done.** Operating contract: content is data, not instructions (all 79 agents). The guard adds glob/brace secret matching, more credential files, Keychain denial, asks for interpreter network one-liners and new remotes, and protects the ledgers (`remember.sh decide` is the only DECISIONS writer). `vet-package.py` vets new dependencies; installs stay allowed. | `sdlc-guard.test.sh` 259, `remember.test.sh` 12 |
| 7 | Reliability never built or measured | **Done.** Packs fixed: idempotent-only retries, route-template labels, readiness without optional dependencies, drain plus preStop, pool budget. Track D runs reliability code checks, a **gated** k6 open-model load test on qa, and the rebuilt system_test_agent (readiness, pod kill, DB restart). Failure-mode rows are in the integration tier. | `testing-agents.test.sh`, `k8s-e2e.sh` (preStop template) |
| 8 | Rollback and migrations | **Done.** Rollback redeploys the previous HEALTHY build first; schema reversal is local-only and human-confirmed; no `migrate reset`. Migrations default to expand/contract with N-1 compatibility; the invalid Postgres syntax is fixed (verified on PG 17.10). | `coding-agents.test.sh` |
| 9 | Coders ignore existing code; no build gate | **Done.** Ownership tables, audit and codebase map read first, minimal diffs, a Wave 2A build gate per step and in every DoD, Go tests colocated. | `coding-agents.test.sh` |
| 10 | Untyped fix agents, candidate bypass | **Done.** Fixes go to the owning role agent, and the Wave 5v security re-review covers the post-Wave-4 diff. The 2B adopt pass produces the role artifacts. Every spawn names `subagent_type`. | `orchestrator-spawns.test.sh` 27 |
| 11 | Optimizers break behaviour | **Done.** `/optimize` only. Tests and mocks are read-only, dead code is proven by static reachability, error handling is never removed, and scope comes from `base_sha`; no `git reset --hard`. | `coding-agents.test.sh` |
| 12 | Unproduced hand-offs | **Done.** `ui_developer/manifest.json` is declared and produced, e2e scope comes from the spec inventory, and the depgraph matching is segment-aware (regression fixture). | `dependency-graph.test.sh` 54 |
| 13 | Commands and versions drift | **Done.** A `## Commands and versions` table is parsed by `commands-table.py` and read by agents, test_runner, CI and gate check (e). The docker USER bug and CI Postgres ports are fixed, and test_runner's broken fallbacks are removed. | `evidence-tools.test.sh` (CT01-04), `coding-agents.test.sh` |
| 14 | Stack and project leakage | **Done (follow-up, same day).** Vertix and the browser-LLM sections are removed, and the coding rules are language-neutral. A design system is used only when the project names one (`tech_profile.frontend.design_system`); ux_designer and design_quality_reviewer no longer hard-load Vertix, shadcn or Tailwind. `/develop` Wave 2/3.5 and `/accept` build with the Commands-and-versions rows, not go/npm/cargo guesses. Vue and Svelte packs are extended and an Angular pack is new, each covering the envelope client, cursor lists, 4 states, forms, session, safe rendering, a11y and component tests. | `coding-agents.test.sh` (10 genericity checks), `ui-framework-packs.test.sh`, `tests/archetype-compile/ui-frameworks/run.sh` |

**Tool flags, verified by running them (2026-09-30, follow-up):** everything except Spring was run
for real on this machine. Spring was checked against the Spring Data docs, because no JDK is installed.
Two recipes could pass a run that should fail; both are fixed and have regression tests:
- **k6 parser (`performance_agent`) failed open.** With `--no-thresholds`, or with a scenario tag that
  matched no request, k6 exits 0 and reports p95 = 0, so the parser said PASS while the real p95 was
  405 ms against a 300 ms target. It now fails a case whose three thresholds weren't all evaluated, or
  which saw no requests. The seven real k6 v2.3.0 summaries are fixtures in `tests/fixtures/k6/`; the
  old parser passes two of them.
- **`go test -json | go-junit-report` failed open.** The default parser drops a package that fails to
  build, and the pipe replaces the exit code with 0, so the sidecar said PASS. The recipe now uses
  `-parser gojson` and keeps go test's exit code.
- **Fail-closed fixes:**
  - Playwright `--reporter=junit` rows wrote no file (the flag replaces the config's reporters). They
    now set `PLAYWRIGHT_JUNIT_OUTPUT_FILE` and pass `--reporter=list,junit`. The `x:acceptance` row
    uses its own `--config`.
  - `test_runner` silently dropped `-race` where cgo was off; the report now says races were NOT checked.
  - `junit-to-sidecar.py` merged Playwright projects, so a chromium-only failure read as FLAKY and the
    total halved. It now keys cases by project.
  - The TC regex now also matches `TestTC_UNIT_10101` function names.
  - `vulture --min-confidence 80` hid every unused function (vulture rates them all 60%); it's now 60.
  - The Java archetypes used `Specification.where(null)`, which Spring Data JPA 4.0 rejects.
  - golang-migrate note: a leading `SET lock_timeout` breaks a `CONCURRENTLY` file.
  - `deadcode` guidance: the exit code is always 0, test-only code is reported, and a library's
    exported API is off limits.
- **Verified as written:**
  - `gotestsum … -count=1 -race`, and `GOFLAGS` honoured;
  - all three Vitest `--outputFile` forms;
  - Playwright config reporters;
  - k6 summary keys and exit 99 on a broken threshold;
  - Alembic `autocommit_block()` with `CREATE INDEX CONCURRENTLY` (upgrade, downgrade and re-run, on
    Postgres 17);
  - `deadcode -test`, knip;
  - every Spring Data `scroll()` / `Window` / `ScrollPosition` call (minimum Spring Data 3.1, Boot 3.1).
- **Archetype samples, compiled and run (follow-up, same day).** There were about 790 code blocks in 75
  archetype files, not ~30. Each language now has a re-runnable harness in `tests/archetype-compile/<lang>/`.
  It extracts the blocks from the markdown at run time and fails when a block is neither checked nor
  skipped with a reason. An offline inventory check for each language runs in `run-all.sh`. The harnesses
  need the toolchain and network for the first dependency install, so they stay opt-in.

  | Language | Blocks checked | Units | Also run |
  |---|---|---|---|
  | Go 1.27.1 | 146/151 (5 comment-only) | 9/9 | handler/service tests; repository tests 26/26 on Postgres |
  | Python 3.12 (pyright) | 162/163 | 15/15 | handler 51/51, service 43/43; repository 32/32 + migrations 4/4 on Postgres |
  | TypeScript 7.0.2 strict | 198/200 | 20/20 | handler 40/40, service 43/43; `prisma validate`; Nest DI probe |
  | Rust 1.98.1 | 157/182 (25 unchecked blocks in the newly covered `languages/rust.md` and `frameworks/axum.md`) | 11/11 | 97/97 on Postgres 17, full migration set |
  | Java 25 / Spring Boot 4.1 | 143/145 | 18/18 | handler 64/64, service 34/34, repository 40/40 on Postgres |
  | Vue / Svelte / Angular packs | 41/41 | 3/3 | 7 component tests each |

  Running them found more than compile errors. The fixes include:
  - an SQL injection (`ORDER BY` direction, Go);
  - gRPC streams with no auth (Go) and a gRPC server whose middleware never ran (TS);
  - JWTs taken from websocket URLs (Go, TS, Rust);
  - auth and rate-limit errors in a second envelope shape (Go, Python, TS, Java);
  - a JWT decode `NameError` that turned every request into a 401 (Python);
  - cursors that broke page 2 for non-default sorts (Rust, Python);
  - a tenant filter enabled outside the transaction, so it filtered nothing (Java);
  - log masking that masked nothing (Java);
  - Postgres DDL that was a syntax error (Go, Rust);
  - APIs removed in Zod 4, Express 5, Prisma 7, axum 0.8, OpenTelemetry, Spring Boot 4, Hibernate 7 and Jackson 3.

  MSW 3 (released 2026-09-28) renamed `onUnhandledRequest` to `onUnhandledFrame` and silently ignores
  the old key. `msw.md` and the RN testing pack are updated.

**Decisions (confirmed by the owner, 2026-09-30):**
- **Changing an existing test.** A coder may change an *existing* test's expectation only when this
  phase's spec changed that behaviour. A coder may never delete, skip or loosen a test. Every change to
  a test that existed before the phase, by a coder or a test agent, carries its why and when in the test:
  one line directly above the change, `TEST-CHANGE <YYYY-MM-DD> phase <N>: <why> (spec: <ref> | moved: <where>)`.
  `tc-inventory.py --diff-base` enforces it. A changed or removed assertion needs a comment within 3 lines
  citing `spec:` or `moved:`. Any other edit to a pre-existing test needs one in the file. Only deleted
  test files and baseline images use `test-changes.json`. Valid comments form the `test_changes` ledger
  in `specs_vs_tests.json`. Rule: `test-case-traceability.md` §Changing an existing test. Tests:
  `evidence-tools` TT01–TT10, and `testing-agents` checks that each of the 10 coder and test agents documents it.
- **Mutation testing** stays advisory (reported by test_runner, not a gate floor).

## Method

- Six `general-purpose` reviewers, each with a hat-specific checklist, ran in parallel over the 22
  agents plus the orchestrator, gate, skills and k8s layer. Each finding carries a severity and a type:
  (a) wrong instruction, (b) missing, or (c) present but unenforced. Every one cites a file and line.
- Three verifiers split the 77 CRITICAL/HIGH findings two hats each. They tried to refute each finding,
  reproduced runtime claims in a scratch directory, and merged duplicates across hats.
- The repo was read-only throughout. The cluster was not touched.
- **Reports:** [architect](board-review-2026-09-30/architect.md) · [senior developer](board-review-2026-09-30/senior_dev.md) · [tester](board-review-2026-09-30/tester.md) · [SRE](board-review-2026-09-30/sre.md) · [DevOps](board-review-2026-09-30/devops.md) · [security](board-review-2026-09-30/security.md)
- **Verification:** [security + architect](board-review-2026-09-30/verify_sec_arch.md) · [tester + senior dev](board-review-2026-09-30/verify_tester_dev.md) · [SRE + DevOps](board-review-2026-09-30/verify_sre_ops.md)
