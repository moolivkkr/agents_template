#!/usr/bin/env python3
"""Prove the harness fails on broken samples: put a known bug back into a COPY of .claude/skills and
check that the harness run on that copy fails, with the expected message.

Most mutations restore the exact text a doc had before it was fixed on 2026-09-30, so this also shows
the old samples were broken. The others cover the inventory itself (a new block, a moved block).
Run through run.sh --selftest (it needs the venv). Exit 0 = every mutation was caught.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parents[2] / ".claude" / "skills"

# (name, file, old text, new text, harness args, text the failing run must print)
MUTATIONS = [
    ("phase detection back on grep -P (macOS grep rejects -P: every project restarts at Phase 1)",
     "core/develop-steps/step-0-orient.md",
     '''LAST_PASSED=0
for g in agent_state/phases/*/gate.passed; do
  n="${g#agent_state/phases/}"; n="${n%/gate.passed}"
  case "$n" in ''|*[!0-9]*) continue ;; esac   # the unmatched glob itself, or a non-numeric dir
  if [ "$n" -gt "$LAST_PASSED" ]; then LAST_PASSED="$n"; fi
done
PHASE="${ARG_PHASE:-$((LAST_PASSED + 1))}"''',
     '''LAST_PASSED=$(ls agent_state/phases/*/gate.passed 2>/dev/null | grep -oP 'phases/\\K\\d+' | sort -n | tail -1)
PHASE=${ARG_PHASE:-$(( ${LAST_PASSED:-0} + 1 ))}''',
     ["--only", "step-0-orient.md#sh1"], "next phase after the highest gate.passed"),
    ("stale data contract only warns again (fail-open)",
     "core/develop-steps/step-0-orient.md",
     '''      || { echo "⛔ BLOCKED: data-contracts.md is stale or unreadable — re-run /plan --phase=${PHASE} or update it"; exit 1; }''',
     '''      || echo "⚠ Contract validation failed — review data-contracts.md before proceeding"''',
     ["--only", "step-0-orient.md#sh6"], "stale contract blocks"),
    ("a missing review report is skipped again (fail-open gate)",
     "core/develop-steps/step-6-phase-gate.md",
     '''  if [ ! -s "$F" ]; then
    echo "⛔ GATE BLOCKED: ${R}.md is missing or empty"; GATE_BLOCKED=true; continue
  fi''',
     '''  [ -f "$F" ] || continue
  :
  :''',
     ["--only", "step-6-phase-gate.md#sh1"], "a missing review blocks"),
    ("no typecheck row runs nothing and passes again",
     "core/develop-steps/step-2-implementation.md",
     '''[ -n "$CMD" ] || { echo "⛔ BLOCKED: no typecheck/build row in $V"; exit 1; }''',
     '''[ -n "$CMD" ] || echo "⛔ BLOCKED: no typecheck/build row in $V"''',
     ["--only", "step-2-implementation.md#sh1"], "no typecheck/build row blocks"),
    ("memory_get reads a missing root file first again (awk stops there)",
     "core/memory-as-tools.md",
     '''  ' "${files[@]}"
}''',
     '''  ' agent_state/lessons.md agent_state/patterns.md agent_state/phases/*/lessons.md 2>/dev/null
}''',
     ["--only", "memory-as-tools.md#sh2"], "per-phase lessons found with no root lessons.md"),
    ("the old pagination block: no semicolon between the cursor and OFFSET queries (a syntax error)",
     "databases/postgres.md",
     """LIMIT $4;

-- ❌ NEVER — OFFSET: rows shift between pages under concurrent writes, and every page re-reads and
-- discards all the rows before it
-- SELECT * FROM certificates WHERE tenant_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3;""",
     """LIMIT $4

-- Offset-based (simpler, OK for small datasets / admin UIs)
SELECT * FROM certificates WHERE tenant_id = $1
ORDER BY created_at DESC LIMIT $2 OFFSET $3""",
     ["--only", "postgres.md#sql6"], "PostgreSQL 17 grammar"),
    ("ConfigMap and Secret in one YAML document again (duplicate keys)",
     "infrastructure/kubernetes.md", "  PORT: \"8080\"\n---\n", "  PORT: \"8080\"\n\n",
     ["--only", "kubernetes.md#yaml2"], "duplicate key"),
    (".golangci.yml without version: \"2\" (golangci-lint v2 refuses it)",
     "languages/go.md", 'version: "2"\n', "\n", ["--only", "go.md#yaml1"], "unsupported version"),
    ("manifest example without started_at (fails agent_state/manifest_schema.json)",
     "core/develop-steps/step-6-phase-gate.md", '  "started_at": "<ISO 8601 timestamp>",\n', "",
     ["--only", "step-6-phase-gate.md#json2"], "'started_at' is a required property"),
    ("sidecar doc drops FLAKY from the case verdicts (the producer and the gate use it)",
     "testing/test-results-sidecar.md", "PASS|FAIL|SKIPPED|FLAKY|BLOCKED|UNTESTED", "PASS|FAIL|SKIPPED|BLOCKED|UNTESTED",
     ["--only", "test-results-sidecar.md#json1"], "the producer/gate use"),
    ("Elasticsearch request body with a trailing comma",
     "databases/elasticsearch.md", '    "refresh_interval": "1s",\n', '    "refresh_interval": "1s",,\n',
     ["--only", "elasticsearch.md#json1"], "request body of PUT /widgets"),
    ("untagged base image again",
     "infrastructure/docker.md", "FROM gcr.io/distroless/static-debian12:nonroot\n", "FROM gcr.io/distroless/static-debian12\n",
     ["--only", "docker.md#dockerfile1", "--family", "dockerfile"], "DL3006"),
    ("non-canonical HCL",
     "infrastructure/terraform.md", '    bucket       = "acme-tfstate"', '    bucket = "acme-tfstate"',
     ["--only", "terraform.md#hcl1"], "fmt -check"),
    ("a new, unconfigured block",
     "databases/sqlite.md", "## Rules\n", "```sql\nSELECT 1;\n```\n\n## Rules\n",
     ["--inventory-only"], "units.EXPECTED says 3"),
    ("a block whose first line changed",
     "databases/mysql.md", "CREATE TABLE users (\n", "CREATE TABLE IF NOT EXISTS users (\n",
     ["--inventory-only"], "drifted"),
]


def main():
    py = sys.executable
    failures = 0
    base = Path(tempfile.mkdtemp(prefix="config-packs-selftest-"))
    try:
        # the unmodified docs pass the same selections first (else a "caught" mutation proves nothing)
        clean = base / "clean"
        shutil.copytree(SKILLS, clean)
        for name, _, _, _, args, _ in MUTATIONS:
            r = subprocess.run([py, str(HERE / "harness.py"), *args], capture_output=True, text=True,
                               env=dict(os.environ, CONFIG_PACKS_SKILLS_DIR=str(clean)))
            if r.returncode:
                failures += 1
                print(f"✗ baseline fails before mutating ({' '.join(args)}):\n{(r.stdout + r.stderr)[-800:]}")
        for i, (name, rel, old, new, args, expect) in enumerate(MUTATIONS, 1):
            d = base / f"m{i}"
            shutil.copytree(SKILLS, d)
            p = d / rel
            text = p.read_text(encoding="utf-8")
            if text.count(old) != 1:
                failures += 1
                print(f"✗ {name}: the text to mutate occurs {text.count(old)} times in {rel} (selftest is stale)")
                continue
            p.write_text(text.replace(old, new), encoding="utf-8")
            r = subprocess.run([py, str(HERE / "harness.py"), *args], capture_output=True, text=True,
                               env=dict(os.environ, CONFIG_PACKS_SKILLS_DIR=str(d)))
            out = r.stdout + r.stderr
            if r.returncode == 0 or expect not in out:
                failures += 1
                print(f"✗ NOT caught: {name} (exit {r.returncode}, wanted /{expect}/)\n{out[-800:]}")
            else:
                line = next((l for l in out.splitlines() if expect in l), "").strip()
                print(f"✓ caught: {name}\n    {line[:220]}")
    finally:
        shutil.rmtree(base, ignore_errors=True)
    print(f"\nselftest: {len(MUTATIONS) - failures}/{len(MUTATIONS)} mutations caught" if not failures
          else f"\nselftest FAILED: {failures} problem(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
