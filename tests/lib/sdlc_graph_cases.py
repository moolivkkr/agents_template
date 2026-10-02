#!/usr/bin/env python3
"""Tests for .claude/hooks/sdlc-graph.py on synthetic repos.

Covers: range handling (definition ranges expanded, allocation ranges not), cross-phase and in-phase
duplicate IDs, comment-only and skipped-only IDs, priority handling, malformed ID cells, results mode,
test weakening, incremental == full rebuild, output budgets, the agent-facing queries, graceful failure,
the verify-gate.sh check (h) wiring, and — the core claim — that the gate agrees with tc-inventory.py on
every ID tc-inventory sees, differing only in the documented stricter checks. Exit 0 = all pass.
"""
import json, os, shutil, subprocess, sys, tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
H = os.path.join(REPO, ".claude", "hooks")
SG = os.path.join(H, "sdlc-graph.py")
TCI = os.path.join(H, "tc-inventory.py")
J2S = os.path.join(H, "junit-to-sidecar.py")
W = tempfile.mkdtemp(prefix="sdlc-graph.")
fails = total = 0
PY = sys.executable


def check(cid, want, got, label):
    global fails, total
    total += 1
    ok = want == got
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'} {cid:5} {label}" + ("" if ok else f"\n      want={want!r}\n      got ={got!r}"))


def write(root, rel, text):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write(text)
    return p


def git(root, *args):
    return subprocess.run(["git", "-C", root, *args], check=True, capture_output=True, text=True).stdout


STRICT = dict(os.environ, SDLC_TC_GATE="strict")      # D-002: the four graph-only checks enforced for one run
WARN = {k: v for k, v in os.environ.items() if k != "SDLC_TC_GATE"}   # the default: those four are warnings


def sg(root, *args, py=PY, env=None):
    p = subprocess.run([py, SG, "--root", root, *args], capture_output=True, text=True, env=env or WARN)
    return p.returncode, p.stdout, p.stderr


def sgj(root, *args):
    rc, out, err = sg(root, "--json", "--full", *args)
    try:
        return rc, json.loads(out)
    except ValueError:
        return rc, {"_raw": out, "_err": err}


def tci(root, phase, *extra):
    out = os.path.join(W, f"tci-{os.path.basename(root)}-{phase}.json")
    p = subprocess.run([PY, TCI, "--phase", str(phase), "--root", root, "--out", out, *extra], capture_output=True, text=True)
    return p.returncode, json.load(open(out))


def gate(root, phase, *extra, env=None):
    out = os.path.join(W, f"gate-{os.path.basename(root)}-{phase}.json")
    rc, so, se = sg(root, "gate", "--phase", str(phase), "--tc-only", "--out", out, *extra, env=env)
    return rc, json.load(open(out)), so


def new_repo(name):
    root = os.path.join(W, name)
    os.makedirs(root)
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@t")
    git(root, "config", "user.name", "t")
    return root


# ═══ fixture A: every inventory loophole in one two-phase repo ═══════════════════════════════════
A = new_repo("a")
write(A, "docs/BRD.md", """# BRD
| ID | Requirement | Priority |
|----|-------------|----------|
| FR-001 | list users | Must |
| FR-002 | create orders | Must |
| FR-003 | cancel orders | Should |
""")
write(A, "docs/design/phases/1/PHASE_PLAN.md", """# Phase 1 — Users
## Scope
- FR-001
## E2E Workflows Unlocked
- list-users: an admin lists users (FR-001)
""")
write(A, "docs/design/phases/1/specs/users.md", """# Users (FR-001)
## Test Coverage Required
| TC ID | Description | Priority |
|---|---|---|
| TC-API-001 | list users | HIGH |
| TC-API-102 | reused by phase 2 | HIGH |
""")
write(A, "docs/design/phases/2/PHASE_PLAN.md", """# Phase 2 — Orders
## Scope
- FR-002, FR-003
## E2E Workflows Unlocked
- name: "checkout"
  description: "buyer checks out"
  triggers: [FR-002]
  steps:
    1. add to cart → cart shows the item
""")
write(A, "docs/design/phases/2/specs/orders.md", """# Orders (FR-002)
TC-API-101 to TC-API-103 — order endpoint tests (a range line in prose: grouping, not IDs)

### Test Case Inventory (TC-API-101 .. TC-API-150 — range owned by this spec)

| TC ID | Category | Test Description | Priority | Tier |
|-------|----------|------------------|----------|------|
| TC-API-101 | API | POST /api/orders creates an order | HIGH | integration |
| TC-API-102 | API | rejects a bad order | MEDIUM | integration |
| TC-API-103 | API | cosmetic message | LOW | unit |
| TC-UI-101 | UI | renders the order form | HIGH | component |
| TC-E2E-101 | E2E | checkout end to end | HIGH | e2e |
| TC-UNIT-201 | UNIT | critical maps to MEDIUM | Critical | unit |
| TC-UNIT-202 | UNIT | bold priority | **HIGH** | unit |
| TC-UNIT-203 | UNIT | low and untested | LOW | unit |
| TC-DUP-001 | UNIT | first inventory row | HIGH | unit |
| TC-DUP-001 | UNIT | second inventory row, same phase | HIGH | unit |
| TC-VAL-001 – TC-VAL-003 | VAL | quantity validation | MEDIUM | unit |
| TC-SEC-REG-001 | SEC | malformed: inner hyphen, invisible to tc-inventory | HIGH | integration |

TC-RNG-001 – TC-RNG-002 — cancel edge cases (MEDIUM, unit)

## Acceptance Criteria
- WHEN a buyer cancels THE SYSTEM SHALL refund (→ TC-UNIT-202) — FR-003

### Deferred
- TC-LATER-001 moves to phase 3
""")
write(A, "docs/design/phases/2/specs/data-contracts.md", """// GET /api/orders
interface Order { id: string }
type ListOrdersResponse = { data: Order[] }
// POST /api/orders
""")
write(A, "api/orders.go", '''package api

type Handler struct{}

func (h *Handler) ListOrders() {}
func (h *Handler) CreateOrder() { query("SELECT id FROM orders") }
func Routes(r Router) {
	r.GET("/api/orders", h.ListOrders)
	r.POST("/api/orders", h.CreateOrder)
}
''')
write(A, "api/orders_test.go", '''package api
import "testing"
// TC-API-102: only mentioned in a comment (TODO write this)
// covers TC-API-104 to TC-API-106
func TestCreateOrder(t *testing.T) {
    t.Run("TC-API-101 creates an order", func(t *testing.T) { if 1 != 1 { t.Fatal("x") } })
    t.Run("TC-VAL-001 quantity zero", func(t *testing.T) {})
    t.Run("TC-UNIT-201 critical", func(t *testing.T) {})
}
func TestLater(t *testing.T) {
    t.Skip("not yet")
    t.Run("TC-UI-101 renders", func(t *testing.T) {})
}
''')
write(A, "web/orders.test.ts", '''describe.skip('order form', () => {
  it('TC-UI-101 renders the form', () => { expect(1).toBe(1) })
})
test('TC-E2E-101 checkout end to end', async () => { expect(true).toBe(true) })
test('TC-DUP-001 dup', () => { expect(1).toBe(1) })
''')
write(A, "tests/test_orders.py", '''import pytest
@pytest.mark.parametrize(
    "msg",
    ["a"],
    ids=["TC-API-103"])
def test_message(msg):
    assert msg
''')
write(A, "migrations/001_orders.sql", "CREATE TABLE orders (id uuid primary key);\n")
git(A, "add", "-A")
git(A, "commit", "-qm", "base")
BASE_A = git(A, "rev-parse", "HEAD").strip()

rc, out, err = sg(A, "build")
check("B01", 0, rc, "full build succeeds on fixture A")
rc, st = sgj(A, "stats")
check("B02", True, st.get("nodes", {}).get("tc", 0) >= 15 and st.get("nodes", {}).get("test", 0) >= 6, "graph holds TC rows and test cases")
check("B03", True, os.path.isfile(os.path.join(A, "agent_state", "graph", "graph.jsonl")) and
      os.path.isfile(os.path.join(A, "agent_state", "graph", ".gitignore")), "graph.jsonl export + .gitignore written")

# ─── ranges, priority, malformed (graph side) ────────────────────────────────────────────────────
rc, tc2 = sgj(A, "tc", "--phase", "2")
rows = {r["tc"]: r for r in tc2["rows"]}
check("R01", ["TC-VAL-001", "TC-VAL-002", "TC-VAL-003"], sorted(k for k in rows if k.startswith("TC-VAL")),
      "a range in an ID cell is expanded into one required ID each")
check("R02", ["TC-RNG-001", "TC-RNG-002"], sorted(k for k in rows if k.startswith("TC-RNG")),
      "a prose line that starts with a range and carries a priority is expanded")
check("R03", False, any(k.startswith("TC-API-1") and int(k.split("-")[2]) > 103 for k in rows),
      "an allocation range ('range owned by this spec', heading) is NOT expanded")
check("R04", {"TC-VAL-002": "MEDIUM"}, {"TC-VAL-002": rows.get("TC-VAL-002", {}).get("priority")},
      "expanded range IDs take the row's priority")
check("P01", ("MEDIUM", "HIGH", "LOW"), (rows["TC-UNIT-201"]["priority"], rows["TC-UNIT-202"]["priority"], rows["TC-UNIT-203"]["priority"]),
      "priority: unknown value → MEDIUM (blocking), **HIGH** → HIGH, LOW stays LOW")
check("M01", True, any("TC-SEC-REG-001" in m for m in tc2["problems"]["malformed_ids"]), "malformed ID cell is reported")

# ─── agreement with tc-inventory.py ─────────────────────────────────────────────────────────────
import importlib.util
sys.dont_write_bytecode = True
_s = importlib.util.spec_from_file_location("sg", SG)
sgm = importlib.util.module_from_spec(_s)
_s.loader.exec_module(sgm)


def compare(root, phase, results=None, diff_base=None):
    """(tc-inventory json, graph inventory) for the same inputs; graph in tc-inventory's own mode."""
    extra = []
    if results:
        extra += ["--results", *results]
    if diff_base:
        extra += ["--diff-base", diff_base]
    _, t = tci(root, phase, *extra)
    g = sgm.Graph(root)
    g.build(incremental=True)
    gi = sgm.tc_inventory(g, phase, results=results, diff_base=diff_base)
    return t, gi


def agreement(cid, root, phase, results=None, diff_base=None, expect_extra=()):
    t, gi = compare(root, phase, results, diff_base)
    tv = {c["name"]: (c["verdict"], c["priority"], c["tier"]) for c in t["cases"]}
    gv = {c["name"]: (c["verdict"], c["priority"], c["tier"]) for c in gi["cases"]}
    common = {k: gv.get(k) for k in tv}
    check(cid + "a", tv, common, f"phase {phase}{' results' if results else ''}: every tc-inventory ID has the same verdict/priority/tier in the graph")
    lists = ["missing", "failing", "comment_only", "skipped_only", "range_annotations"]
    tl = {k: sorted(t[k]) for k in lists}
    gl = {k: sorted(x for x in gi[k] if x in tv or k == "range_annotations") for k in lists}
    check(cid + "b", tl, gl, f"phase {phase}: missing/failing/comment-only/skipped-only/range lists agree (restricted to tc-inventory's IDs)")
    check(cid + "c", (sorted(t["duplicate_ids"]), sorted(t["duplicate_in_phase"])),
          (sorted(k for k in gi["duplicate_ids"] if k in tv), sorted(gi["duplicate_in_phase"])), f"phase {phase}: duplicate IDs agree")
    check(cid + "d", sorted(expect_extra), sorted(set(gv) - set(tv)), f"phase {phase}: the graph's extra IDs are exactly the expanded definition ranges")
    check(cid + "e", sorted(w["kind"] + w["file"] for w in t["weakening_unacknowledged"]),
          sorted(w["kind"] + w["file"] for w in gi["weakening_unacknowledged"]), f"phase {phase}: unacknowledged test weakening agrees")
    strict = gi["verdict"] != "PASS" or t["verdict"] == "PASS"
    check(cid + "f", True, strict, f"phase {phase}: the graph never PASSes what tc-inventory FAILs (graph {gi['verdict']}, tci {t['verdict']})")
    return t, gi


t1, g1 = agreement("A1", A, 1)
t2, g2 = agreement("A2", A, 2, expect_extra=["TC-VAL-001", "TC-VAL-002", "TC-VAL-003", "TC-RNG-001", "TC-RNG-002"])
check("X01", {"TC-API-102": ["1"]}, {k: v for k, v in g2["duplicate_ids"].items() if k == "TC-API-102"}, "cross-phase ID flagged (phase-blind grep would count it covered)")
check("X02", ["TC-DUP-001"], sorted(g2["duplicate_in_phase"]), "two inventory rows for one ID in a phase are flagged")
check("X03", True, "TC-API-102" in g2["comment_only"] and "TC-API-102" in g2["missing"], "comment-only annotation covers nothing")
check("X04", True, "TC-UI-101" in g2["skipped_only"], "an ID only in skipped tests (t.Skip, describe.skip) is skipped-only")
check("X05", 1, len(g2["range_annotations"]), "a range annotation in a test file is flagged")
check("X06", False, "TC-API-103" in g2["missing"] or "TC-UNIT-203" in g2["missing"], "LOW rows never block")
check("X07", True, "TC-UNIT-201" not in g2["missing"], "an unknown priority is MEDIUM: blocking, and here covered by a named test")

# results mode: a sidecar where TC-API-101 FAILED and TC-API-103 PASSED
os.makedirs(os.path.join(A, "agent_state", "phases", "2", "reports"), exist_ok=True)
write(A, "agent_state/junit/unit.xml", '''<testsuites><testsuite name="api">
 <testcase classname="api" name="TestCreateOrder/TC-API-101 creates an order"><failure message="boom"/></testcase>
 <testcase classname="api" name="TestMessage[TC-API-103]"/>
 <testcase classname="api" name="TestCreateOrder/TC-VAL-001 quantity zero"/>
</testsuite></testsuites>''')
SC = os.path.join(A, "agent_state", "phases", "2", "reports", "unit_tests.json")
subprocess.run([PY, J2S, "--tier", "unit", "--out", SC, "--exit-code", "1", "--root", A, os.path.join(A, "agent_state/junit/unit.xml")], capture_output=True)
t2r, g2r = agreement("A3", A, 2, results=[SC], expect_extra=["TC-VAL-001", "TC-VAL-002", "TC-VAL-003", "TC-RNG-001", "TC-RNG-002"])
check("A3g", (["TC-API-101"], "PASS"), (g2r["failing"], {c["name"]: c["verdict"] for c in g2r["cases"]}["TC-API-103"]),
      "results mode: a FAILED named test fails its ID; a PASSED one covers it")

# weakening since base: a new skip and a .only
write(A, "web/orders.test.ts", open(os.path.join(A, "web/orders.test.ts")).read().replace("test('TC-E2E-101", "test.only('TC-E2E-101"))
write(A, "api/orders_test.go", open(os.path.join(A, "api/orders_test.go")).read().replace(
    "func TestCreateOrder(t *testing.T) {", "func TestCreateOrder(t *testing.T) {\n    t.Skip(\"flaky\")"))
t2w, g2w = agreement("A4", A, 2, diff_base=BASE_A, expect_extra=["TC-VAL-001", "TC-VAL-002", "TC-VAL-003", "TC-RNG-001", "TC-RNG-002"])
check("A4g", True, len(g2w["weakening_unacknowledged"]) >= 2, "added skip + .only since the base are unacknowledged weakening")
git(A, "checkout", "--", "web/orders.test.ts", "api/orders_test.go")
# the agreement runs above use the default policy (warn); the same inputs under strict only add blockers
_ga = sgm.Graph(A)
_ga.build(incremental=True)
_wv = sgm.tc_inventory(_ga, 2, results=[SC], policy={"strict": set(), "source": "t", "error": None})
_sv = sgm.tc_inventory(_ga, 2, results=[SC], policy={"strict": set(sgm.TC_GATE_CHECKS), "source": "t", "error": None})
check("A5", (True, True, True), (set(_wv["missing"]) <= set(_sv["missing"]), _sv["failed"] > _wv["failed"],
                                 {c["name"]: c["verdict"] for c in _wv["cases"]} == {c["name"]: c["verdict"] for c in _sv["cases"]}),
      "strict ⊇ warn: same verdict per ID, strict only adds blockers (missing range IDs, malformed)")

# ─── the gate: strict superset (policy strict: the four D-002 checks enforced) ────────────────────────
rc, gj, so = gate(A, 2, env=STRICT)
check("G01", 1, rc, "gate FAILs fixture A phase 2")
gb = "\n".join(so.splitlines())
check("G02", True, "no runner results" not in gb, "with sidecars in reports/ the gate runs in results mode")
check("G03", True, "no base commit" in gb, "gate BLOCKs when agent_state/phases/N/base_sha is missing")
check("G04", True, "malformed TC ID" in gb and "TC-SEC-REG-001" in gb, "gate BLOCKs on a malformed ID cell")
check("G05", True, "TC-VAL-002" in gb and "defined by a range" in gb, "gate BLOCKs on an uncovered range-defined ID and says so")
gb = "\n".join(l for l in so.splitlines() if l.startswith("BLOCKING: "))
check("G03b", (True, True, True, []), ("no base commit" in gb, "malformed TC ID" in gb, "TC-VAL-002" in gb, gj["warnings"]),
      "strict: base_sha, malformed and range findings are BLOCKING lines, and nothing is a warning")
rc, gj1, so1 = gate(A, 1, env=STRICT)
check("G06", True, "BLOCKING: TC: no runner results" in so1, "strict: gate BLOCKs a phase with no runner sidecar (coverage nobody ran)")
# default policy (no gate-policy.json): the same four findings are WARNINGS; everything else still blocks
rc, gw, sow = gate(A, 2)
bl = [l for l in sow.splitlines() if l.startswith("BLOCKING: ")]
wl = [l for l in sow.splitlines() if l.startswith("WARNING: ")]
check("G08", (1, ["base_sha_required", "malformed_ids", "range_ids"]), (rc, sorted(w["check"] for w in gw["warnings"])),
      "warn (default): fixture A phase 2 still FAILs; base_sha/malformed/range findings are warnings")
check("G09", (False, False, False), (any("malformed" in l for l in bl), any("defined by a range" in l for l in bl), any("no base commit" in l for l in bl)),
      "warn: no BLOCKING line for the four D-002 findings")
check("G10", (True, True, True), (any("TC-SEC-REG-001" in l and "[malformed_ids]" in l for l in wl),
                                  any("TC-VAL-002" in l and "[range_ids]" in l for l in wl), any("[base_sha_required]" in l for l in wl)),
      "warn: each finding is a WARNING: line with the example and its fix")
check("G11", (True, True, True, True, True),
      (any("TC-API-101 failing" in l for l in bl), any("TC-API-102 is also defined by phase(s) 1" in l for l in bl),
       any("TC-DUP-001 has 2 inventory rows" in l for l in bl), any("range annotation in a test" in l for l in bl),
       any("TC-API-102 (MEDIUM" in l and "only a comment" in l for l in bl)),
      "warn: failing, cross-phase dup, in-phase dup, range annotation and comment-only still BLOCK")
check("G12", (gw["warning_count"], "D-002", ["base_sha_required", "malformed_ids", "range_ids", "results_required"]),
      (sum(w["count"] for w in gw["warnings"]), gw["policy"]["decision"], gw["policy"]["warn_checks"]),
      "warn: the sidecar carries warning_count, per-check warnings and the policy in force")
rc, gw1, so1 = gate(A, 1)
check("G13", (True, False), ("WARNING: TC: [results_required]" in so1, "BLOCKING: TC: no runner results" in so1),
      "warn: no runner sidecar is a warning (source mode, like tc-inventory without --results)")
check("G07", True, os.path.isfile(os.path.join(A, "agent_state", "graph", "summary-phase-2.json")), "gate writes summary-phase-N.json")

# ═══ fixture B: a clean phase — gate PASSes, and so does tc-inventory ══════════════════════════════
B = new_repo("b")
write(B, "docs/design/phases/1/specs/orders.md", """# Orders (FR-001)
## Test Coverage Required
| TC ID | Category | Description | Priority | Tier |
|---|---|---|---|---|
| TC-API-10101 | API | create order | HIGH | integration |
| TC-API-10102 | API | reject bad order | MEDIUM | unit |
| TC-UI-10101 | UI | cosmetic | LOW | component |
""")
write(B, "src/orders.go", "package src\nfunc Create() int { return 1 }\n")
write(B, "src/orders_test.go", 'package src\nimport "testing"\nfunc TestOrders(t *testing.T) {\n  t.Run("TC-API-10101 create order", func(t *testing.T) {})\n  t.Run("TC-API-10102 reject bad order", func(t *testing.T) {})\n}\n')
git(B, "add", "-A")
git(B, "commit", "-qm", "phase 1")
P1 = os.path.join(B, "agent_state", "phases", "1")
os.makedirs(os.path.join(P1, "reports"))
open(os.path.join(P1, "base_sha"), "w").write(git(B, "rev-parse", "HEAD").strip() + "\n")
write(B, "agent_state/phases/1/junit/unit.xml", '<testsuite><testcase classname="src" name="TestOrders/TC-API-10101 create order"/>'
      '<testcase classname="src" name="TestOrders/TC-API-10102 reject bad order"/></testsuite>')
subprocess.run([PY, J2S, "--tier", "unit", "--exit-code", "0", "--root", B, "--out", os.path.join(P1, "reports", "test_results.json"),
                os.path.join(P1, "junit", "unit.xml")], capture_output=True)
rc, gjb, sob = gate(B, 1)
_, tb = tci(B, 1, "--results", os.path.join(P1, "reports", "test_results.json"), "--diff-base", open(os.path.join(P1, "base_sha")).read().strip())
check("C01", (0, "PASS", "PASS"), (rc, gjb["verdict"], tb["verdict"]), "clean phase: graph gate and tc-inventory both PASS (results mode)")
check("C02", (2, 2), (gjb["passed"], gjb["total"]), "2/2 HIGH+MEDIUM covered; LOW not counted")

# ═══ D-002 warn-first policy: each new finding alone, each pre-existing blocker alone ════════════════
# Every variant is a copy of the clean fixture B with ONE change. The four graph-only findings must WARN and
# PASS by default and BLOCK under strict; every finding tc-inventory.py fails on must BLOCK in BOTH modes,
# and tc-inventory must agree it fails (so warn mode never passes what tc-inventory fails).
B_SPEC = "docs/design/phases/1/specs/orders.md"
B_TEST = "src/orders_test.go"
B_RES = "agent_state/phases/1/reports/test_results.json"


def variant(name, mutate):
    root = os.path.join(W, "v-" + name)
    shutil.copytree(B, root, symlinks=True)
    mutate(root)
    return root


def edit(root, rel, fn):
    p = os.path.join(root, rel)
    text = fn(open(p).read())
    open(p, "w").write(text)


def tci_full(root):
    extra = []
    if os.path.exists(os.path.join(root, B_RES)):
        extra += ["--results", os.path.join(root, B_RES)]
    bp = os.path.join(root, "agent_state/phases/1/base_sha")
    if os.path.exists(bp):
        extra += ["--diff-base", open(bp).read().strip()]
    return tci(root, 1, *extra)


def sidecar(root, cases_xml, rc="0"):
    write(root, "agent_state/phases/1/junit/unit.xml", f"<testsuite>{cases_xml}</testsuite>")
    subprocess.run([PY, J2S, "--tier", "unit", "--exit-code", rc, "--root", root, "--out", os.path.join(root, B_RES),
                    os.path.join(root, "agent_state/phases/1/junit/unit.xml")], capture_output=True)


OK_XML = ('<testcase classname="src" name="TestOrders/TC-API-10101 create order"/>'
          '<testcase classname="src" name="TestOrders/TC-API-10102 reject bad order"/>')
NEW = {   # check → mutation that produces exactly that finding on the clean fixture
    "malformed_ids": lambda r: edit(r, B_SPEC, lambda t: t + "| TC-SEC-012a | SEC | suffix letter | HIGH | integration |\n"
                                                          "| TC-E2E-ING-001 | E2E | inner hyphen | HIGH | e2e |\n"),
    "range_ids": lambda r: edit(r, B_SPEC, lambda t: t + "| TC-VAL-10101 – TC-VAL-10103 | VAL | validation | MEDIUM | unit |\n"),
    "results_required": lambda r: os.remove(os.path.join(r, B_RES)),
    "base_sha_required": lambda r: os.remove(os.path.join(r, "agent_state/phases/1/base_sha")),
}
for k, (chk, mut) in enumerate(NEW.items(), 1):
    root = variant(chk, mut)
    rcw, gw_, sow_ = gate(root, 1)
    rcs, gs_, sos_ = gate(root, 1, env=STRICT)
    _, tv = tci_full(root)
    check(f"D{k:02}a", (0, "PASS", [chk]), (rcw, gw_["verdict"], [w["check"] for w in gw_["warnings"]]),
          f"warn (default): {chk} alone → WARNING, gate PASSes (tc-inventory: {tv['verdict']})")
    check(f"D{k:02}b", (True, False), (f"WARNING: TC: [{chk}]" in sow_, any(l.startswith("BLOCKING: ") for l in sow_.splitlines())),
          f"warn: {chk} is printed as a WARNING: line, no BLOCKING: line")
    check(f"D{k:02}c", (1, "FAIL", []), (rcs, gs_["verdict"], gs_["warnings"]), f"strict: {chk} alone BLOCKs")
    if chk != "results_required":       # tc-inventory, without --results, is in source mode: the named tests pass it
        check(f"D{k:02}d", "PASS", tv["verdict"], f"{chk} is a graph-only finding: tc-inventory PASSes this variant")
gw_ = gate(variant("malformed-count", NEW["malformed_ids"]), 1)[1]
check("D05", (2, ["TC-E2E-ING-001", "TC-SEC-012a"]), (gw_["warning_count"], sorted(x.split(": ")[1] for x in gw_["warnings"][0]["items"])),
      "warn: TC-SEC-012a and TC-E2E-ING-001 (the real-project shapes) are counted, each listed")

OLD = {   # pre-existing tc-inventory blockers → mutation; each must BLOCK in warn mode too
    "missing HIGH ID": lambda r: edit(r, B_SPEC, lambda t: t + "| TC-API-10109 | API | never tested | HIGH | integration |\n"),
    "failed test": lambda r: sidecar(r, '<testcase classname="src" name="TestOrders/TC-API-10101 create order"><failure message="x"/></testcase>'
                                        '<testcase classname="src" name="TestOrders/TC-API-10102 reject bad order"/>', "1"),
    "comment-only": lambda r: (edit(r, B_SPEC, lambda t: t + "| TC-API-10110 | API | only a comment | HIGH | unit |\n"),
                               edit(r, B_TEST, lambda t: t + "// TC-API-10110 TODO\n")),
    "duplicate cross-phase": lambda r: write(r, "docs/design/phases/2/specs/x.md",
                                             "| TC ID | Description | Priority |\n|---|---|---|\n| TC-API-10101 | again | HIGH |\n"),
    "duplicate in-phase": lambda r: edit(r, B_SPEC, lambda t: t + "| TC-API-10101 | API | twice | HIGH | integration |\n"),
    "range annotation in a test": lambda r: edit(r, B_TEST, lambda t: t + "// covers TC-API-10101 to TC-API-10102\n"),
    "unacknowledged weakening": lambda r: edit(r, B_TEST, lambda t: t.replace("func TestOrders(t *testing.T) {",
                                                                               "func TestOrders(t *testing.T) {\n  t.Skip(\"later\")")),
}
for k, (what, mut) in enumerate(OLD.items(), 1):
    root = variant("old-" + str(k), mut)
    rcw, gw_, sow_ = gate(root, 1)
    _, tv = tci_full(root)
    check(f"E{k:02}", (1, "FAIL", True, "FAIL"), (rcw, gw_["verdict"], any(l.startswith("BLOCKING: ") for l in sow_.splitlines()), tv["verdict"]),
          f"warn (default): pre-existing blocker '{what}' still BLOCKs, and tc-inventory fails it too")
root = variant("old-results-err", lambda r: None)
open(os.path.join(root, "bad.json"), "w").write("{not json")
rc, gw_, sow_ = gate(root, 1, "--results", os.path.join(root, "bad.json"))
check("E08", (1, True), (rc, "unreadable results sidecar" in sow_), "warn: an unreadable --results sidecar still BLOCKs (tc-inventory exits on it)")
root = variant("old-norows", lambda r: write(r, B_SPEC, "# Orders\n| TC ID | Priority |\n|---|---|\n| TC-A-1 – TC-A-3 | HIGH |\n"))
rc, gw_, sow_ = gate(root, 1)
check("E09", (1, "BLOCKED"), (rc, gw_["verdict"]), "warn: a phase whose only TC rows are a range is BLOCKED (tc-inventory sees no rows)")
root = variant("range-dup", lambda r: write(r, "docs/design/phases/2/specs/x.md",
                                            "| TC ID | Description | Priority |\n|---|---|---|\n| TC-API-10101 – TC-API-10102 | range | HIGH |\n"))
rc, gw_, _ = gate(root, 1)
rcs, gs_, _ = gate(root, 1, env=STRICT)
check("E10", (0, ["range_ids"], 1, ["TC-API-10101", "TC-API-10102"]), (rc, [w["check"] for w in gw_["warnings"]], rcs, sorted(gs_["duplicate_ids"])),
      "a cross-phase duplicate that exists only through another phase's range: warning by default, BLOCKING when strict")
root = variant("range-fail", lambda r: (NEW["range_ids"](r), sidecar(r, OK_XML + '<testcase classname="src" name="TestV/TC-VAL-10102 v">'
                                                                         '<failure message="x"/></testcase>', "1")))
rc, gw_, sow_ = gate(root, 1)
check("E11", (1, True), (rc, "BLOCKING: TC: TC-VAL-10102 failing" in sow_), "warn: a range-defined ID whose test RAN and FAILED still BLOCKs")

# ─── policy: file, per-check granularity, env override, broken file, commands ──────────────────────────
root = variant("policy", lambda r: (NEW["malformed_ids"](r), NEW["range_ids"](r)))
rc, out, _ = sg(root, "policy", "--strict-check", "malformed_ids")
pol = json.load(open(os.path.join(root, "agent_state/config/gate-policy.json")))
check("PO01", (0, {"strict": False, "strict_checks": ["malformed_ids"]}), (rc, pol["tc_gate"]), "policy --strict-check writes gate-policy.json")
rc, gp_, sop = gate(root, 1)
check("PO02", (1, ["range_ids"], True), (rc, [w["check"] for w in gp_["warnings"]], "BLOCKING: TC: malformed TC ID" in sop),
      "one check enforced: malformed IDs BLOCK, range IDs stay a warning")
rc, gp_, _ = gate(root, 1, env=dict(WARN, SDLC_TC_GATE="warn"))
check("PO03", (0, 2), (rc, len(gp_["warnings"])), "env SDLC_TC_GATE=warn overrides the file for one run")
sg(root, "policy", "--strict")
rc, gp_, _ = gate(root, 1)
check("PO04", (1, [], ["base_sha_required", "malformed_ids", "range_ids", "results_required"]),
      (rc, gp_["warnings"], gp_["policy"]["strict_checks"]), "policy --strict: every check enforced, no warnings")
rc, out, _ = sg(root, "policy", "--warn-check", "range_ids")
check("PO05", ["base_sha_required", "malformed_ids", "results_required"],
      json.load(open(os.path.join(root, "agent_state/config/gate-policy.json")))["tc_gate"]["strict_checks"], "policy --warn-check relaxes one check")
sg(root, "policy", "--warn")
rc, gp_, _ = gate(root, 1)
check("PO06", (0, 2), (rc, len(gp_["warnings"])), "policy --warn: back to warnings")
write(root, "agent_state/config/gate-policy.json", "{broken")
rc, gp_, sop = gate(root, 1)
check("PO07", (1, True, True), (rc, "gate policy:" in sop and "unreadable" in sop, "BLOCKING: TC: malformed TC ID" in sop),
      "an unreadable gate-policy.json BLOCKs and enforces every check (someone meant to tighten)")
write(root, "agent_state/config/gate-policy.json", '{"tc_gate": {"strict_checks": ["malformed"]}}')
rc, gp_, sop = gate(root, 1)
check("PO08", (1, True), (rc, "unknown check(s) malformed" in sop), "a typo'd check name BLOCKs with the known names")
os.remove(os.path.join(root, "agent_state/config/gate-policy.json"))
rc, sh = sgj(root, "policy")
check("PO09", (0, "WARN"), (rc, sh["checks"]["malformed_ids"][:4]), "policy (show): defaults to WARN with no file")
rc, wn = sgj(root, "warnings")
p1 = next(p for p in wn["phases"] if p["phase"] == 1)
check("PO10", (0, {"malformed_ids": 2, "range_ids": 3}, False, 5), (rc, p1["warnings"], p1["ready_for_strict"], wn["total_warnings"]),
      "warnings: per-phase counts by check + ready_for_strict (the alignment tracker)")
rc, out, _ = sg(B, "warnings", "--phase", "1")
check("PO11", (0, True), (rc, "ready_for_strict: true" in out or '"ready_for_strict":true' in out), "warnings: a clean phase is ready for strict")
rc, out, _ = sg(root, "gate", "--phase", "1", "--summary")
check("PO12", True, "WARNING: TC: [malformed_ids]" in out and "warnings 5" in out, "gate --summary surfaces the warnings and their count")
rc, tcj = sgj(root, "tc", "--phase", "1")
check("PO13", True, any("[range_ids]" in w for w in tcj["warnings"]), "tc (query) surfaces the warnings too")

# ─── incremental == full ───────────────────────────────────────────────────────────────────────────
def jsonl(root, gd):
    return open(os.path.join(gd, "graph.jsonl")).read()


GD_INC = os.path.join(W, "inc")
sg(A, "--graph-dir", GD_INC, "build")
# edit a spec, add a test, delete a file, rename a file, change agent_state
write(A, "docs/design/phases/2/specs/orders.md", open(os.path.join(A, "docs/design/phases/2/specs/orders.md")).read().replace("cosmetic message", "cosmetic text"))
write(A, "web/new.test.ts", "test('TC-UI-101 renders', () => {})\n")
os.remove(os.path.join(A, "migrations/001_orders.sql"))
os.rename(os.path.join(A, "tests/test_orders.py"), os.path.join(A, "tests/test_orders2.py"))
write(A, "agent_state/phases/2/roster.json", '{"phase":2,"required":["unit_test_agent"]}')
git(A, "add", "-A")
git(A, "commit", "-qm", "edit")
rc, out, _ = sg(A, "--graph-dir", GD_INC, "build", "--incremental")
inc_stats = json.loads(out)
GD_FULL = os.path.join(W, "full")
sg(A, "--graph-dir", GD_FULL, "build")
check("I01", True, inc_stats["mode"] == "incremental" and 0 < inc_stats["reindexed"] <= 6 and inc_stats["removed"] == 2,
      f"incremental re-indexes only changed files ({inc_stats['reindexed']} re-indexed, {inc_stats['removed']} removed)")
check("I02", jsonl(A, GD_FULL), jsonl(A, GD_INC), "incremental build == full rebuild (graph.jsonl byte-identical)")
write(A, "api/extra.go", "package api\nfunc Extra() {}\n")       # untracked, uncommitted file
rc, out, _ = sg(A, "--graph-dir", GD_INC, "build", "--incremental")
sg(A, "--graph-dir", GD_FULL, "build")
check("I03", jsonl(A, GD_FULL), jsonl(A, GD_INC), "an untracked working-tree file is picked up incrementally too")
rc, out, _ = sg(A, "--graph-dir", GD_INC, "build", "--incremental")
check("I04", 0, json.loads(out)["reindexed"], "no change → nothing re-indexed")

# ─── budgets ───────────────────────────────────────────────────────────────────────────────────────
rc, out, _ = sg(A, "tc", "--phase", "2", "--max-tokens", "100")
check("O01", True, len(out) <= 100 * 4 + 40, f"--max-tokens 100 caps output ({len(out)} chars)")
check("O02", True, "more" in out or "truncated" in out, "a capped answer says it was capped")
rc, j = sgj(A, "tc", "--phase", "2")
rc, out, _ = sg(A, "--json", "tc", "--phase", "2", "--limit", "2")
check("O03", True, len(json.loads(out)["rows"]) <= 3, "--limit caps rows per list (2 + a '+N more' marker)")
rc, out, _ = sg(A, "context", "--agent", "unit_test_agent", "--phase", "2", "--max-tokens", "300")
check("O04", True, len(out) <= 300 * 4 + 40, "options after the subcommand work and cap context")

# ─── agent-facing queries ────────────────────────────────────────────────────────────────────────
rc, ctx = sgj(A, "context", "--agent", "unit_test_agent", "--phase", "2")
todo = ctx.get("todo (id priority tier spec-row [status])", [])
check("Q01", True, bool(todo) and all(" unit " in t or " ? " in t for t in todo), "context: unit_test_agent gets only unit-tier rows")
check("Q02", True, all(s["where"].startswith("docs/design/phases/2/specs/") for s in ctx["spec_sections_to_read"]) and bool(ctx["spec_sections_to_read"]),
      "context: spec sections to read are file:start-end slices of this phase's specs")
rc, ctx_i = sgj(A, "context", "--agent", "integration_test_agent", "--phase", "2")
check("Q03", True, any(e["endpoint"] == "POST /api/orders" and e["handlers"] for e in ctx_i["endpoints"]),
      "context: integration agent sees the phase's endpoints with their handler spans")
rc, un = sgj(A, "unlocked", "--phase", "2")
check("Q04", (["checkout"], ["list-users"]), ([w["id"] for w in un["this_phase"]], [w["id"] for w in un["regression"]]),
      "unlocked: this phase's E2E workflows + earlier phases' as regression (C3 producer)")
check("Q05", ["TC-E2E-101"], [r["tc"] for r in un["e2e_tc_rows"]], "unlocked: the phase's TC-E2E rows")
check("Q05b", (["FR-002"], "buyer checks out"), (un["this_phase"][0]["frs"], un["this_phase"][0]["text"]),
      "unlocked: project_planner's `- name:` / description / triggers entry is parsed")
rc, tr = sgj(A, "trace", "FR-002")
check("Q06", True, tr["phases"] == ["2"] and any(t["tc"] == "TC-API-101" for t in tr["tc"]), "trace FR: phase + TC rows via the spec section")
rc, tr = sgj(A, "trace", "TC-API-102")
check("Q07", [1, 2], sorted(d["phase"] for d in tr["defined_in"]), "trace TC: every phase defining it")
rc, cons = sgj(A, "consumers", "GET /api/orders")
check("Q08", True, bool(cons["handlers"]) and cons["handlers"][0]["handler"].endswith("#Handler.ListOrders") and bool(cons["declared_in"]),
      "consumers endpoint: declaring contract + handler symbol")
rc, cons = sgj(A, "consumers", "table:orders")
check("Q09", True, any("CreateOrder" in r for r in cons["readers"]), "consumers table: reader symbols")
rc, orph = sgj(A, "orphans", "--phase", "2")
check("Q10", True, "TC-SEC-REG-001" not in json.dumps(orph["tests_naming_undefined_tc"]), "orphans runs and lists categories")
rc, imp = sgj(A, "impact", "api/orders.go")
check("Q11", True, "GET /api/orders" in imp["endpoints"] and "api/orders_test.go" in imp["tests_to_run"], "impact file: endpoints + tests to run")
write(A, "api/orders.go", open(os.path.join(A, "api/orders.go")).read().replace("func (h *Handler) ListOrders() {}", "func (h *Handler) ListOrders() { _ = 1 }"))
rc, dc = sgj(A, "diff-context", "--base", "HEAD", "--phase", "2")
check("Q12", True, any(s["symbol"] == "Handler.ListOrders" and "GET /api/orders" in s["endpoints"] for s in dc["changed_symbols"]),
      "diff-context: changed symbol span + the endpoint it serves")
rc, cc = sgj(A, "consumers", "--changed-since", "HEAD")
check("Q13", True, any(r["changed"].endswith("Handler.ListOrders") and r["existed_at_base"] for r in cc["with_consumers"]),
      "consumers --changed-since: changed symbols with consumers, marked pre-existing")
git(A, "checkout", "--", "api/orders.go")
rc, rm = sgj(A, "repomap", "--focus", "api/orders.go")
check("Q14", "api/orders.go", rm["ranked"][0]["file"] if rm.get("ranked") else None, "repomap: focus file ranks first")

# ─── graceful failure ──────────────────────────────────────────────────────────────────────────────
bad = os.path.join(W, "not-a-dir")
open(bad, "w").write("x")
rc, out, err = sg(A, "--graph-dir", os.path.join(bad, "g"), "tc", "--phase", "1")
check("F01", (4, True), (rc, "GRAPH UNAVAILABLE" in err), "an unbuildable graph exits 4 with a fall-back message")

# ─── python 3.9 (macOS system python) ──────────────────────────────────────────────────────────────
if os.path.exists("/usr/bin/python3"):
    v = subprocess.run(["/usr/bin/python3", "-c", "import sys; print(sys.version_info[:2] >= (3, 9))"], capture_output=True, text=True).stdout.strip()
    if v == "True":
        rc, out, err = sg(B, "--graph-dir", os.path.join(W, "py39"), "gate", "--phase", "1", "--tc-only", py="/usr/bin/python3")
        check("V01", 0, rc, "runs on /usr/bin/python3 (system python): clean gate PASSes")

# ═══ tc: --spec-only / --out / --source / --diff-base (the call sites that used tc-inventory.py) ═══════
PRI = os.path.join(W, "prio-a2.json")
rc, out, _ = sg(A, "tc", "--phase", "2", "--spec-only", "--out", PRI)
gp = json.load(open(PRI))
_, tp = tci(A, 2, "--spec-only")
check("T01", (0, True, {k: tp[k] for k in tp}), (rc, "TC-VAL-002" in gp and "TC-RNG-001" in gp, {k: gp.get(k) for k in tp}),
      "tc --spec-only: tc-inventory's {id: priority} exactly, plus range-defined IDs")
OUTJ = os.path.join(W, "tc-a2.json")
rc, out, _ = sg(A, "tc", "--phase", "2", "--source", "--out", OUTJ)
tj = json.load(open(OUTJ))
_, ts = tci(A, 2)
check("T02", (1, "source", True), (rc, tj["mode"], {c["name"]: c["verdict"] for c in ts["cases"]} ==
                                   {c["name"]: c["verdict"] for c in tj["cases"] if c["name"] in {x["name"] for x in ts["cases"]}}),
      "tc --source --out: tc-inventory's source-mode JSON shape and verdicts; exit 1 unless PASS")
check("T03", True, all(k in tj for k in ("missing", "failing", "skipped_only", "comment_only", "duplicate_ids", "weakening_unacknowledged", "cases")),
      "tc --out keeps every key the jq summaries in test.md/accept.md read")
rc, out, err = sg(A, "tc", "--phase", "2", "--diff-base", "", "--out", OUTJ)
check("T04", (2, True), (rc, "--diff-base is empty" in err), "tc --diff-base '' is an error, like tc-inventory (the weakening check would silently not run)")
rc, out, err = sg(A, "gate", "--phase", "2", "--tc-only", "--diff-base", "")
check("T05", (2, True), (rc, "--diff-base is empty" in err), "gate --diff-base '' is an error too, in any policy: a caller passing $(cat base_sha) still blocks")

# ═══ fixture D: role profiles (developers, verifiers, auditors, spec_impl_reconciler) ═════════════════
D = new_repo("d")
write(D, "docs/design/phases/1/PHASE_PLAN.md", "# Phase 1 — Orders\n## Scope\n- FR-001, FR-009\n")
write(D, "docs/design/phases/1/specs/orders.md", """# Orders (FR-001)
Intro: orders belong to a tenant.

## Acceptance Criteria
- WHEN a user lists orders THE SYSTEM SHALL return only their own orders (FR-001)

## Interface Contracts
### GET /api/orders/{id}
Returns one order.
### POST /api/admin/purge
Admin purge.

## Data Model
```sql
CREATE TABLE orders (id uuid primary key, owner_id uuid NOT NULL, tenant_id uuid NOT NULL);
```

## Edge Cases
- empty list returns []

## BRD Traceability
| FR | criteria |
|---|---|
| FR-001 | list |

## Test Coverage Required
| TC ID | Category | Description | Priority | Tier |
|---|---|---|---|---|
| TC-API-001 | API | GET /api/orders/{id} returns the order | HIGH | integration |
| TC-SEC-001 | SEC | a user can't read another user's order | HIGH | integration |
""")
write(D, "docs/design/phases/1/specs/data-contracts.md", """# Data Contracts
## 0. Error envelope
{ "error": { "code": "..." } }
## 1. Orders
### GET /api/orders/{id}
interface Order { id: string }
## 2. Admin
### POST /api/admin/purge
interface PurgeResult { n: number }
""")
write(D, "docs/design/phases/1/specs/orders-list.wireframe.md", """# Screen: Orders list
route: /orders
## Layout
A table.
## Data Bindings
| Component | Endpoint | Field | Shape |
|---|---|---|---|
| ordersTable | GET /api/orders/{id} | data | OBJECT |
## Accessibility
Every row is keyboard reachable; aria-label on the table; focus visible.
## UI Test Case Inventory
| TC ID | Category | Description | Priority | Tier |
|---|---|---|---|---|
| TC-UI-001 | UI | renders the table | HIGH | component |
| TC-A11Y-001 | A11Y | table is keyboard reachable | HIGH | e2e |
""")
write(D, "docs/design/phases/1/specs/orders-mobile.ui-spec.md", """# Screen: Orders (RN + Expo)
## RN Component Tree
FlatList of orders.
## Data Bindings
| ordersList | GET /api/orders/{id} | data | OBJECT |
""")
write(D, "docs/design/phases/1/specs/09_ui.md", """# Orders UI
## Layout
Header, then the orders table.
## The 4 States
loading / error / empty / data
## Data Model
`ui_prefs` table: owner_id, columns shown.
""")
write(D, "api/orders.go", '''package api

type Handler struct{}

func (h *Handler) GetOrder() { query("SELECT id FROM orders WHERE tenant_id = $1") }
func Routes(r Router) {
	r.GET("/api/orders/:id", h.GetOrder)
}
''')
write(D, "migrations/001_init.sql", "CREATE TABLE users (id uuid primary key);\n")
git(D, "add", "-A")
git(D, "commit", "-qm", "base")
os.makedirs(os.path.join(D, "agent_state", "phases", "1"))
open(os.path.join(D, "agent_state", "phases", "1", "base_sha"), "w").write(git(D, "rev-parse", "HEAD").strip() + "\n")
write(D, "migrations/002_orders.sql", "CREATE TABLE orders (id uuid primary key);\nALTER TABLE users ADD COLUMN tenant_id uuid;\n")
write(D, "api/orders.go", open(os.path.join(D, "api/orders.go")).read() + "\nfunc Extra() {}\n")
git(D, "add", "-A")
git(D, "commit", "-qm", "phase 1 work")
sg(D, "build")
OM, DC, WF, MB = ("docs/design/phases/1/specs/orders.md", "docs/design/phases/1/specs/data-contracts.md",
                  "docs/design/phases/1/specs/orders-list.wireframe.md", "docs/design/phases/1/specs/orders-mobile.ui-spec.md")
RK, SK = "spec_sections_to_read (file: line spans)", "skipped (open on demand: file: start-end)"
LN = {f: open(os.path.join(D, f)).read().split("\n") for f in (OM, DC, WF, MB)}


def ctxd(role, *extra):
    rc, j = sgj(D, "context", "--agent", role, "--phase", "1", *extra)
    return j


def read_titles(j, f):
    """Headings inside the spans the profile tells the role to read in file f."""
    row = next((r for r in j.get(RK, []) if r.startswith(f + ":")), None)
    if not row:
        return set()
    out = set()
    for a_, b_ in (x.split("-") for x in row.split(": ", 1)[1].split(" (~")[0].split(", ")):
        out |= {l.lstrip("# ").strip() for l in LN[f][int(a_) - 1:int(b_)] if l.startswith("#")}
    return out


bk = ctxd("backend_developer")
check("PR01", ({"Acceptance Criteria", "Interface Contracts", "Data Model", "Edge Cases"}, set()),
      (read_titles(bk, OM) & {"Acceptance Criteria", "Interface Contracts", "Data Model", "Edge Cases"},
       read_titles(bk, OM) & {"Test Coverage Required", "BRD Traceability"}),
      "backend_developer: reads behaviour/contract/data/edge sections; skips the TC inventory and BRD traceability")
check("PR02", (True, False, False), (DC + ":" in " ".join(bk[RK]), any(r.startswith(WF) for r in bk[RK]), any(r.startswith(MB) for r in bk[RK])),
      "backend_developer: reads the contract file, not the screen specs")
check("PR03", True, all(any(r.startswith(f) for r in bk[SK]) for f in (OM, WF, MB)), "every skipped span is listed with its file (open on demand)")
check("PR04", True, any(r.startswith("TC-SEC-001 HIGH") for r in bk["security_rows (TC-SEC: implement the mitigation)"]),
      "backend_developer: TC-SEC rows to implement, though their inventory section is skipped")
check("PR05", True, 0 < bk["spec_sections_tokens"] < bk["whole_specs_dir_tokens"], "backend_developer reads less than the whole specs/ dir")
ui = ctxd("ui_developer")
check("PR06", ({"Layout", "Data Bindings", "Accessibility"}, set()),
      (read_titles(ui, WF) & {"Layout", "Data Bindings", "Accessibility"}, read_titles(ui, WF) & {"UI Test Case Inventory"}),
      "ui_developer: its web screen spec minus the UI test inventory")
check("PR07", (False, {"0. Error envelope", "1. Orders", "GET /api/orders/{id}"}, set()),
      (any(r.startswith(MB) for r in ui[RK]), read_titles(ui, DC) & {"0. Error envelope", "1. Orders", "GET /api/orders/{id}"},
       read_titles(ui, DC) & {"2. Admin", "POST /api/admin/purge"}),
      "ui_developer: no mobile screen; contract sections for the endpoints it binds + the cross-cutting envelope, not the rest")
check("PR08", ({"Acceptance Criteria", "GET /api/orders/{id}"}, set()),
      (read_titles(ui, OM) & {"Acceptance Criteria", "GET /api/orders/{id}"}, read_titles(ui, OM) & {"POST /api/admin/purge", "Data Model", "Edge Cases"}),
      "ui_developer: acceptance criteria + only the bound endpoint's contract subsection of a component spec")
check("PR09", (True, True), (any("NOT DECLARED" not in x and "GET /api/orders/{}" in x for x in ui["bound_endpoints (declared in a contract?)"]),
                              [s["screen"] for s in ui["screens"]] == ["orders-list"]),
      "ui_developer: bound endpoints checked against the contracts (STOP condition) + its screens only")
check("PR09b", True, any(r.startswith("TC-SEC-001") for r in ui["security_rows (TC-SEC: implement the mitigation)"]),
      "ui_developer: TC-SEC rows too (the threat model's UI mitigations)")
U9 = "docs/design/phases/1/specs/09_ui.md"
LN[U9] = open(os.path.join(D, U9)).read().split("\n")
check("PR09c", ({"Layout", "The 4 States"}, {"Data Model"}, set()),
      (read_titles(ui, U9) & {"Layout", "The 4 States"}, read_titles(bk, U9) - {"Orders UI"}, read_titles(bk, U9) & {"Layout", "The 4 States"}),
      "a component spec named as UI (09_ui.md) is a screen spec to ui_developer; backend still reads its non-UI sections")
mb = ctxd("mobile_developer")
check("PR10", (True, False), (any(r.startswith(MB) for r in mb[RK]), any(r.startswith(WF) for r in mb[RK])), "mobile_developer: the RN screen, not the web one")
db = ctxd("database_agent")
check("PR11", (True, False, False), ("Data Model" in read_titles(db, OM), "POST /api/admin/purge" in read_titles(db, OM), any(r.startswith(WF) for r in db[RK])),
      "database_agent: data-model sections, not API subsections or screens")
ti = ctxd("tenant_isolation_verifier")
check("PR12", ({"Acceptance Criteria", "Data Model"}, set()),
      (read_titles(ti, OM) & {"Acceptance Criteria", "Data Model"}, read_titles(ti, OM) & {"Edge Cases", "Test Coverage Required"}),
      "tenant_isolation_verifier: sections that define ownership/tenancy + the data model only")
check("PR13", True, any(r.startswith("GET /api/orders/{}") and "api/orders.go" in r
                        for r in ti["id_routes (changed this phase; Step 1 seed — grep for what regex routes miss)"]),
      "tenant_isolation_verifier: ID routes changed this phase with their handler")
ms = ctxd("migration_safety_reviewer")
check("PR14", ([{"file": "migrations/002_orders.sql", "creates": ["orders"], "alters": ["users"]}], True),
      (ms["migrations_changed (UP/DOWN to review)"], "Data Model" in read_titles(ms, OM)),
      "migration_safety_reviewer: migrations changed since base_sha (creates/alters) + the data-model section")
cq = ctxd("code_quality_verifier")
check("PR15", ([], ["POST /api/admin/purge"]), (cq[RK], cq["endpoints_without_handler"]),
      "code_quality_verifier: no spec prose; declared endpoints with handlers, and the ones with none")
ax = ctxd("accessibility_auditor")
check("PR16", (True, False, ["TC-A11Y-001"]), ("Accessibility" in read_titles(ax, WF), any(r.startswith(MB) for r in ax[RK]),
                                              [r.split()[0] for r in ax["a11y_rows (results: e2e_results.json)"]]),
      "accessibility_auditor: web screen accessibility sections, no mobile screen, the A11Y rows")
us = ctxd("ui_standards_auditor")
check("PR17", (True, True, False), (any(r.startswith(WF) for r in us[RK]), any(r.startswith(MB) for r in us[RK]), any(r.startswith(OM) for r in us[RK])),
      "ui_standards_auditor: every screen spec, no component spec")
sr = ctxd("spec_impl_reconciler")
check("PR18", (True, set()), ({"Acceptance Criteria", "BRD Traceability", "Edge Cases"} <= read_titles(sr, OM), read_titles(sr, OM) & {"Test Coverage Required"}),
      "spec_impl_reconciler: every spec section except the TC inventory (whole-spec coverage, read on demand)")
check("PR19", (True, True, ["FR-009"]),
      (any(r.startswith("POST /api/admin/purge → MISSING") for r in sr["endpoints declared → handler (Level 1)"]),
       any(r.startswith("Order ") and "NOT FOUND" in r for r in sr["contract types → code"]), sr["FRs in scope with no spec section"]),
      "spec_impl_reconciler: inventory — endpoint with no handler, contract type not in code, FR in scope with no spec")
rc, out, _ = sg(D, "context", "--agent", "backend_developer", "--phase", "1", "--max-tokens", "250")
check("PR20", True, OM + ":" in out and DC + ":" in out, "a tight --max-tokens cuts the other lists before the reading list")
if os.path.exists("/usr/bin/python3"):
    rc, out, err = sg(D, "--graph-dir", os.path.join(W, "py39d"), "context", "--agent", "ui_developer", "--phase", "1", py="/usr/bin/python3")
    check("V02", (0, True), (rc, WF in out), "role profiles run on /usr/bin/python3 too")

# ═══ verify-gate.sh check (h) ══════════════════════════════════════════════════════════════════════
AG = "backend_developer code_reviewer_I code_reviewer_II security_reviewer code_quality_verifier unit_test_agent test_runner spec_test_reconciler acceptance_test_agent".split()
R = os.path.join(P1, "reports")
C = os.path.join(B, "agent_state", "reconciliation", "phase-1")
os.makedirs(C, exist_ok=True)
for f in ("unit_tests.json", "acceptance_report.json"):
    shutil.copy(os.path.join(R, "test_results.json"), os.path.join(R, f))
for f in ("unit_tests", "test_results", "acceptance_report"):
    open(os.path.join(R, f + ".md"), "w").write("see json\n")
subprocess.run([PY, TCI, "--phase", "1", "--root", B, "--results", os.path.join(R, "test_results.json"), "--diff-base",
                open(os.path.join(P1, "base_sha")).read().strip(), "--out", os.path.join(C, "specs_vs_tests.json")], capture_output=True)
open(os.path.join(C, "specs_vs_tests.md"), "w").write("inventory\nBLOCKING:0 WARNING:0 INFO:0\n")
open(os.path.join(P1, "roster.json"), "w").write(json.dumps({"phase": 1, "required": AG}))
with open(os.path.join(P1, "execution.jsonl"), "w") as f:
    for a in AG:
        rep = {"backend_developer": None, "unit_test_agent": "agent_state/phases/1/reports/unit_tests.md",
               "test_runner": "agent_state/phases/1/reports/test_results.md",
               "acceptance_test_agent": "agent_state/phases/1/reports/acceptance_report.md",
               "spec_test_reconciler": "agent_state/reconciliation/phase-1/specs_vs_tests.md"}.get(a, f"agent_state/phases/1/reports/{a}.md")
        if rep and not os.path.exists(os.path.join(B, rep)):
            open(os.path.join(B, rep), "w").write("review\nBLOCKING:0 WARNING:0 INFO:0\n")
        f.write(json.dumps({"agent": a, "phase": 1, "status": "completed", "report": rep, "ts": "t"}) + "\n")


def verify_gate(env=None):
    p = subprocess.run(["bash", os.path.join(H, "verify-gate.sh"), "1"], capture_output=True, text=True,
                       env=dict(env or WARN, CLAUDE_PROJECT_DIR=B))
    return p.returncode, p.stdout + p.stderr


rc, log = verify_gate()
check("H01", (0, True), (rc, "(h) TC inventory" in log and "sdlc-graph gate" in log), "verify-gate (h) runs the graph TC gate; clean phase PASSes")
spec = os.path.join(B, "docs/design/phases/1/specs/orders.md")
orig = open(spec).read()
open(spec, "w").write(orig + "| TC-SEC-REG-001 | SEC | hidden row | HIGH | integration |\n")
rc, log = verify_gate()
check("H02", (0, True, False), (rc, "tc warning (D-002, not blocking): [malformed_ids]" in log and "TC-SEC-REG-001" in log, "tc: malformed TC ID" in log),
      "verify-gate (h), default policy: a malformed ID row is a visible warning, the gate passes")
rc, log = verify_gate(STRICT)
check("H02s", (2, True), (rc, "tc: malformed TC ID" in log), "verify-gate (h), strict: BLOCKs on a malformed ID row tc-inventory can't see")
open(spec, "w").write(orig.replace("| TC-UI-10101 |", "| TC-API-10103 – TC-API-10104 | API | range rows | HIGH | integration |\n| TC-UI-10101 |"))
rc, log = verify_gate(STRICT)
check("H03", (2, True), (rc, "TC-API-10103" in log and "defined by a range" in log), "verify-gate (h), strict: BLOCKs on uncovered range-defined IDs")
rc, log = verify_gate()
check("H03w", (True, False), ("tc warning (D-002, not blocking): [range_ids]" in log and "TC-API-10103" in log,
                              any(l.strip().startswith("✗ tc:") and "TC-API-10103" in l for l in log.splitlines())),
      "verify-gate (h), default: uncovered range-defined IDs are a warning, not a ✗")
open(spec, "w").write(orig)
os.remove(os.path.join(P1, "base_sha"))
rc, log = verify_gate(STRICT)
check("H04", (2, True), (rc, "tc: no base commit" in log), "verify-gate (h), strict: BLOCKs when base_sha is missing (weakening check can't run)")
rc, log = verify_gate()
check("H04w", (0, True, True), (rc, "[base_sha_required]" in log, "1 D-002 warning(s)" in log),
      "verify-gate (h), default: missing base_sha is a warning; the ok line counts the warnings and names the commands")

print(f"\nsdlc-graph: {total - fails}/{total} passed")
shutil.rmtree(W, ignore_errors=True)
sys.exit(1 if fails else 0)
