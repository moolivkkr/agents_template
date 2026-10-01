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
import importlib.util
_spec = importlib.util.spec_from_file_location("ds", DS)
assert _spec and _spec.loader
ds = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(ds)
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
         "kind": "decision", "blocking": True, "options": [{"id": "A", "label": "a"}, {"id": "B", "label": "b"}]}
    d.update(kw)
    put(f"{topic}.request.json", d)
    return d


def scores_for(domain, values):
    """values: {option: score for every criterion} or {option: (score, {criterion: override})}."""
    out = {}
    for o, v in values.items():
        base, over = (v, {}) if not isinstance(v, tuple) else v
        out[o] = {c: over.get(c, base) for c in ds.RUBRICS[domain]}
    return out


BRIEF = ("# Research: option {i}\n\n## Evidence by criterion\n| Criterion | For | Against | Source |\n|---|---|---|---|\n"
         "| brd_alignment | meets FR-020 directly | none found | https://example.org/{i}/docs |\n"
         "| feasibility | used in production by the team's stack | migration effort | docs/IMPLEMENTATION_GUIDELINES.md:42 |\n")
ARGUMENT = ("# Argument for option {i}\n\n## Top strengths\n1. Meets FR-020 directly (research {t}.research-{i}.md, row 1).\n"
            "## Why the alternatives fit worse\n- They need application-level integrity checks.\n"
            "## Weaknesses I acknowledge\n- Migration effort; mitigated by expand/contract.\n")


def debate(topic, verdict="A", values=None, phase=1, promote=True, artifacts=True, second=None, apply=True, **kw):
    """Write a complete, valid debate for an existing request: briefs, arguments, transcript, a v1 verdict
    whose request_sha, scores, gap and confidence agree, and its D-NNN. kw overrides verdict fields."""
    r = load_req(topic)
    domain = r.get("domain") or "architecture"
    ids = [o["id"] for o in r["options"]]
    values = values or {i: (8 if i == verdict else 5) for i in ids}
    sc = scores_for(domain, values)
    t = ds.totals(sc, ids, ds.RUBRICS[domain])
    ranked = sorted(t.values(), reverse=True)
    gap = round(ranked[0] - ranked[1], 2)
    if artifacts:
        for i in ids:
            put(f"{topic}.research-{i}.md", BRIEF.format(i=i))
            if r.get("impact") == "HIGH":
                put(f"{topic}.argument-{i}.md", ARGUMENT.format(i=i, t=topic))
        put(f"{topic}.transcript.md", "# Transcript\n" + "".join(f"- debate_researcher {i}: COMPLETE, {topic}.research-{i}.md\n" for i in ids))
    did = "D-%03d" % (abs(hash(topic)) % 900 + 1)
    v = {"schema": "sdlc.debate-verdict/v1", "topic": topic, "phase": phase, "impact": r.get("impact"), "domain": domain,
         "status": "RESOLVED", "verdict": verdict, "verdict_label": next(o["label"] for o in r["options"] if o["id"] == verdict),
         "confidence": ds.band(gap), "rubric": domain, "presentation_order": list(reversed(ids)), "scores": sc, "gap": gap,
         "decisive_factor": "x", "claims_checked": [{"claim": "c", "source": "https://example.org", "result": "confirmed"}],
         "rationale": "r", "request_sha": ds.request_sha(r), "decision_id": did}
    if domain == "security":
        v["hardened_default"] = verdict
    v.update(kw)
    put(f"{topic}.verdict.json", v)
    if second is not None:
        put(f"{topic}.second-opinion.json", dict({"schema": "sdlc.debate-second-opinion/v1", "topic": topic, "model": "claude-fable-5-1",
                                                  "verdict": verdict, "presentation_order": ids, "scores": sc,
                                                  "request_sha": ds.request_sha(r)}, **second))
    if promote:
        add_decision(did, topic, decision=v["verdict_label"])
    if apply:
        r2 = load_req(topic); r2["applied"] = verdict; put(f"{topic}.request.json", r2)
    return v


def load_ver(topic):
    return json.load(open(os.path.join(W, "agent_state", "debates", f"{topic}.verdict.json")))


def reverse_decision(did):
    p = os.path.join(W, "docs", "DECISIONS.md")
    text = open(p).read()
    text = re.sub(rf"(### {re.escape(did)}\b.*?- status:) active", r"\1 reversed", text, count=1, flags=re.S)
    open(p, "w").write(text)


def load_req(topic):
    return json.load(open(os.path.join(W, "agent_state", "debates", f"{topic}.request.json")))


def add_decision(did, topic, link=None, decision=None, status="active"):
    os.makedirs(os.path.join(W, "docs"), exist_ok=True)
    with open(os.path.join(W, "docs", "DECISIONS.md"), "a") as fh:
        fh.write(f"\n### {did} — {topic}\n- status: {status}\n- link: {link or f'agent_state/debates/{topic}.verdict.json'}\n"
                 + (f"- decision: > {decision}\n" if decision else ""))


# ---------------------------------------------------------------- DS: debate-status.py
fresh(); req("cache")
rc, rep, T = status("--check")
check("DS-01", ("pending", 2), (T["cache"]["status"], rc), "a blocking request with no verdict is pending and fails --check")
debate("cache")
rc, rep, T = status("--check")
check("DS-02", ("resolved", 0, []), (T["cache"]["status"], rc, T["cache"]["review"]), "a complete, promoted, clear-cut debate is resolved with nothing to review")

fresh(); req("cache"); debate("cache", verdict="A", values={"A": 8, "B": 5}); v = json.load(open(os.path.join(W, "agent_state/debates/cache.verdict.json"))); v["verdict"] = "C"; put("cache.verdict.json", v)
rc, rep, T = status("--check")
check("DS-03", ("invalid", 2), (T["cache"]["status"], rc), "a verdict for an option the request never offered is invalid")
fresh(); req("cache", options=[{"id": "A", "label": "a"}])
rc, rep, T = status("--check")
check("DS-04", True, any("fewer than 2 options" in p for p in T["cache"]["problems"]), "a request with one option breaks the contract")
fresh(); req("Cache Choice")
rc, rep, T = status()
check("DS-05", True, any("slug" in p for p in T["Cache Choice"]["problems"]), "a topic that isn't a slug breaks the contract")
fresh(); req("cache", domain="vibes")
rc, rep, T = status()
check("DS-06", True, any("domain" in p for p in T["cache"]["problems"]), "an unknown domain breaks the contract (it picks the rubric)")

# unreadable and misformatted debate files (board TEST-01)
fresh(); put("token_storage.request.json", '{"schema": "sdlc.debate-request/v1", "topic": "token_storage",}')
rc, rep, T = status("--check")
check("DS-07", (2, True), (rc, any("not valid JSON" in b for b in rep["blocking"])), "a request that isn't valid JSON blocks instead of being ignored")
fresh(); put("token_storage.request.json", {"schema": "v1.0", "type": "debate-request", "topic": "token_storage", "options": []})
rc, rep, T = status("--check")
check("DS-08", (2, True), (rc, any("isn't in its format" in b for b in rep["blocking"])), "a request with a mistyped schema/type marker blocks")
fresh(); put("notes.json", {"hello": 1})
rc, rep, T = status("--check")
check("DS-09", (0, ["agent_state/debates/notes.json"]), (rc, rep["unrecognized"]), "an unrelated JSON file is listed, not blocking")
fresh(); req("cache", decisions=["D-002"])
rc, rep, T = status("--check")
check("DS-10", ("pending", 2), (T.get("cache", {}).get("status"), rc), "a v1 request that cites prior decisions isn't misread as unresolved.json")

# a verdict must be v1, complete and consistent with its own scores (board TEST-02, AI-02, TEST-04, TEST-12)
fresh(); req("db"); put("db.verdict.json", {"topic": "db", "verdict": "A", "confidence": "LOW"})
rc, rep, T = status("--check")
check("DS-11", ("invalid", 2), (T["db"]["status"], rc), "a schema-less verdict for a v1 request is invalid, not a quiet legacy pass")
fresh(); req("db"); debate("db", values={"A": 7, "B": (7, {"ecosystem": 6})}, confidence="HIGH", second={})
rc, rep, T = status("--check")
check("DS-12", (2, True), (rc, any("gap of 0.1" in p and "LOW" in p for p in T["db"]["problems"])), "confidence HIGH on a 0.1 gap is recomputed and rejected")
fresh(); req("db"); debate("db", verdict="A", values={"A": (7, {"brd_alignment": 6}), "B": 7})
rc, rep, T = status("--check")
check("DS-13", (2, True), (rc, any("below B" in p for p in T["db"]["problems"])), "a verdict for the lower-scoring option is rejected")
fresh(); req("db"); debate("db", scores={"A": {"total": 8}, "B": {"total": 5}})
rc, rep, T = status("--check")
check("DS-14", (2, True), (rc, any("no 1-10 score for" in p for p in T["db"]["problems"])), "scores without every rubric criterion are rejected")
fresh(); req("db", domain="data_model"); debate("db", rubric="architecture")
rc, rep, T = status("--check")
check("DS-15", (2, True), (rc, any("rubric is 'architecture'" in p for p in T["db"]["problems"])), "a verdict scored on another domain's rubric is rejected")
fresh(); req("db"); debate("db", claims_checked=[])
rc, rep, T = status("--check")
check("DS-16", (2, True), (rc, any("claims_checked" in p for p in T["db"]["problems"])), "a verdict whose decisive claim was never re-checked at source is rejected")
fresh(); req("db"); debate("db", artifacts=False)
rc, rep, T = status("--check")
check("DS-17", (2, True), (rc, any("no debate behind the verdict" in p for p in T["db"]["problems"])), "a verdict with no research, arguments or transcript is rejected")
fresh(); req("db"); v = debate("db"); v["scores"]["A"]["total"] = 9.9; put("db.verdict.json", v)
rc, rep, T = status("--check")
check("DS-18", True, any("total is 9.9" in p for p in T["db"]["problems"]), "a self-reported total that doesn't match the scores is caught")

# second opinions (board TEST-05, ARCH-11, AI-07)
fresh(); req("db"); debate("db", values={"A": 7, "B": (7, {"brd_alignment": 6})})
rc, rep, T = status("--check")
check("DS-19", (2, True), (rc, any("no second opinion" in b for b in rep["blocking"])), "a close HIGH call without a second opinion blocks")
debate("db", values={"A": 7, "B": (7, {"brd_alignment": 6})}, second={})
rc, rep, T = status("--check")
check("DS-20", (0, "resolved"), (rc, T["db"]["status"]), "a valid, agreeing second opinion (reverse order) clears the block")
put("db.second-opinion.json", {})
rc, rep, T = status("--check")
check("DS-21", 2, rc, "an empty second-opinion file does not clear the block")
debate("db", values={"A": 7, "B": (7, {"brd_alignment": 6})}, second={"presentation_order": ["B", "A"]})
rc, rep, T = status("--check")
check("DS-22", (2, True), (rc, any("reverse presentation order" in b for b in rep["blocking"])), "a second opinion that read the same order as the primary is invalid")
debate("db", values={"A": 7, "B": (7, {"brd_alignment": 6})}, second={"verdict": "B", "model": "claude-opus-5-5", "scores": scores_for("architecture", {"A": 6, "B": 7})})
rc, rep, T = status("--check")
check("DS-23", (0, True, True), (rc, any("second opinion (claude-opus-5-5) chose B" in r for r in T["db"]["review"]),
                                 any("not Fable" in r for r in T["db"]["review"])), "a disagreeing second opinion and a non-Fable model go to review")
fresh(); req("db", impact="MEDIUM"); debate("db", values={"A": 7, "B": (7, {"ecosystem": 6})})
rc, rep, T = status("--check")
check("DS-24", (0, True), (rc, "LOW confidence" in T["db"]["review"]), "MEDIUM impact needs no second opinion; LOW confidence is flagged")

# security (board TEST-03, ARCH-10, TEST-08)
fresh(); req("tokens", domain="security"); debate("tokens", verdict="A", hardened_default=None)
rc, rep, T = status("--check")
check("DS-25", ("invalid", 2), (T["tokens"]["status"], rc), "a RESOLVED security verdict that names no hardened_default is invalid")
fresh(); req("tokens", domain="security"); debate("tokens", verdict="A", values={"A": 7, "B": (7, {"operability": 6})}, hardened_default="B", second={})
rc, rep, T = status("--check")
check("DS-26", (2, True), (rc, any("must be the hardened default" in p for p in T["tokens"]["problems"])), "a close security call that isn't the hardened default blocks")
debate("tokens", verdict="A", values={"A": 7, "B": (7, {"operability": 6})}, hardened_default="B", second={}, must_override="NFR-SEC-009 requires header auth for the CLI client")
rc, rep, T = status("--check")
check("DS-27", (0, True), (rc, any("must_override" in r for r in T["tokens"]["review"])), "…unless must_override names the requirement (then it's flagged for review)")
fresh(); req("tokens", domain="security"); debate("tokens", verdict="B", values={"A": 7, "B": (7, {"operability": 6})}, hardened_default="B", second={"verdict": "A", "scores": scores_for("security", {"A": 8, "B": 6})})
rc, rep, T = status("--check")
check("DS-28", (2, True), (rc, any("second opinion disagrees" in b and b.startswith("security debate") for b in rep["blocking"])), "a security call where the second opinion disagrees waits for a person")
put("tokens.override.json", {"topic": "tokens", "user_override": "B", "user_rationale": "keep the hardened cookie", "original_verdict": "B"})
d = load_ver("tokens")["decision_id"]; reverse_decision(d)
add_decision("D-990", "tokens override", link="agent_state/debates/tokens.override.json", decision="b")
rc, rep, T = status("--check")
check("DS-29", ("overridden", 0), (T["tokens"]["status"], rc), "…and the person's recorded choice clears it")
fresh(); req("tokens", domain="security"); debate("tokens", verdict="A", hardened_default=None, status="INCOMPLETE", confidence="LOW", reason="no option is clearly more restrictive", second={})
rc, rep, T = status("--check")
check("DS-30", (2, True), (rc, any("INCOMPLETE: a person decides" in b for b in rep["blocking"])), "a security debate with no hardened option is valid INCOMPLETE and waits for a person")

# binding, ledger, legacy, auto-resolution, withdrawal, overrides, phases (board ARCH-05, TEST-14, TEST-16, TEST-17, TEST-09, TEST-11, ARCH-06)
fresh(); req("db"); debate("db"); req("db", options=[{"id": "A", "label": "a"}, {"id": "B", "label": "b"}, {"id": "C", "label": "c"}])
rc, rep, T = status("--check")
check("DS-31", ("stale", 2), (T["db"]["status"], rc), "a verdict for an earlier version of the request is stale and blocks")
fresh(); req("db", phase=5); debate("db", phase=3)
rc, rep, T = status("--check")
check("DS-32", True, any("phase 3, the request is phase 5" in p for p in T["db"]["problems"]), "a verdict from another phase doesn't answer this request")
fresh(); req("db"); debate("db", promote=False); add_decision("D-777", "something-else", link="agent_state/debates/other.verdict.json"); v = json.load(open(os.path.join(W, "agent_state/debates/db.verdict.json"))); v["decision_id"] = "D-777"; put("db.verdict.json", v)
rc, rep, T = status("--check")
check("DS-33", (2, True), (rc, any("D-NNN in docs/DECISIONS.md linking" in b for b in rep["blocking"])), "a decision_id pointing at an unrelated ledger entry doesn't count as promoted")
fresh(); put("step2-database_choice.json", {"type": "debate_request", "decision": "db", "options": [{"id": "A"}, {"id": "B"}], "impact": "HIGH"})
rc, rep, T = status("--check")
check("DS-34", ("pending", 2), (T.get("step2-database_choice", {}).get("status"), rc), "a legacy <step>-<topic>.json request is found")
put("database_choice-verdict.json", {"topic": "database_choice", "verdict": "A", "confidence": "HIGH"})
rc, rep, T = status("--check")
check("DS-35", ("resolved", 0, True), (T["database_choice"]["status"], rc, "legacy verdict format" in T["database_choice"]["review"]), "…and matched to its legacy verdict, flagged as legacy")
fresh(); req("auth-token"); put("token.verdict.json", {"schema": "sdlc.debate-verdict/v1", "topic": "token", "verdict": "A", "confidence": "HIGH"})
rc, rep, T = status("--check")
check("DS-36", ("pending", 2), (T["auth-token"]["status"], rc), "a v1 request is never suffix-matched to an unrelated verdict")
fresh(); req("logfmt"); put("unresolved.json", {"decisions": [{"topic": "logfmt", "phase": 1, "auto_resolved_with": "A", "reason": "escalation_limit_exceeded"}]})
rc, rep, T = status("--check")
check("DS-37", ("auto_resolved", 0), (T["logfmt"]["status"], rc), "a default recorded in unresolved.json resolves the request for the gate")
fresh(); req("tokens", domain="security"); put("unresolved.json", {"decisions": [{"topic": "tokens", "phase": 1, "auto_resolved_with": "A"}]})
rc, rep, T = status("--check")
check("DS-38", ("invalid", 2), (T["tokens"]["status"], rc), "a security decision auto-resolved without hardened: true is invalid")
put("unresolved.json", {"decisions": [{"topic": "tokens", "phase": 1, "auto_resolved_with": "Z", "hardened": True}]})
rc, rep, T = status("--check")
check("DS-39", ("invalid", 2), (T["tokens"]["status"], rc), "an auto-resolution to an option the request doesn't offer is invalid")
fresh(); req("old", status="withdrawn", withdrawn_reason="dup")
rc, rep, T = status("--check")
check("DS-40", ("invalid", 2), (T["old"]["status"], rc), "withdrawing with no real reason is invalid")
req("old", status="withdrawn", withdrawn_reason="superseded by D-004, which chose the queue design")
rc, rep, T = status("--check")
check("DS-41", ("withdrawn", 0), (T["old"]["status"], rc), "a withdrawn request with a reason doesn't block")
fresh(); req("auth"); put("auth.override.json", {"topic": "auth", "user_override": "A"})
rc, rep, T = status("--check")
check("DS-42", ("invalid", 2), (T["auth"]["status"], rc), "an override with no rationale doesn't silence a request")
put("auth.override.json", {"topic": "auth", "user_override": "A", "user_rationale": "owner chose sessions for the admin app"})
add_decision("D-991", "auth override", link="agent_state/debates/auth.override.json", decision="a")
r2 = load_req("auth"); r2["applied"] = "A"; put("auth.request.json", r2)
rc, rep, T = status("--check")
check("DS-43", ("overridden", 0), (T["auth"]["status"], rc), "a complete override records the person's decision")
fresh(); req("auth", options=[{"id": "A", "label": "a"}]); put("auth.override.json", {"topic": "auth", "user_override": "A", "user_rationale": "owner chose sessions"})
rc, rep, T = status("--check")
check("DS-44", ("invalid", 2), (T["auth"]["status"], rc), "an override can't clear a request that breaks the contract")
fresh(); req("x", phase=None)
rc, rep, T = status("--phase", "3", "--check")
check("DS-45", (2, True), (rc, "request has no phase field" in T["x"]["review"]), "an unattributed pending request blocks every phase's gate")
fresh(); req("later", phase=2)
rc, rep, T = status("--phase", "1", "--check")
check("DS-46", (0, []), (rc, rep["topics"]), "another phase's request is out of scope")
fresh(); req("padded", phase="01")
rc, rep, T = status("--phase", "1", "--check")
check("DS-47", (2, ["padded"]), (rc, [t["topic"] for t in rep["topics"]]), "a zero-padded phase still matches its phase")
fresh(); req("soft", blocking=False, default_taken="A")
rc, rep, T = status("--check")
check("DS-48", (2, "pending"), (rc, T["soft"]["status"]), "a non-blocking request still needs its debate before the gate")
debate("soft", verdict="B", values={"A": 5, "B": 8}, apply=False)
rc, rep, T = status("--check")
check("DS-49", (2, True), (rc, any("the decision is B but backend_developer built option A" in b for b in rep["blocking"])), "a verdict that differs from the default the requester built blocks until it's relaunched")
req("soft", blocking=False, default_taken="A"); debate("soft", verdict="B", values={"A": 5, "B": 8}, apply=False)
r2 = load_req("soft"); r2["applied"] = "B"; put("soft.request.json", r2)
rc, rep, T = status("--check")
check("DS-50", 0, rc, "…and passes once the relaunch is recorded as applied")
fresh(); req("soft", blocking=False)
rc, rep, T = status()
check("DS-51", True, any("default_taken" in p for p in T["soft"]["problems"]), "a non-blocking request must say which default the agent built")
fresh(); req("db"); debate("db")
rc, rep, T = status("--json")
check("DS-52", True, {"agent_state/debates/db.request.json", "agent_state/debates/db.verdict.json", "agent_state/debates/db.research-A.md", "agent_state/debates/db.transcript.md"} <= set(T["db"]["files"]),
      "--json lists each topic's files (what /reset-phase archives)")
p = subprocess.run([sys.executable, DS, "--root", W, "--request-sha", "db"], capture_output=True, text=True)
check("DS-53", (0, ds.request_sha(load_req("db"))), (p.returncode, p.stdout.strip()), "--request-sha prints the hash the arbitrator copies into the verdict")
p = subprocess.run([sys.executable, DS, "--root", W], capture_output=True, text=True)
check("DS-54", (0, True), (p.returncode, "RESOLVED" in p.stdout), "the human-readable listing renders")

# round 2 (board review 2026-09-30-debate-2)
fresh(); req("db"); debate("db", claims_checked=[{"claim": "c", "source": "memory", "result": "unverifiable"}])
rc, rep, T = status("--check")
check("DS-55", (2, True), (rc, any("unverifiable" in p for p in T["db"]["problems"])), "an unverifiable decisive claim caps confidence at MEDIUM (so a close-call check can't be skipped)")
fresh(); req("db"); debate("db"); put("db.transcript.md", open(os.path.join(W, "agent_state/debates/db.transcript.md")).read() + "EVIDENCE INCOMPLETE: B: researcher returned PARTIAL\n")
rc, rep, T = status("--check")
check("DS-56", (2, True), (rc, any("evidence has gaps" in p for p in T["db"]["problems"])), "an evidence gap recorded in the transcript caps confidence at MEDIUM")
fresh(); req("db"); debate("db", values={"A": 7, "B": (7, {"brd_alignment": 6})}, second={"request_sha": "0000000000000000"})
rc, rep, T = status("--check")
check("DS-57", (2, True), (rc, any("earlier version of the request" in b for b in rep["blocking"])), "a second opinion left from an earlier version of the request doesn't count")
fresh(); req("db"); debate("db", values={"A": 7, "B": (7, {"brd_alignment": 6})}, second={"verdict": "B"})
v = load_ver("db"); so = json.load(open(os.path.join(W, "agent_state/debates/db.second-opinion.json"))); so["request_sha"] = v["request_sha"]; put("db.second-opinion.json", so)
rc, rep, T = status("--check")
check("DS-58", (2, True), (rc, any("below its own top option" in b for b in rep["blocking"])), "a second opinion whose verdict contradicts its own scores is invalid")
fresh(); req("db"); debate("db"); add_decision("D-500", "db again", link="agent_state/debates/db.verdict.json", decision="a")
rc, rep, T = status("--check")
check("DS-59", (2, True), (rc, any("2 active D-NNN entries" in b for b in rep["blocking"])), "two active ledger entries for one verdict block")
fresh(); req("db"); v = debate("db", promote=False); add_decision(v["decision_id"], "db", decision="option b, the old choice")
rc, rep, T = status("--check")
check("DS-60", (2, True), (rc, any("not the verdict" in b for b in rep["blocking"])), "a ledger entry that records another option blocks")
fresh(); req("auth"); debate("auth"); put("auth.override.json", {"topic": "auth", "user_override": "B", "user_rationale": "owner wants sessions"})
r2 = load_req("auth"); r2["applied"] = "B"; put("auth.request.json", r2)
rc, rep, T = status("--check")
check("DS-61", (2, True), (rc, any("never reached docs/DECISIONS.md" in b for b in rep["blocking"])), "an override that never reached the ledger blocks")
add_decision("D-777", "auth override", link="agent_state/debates/auth.override.json", decision="b")
rc, rep, T = status("--check")
check("DS-62", (2, True), (rc, any("still active" in b for b in rep["blocking"])), "…and so does leaving the overridden verdict's entry active")
reverse_decision(load_ver("auth")["decision_id"])
rc, rep, T = status("--check")
check("DS-63", 0, rc, "…until it's reversed")
fresh(); req("tokens", domain="security", status="withdrawn", withdrawn_reason="no longer needed after the redesign")
rc, rep, T = status("--check")
check("DS-64", (2, True), (rc, any(b.startswith("security debate 'tokens' was withdrawn without a person") for b in rep["blocking"])), "an agent can't withdraw a security debate on its own")
req("tokens", domain="security", status="withdrawn", withdrawn_reason="no longer needed after the redesign", withdrawn_by="human:owner")
rc, rep, T = status("--check")
check("DS-65", (0, True), (rc, any(r.startswith("withdrawn:") for r in T["tokens"]["review"])), "a person's withdrawal passes, and it's on the review list")
fresh(); req("ttl", decision="How long session tokens stay valid")
rc, rep, T = status()
check("DS-66", True, any("looks like a security decision" in p for p in T["ttl"]["problems"]), "a security decision labelled architecture is caught")
req("ttl", decision="How long session tokens stay valid", domain_reason="UX timeout only; token security is D-004")
rc, rep, T = status()
check("DS-67", [], [p for p in T["ttl"]["problems"] if "security" in p], "…unless domain_reason says why it isn't")
fresh(); req("db"); debate("db"); put("db.research-A.md", "x"); put("db.argument-B.md", "y")
rc, rep, T = status("--check")
check("DS-68", (2, True), (rc, any("too thin" in p for p in T["db"]["problems"])), "placeholder research and arguments don't count as a debate")
fresh(); req("db"); debate("db", apply=False)
rc, rep, T = status("--check")
check("DS-69", (2, True), (rc, any("hasn't applied it yet" in b for b in rep["blocking"])), "a blocking request whose requester was never relaunched with the verdict blocks")

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
check("DL-02", True, "pass `false`" in mod and "run_in_background" in mod and mod.count("waiting for all") >= 2 and "child-returns.md" in mod,
      "the moderator waits for its researchers and advocates (run_in_background false where offered) and loads child-returns.md")
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
yrs = {f: re.findall(r"20\d\d[ -]20\d\d|provider 20\d\d", read(f)) for f in (".claude/agents/core/debate_researcher.md",
       ".claude/skills/core/deep-research.md", ".claude/skills/core/auto-research.md")}
check("DL-08", {f: [] for f in yrs}, yrs, "the researcher and its research packs don't hard-code search years")

proto = read(".claude/skills/core/debate-protocol.md")
rubric_rows = re.findall(r"^\| `(\w+)` \| (.+) \|$", proto.split("## Rubrics by domain")[1].split("### Score anchors")[0], re.M)
domains = {d: sum(int(w) for w in re.findall(r"(\d+)\**(?: ·|$)", row.replace("**", ""))) for d, row in rubric_rows}
proto_rubrics = {d: {c: int(w) for c, w in re.findall(r"(\w+) (\d+)", row.replace("**", ""))} for d, row in rubric_rows}
check("DL-09", ds.RUBRICS, proto_rubrics, "the protocol's rubric table and debate-status.py's RUBRICS are the same (criteria and weights)")
check("DL-10", {d: 100 for d in domains}, domains, "every rubric's weights sum to 100")
crit = set(re.findall(r"(\w+) \d+", " ".join(r for _, r in rubric_rows).replace("**", "")))
anchored = set(re.findall(r"^\| (\w+) \|", proto.split("### Score anchors")[1].split("## Confidence")[0], re.M)) - {"Criterion"}
check("DL-11", sorted(crit), sorted(crit & anchored), "every rubric criterion has 2/5/8 anchors")
check("DL-12", True, "security_posture 35" in proto.replace("**", ""), "the security rubric weighs security posture heaviest")

contract = read(".claude/skills/core/agent-common.md")
check("DL-13", True, "NEEDS_DECISION <topic>" in contract and "Finish in this run" in contract and "run_in_background" in contract and "pass up" in contract,
      "the operating contract has the NEEDS_DECISION hand-back, finish-in-this-run, waiting for children and passing a child's question up")
agents = glob.glob(os.path.join(REPO, ".claude/agents/core/*.md")) + glob.glob(os.path.join(REPO, ".claude/agents/templates/*.tmpl"))
missing = [os.path.basename(a) for a in agents if "NEEDS_DECISION <topic>" not in open(a).read()]
check("DL-14", [], missing, "every agent carries the synced contract (run .claude/agents/_sync-contract.sh)")
settings = json.loads(read(".claude/settings.json"))
check("DL-15", "2", settings.get("env", {}).get("CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH"), "project settings cap nesting at parent → moderator → debate team")
orch = read(".claude/commands/develop-orchestrator.md")
check("DL-16", True, "debate-status.py" in orch.split("### Wave 0c")[1].split("\n```\n")[0] and "NEEDS_DECISION <topic>" in orch,
      "the orchestrator stages debate-status.py and handles NEEDS_DECISION returns")
SPAWNERS = ["accept", "autonomous", "benchmark", "demo", "deploy", "design", "develop", "develop-orchestrator", "discuss", "docs",
            "hotfix", "init", "map", "optimize", "plan", "product-workflows", "recon", "reconcile", "review", "rollback", "stitch",
            "test", "ui-audit", "board-review"]
spawn_like = [os.path.basename(p)[:-3] for p in glob.glob(os.path.join(REPO, ".claude/commands/*.md"))
              if re.search(r"subagent_type|\*\*Agent:\*\*|^\s*Spawn `|spawning parallel", open(p).read(), re.M)]
check("DL-19", [], sorted(set(spawn_like) - set(SPAWNERS)), "every command that spawns agents is in the spawner list (add new ones there)")
check("DL-20", [], [c for c in SPAWNERS if "skills/core/child-returns.md" not in read(f".claude/commands/{c}.md")],
      "every spawning command follows child-returns.md (NEEDS_DECISION is handled outside /develop too)")
check("DL-21", True, all(k in arb for k in ("MODE: promote", "Skip any `docs/DECISIONS.md` entry", "initial_reasoning", "REQUEST_SHA")),
      "the second opinion can't see the first judgment, the ledger entry waits for it, and the judge doesn't read the requester's reasoning")
check("DL-22", True, all(k in mod for k in ("MODE: promote", "Fable spawn fails", "Concurrent subagent limit", "NEEDS_INPUT", "EVIDENCE INCOMPLETE")),
      "the moderator promotes after the second opinion, handles a failed Fable spawn, the spawn limit and every child status")
check("DL-24", True, "Read both `problems` and `gate`" in mod and "Never return COMPLETE while `gate`" in mod and "Started but unfinished" in mod
      and "Write the transcript so far" in mod, "the moderator returns what the gate says, resumes unfinished debates and writes its transcript before the arbitrator")
check("DL-25", True, "Don't run `debate-status.py` in this mode" in arb and "word for word" in arb and "evidence_gaps" in arb
      and "Don't change a score to make a problem go away" in arb, "the arbitrator keeps the second opinion blind, names the option in the ledger, records gaps and doesn't game the check")
cr = read(".claude/skills/core/child-returns.md")
check("DL-26", True, all(k in cr for k in ('"applied"', "needs a person", "Before a command finishes", "withdrawn_by", "--link agent_state/debates/<topic>.override.json")),
      "child-returns sets applied, routes needs-a-person, closes open debates before a command ends, guards withdrawals and records overrides")
check("DL-27", [], [c for c in ("plan", "discuss", "design") if "Before a command finishes" not in read(f".claude/commands/{c}.md")],
      "/plan, /discuss and /design decide their debates before /develop builds on them")
routing = read(".claude/skills/core/model-routing.md")
check("DL-23", True, "second opinion on a close HIGH-impact debate" in routing and "/board-review` verifiers" in routing,
      "model-routing.md sanctions the debate second opinion and the board verifiers on Fable")
gate = read(".claude/hooks/verify-gate.sh")
check("DL-17", True, "debate-status.py" in gate and "(f) no pending debate" in gate, "verify-gate.sh runs the debate check")
rub = json.loads(read("agent_state/eval/suite/T-007-debate/rubric.json"))
check("DL-18", 1.0, round(sum(r["weight"] for r in rub["rubric"]), 6), "eval T-007-debate exists and its weights sum to 1.0")

shutil.rmtree(W, ignore_errors=True)
print("─" * 44)
print(f"debate: {total - fails} passed, {fails} failed")
sys.exit(1 if fails else 0)
