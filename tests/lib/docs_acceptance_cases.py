#!/usr/bin/env python3
"""Tests for .claude/hooks/docs-policy.py and acceptance-map.py on synthetic repos.

docs-policy: lean by default, per-project overrides, profile switch, one-run env override, and every key the
commands gate on actually exists (a typo'd key would silently skip a document forever).

acceptance-map: a requirement change or a new phase must show up as blocking acceptance work — a changed FR
is CHANGED until its TC-ACC rows follow it (or a reasoned ack), an FR with no rows is NEW, a missing SHALL is
PARTIAL — while edits that don't change the requirement (traceability matrix, Source column) don't. Exit 0 = all pass.
"""
import glob, json, os, re, shutil, subprocess, sys, tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DP = os.path.join(REPO, ".claude", "hooks", "docs-policy.py")
AM = os.path.join(REPO, ".claude", "hooks", "acceptance-map.py")
W = tempfile.mkdtemp(prefix="docs-acceptance.")
fails = total = 0


def check(cid, want, got, label):
    global fails, total
    total += 1
    ok = want == got
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'} {cid:5} {label}" + ("" if ok else f"\n      want={want!r}\n      got ={got!r}"))


def write(rel, text):
    p = os.path.join(W, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write(text)
    return p


def git(*args):
    subprocess.run(["git", "-C", W, *args], check=True, capture_output=True)


def run(script, *args, env=None):
    e = {k: v for k, v in os.environ.items() if k != "SDLC_DOCS"}
    e.update(env or {})
    p = subprocess.run([sys.executable, script, *args], capture_output=True, text=True, cwd=W, env=e)
    return p.returncode, p.stdout + p.stderr


def amap(*args):
    rc, out = run(AM, *args)
    try:
        m = json.load(open(os.path.join(W, "agent_state/accept/acceptance_map.json")))
    except (OSError, ValueError):
        m = {"frs": []}
    return rc, out, {f["fr"]: f for f in m["frs"]}, m


git("init", "-q"); git("config", "user.email", "t@t"); git("config", "user.name", "t")

# ─── docs-policy ──────────────────────────────────────────────────────────────────────────────────
check("DP-01", 1, run(DP, "is-on", "architecture_diagrams")[0], "lean default: architecture diagrams are off")
check("DP-02", 1, run(DP, "is-on", "adr_files")[0], "lean default: ADR files are off (decisions still go to DECISIONS.md)")
check("DP-03", 0, run(DP, "is-on", "worklog")[0], "lean default: the regenerated worklog stays on")
check("DP-04", 2, run(DP, "is-on", "architecture")[0], "an unknown key is a usage error (exit 2), not a silent off")
check("DP-05", 0, run(DP, "set", "adr_files", "on")[0], "set writes a per-project override")
check("DP-06", 0, run(DP, "is-on", "adr_files")[0], "the override turns ADR files on")
check("DP-07", True, os.path.isfile(os.path.join(W, "agent_state/config/docs-policy.json")), "override lives in agent_state/config/docs-policy.json")
run(DP, "set", "developer_docs", "off")
run(DP, "profile", "full")
check("DP-08", 0, run(DP, "is-on", "architecture_diagrams")[0], "profile full turns diagrams on")
check("DP-09", 1, run(DP, "is-on", "developer_docs")[0], "an explicit override beats the profile")
check("DP-10", 1, run(DP, "is-on", "architecture_diagrams", env={"SDLC_DOCS": "lean"})[0], "env SDLC_DOCS=lean wins for one run")
run(DP, "profile", "lean", "--reset")
check("DP-11", 1, run(DP, "is-on", "adr_files")[0], "profile lean --reset clears overrides")
rc, out = run(DP, "show", "--json")
try:
    shown = {r["key"] for r in json.loads(out)["optional"]}
except ValueError:
    shown = set()
check("DP-12", 9, len(shown), "show --json lists every optional key")
write("agent_state/config/docs-policy.json", "{not json")
check("DP-13", 1, run(DP, "is-on", "architecture_diagrams")[0], "an unreadable policy file falls back to lean")
os.remove(os.path.join(W, "agent_state/config/docs-policy.json"))

# Every key the framework gates on exists, and every key is gated somewhere (no dead switch).
GATED = re.compile(r"docs-policy\.py\"?\s+is-on\s+([a-z_]+)|docs_on\s+([a-z_]+)")
used = set()
for p in glob.glob(os.path.join(REPO, ".claude", "**", "*.md"), recursive=True):
    used |= {a or b for a, b in GATED.findall(open(p, encoding="utf-8").read())}
known = shown or set()
check("DP-14", [], sorted(used - known), "every key a command gates on is a real docs-policy key")
check("DP-15", [], sorted(known - used), "every docs-policy key is gated by some command or agent")

# ─── acceptance-map fixture ───────────────────────────────────────────────────────────────────────
BRD = """# BRD
## 4. Functional Requirements
| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| FR-001 | Buyers place orders | Must | requirements/orders.md |
| FR-002 | Buyers cancel orders | Must | requirements/orders.md |
| FR-003 | Admins export orders | Should | requirements/admin.md |
| FR-004 | Orders sync to ERP | Must | requirements/erp.md |
| FR-005 | Dark mode | Won't | requirements/ui.md |

### Acceptance criteria
FR-001: WHEN a Buyer submits a valid cart THE SYSTEM SHALL create an order with status "open".
  AND WHEN the order is created THE SYSTEM SHALL email the Buyer a receipt.
FR-003: WHEN an Admin requests an export THE SYSTEM SHALL produce a CSV.
  THE SYSTEM SHALL include every order of the tenant.
  THE SYSTEM SHALL exclude other tenants' orders.

## 5. Non-Functional Requirements
| ID | Category | Requirement | Target |
|----|----------|-------------|--------|
| NFR-001 | Performance | p95 order create | < 300 ms |

## 11. Traceability Matrix
| FR-001 | orders | requirements/orders.md | phase 1 | TBD |
"""
write("docs/BRD.md", BRD)
write("docs/design/phases/1/PHASE_PLAN.md", """# Phase 1
## Scope
- FR-001, FR-002, FR-003
- Deferred: FR-004 (moved to phase 2)
## Exit Criteria
- FR-004 is not needed yet
""")
write("docs/design/phases/2/PHASE_PLAN.md", "# Phase 2\n## Scope\n- FR-004\n")
SPEC = """# Orders spec
| TC ID | Category | Description | Priority | Tier |
|-------|----------|-------------|----------|------|
| TC-ACC-10101 | ACC | FR-001 SHALL 1 — Buyer: valid cart → order "open" | HIGH | acceptance |
| TC-ACC-10102 | ACC | FR-001 SHALL 2 — Buyer: receipt emailed | HIGH | acceptance |
| TC-ACC-10103 | ACC | FR-003 SHALL 1 — Admin: export produces CSV | MEDIUM | acceptance |
| TC-ACC-10104 | ACC | FR-003 SHALL 2 — Admin: export has every tenant order | MEDIUM | acceptance |
| TC-ACC-10199 | ACC | FR-099 SHALL 1 — removed requirement | HIGH | acceptance |
| TC-API-10101 | API | POST /orders → 201 | HIGH | integration |
"""
write("docs/design/phases/1/specs/orders.md", SPEC)
write("tests/acceptance/orders.spec.ts", """import { test } from '@playwright/test'
test('TC-ACC-10101 FR-001 SHALL 1 — Buyer: order open', async () => {})
test('TC-ACC-10102 FR-001 SHALL 2 — Buyer: receipt', async () => {})
test('TC-ACC-10103 FR-003 SHALL 1 — Admin: CSV', async () => {})
test.skip('TC-ACC-10104 FR-003 SHALL 2 — Admin: all orders', async () => {})
""")
git("add", "-A"); git("commit", "-qm", "fixture")

rc, out, F, M = amap("--phase", "1")
check("AM-01", "COVERED", F.get("FR-001", {}).get("status"), "FR-001: both SHALLs have named, non-skipped tests → COVERED")
check("AM-02", "NEW", F.get("FR-002", {}).get("status"), "FR-002: in scope, no TC-ACC row → NEW")
check("AM-03", "PARTIAL", F.get("FR-003", {}).get("status"), "FR-003: 3 SHALLs, rows for 2 → PARTIAL (worse than its skipped test)")
check("AM-04", True, any("UNTESTED" in i for i in F.get("FR-003", {}).get("issues", [])), "…and the skipped test is reported as UNTESTED too")
check("AM-05", False, "FR-004" in F, "--phase 1 excludes the FR the plan defers to phase 2")
check("AM-06", False, "FR-005" in F, "a Won't FR is never in scope")
check("AM-07", False, any(k.startswith("NFR") for k in F), "NFR-001 is not read as FR-001")
check("AM-08", 1, rc, "blocking gaps → exit 1")
check("AM-09", ["TC-ACC-10199"], [o["id"] for o in M.get("delta", {}).get("retire_rows", [])], "a TC-ACC row for an FR the BRD dropped is a row to retire")
check("AM-10", True, os.path.isfile(os.path.join(W, "agent_state/accept/acceptance_map.md")), "the readable map is written next to the JSON")

rc, out, F, M = amap("--phase", "2")
check("AM-11", "NEW", F.get("FR-004", {}).get("status"), "a new phase adds its FRs: --phase 2 includes FR-004 (no rows → NEW)")
check("AM-12", "COVERED", F.get("FR-001", {}).get("status"), "…and still re-proves phase 1's FRs")

rc, out, F, M = amap("--all")
check("AM-13", True, "FR-004" in F and "FR-002" in F, "--all covers every non-Won't FR in the BRD")

# results mode: a failing test makes the FR FAILING; a missing verdict is UNTESTED
write("agent_state/phases/1/reports/acceptance_report.json", json.dumps({
    "schema": "sdlc.test-results/v1", "tier": "acceptance", "verdict": "PASS", "total": 3, "failed": 0,
    "cases": [{"name": "TC-ACC-10101 …", "ids": ["TC-ACC-10101"], "verdict": "PASS", "priority": "HIGH"},
              {"name": "TC-ACC-10102 …", "ids": ["TC-ACC-10102"], "verdict": "FAIL", "priority": "HIGH"},
              {"name": "TC-ACC-10103 …", "ids": ["TC-ACC-10103"], "verdict": "PASS", "priority": "MEDIUM"}]}))
SC = "agent_state/phases/1/reports/acceptance_report.json"
rc, out, F, M = amap("--phase", "1", "--results", SC)
check("AM-14", "FAILING", F.get("FR-001", {}).get("status"), "results mode: a failed TC-ACC test → FAILING")

# merge-into: blocking FRs become UNTESTED cases the gate already blocks on; idempotent
rc, out, F, M = amap("--phase", "1", "--results", SC, "--merge-into", SC)
sc = json.load(open(os.path.join(W, SC)))
merged = [c for c in sc["cases"] if c.get("source") == "acceptance-map"]
check("AM-15", ("FAIL", 4), (sc["verdict"], len(merged)), "merge-into: 3 blocking FRs + 1 row to retire → 4 UNTESTED cases, sidecar verdict FAIL")
check("AM-16", {"HIGH", "MEDIUM"}, {c["priority"] for c in merged}, "merged cases carry the FR's MoSCoW priority (Must→HIGH, Should→MEDIUM)")
check("AM-16b", True, any("RETIRE" in c["name"] and "TC-ACC-10199" in c["name"] for c in merged), "a scoped run merges the row to retire as a blocking case")
amap("--phase", "1", "--results", SC, "--merge-into", SC)
sc = json.load(open(os.path.join(W, SC)))
check("AM-17", 4, len([c for c in sc["cases"] if c.get("source") == "acceptance-map"]), "merge-into is idempotent (re-run replaces, doesn't append)")

# record only what passed; then a requirement change is CHANGED until the spec follows it
GREEN = "agent_state/accept/green.json"
write(GREEN, json.dumps({"schema": "sdlc.test-results/v1", "cases": [
    {"name": t, "ids": [t], "verdict": "PASS"} for t in ("TC-ACC-10101", "TC-ACC-10102", "TC-ACC-10103", "TC-ACC-10104")]}))
check("AM-18", 2, run(AM, "--phase", "1", "--record")[0], "--record without --results is refused")
rc, out = run(AM, "--phase", "1", "--results", GREEN, "--record")
base = json.load(open(os.path.join(W, "agent_state/accept/fr-baseline.json")))
check("AM-19", ["FR-001"], sorted(base["frs"]), "record stores only green FRs (FR-001); NEW/PARTIAL FRs are not baselined")

write("docs/BRD.md", BRD.replace("| FR-001 | orders | requirements/orders.md | phase 1 | TBD |", "| FR-001 | orders | requirements/orders.md | phase 1 | TC-ACC-10101 |")
      .replace("| FR-001 | Buyers place orders | Must | requirements/orders.md |", "| FR-001 | Buyers place orders | Must | as-built: api/orders.go:42 |"))
rc, out, F, M = amap("--phase", "1", "--results", GREEN)
check("AM-20", "COVERED", F.get("FR-001", {}).get("status"), "editing the traceability matrix or the Source column is not a requirement change")
check("AM-21", True, F.get("FR-001", {}).get("as_built"), "an as-built Source marks the FR as-built")

CHANGED_BRD = BRD.replace('with status "open"', 'with status "pending"')
write("docs/BRD.md", CHANGED_BRD)
rc, out, F, M = amap("--phase", "1", "--results", GREEN)
check("AM-22", ("CHANGED", True), (F.get("FR-001", {}).get("status"), F.get("FR-001", {}).get("blocking")),
      "changing an acceptance criterion makes the FR CHANGED and blocking, even though its old tests pass")
rc, out = run(AM, "--phase", "1", "--results", GREEN, "--record")
check("AM-23", 1, rc, "record refuses to re-baseline a CHANGED FR whose TC-ACC rows didn't change")
check("AM-24", 2, run(AM, "--phase", "1", "--results", GREEN, "--record", "--ack", "FR-001", "ok")[0], "an ack needs a real reason (15+ chars)")
rc, out = run(AM, "--phase", "1", "--results", GREEN, "--record", "--ack", "FR-001", "status label renamed only; tests assert the new label")
rc2, out2, F, M = amap("--phase", "1", "--results", GREEN)
check("AM-25", "COVERED", F.get("FR-001", {}).get("status"), "a reasoned ack re-baselines the FR and keeps the reason")
base = json.load(open(os.path.join(W, "agent_state/accept/fr-baseline.json")))
check("AM-26", True, "ack" in base["frs"]["FR-001"], "the ack is kept in the baseline")

write("docs/BRD.md", CHANGED_BRD.replace("email the Buyer a receipt", "text the Buyer a receipt"))
rc, out, F, M = amap("--phase", "1", "--results", GREEN)
check("AM-27", "CHANGED", F.get("FR-001", {}).get("status"), "a second change is caught against the new baseline")
write("docs/design/phases/1/specs/orders.md", SPEC.replace("receipt emailed", "receipt texted"))
rc, out = run(AM, "--phase", "1", "--results", GREEN, "--record")
check("AM-28", 0, rc, "once the TC-ACC rows follow the requirement, record re-baselines without an ack")
rc, out, F, M = amap("--phase", "1", "--results", GREEN)
check("AM-29", "COVERED", F.get("FR-001", {}).get("status"), "…and the FR is COVERED again")

check("AM-30", 2, run(AM, "--brd", "docs/NOPE.md")[0], "a missing BRD is an input error (exit 2)")

# ─── requirement changes found by /recon: add, update and retire acceptance tests ─────────────────
rc, out, F, M = amap("--phase", "1")
d = M.get("delta", {})
check("AM-31", ["FR-002", "FR-003"], sorted(a["fr"] for a in d.get("add", [])), "delta.add lists the FRs that need rows + tests (NEW, PARTIAL)")
write("docs/BRD.md", CHANGED_BRD.replace("| FR-005 | Dark mode | Won't | requirements/ui.md |",
      "| FR-005 | Dark mode | Won't | requirements/ui.md |\n| FR-006 | Buyers see order history | Should | as-built: api/history.go:10 |"))
write("docs/design/phases/1/specs/amend.md", """# Amendments (recon 2026-09-30)
| TC ID | Category | Description | Priority | Tier |
|-------|----------|-------------|----------|------|
| TC-ACC-10901 | ACC | FR-006 SHALL 1 — Buyer: order history lists past orders | MEDIUM | acceptance |
| TC-ACC-10902 | ACC | FR-005 SHALL 1 — dark mode toggle | LOW | acceptance |
""")
write("tests/acceptance/stale.spec.ts", "test('TC-ACC-10777 FR-001 — an old check whose row was retired', async () => {})\n")
rc, out, F, M = amap("--phase", "1")
d = M.get("delta", {})
check("AM-32", True, "FR-006" in F, "an FR whose rows were added to a delivered phase's spec is in that phase's scope (no re-plan needed)")
check("AM-33", [1], F.get("FR-006", {}).get("phases"), "…and is owned by that phase")
check("AM-34", ["TC-ACC-10199", "TC-ACC-10902"], sorted(r["id"] for r in d.get("retire_rows", [])), "rows for a dropped FR and for a Won't FR are rows to retire")
check("AM-35", True, any("Won" in r["reason"] for r in d.get("retire_rows", [])), "…each with its reason")
check("AM-36", ["TC-ACC-10777"], [t["id"] for t in d.get("retire_tests", [])], "test code named with a TC-ACC ID no row defines is a test to delete")
check("AM-37", ["FR-001"], [u["fr"] for u in d.get("update", [])], "delta.update lists CHANGED FRs with their rows")
check("AM-37b", False, (d.get("update") or [{}])[0].get("rows_amended"), "…and says the rows haven't been rewritten yet (what /recon --apply must do)")
rc, out, F, M = amap()
check("AM-38", (False, 0), (M.get("retire_blocks"), M["summary"]["blocking"] - sum(f["blocking"] for f in F.values())),
      "an unscoped run (bare /recon) reports retire items without blocking on them")
rc, out, F, M = amap("--all")
check("AM-39", 1, rc, "--all blocks while rows/tests for removed requirements remain")
write("docs/design/phases/1/specs/orders.md", SPEC.replace("| TC-ACC-10199 | ACC | FR-099 SHALL 1 — removed requirement | HIGH | acceptance |\n", ""))
write("docs/design/phases/1/specs/amend.md", open(os.path.join(W, "docs/design/phases/1/specs/amend.md")).read()
      .replace("| TC-ACC-10902 | ACC | FR-005 SHALL 1 — dark mode toggle | LOW | acceptance |\n", ""))
os.remove(os.path.join(W, "tests/acceptance/stale.spec.ts"))
rc, out, F, M = amap("--all")
d = M.get("delta", {})
check("AM-40", (0, 0), (len(d.get("retire_rows", [])), len(d.get("retire_tests", []))), "once the rows and the test are removed, nothing is left to retire")

shutil.rmtree(W, ignore_errors=True)
print("─" * 44)
print(f"docs-and-acceptance-map: {total - fails} passed, {fails} failed")
sys.exit(1 if fails else 0)
