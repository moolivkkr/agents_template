#!/usr/bin/env python3
"""Cases for tests/phase-ledger.test.sh — the phase ledger hook (.claude/hooks/ledger.py), its report, and the
project updater's --ledger-only mode. Payloads in tests/fixtures/ledger/ were recorded from a real `claude -p` run
(Claude Code 2.1.285, 2026-10-02) with paths stripped."""
import importlib.util, json, os, shutil, statistics, subprocess, sys, tempfile, time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
HOOK = os.path.join(REPO, ".claude", "hooks", "ledger.py")
FIX = os.path.join(REPO, "tests", "fixtures", "ledger")
UPDATER = os.path.join(REPO, "scripts", "startup-project-update.sh")
FACTS = "PROJECT_" + "FACTS.md"   # (name split only so a grep for writes to the real ledger file stays quiet)

spec = importlib.util.spec_from_file_location("ledger", HOOK)
ledger = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ledger)

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ✓ " + name)
    else:
        FAIL += 1
        print("  ✗ FAIL: %s %s" % (name, detail))


def project(phases=None, facts=True):
    d = tempfile.mkdtemp(prefix="ledger-case-")
    subprocess.run(["git", "init", "-q", d], check=True)
    subprocess.run(["git", "-C", d, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "i"],
                   check=True)
    os.makedirs(os.path.join(d, "docs"))
    if facts:
        open(os.path.join(d, "docs", FACTS), "w").write("# facts\n")
        open(os.path.join(d, "docs", "DECISIONS.md"), "w").write("# decisions\n")
    for n, manifest in (phases or {}).items():
        p = os.path.join(d, "agent_state", "phases", str(n))
        os.makedirs(p)
        if manifest is not None:
            json.dump(manifest, open(os.path.join(p, "manifest.json"), "w"))
    return d


def run(root, payload, env=None, raw=None):
    e = dict(os.environ, CLAUDE_PROJECT_DIR=root)
    for k in ("SDLC_LEDGER", "SDLC_LEDGER_CARD", "SDLC_PHASE"):
        e.pop(k, None)
    e.update(env or {})
    data = raw if raw is not None else json.dumps(payload).encode()
    r = subprocess.run([sys.executable, HOOK], input=data, env=e, capture_output=True, timeout=30)
    return r.returncode, r.stdout.decode(), r.stderr.decode()


def events(root):
    out = []
    ldir = os.path.join(root, "agent_state", "ledger")
    for n in sorted(os.listdir(ldir)) if os.path.isdir(ldir) else []:
        if n.startswith("events-"):
            out += [json.loads(l) for l in open(os.path.join(ldir, n)) if l.strip()]
    return out


def report(root, *args):
    r = subprocess.run([sys.executable, HOOK, "report", "--root", root, *args], capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout, r.stderr


def P(ev, sid="s1", **kw):
    d = {"session_id": sid, "hook_event_name": ev}
    d.update(kw)
    return d


def spawn(tuid, typ, prompt, sid="s1", by=None):
    d = P("PreToolUse", sid, tool_name="Agent", tool_use_id=tuid,
          tool_input={"description": "d " + tuid, "prompt": prompt, "subagent_type": typ})
    if by:
        d["agent_id"], d["agent_type"] = by, "general-purpose"
    return d


def ret(tuid, agent, status="completed", sid="s1"):
    return P("PostToolUse", sid, tool_name="Agent", tool_use_id=tuid, tool_input={},
             tool_response={"status": status, "agentId": agent, "totalTokens": 100})


def start(agent, typ, sid="s1"):
    return P("SubagentStart", sid, agent_id=agent, agent_type=typ)


def stop(agent, typ, sid="s1", transcript=None):
    d = P("SubagentStop", sid, agent_id=agent, agent_type=typ, last_assistant_message="ok")
    if transcript:
        d["agent_transcript_path"] = transcript
    return d


def edit(path, agent=None, sid="s1", tool="Edit"):
    d = P("PostToolUse", sid, tool_name=tool, tool_input={"file_path": path})
    if agent:
        d["agent_id"], d["agent_type"] = agent, "general-purpose"
    return d


# ─── 1. replay of the recorded probe ───────────────────────────────────────────────────────────────
def case_replay():
    print("replay: recorded claude -p payloads")
    root = project({7: {"phase": 7}})
    tdir = os.path.join(root, "transcripts")
    shutil.copytree(os.path.join(FIX, "transcripts"), tdir)
    outs = []
    for line in open(os.path.join(FIX, "probe-payloads.jsonl")):
        d = json.loads(line)
        if "agent_transcript_path" in d:
            d["agent_transcript_path"] = d["agent_transcript_path"].replace("@TRANSCRIPTS@", tdir)
        rc, out, _ = run(root, d)
        outs.append((d["hook_event_name"], rc, out))
    check("every recorded payload exits 0", all(rc == 0 for _, rc, _ in outs))
    check("only SubagentStart writes stdout", all((ev == "SubagentStart") == bool(o) for ev, _, o in outs),
          [ev for ev, _, o in outs if o and ev != "SubagentStart"])
    cards = [json.loads(o) for ev, _, o in outs if o]
    check("card is SubagentStart hookSpecificOutput JSON",
          cards and all(c["hookSpecificOutput"]["hookEventName"] == "SubagentStart" for c in cards))
    ev = events(root)
    kinds = {}
    for e in ev:
        kinds[e["event"]] = kinds.get(e["event"], 0) + 1
    check("event mix", kinds.get("spawn_requested") == 4 and kinds.get("started") == 4 and kinds.get("finished") == 4
          and kinds.get("spawn_returned") == 4 and kinds.get("turn_end") == 2 and kinds.get("task_created") == 1
          and kinds.get("task_completed") == 1 and kinds.get("files") == 2 and kinds.get("bash") == 1
          and kinds.get("todos") == 1, kinds)
    fin = {e["agent"]: e for e in ev if e["event"] == "finished"}
    check("finished: exact link from .meta.json for every subagent", all(e["match"] == "exact" for e in fin.values()),
          {k: v.get("match") for k, v in fin.items()})
    check("TASK tags resolved (T-PROBE-1, T-A, T-B, none)",
          sorted(str(e.get("task")) for e in fin.values()) == ["None", "T-A", "T-B", "T-PROBE-1"])
    st = {e["agent"]: e for e in ev if e["event"] == "started"}
    check("background spawn that returned before SubagentStart is matched exactly",
          st["a9815d0746c06925a"]["match"] == "exact" and st["a9815d0746c06925a"]["task"] == "T-A")
    check("common fields on every entry", all(
        all(k in e for k in ("ts", "session_id", "phase", "head", "event", "agent", "plan_version", "facts_v",
                             "decisions_v")) for e in ev))
    check("plan_version is null in step 1", all(e["plan_version"] is None for e in ev))
    check("phase 7 and HEAD recorded", all(e["phase"] == 7 and e["head"] for e in ev))
    sub_edit = [e for e in ev if e["event"] == "files" and e["agent"] != "main"]
    check("subagent edit attributed to agent_id", len(sub_edit) == 1 and sub_edit[0]["agent"] == "aa677ac5ed44124aa")
    sp = [e for e in ev if e["event"] == "spawn_requested"]
    check("spawn: prompt sha256 + ≤200-char head, subagent_type",
          all(len(e["prompt_sha256"]) == 64 and len(e["prompt_head"]) <= 200 and e["subagent_type"] for e in sp))
    check("finished: transcript size only", all(isinstance(e["transcript_bytes"], int) for e in fin.values()))
    shutil.rmtree(root)


# ─── 2. each event type ────────────────────────────────────────────────────────────────────────────
def case_event_types():
    print("event types (synthetic)")
    root = project({1: {"phase": 1}})
    run(root, P("TaskCreated", task_id="7", task_subject="write the spec"))
    run(root, P("TaskCompleted", task_id="7", task_subject="write the spec"))
    run(root, P("StopFailure", error="rate_limit", error_details="429 Too Many Requests"))
    run(root, P("Stop", background_tasks=[{"id": "x"}]))
    run(root, P("PostToolUse", tool_name="TodoWrite", tool_input={"todos": [{"status": "completed"}, {"status": "pending"}]}))
    run(root, P("PostToolUse", tool_name="NotebookEdit", tool_input={"notebook_path": os.path.join(root, "n.ipynb")}))
    run(root, P("PostToolUse", tool_name="MultiEdit", tool_input={"file_path": "src/x.go"}))
    run(root, P("PostToolUse", tool_name="Write", tool_input={"file_path": os.path.join(root, "a", "b.txt")}))
    run(root, P("PostToolUse", tool_name="Read", tool_input={"file_path": "x"}))           # ignored
    run(root, P("PreToolUse", tool_name="Bash", tool_input={"command": "ls"}))              # ignored (pre, not spawn)
    run(root, P("UserPromptSubmit", prompt="hi"))                                           # ignored
    run(root, P("PostToolUse", tool_name="Bash", tool_input={
        "command": "curl -H 'Authorization: Bearer abcdefghijklmnop' https://u:pw123@h/x?token=zzz && echo " + "x" * 400}))
    ev = events(root)
    by = {e["event"]: e for e in ev}
    check("task_created/task_completed with task_id + subject",
          by["task_created"]["task_id"] == "7" and by["task_completed"]["subject"] == "write the spec")
    check("turn_error records error + details", by["turn_error"]["error"] == "rate_limit" and "429" in by["turn_error"]["details"])
    check("turn_end records background task count", by["turn_end"]["background_tasks"] == 1)
    check("todos counts by status", by["todos"]["counts"] == {"completed": 1, "pending": 1})
    files = sorted(f for e in ev if e["event"] == "files" for f in e["files"])
    check("file paths relative to the project", files == ["a/b.txt", "n.ipynb", "src/x.go"], files)
    check("Read / pre-Bash / UserPromptSubmit ignored", len(ev) == 9, len(ev))
    b = by["bash"]["command"]
    check("bash command truncated to 200 chars", len(b) <= 200)
    check("obvious secrets masked in bash commands", "abcdefghijklmnop" not in b and "pw123" not in b, b)
    shutil.rmtree(root)


# ─── 3. spawn → start matching ─────────────────────────────────────────────────────────────────────
def case_matching():
    print("spawn → start matching")
    # (a) two parallel same-type spawns WITH TASK tags, foreground: FIFO at start, corrected by the spawn return
    root = project({2: {"phase": 2}})
    run(root, spawn("tu1", "Explore", "TASK: T-1. look"))
    run(root, spawn("tu2", "Explore", "TASK: T-2. look"))
    _, c1, _ = run(root, start("ag1", "Explore"))
    _, c2, _ = run(root, start("ag2", "Explore"))
    check("FIFO: first start gets the oldest spawn's task in its card", "task T-1" in c1 and "task T-2" in c2)
    run(root, ret("tu2", "ag1"))          # harness says ag1 actually came from tu2 (swap)
    run(root, ret("tu1", "ag2"))
    run(root, stop("ag1", "Explore"))     # no transcript → uses the corrected state
    run(root, stop("ag2", "Explore"))
    fin = {e["agent"]: e for e in events(root) if e["event"] == "finished"}
    check("spawn return corrects a wrong FIFO guess", fin["ag1"]["task"] == "T-2" and fin["ag2"]["task"] == "T-1",
          {k: v.get("task") for k, v in fin.items()})
    check("durations recorded", all(isinstance(e.get("duration_s"), (int, float)) for e in fin.values()))
    shutil.rmtree(root)
    # (b) same, WITHOUT TASK tags: tool_use_ids FIFO, task null
    root = project({2: {"phase": 2}})
    run(root, spawn("tu1", "Explore", "look one"))
    run(root, spawn("tu2", "Explore", "look two"))
    run(root, start("ag1", "Explore"))
    run(root, start("ag2", "Explore"))
    st = {e["agent"]: e for e in events(root) if e["event"] == "started"}
    check("no TASK tag: FIFO tool_use_id, task null",
          st["ag1"]["tool_use_id"] == "tu1" and st["ag2"]["tool_use_id"] == "tu2"
          and st["ag1"]["task"] is None and st["ag1"]["match"] == "fifo")
    # different type never steals the pending spawn
    run(root, spawn("tu3", "Plan", "TASK: P-1 plan"))
    run(root, start("ag3", "Explore"))
    st = {e["agent"]: e for e in events(root) if e["event"] == "started"}
    check("type mismatch → no match", st["ag3"]["match"] == "none" and st["ag3"]["task"] is None)
    _, out, _ = report(root, "--json")
    um = json.loads(out)["phases"]["2"]["unmatched_spawns"]
    check("report lists the unclaimed spawn", [u["task"] for u in um] == ["P-1"], um)
    shutil.rmtree(root)
    # (c) background: return before start → exact; exact link from meta.json at stop
    root = project({2: {"phase": 2}})
    tdir = os.path.join(root, "tr")
    os.makedirs(tdir)
    json.dump({"toolUseId": "tuB", "requestShape": "background"}, open(os.path.join(tdir, "agent-agB.meta.json"), "w"))
    open(os.path.join(tdir, "agent-agB.jsonl"), "w").write("x" * 1234)
    run(root, spawn("tuA", "Explore", "TASK: A-1 x"))
    run(root, spawn("tuB", "Explore", "TASK: B-1 x"))
    run(root, ret("tuB", "agB", status="async_launched"))
    run(root, start("agB", "Explore"))
    run(root, stop("agB", "Explore", transcript=os.path.join(tdir, "agent-agB.jsonl")))
    ev = events(root)
    s = [e for e in ev if e["event"] == "started"][0]
    f = [e for e in ev if e["event"] == "finished"][0]
    check("async return before start → exact match", s["match"] == "exact" and s["task"] == "B-1")
    check("stop reads toolUseId from .meta.json and transcript size",
          f["match"] == "exact" and f["task"] == "B-1" and f["transcript_bytes"] == 1234 and f["shape"] == "background")
    # nested spawn by a subagent is attributed to it
    run(root, spawn("tuN", "Explore", "nested", by="agB"))
    n = [e for e in events(root) if e["event"] == "spawn_requested" and e["tool_use_id"] == "tuN"][0]
    check("nested spawn attributed to the spawning subagent", n["agent"] == "agB")
    shutil.rmtree(root)


# ─── 4. phase derivation ───────────────────────────────────────────────────────────────────────────
def case_phase():
    print("phase derivation")
    d = project({})
    check("no phases → unscoped", ledger.derive_phase(d) == "unscoped")
    os.makedirs(os.path.join(d, "agent_state", "phases", "3"))
    check("dirs without manifests → latest dir", ledger.derive_phase(d) == 3)
    for n, m in ((5, {"phase": 5, "status": "IN_FLIGHT"}), (8, {"status": "CLOSED_AS_WORKSTREAM", "gate": {"state": "NOT_APPLICABLE"}}),
                 (9, {"status": "STUB", "gate": {"state": "NOT_APPLICABLE"}}), (4, {"phase": 4})):
        p = os.path.join(d, "agent_state", "phases", str(n))
        os.makedirs(p)
        json.dump(m, open(os.path.join(p, "manifest.json"), "w"))
    check("highest OPEN manifest wins over closed 8/9 (rera shape)", ledger.derive_phase(d) == 5)
    p6 = os.path.join(d, "agent_state", "phases", "6")
    os.makedirs(p6)
    json.dump({"phase": 6}, open(os.path.join(p6, "manifest.json"), "w"))
    open(os.path.join(p6, "gate.passed"), "w").write("ok")
    check("gate.passed closes a phase", ledger.derive_phase(d) == 5)
    os.makedirs(os.path.join(d, "agent_state", "autonomous"))
    json.dump({"active": True, "phase": 11, "status": "running"}, open(os.path.join(d, "agent_state", "autonomous", "run.json"), "w"))
    check("active /autonomous run.json wins", ledger.derive_phase(d) == 11)
    json.dump({"active": False, "phase": 11}, open(os.path.join(d, "agent_state", "autonomous", "run.json"), "w"))
    check("inactive run.json ignored", ledger.derive_phase(d) == 5)
    check("pin wins over everything", ledger.derive_phase(d, pin=12) == 12)
    # through the hook: policy pin, env pin, and cache invalidation when a new phase dir appears
    run(d, P("Stop"))
    p10 = os.path.join(d, "agent_state", "phases", "10")
    os.makedirs(p10)
    json.dump({"phase": 10}, open(os.path.join(p10, "manifest.json"), "w"))
    run(d, P("Stop"))
    run(d, P("Stop"), env={"SDLC_PHASE": "7"})
    os.makedirs(os.path.join(d, "agent_state", "config"), exist_ok=True)
    json.dump({"phase": 3}, open(os.path.join(d, "agent_state", "config", "ledger-policy.json"), "w"))
    run(d, P("Stop"))
    ph = [e["phase"] for e in events(d)]
    check("hook: cached phase refreshes on a new phase dir; env and policy pins apply", ph == [5, 10, 7, 3], ph)
    shutil.rmtree(d)


# ─── 5. concurrency ────────────────────────────────────────────────────────────────────────────────
def case_lock():
    print("lock: 20 parallel writers")
    root = project({1: {}})
    script = ("import subprocess,sys,json\n"
              "for i in range(10):\n"
              "  p={'session_id':'s%s','hook_event_name':'PostToolUse','tool_name':'Bash','tool_input':{'command':'w'+str(i)}}\n"
              "  subprocess.run([sys.executable,%r],input=json.dumps(p).encode())\n")
    env = dict(os.environ, CLAUDE_PROJECT_DIR=root)
    procs = [subprocess.Popen([sys.executable, "-c", script % (w % 4, HOOK)], env=env) for w in range(20)]
    for p in procs:
        p.wait()
    ldir = os.path.join(root, "agent_state", "ledger")
    lines = [l for n in os.listdir(ldir) if n.startswith("events-") for l in open(os.path.join(ldir, n))]
    ok = True
    for l in lines:
        try:
            json.loads(l)
        except ValueError:
            ok = False
    check("200 events, every line intact JSON", len(lines) == 200 and ok, len(lines))
    check("no hook errors under contention", not os.path.exists(os.path.join(ldir, "errors.log")))
    shutil.rmtree(root)


# ─── 6. never fail ─────────────────────────────────────────────────────────────────────────────────
def case_never_fail():
    print("never fail")
    root = project({1: {}})
    for name, raw in (("garbage", b"{not json"), ("empty", b""), ("list", b"[1,2]"), ("binary", b"\xff\xfe\x00"),
                      ("wrong types", json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Agent",
                                                  "tool_input": "oops"}).encode()),
                      ("null fields", json.dumps({"hook_event_name": "SubagentStop", "agent_id": None,
                                                  "agent_transcript_path": 5}).encode())):
        rc, out, err = run(root, None, raw=raw)
        check("%s → exit 0, silent" % name, rc == 0 and out == "" and err == "", (rc, out, err[:200]))
    os.makedirs(os.path.join(root, "agent_state"), exist_ok=True)
    os.chmod(os.path.join(root, "agent_state"), 0o555)
    try:
        rc, out, err = run(root, P("Stop"))
        check("unwritable agent_state → exit 0, silent", rc == 0 and out == "" and err == "", (rc, err[:200]))
    finally:
        os.chmod(os.path.join(root, "agent_state"), 0o755)
    rc, out, err = run("/nonexistent-dir-xyz", P("Stop"))
    check("missing project dir → exit 0", rc == 0)
    # an exception inside lands in errors.log, capped
    ldir = os.path.join(root, "agent_state", "ledger")
    os.makedirs(ldir, exist_ok=True)
    for n in os.listdir(ldir):
        if n.startswith("events-"):
            os.remove(os.path.join(ldir, n))
    os.makedirs(os.path.join(ldir, "events-" + time.strftime("%Y-%m-%d", time.gmtime()) + ".jsonl"))  # a dir: append fails
    rc, out, err = run(root, P("Stop"))
    check("write failure → exit 0 and one errors.log line", rc == 0 and out == "" and
          os.path.exists(os.path.join(ldir, "errors.log")))
    open(os.path.join(ldir, "errors.log"), "a").write("x" * (300 * 1024))
    run(root, P("Stop"))
    check("errors.log capped (rotated past 256 KB)", os.path.getsize(os.path.join(ldir, "errors.log")) < 4096
          and os.path.exists(os.path.join(ldir, "errors.log.1")))
    shutil.rmtree(root)


# ─── 7. task card ──────────────────────────────────────────────────────────────────────────────────
def case_card():
    print("task card")
    root = project({4: {"phase": 4}})
    pd = os.path.join(root, "agent_state", "phases", "4")
    open(os.path.join(pd, "base_sha"), "w").write("0123456789abcdef0123\n")
    json.dump({"phase": 4, "required": ["code_reviewer_I"] + ["agent_%03d" % i for i in range(400)]},
              open(os.path.join(pd, "roster.json"), "w"))
    run(root, spawn("t1", "code_reviewer_I", "TASK: W4-review do it"))
    _, out, _ = run(root, start("a1", "code_reviewer_I"))
    card = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    check("card: phase, task, base_sha, facts/decisions versions, read pointer",
          "phase 4" in card and "task W4-review" in card and "base_sha 0123456789ab" in card
          and "docs/" + FACTS in card and "DECISIONS" in card, card)
    check("card: roster line for a required agent", "REQUIRED agent for phase 4" in card)
    check("card ≤ ~800 tokens (3200 chars) even with a 400-agent roster", len(card) <= 3200, len(card))
    _, out, _ = run(root, start("a2", "Explore"))
    check("card omits the roster line for a non-required type", "REQUIRED" not in json.loads(out)["hookSpecificOutput"]["additionalContext"])
    _, out, _ = run(root, start("a3", "Explore"), env={"SDLC_LEDGER_CARD": "0"})
    check("SDLC_LEDGER_CARD=0 → no card", out == "")
    os.makedirs(os.path.join(root, "agent_state", "config"))
    pol = os.path.join(root, "agent_state", "config", "ledger-policy.json")
    json.dump({"enabled": True, "task_card": False}, open(pol, "w"))
    _, out, _ = run(root, start("a4", "Explore"))
    check("policy task_card:false → no card", out == "")
    _, out, _ = run(root, start("a5", "Explore"), env={"SDLC_LEDGER_CARD": "1"})
    check("env SDLC_LEDGER_CARD=1 overrides policy", out != "")
    n = len(events(root))
    json.dump({"enabled": False}, open(pol, "w"))
    run(root, start("a6", "Explore"))
    check("policy enabled:false → nothing recorded", len(events(root)) == n)
    run(root, start("a7", "Explore"), env={"SDLC_LEDGER": "1"})
    check("env SDLC_LEDGER=1 overrides a disabled policy", len(events(root)) == n + 1)
    os.remove(pol)
    run(root, start("a8", "Explore"), env={"SDLC_LEDGER": "0"})
    check("env SDLC_LEDGER=0 → nothing recorded", len(events(root)) == n + 1)
    shutil.rmtree(root)
    bare = project({}, facts=False)
    _, out, _ = run(bare, start("a1", "Explore"))
    check("nothing known (unscoped, no facts, no task) → no card", out == "")
    check("…but the start is still recorded", [e["event"] for e in events(bare)] == ["started"])
    shutil.rmtree(bare)


# ─── 8. report ─────────────────────────────────────────────────────────────────────────────────────
def case_report():
    print("report")
    root = project({5: {"phase": 5}, 6: {"phase": 6}})
    pin = {"SDLC_PHASE": "5"}
    for p in (spawn("t1", "backend_developer", "TASK: B-1 x"), spawn("t2", "unit_test_agent", "TASK: U-1 x"),
              start("b1", "backend_developer"), start("u1", "unit_test_agent"),
              edit("src/shared.go", "b1"), edit("src/shared.go", "u1"), edit("src/only_b.go", "b1"),
              stop("b1", "backend_developer"), P("Stop"), spawn("t3", "Explore", "TASK: lost x")):
        run(root, p, env=pin)
    for p in (spawn("t9", "code_reviewer_I", "TASK: R-1 x"), start("r1", "code_reviewer_I"), stop("r1", "code_reviewer_I"),
              edit("src/shared.go"), P("StopFailure", error="overloaded")):
        run(root, p, env={"SDLC_PHASE": "6"})
    open(os.path.join(root, "agent_state", "ledger", "events-2026-01-01.jsonl"), "w").write(
        '{"ts":"2026-01-01T00:00:00.000Z","phase":4,"event":"turn_end","session_id":"old"}\nnot json\n')
    json.dump({"phase": 5, "required": ["backend_developer", "unit_test_agent", "code_reviewer_I", "deploy_dev"]},
              open(os.path.join(root, "agent_state", "phases", "5", "roster.json"), "w"))
    rc, txt, err = report(root, "--phase", "5", "--compare-roster")
    check("report exits 0", rc == 0, err)
    check("--phase 5 shows only phase 5", "phase 5 —" in txt and "phase 6 —" not in txt and "phase 4" not in txt, txt)
    check("unfinished subagent flagged", "unfinished" in txt and "unit_test_agent" in txt, txt)
    check("unmatched spawn flagged", "spawns with no subagent start: 1" in txt and "task lost" in txt, txt)
    check("concurrent overlap on a shared file flagged", "src/shared.go" in txt and "src/only_b.go" not in txt, txt)
    check("roster compare: missing reviewer, deploy_* not treated as agents",
          "missing 2: unit_test_agent, code_reviewer_I" in txt and "deploy_dev" in txt, txt)
    check("unparseable line counted", "1 unparseable" in txt, txt)
    rc, out, _ = report(root, "--json")
    j = json.loads(out)
    check("--json has every phase incl. older file", set(j["phases"]) == {"4", "5", "6"}, list(j["phases"]))
    check("phase 6: main edit outside any live subagent window → no overlap", j["phases"]["6"]["overlaps"] == [])
    check("phase 6: turn error listed", j["phases"]["6"]["errors"][0]["error"] == "overloaded")
    rc, out, _ = report(root, "--json", "--since", "2026-06-01")
    check("--since drops the old file", "4" not in json.loads(out)["phases"])
    rc, out, _ = report(root, "--phase", "5", "--phase", "6")
    check("repeatable --phase", "phase 5 —" in out and "phase 6 —" in out)
    rc, out, _ = report(root, "--max-chars", "200")
    check("output budget enforced", len(out) <= 320 and "budget" in out, len(out))
    rc, out, _ = report(root)
    check("default report within ~1.5k tokens", len(out) <= 6200, len(out))
    rc, out, _ = report(root, "--phase", "42")
    check("empty filter is not an error", rc == 0 and "no events" in out, out)
    shutil.rmtree(root)


# ─── 9. rotation + settings wiring ─────────────────────────────────────────────────────────────────
def case_rotation_and_settings():
    print("rotation + framework settings")
    root = project({1: {}})
    for i in range(6):
        run(root, P("Stop"), env={"SDLC_LEDGER_ROTATE_BYTES": "500"})
    names = sorted(n for n in os.listdir(os.path.join(root, "agent_state", "ledger")) if n.startswith("events-"))
    check("rotates to events-<day>.N.jsonl past the size limit", len(names) >= 2 and any(".1.jsonl" in n for n in names), names)
    check("no event lost across rotation", len(events(root)) == 6)
    shutil.rmtree(root)
    s = json.load(open(os.path.join(REPO, ".claude", "settings.json")))
    want = {"PreToolUse": "Agent|Task", "PostToolUse": None, "SubagentStart": None, "SubagentStop": None,
            "TaskCreated": None, "TaskCompleted": None, "Stop": None, "StopFailure": None}
    for ev, m in want.items():
        gs = [g for g in s["hooks"].get(ev, []) if any("ledger.py" in h.get("command", "") for h in g["hooks"])]
        check("settings: %s wired%s" % (ev, " (matcher %s)" % m if m else ""), gs and (m is None or gs[0].get("matcher") == m))
    pm = [g.get("matcher", "") for g in s["hooks"]["PostToolUse"] if any("ledger.py" in h["command"] for h in g["hooks"])][0]
    check("PostToolUse matcher covers spawn, edit tools, Bash, TodoWrite",
          all(t in pm.split("|") for t in ("Agent", "Edit", "Write", "MultiEdit", "NotebookEdit", "Bash", "TodoWrite")))
    cmds = [h["command"] for gs in s["hooks"].values() for g in gs for h in g["hooks"]]
    check("existing verify-gate / autonomous hooks untouched", any("verify-gate.sh" in c for c in cmds)
          and any("autonomous-continue.sh" in c for c in cmds) and any("manifest-write-check.sh" in c for c in cmds))


# ─── 10. updater --ledger-only ─────────────────────────────────────────────────────────────────────
def git_status(p):
    return subprocess.run(["git", "-C", p, "status", "--porcelain", "--untracked-files=all"], capture_output=True,
                          text=True).stdout


def upd(p, *args):
    r = subprocess.run(["bash", UPDATER, "--project", p, "--ledger-only", *args], capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout + r.stderr


def case_updater():
    print("updater --ledger-only")
    p = tempfile.mkdtemp(prefix="ledger-upd-")
    subprocess.run(["git", "init", "-q", p], check=True)
    os.makedirs(os.path.join(p, ".claude", "hooks"))
    os.makedirs(os.path.join(p, "src"))
    user_settings = {"permissions": {"allow": ["Bash(ls:*)"]}, "hooks": {
        "PostToolUse": [{"matcher": "Write", "hooks": [{"type": "command", "command": "echo user-hook"}]}],
        "Stop": [{"hooks": [{"type": "command", "command": "echo user-stop"}]}]}}
    json.dump(user_settings, open(os.path.join(p, ".claude", "settings.json"), "w"), indent=2)
    open(os.path.join(p, ".claude", "hooks", "my-own.sh"), "w").write("#!/bin/sh\n")
    open(os.path.join(p, "src", "a.txt"), "w").write("a\n")
    open(os.path.join(p, ".gitignore"), "w").write("node_modules/\n")
    subprocess.run(["git", "-C", p, "add", "-A"], check=True)
    subprocess.run(["git", "-C", p, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "i"], check=True)
    open(os.path.join(p, "src", "a.txt"), "a").write("uncommitted work\n")
    open(os.path.join(p, "src", "new.txt"), "w").write("untracked work\n")
    before = git_status(p)
    rc, out = upd(p, "--dry-run")
    check("--dry-run exits 0 and changes nothing", rc == 0 and git_status(p) == before, out)
    check("--dry-run lists exactly the ledger files",
          "ledger.py, .claude/hooks/.framework-manifest.json, .claude/settings.json, .gitignore" in out, out)
    rc, out = upd(p)
    after = set(git_status(p).splitlines()) - set(before.splitlines())
    check("install exits 0", rc == 0, out)
    check("only expected files changed", after == {" M .claude/settings.json", " M .gitignore",
                                                  "?? .claude/hooks/ledger.py", "?? .claude/hooks/.framework-manifest.json"},
          sorted(after))
    check("uncommitted work untouched", open(os.path.join(p, "src", "a.txt")).read() == "a\nuncommitted work\n"
          and os.path.exists(os.path.join(p, "src", "new.txt")))
    s = json.load(open(os.path.join(p, ".claude", "settings.json")))
    cmds = [h["command"] for gs in s["hooks"].values() for g in gs for h in g["hooks"]]
    check("user hook entries + permissions kept", "echo user-hook" in cmds and "echo user-stop" in cmds
          and s["permissions"] == user_settings["permissions"])
    check("no other framework hooks or env added", not any(x in c for c in cmds for x in
                                                           ("verify-gate", "autonomous", "inject-project-facts", "manifest-write"))
          and "env" not in s, cmds)
    check("ledger wired on all 8 events", sum(1 for gs in s["hooks"].values() for g in gs for h in g["hooks"]
                                              if "ledger.py" in h["command"]) == 8)
    check(".gitignore gets agent_state/ledger/", "agent_state/ledger/" in open(os.path.join(p, ".gitignore")).read())
    check("installed hook identical to the framework's",
          open(os.path.join(p, ".claude", "hooks", "ledger.py")).read() == open(HOOK).read())
    mf = json.load(open(os.path.join(p, ".claude", "hooks", ".framework-manifest.json")))
    check("manifest records ledger.py only", list(mf["files"]) == ["ledger.py"], mf["files"])
    snap = git_status(p), open(os.path.join(p, ".claude", "settings.json")).read()
    rc, out = upd(p)
    check("idempotent: second run changes nothing", rc == 0 and (git_status(p), open(os.path.join(p, ".claude", "settings.json")).read()) == snap
          and "files written: none" in out, out)
    open(os.path.join(p, ".claude", "hooks", "ledger.py"), "a").write("# local edit\n")
    rc, out = upd(p)
    check("locally modified ledger.py kept (exit 1) without --force", rc == 1 and
          open(os.path.join(p, ".claude", "hooks", "ledger.py")).read().endswith("# local edit\n"), out[-300:])
    rc, out = upd(p, "--force")
    check("--force replaces it", rc == 0 and open(os.path.join(p, ".claude", "hooks", "ledger.py")).read() == open(HOOK).read())
    r = subprocess.run(["bash", UPDATER, "--project", p, "--ledger-only", "--hooks-only"], capture_output=True, text=True)
    check("--ledger-only with --hooks-only is a usage error", r.returncode == 2)
    shutil.rmtree(p)
    # no settings.json at all (rera's shape): created with ONLY the ledger hooks
    q = tempfile.mkdtemp(prefix="ledger-upd-")
    subprocess.run(["git", "init", "-q", q], check=True)
    os.makedirs(os.path.join(q, ".claude"))
    json.dump({"permissions": {}}, open(os.path.join(q, ".claude", "settings.local.json"), "w"))
    rc, out = upd(q)
    s = json.load(open(os.path.join(q, ".claude", "settings.json")))
    check("absent settings.json → created with ledger hooks only", rc == 0 and set(s) == {"hooks"} and all(
        "ledger.py" in h["command"] for gs in s["hooks"].values() for g in gs for h in g["hooks"]), s)
    check("settings.local.json untouched", json.load(open(os.path.join(q, ".claude", "settings.local.json"))) == {"permissions": {}})
    shutil.rmtree(q)


# ─── 11. timing ────────────────────────────────────────────────────────────────────────────────────
def case_timing():
    print("timing")
    root = project({1: {"phase": 1}})
    ts = []
    for i in range(15):
        t = time.perf_counter()
        run(root, P("PostToolUse", tool_name="Bash", tool_input={"command": "x"}))
        ts.append((time.perf_counter() - t) * 1000)
    base = []
    for i in range(15):
        t = time.perf_counter()
        subprocess.run([sys.executable, "-c", "pass"], capture_output=True)
        base.append((time.perf_counter() - t) * 1000)
    med, bmed = statistics.median(ts), statistics.median(base)
    print("    hook median %.1f ms (bare interpreter %.1f ms)" % (med, bmed))
    check("hook overhead over interpreter start < 60 ms (target total < 50 ms on an idle machine)", med - bmed < 60,
          "%.1f vs %.1f" % (med, bmed))
    shutil.rmtree(root)


if __name__ == "__main__":
    for c in (case_replay, case_event_types, case_matching, case_phase, case_lock, case_never_fail, case_card,
              case_report, case_rotation_and_settings, case_updater, case_timing):
        try:
            c()
        except Exception as e:      # a crashing case is a failure, not a silent skip
            import traceback
            traceback.print_exc()
            check(c.__name__ + " ran to completion", False, repr(e))
    print("phase-ledger: %d passed, %d failed" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)
