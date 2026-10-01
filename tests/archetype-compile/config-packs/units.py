"""What checks each non-application code block in .claude/skills (read by harness.py).

EXPECTED pins how many blocks of each family every file has; BLOCKS pins each block's first non-empty
line (anchor) and says how it is checked, or why it is skipped. A change to either fails the run until
this file is looked at again. Keys are "<path under .claude/skills>#<family><n>".

Per-block keys (all optional except anchor and check|skip):
  check      sh | pg | mysql | sqlite | yaml | json | dockerfile | hcl | ngql
  skip       reason (the block is not checked at all — only for template placeholders)
  subst      [(old, new)] or [("re", pattern, repl)]: declared, line-count-preserving edits applied before
             checking (template placeholders such as <Go> or `N`); a substitution that matches nothing fails
  wrap       "...{}..." harness context around a fragment (+ indent); findings inside it say so
  sh:   sc_exclude {SCnnnn: reason}, exec [scenario], shell
  sql:  fixture (SQL_FIXTURES key), params (PREPARE statements with $n / ?), rollback_between
  yaml: gha, compose (+env), k8s, maestro (True | "commands"), openapi, golangci
  json: mode strict | jsonc (// comments, several values) | console (Elasticsearch Dev Tools),
        schema name(s) from SCHEMA_CHECKS, count
  dockerfile: context (DOCKER_CONTEXTS key), build_args, hadolint_ignore
  hcl:  fixture (HCL_FIXTURES key)
  ngql: fixture (NGQL_SETUP key), use, after_ddl_wait

An exec scenario runs the block in an empty directory after its `setup` script (fixtures only; the block
itself is never edited, except by the scenario's declared `subst`): `prepend` lists other blocks of the
same file whose definitions it needs, `post` runs in the same shell afterwards, `rc` is the expected exit
code (or "nonzero"), `expect`/`reject` are regexes over the output, `linux: False` keeps it macOS-only
(the Linux container has no python3/jq/git/go), `needs` lists tools the scenario requires.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
K8S_VERSION = "1.37.1"   # kubeconform schema version: the newest in its default schema repo on 2026-09-30 (1.38 absent)
NEBULA_VERSION = "v3.8.0"
_ctx = None


def bind(ctx):
    global _ctx
    _ctx = ctx


# ───────────────────────────────────────────────────────────────────────────── inventory ──
EXPECTED = {
    "api/response-envelope.md": {"json": 3},
    "core/api-excellence.md": {"json": 1, "yaml": 1},
    "core/candidate-selection.md": {"sh": 3},
    "core/change-impact-analysis.md": {"json": 1, "sh": 4},
    "core/code-quality.md": {"sh": 1},
    "core/commands-and-versions.md": {"sh": 1},
    "core/debate-protocol.md": {"json": 1},
    "core/develop-steps/step-0-5-implementation-readiness-gate.md": {"sh": 1},
    "core/develop-steps/step-0-orient.md": {"json": 3, "sh": 12},
    "core/develop-steps/step-2-5-api-contract-validation.md": {"sh": 1},
    "core/develop-steps/step-2-implementation.md": {"sh": 6},
    "core/develop-steps/step-3-tests.md": {"json": 2},
    "core/develop-steps/step-3d-3e-reconciliation.md": {"sh": 1},
    "core/develop-steps/step-3f-code-optimization.md": {"sh": 3},
    "core/develop-steps/step-3g-post-optimization-test-re-run.md": {"sh": 1},
    "core/develop-steps/step-6-phase-gate.md": {"json": 2, "sh": 6},
    "core/develop-steps/step-7-report.md": {"sh": 1},
    "core/develop-steps/step-7b-phase-post-mortem.md": {"json": 1, "sh": 5},
    "core/dual-ledger-replan.md": {"json": 1},
    "core/edit-validation.md": {"sh": 3},
    "core/eval-harness.md": {"json": 4},
    "core/gate-verification.md": {"sh": 1},
    "core/implementation-guidelines-template.md": {"json": 3, "sql": 1, "yaml": 1},
    "core/memory-as-tools.md": {"sh": 3},
    "core/model-routing.md": {"json": 1},
    "core/product-workflow-research.md": {"yaml": 2},
    "core/resiliency-patterns.md": {"yaml": 2},
    "core/scale-adaptive-depth.md": {"json": 1},
    "core/shared-backend-patterns.md": {"json": 1, "sql": 1},
    "core/verification-protocol.md": {"sh": 4},
    "databases/dynamodb.md": {"sh": 1},
    "databases/elasticsearch.md": {"json": 9},
    "databases/firestore.md": {"sh": 1},
    "databases/mysql.md": {"sql": 4},
    "databases/nebula.md": {"ngql": 5},
    "databases/postgres.md": {"sql": 7},
    "databases/query-optimization.md": {"sql": 12},
    "databases/sqlite.md": {"sql": 3},
    "frameworks/quarkus.md": {"sh": 1},
    "frameworks/react.md": {"json": 1},
    "frameworks/spring-boot.md": {"json": 1, "yaml": 1},
    "infrastructure/docker.md": {"dockerfile": 2, "yaml": 1},
    "infrastructure/github-actions.md": {"yaml": 4},
    "infrastructure/kubernetes.md": {"yaml": 3},
    "infrastructure/localstack-aws-local.md": {"sh": 10, "yaml": 4},
    "infrastructure/saas-tenancy-models.md": {"sql": 2, "yaml": 1},
    "infrastructure/secrets-management.md": {"hcl": 1, "sh": 1, "yaml": 1},
    "infrastructure/terraform.md": {"hcl": 2, "sh": 1},
    "languages/go.md": {"yaml": 1},
    "languages/java.md": {"yaml": 1},
    "languages/rust.md": {"sh": 2, "sql": 1},
    "languages/typescript.md": {"json": 1},
    "testing/appium-mobile.md": {"sh": 1},
    "testing/contract-testing.md": {"sh": 1, "yaml": 1},
    "testing/detox.md": {"sh": 1},
    "testing/external-service-mocks.md": {"json": 5},
    "testing/gomock.md": {"sh": 1},
    "testing/junit-mockito.md": {"sh": 1},
    "testing/load-testing.md": {"sh": 3, "yaml": 2},
    "testing/maestro.md": {"sh": 1, "yaml": 3},
    "testing/msw.md": {"sh": 2},
    "testing/mutation-testing.md": {"json": 1, "sh": 1},
    "testing/playwright.md": {"sh": 1},
    "testing/targeted-testing.md": {"sh": 2},
    "testing/test-case-traceability.md": {"sh": 1},
    "testing/test-results-sidecar.md": {"json": 1, "sh": 2},
    "testing/testcontainers.md": {"sh": 1},
    "testing/vitest.md": {"sh": 1},
    "ui/accessibility-patterns.md": {"json": 1},
    "ui/shadcn.md": {"sh": 1},
    "ui/stitch-design.md": {"json": 1},
    "ui/structured-wireframe-format.md": {"yaml": 6},
}

# shared shellcheck exclusions (each block opts in by name; the reason travels with it)
FRAGMENT_VARS = {"SC2034": "fragment: the variable is read by the next step/block, not inside this one",
                 "SC2154": "fragment: the variable (PHASE, FILE, …) is set by the step that runs it"}
GIT_REPO = ("git init -q . && git config user.email h@example.invalid && git config user.name harness && "
            "git commit -q --allow-empty -m base")
JSON_TMP_EDIT = [("# produce the edited content into $TMP (do NOT touch $FILE yet)", 'cp "$EDITED" "$TMP"')]

BLOCKS = {
    # ── api/response-envelope.md: the canonical envelope every other example is checked against
    "api/response-envelope.md#json1": dict(anchor='{', check="json", schema="envelope"),
    "api/response-envelope.md#json2": dict(anchor='{', check="json", schema="envelope"),
    "api/response-envelope.md#json3": dict(anchor='{', check="json", schema="envelope"),
    # ── core/api-excellence.md
    "core/api-excellence.md#yaml1": dict(anchor='# openapi.yaml — single source of truth', check="yaml", openapi=True),
    "core/api-excellence.md#json1": dict(anchor='{', check="json", schema="envelope"),
    # ── core/candidate-selection.md
    "core/candidate-selection.md#sh1": dict(
        anchor='# From the repo root. BASE is the current HEAD the phase builds on.', check="sh",
        sc_exclude={"SC2154": FRAGMENT_VARS["SC2154"]},
        exec=[dict(name="creates N worktrees", linux=False, needs=["git"], env={"PHASE": "2", "N": "2"},
                   setup=GIT_REPO, post="git worktree list | grep -c candidates/c", expect=[r"^2$"]),
              dict(name="stops when a worktree cannot be made", linux=False, needs=["git"], env={"PHASE": "2", "N": "2"},
                   setup=GIT_REPO + " && git branch cand/phase-2/c2", rc="nonzero", expect=[r"worktree for candidate c2 failed"])]),
    "core/candidate-selection.md#sh2": dict(
        anchor='WINNER="c${WIN}"                       # e.g. c2', check="sh", sc_exclude={"SC2154": FRAGMENT_VARS["SC2154"]},
        exec=[dict(name="failed merge stops before deleting branches", linux=False, needs=["git"],
                   env={"PHASE": "2", "N": "2", "WIN": "1"}, setup=GIT_REPO, rc="nonzero",
                   expect=[r"merge of cand/phase-2/c1 failed"])]),
    "core/candidate-selection.md#sh3": dict(anchor='echo "{\\"ts\\":\\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\\",\\"event\\":\\"candidate_selection\\",\\"phase\\":${PHASE},\\', check="sh",
                                            sc_exclude={"SC2154": FRAGMENT_VARS["SC2154"]}),
    # ── core/change-impact-analysis.md
    "core/change-impact-analysis.md#sh1": dict(
        anchor='# Files changed in this phase: since the commit it started from (base_sha, written at Wave 0c).', check="sh",
        exec=[dict(name="no base_sha means full regression, not a guess", linux=False, env={"PHASE": "3"},
                   rc="nonzero", expect=[r"run the FULL regression"])]),
    "core/change-impact-analysis.md#sh2": dict(anchor='# Extract unique packages/directories from changed files (one per line; "." for root files)', check="sh",
                                               sc_exclude={"SC2034": FRAGMENT_VARS["SC2034"]}),
    "core/change-impact-analysis.md#sh3": dict(anchor='# For Go projects: a package is affected when it changed or imports a changed package (test imports', check="sh",
                                               sc_exclude={"SC2034": FRAGMENT_VARS["SC2034"]}),
    "core/change-impact-analysis.md#sh4": dict(
        anchor='SELECTION_THRESHOLD=80  # If > 80% affected, just run all (no savings)', check="sh",
        sc_exclude={"SC2154": FRAGMENT_VARS["SC2154"]},
        exec=[dict(name="Steps 1-5 on a Go module: the changed package and its importer, not the others",
                   prepend=["core/change-impact-analysis.md#sh1", "core/change-impact-analysis.md#sh2",
                            "core/change-impact-analysis.md#sh3"],
                   linux=False, needs=["git", "go"], env={"PHASE": "3", "FULL_TEST_CMD": "go test ./..."},
                   setup=GIT_REPO + " && mkdir -p agent_state/phases/3 a b c d e && "
                         "printf 'module example.com/m\\n\\ngo 1.21\\n' > go.mod && "
                         "printf 'package a\\n\\nfunc A() int { return 1 }\\n' > a/a.go && "
                         "printf 'package b\\n\\nimport \"example.com/m/a\"\\n\\nfunc B() int { return a.A() }\\n' > b/b.go && "
                         "for p in c d e; do printf 'package %s\\n\\nfunc X() int { return 3 }\\n' $p > $p/x.go; done && "
                         "git add -A && git commit -qm v1 && git rev-parse HEAD > agent_state/phases/3/base_sha && "
                         "printf 'package a\\n\\nfunc A() int { return 2 }\\n' > a/a.go && git commit -qam v2",
                   expect=[r"regression: go test (example\.com/m/a example\.com/m/b|example\.com/m/b example\.com/m/a) ?$"],
                   reject=[r"example\.com/m/c", r"\./\.\.\."])]),
    "core/change-impact-analysis.md#json1": dict(anchor='{', check="json"),
    # ── core/code-quality.md
    "core/code-quality.md#sh1": dict(anchor='# Good rhythm', check="sh"),
    # ── core/commands-and-versions.md
    "core/commands-and-versions.md#sh1": dict(anchor='python3 .claude/hooks/commands-table.py docs/IMPLEMENTATION_GUIDELINES.md --out agent_state/config/verify-commands.json', check="sh"),
    # ── core/debate-protocol.md
    "core/debate-protocol.md#json1": dict(anchor='{', check="json"),
    # ── core/dual-ledger-replan.md
    "core/dual-ledger-replan.md#json1": dict(anchor='{', check="json"),
    # ── core/edit-validation.md
    "core/edit-validation.md#sh1": dict(
        anchor='# Occurrences of the whole (multi-line) block: 0, 1, or 2 meaning "more than one". Not grep -c: it',
        check="sh", sc_exclude=FRAGMENT_VARS,
        exec=[dict(name="multi-line block absent although its first line is present: 0", linux=False,
                   setup="printf 'a()\\nb()\\na()\\n' > f.txt", env={"FILE": "f.txt", "SEARCH_BLOCK": "a()\nc()"},
                   post='echo "COUNT=$COUNT"', same_shell=True, expect=[r"COUNT=0"]),
              dict(name="block present once: 1", linux=False, setup="printf 'a()\\nb()\\na()\\n' > f.txt",
                   env={"FILE": "f.txt", "SEARCH_BLOCK": "a()\nb()"}, post='echo "COUNT=$COUNT"', same_shell=True, expect=[r"COUNT=1"]),
              dict(name="block present twice: >1", linux=False, setup="printf 'a()\\nb()\\na()\\n' > f.txt",
                   env={"FILE": "f.txt", "SEARCH_BLOCK": "a()"}, post='echo "COUNT=$COUNT"', same_shell=True, expect=[r"COUNT=2"])]),
    "core/edit-validation.md#sh2": dict(
        anchor='# Same file name in a scratch dir: the checkers pick the parser from the extension (a bare mktemp file',
        check="sh", sc_exclude=FRAGMENT_VARS,
        exec=[dict(name="broken JSON edit is rejected", linux=False, needs=["jq"], subst=JSON_TMP_EDIT,
                   setup="echo '{}' > c.json && echo '{\"a\": }' > edited.json",
                   env={"FILE": "c.json", "EDITED": "edited.json"}, rc="nonzero"),
              dict(name="valid JSON edit passes", linux=False, needs=["jq"], subst=JSON_TMP_EDIT,
                   setup="echo '{}' > c.json && echo '{\"a\": 1}' > edited.json",
                   env={"FILE": "c.json", "EDITED": "edited.json"}, rc=0),
              dict(name="broken Python edit is rejected", linux=False, subst=JSON_TMP_EDIT,
                   setup="echo 'x = 1' > m.py && echo 'def (:' > edited.py",
                   env={"FILE": "m.py", "EDITED": "edited.py"}, rc="nonzero")]),
    "core/edit-validation.md#sh3": dict(anchor='ORIG_LINES=$(wc -l < "$FILE")', check="sh", sc_exclude=FRAGMENT_VARS),
    # ── core/eval-harness.md: same shape as the real suite files in agent_state/eval/
    "core/eval-harness.md#json1": dict(anchor='{', check="json", schema="eval_rubric"),
    "core/eval-harness.md#json2": dict(anchor='{', check="json", schema="eval_trajectory"),
    "core/eval-harness.md#json3": dict(anchor='{', check="json", schema="eval_baseline"),
    "core/eval-harness.md#json4": dict(anchor='{', check="json", schema="eval_artifacts"),
    # ── core/gate-verification.md
    "core/gate-verification.md#sh1": dict(
        anchor="# Tests actually run — the project's own command, exit code kept (a bare `| tee` would report tee's 0).",
        check="sh",
        exec=[dict(name="no test:unit row stops instead of running nothing", linux=False, needs=["jq"],
                   env={"PHASE": "2"}, setup="mkdir -p agent_state/config && echo '{\"commands\":{}}' > agent_state/config/verify-commands.json",
                   rc="nonzero", expect=[r"no test:unit row"], reject=[r"exit=0"])]),
    # ── core/implementation-guidelines-template.md (blocks nested in the ````markdown templates)
    "core/implementation-guidelines-template.md#json1": dict(anchor='{', check="json", schema="envelope", subst=[("{ ... }", "{}")]),
    "core/implementation-guidelines-template.md#json2": dict(anchor='{', check="json", schema="envelope",
                                                             subst=[("[ ... ]", "[]"), ("{{DEFAULT_PAGE_SIZE}}", "20")]),
    "core/implementation-guidelines-template.md#json3": dict(anchor='{', check="json", schema="envelope"),
    "core/implementation-guidelines-template.md#yaml1": dict(anchor='{{DOCKER_COMPOSE_EXAMPLE}}',
                                                             skip="template placeholder only: impl_guidelines_agent writes the project's compose file here"),
    "core/implementation-guidelines-template.md#sql1": dict(anchor='{{RLS_POLICY_EXAMPLE}}',
                                                            skip="template placeholder only: impl_guidelines_agent writes the project's RLS policy here"),
    # ── core/memory-as-tools.md
    "core/memory-as-tools.md#sh1": dict(
        anchor='# Lesson/pattern sources that exist: root indices + per-phase lesson files (fallback), one per line.', check="sh",
        exec=[dict(name="no sources: returns 1 at once (grep would read stdin)", linux=False, post="memory_search auth </dev/null; echo rc=$?", same_shell=True,
                   expect=[r"rc=1"])]),
    "core/memory-as-tools.md#sh2": dict(
        anchor='memory_get() {', check="sh",
        exec=[dict(name="per-phase lessons found with no root lessons.md", prepend=["core/memory-as-tools.md#sh1"],
                   setup="mkdir -p agent_state/phases/2 && printf '### L-2-001 cache keys\\nbody one\\n### L-2-002 other\\nbody two\\n' > agent_state/phases/2/lessons.md",
                   post="memory_get L-2-001", same_shell=True, expect=[r"### L-2-001 cache keys\nbody one"], reject=[r"L-2-002"])]),
    "core/memory-as-tools.md#sh3": dict(
        anchor="# Derive tags from the task's target files, then retrieve matching lessons only.", check="sh",
        exec=[dict(name="prime by tag", prepend=["core/memory-as-tools.md#sh1", "core/memory-as-tools.md#sh2"],
                   setup="mkdir -p agent_state && printf -- '- auth: L-1-001\\n\\n### L-1-001 token reuse\\n- **Tags:** auth\\nrotate\\n### L-1-002 x\\n' > agent_state/lessons.md",
                   post="memory_prime auth", same_shell=True, expect=[r"### L-1-001 token reuse"], reject=[r"L-1-002 x"])]),
    # ── core/model-routing.md: one execution.jsonl line
    "core/model-routing.md#json1": dict(anchor='{"ts":"<ISO>","event":"model_escalation","agent":"backend_developer","from":"opus","to":"fable","reason":"integration tests failed after first attempt"}', check="json"),
    # ── core/product-workflow-research.md (templates: "a | b" lists the allowed values)
    "core/product-workflow-research.md#yaml1": dict(anchor='screen:', check="yaml"),
    "core/product-workflow-research.md#yaml2": dict(anchor='entity:', check="yaml"),
    # ── core/resiliency-patterns.md (container-level fragments, validated inside a Deployment)
    "core/resiliency-patterns.md#yaml1": dict(
        anchor='readinessProbe: { httpGet: { path: /readyz, port: http }, periodSeconds: 5,  timeoutSeconds: 2, failureThreshold: 3 }',
        check="yaml", k8s=True, indent=10,
        wrap="apiVersion: apps/v1\nkind: Deployment\nmetadata: { name: api }\nspec:\n  selector: { matchLabels: { app: api } }\n"
             "  template:\n    metadata: { labels: { app: api } }\n    spec:\n      containers:\n        - name: api\n"
             "          image: registry.example/api@sha256:0000000000000000000000000000000000000000000000000000000000000000\n"
             "          ports: [{ name: http, containerPort: 8080 }]\n{}\n"),
    "core/resiliency-patterns.md#yaml2": dict(
        anchor='# deployment: the grace period covers preStop + drain + flush + margin', check="yaml", k8s=True, indent=4,
        wrap="apiVersion: apps/v1\nkind: Deployment\nmetadata: { name: api }\nspec:\n  selector: { matchLabels: { app: api } }\n"
             "  template:\n    metadata: { labels: { app: api } }\n{}\n"),
    # ── core/scale-adaptive-depth.md
    "core/scale-adaptive-depth.md#json1": dict(anchor='{', check="json"),
    # ── core/shared-backend-patterns.md
    "core/shared-backend-patterns.md#sql1": dict(anchor='-- RLS policy as a safety net (PostgreSQL example)', check="pg", fixture="orders_tenant"),
    "core/shared-backend-patterns.md#json1": dict(
        anchor='// Canonical definition: ~/.claude/skills/api/response-envelope.md (it wins over this summary)',
        check="json", mode="jsonc", count=3, schema="envelope", subst=[("{ ... }", "{}"), ("[ ... ]", "[]")]),
    # ── core/verification-protocol.md
    "core/verification-protocol.md#sh1": dict(
        anchor='# Extract all requirement IDs from spec — the IDs only (they also sit in tables, not just at line', check="sh",
        exec=[dict(name="IDs in tables; FR-1 is not covered by FR-10", setup="mkdir -p docs src && "
                   "printf '| FR-1 | login |\\n| FR-10 | logout |\\n| NFR-PERF-01 | p95 |\\n' > docs/BRD.md && "
                   "printf '// FR-10 logout\\n// NFR-PERF-01\\n' > src/x.go",
                   expect=[r"MISSING: FR-1 has no implementation reference"], reject=[r"MISSING: FR-10", r"MISSING: NFR-PERF-01"])]),
    "core/verification-protocol.md#sh2": dict(
        anchor='# Paths the OpenAPI spec defines (the keys under paths:), one per line', check="sh",
        exec=[dict(name="spec and code paths compared in one shape", setup="mkdir -p src && "
                   "printf 'paths:\\n  /api/v1/users:\\n    get: {}\\n  /api/v1/users/{id}:\\n    get: {}\\n  /api/v1/orders:\\n    get: {}\\n' > openapi.yaml && "
                   "printf 'r.GET(\"/api/v1/users\", h)\\nr.GET(\"/api/v1/users/:id\", h)\\nr.GET(\"/api/v1/debug\", h)\\n' > src/routes.go",
                   expect=[r"^/api/v1/orders$", r"^\t/api/v1/debug$"], reject=[r"users"])]),
    "core/verification-protocol.md#sh3": dict(anchor='# Scan for leftover markers', check="sh"),
    "core/verification-protocol.md#sh4": dict(anchor='# Automated existence check example', check="sh"),
    # ── core/develop-steps/step-0-5-implementation-readiness-gate.md (HARD GATE)
    "core/develop-steps/step-0-5-implementation-readiness-gate.md#sh1": dict(
        anchor='# Check 1: Specs exist for this phase', check="sh",
        exec=[dict(name="no specs: blocked", env={"PHASE": "2"}, rc="nonzero", expect=[r"BLOCKED: No specs"]),
              dict(name="ready phase passes", env={"PHASE": "2"}, setup=(
                  "d=docs/design/phases/2; mkdir -p $d/specs agent_state/reconciliation/phase-2 && touch $d/specs/a.md $d/specs/data-contracts.md "
                  "$d/VERIFICATION_REPORT.md && seq 1 25 > $d/phase_context.md && "
                  "printf '| Metric | Value |\\n|---|---|\\n| Blocking issues | 0 |\\n' > agent_state/reconciliation/phase-2/brd_vs_specs.md"), rc=0),
              dict(name="reconciliation with blocking issues: blocked", env={"PHASE": "2"}, setup=(
                  "d=docs/design/phases/2; mkdir -p $d/specs agent_state/reconciliation/phase-2 && touch $d/specs/a.md "
                  "$d/VERIFICATION_REPORT.md && seq 1 25 > $d/phase_context.md && "
                  "printf '| Blocking issues | 2 |\\n' > agent_state/reconciliation/phase-2/brd_vs_specs.md"), rc="nonzero",
                   expect=[r"reports 2 blocking issue"]),
              dict(name="no reconciliation report: blocked", env={"PHASE": "2"}, setup=(
                  "d=docs/design/phases/2; mkdir -p $d/specs && touch $d/specs/a.md $d/VERIFICATION_REPORT.md && seq 1 25 > $d/phase_context.md"),
                   rc="nonzero", expect=[r"no BRD↔Spec reconciliation"])]),
    # ── core/develop-steps/step-0-orient.md
    "core/develop-steps/step-0-orient.md#sh1": dict(
        anchor='# Highest N with agent_state/phases/N/gate.passed. No grep -P: macOS grep rejects it (exit 2), which', check="sh",
        sc_exclude={"SC2154": "ARG_PHASE is the /develop --phase argument"},
        exec=[dict(name="next phase after the highest gate.passed", setup="for p in 1 2 10; do mkdir -p agent_state/phases/$p; touch agent_state/phases/$p/gate.passed; done; mkdir -p agent_state/phases/11",
                   expect=[r"Running Phase 11$"]),
              dict(name="fresh project starts at 1", expect=[r"Running Phase 1$"]),
              dict(name="--phase wins", env={"ARG_PHASE": "5"}, setup="mkdir -p agent_state/phases/2 && touch agent_state/phases/2/gate.passed",
                   expect=[r"Running Phase 5$"])]),
    "core/develop-steps/step-0-orient.md#sh2": dict(
        anchor='mkdir -p "agent_state/phases/${PHASE:?}"', check="sh", sc_exclude={"SC2154": FRAGMENT_VARS["SC2154"]},
        exec=[dict(name="one valid JSON line", linux=False, env={"PHASE": "3"},
                   post="python3 -c \"import json;[json.loads(l) for l in open('agent_state/phases/3/execution.jsonl')];print('JSONL-OK')\"",
                   expect=[r"JSONL-OK"])]),
    "core/develop-steps/step-0-orient.md#sh3": dict(
        anchor='# Check for previous gate.failed files', check="sh",
        exec=[dict(name="lists blockers of a previous failure", linux=False, env={"PHASE": "3"},
                   setup="mkdir -p agent_state/phases/3 && echo '{\"blockers\":[{\"gate_item\":\"unit_tests\"}]}' > agent_state/phases/3/gate.failed",
                   expect=[r"gate.failed: blocked by unit_tests"])]),
    "core/develop-steps/step-0-orient.md#sh4": dict(
        anchor='LOCK_FILE="agent_state/phases/${PHASE:?}/.lock"', check="sh",
        exec=[dict(name="free: takes the lock", env={"PHASE": "3"}, setup="mkdir -p agent_state/phases/3",
                   post="wc -l < agent_state/phases/3/.lock", expect=[r"^\s*2$"], reject=[r"locked by"]),
              dict(name="held: warns and never overwrites the holder", env={"PHASE": "3"},
                   setup="mkdir -p agent_state/phases/3 && printf 'other@host\\n2026-09-29T10:00:00Z\\n' > agent_state/phases/3/.lock",
                   post="head -1 agent_state/phases/3/.lock", expect=[r"locked by other@host since 2026-09-29T10:00:00Z", r"^other@host$"])]),
    "core/develop-steps/step-0-orient.md#sh5": dict(anchor='rm -f "agent_state/phases/${PHASE}/.lock"', check="sh",
                                                    sc_exclude={"SC2154": FRAGMENT_VARS["SC2154"]}),
    "core/develop-steps/step-0-orient.md#sh6": dict(
        anchor='# Quick staleness check — BLOCKING (step 3 above): a stale contract stops the phase', check="sh",
        exec=[dict(name="stale contract blocks", linux=False, env={"PHASE": "3"}, setup=(
                       "mkdir -p agent_state/phases/2 docs/design/phases/3/specs && "
                       "echo '{\"artifacts\":{\"api_routes\":[\"GET /api/v1/users\",\"POST /api/v1/old\"]}}' > agent_state/phases/2/manifest.json && "
                       "echo 'GET /api/v1/users' > docs/design/phases/3/specs/data-contracts.md"),
                   rc="nonzero", expect=[r"STALE CONTRACTS", r"POST /api/v1/old", r"BLOCKED"]),
              dict(name="consistent contract passes", linux=False, env={"PHASE": "3"}, setup=(
                       "mkdir -p agent_state/phases/2 docs/design/phases/3/specs && "
                       "echo '{\"artifacts\":{\"api_routes\":[\"GET /api/v1/users\"]}}' > agent_state/phases/2/manifest.json && "
                       "echo 'GET /api/v1/users' > docs/design/phases/3/specs/data-contracts.md"),
                   rc=0, expect=[r"Data contracts consistent with Phase 2 manifest"])]),
    "core/develop-steps/step-0-orient.md#sh7": dict(
        anchor='# Schema evolution validation — writes reports/schema_evolution.md (read by Breaking Change', check="sh",
        exec=[dict(name="removed field blocks and lands in the report", linux=False, env={"PHASE": "2"}, setup=(
                       "mkdir -p docs/design/phases/1/specs docs/design/phases/2/specs && "
                       "printf 'interface User {\\n  id: string;\\n  role: string;\\n}\\n' > docs/design/phases/1/specs/data-contracts.md && "
                       "printf 'interface User {\\n  id: string;\\n}\\n' > docs/design/phases/2/specs/data-contracts.md"),
                   post="grep -c 'BREAKING: User.role REMOVED' agent_state/phases/2/reports/schema_evolution.md",
                   rc="nonzero", expect=[r"BLOCKED: breaking schema change", r"^1$"]),  # post: the report Step 6 reads
              dict(name="additive change passes", linux=False, env={"PHASE": "2"}, setup=(
                       "mkdir -p docs/design/phases/1/specs docs/design/phases/2/specs && "
                       "printf 'interface User {\\n  id: string;\\n}\\n' > docs/design/phases/1/specs/data-contracts.md && "
                       "printf 'interface User {\\n  id: string;\\n  email?: string;\\n}\\n' > docs/design/phases/2/specs/data-contracts.md"),
                   rc=0, expect=[r"Schema evolution clean"])]),
    "core/develop-steps/step-0-orient.md#sh8": dict(
        anchor='# Breaking change propagation — check all consuming phases', check="sh",
        exec=[dict(name="report without BREAKING: quiet, no integer error", env={"PHASE": "2"},
                   setup="mkdir -p agent_state/phases/2/reports && echo '✅ clean' > agent_state/phases/2/reports/schema_evolution.md",
                   rc=0, reject=[r"integer expression", r"breaking change\(s\) detected"])]),
    "core/develop-steps/step-0-orient.md#sh9": dict(
        anchor='CONTEXT_FILE="docs/design/phases/${PHASE}/phase_context.md"', check="sh",
        sc_exclude={"SC2154": FRAGMENT_VARS["SC2154"]},
        exec=[dict(name="BRD newer than phase_context warns (BSD and GNU stat)", env={"PHASE": "2"},
                   setup="mkdir -p docs/design/phases/2 && touch -t 202601010000 docs/design/phases/2/phase_context.md && touch -t 202602010000 docs/BRD.md",
                   expect=[r"BRD was modified AFTER"], reject=[r"integer expression", r"File:"])]),
    "core/develop-steps/step-0-orient.md#sh10": dict(
        anchor='SPEC_DIR="docs/design/phases/${PHASE}/specs"', check="sh", sc_exclude={"SC2154": FRAGMENT_VARS["SC2154"]},
        exec=[dict(name="old spec reported (BSD and GNU stat)", env={"PHASE": "2"},
                   setup="mkdir -p docs/design/phases/2/specs && touch -t 202001010000 docs/design/phases/2/specs/auth.md",
                   expect=[r"spec auth\.md is [0-9]+ days old"], reject=[r"integer expression"])]),
    "core/develop-steps/step-0-orient.md#sh11": dict(anchor='# Bring up local dev stack from IMPLEMENTATION_GUIDELINES Section 5', check="sh"),
    "core/develop-steps/step-0-orient.md#sh12": dict(anchor='echo "{\\"ts\\":\\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\\",\\"event\\":\\"estimate\\",\\"phase\\":${PHASE},\\"estimated_tokens\\":${TOTAL_TOKENS},\\"components\\":${NUM_COMPONENTS},\\"has_ui\\":${HAS_UI}}" >> "agent_state/phases/${PHASE}/execution.jsonl"',
                                                     check="sh", sc_exclude={"SC2154": FRAGMENT_VARS["SC2154"]}),
    "core/develop-steps/step-0-orient.md#json1": dict(anchor='{ "type": "escalation", "impact": "LOW", "recommendation": "A", "continueWithDefault": true }', check="json"),
    "core/develop-steps/step-0-orient.md#json2": dict(anchor='{', check="json"),
    "core/develop-steps/step-0-orient.md#json3": dict(anchor='// agent_state/debates/unresolved.json', check="json", mode="jsonc",
                                                      subst=[('"phase": N,', '"phase": 1,')]),
    # ── core/develop-steps/step-2-5-api-contract-validation.md
    "core/develop-steps/step-2-5-api-contract-validation.md#sh1": dict(anchor='CONTRACT_FILE="docs/design/phases/${PHASE}/specs/api-contracts.md"', check="sh",
                                                                       sc_exclude=FRAGMENT_VARS),
    # ── core/develop-steps/step-2-implementation.md
    "core/develop-steps/step-2-implementation.md#sh1": dict(
        anchor='V=agent_state/config/verify-commands.json', check="sh",
        exec=[dict(name="no typecheck/build row blocks", linux=False, needs=["jq"], env={"PHASE": "2"},
                   setup="mkdir -p agent_state/config && echo '{\"commands\":{}}' > agent_state/config/verify-commands.json",
                   rc="nonzero", expect=[r"BLOCKED: no typecheck/build row"]),
              dict(name="failing typecheck fails", linux=False, needs=["jq"], env={"PHASE": "2"},
                   setup="mkdir -p agent_state/config && echo '{\"commands\":{\"typecheck\":\"false | true\"}}' > agent_state/config/verify-commands.json",
                   rc="nonzero"),
              dict(name="passing typecheck passes", linux=False, needs=["jq"], env={"PHASE": "2"},
                   setup="mkdir -p agent_state/config && echo '{\"commands\":{\"build\":\"true\"}}' > agent_state/config/verify-commands.json",
                   rc=0)]),
    "core/develop-steps/step-2-implementation.md#sh2": dict(anchor='echo "{\\"ts\\":\\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\\",\\"event\\":\\"compile_check\\",\\"step\\":\\"B2a-check\\",\\"status\\":\\"passed|failed\\",\\"language\\":\\"<lang>\\",\\"attempt\\":${ATTEMPT:-1}}" >> "agent_state/phases/${PHASE}/execution.jsonl"',
                                                            check="sh", sc_exclude={"SC2154": FRAGMENT_VARS["SC2154"]}),
    "core/develop-steps/step-2-implementation.md#sh3": dict(
        anchor='# Atomic agent handoff — prevents downstream agents from reading partial manifests', check="sh",
        sc_exclude={"SC2015": "intended: the block runs when ANY step of the &&-chain fails (validate, mv, touch)"},
        exec=[dict(name="valid manifest: moved and VERIFIED", linux=False, env={"PHASE": "2"},
                   setup="mkdir -p agent_state/phases/2/backend_developer && echo '{}' > agent_state/phases/2/backend_developer/manifest.json.tmp",
                   post="ls agent_state/phases/2/.backend_developer_VERIFIED agent_state/phases/2/backend_developer/manifest.json",
                   rc=0, expect=[r"_VERIFIED"]),
              dict(name="corrupt manifest: blocked, nothing VERIFIED", linux=False, env={"PHASE": "2"},
                   setup="mkdir -p agent_state/phases/2/backend_developer && echo '{' > agent_state/phases/2/backend_developer/manifest.json.tmp",
                   rc="nonzero", expect=[r"manifest invalid"])]),
    "core/develop-steps/step-2-implementation.md#sh4": dict(anchor='echo "{\\"ts\\":\\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\\",\\"event\\":\\"compile_check\\",\\"step\\":\\"B2b-check\\",\\"status\\":\\"passed|failed\\",\\"language\\":\\"<lang>\\",\\"attempt\\":${ATTEMPT:-1}}" >> "agent_state/phases/${PHASE}/execution.jsonl"',
                                                            check="sh", sc_exclude={"SC2154": FRAGMENT_VARS["SC2154"]}),
    "core/develop-steps/step-2-implementation.md#sh5": dict(anchor='# Detect frontend framework and run build check',
                                                            skip="pseudo-step: comments only (the command comes from the build row of verify-commands.json)"),
    "core/develop-steps/step-2-implementation.md#sh6": dict(anchor='echo "{\\"ts\\":\\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\\",\\"event\\":\\"frontend_build_check\\",\\"step\\":\\"B3-check\\",\\"status\\":\\"passed|failed\\",\\"framework\\":\\"<framework>\\",\\"attempt\\":${ATTEMPT:-1}}" >> "agent_state/phases/${PHASE}/execution.jsonl"',
                                                            check="sh", sc_exclude={"SC2154": FRAGMENT_VARS["SC2154"]}),
    # ── core/develop-steps/step-3-tests.md
    "core/develop-steps/step-3-tests.md#json1": dict(anchor='// In manifest.json test_results section:', check="json", mode="jsonc",
                                                     wrap="{\n{}\n}", schema="manifest_test_results"),
    "core/develop-steps/step-3-tests.md#json2": dict(anchor='"cross_phase_regression": {', check="json", wrap="{\n{}\n}"),
    # ── core/develop-steps/step-3d-3e-reconciliation.md
    "core/develop-steps/step-3d-3e-reconciliation.md#sh1": dict(
        anchor='# Deterministic TC inventory — names of tests that ran and passed, not grep (board review TEST-02):', check="sh",
        exec=[dict(name="no base_sha: blocked before tc-inventory runs without the weakening check", env={"PHASE": "3"},
                   rc="nonzero", expect=[r"BLOCKED: no agent_state/phases/3/base_sha"])]),
    # ── core/develop-steps/step-3f-code-optimization.md
    "core/develop-steps/step-3f-code-optimization.md#sh1": dict(
        anchor='# Scope = only files changed in this phase: since its base_sha (or /optimize --since). A gate.passed', check="sh",
        sc_exclude={"SC2154": "OPTIMIZE_BASE is /optimize --since"},
        exec=[dict(name="no base: blocked", env={"PHASE": "3"}, rc="nonzero", expect=[r"BLOCKED: no base commit"]),
              dict(name="scope = files changed since base_sha", linux=False, needs=["git"], env={"PHASE": "3"},
                   setup=GIT_REPO + " && mkdir -p agent_state/phases/3 && echo a > old.go && git add -A && git commit -qm old && "
                         "git rev-parse HEAD > agent_state/phases/3/base_sha && echo b > new.go && git add new.go && git commit -qm new",
                   rc=0, expect=[r"^new\.go$"], reject=[r"old\.go"])]),
    "core/develop-steps/step-3f-code-optimization.md#sh2": dict(anchor='# Record the pre-optimization commit (no tags, no resets)', check="sh",
                                                                sc_exclude={"SC2034": FRAGMENT_VARS["SC2034"]}),
    "core/develop-steps/step-3f-code-optimization.md#sh3": dict(anchor='git revert --no-edit "${PRE_SHA}..HEAD"   # undo the optimization commits without discarding anyone\'s work',
                                                                check="sh", sc_exclude={"SC2154": FRAGMENT_VARS["SC2154"]}),
    # ── core/develop-steps/step-3g-post-optimization-test-re-run.md
    "core/develop-steps/step-3g-post-optimization-test-re-run.md#sh1": dict(
        anchor='git revert --no-edit "<commit-hash>"   # <commit-hash>: the optimization commit from step 1', check="sh"),
    # ── core/develop-steps/step-6-phase-gate.md
    "core/develop-steps/step-6-phase-gate.md#sh1": dict(anchor='GATE_BLOCKED=false', check="sh"),  # exec scenarios below
    "core/develop-steps/step-6-phase-gate.md#sh2": dict(
        anchor='cat > "agent_state/phases/${PHASE}/gate.failed" <<EOF', check="sh",
        exec=[dict(name="writes valid JSON with the gate_item step 0 reads", linux=False, env={"PHASE": "4"},
                   setup="mkdir -p agent_state/phases/4",
                   post="python3 -c \"import json;d=json.load(open('agent_state/phases/4/gate.failed'));print('ITEM', d['blockers'][0]['gate_item'])\"",
                   expect=[r"ITEM <failing gate item"])]),
    "core/develop-steps/step-6-phase-gate.md#sh3": dict(
        anchor='SCHEMA_EVO="agent_state/phases/${PHASE}/reports/schema_evolution.md"', check="sh",
        sc_exclude={"SC2154": FRAGMENT_VARS["SC2154"]},
        exec=[dict(name="unresolved BREAKING refuses the force-gate", env={"PHASE": "4"},
                   setup="mkdir -p agent_state/phases/4/reports && printf '  ⛔ BREAKING: User.role REMOVED (was string)\\n  ⛔ BREAKING: User.x REMOVED — versioned\\n' > agent_state/phases/4/reports/schema_evolution.md",
                   rc="nonzero", expect=[r"FORCE-GATE REFUSED: 1 unresolved"])]),
    "core/develop-steps/step-6-phase-gate.md#json1": dict(anchor='{', check="json", subst=[('"phase": N,', '"phase": 4,')], schema="gate_forced"),
    "core/develop-steps/step-6-phase-gate.md#sh4": dict(
        anchor='# Atomic manifest write: both checks run on the .tmp BEFORE the mv (a schema check after the mv', check="sh",
        sc_exclude={"SC2015": "intended: the block runs when validation OR the mv fails"},
        exec=[dict(name="complete manifest is moved", linux=False, env={"PHASE": "4"}, setup=(
                       "mkdir -p agent_state/phases/4 && echo '{\"phase\":4,\"goal\":\"g\",\"started_at\":\"t\",\"completed_at\":\"t\",\"attempt\":1,"
                       "\"brd_requirements_met\":[],\"test_results\":{},\"artifacts\":{},\"known_issues\":[],\"carried_forward\":[]}' > agent_state/phases/4/manifest.json.tmp"),
                   post="ls agent_state/phases/4", rc=0, expect=[r"^manifest\.json$"], reject=[r"manifest\.json\.tmp"]),
              dict(name="missing field: not written", linux=False, env={"PHASE": "4"},
                   setup="mkdir -p agent_state/phases/4 && echo '{\"phase\":4,\"goal\":\"g\"}' > agent_state/phases/4/manifest.json.tmp",
                   post="ls agent_state/phases/4", rc="nonzero", expect=[r"MISSING FIELDS", r"manifest\.json\.tmp"],
                   reject=[r"^manifest\.json$"])]),
    "core/develop-steps/step-6-phase-gate.md#sh5": dict(anchor='git tag "phase-${PHASE}-complete" -m "Phase ${PHASE} gate passed: $(date)"', check="sh",
                                                        sc_exclude={"SC2154": FRAGMENT_VARS["SC2154"]}),
    "core/develop-steps/step-6-phase-gate.md#sh6": dict(anchor='mkdir -p "agent_state/phases/${PHASE:?}"', check="sh"),
    "core/develop-steps/step-6-phase-gate.md#json2": dict(
        anchor='{', check="json", schema="manifest",
        subst=[('"phase": N,', '"phase": 4,'), ("<ISO 8601 timestamp>", "2026-09-30T12:00:00Z")]),
    # ── core/develop-steps/step-7-report.md
    "core/develop-steps/step-7-report.md#sh1": dict(anchor='echo "{\\"ts\\":\\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\\",\\"event\\":\\"pipeline_complete\\",\\"phase\\":${PHASE},\\"status\\":\\"<gate_passed|gate_failed|gate_forced>\\",\\"total_duration_s\\":<N>,\\"agents_run\\":<N>,\\"agents_failed\\":<N>}" >> "agent_state/phases/${PHASE}/execution.jsonl"',
                                                    check="sh", sc_exclude={"SC2154": FRAGMENT_VARS["SC2154"]}),
    # ── core/develop-steps/step-7b-phase-post-mortem.md
    "core/develop-steps/step-7b-phase-post-mortem.md#sh1": dict(
        anchor='# Calculate retry rate from execution log. jq, not grep \'"status":"completed"\': a line written as', check="sh",
        exec=[dict(name="counts json.dumps-spaced lines too", linux=False, needs=["jq"], env={"PHASE": "4"}, setup=(
                       "mkdir -p agent_state/phases/4 && printf '%s\\n' '{\"agent\": \"a\", \"status\": \"completed\"}' "
                       "'{\"agent\":\"b\",\"status\":\"completed\"}' '{\"agent\": \"a\", \"status\": \"failed\"}' 'not json' > agent_state/phases/4/execution.jsonl"),
                   expect=[r"Retry rate: 50% \(1 of 2 agents retried\)"])]),
    "core/develop-steps/step-7b-phase-post-mortem.md#sh2": dict(anchor='# Parse execution.jsonl for time distribution', check="sh"),
    "core/develop-steps/step-7b-phase-post-mortem.md#sh3": dict(anchor='# Carried-forward trend analysis', check="sh"),
    "core/develop-steps/step-7b-phase-post-mortem.md#sh4": dict(
        anchor='# Gate health analysis', check="sh",
        exec=[dict(name="two earlier failures", env={"PHASE": "4"},
                   setup="mkdir -p agent_state/phases/4 && touch agent_state/phases/4/gate.failed agent_state/phases/4/gate.failed.resolved",
                   expect=[r"PASSED on attempt 3 \(2 previous"])]),
    "core/develop-steps/step-7b-phase-post-mortem.md#json1": dict(anchor='"postmortem": {', check="json", wrap="{\n{}\n}",
                                                                 subst=[('"retry_rate_pct": N,', '"retry_rate_pct": 0,'), ('"systemic_patterns": N,', '"systemic_patterns": 0,')]),
    "core/develop-steps/step-7b-phase-post-mortem.md#sh5": dict(anchor='echo "{\\"ts\\":\\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\\",\\"event\\":\\"postmortem_complete\\",\\"phase\\":${PHASE},\\"retry_rate_pct\\":${RETRY_RATE:-0},\\"systemic_patterns\\":${PATTERN_COUNT:-0},\\"carried_forward_trend\\":\\"${CF_TREND:-baseline}\\"}" >> "agent_state/phases/${PHASE}/execution.jsonl"',
                                                                check="sh", sc_exclude={"SC2154": FRAGMENT_VARS["SC2154"]}),
    # ── databases/dynamodb.md
    "databases/dynamodb.md#sh1": dict(anchor='# Docker', check="sh"),
    # ── databases/elasticsearch.md (Kibana Dev Tools console format; not executed against Elasticsearch)
    "databases/elasticsearch.md#json1": dict(anchor='// Create index with explicit mappings — never rely on dynamic mapping in production', check="json", mode="console"),
    "databases/elasticsearch.md#json2": dict(anchor='POST /widgets/_search', check="json", mode="console"),
    "databases/elasticsearch.md#json3": dict(anchor='POST /widgets/_search', check="json", mode="console"),
    "databases/elasticsearch.md#json4": dict(anchor='POST /widgets/_search', check="json", mode="console"),
    "databases/elasticsearch.md#json5": dict(anchor='POST /_bulk', check="json", mode="console"),
    "databases/elasticsearch.md#json6": dict(anchor='// Create new index with updated mappings', check="json", mode="console", subst=[("{ ... }", "{}")]),
    "databases/elasticsearch.md#json7": dict(anchor='POST /widgets/_search', check="json", mode="console", subst=[("{ ... }", "{}")]),
    "databases/elasticsearch.md#json8": dict(anchor='// Page 1', check="json", mode="console", subst=[("{ ... }", "{}")]),
    "databases/elasticsearch.md#json9": dict(anchor='POST /widgets/_search?scroll=5m', check="json", mode="console", subst=[("{ ... }", "{}")]),
    # ── databases/firestore.md
    "databases/firestore.md#sh1": dict(anchor='# Install Firebase CLI', check="sh"),
    # ── databases/mysql.md
    "databases/mysql.md#sql1": dict(anchor='CREATE TABLE users (', check="mysql"),
    "databases/mysql.md#sql2": dict(anchor="-- Name the FK column's index yourself (InnoDB otherwise adds one named after the constraint)", check="mysql", fixture="mysql_orders"),
    "databases/mysql.md#sql3": dict(anchor='-- Parameterized always', check="mysql", fixture="mysql_orders", params=True),
    "databases/mysql.md#sql4": dict(anchor='START TRANSACTION;', check="mysql", fixture="mysql_accounts"),
    # ── databases/nebula.md (NebulaGraph 3.x, nGQL)
    "databases/nebula.md#ngql1": dict(anchor='CREATE SPACE IF NOT EXISTS threatmatrix (partition_num=15, replica_factor=3, vid_type=FIXED_STRING(64));', check="ngql",
                                      subst=[("replica_factor=3", "replica_factor=1")], after_ddl_wait=3),
    "databases/nebula.md#ngql2": dict(anchor='INSERT VERTEX asset(name, kind, created_at) VALUES "asset:10.0.0.5":("web-01","host", now());', check="ngql",
                                      fixture="threatmatrix", use="USE threatmatrix;"),
    "databases/nebula.md#ngql3": dict(anchor="-- 2-hop neighbors via native traversal (bind the starting VID, don't scan)", check="ngql",
                                      fixture="threatmatrix_indexed", use="USE threatmatrix;"),
    "databases/nebula.md#ngql4": dict(anchor='CREATE TAG INDEX IF NOT EXISTS idx_asset_name ON asset(name(32));', check="ngql",
                                      fixture="threatmatrix", use="USE threatmatrix;", after_ddl_wait=3),
    "databases/nebula.md#ngql5": dict(anchor='CREATE TAG session(created_at timestamp) TTL_DURATION = 86400, TTL_COL = "created_at";', check="ngql",
                                      fixture="threatmatrix", use="USE threatmatrix;"),
    # ── databases/postgres.md
    "databases/postgres.md#sql1": dict(anchor='created_at  timestamptz NOT NULL DEFAULT now(),', check="pg",
                                       wrap="CREATE TABLE audit_fields_example (\n  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),\n{}\n);\n"),
    "databases/postgres.md#sql2": dict(anchor='-- B-tree (default): equality and range queries', check="pg", fixture="app"),
    "databases/postgres.md#sql3": dict(anchor='-- Always parameterized — never string concatenation', check="pg", fixture="app", params=True),
    "databases/postgres.md#sql4": dict(anchor='ALTER TABLE certificates ENABLE ROW LEVEL SECURITY;', check="pg", fixture="app"),
    "databases/postgres.md#sql5": dict(anchor='-- Use appropriate isolation level', check="pg", rollback_between=True),
    "databases/postgres.md#sql6": dict(anchor="-- Cursor-based (keyset) — the only pagination: the cursor encodes the last row's (created_at, id)",
                                       check="pg", fixture="app", params=True),
    "databases/postgres.md#sql7": dict(anchor='-- Store flexible config in JSONB', check="pg", params=True),
    # ── databases/query-optimization.md
    "databases/query-optimization.md#sql1": dict(anchor='-- Equality: WHERE email = $1', check="pg", fixture="app"),
    "databases/query-optimization.md#sql2": dict(anchor='-- JSONB containment: WHERE metadata @> \'{"type": "premium"}\'', check="pg", fixture="app"),
    "databases/query-optimization.md#sql3": dict(anchor='-- Only index active users — smaller index, faster for common query', check="pg", fixture="app"),
    "databases/query-optimization.md#sql4": dict(anchor='-- INCLUDE columns are stored in the index but not used for lookup', check="pg", fixture="app", params=True),
    "databases/query-optimization.md#sql5": dict(anchor='-- Find unused indexes (since the last stats reset). Unique and primary-key indexes enforce', check="pg", fixture="app"),
    "databases/query-optimization.md#sql6": dict(anchor='-- BAD: counts ALL matching rows, then checks > 0', check="pg", fixture="app", params=True),
    "databases/query-optimization.md#sql7": dict(anchor='-- BAD: fetches all columns including large JSONB/text fields', check="pg", fixture="app", params=True),
    "databases/query-optimization.md#sql8": dict(anchor='-- Run EXPLAIN ANALYZE on every new query before deploying', check="pg", fixture="app"),
    "databases/query-optimization.md#sql9": dict(anchor='-- CTEs are optimization barriers in PostgreSQL < 12', check="pg", fixture="app"),
    "databases/query-optimization.md#sql10": dict(anchor='-- Insert multiple rows with unnest — single query, parameterized', check="pg", fixture="app", params=True),
    "databases/query-optimization.md#sql11": dict(anchor="-- The server must preload the module (shared_preload_libraries = 'pg_stat_statements', then a", check="pg"),
    "databases/query-optimization.md#sql12": dict(anchor='-- Table cache hit ratio — should be > 99%', check="pg", fixture="app"),
    # ── databases/sqlite.md
    "databases/sqlite.md#sql1": dict(anchor='PRAGMA journal_mode=WAL;      -- concurrent reads during writes', check="sqlite"),
    "databases/sqlite.md#sql2": dict(anchor='-- Column addition safe (SQLite supports ADD COLUMN)', check="sqlite", fixture="sqlite_users"),
    "databases/sqlite.md#sql3": dict(anchor='CREATE INDEX idx_users_email ON users(email);', check="sqlite", fixture="sqlite_users"),
    # ── frameworks/quarkus.md
    "frameworks/quarkus.md#sh1": dict(anchor='# Live reload with dev services (auto-provisions DB, Kafka, Redis)', check="sh"),
    # ── frameworks/react.md: the rules of a flat-config entry
    "frameworks/react.md#json1": dict(anchor='{', check="json", schema="eslint_rules"),
    # ── frameworks/spring-boot.md
    "frameworks/spring-boot.md#yaml1": dict(anchor='# application.yml — base config', check="yaml"),
    "frameworks/spring-boot.md#json1": dict(anchor='{"error": {"code": "NOT_FOUND", "message": "Widget not found.", "request_id": "b7e1c2…", "retryable": false}}',
                                            check="json", schema="envelope"),
    # ── infrastructure/docker.md
    "infrastructure/docker.md#dockerfile1": dict(
        anchor="# Stage 1: Builder — the tag's Go version equals the versions table and the `go` line in go.mod.", check="dockerfile",
        subst=[("ARG GO_VERSION=<Go>", "ARG GO_VERSION=1.25")], context="go", build_args={"GIT_SHA": "abc123"},
        run_checks=[dict(name="runs as the numeric user, GIT_SHA baked in", args=["--entrypoint", "/app"], cmd=["whoami"],
                         expect=r"uid=65532 GIT_SHA=abc123")]),
    "infrastructure/docker.md#yaml1": dict(anchor='services:', check="yaml", compose=True,
                                           subst=[("postgres:<PostgreSQL>-alpine", "postgres:17-alpine")]),
    "infrastructure/docker.md#dockerfile2": dict(
        anchor='# Copy dependency files FIRST (changes less often)', check="dockerfile", context="node",
        wrap="FROM node:22-slim\nWORKDIR /app\n{}\n"),
    # ── infrastructure/github-actions.md
    "infrastructure/github-actions.md#yaml1": dict(
        anchor='name: CI', check="yaml", gha=True,
        subst=[("<commands.lint>", "make lint"), ("<commands.typecheck>", "make typecheck"),
               ('<commands["test:unit"]>', "make test-unit"), ('<commands["test:integration"]>', "make test-integration"),
               ("<commands.build>", "make build"), ("postgres:<PostgreSQL>-alpine", "postgres:17-alpine")]),
    "infrastructure/github-actions.md#yaml2": dict(
        anchor='# setup-go / setup-node have built-in caching keyed on the lockfile (go.sum, package-lock.json).', check="yaml", gha=True,
        subst=[("<lang>", "go")], indent=10,
        wrap="name: cache\non: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/cache@v4\n        with:\n"
             "          path: ~/go/pkg/mod\n{}\n"),
    "infrastructure/github-actions.md#yaml3": dict(anchor='env:', check="yaml", gha=True, indent=4,
                                                   wrap="name: env\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n{}\n    steps:\n      - run: echo ok\n"),
    "infrastructure/github-actions.md#yaml4": dict(anchor='deploy-prod:', check="yaml", gha=True, indent=2,
                                                   wrap="name: cd\non: push\njobs:\n  deploy-staging:\n    runs-on: ubuntu-latest\n    steps:\n      - run: ./deploy.sh staging\n{}\n"),
    # ── infrastructure/kubernetes.md
    "infrastructure/kubernetes.md#yaml1": dict(anchor='apiVersion: apps/v1', check="yaml", k8s=True,
                                               subst=[("sha256:<digest>", "sha256:" + "0" * 64)]),
    "infrastructure/kubernetes.md#yaml2": dict(anchor='# ConfigMap: non-sensitive config', check="yaml", k8s=True),
    "infrastructure/kubernetes.md#yaml3": dict(anchor='apiVersion: autoscaling/v2', check="yaml", k8s=True),
    # ── infrastructure/localstack-aws-local.md
    "infrastructure/localstack-aws-local.md#yaml1": dict(anchor='services:', check="yaml", compose=True),
    "infrastructure/localstack-aws-local.md#yaml2": dict(anchor='services:', check="yaml", compose=True),
    "infrastructure/localstack-aws-local.md#sh1": dict(anchor='# .env.local', check="sh",
                                                       sc_exclude={"SC2034": "a dotenv file: the variables are read by the app, not by this file",
                                                                   "SC2209": "dotenv value `test` is a string, not a command to run"}),
    "infrastructure/localstack-aws-local.md#sh2": dict(anchor='#!/bin/bash', check="sh"),
    "infrastructure/localstack-aws-local.md#sh3": dict(anchor='#!/bin/bash', check="sh"),
    "infrastructure/localstack-aws-local.md#sh4": dict(anchor='#!/bin/bash', check="sh"),
    "infrastructure/localstack-aws-local.md#sh5": dict(anchor='#!/bin/bash', check="sh"),
    "infrastructure/localstack-aws-local.md#sh6": dict(anchor='#!/bin/bash', check="sh"),
    "infrastructure/localstack-aws-local.md#sh7": dict(anchor='#!/bin/bash', check="sh"),
    "infrastructure/localstack-aws-local.md#yaml3": dict(anchor='# .github/workflows/test.yml', check="yaml", gha=True,
                                                         wrap="name: test\non: pull_request\n{}\n"),
    "infrastructure/localstack-aws-local.md#yaml4": dict(anchor='# Extends base docker-compose.yml with multi-region HA', check="yaml", compose=True,
                                                         env={"SESSION_SECRET_WEST": "harness-not-a-secret"}),
    "infrastructure/localstack-aws-local.md#sh8": dict(anchor='#!/bin/bash', check="sh"),
    "infrastructure/localstack-aws-local.md#sh9": dict(
        anchor='#!/bin/bash', check="sh",
        sc_exclude={"SC2015": "test-report idiom: log_fail on a failed check; log_pass itself cannot fail"},
        exec=[dict(name="nothing listening: every check reported, suite exits 1 (set -e no longer aborts on curl)", linux=False,
                   needs=["curl"], setup="mkdir -p bin && printf '#!/bin/sh\\nexit 0\\n' > bin/docker && printf '#!/bin/sh\\necho {}\\n' > bin/awslocal && chmod +x bin/*",
                   env={"PATH": "{cwd}/bin:/usr/bin:/bin:/opt/homebrew/bin"},
                   subst=[("sleep 5", "true"), ("sleep 10", "true"), ("re", r"code 808([01])\)", r"code 5908\1)")],
                   rc=1, expect=[r"East unhealthy \(000\)", r"Results: [0-9]+ passed, [0-9]+ failed", r"HA validation: FAIL"])]),
    "infrastructure/localstack-aws-local.md#sh10": dict(anchor='# /deploy --target=ha-local', check="sh",
                                                        sc_exclude={"SC1113": "not a shebang: the first line is a comment that starts with '# /'"}),
    # ── infrastructure/saas-tenancy-models.md
    "infrastructure/saas-tenancy-models.md#sql1": dict(anchor='-- Enable RLS on every tenant-scoped table', check="pg", fixture="resources"),
    "infrastructure/saas-tenancy-models.md#sql2": dict(anchor='-- WRONG: global uniqueness', check="pg", fixture="unique_demo",
                                                       subst=[("re", r"^(UNIQUE\(.*\))$", r"ALTER TABLE unique_demo ADD \1;")]),
    "infrastructure/saas-tenancy-models.md#yaml1": dict(anchor='# Kubernetes namespace per premium tenant', check="yaml", k8s=True,
                                                        subst=[("${TENANT_SLUG}", "acme"), ("${TENANT_ID}", "4b1d6c1e-2f3a-4b5c-8d9e-0f1a2b3c4d5e"),
                                                               ("${API_IMAGE}", "registry.example/api@sha256:" + "0" * 64)]),
    # ── infrastructure/secrets-management.md
    "infrastructure/secrets-management.md#hcl1": dict(anchor='# Vault: reference, never inline the value', check="hcl", fixture="vault"),
    "infrastructure/secrets-management.md#yaml1": dict(
        anchor='# Kubernetes: inject from a manager via External Secrets / CSI driver, not a committed Secret', check="yaml", k8s=True, indent=10,
        wrap="apiVersion: apps/v1\nkind: Deployment\nmetadata: { name: api }\nspec:\n  selector: { matchLabels: { app: api } }\n"
             "  template:\n    metadata: { labels: { app: api } }\n    spec:\n      containers:\n        - name: api\n"
             "          image: registry.example/api:1.0.0\n{}\n"),
    "infrastructure/secrets-management.md#sh1": dict(anchor='gitleaks detect --source . --redact           # scan working tree + history', check="sh"),
    # ── infrastructure/terraform.md
    "infrastructure/terraform.md#hcl1": dict(anchor='# backend.tf', check="hcl"),
    "infrastructure/terraform.md#hcl2": dict(anchor='module "api" {', check="hcl", fixture="modules"),
    "infrastructure/terraform.md#sh1": dict(anchor='terraform fmt -recursive && terraform validate', check="sh"),
    # ── languages/go.md
    "languages/go.md#yaml1": dict(anchor='# .golangci.yml — golangci-lint v2 refuses a config without the version key', check="yaml", golangci=True),
    # ── languages/java.md
    "languages/java.md#yaml1": dict(anchor='spring:', check="yaml"),
    # ── languages/rust.md
    "languages/rust.md#sh1": dict(anchor='# Create migration (writes migrations/<YYYYMMDDHHMMSS>_create_orders_table.sql)', check="sh"),
    "languages/rust.md#sql1": dict(anchor='-- migrations/20240115093000_create_orders_table.sql', check="pg", fixture="tenants"),
    "languages/rust.md#sh2": dict(anchor='# Run migrations', check="sh"),
    # ── languages/typescript.md
    "languages/typescript.md#json1": dict(anchor='{', check="json", schema="tsconfig"),
    # ── testing/appium-mobile.md
    "testing/appium-mobile.md#sh1": dict(anchor='npm i -D appium webdriverio @wdio/cli', check="sh"),
    # ── testing/contract-testing.md
    "testing/contract-testing.md#sh1": dict(anchor='# Publish contract from consumer CI. The token comes from the PACT_BROKER_TOKEN env var (a CI', check="sh"),
    "testing/contract-testing.md#yaml1": dict(anchor='# Consumer CI pipeline', check="yaml"),  # a generic CI sketch, not a GitHub Actions file
    # ── testing/detox.md
    "testing/detox.md#sh1": dict(anchor='detox build -c ios.sim.release && detox test -c ios.sim.release', check="sh"),
    # ── testing/external-service-mocks.md (recorded vendor response shapes; several per block)
    "testing/external-service-mocks.md#json1": dict(anchor='// POST /v1/payment_intents', check="json", mode="jsonc", count=3),
    "testing/external-service-mocks.md#json2": dict(anchor='// GET /.well-known/jwks.json (JWKS endpoint)', check="json", mode="jsonc", count=2),
    "testing/external-service-mocks.md#json3": dict(anchor='// POST /v3/mail/send (SendGrid)', check="json", mode="jsonc", count=1),
    "testing/external-service-mocks.md#json4": dict(anchor='// POST /2010-04-01/Accounts/{sid}/Messages.json', check="json", mode="jsonc", count=1),
    "testing/external-service-mocks.md#json5": dict(anchor='// POST /v1/chat/completions (OpenAI)', check="json", mode="jsonc", count=2),
    # ── testing/gomock.md
    "testing/gomock.md#sh1": dict(anchor='# Install mockgen', check="sh"),
    # ── testing/junit-mockito.md
    "testing/junit-mockito.md#sh1": dict(anchor='mvn test                                    # run all tests', check="sh"),
    # ── testing/load-testing.md
    "testing/load-testing.md#sh1": dict(anchor='# Against the deployed build', check="sh",
                                        sc_exclude={"SC2034": "rc is what the CI step hands to its caller", "SC2154": FRAGMENT_VARS["SC2154"]}),
    "testing/load-testing.md#sh2": dict(anchor='# Run with 100 users, spawn rate 10/sec', check="sh"),
    "testing/load-testing.md#yaml1": dict(anchor='# benchmark.yml — drill interpolates {{ VAR }} from the environment (base, url, headers):', check="yaml", drill=True),
    "testing/load-testing.md#sh3": dict(anchor='drill --benchmark benchmark.yml --stats', check="sh"),
    "testing/load-testing.md#yaml2": dict(anchor='load-test:', check="yaml", gha=True, indent=2,
                                          wrap="name: load\non: push\njobs:\n  deploy-staging:\n    runs-on: ubuntu-latest\n    steps:\n      - run: ./deploy.sh staging\n{}\n"),
    # ── testing/maestro.md
    "testing/maestro.md#sh1": dict(anchor='curl -fsSL "https://get.maestro.mobile.dev" -o maestro-install.sh && bash maestro-install.sh   # installs to ~/.maestro/bin',
                                   check="sh", sc_exclude={"SC2154": FRAGMENT_VARS["SC2154"]}),
    "testing/maestro.md#yaml1": dict(anchor='# .maestro/TC-ME2E-20101-login.yaml', check="yaml", maestro=True),
    "testing/maestro.md#yaml2": dict(anchor='# .maestro/subflows/sign-in.yaml — reused by every authenticated flow', check="yaml", maestro=True),
    "testing/maestro.md#yaml3": dict(anchor='- runFlow: subflows/sign-in.yaml', check="yaml", maestro="commands"),
    # ── testing/msw.md
    "testing/msw.md#sh1": dict(anchor='npm install msw --save-dev', check="sh"),
    "testing/msw.md#sh2": dict(anchor='# Generate service worker file', check="sh"),
    # ── testing/mutation-testing.md
    "testing/mutation-testing.md#sh1": dict(
        anchor='P="${PHASE:?}"; BASE="$(cat "agent_state/phases/$P/base_sha")" || exit 1', check="sh",
        exec=[dict(name="scope = changed source files; tests excluded", linux=False, needs=["git"], env={"PHASE": "3"},
                   setup=GIT_REPO + " && mkdir -p agent_state/phases/3 && git rev-parse HEAD > agent_state/phases/3/base_sha && "
                         "echo a > svc.go && echo t > svc_test.go && git add svc.go svc_test.go && git commit -qm c",
                   post="cat agent_state/phases/3/mutation_scope.txt", rc=0, expect=[r"^svc\.go$"], reject=[r"svc_test"]),
              dict(name="nothing changed is an empty scope, not a failure", linux=False, needs=["git"], env={"PHASE": "3"},
                   setup=GIT_REPO + " && mkdir -p agent_state/phases/3 && git rev-parse HEAD > agent_state/phases/3/base_sha", rc=0),
              dict(name="unknown base fails", linux=False, needs=["git"], env={"PHASE": "3"},
                   setup=GIT_REPO + " && mkdir -p agent_state/phases/3 && echo deadbeef > agent_state/phases/3/base_sha", rc="nonzero")]),
    "testing/mutation-testing.md#json1": dict(anchor='{"schema": "sdlc.mutation/v1", "tool": "gremlins", "command": "…", "scope_files": 12,', check="json"),
    # ── testing/playwright.md
    "testing/playwright.md#sh1": dict(anchor='APP_BASE_URL=http://app-qa.localhost:18080 npx playwright test          # run all tests against qa', check="sh"),
    # ── testing/targeted-testing.md
    "testing/targeted-testing.md#sh1": dict(anchor='# Go — test specific package', check="sh"),
    "testing/targeted-testing.md#sh2": dict(anchor='# Go — use air or gotestsum', check="sh"),
    # ── testing/test-case-traceability.md
    "testing/test-case-traceability.md#sh1": dict(
        anchor='P="${PHASE:?}"', check="sh",
        exec=[dict(name="no runner sidecars: blocked, not silently source mode", env={"PHASE": "3"}, rc="nonzero",
                   expect=[r"no runner sidecars"])]),
    # ── testing/test-results-sidecar.md
    "testing/test-results-sidecar.md#sh1": dict(anchor='python3 .claude/hooks/junit-to-sidecar.py --tier unit --command "<the command you ran>" --exit-code "$RC" \\',
                                                check="sh", sc_exclude={"SC2154": FRAGMENT_VARS["SC2154"]}),
    "testing/test-results-sidecar.md#json1": dict(anchor='{', check="json", schema="sidecar"),
    "testing/test-results-sidecar.md#sh2": dict(anchor="git log -1 --format=%H -- . ':(exclude)agent_state' ':(exclude)docs' ':(exclude).claude' ':(exclude)deploy/k8s/overlays'", check="sh"),
    # ── testing/testcontainers.md
    "testing/testcontainers.md#sh1": dict(anchor='go get github.com/testcontainers/testcontainers-go', check="sh"),
    # ── testing/vitest.md
    "testing/vitest.md#sh1": dict(anchor='vitest                     # watch mode (dev)', check="sh"),
    # ── ui/accessibility-patterns.md
    "ui/accessibility-patterns.md#json1": dict(anchor='{', check="json", schema="eslint_rules"),
    # ── ui/shadcn.md
    "ui/shadcn.md#sh1": dict(anchor='# Initialize shadcn/ui in a project', check="sh"),
    # ── ui/stitch-design.md
    "ui/stitch-design.md#json1": dict(anchor='{', check="json"),
    # ── ui/structured-wireframe-format.md (format spec: YAML parse only)
    "ui/structured-wireframe-format.md#yaml1": dict(anchor='# <screen-name>.wireframe.yaml', check="yaml"),
    "ui/structured-wireframe-format.md#yaml2": dict(anchor='screen:', check="yaml"),
    "ui/structured-wireframe-format.md#yaml3": dict(anchor='states:', check="yaml"),
    "ui/structured-wireframe-format.md#yaml4": dict(anchor='error_boundaries:', check="yaml"),
    "ui/structured-wireframe-format.md#yaml5": dict(anchor='screen:', check="yaml"),
    "ui/structured-wireframe-format.md#yaml6": dict(anchor='screen:', check="yaml"),
}

# step 6 gate fixtures: complete evidence, then one broken item per scenario
_STEP6_BASE = (
    "R=agent_state/phases/4/reports; mkdir -p $R agent_state/reconciliation/phase-4 docs/design/phases/4/specs && "
    "for t in unit_tests integration_tests e2e_results acceptance_report; do printf 'Total: 12\\nFailed: 0\\n' > $R/$t.md; done && "
    "for r in code_review_I code_review_II security_review; do printf '# Review\\nBLOCKING:0 WARNING:2 INFO:1\\n' > $R/$r.md; done && "
    "echo 'TC-API-001 creates' > docs/design/phases/4/specs/a.md && "
    "echo '{\"verdict\":\"PASS\"}' > agent_state/reconciliation/phase-4/specs_vs_tests.json")
BLOCKS["core/develop-steps/step-6-phase-gate.md#sh1"]["exec"] = [
    dict(name="complete evidence passes", linux=False, needs=["jq"], env={"PHASE": "4"}, setup=_STEP6_BASE, rc=0,
         expect=[r"Gate item enforcement passed"]),
    dict(name="a report with no total blocks", linux=False, needs=["jq"], env={"PHASE": "4"},
         setup=_STEP6_BASE + " && echo 'all good' > $R/unit_tests.md", rc=1, expect=[r"unit: no 'total: N'"]),
    dict(name="a missing review blocks", linux=False, needs=["jq"], env={"PHASE": "4"},
         setup=_STEP6_BASE + " && rm $R/security_review.md", rc=1, expect=[r"security_review\.md is missing"]),
    dict(name="a review count line with BLOCKING:2 blocks", linux=False, needs=["jq"], env={"PHASE": "4"},
         setup=_STEP6_BASE + " && printf 'BLOCKING:2 WARNING:0 INFO:0\\n' > $R/code_review_II.md", rc=1,
         expect=[r"code_review_II has 2 unresolved"]),
    dict(name="prose fallback: an unresolved BLOCKING next to a resolved one still blocks", linux=False, needs=["jq"], env={"PHASE": "4"},
         setup=_STEP6_BASE + " && printf -- '- BLOCKING: SQL injection in q.go:12\\n- BLOCKING: IDOR in h.go:40 (resolved)\\n- BLOCKING: race in w.go:7\\n' > $R/code_review_I.md",
         rc=1, expect=[r"code_review_I has 1 unresolved"]),
    dict(name="TC inventory verdict FAIL blocks", linux=False, needs=["jq"], env={"PHASE": "4"},
         setup=_STEP6_BASE + " && echo '{\"verdict\":\"FAIL\"}' > agent_state/reconciliation/phase-4/specs_vs_tests.json",
         rc=1, expect=[r"TC-\* inventory verdict is FAIL"]),
    dict(name="specs with TC IDs but no inventory blocks", linux=False, needs=["jq"], env={"PHASE": "4"},
         setup=_STEP6_BASE + " && rm agent_state/reconciliation/phase-4/specs_vs_tests.json", rc=1, expect=[r"specs_vs_tests\.json is missing"]),
]

# nebula.md claims, proven on NebulaGraph (live); every claim has its own space
NGQL_CLAIMS = [
    dict(name='LOOKUP needs an index', block="databases/nebula.md#ngql1", at='`LOOKUP` and property-anchored `MATCH` **cannot run without an index**', setup=['CREATE SPACE IF NOT EXISTS c_lookup (partition_num=3, replica_factor=1, vid_type=FIXED_STRING(64));', 'SLEEP', 'USE c_lookup; CREATE TAG IF NOT EXISTS asset(name string, kind string, created_at timestamp); CREATE EDGE IF NOT EXISTS communicates_with(protocol string, first_seen timestamp, last_seen timestamp);', 'SLEEP', 'USE c_lookup; INSERT VERTEX asset(name, kind, created_at) VALUES "a1":("web-01","host", now()), "a2":("dns","host", now()); INSERT EDGE communicates_with(protocol, first_seen, last_seen) VALUES "a1" -> "a2"@0:("dns", now(), now());'], query='USE c_lookup; LOOKUP ON asset WHERE asset.name == "web-01" YIELD id(vertex) AS vid;', error='There is no index to use at runtime'),
    dict(name='MATCH from a tag needs an index', block="databases/nebula.md#ngql1", at='`LOOKUP` and property-anchored `MATCH` **cannot run without an index**', setup=['CREATE SPACE IF NOT EXISTS c_match (partition_num=3, replica_factor=1, vid_type=FIXED_STRING(64));', 'SLEEP', 'USE c_match; CREATE TAG IF NOT EXISTS asset(name string, kind string, created_at timestamp); CREATE EDGE IF NOT EXISTS communicates_with(protocol string, first_seen timestamp, last_seen timestamp);', 'SLEEP', 'USE c_match; INSERT VERTEX asset(name, kind, created_at) VALUES "a1":("web-01","host", now()), "a2":("dns","host", now()); INSERT EDGE communicates_with(protocol, first_seen, last_seen) VALUES "a1" -> "a2"@0:("dns", now(), now());'], query='USE c_match; MATCH (a:asset)-[:communicates_with]->(b:asset) WHERE a.asset.kind == "host" RETURN a, b LIMIT 100;', error='IndexNotFound: No valid index found'),
    dict(name='a new index does not backfill existing rows', block="databases/nebula.md#ngql1", at='Creating an index does not backfill', setup=['CREATE SPACE IF NOT EXISTS c_backfill (partition_num=3, replica_factor=1, vid_type=FIXED_STRING(64));', 'SLEEP', 'USE c_backfill; CREATE TAG IF NOT EXISTS asset(name string, kind string, created_at timestamp); CREATE EDGE IF NOT EXISTS communicates_with(protocol string, first_seen timestamp, last_seen timestamp);', 'SLEEP', 'USE c_backfill; INSERT VERTEX asset(name, kind, created_at) VALUES "a1":("web-01","host", now()), "a2":("dns","host", now()); INSERT EDGE communicates_with(protocol, first_seen, last_seen) VALUES "a1" -> "a2"@0:("dns", now(), now());', 'USE c_backfill; CREATE TAG INDEX IF NOT EXISTS idx_asset_name ON asset(name(32));', 'SLEEP'], query='USE c_backfill; LOOKUP ON asset WHERE asset.name == "web-01" YIELD id(vertex) AS vid;', expect=['Empty set']),
    dict(name='REBUILD makes existing rows visible', block="databases/nebula.md#ngql1", at='REQUIRED after creating an index on existing data', setup=['CREATE SPACE IF NOT EXISTS c_rebuild (partition_num=3, replica_factor=1, vid_type=FIXED_STRING(64));', 'SLEEP', 'USE c_rebuild; CREATE TAG IF NOT EXISTS asset(name string, kind string, created_at timestamp); CREATE EDGE IF NOT EXISTS communicates_with(protocol string, first_seen timestamp, last_seen timestamp);', 'SLEEP', 'USE c_rebuild; INSERT VERTEX asset(name, kind, created_at) VALUES "a1":("web-01","host", now()), "a2":("dns","host", now()); INSERT EDGE communicates_with(protocol, first_seen, last_seen) VALUES "a1" -> "a2"@0:("dns", now(), now());', 'USE c_rebuild; CREATE TAG INDEX IF NOT EXISTS idx_asset_name ON asset(name(32));', 'SLEEP', 'USE c_rebuild; REBUILD TAG INDEX idx_asset_name;', 'SLEEP'], query='USE c_rebuild; LOOKUP ON asset WHERE asset.name == "web-01" YIELD id(vertex) AS vid;', expect=['"a1"']),
    dict(name='GO from a known VID needs no index', block="databases/nebula.md#ngql1", at='native, fastest traversal from known VIDs', setup=['CREATE SPACE IF NOT EXISTS c_go (partition_num=3, replica_factor=1, vid_type=FIXED_STRING(64));', 'SLEEP', 'USE c_go; CREATE TAG IF NOT EXISTS asset(name string, kind string, created_at timestamp); CREATE EDGE IF NOT EXISTS communicates_with(protocol string, first_seen timestamp, last_seen timestamp);', 'SLEEP', 'USE c_go; INSERT VERTEX asset(name, kind, created_at) VALUES "a1":("web-01","host", now()), "a2":("dns","host", now()); INSERT EDGE communicates_with(protocol, first_seen, last_seen) VALUES "a1" -> "a2"@0:("dns", now(), now());'], query='USE c_go; GO 1 STEPS FROM "a1" OVER communicates_with YIELD dst(edge) AS peer;', expect=['"a2"']),
    dict(name='replica_factor above the storaged count is refused', block="databases/nebula.md#ngql1", at='must not exceed the', setup=[], query='CREATE SPACE IF NOT EXISTS c_replicas (partition_num=15, replica_factor=3, vid_type=FIXED_STRING(64));', error='Host not enough'),
]

# ─────────────────────────────────────────────────────────────────────────── SQL fixtures ──
SQL_FIXTURES = {
    # PostgreSQL: the tables the database packs' fragments assume
    "app": """
CREATE TABLE tenants (id uuid PRIMARY KEY DEFAULT gen_random_uuid());
CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid, email text, name text, password_hash text,
  status text, is_active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now(), deleted_at timestamptz);
CREATE TABLE orders (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid, user_id uuid REFERENCES users(id), status text,
  total numeric(12,2), created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE events (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), type text, metadata jsonb, payload jsonb, created_at timestamptz);
CREATE TABLE tickets (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tags text[]);
CREATE TABLE articles (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), title text, body text);
CREATE TABLE tags (name text, category text);
CREATE TABLE certificates (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, serial text, status text,
  created_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz);
CREATE TABLE certs (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, status text, serial text, expires_at timestamptz);
""",
    "orders_tenant": "CREATE TABLE orders (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, total numeric);",
    "resources": "CREATE TABLE resources (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, name text);",
    "unique_demo": "CREATE TABLE unique_demo (tenant_id uuid NOT NULL, serial_number text, name text, slug text);",
    "tenants": "CREATE TABLE tenants (id uuid PRIMARY KEY DEFAULT gen_random_uuid());",
    # MySQL 8.4
    "mysql_orders": """
CREATE TABLE users (id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY, email VARCHAR(255) NOT NULL, name VARCHAR(255) NOT NULL);
CREATE TABLE orders (id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY, user_id BIGINT UNSIGNED NOT NULL,
  status VARCHAR(20) NOT NULL, created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6));
""",
    "mysql_accounts": "CREATE TABLE accounts (id BIGINT UNSIGNED PRIMARY KEY, balance DECIMAL(12,2) NOT NULL);\n"
                      "INSERT INTO accounts VALUES (1, 500), (2, 0);",
    # SQLite
    "sqlite_users": "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL);\n"
                    "CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id));",
}

# ───────────────────────────────────────────────── claims a doc makes, proven on the real engine (--live) ──
_ORDERS_200K = """
CREATE TABLE orders (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL, status text NOT NULL,
  total numeric(12,2), created_at timestamptz NOT NULL);
INSERT INTO orders (user_id, status, total, created_at)
SELECT md5((g % 2000)::text)::uuid, CASE WHEN g % 100 = 0 THEN 'pending' ELSE 'completed' END, g % 500,
       now() - g * interval '1 minute'
FROM generate_series(1, 200000) g;
"""
_TENANCY_RLS = (
    "DROP ROLE IF EXISTS app_rw; CREATE ROLE app_rw NOSUPERUSER NOBYPASSRLS;"
    "CREATE TABLE resources (id serial PRIMARY KEY, tenant_id uuid NOT NULL);"
    "GRANT SELECT, INSERT ON resources TO app_rw; GRANT USAGE ON SEQUENCE resources_id_seq TO app_rw;"
    "INSERT INTO resources (tenant_id) SELECT CASE WHEN g <= 4 THEN md5('a')::uuid ELSE md5('b')::uuid END"
    " FROM generate_series(1, 10) g;"
    "ALTER TABLE resources ENABLE ROW LEVEL SECURITY; ALTER TABLE resources FORCE ROW LEVEL SECURITY;"
    "CREATE POLICY tenant_isolation ON resources USING (tenant_id = current_setting('app.current_tenant_id')::uuid)"
    " WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);"
    "SET ROLE app_rw;")
CLAIMS = [
    dict(name="composite index: not used for (status) alone on PG17", block="databases/query-optimization.md#sql1", at="but NOT for (status) alone",
         setup=_ORDERS_200K + "CREATE INDEX idx_orders_user_status_created ON orders(user_id, status, created_at DESC); ANALYZE orders;",
         query="EXPLAIN SELECT * FROM orders WHERE status = 'pending'", expect=[r"Seq Scan on orders"], reject=[r"idx_orders_user_status_created"]),
    dict(name="composite index: used for (user_id, status) ORDER BY created_at", block="databases/query-optimization.md#sql1", at="Leftmost prefix rule",
         setup=_ORDERS_200K + "CREATE INDEX idx_orders_user_status_created ON orders(user_id, status, created_at DESC); ANALYZE orders;",
         query="EXPLAIN SELECT * FROM orders WHERE user_id = md5('7')::uuid AND status = 'pending' ORDER BY created_at",
         expect=[r"Index Scan( Backward)? using idx_orders_user_status_created"], reject=[r"\bSort\b"]),
    dict(name="partial index picked when the WHERE matches", block="databases/query-optimization.md#sql3", at="Query planner uses this index automatically",
         setup=_ORDERS_200K + "CREATE INDEX idx_orders_pending ON orders(created_at DESC) WHERE status = 'pending'; ANALYZE orders;",
         query="EXPLAIN SELECT * FROM orders WHERE status = 'pending' ORDER BY created_at DESC", expect=[r"idx_orders_pending"]),
    dict(name="covering index: Index Only Scan after VACUUM", block="databases/query-optimization.md#sql4", at="This query can be satisfied entirely",
         setup=_ORDERS_200K + "CREATE INDEX idx_orders_user_covering ON orders(user_id) INCLUDE (status, total, created_at); VACUUM ANALYZE orders;",
         query="EXPLAIN SELECT status, total, created_at FROM orders WHERE user_id = md5('7')::uuid",
         expect=[r"Index Only Scan using idx_orders_user_covering"]),
    dict(name="EXISTS stops at the first match", block="databases/query-optimization.md#sql6", at="GOOD: stops at first match",
         setup=_ORDERS_200K + "ANALYZE orders;",
         query="EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF) SELECT EXISTS(SELECT 1 FROM orders WHERE user_id = md5('7')::uuid)",
         expect=[r"Seq Scan on orders \(actual rows=1 loops=1\)"]),
    dict(name="CTE inlined on PG12+ (no CTE Scan)", block="databases/query-optimization.md#sql9", at="In PostgreSQL 12+, CTEs can be inlined",
         setup="CREATE TABLE users (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), email text, is_active boolean);"
               "CREATE TABLE orders (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid, created_at timestamptz);",
         query="EXPLAIN WITH active_users AS (SELECT id, email FROM users WHERE is_active = true) "
               "SELECT au.email FROM active_users au JOIN orders o ON o.user_id = au.id",
         reject=[r"CTE Scan"], expect=[r"Seq Scan on users"]),
    dict(name="uuid ids: unnest($1::text[]) = uuid fails, ::uuid[] works", block="databases/query-optimization.md#sql10", at="ids are uuids",
         setup="CREATE TABLE users (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid, status text);"
               "PREPARE good AS UPDATE users SET status = d.s FROM (SELECT unnest($1::uuid[]) AS id, unnest($2::text[]) AS s) d "
               "WHERE users.id = d.id AND users.tenant_id = $3;",
         query="PREPARE bad AS UPDATE users SET status = d.s FROM (SELECT unnest($1::text[]) AS id, unnest($2::text[]) AS s) d WHERE users.id = d.id",
         error=r"operator does not exist: uuid = text"),
    dict(name="pg_stat_statements needs shared_preload_libraries", block="databases/query-optimization.md#sql11", at="The server must preload the module",
         setup="CREATE EXTENSION IF NOT EXISTS pg_stat_statements;",
         query="SELECT CASE WHEN current_setting('shared_preload_libraries') LIKE '%pg_stat_statements%' "
               "THEN 'preloaded, view works: ' || (SELECT count(*) >= 0 FROM pg_stat_statements)::text ELSE 'not preloaded' END",
         expect=[r"preloaded, view works: true"]),
    dict(name="jsonb_path_ops serves @>", block="databases/postgres.md#sql7", at="the jsonb_path_ops index serves",
         setup="CREATE TABLE policies (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, config jsonb NOT NULL DEFAULT '{}');"
               "INSERT INTO policies (tenant_id, config) SELECT md5((g % 50)::text)::uuid, jsonb_build_object('algorithm', "
               "CASE WHEN g % 1000 = 0 THEN 'ECDSA-P256' ELSE 'RSA-' || g END) FROM generate_series(1, 100000) g;"
               "CREATE INDEX ON policies USING GIN (config jsonb_path_ops); ANALYZE policies;",
         query="""EXPLAIN SELECT id FROM policies WHERE config @> '{"algorithm": "ECDSA-P256"}'""",
         expect=[r"Bitmap Index Scan on policies_config_idx"]),
    dict(name="jsonb_path_ops does not serve ->> equality", block="databases/postgres.md#sql7", at="can't use that index",
         setup="CREATE TABLE policies (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, config jsonb NOT NULL DEFAULT '{}');"
               "INSERT INTO policies (tenant_id, config) SELECT md5((g % 50)::text)::uuid, jsonb_build_object('algorithm', "
               "CASE WHEN g % 1000 = 0 THEN 'ECDSA-P256' ELSE 'RSA-' || g END) FROM generate_series(1, 100000) g;"
               "CREATE INDEX ON policies USING GIN (config jsonb_path_ops); ANALYZE policies;",
         query="EXPLAIN SELECT id FROM policies WHERE config->>'algorithm' = 'ECDSA-P256'",
         reject=[r"policies_config_idx"], expect=[r"Seq Scan on policies"]),
    dict(name="keyset page: one index range scan, no sort", block="databases/postgres.md#sql6", at="Cursor-based (keyset)",
         setup="CREATE TABLE certificates (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, serial text, status text,"
               " created_at timestamptz NOT NULL);"
               "INSERT INTO certificates (tenant_id, serial, status, created_at) SELECT md5((g % 5)::text)::uuid, 's' || g, 'active',"
               " now() - g * interval '1 minute' FROM generate_series(1, 200000) g;"
               "CREATE INDEX certificates_page_idx ON certificates (tenant_id, created_at DESC, id DESC); ANALYZE certificates;",
         query="EXPLAIN SELECT id, serial, status, created_at FROM certificates WHERE tenant_id = md5('1')::uuid "
               "AND (created_at, id) < (now() - interval '50000 minutes', '00000000-0000-0000-0000-000000000000') "
               "ORDER BY created_at DESC, id DESC LIMIT 20",
         expect=[r"Index Scan using certificates_page_idx", r"Index Cond: .*ROW\(created_at, id\) <"], reject=[r"\bSort\b"]),
    dict(name="ADD COLUMN constant DEFAULT is metadata-only; a volatile one rewrites", block="databases/postgres.md", at="is metadata-only since PostgreSQL 11",
         setup="CREATE TABLE big (id int); INSERT INTO big SELECT generate_series(1, 100000);"
               "CREATE TABLE fn (k text, v oid); INSERT INTO fn VALUES ('start', pg_relation_filenode('big'));"
               "ALTER TABLE big ADD COLUMN c int NOT NULL DEFAULT 0; INSERT INTO fn VALUES ('constant', pg_relation_filenode('big'));"
               "ALTER TABLE big ADD COLUMN u uuid DEFAULT gen_random_uuid(); INSERT INTO fn VALUES ('volatile', pg_relation_filenode('big'));",
         query="SELECT 'constant rewrote=' || ((SELECT v FROM fn WHERE k='constant') <> (SELECT v FROM fn WHERE k='start'))"
               " || ' volatile rewrote=' || ((SELECT v FROM fn WHERE k='volatile') <> (SELECT v FROM fn WHERE k='constant'))",
         expect=[r"constant rewrote=false volatile rewrote=true"]),
    dict(name="RLS: the owner bypasses ENABLE alone; FORCE applies it to the owner too", block="core/shared-backend-patterns.md#sql1", at="FORCE ROW LEVEL SECURITY",
         setup="DROP ROLE IF EXISTS app_owner; CREATE ROLE app_owner NOSUPERUSER NOBYPASSRLS; GRANT CREATE ON SCHEMA public TO app_owner;"
               "SET ROLE app_owner;"
               "CREATE TABLE orders (id serial, tenant_id uuid NOT NULL);"
               "INSERT INTO orders (tenant_id) SELECT md5((g % 2)::text)::uuid FROM generate_series(1, 10) g;"
               "CREATE POLICY tenant_isolation ON orders USING (tenant_id = current_setting('app.current_tenant_id')::uuid);"
               "ALTER TABLE orders ENABLE ROW LEVEL SECURITY;"
               "SELECT set_config('app.current_tenant_id', md5('0')::uuid::text, false);"
               "CREATE TABLE seen (k text, n int); INSERT INTO seen SELECT 'enable_only', count(*) FROM orders;"
               "ALTER TABLE orders FORCE ROW LEVEL SECURITY; INSERT INTO seen SELECT 'forced', count(*) FROM orders;"
               "RESET ROLE;",
         query="SELECT string_agg(k || '=' || n, ' ' ORDER BY k DESC) FROM seen", expect=[r"forced=5 enable_only=10"]),
    # saas-tenancy-models.md's policy, run as a NOSUPERUSER NOBYPASSRLS role that does not own the table
    dict(name='tenancy RLS: a tenant sees only its own rows', block="infrastructure/saas-tenancy-models.md#sql1", at='Policy enforces isolation even if WHERE clause is missing',
         setup=_TENANCY_RLS + "BEGIN; SELECT set_config('app.current_tenant_id', md5('a')::uuid::text, true);",
         query="SELECT count(*) || ' of 10' FROM resources", expect=['^4 of 10$']),
    dict(name='tenancy RLS: no tenant set (fresh session) fails closed', block="infrastructure/saas-tenancy-models.md#sql1", at='with no default raises an error when the setting is',
         setup=_TENANCY_RLS + '',
         query='SELECT count(*) FROM resources', error='unrecognized configuration parameter "app\\.current_tenant_id"'),
    dict(name='tenancy RLS: pooled session after a tenant transaction fails closed', block="infrastructure/saas-tenancy-models.md#sql1", at='errors too: closed either way',
         setup=_TENANCY_RLS + "BEGIN; SELECT set_config('app.current_tenant_id', md5('a')::uuid::text, true); COMMIT;",
         query='SELECT count(*) FROM resources', error='invalid input syntax for type uuid: ""'),
    dict(name='tenancy RLS: WITH CHECK refuses a row for another tenant', block="infrastructure/saas-tenancy-models.md#sql1", at="WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);",
         setup=_TENANCY_RLS + "BEGIN; SELECT set_config('app.current_tenant_id', md5('a')::uuid::text, true);",
         query="INSERT INTO resources (tenant_id) VALUES (md5('b')::uuid) RETURNING id", error='new row violates row-level security policy'),
]
MYSQL_CLAIMS = [
    dict(name="InnoDB default isolation is REPEATABLE READ", block="databases/mysql.md#sql4", at="START TRANSACTION",
         query="SELECT @@transaction_isolation", expect=[r"REPEATABLE-READ"]),
    dict(name="InnoDB creates the FK index itself when none exists", block="databases/mysql.md#sql2", at="Name the FK column's index yourself",
         setup=["CREATE TABLE users (id BIGINT UNSIGNED PRIMARY KEY)",
                "CREATE TABLE orders (id BIGINT UNSIGNED PRIMARY KEY, user_id BIGINT UNSIGNED NOT NULL, "
                "CONSTRAINT fk_orders_user FOREIGN KEY (user_id) REFERENCES users(id))"],
         query="SELECT GROUP_CONCAT(index_name) FROM information_schema.statistics WHERE table_schema = DATABASE() "
               "AND table_name = 'orders' AND column_name = 'user_id'", expect=[r"^fk_orders_user$"]),
]
SQLITE_CLAIMS = [
    dict(name="DROP COLUMN works on a plain column (SQLite >= 3.35)", block="databases/sqlite.md#sql2", at="ALTER TABLE users DROP COLUMN phone",
         setup="CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, phone TEXT);",
         query="ALTER TABLE users DROP COLUMN phone"),
    dict(name="DROP COLUMN fails on an indexed column", block="databases/sqlite.md#sql2", at="It fails on PRIMARY KEY and UNIQUE",
         setup="CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT); CREATE INDEX idx_users_email ON users(email);",
         query="ALTER TABLE users DROP COLUMN email", error=r"error in index idx_users_email after drop column"),
    dict(name="DROP COLUMN fails on a PRIMARY KEY column", block="databases/sqlite.md#sql2", at="It fails on PRIMARY KEY and UNIQUE",
         setup="CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT);",
         query="ALTER TABLE users DROP COLUMN id", error=r"cannot drop PRIMARY KEY column"),
    dict(name="DROP COLUMN fails on a UNIQUE column", block="databases/sqlite.md#sql2", at="It fails on PRIMARY KEY and UNIQUE",
         setup="CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT UNIQUE);",
         query="ALTER TABLE users DROP COLUMN email", error=r"cannot drop UNIQUE column"),
    dict(name="DROP COLUMN fails on a column a table-level FOREIGN KEY names", block="databases/sqlite.md#sql2", at="table-level FOREIGN KEY still names",
         setup="CREATE TABLE p (id INTEGER PRIMARY KEY); CREATE TABLE u (id INTEGER PRIMARY KEY, p INTEGER, FOREIGN KEY (p) REFERENCES p(id));",
         query="ALTER TABLE u DROP COLUMN p", error=r"unknown column \"p\" in foreign key definition"),
]

# ───────────────────────────────────────────────────────────────────── schema checks (json) ──
def _load(p):
    return json.load(open(REPO / p, encoding="utf-8"))


def _validate(schema, value, b, what):
    import jsonschema
    v = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    return [(b.first_line, f"{what}: {'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message}")
            for e in sorted(v.iter_errors(value), key=lambda e: list(map(str, e.absolute_path)))]


def _envelope(b, vals, spec):
    """api/response-envelope.md: success {data, meta.request_id[, meta.pagination]} or error {error{…}}."""
    errs = []
    for i, v in enumerate(vals, 1):
        tag = f"envelope value {i}"
        if not isinstance(v, dict):
            errs.append((b.first_line, f"{tag}: not an object"))
            continue
        if "error" in v:
            if set(v) != {"error"}:
                errs.append((b.first_line, f"{tag}: an error body has only \"error\" (no data/meta), got {sorted(v)}"))
            e = v["error"]
            for k, t in (("code", str), ("message", str), ("request_id", str), ("retryable", bool)):
                if not isinstance(e.get(k), t):
                    errs.append((b.first_line, f"{tag}: error.{k} missing or not {t.__name__}"))
            for d in e.get("details", []):
                if not {"field", "code", "message"} <= set(d):
                    errs.append((b.first_line, f"{tag}: error.details[] entries need field, code, message"))
            extra = set(e) - {"code", "message", "details", "request_id", "retryable"}
            if extra:
                errs.append((b.first_line, f"{tag}: unknown error keys {sorted(extra)}"))
            continue
        if set(v) != {"data", "meta"}:
            errs.append((b.first_line, f"{tag}: a success body is exactly {{data, meta}}, got {sorted(v)}"))
            continue
        meta = v["meta"]
        if not isinstance(meta.get("request_id"), str):
            errs.append((b.first_line, f"{tag}: meta.request_id missing"))
        if isinstance(v["data"], list):
            p = meta.get("pagination")
            if not isinstance(p, dict) or not (isinstance(p.get("has_more"), bool) and isinstance(p.get("limit"), int)
                                               and (p.get("next_cursor") is None or isinstance(p.get("next_cursor"), str))):
                errs.append((b.first_line, f"{tag}: a collection needs meta.pagination {{next_cursor, has_more, limit}}"))
            if p and set(p) - {"next_cursor", "has_more", "limit", "total_count"}:
                errs.append((b.first_line, f"{tag}: pagination has non-cursor keys {sorted(set(p) - {'next_cursor', 'has_more', 'limit', 'total_count'})}"))
        elif "pagination" in meta:
            errs.append((b.first_line, f"{tag}: pagination on a single resource"))
    return errs


def _manifest(b, vals, spec):
    return _validate(_load("agent_state/manifest_schema.json"), vals[0], b, "agent_state/manifest_schema.json")


def _manifest_test_results(b, vals, spec):
    s = _load("agent_state/manifest_schema.json")
    sub = dict(s["properties"]["test_results"], **{"$defs": s["$defs"]})
    return _validate(sub, vals[0]["test_results"], b, "manifest_schema.json#/properties/test_results")


def _gate_forced(b, vals, spec):
    """The two jq expressions verify-gate.sh evaluates on gate.forced, run on the example."""
    errs = []
    doc = json.dumps(vals[0])
    for expr, what in (('(.blockers | type=="array" and length>0) and (.user_rationale // "" | length>0)', "well-formed override"),
                       ('[.security_acknowledged[]? | select((.finding // "") != "" and (.approved_by // "") != "" and (.reason // "") != "")] | length > 0',
                        "per-finding security acknowledgement")):
        r = subprocess.run(["jq", "-e", expr], input=doc, capture_output=True, text=True)
        if r.returncode:
            errs.append((b.first_line, f"verify-gate.sh would not accept this gate.forced ({what}): jq {expr}"))
    return errs


SIDECAR_SCHEMA = {
    "type": "object",
    "required": ["schema", "tier", "verdict", "total", "passed", "failed", "skipped", "flaky", "code_sha", "dirty", "cases"],
    "properties": {
        "schema": {"const": "sdlc.test-results/v1"},
        "tier": {"type": "string", "minLength": 1},
        "verdict": {"enum": ["PASS", "FAIL", "ERROR", "BLOCKED"]},
        "total": {"type": "integer", "minimum": 0}, "passed": {"type": "integer", "minimum": 0},
        "failed": {"type": "integer", "minimum": 0}, "skipped": {"type": "integer", "minimum": 0},
        "flaky": {"type": "integer", "minimum": 0},
        "code_sha": {"type": ["string", "null"]}, "dirty": {"type": "boolean"},
        "env": {"type": ["string", "null"]}, "base_url": {"type": ["string", "null"]},
        "command": {"type": ["string", "null"]}, "exit_code": {"type": ["integer", "null"]},
        "cases": {"type": "array", "items": {
            "type": "object", "required": ["name", "verdict"],
            "properties": {"name": {"type": "string"},
                           "verdict": {"enum": ["PASS", "FAIL", "SKIPPED", "FLAKY", "BLOCKED", "UNTESTED"]},
                           "ids": {"type": "array", "items": {"type": "string", "pattern": "^TC-[A-Z0-9]+-[0-9]+$"}},
                           "priority": {"enum": ["HIGH", "MEDIUM", "LOW"]}}}},
        "quarantined": {"type": "array", "items": {"type": "object", "required": ["name", "issue", "expires"],
                                                   "properties": {"expires": {"type": "string", "format": "date"}}}},
        "ts": {"type": "string", "format": "date-time"},
    },
}


def _sidecar(b, vals, spec):
    """sdlc.test-results/v1 as its producer (junit-to-sidecar.py) writes it and verify-gate.sh reads it.
    The doc's "A|B|C" values list the allowed values: every one must be valid, and the verdict lists must
    be complete (the gate selects on FLAKY, the converter writes it)."""
    import copy
    errs = []
    doc = copy.deepcopy(vals[0])
    enum_of = {("verdict",): SIDECAR_SCHEMA["properties"]["verdict"]["enum"],
               ("cases", "verdict"): SIDECAR_SCHEMA["properties"]["cases"]["items"]["properties"]["verdict"]["enum"],
               ("cases", "priority"): SIDECAR_SCHEMA["properties"]["cases"]["items"]["properties"]["priority"]["enum"]}
    for path, enum in enum_of.items():
        holders = [doc] if len(path) == 1 else doc.get(path[0], [])
        for h in holders:
            alts = str(h.get(path[-1], "")).split("|")
            bad = [a for a in alts if a not in enum]
            if bad:
                errs.append((b.first_line, f"sidecar {'.'.join(path)}: {bad} not in {enum}"))
            if path != ("cases", "priority") and set(alts) != set(enum):
                errs.append((b.first_line, f"sidecar {'.'.join(path)} lists {alts}; the producer/gate use {enum}"))
            h[path[-1]] = alts[0]
    doc["env"] = doc.get("env", "").split("|")[0]
    doc["tier"] = doc.get("tier", "").split("|")[0]
    errs += _validate(SIDECAR_SCHEMA, doc, b, "sdlc.test-results/v1 (harness schema)")
    # the producer's own output must satisfy the same schema (keeps the schema honest)
    import tempfile
    d = Path(tempfile.mkdtemp(prefix="sidecar-", dir=_ctx.tmp))
    (d / "u.xml").write_text('<testsuite><testcase classname="a" name="TestTC_API_001_ok"/>'
                             '<testcase name="TC-API-002 fails"><failure message="x"/></testcase>'
                             '<testcase name="skip"><skipped/></testcase></testsuite>')
    r = subprocess.run(["python3", str(REPO / ".claude/hooks/junit-to-sidecar.py"), "--tier", "unit", "--command", "go test",
                        "--exit-code", "1", "--out", str(d / "out.json"), str(d / "u.xml")], capture_output=True, text=True, cwd=d)
    if not (d / "out.json").exists():
        errs.append((b.first_line, f"junit-to-sidecar.py produced nothing: {r.stderr.strip()}"))
    else:
        errs += [(ln, "junit-to-sidecar.py output vs the schema: " + m) for ln, m in
                 _validate(SIDECAR_SCHEMA, json.load(open(d / "out.json")), b, "producer")]
    return errs


def _eval_shape(kind):
    """Doc examples use the same keys/check kinds as the real suite under agent_state/eval/."""
    def check(b, vals, spec):
        suite = sorted((REPO / "agent_state/eval/suite").glob("*/"))
        v = vals[0]
        errs = []
        if kind == "rubric":
            real = [r for t in suite for r in json.load(open(t / "rubric.json"))["rubric"]]
            keys = set().union(*map(set, real)) | {"ids"}
            checks = {r["check"] for r in real} | {"tc_ids_annotated"}
            for r in v["rubric"]:
                if set(r) - keys:
                    errs.append((b.first_line, f"rubric entry keys {sorted(set(r) - keys)} are not used by any suite rubric.json"))
                if r.get("check") not in checks:
                    errs.append((b.first_line, f"rubric check {r.get('check')!r} is not one the suite uses {sorted(checks)}"))
            if abs(sum(r["weight"] for r in v["rubric"]) - 1.0) > 1e-9:
                errs.append((b.first_line, f"rubric weights sum to {sum(r['weight'] for r in v['rubric'])}, not 1.0"))
        elif kind == "trajectory":
            real = [s for t in suite for s in json.load(open(t / "expected_trajectory.json"))["expected_trajectory"]]
            keys = set().union(*map(set, real))
            for s in v["expected_trajectory"]:
                if set(s) - keys:
                    errs.append((b.first_line, f"trajectory step keys {sorted(set(s) - keys)} not used by the suite"))
            names = [s["step"] for s in v["expected_trajectory"]]
            for s in v["expected_trajectory"]:
                if s.get("order_after") and s["order_after"] not in names:
                    errs.append((b.first_line, f"order_after {s['order_after']!r} names no step"))
        elif kind == "artifacts":
            prefixes = {a.split(":", 1)[0] for t in suite for x in json.load(open(t / "expected_artifacts.json"))["artifacts"] for a in x["assert"]}
            for x in v["artifacts"]:
                for a in x["assert"]:
                    if a.split(":", 1)[0] not in prefixes:
                        errs.append((b.first_line, f"assert kind {a.split(':', 1)[0]!r} is not used by the suite ({sorted(prefixes)})"))
        elif kind == "baseline":
            real = json.load(open(next((REPO / "agent_state/eval/baselines").glob("*.json"))))
            missing = {"date", "git_sha", "suite_sha", "suite_size", "tasks"} - set(v)
            if missing:
                errs.append((b.first_line, f"baseline lacks {sorted(missing)}"))
            tkeys = set().union(*map(set, real["tasks"]))
            for t in v["tasks"]:
                if set(t) - tkeys:
                    errs.append((b.first_line, f"baseline task keys {sorted(set(t) - tkeys)} not in the seed baseline"))
        return errs
    return check


def _eslint_rules(b, vals, spec):
    """A flat-config rules map: every key a jsx-a11y rule, every value a severity. --live: ESLint 10 with
    eslint-plugin-jsx-a11y loads it after flatConfigs.recommended and reports a known violation."""
    errs = []
    v = vals[0]
    for k, sev in v.items():
        if not k.startswith("jsx-a11y/") or sev not in ("error", "warn", "off", 2, 1, 0):
            errs.append((b.first_line, f"not a rules map entry: {k!r}: {sev!r}"))
    if _ctx is not None and _ctx.live and not errs:
        d = _eslint_dir()
        (d / "eslint.config.mjs").write_text(
            'import jsxA11y from "eslint-plugin-jsx-a11y";\n'
            f"export default [jsxA11y.flatConfigs.recommended, {{ files: [\"**/*.jsx\"], rules: {json.dumps(v)} }}];\n")
        (d / "c.jsx").write_text('export const C = () => <div><img src="x.png" /><h1></h1></div>;\n')
        r = subprocess.run(["npx", "--no-install", "eslint", "-f", "json", "c.jsx"], cwd=d, capture_output=True, text=True)
        try:
            msgs = json.loads(r.stdout)[0]["messages"]
        except Exception:
            return [(b.first_line, f"ESLint could not load the config: {(r.stdout + r.stderr).strip()[:400]}")]
        fatal = [m for m in msgs if m.get("fatal") or "Definition for rule" in m.get("message", "")]
        if fatal:
            errs.append((b.first_line, f"ESLint: {fatal[0]['message']}"))
        if not any(m.get("ruleId") == "jsx-a11y/heading-has-content" for m in msgs):
            errs.append((b.first_line, "ESLint with this config did not report jsx-a11y/heading-has-content on an empty <h1>"))
    return errs


_ESLINT_DIR = None


def _eslint_dir():
    global _ESLINT_DIR
    if _ESLINT_DIR is None:
        d = HERE / ".cache" / "eslint10"
        d.mkdir(parents=True, exist_ok=True)
        if not (d / "node_modules" / "eslint-plugin-jsx-a11y").exists():
            (d / "package.json").write_text('{"name": "harness-eslint", "private": true, "type": "module"}\n')
            # eslint-plugin-jsx-a11y 6.10.2 (the latest) declares peer eslint <= 9, so npm refuses ESLint 10
            # without --legacy-peer-deps; the plugin itself runs under 10 (this check is the proof)
            subprocess.run(["npm", "install", "--silent", "--no-audit", "--no-fund", "--legacy-peer-deps",
                            "eslint@10", "eslint-plugin-jsx-a11y@6"], cwd=d, capture_output=True, text=True)
        _ESLINT_DIR = d
    for f in ("eslint.config.mjs", "c.jsx"):
        (_ESLINT_DIR / f).unlink(missing_ok=True)
    return _ESLINT_DIR


def _tsconfig(b, vals, spec):
    """--live: the TypeScript compiler accepts every compilerOptions key (tsc --showConfig)."""
    if _ctx is None or not _ctx.live:
        return []
    import tempfile
    d = Path(tempfile.mkdtemp(prefix="tsconfig-", dir=_ctx.tmp))
    (d / "tsconfig.json").write_text(json.dumps(vals[0]))
    (d / "a.ts").write_text("export const x: number = 1;\n")
    r = subprocess.run(["npx", "--yes", "-p", "typescript@5.9", "tsc", "--showConfig", "-p", str(d)], capture_output=True, text=True)
    if r.returncode:
        return [(b.first_line, f"tsc --showConfig: {(r.stdout + r.stderr).strip()[:400]}")]
    shown = json.loads(r.stdout).get("compilerOptions", {})
    return [(b.first_line, f"tsc dropped compilerOptions.{k}") for k in vals[0]["compilerOptions"] if k not in shown]


SCHEMA_CHECKS = {
    "envelope": _envelope, "manifest": _manifest, "manifest_test_results": _manifest_test_results,
    "gate_forced": _gate_forced, "sidecar": _sidecar, "eval_rubric": _eval_shape("rubric"),
    "eval_trajectory": _eval_shape("trajectory"), "eval_artifacts": _eval_shape("artifacts"),
    "eval_baseline": _eval_shape("baseline"), "eslint_rules": _eslint_rules, "tsconfig": _tsconfig,
}

# ─────────────────────────────────────────────────────────────── docker build contexts ──
DOCKER_CONTEXTS = {
    "go": {
        "go.mod": "module example.com/app\n\ngo 1.25\n",
        "go.sum": "",
        "cmd/app/main.go": 'package main\n\nimport (\n\t"fmt"\n\t"os"\n)\n\nfunc main() {\n'
                           '\tif len(os.Args) > 1 && os.Args[1] == "whoami" {\n'
                           '\t\tfmt.Printf("uid=%d GIT_SHA=%s\\n", os.Getuid(), os.Getenv("GIT_SHA"))\n\t\treturn\n\t}\n'
                           '\tfmt.Println("serve")\n}\n',
        ".dockerignore": ".git\n",
    },
    "node": {
        "package.json": '{"name": "app", "version": "1.0.0", "private": true, "scripts": {"build": "node -e \\"require(\'fs\').mkdirSync(\'dist\', {recursive: true})\\""}}\n',
        "package-lock.json": '{"name": "app", "version": "1.0.0", "lockfileVersion": 3, "requires": true, '
                             '"packages": {"": {"name": "app", "version": "1.0.0"}}}\n',
        "src/index.js": "console.log('ok');\n",
    },
}

# ─────────────────────────────────────────────────────────────── terraform/tofu fixtures ──
HCL_FIXTURES = {
    "vault": {"versions.tf": 'terraform {\n  required_providers {\n    vault = { source = "hashicorp/vault" }\n  }\n}\n'},
    "modules": {
        "envs/prod/variables.tf": 'variable "api_cpu" { type = number }\nvariable "api_image" { type = string }\n',
        "envs/prod/network.tf": 'module "network" {\n  source = "../../modules/network"\n}\n',
        "modules/network/main.tf": 'output "private_subnet_ids" { value = ["subnet-a", "subnet-b"] }\n',
        "modules/service/main.tf": 'variable "name" { type = string }\nvariable "cpu" { type = number }\n'
                                   'variable "image" { type = string }\nvariable "subnets" { type = list(string) }\n',
    },
}
# module "api" { source = "../../modules/service" } resolves from envs/<env>/ → the fixture places the
# block two levels down so the relative source path is the doc's own
HCL_LAYOUT = {"modules": "envs/prod"}

# ─────────────────────────────────────────────────────────────────── nGQL fixtures ──
_SPACE = ["CREATE SPACE IF NOT EXISTS threatmatrix (partition_num=3, replica_factor=1, vid_type=FIXED_STRING(64));"]
_SCHEMA = ["USE threatmatrix; CREATE TAG IF NOT EXISTS asset(name string, kind string, created_at timestamp); "
           "CREATE TAG IF NOT EXISTS actor(handle string, confidence double); "
           "CREATE EDGE IF NOT EXISTS communicates_with(protocol string, first_seen timestamp, last_seen timestamp);"]
NGQL_SETUP = {
    "threatmatrix": _SPACE + ["SLEEP"] + _SCHEMA + ["SLEEP"],
    "threatmatrix_indexed": _SPACE + ["SLEEP"] + _SCHEMA + ["SLEEP"] + [
        "USE threatmatrix; CREATE TAG INDEX IF NOT EXISTS idx_asset_name ON asset(name(32));", "SLEEP",
        'USE threatmatrix; INSERT VERTEX asset(name, kind, created_at) VALUES "asset:10.0.0.5":("web-01","host", now()), '
        '"asset:8.8.8.8":("dns","host", now()); INSERT EDGE communicates_with(protocol, first_seen, last_seen) '
        'VALUES "asset:10.0.0.5" -> "asset:8.8.8.8"@0:("dns", now(), now());',
        "USE threatmatrix; REBUILD TAG INDEX idx_asset_name;", "SLEEP"],
}


def tool_versions(ctx):
    def v(cmd):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return (r.stdout or r.stderr).strip().splitlines()[0] if (r.stdout or r.stderr).strip() else "?"
        except Exception:
            return "not installed"
    import sqlite3
    out = [f"bash {', '.join(x for _, x in ctx.bashes)}",
           "shellcheck " + re.sub(r".*version: ", "", subprocess.run(["shellcheck", "--version"], capture_output=True, text=True).stdout.replace("\n", " ")).split()[0],
           "actionlint " + v(["actionlint", "--version"]), v(["hadolint", "--version"]),
           v([__import__("shutil").which("terraform") or "tofu", "version"]), f"SQLite {sqlite3.sqlite_version}"]
    try:
        import pglast
        out.append(f"pglast {pglast.__version__} (libpg_query {'.'.join(map(str, pglast.parser.get_postgresql_version()))})")
    except Exception:
        pass
    out.append(v(["docker", "compose", "version"]) if __import__("shutil").which("docker") else "docker compose ?")
    if ctx.live:
        out += [f"postgres {getattr(ctx, 'pg_version', '-')}", f"mysql {getattr(ctx, 'mysql_version', '-')}",
                f"kubeconform (k8s schema {K8S_VERSION})", v(["golangci-lint", "version"]).split(" built")[0],
                f"NebulaGraph {NEBULA_VERSION}" if ctx.nebula else "NebulaGraph -"]
    return out
