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
check("AM-38", (None, 0, 3), (M.get("working_phase"), M["summary"]["blocking"] - sum(f["blocking"] for f in F.values()),
                               len(M["delta"]["retire_needs_decision"])),
      "an unscoped run (bare /recon) has no working phase: it removes nothing, lists 3 for a decision, blocks on none")
rc, out, F, M = amap("--all")
check("AM-39", (0, 0, 3), (len(M["delta"]["retire_rows"]), len(M["delta"]["retire_tests"]), len(M["delta"]["retire_needs_decision"])),
      "/accept (--all, no working phase) removes nothing: the 3 candidates wait for a decision")
rc, out, F, M = amap("--all", "--working-phase", "1")
check("AM-39b", 3, len(M["delta"]["retire_rows"]) + len(M["delta"]["retire_tests"]), "--working-phase 1 may remove phase 1's own rows/tests")
write("docs/design/phases/1/specs/orders.md", SPEC.replace("| TC-ACC-10199 | ACC | FR-099 SHALL 1 — removed requirement | HIGH | acceptance |\n", ""))
write("docs/design/phases/1/specs/amend.md", open(os.path.join(W, "docs/design/phases/1/specs/amend.md")).read()
      .replace("| TC-ACC-10902 | ACC | FR-005 SHALL 1 — dark mode toggle | LOW | acceptance |\n", ""))
os.remove(os.path.join(W, "tests/acceptance/stale.spec.ts"))
rc, out, F, M = amap("--all")
d = M.get("delta", {})
check("AM-40", (0, 0, 0), (len(d.get("retire_rows", [])), len(d.get("retire_tests", [])), len(d.get("retire_needs_decision", []))),
      "once the rows and the test are removed, nothing is left to retire")

# ─── removals are limited to the phase being worked on ────────────────────────────────────────────
shutil.rmtree(W, ignore_errors=True)
W = tempfile.mkdtemp(prefix="docs-acceptance-scope.")
git("init", "-q"); git("config", "user.email", "t@t"); git("config", "user.name", "t")
write("docs/BRD.md", """# BRD
## 4. Functional Requirements
| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| FR-001 | Buyers place orders | Must | r.md |
| FR-002 | Buyers cancel orders | Must | r.md |
| FR-004 | Orders sync to ERP | Should | r.md |
""")
write("docs/design/phases/1/PHASE_PLAN.md", "# Phase 1\n## Scope\n- FR-001, FR-002\n")
PLAN2 = "# Phase 2\n## Scope\n- FR-004\n"
write("docs/design/phases/2/PHASE_PLAN.md", PLAN2)
HDR = "| TC ID | Category | Description | Priority | Tier |\n|---|---|---|---|---|\n"
P1 = (HDR + "| TC-ACC-10101 | ACC | FR-001 SHALL 1 — place | HIGH | acceptance |\n"
      "| TC-ACC-10102 | ACC | FR-002 SHALL 1 — cancel | HIGH | acceptance |\n"
      "| TC-ACC-10301 | ACC | FR-010 SHALL 1 — dropped requirement, phase 1's row | HIGH | acceptance |\n")
write("docs/design/phases/1/specs/orders.md", P1)
P2 = (HDR + "| TC-ACC-20101 | ACC | FR-004 SHALL 1 — sync | MEDIUM | acceptance |\n"
      "| TC-ACC-20102 | ACC | FR-011 SHALL 1 — dropped requirement, phase 2's own row | HIGH | acceptance |\n")
write("docs/design/phases/2/specs/erp.md", P2)
T1 = ("test('TC-ACC-10101 FR-001 SHALL 1 — place', async () => {})\n"
      "test('TC-ACC-10102 FR-002 SHALL 1 — cancel', async () => {})\n"
      "test('TC-ACC-10301 FR-010 SHALL 1 — dropped', async () => {})\n"
      "test('TC-ACC-10555 FR-001 — phase 1 test whose row is gone', async () => {})\n"
      "test('TC-ACC-014 legacy-numbered test whose row is gone', async () => {})\n")
write("tests/acceptance/p1.spec.ts", T1)
T2 = ("test('TC-ACC-20101 FR-004 SHALL 1 — sync', async () => {})\n"
      "test('TC-ACC-20102 FR-011 SHALL 1 — dropped', async () => {})\n"
      "test('TC-ACC-20555 FR-004 — phase 2 test whose row is gone', async () => {})\n")
write("tests/acceptance/p2.spec.ts", T2)
git("add", "-A"); git("commit", "-qm", "base")
BASE2 = subprocess.run(["git", "-C", W, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()

rc, out, F, M = amap("--phase", "2")
d = M["delta"]
nd = {x["id"]: x for x in d["retire_needs_decision"]}
check("SC-01", ["TC-ACC-20102"], [r["id"] for r in d["retire_rows"]], "working phase 2 may retire only its OWN row for a dropped FR")
check("SC-02", True, "TC-ACC-10301" in nd and nd["TC-ACC-10301"]["owner"] == 1, "phase 1's row for a dropped FR is left in place: needs a decision (owner 1)")
check("SC-03", ["TC-ACC-20555"], [t["id"] for t in d["retire_tests"]], "working phase 2 may delete only stale tests from its own ID block")
check("SC-04", True, "TC-ACC-10555" in nd and "TC-ACC-014" in nd, "phase 1's stale test and a legacy-numbered one are left in place")
check("SC-05", None, nd.get("TC-ACC-014", {}).get("owner", "x"), "a legacy ID has no provable owner, so it's never removed automatically")
check("SC-06", 2, M["summary"]["blocking"], "only the working phase's own 2 retire items block its gate; the other phase's don't")
write("agent_state/p2.json", json.dumps({"schema": "sdlc.test-results/v1", "verdict": "PASS", "cases": []}))
amap("--phase", "2", "--merge-into", "agent_state/p2.json")
names = " ".join(c["name"] for c in json.load(open(os.path.join(W, "agent_state/p2.json")))["cases"])
check("SC-07", (True, False, False), ("TC-ACC-20102" in names, "TC-ACC-10301" in names, "TC-ACC-10555" in names),
      "the gate's sidecar carries only the working phase's retire items")

write("docs/design/phases/2/PHASE_PLAN.md", PLAN2 + "- Retires FR-010 (replaced by FR-004)\n")
rc, out, F, M = amap("--phase", "2")
check("SC-08", True, "TC-ACC-10301" in [r["id"] for r in M["delta"]["retire_rows"]],
      "a phase-1 row becomes removable by phase 2 only when phase 2's PHASE_PLAN names its FR")
write("docs/design/phases/2/PHASE_PLAN.md", PLAN2)

# the guard: what did the working phase actually delete since it started?
write("docs/design/phases/1/specs/orders.md", P1.replace("| TC-ACC-10102 | ACC | FR-002 SHALL 1 — cancel | HIGH | acceptance |\n", ""))
write("tests/acceptance/p1.spec.ts", T1.replace("test('TC-ACC-10102 FR-002 SHALL 1 — cancel', async () => {})\n", ""))
write("docs/design/phases/2/specs/erp.md", P2.replace("| TC-ACC-20102 | ACC | FR-011 SHALL 1 — dropped requirement, phase 2's own row | HIGH | acceptance |\n", ""))
write("tests/acceptance/p2.spec.ts", T2.replace("test('TC-ACC-20102 FR-011 SHALL 1 — dropped', async () => {})\n", ""))
rc, out, F, M = amap("--phase", "2", "--diff-base", BASE2)
outside = {x["id"]: x for x in M["removed_outside_phase"]}
check("SC-09", ["TC-ACC-10102"], sorted(outside), "deleting phase 1's row + test while working on phase 2 is flagged; deleting phase 2's own is not")
check("SC-10", [1], outside.get("TC-ACC-10102", {}).get("owner"), "…with the owning phase")
check("SC-11", 1, rc, "…and it blocks the working phase's gate")
write("agent_state/p2.json", json.dumps({"schema": "sdlc.test-results/v1", "verdict": "PASS", "cases": []}))
amap("--phase", "2", "--diff-base", BASE2, "--merge-into", "agent_state/p2.json")
check("SC-12", True, any("REMOVED OUTSIDE PHASE" in c["name"] and "TC-ACC-10102" in c["name"]
                         for c in json.load(open(os.path.join(W, "agent_state/p2.json")))["cases"]),
      "the removal lands in the sidecar as a blocking case (restore it)")
write("docs/design/phases/1/specs/orders.md", P1)
write("tests/acceptance/p1.spec.ts", T1.replace("test('TC-ACC-014 legacy-numbered test whose row is gone', async () => {})\n", ""))
rc, out, F, M = amap("--phase", "2", "--diff-base", BASE2)
check("SC-13", ["TC-ACC-014"], [x["id"] for x in M["removed_outside_phase"]], "deleting a test with no provable owner is flagged too")
write("tests/acceptance/p1.spec.ts", T1.replace("test('TC-ACC-10301 FR-010 SHALL 1 — dropped', async () => {})\n", ""))
write("docs/design/phases/1/specs/orders.md", P1.replace("| TC-ACC-10301 | ACC | FR-010 SHALL 1 — dropped requirement, phase 1's row | HIGH | acceptance |\n", ""))
write("docs/design/phases/2/PHASE_PLAN.md", PLAN2 + "- Retires FR-010 (replaced by FR-004)\n")
rc, out, F, M = amap("--phase", "2", "--diff-base", BASE2)
check("SC-14", [], [x["id"] for x in M["removed_outside_phase"]], "removing a phase-1 row + test is allowed when phase 2's plan names its FR")

shutil.rmtree(W, ignore_errors=True)
print("─" * 44)
print(f"docs-and-acceptance-map: {total - fails} passed, {fails} failed")
sys.exit(1 if fails else 0)
