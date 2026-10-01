#!/usr/bin/env python3
"""Tests for the decision debate system (docs/DEBATE_AND_BOARD_REVIEW_2026-09-30.md, D1-D11).

DS-*: .claude/hooks/debate-status.py on synthetic debate directories — classification by content,
legacy names, the request/verdict contract, second opinions, security's hardened default, withdrawn,
overrides, phase scoping.
DL-*: lint of the debate prompts and wiring, so a fix can't silently regress: one naming contract,
foreground spawns, no minute budgets or first-option fallbacks, no advocate scores, a rubric per
domain whose weights sum to 100, NEEDS_DECISION in every agent's contract, the depth cap, T-007.
Exit 0 = all pass.
"""
import glob, json, os, re, shutil, subprocess, sys, tempfile

sys.dont_write_bytecode = True  # the lint imports hook modules; keep __pycache__ out of .claude/hooks

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DS = os.path.join(REPO, ".claude", "hooks", "debate-status.py")
W = tempfile.mkdtemp(prefix="debate.")
fails = total = 0


def check(cid, want, got, label):
    global fails, total
    total += 1
    ok = want == got
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'} {cid:5} {label}" + ("" if ok else f"\n      want={want!r}\n      got ={got!r}"))


def read(rel):
    return open(os.path.join(REPO, rel), encoding="utf-8").read()


def fresh():
    shutil.rmtree(os.path.join(W, "agent_state"), ignore_errors=True)
    shutil.rmtree(os.path.join(W, "docs"), ignore_errors=True)
    os.makedirs(os.path.join(W, "agent_state", "debates"))


def put(name, doc):
    p = os.path.join(W, "agent_state", "debates", name)
    with open(p, "w") as fh:
        fh.write(doc if isinstance(doc, str) else json.dumps(doc))


def decisions(text):
    os.makedirs(os.path.join(W, "docs"), exist_ok=True)
    open(os.path.join(W, "docs", "DECISIONS.md"), "w").write(text)


def status(*args):
    p = subprocess.run([sys.executable, DS, "--root", W, "--json", *args], capture_output=True, text=True)
    try:
        rep = json.loads(p.stdout)
    except ValueError:
        rep = {"topics": [], "blocking": [], "error": p.stdout + p.stderr}
    return p.returncode, rep, {t["topic"]: t for t in rep.get("topics", [])}


def req(topic, phase: "int | None" = 1, **kw):
    d = {"schema": "sdlc.debate-request/v1", "type": "debate_request", "topic": topic, "phase": phase,
         "from_agent": "backend_developer", "decision": "pick", "impact": "HIGH", "domain": "architecture",
         "blocking": True, "options": [{"id": "A", "label": "a"}, {"id": "B", "label": "b"}]}
    d.update(kw)
    put(f"{topic}.request.json", d)


def ver(topic, verdict="A", **kw):
    d = {"schema": "sdlc.debate-verdict/v1", "topic": topic, "phase": 1, "status": "RESOLVED", "verdict": verdict,
         "verdict_label": "a", "confidence": "HIGH", "scores": {"A": {"total": 8}, "B": {"total": 5}},
         "rationale": "r", "decisive_factor": "brd", "decision_id": "D-001"}
    d.update(kw)
    put(f"{topic}.verdict.json", d)


PROMOTED = "### D-001 — x\n- link: agent_state/debates/{t}.verdict.json\n"

# ---------------------------------------------------------------- DS: debate-status.py
fresh(); req("cache")
rc, rep, T = status("--check")
check("DS-01", ("pending", 2), (T["cache"]["status"], rc), "a blocking request with no verdict is pending and fails --check")
ver("cache"); decisions(PROMOTED.format(t="cache"))
rc, rep, T = status("--check")
check("DS-02", ("resolved", 0, []), (T["cache"]["status"], rc, T["cache"]["review"]), "a promoted HIGH-confidence verdict is resolved with nothing to review")

fresh(); req("cache"); ver("cache", verdict="C"); decisions(PROMOTED.format(t="cache"))
rc, rep, T = status("--check")
check("DS-03", ("invalid", 2), (T["cache"]["status"], rc), "a verdict for an option the request never offered is invalid")

fresh(); req("cache", options=[{"id": "A"}])
rc, rep, T = status("--check")
check("DS-04", True, any("fewer than 2 options" in p for p in T["cache"]["problems"]), "a request with one option breaks the contract")
fresh(); req("Cache Choice")
rc, rep, T = status()
check("DS-05", True, any("slug" in p for p in T["Cache Choice"]["problems"]), "a topic that isn't a slug breaks the contract")
fresh(); req("cache", domain="vibes")
rc, rep, T = status()
check("DS-06", True, any("domain" in p for p in T["cache"]["problems"]), "an unknown domain breaks the contract (it picks the rubric)")

# second opinion: required for HIGH impact below HIGH confidence; disagreement goes to review
fresh(); req("db"); ver("db", confidence="MEDIUM"); decisions(PROMOTED.format(t="db"))
rc, rep, T = status("--check")
check("DS-07", (2, True), (rc, any("second opinion" in b for b in rep["blocking"])), "a close HIGH call without a second opinion blocks")
put("db.second-opinion.json", {"schema": "sdlc.debate-second-opinion/v1", "topic": "db", "model": "fable", "verdict": "A"})
rc, rep, T = status("--check")
check("DS-08", (0, "resolved"), (rc, T["db"]["status"]), "a second opinion file is not mistaken for a verdict, and an agreeing one clears the block")
put("db.second-opinion.json", {"schema": "sdlc.debate-second-opinion/v1", "topic": "db", "model": "fable", "verdict": "B"})
rc, rep, T = status("--check")
check("DS-09", (0, True), (rc, any("second opinion (fable) chose B" in r for r in T["db"]["review"])), "a disagreeing second opinion goes to review, not the gate")
fresh(); req("db", impact="MEDIUM"); ver("db", confidence="LOW"); decisions(PROMOTED.format(t="db"))
rc, rep, T = status("--check")
check("DS-10", (0, True), (rc, "LOW confidence" in T["db"]["review"]), "MEDIUM impact needs no second opinion; LOW confidence is flagged for review")

# security
fresh(); req("tokens", domain="security"); ver("tokens", verdict="A"); decisions(PROMOTED.format(t="tokens"))
rc, rep, T = status("--check")
check("DS-11", ("invalid", 2), (T["tokens"]["status"], rc), "a security verdict that names no hardened_default is invalid")
ver("tokens", verdict="A", hardened_default="B", confidence="HIGH")
rc, rep, T = status()
check("DS-12", True, any("not the hardened default" in r for r in T["tokens"]["review"]), "a security verdict that isn't the hardened default is flagged")
ver("tokens", verdict="B", hardened_default="B", status="INCOMPLETE", confidence="MEDIUM")
rc, rep, T = status()
check("DS-13", True, any("INCOMPLETE verdict must have confidence LOW" in p for p in T["tokens"]["problems"]), "INCOMPLETE with confidence above LOW is invalid")

# legacy names, auto-resolved, withdrawn, override, unattributed, phase scope
fresh(); put("step2-database_choice.json", {"type": "debate_request", "decision": "db", "options": [{"id": "A"}, {"id": "B"}], "impact": "HIGH"})
rc, rep, T = status("--check")
check("DS-14", ("pending", 2), (T.get("step2-database_choice", {}).get("status"), rc), "a legacy <step>-<topic>.json request is found (the old gate glob missed it)")
put("database_choice-verdict.json", {"topic": "database_choice", "verdict": "A", "confidence": "HIGH"})
rc, rep, T = status("--check")
check("DS-15", ("resolved", 0, True), (T["database_choice"]["status"], rc, "legacy verdict format" in T["database_choice"]["review"]), "…and matched to its legacy <topic>-verdict.json, flagged as legacy")
fresh(); req("logfmt"); put("unresolved.json", {"phase": 1, "decisions": [{"topic": "logfmt", "auto_resolved_with": "A", "reason": "escalation_limit_exceeded"}]})
rc, rep, T = status("--check")
check("DS-16", ("auto_resolved", 0), (T["logfmt"]["status"], rc), "a default recorded in unresolved.json resolves the request for the gate")
fresh(); req("old", status="withdrawn")
rc, rep, T = status("--check")
check("DS-17", ("invalid", 2), (T["old"]["status"], rc), "withdrawing without a reason is invalid")
req("old", status="withdrawn", withdrawn_reason="superseded by D-004, which chose the queue design")
rc, rep, T = status("--check")
check("DS-18", ("withdrawn", 0), (T["old"]["status"], rc), "a withdrawn request with a reason doesn't block")
fresh(); req("auth"); ver("auth", decision_id="D-007"); put("auth.override.json", {"topic": "auth", "user_override": "B", "original_verdict": "A"})
rc, rep, T = status("--check")
check("DS-19", ("overridden", 0), (T["auth"]["status"], rc), "a user override is recognised (not an orphan request) and doesn't block")
fresh(); req("x", phase=None)
rc, rep, T = status("--phase", "3", "--check")
check("DS-20", (2, True), (rc, "request has no phase field" in T["x"]["review"]), "an unattributed pending request blocks every phase's gate")
fresh(); req("later", phase=2)
rc, rep, T = status("--phase", "1", "--check")
check("DS-21", (0, []), (rc, rep["topics"]), "another phase's request is out of scope")
fresh(); req("soft", blocking=False)
rc, rep, T = status("--check")
check("DS-22", (0, "pending"), (rc, T["soft"]["status"]), "a non-blocking pending request is listed but doesn't block")
fresh(); put("notes.json", {"hello": 1}); put("broken.json", "{not json")
rc, rep, T = status()
check("DS-23", 2, len(rep["unrecognized"]), "unrelated and broken JSON files are reported, not misread")
fresh(); req("cache"); ver("cache")
rc, rep, T = status("--check")
check("DS-24", (2, True), (rc, any("never promoted" in b for b in rep["blocking"])), "a v1 verdict missing from docs/DECISIONS.md blocks")
decisions("### D-001 — Use a cache\n- link: elsewhere\n")
rc, rep, T = status("--check")
check("DS-25", 0, rc, "…and the decision_id heading in DECISIONS.md counts as promoted")
p = subprocess.run([sys.executable, DS, "--root", W], capture_output=True, text=True)
check("DS-26", (0, True), (p.returncode, "RESOLVED" in p.stdout), "the human-readable listing renders")

# ---------------------------------------------------------------- DL: prompt and wiring lint
OLD = re.compile(r"-verdict\.json|-request\.json|<step>-<topic>\.json|\{topic\}-(?:research|argument|transcript|verdict)")
offenders = []
for p in glob.glob(os.path.join(REPO, ".claude", "**", "*"), recursive=True):
    if "/worktrees/" in p or not os.path.isfile(p) or not p.endswith((".md", ".sh", ".tmpl")):
        continue
    for i, line in enumerate(open(p, encoding="utf-8", errors="replace"), 1):
        if OLD.search(line) and "older names" not in line and "derived `step2-verdict.json`" not in line:
            offenders.append(f"{os.path.relpath(p, REPO)}:{i}")
check("DL-01", [], offenders, "no agent, command or skill uses the old debate file names (one naming contract)")

mod = read(".claude/agents/core/debate_moderator.md")
check("DL-02", True, mod.count("run_in_background: false") >= 3, "the moderator spawns researchers, advocates and arbitrators in the foreground")
check("DL-03", [], re.findall(r"\b\d+[- ]minute|\b\d+ minutes? max", mod), "the moderator has no minute budgets (a subagent has no clock)")
check("DL-04", True, "Agent tool" in mod and "BLOCKED" in mod and "SendMessage" in mod, "the moderator handles a missing Agent tool and doesn't resume children via SendMessage")
for n, f in zip("abc", ("debate_moderator", "debate_arbitrator", "debate-protocol")):
    path = f".claude/agents/core/{f}.md" if f.startswith("debate_") else ".claude/skills/core/debate-protocol.md"
    bad = re.findall(r"[^\n]*(?:auto-resolves with the first option|first option's recommended default)[^\n]*", read(path))
    check(f"DL-05{n}", [], bad, f"{f}: no fallback that picks the first option")
adv = read(".claude/agents/core/debate_advocate.md")
check("DL-06", [], re.findall(r"Score \(1-10\)|Weighted Total|self-assessed", adv), "advocates carry no self-score table")
arb = read(".claude/agents/core/debate_arbitrator.md")
check("DL-07", True, all(k in arb for k in ("PRESENTATION ORDER", "criterion by criterion", "claims_checked", "hardened_default", "MODE: second-opinion")),
      "the arbitrator scores criterion by criterion in the given order, re-checks claims, applies the hardened default, has a second-opinion mode")
check("DL-08", [], re.findall(r"20\d\d 20\d\d", read(".claude/agents/core/debate_researcher.md")), "the researcher doesn't search hard-coded years")

proto = read(".claude/skills/core/debate-protocol.md")
rubric_rows = re.findall(r"^\| `(\w+)` \| (.+) \|$", proto.split("## Rubrics by domain")[1].split("### Score anchors")[0], re.M)
domains = {d: sum(int(w) for w in re.findall(r"(\d+)\**(?: ·|$)", row.replace("**", ""))) for d, row in rubric_rows}
sys.path.insert(0, os.path.dirname(DS))
import importlib.util
spec = importlib.util.spec_from_file_location("ds", DS)
assert spec and spec.loader
ds = importlib.util.module_from_spec(spec); spec.loader.exec_module(ds)
check("DL-09", sorted(ds.DOMAINS), sorted(domains), "the protocol has one rubric per domain debate-status accepts")
check("DL-10", {d: 100 for d in domains}, domains, "every rubric's weights sum to 100")
crit = set(re.findall(r"(\w+) \d+", " ".join(r for _, r in rubric_rows).replace("**", "")))
anchored = set(re.findall(r"^\| (\w+) \|", proto.split("### Score anchors")[1].split("## Confidence")[0], re.M)) - {"Criterion"}
check("DL-11", sorted(crit), sorted(crit & anchored), "every rubric criterion has 2/5/8 anchors")
check("DL-12", True, "security_posture 35" in proto.replace("**", ""), "the security rubric weighs security posture heaviest")

contract = read(".claude/skills/core/agent-common.md")
check("DL-13", True, "NEEDS_DECISION <topic>" in contract and "Finish in this run" in contract and "run_in_background: false" in contract,
      "the operating contract has the NEEDS_DECISION hand-back, finish-in-this-run and foreground spawning")
agents = glob.glob(os.path.join(REPO, ".claude/agents/core/*.md")) + glob.glob(os.path.join(REPO, ".claude/agents/templates/*.tmpl"))
missing = [os.path.basename(a) for a in agents if "NEEDS_DECISION <topic>" not in open(a).read()]
check("DL-14", [], missing, "every agent carries the synced contract (run .claude/agents/_sync-contract.sh)")
settings = json.loads(read(".claude/settings.json"))
check("DL-15", "2", settings.get("env", {}).get("CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH"), "project settings cap nesting at parent → moderator → debate team")
orch = read(".claude/commands/develop-orchestrator.md")
check("DL-16", True, "debate-status.py" in orch.split("### Wave 0c")[1].split("\n```\n")[0] and "NEEDS_DECISION <topic>" in orch,
      "the orchestrator stages debate-status.py and handles NEEDS_DECISION returns")
gate = read(".claude/hooks/verify-gate.sh")
check("DL-17", True, "debate-status.py" in gate and "(f) no pending debate" in gate, "verify-gate.sh runs the debate check")
rub = json.loads(read("agent_state/eval/suite/T-007-debate/rubric.json"))
check("DL-18", 1.0, round(sum(r["weight"] for r in rub["rubric"]), 6), "eval T-007-debate exists and its weights sum to 1.0")

shutil.rmtree(W, ignore_errors=True)
print("─" * 44)
print(f"debate: {total - fails} passed, {fails} failed")
sys.exit(1 if fails else 0)
