# Shared brief: landscape review of agent frameworks (2026-10-02)

## Goal
Find capabilities that the startup-agents SDLC framework is MISSING or does WORSE than the state of the
art, and that are worth adding. The owner builds real products with it (e.g. "rera": Python/FastAPI +
React + React Native, k3s, Postgres RLS) and is about to start a new phase. Output feeds a ranked plan.

## Honesty rules (the owner's, strict)
- Verify every claim about another product with current sources (WebSearch / WebFetch); it is
  2026-10-02 and this space changes monthly. Cite a URL + the date you checked for each claim.
- Say "unverified" when you can't confirm something. No marketing numbers presented as fact; if a
  vendor claims a benchmark, say it's a vendor claim.
- Before calling something a gap, check our repo: /Users/kishoremoli/development/startup-agents
  (read with `git -C <repo> show main:<path>` or `git grep <pattern> main` — the checkout has an old
  branch; `main` is current). Key docs: README.md, docs/FRAMEWORK_REVIEW_2026-09-30.md (§2 "How we
  compare", §3 landscape — DON'T repeat it; report only what is new or changed since, or outside its
  scope), docs/SDLC_GRAPH.md, docs/PHASE_LEDGER.md, docs/AUTONOMOUS_GUIDE.md, docs/DEPLOYMENT_GUIDE.md,
  docs/STITCH_DESIGN_GUIDE.md, docs/DECISIONS.md, .claude/commands/*.md, .claude/agents/core/*.md.
- Supply-chain rule: borrow techniques; never recommend installing another framework's hooks/installer.

## What we already have (summary — verify details in the repo)
- Pipeline: /init (BRD, guidelines, generated agents) → /map → /discuss → /plan (specs with EARS + TC-*
  IDs) → /design (Google Stitch two-way) → /develop (develop-orchestrator: waves 0–6, named agents per
  tier and per reviewer, roster gate, candidate selection N=2–3 in worktrees) → /accept; /autonomous with
  a Stop-hook inner loop + an external supervisor script (budgets, exit codes, restart).
- ~90 agents (core + generated templates), ~230 skill packs, every code sample compiled/run in CI-like
  harnesses; closed error-code set.
- Gates: verify-gate.sh (runner-written test evidence, roster complete, TC inventory via sdlc-graph,
  debate verdicts, Stitch fidelity), D-002 warning-first strict checks.
- Memory: Tier 0 facts (PROJECT_FACTS.md, bi-temporal), Tier 0.5 decisions ledger, lessons +
  procedural promotion, codebase KB from /map, sdlc-graph (SQLite artifact/traceability graph; pipeline
  agents get work lists from it; interactive FTS Q&A measured +32% tokens → off).
- Phase ledger step 1 (hooks record spawns/subagent start-stop/files/turns; observe only).
- Debate protocol (moderator/advocates/arbitrator), /board-review (multi-hat review + blind verifiers).
- Security: sdlc-guard PreToolUse permission guard + PATH shims, dependency vetting (typosquat/age),
  security_reviewer, tenant_isolation_verifier, threat_model_agent, SAST/secrets in code_quality_verifier.
- Deploy: local compose, k3s lab dev/qa with digest promotion, EKS staging/prod (offline-validated).
- Testing tiers: unit/integration/UI/e2e/mobile device/acceptance/performance(k6)/system; test_runner
  independent re-run; advisory mutation; TC-DATA per-element UI data checks.
- Measurement: /eval (outcome + trajectory), scripts/eval-question-tokens.py (real token A/B).
- Known open items (don't re-report as discoveries, but DO report how others solve them): hook-written
  completion (B7), RED-evidence gate, bounded fix ladder + rulings ledger, LSP/precise code graph for
  reviewers, per-wave orchestrator split, plugin packaging, delta specs, learnings applies_when/retire_when,
  fresh session per phase, mid-wave checks (PRM).

## Output (write to the file path in your task, then return a short summary)
1. A table: capability | who does it best (product, how, URL, date checked) | do we have it? (yes /
   partial / no, with our file path) | value for us (H/M/L) | effort (S/M/L) | risk/caveats.
2. The 3–5 strongest recommendations for us, each with a concrete "what we'd build" in 2–4 lines.
3. Things we should NOT copy and why (hype, unverified, poor trade-offs).
4. Unverified items list.
Keep the file under ~2,500 words. Quality over volume.
