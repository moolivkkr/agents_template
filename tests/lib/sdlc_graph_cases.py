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


def sg(root, *args, py=PY):
    p = subprocess.run([py, SG, "--root", root, *args], capture_output=True, text=True)
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


def gate(root, phase, *extra):
    out = os.path.join(W, f"gate-{os.path.basename(root)}-{phase}.json")
    rc, so, se = sg(root, "gate", "--phase", str(phase), "--tc-only", "--out", out, *extra)
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
- checkout: buyer checks out (FR-002)
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

# ─── the gate: strict superset ─────────────────────────────────────────────────────────────────────
rc, gj, so = gate(A, 2)
check("G01", 1, rc, "gate FAILs fixture A phase 2")
gb = "\n".join(so.splitlines())
check("G02", True, "no runner results" not in gb, "with sidecars in reports/ the gate runs in results mode")
check("G03", True, "no base commit" in gb, "gate BLOCKs when agent_state/phases/N/base_sha is missing")
check("G04", True, "malformed TC ID" in gb and "TC-SEC-REG-001" in gb, "gate BLOCKs on a malformed ID cell")
check("G05", True, "TC-VAL-002" in gb and "defined by a range" in gb, "gate BLOCKs on an uncovered range-defined ID and says so")
rc, gj1, so1 = gate(A, 1)
check("G06", True, "no runner results" in so1, "gate BLOCKs a phase with no runner sidecar (coverage nobody ran)")
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


def verify_gate():
    p = subprocess.run(["bash", os.path.join(H, "verify-gate.sh"), "1"], capture_output=True, text=True,
                       env=dict(os.environ, CLAUDE_PROJECT_DIR=B))
    return p.returncode, p.stdout + p.stderr


rc, log = verify_gate()
check("H01", (0, True), (rc, "(h) TC inventory" in log and "sdlc-graph gate" in log), "verify-gate (h) runs the graph TC gate; clean phase PASSes")
spec = os.path.join(B, "docs/design/phases/1/specs/orders.md")
orig = open(spec).read()
open(spec, "w").write(orig + "| TC-SEC-REG-001 | SEC | hidden row | HIGH | integration |\n")
rc, log = verify_gate()
check("H02", (2, True), (rc, "tc: malformed TC ID" in log), "verify-gate (h) BLOCKs on a malformed ID row tc-inventory can't see")
open(spec, "w").write(orig.replace("| TC-UI-10101 |", "| TC-API-10103 – TC-API-10104 | API | range rows | HIGH | integration |\n| TC-UI-10101 |"))
rc, log = verify_gate()
check("H03", (2, True), (rc, "TC-API-10103" in log and "defined by a range" in log), "verify-gate (h) BLOCKs on uncovered range-defined IDs")
open(spec, "w").write(orig)
os.remove(os.path.join(P1, "base_sha"))
rc, log = verify_gate()
check("H04", (2, True), (rc, "no base commit" in log), "verify-gate (h) BLOCKs when base_sha is missing (weakening check can't run)")

print(f"\nsdlc-graph: {total - fails}/{total} passed")
shutil.rmtree(W, ignore_errors=True)
sys.exit(1 if fails else 0)
