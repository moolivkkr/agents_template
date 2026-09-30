#!/usr/bin/env python3
"""Tests for .claude/hooks/junit-to-sidecar.py and tc-inventory.py on synthetic repos.

Each case encodes a loophole the 2026-09-30 board review found in the grep-based TC inventory
(TEST-02/DEV-13/TEST-17) or in self-reported test counts (TEST-01/TEST-08/TEST-10). Exit 0 = all pass.
"""
import json, os, shutil, subprocess, sys, tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
J2S = os.path.join(REPO, ".claude", "hooks", "junit-to-sidecar.py")
TCI = os.path.join(REPO, ".claude", "hooks", "tc-inventory.py")
W = tempfile.mkdtemp(prefix="evidence-tools.")
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


def run(*args):
    p = subprocess.run([sys.executable, *args], capture_output=True, text=True, cwd=W)
    return p.returncode, p.stdout + p.stderr


# ─── fixture repo ─────────────────────────────────────────────────────────────────────────────────
git("init", "-q"); git("config", "user.email", "t@t"); git("config", "user.name", "t")
write("docs/design/phases/1/specs/users.md", "| TC ID | Description | Priority |\n|---|---|---|\n| TC-API-001 | list users | HIGH |\n| TC-API-102 | reused by phase 2 | HIGH |\n")
write("docs/design/phases/2/specs/orders.md", """# Orders
TC-API-101 to TC-API-103 — order endpoint tests (a range line: grouping, not IDs)

| TC ID | Category | Test Description | Priority | Tier |
|-------|----------|------------------|----------|------|
| TC-API-101 | API | creates an order | HIGH | integration |
| TC-API-102 | API | rejects a bad order | MEDIUM | integration |
| TC-API-103 | API | cosmetic message | LOW | unit |
| TC-UI-101 | UI | renders the order form | HIGH | component |
| TC-E2E-101 | E2E | checkout end to end | HIGH | e2e |
""")
write("api/orders_test.go", '''package api
import "testing"
// TC-API-102: only mentioned in a comment (TODO write this)
// covers TC-API-104 to TC-API-106
func TestCreateOrder(t *testing.T) {
    t.Run("TC-API-101 creates an order", func(t *testing.T) { if 1 != 1 { t.Fatal("x") } })
}
func TestLater(t *testing.T) {
    t.Skip("not yet")
    t.Run("TC-UI-101 renders", func(t *testing.T) {})
}
''')
write("web/orders.test.ts", '''describe.skip('order form', () => {
  it('TC-UI-101 renders the form', () => { expect(1).toBe(1) })
})
test('TC-E2E-101 checkout end to end', async () => { expect(true).toBe(true) })
''')
write("tests/test_orders.py", '''import pytest
@pytest.mark.parametrize(
    "msg",
    ["a"],
    ids=["TC-API-103"])
def test_message(msg):
    assert msg
''')
git("add", "-A"); git("commit", "-qm", "base")
BASE = subprocess.run(["git", "-C", W, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()

# ─── tc-inventory, source mode ────────────────────────────────────────────────────────────────────
rc, out = run(TCI, "--phase", "2", "--root", W, "--out", f"{W}/agent_state/inv.json")
inv = json.load(open(f"{W}/agent_state/inv.json"))
v = {c["name"]: c["verdict"] for c in inv["cases"]}
check("TI01", 1, rc, "source mode FAILs when HIGH/MEDIUM IDs are uncovered")
check("TI02", "PASS", v.get("TC-API-101"), "ID in a t.Run subtest name counts")
check("TI03", "UNTESTED", v.get("TC-UI-101"), "ID only in skipped tests (t.Skip, describe.skip) does not count")
check("TI04", ["TC-UI-101"], inv["skipped_only"], "skipped-only IDs are listed")
check("TI05", "UNTESTED", v.get("TC-API-102"), "ID only in a comment/TODO does not count")
check("TI06", ["TC-API-102"], inv["comment_only"], "comment-only IDs are listed")
check("TI07", "PASS", v.get("TC-API-103"), "pytest parametrize ids= counts (LOW)")
check("TI08", "PASS", v.get("TC-E2E-101"), "Jest/Playwright test title counts")
check("TI09", {"TC-API-102": ["1"]}, inv["duplicate_ids"], "an ID defined by two phases is flagged")
check("TI10", 1, len(inv["range_annotations"]), "a range annotation in a test file is flagged")
check("TI11", 5, len(inv["cases"]), "range line in the spec prose is not an ID (5 table rows only)")
check("TI12", ["TC-API-102", "TC-UI-101"], sorted(inv["missing"]), "missing = uncovered HIGH/MEDIUM only (LOW not blocking)")

# ─── junit-to-sidecar ─────────────────────────────────────────────────────────────────────────────
write("agent_state/junit/unit.xml", '''<testsuites><testsuite name="api">
 <testcase classname="api" name="TestCreateOrder/TC-API-101 creates an order"><failure message="boom"/></testcase>
 <testcase classname="api" name="TestFlaky"><failure message="1st"/></testcase>
 <testcase classname="api" name="TestFlaky"/>
 <testcase classname="api" name="TestMessage[TC-API-103]"/>
 <testcase classname="api" name="TestLater"><skipped/></testcase>
</testsuite></testsuites>''')
rc, out = run(J2S, "--tier", "unit", "--out", f"{W}/agent_state/unit.json", "--exit-code", "1", "--root", W, f"{W}/agent_state/junit/unit.xml")
sc = json.load(open(f"{W}/agent_state/unit.json"))
check("JS01", (1, "FAIL"), (rc, sc["verdict"]), "a failing testcase makes the sidecar FAIL")
check("JS02", (3, 1, 1, 1, 1), (sc["total"], sc["passed"], sc["failed"], sc["skipped"], sc["flaky"]),
      "counts: total excludes skipped; fail-then-pass on retry = flaky, not passed")
check("JS03", ["TC-API-101"], next(c["ids"] for c in sc["cases"] if "TC-API-101" in c["name"]), "TC IDs parsed from test names")
check("JS04", (BASE, False), (sc["code_sha"], sc["dirty"]), "code_sha = last code commit; clean tree")
write("agent_state/junit/ok.xml", '<testsuite><testcase name="TestA_TC_API_101"/></testsuite>')
rc, _ = run(J2S, "--tier", "unit", "--out", f"{W}/agent_state/ok.json", "--exit-code", "2", "--root", W, f"{W}/agent_state/junit/ok.xml")
check("JS05", (1, "ERROR"), (rc, json.load(open(f"{W}/agent_state/ok.json"))["verdict"]), "non-zero exit with no failing case = ERROR (runner crashed)")
rc, _ = run(J2S, "--tier", "unit", "--out", f"{W}/agent_state/ok2.json", "--exit-code", "0", "--root", W, f"{W}/agent_state/junit/ok.xml")
ok2 = json.load(open(f"{W}/agent_state/ok2.json"))
check("JS06", (0, "PASS", ["TC-API-101"]), (rc, ok2["verdict"], ok2["cases"][0]["ids"]), "clean run PASSes; TC_API_101 (underscore form) normalises")
write("agent_state/junit/empty.xml", "<testsuite/>")
rc, _ = run(J2S, "--tier", "unit", "--out", f"{W}/agent_state/empty.json", "--root", W, f"{W}/agent_state/junit/empty.xml")
check("JS07", (1, "FAIL"), (rc, json.load(open(f"{W}/agent_state/empty.json"))["verdict"]), "zero tests = FAIL")

# ─── tc-inventory, results mode (covering test must have PASSED in the run) ──────────────────────
rc, _ = run(TCI, "--phase", "2", "--root", W, "--results", f"{W}/agent_state/unit.json", "--out", f"{W}/agent_state/inv2.json")
inv2 = json.load(open(f"{W}/agent_state/inv2.json"))
v2 = {c["name"]: c["verdict"] for c in inv2["cases"]}
check("TR01", "FAIL", v2.get("TC-API-101"), "results mode: an ID whose test FAILED is failing, not covered")
check("TR02", "UNTESTED", v2.get("TC-E2E-101"), "results mode: an ID with no executed test is UNTESTED")
check("TR03", "PASS", v2.get("TC-API-103"), "results mode: an ID whose test passed is covered")

# ─── test weakening since the phase base ─────────────────────────────────────────────────────────
write("web/orders.test.ts", '''describe.skip('order form', () => {
  it('TC-UI-101 renders the form', () => { })
})
test.only('TC-E2E-101 checkout end to end', async () => { })
''')
write("api/orders_test.go", open(os.path.join(W, "api/orders_test.go")).read().replace(
    'func TestCreateOrder(t *testing.T) {', 'func TestCreateOrder(t *testing.T) {\n    t.Skip("flaky")'))
rc, _ = run(TCI, "--phase", "2", "--root", W, "--diff-base", BASE, "--out", f"{W}/agent_state/inv3.json")
inv3 = json.load(open(f"{W}/agent_state/inv3.json"))
kinds = sorted(w["kind"] for w in inv3["weakening"])
check("TW01", ["added_only", "added_skip", "removed_assertion", "removed_assertion"], kinds,
      "diff mode finds removed assertions, a new t.Skip and a new test.only")
check("TW02", 4, len(inv3["weakening_unacknowledged"]), "unacknowledged weakening counts toward failure")
write("agent_state/phases/2/test-changes.json", json.dumps([{"file": "web/orders.test.ts", "kind": "removed_assertion",
                                                             "reason": "assertion moved to a shared helper"}]))
run(TCI, "--phase", "2", "--root", W, "--diff-base", BASE, "--out", f"{W}/agent_state/inv4.json")
check("TW03", 2, len(json.load(open(f"{W}/agent_state/inv4.json"))["weakening_unacknowledged"]),
      "an acknowledged change (file+kind+reason) no longer counts")

# ─── a fully covered phase passes ────────────────────────────────────────────────────────────────
C = tempfile.mkdtemp(prefix="evidence-clean.")
os.makedirs(f"{C}/docs/design/phases/1"); os.makedirs(f"{C}/pkg")
open(f"{C}/docs/design/phases/1/s.md", "w").write("| TC ID | Priority |\n|---|---|\n| TC-E-001 | HIGH |\n| TC-E-002 | MEDIUM |\n")
open(f"{C}/pkg/a_test.go", "w").write('package pkg\nimport "testing"\nfunc TestA(t *testing.T) {\n tests := []struct{ name string }{{name: "TC-E-001 ok"}, {name: "TC-E-002 ok"}}\n _ = tests\n}\n')
p = subprocess.run([sys.executable, TCI, "--phase", "1", "--root", C, "--out", f"{C}/inv.json"], capture_output=True, text=True)
check("TC01", (0, "PASS"), (p.returncode, json.load(open(f"{C}/inv.json"))["verdict"]), "table-driven name: fields cover their IDs → PASS")
p = subprocess.run([sys.executable, TCI, "--phase", "9", "--root", C, "--out", f"{C}/none.json"], capture_output=True, text=True)
check("TC02", (1, "BLOCKED"), (p.returncode, json.load(open(f"{C}/none.json"))["verdict"]), "no spec inventory = BLOCKED, never a vacuous PASS")


# ─── commands-table.py ───────────────────────────────────────────────────────────────────────────
CT = os.path.join(REPO, ".claude", "hooks", "commands-table.py")
G = tempfile.mkdtemp(prefix="cmdtable.")
open(f"{G}/IG.md", "w").write("""# Guidelines
## Commands and versions

| Purpose | Command |
|---|---|
| build | `go build ./...` |
| lint | golangci-lint run ./... |
| test:unit | gotestsum --junitfile agent_state/phases/$PHASE/junit/unit.xml -- -count=1 ./... |
| migrate | ./bin/app migrate |

| Component | Version |
|---|---|
| Go | 1.27 |
| PostgreSQL | 17 |

## Next section
| Purpose | Command |
|---|---|
| test:unit | WRONG — outside the section |
""")
p = subprocess.run([sys.executable, CT, f"{G}/IG.md", "--out", f"{G}/v.json"], capture_output=True, text=True)
v = json.load(open(f"{G}/v.json")) if p.returncode == 0 else {}
check("CT01", (0, "go build ./...", "golangci-lint run ./..."), (p.returncode, v.get("typecheck"), v.get("lint")),
      "typecheck falls back to build; backticks stripped")
check("CT02", ("gotestsum --junitfile agent_state/phases/$PHASE/junit/unit.xml -- -count=1 ./...", {"Go": "1.27", "PostgreSQL": "17"}),
      (v.get("test"), v.get("versions")), "test = test:unit from THIS section only; versions parsed")
open(f"{G}/bad.md", "w").write("## Commands and versions\n| Purpose | Command |\n|---|---|\n| build | make |\n")
p = subprocess.run([sys.executable, CT, f"{G}/bad.md", "--out", f"{G}/b.json"], capture_output=True, text=True)
check("CT03", 1, p.returncode, "no test:unit command → error, never a gate that runs nothing")
open(f"{G}/none.md", "w").write("# no table\n")
p = subprocess.run([sys.executable, CT, f"{G}/none.md", "--out", f"{G}/n.json"], capture_output=True, text=True)
check("CT04", 1, p.returncode, "missing section → error")
shutil.rmtree(G, ignore_errors=True)

shutil.rmtree(W, ignore_errors=True); shutil.rmtree(C, ignore_errors=True)
print(f"\n{total - fails}/{total} passed")
sys.exit(1 if fails else 0)
