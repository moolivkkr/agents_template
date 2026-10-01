#!/usr/bin/env python3
"""Tests for /board-review's deterministic half, .claude/hooks/board-review.py, and its wiring.

BR-*: target groups resolve; citations are checked against real lines; verification inputs are
blind (no severity), include every CRITICAL/HIGH plus a deterministic MEDIUM/LOW sample; merge
drops refuted findings, takes the verifier's severity, folds duplicates, refuses an unverified
CRITICAL/HIGH, derives scores from the worst verified finding, flags a verifier that changed
nothing; compare shows movement.
BL-*: the command and the hat checklists stay wired (every hat has a checklist the command names,
foreground spawns, Fable verifiers, report-everything). Exit 0 = all pass.
"""
import json, os, re, shutil, subprocess, sys, tempfile

sys.dont_write_bytecode = True  # the wiring lint imports board-review.py; keep __pycache__ out of .claude/hooks

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BR = os.path.join(REPO, ".claude", "hooks", "board-review.py")
W = tempfile.mkdtemp(prefix="board-review.")
RUN = os.path.join(W, "docs", "board-review-2026-10-01-debate")
fails = total = 0


def check(cid, want, got, label):
    global fails, total
    total += 1
    ok = want == got
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'} {cid:5} {label}" + ("" if ok else f"\n      want={want!r}\n      got ={got!r}"))


def br(*args, root=W):
    p = subprocess.run([sys.executable, BR, "--root", root, *args], capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def write(rel, text):
    p = os.path.join(W, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write(text if isinstance(text, str) else json.dumps(text, indent=2))
    return p


def finding(fid, sev, agents=("a1",), line=2, **kw):
    f = {"id": fid, "severity": sev, "type": "a", "agents": list(agents), "file": ".claude/agents/core/a1.md",
         "line": line, "evidence": "quote", "problem": "fails when", "fix": "do this"}
    f.update(kw)
    return f


def hat(name, findings, targets=("a1", "a2"), coverage=("a1", "a2")):
    return {"schema": "sdlc.board-findings/v1", "hat": name, "run": "t", "targets": list(targets),
            "coverage": [{"agent": a, "note": "read"} for a in coverage], "findings": findings}


write(".claude/agents/core/a1.md", "line1\nline2\nline3\n")
write(".claude/agents/core/a2.md", "x\n")

# ---------------------------------------------------------------- targets
rc, out = br("targets", "debate", root=REPO)
r = json.loads(out)
check("BR-01", (0, 4, []), (rc, len(r["agents"]), r["missing"]), "the debate group resolves to its four agents")
for g in ("coding-testing", "requirements", "reconcile", "planning", "review", "ops", "all"):
    rc, out = br("targets", g, root=REPO)
    r = json.loads(out)
    check(f"BR-02{g[:3]}", (0, [], []), (rc, r["missing"], r["context_missing"]), f"group '{g}' resolves every agent and context file")
rc, out = br("targets", "debate_moderator,no_such_agent", root=REPO)
check("BR-03", (2, ["no_such_agent"]), (rc, json.loads(out)["missing"]), "an unknown agent name fails resolution")

# ---------------------------------------------------------------- validate
write(f"{RUN}/hats/architect.json", hat("architect", [finding("ARCH-01", "HIGH"), finding("ARCH-02", "MEDIUM")]))
rc, out = br("validate", f"{RUN}/hats/architect.json")
check("BR-04", 0, rc, "a well-formed findings file validates")
bad = hat("tester", [finding("TEST-01", "HIGH", line=99), finding("TEST-01", "SEVERE"), finding("ARCH-9", "LOW"),
                     finding("TEST-04", "LOW", file=".claude/agents/core/ghost.md")], coverage=("a1",))
write(f"{W}/bad.json", bad)
rc, out = br("validate", f"{W}/bad.json")
for cid, needle, label in [("BR-05", "outside .claude/agents/core/a1.md", "a citation past the end of the file is rejected"),
                           ("BR-06", "does not exist", "a citation to a missing file is rejected"),
                           ("BR-07", "duplicate id", "duplicate ids are rejected"),
                           ("BR-08", "severity must be", "an unknown severity is rejected"),
                           ("BR-09", "id must be TEST-<n>", "an id with another hat's prefix is rejected"),
                           ("BR-10", "'a2' has no coverage", "a target with no coverage entry is reported")]:
    check(cid, (2, True), (rc, needle in out), label)

# ---------------------------------------------------------------- select (blind)
sec = [finding(f"SEC-0{i}", s) for i, s in enumerate(["CRITICAL", "HIGH", "MEDIUM", "MEDIUM", "LOW", "MEDIUM", "LOW", "LOW"], 1)]
write(f"{RUN}/hats/security.json", hat("security", sec))
rc, out = br("select", "--dir", RUN)
plan = json.load(open(f"{RUN}/verify/plan.json"))
check("BR-11", {"V1": ["security", "architect"]}, {k: v["hats"] for k, v in plan.items()}, "security and architect share a verifier")
inp = json.load(open(f"{RUN}/verify/input-V1.json"))
ids = [f["id"] for f in inp["findings"]]
check("BR-12", [], [f["id"] for f in inp["findings"] if "severity" in f], "verifier input carries no severity (blind)")
check("BR-13", True, {"SEC-01", "SEC-02", "ARCH-01"} <= set(ids), "every CRITICAL and HIGH finding is in the input")
check("BR-14", True, len([i for i in ids if i.startswith("SEC") and i not in ("SEC-01", "SEC-02")]) >= 3, "at least 3 MEDIUM/LOW findings per hat are sampled")
check("BR-14b", (True, []), (len(inp["others"]) > 0 and all(o["id"] not in ids for o in inp["others"]), [o["id"] for o in inp["others"] if "severity" in o]),
      "the input lists the other findings (for cross-verifier duplicates), also without severity")
rc, out = br("select", "--dir", RUN)
check("BR-15", ids, [f["id"] for f in json.load(open(f"{RUN}/verify/input-V1.json"))["findings"]], "selection and order are deterministic for a run")
check("BR-16", False, ids == sorted(ids), "the order is shuffled, not grouped by hat or severity")

# ---------------------------------------------------------------- verification + merge
def verdicts(vs):
    write(f"{RUN}/verify/V1.json", {"schema": "sdlc.board-verification/v1", "verifier": "V1", "model": "fable",
                                     "hats": ["security", "architect"], "verdicts": vs})

def v(fid, verdict="confirmed", sev="HIGH", **kw):
    d = {"id": fid, "verdict": verdict, "severity": sev, "reproduction": "opened file", "note": "n"}
    d.update(kw)
    return d

verdicts([v(i, note="") for i in ids])
rc, out = br("validate", f"{RUN}/verify/V1.json")
check("BR-16b", (2, True), (rc, "no note" in out), "every verdict needs a note (it explains any severity change)")
verdicts([v("SEC-01", sev="CRITICAL")])
rc, out = br("validate", f"{RUN}/verify/V1.json")
check("BR-17", (2, True), (rc, "has no verdict" in out), "a verification missing an input id fails validation")
rc, out = br("merge", "--dir", RUN)
check("BR-18", (2, True), (rc, "SEC-02 (HIGH) has no verifier verdict" in out), "merge refuses a CRITICAL/HIGH finding nobody verified")

full = {i: v(i) for i in ids}
full["SEC-01"] = v("SEC-01", sev="CRITICAL")
full["SEC-02"] = v("SEC-02", "refuted", note="the cited line says the opposite")
full["ARCH-01"] = v("ARCH-01", "narrowed", sev="MEDIUM", note="only one of the two agents")
for i in ids:
    if i not in ("SEC-01", "SEC-02", "ARCH-01"):
        full[i] = v(i, sev="LOW")
other = [i for i in ids if i not in ("SEC-01", "SEC-02", "ARCH-01")]
full[other[0]] = v(other[0], sev="HIGH", duplicate_of="SEC-01")
verdicts(list(full.values()))
rc, out = br("validate", f"{RUN}/verify/V1.json")
check("BR-19", 0, rc, "a complete verification validates")
rc, out = br("merge", "--dir", RUN)
m = json.load(open(f"{RUN}/merged.json"))
F = {f["id"]: f for f in m["findings"]}
check("BR-20", (0, ["SEC-02"]), (rc, [f["id"] for f in m["refuted"]]), "merge succeeds and drops the refuted finding")
check("BR-21", ("MEDIUM", "HIGH"), (F["ARCH-01"]["severity"], F["ARCH-01"]["hat_severity"]), "a narrowed finding takes the verifier's severity, keeping the hat's for the record")
check("BR-22", (False, [other[0]]), (other[0] in F, F["SEC-01"].get("duplicates")), "a duplicate folds into the finding it duplicates")
check("BR-23", 1, m["scores"]["a1"]["security"], "an agent's score under a hat is its worst verified finding (CRITICAL = 1)")
check("BR-24", 3, m["scores"]["a1"]["architect"], "…a narrowed HIGH→MEDIUM scores 3")
check("BR-25", 5, m["scores"]["a2"]["architect"], "a covered agent with no findings scores 5")
unsampled = [f["id"] for f in sec if f["id"] not in ids]
check("BR-25b", ("verified", True), (m["score_basis"]["a1"]["security"], "*" in open(f"{RUN}/scorecard.md").read() or not unsampled),
      "the score basis says whether the worst finding was verified; unsampled ones are starred")
check("BR-26", True, any(c["id"] == "ARCH-01" and c["direction"] == "down" for c in m["severity_changes"]), "severity changes are recorded with direction")
sc = open(f"{RUN}/scorecard.md").read()
check("BR-27", True, "| a1 |" in sc and "| V1 | fable |" in sc and "## Refuted" in sc, "scorecard.md has the table, verifier stats and refuted list")

# a verifier that changed nothing across >= 10 findings is flagged
RUN2 = os.path.join(W, "docs", "board-review-2026-10-02-debate")
many = [finding(f"SEC-{i:02d}", "HIGH") for i in range(1, 12)]
write(f"{RUN2}/hats/security.json", hat("security", many, coverage=("a1",), targets=("a1",)))
br("select", "--dir", RUN2)
write(f"{RUN2}/verify/V1.json", {"schema": "sdlc.board-verification/v1", "verifier": "V1", "model": "fable", "hats": ["security"],
                                  "verdicts": [v(f["id"]) for f in many]})
rc, out = br("merge", "--dir", RUN2)
check("BR-28", (0, True), (rc, "changed nothing across 11 findings" in out), "a verifier that confirmed everything unchanged is flagged")
m2 = json.load(open(f"{RUN2}/merged.json"))
check("BR-29", None, m2["scores"]["a1"].get("architect"), "a hat that didn't run has no score (not a clean 5)")
rc, out = br("compare", f"{RUN}/merged.json", f"{RUN2}/merged.json")
check("BR-30", (0, True), (rc, "| a1 |" in out and "Score movement" in out), "compare shows per-agent score movement between runs")

# ---------------------------------------------------------------- wiring lint
cmd = open(os.path.join(REPO, ".claude/commands/board-review.md")).read()
sys.path.insert(0, os.path.dirname(BR))
import importlib.util
spec = importlib.util.spec_from_file_location("brm", BR)
assert spec and spec.loader
brm = importlib.util.module_from_spec(spec); spec.loader.exec_module(brm)
missing = [h for h in brm.HATS if not os.path.isfile(os.path.join(REPO, f".claude/skills/review/board-review/{h}.md"))]
check("BL-01", [], missing, "every hat the tool knows has a checklist file")
unnamed = [h for h in brm.HATS if f"~/.claude/skills/review/board-review/{h}.md" not in cmd]
check("BL-02", [], unnamed, "the command names every hat checklist by path")
check("BL-03", True, cmd.count("run_in_background: false") >= 2 and "model: fable" in cmd, "hats and verifiers are spawned in the foreground; verifiers on Fable")
proto = open(os.path.join(REPO, ".claude/skills/review/board-review/protocol.md")).read()
check("BL-04", True, "Report everything you find" in proto and "removes the hat's severity" in proto, "the protocol asks hats for everything and verifies blind")
prefixes = {h: re.search(r"Prefix: `(\w+)`", open(os.path.join(REPO, f".claude/skills/review/board-review/{h}.md")).read()) for h in brm.HATS}
check("BL-05", brm.HATS, {h: (m.group(1) if m else None) for h, m in prefixes.items()}, "each checklist states the id prefix the validator enforces")

shutil.rmtree(W, ignore_errors=True)
print("─" * 44)
print(f"board-review: {total - fails} passed, {fails} failed")
sys.exit(1 if fails else 0)
