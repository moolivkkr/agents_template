#!/usr/bin/env bash
# agent-budget.test.sh — per-subagent budgets enforced by .claude/hooks/agent-budget.py: hook payloads replayed in
# a temp git project. Covers: main session never limited, BUDGET: line from the spawn prompt reaches the agent,
# budget card injected, soft warning once, hard call cap with wrap-up window, no-progress cap reset by edits and
# commits, repeated identical command, refusals stop at once (no wrap-up beyond a commit), minutes cap, policy
# per-type override, SDLC_BUDGET=0, resume keeps counting, fail-open on garbage, status output, settings wiring.
# Run: bash tests/agent-budget.test.sh   (exit 0 = pass)
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 -B - "$DIR/.." <<'PYEOF'
import json, os, subprocess, sys, tempfile, time
REPO = os.path.abspath(sys.argv[1])
HOOK = os.path.join(REPO, ".claude/hooks/agent-budget.py")
P = F = 0

def check(name, cond, extra=""):
    global P, F
    if cond: P += 1; print(f"  ✓ {name}")
    else: F += 1; print(f"  ✗ FAIL: {name} {extra}")

def proj():
    d = tempfile.mkdtemp(prefix="budget-")
    subprocess.run(["git", "init", "-q", d]); subprocess.run(["git", "-C", d, "commit", "-q", "--allow-empty", "-m", "init"],
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})
    return d

def run(d, payload, env=None):
    payload = {"cwd": d, **payload}
    e = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PROJECT_DIR", "SDLC_BUDGET")}
    e.update(env or {})
    r = subprocess.run([sys.executable, HOOK], input=json.dumps(payload), capture_output=True, text=True, env=e)
    try: out = json.loads(r.stdout) if r.stdout.strip() else None
    except ValueError: out = {"raw": r.stdout}
    return r.returncode, out

def pre(d, aid, tool="Bash", cmd="ls", **kw):
    ti = {"command": cmd} if tool == "Bash" else {"file_path": os.path.join(d, "f.txt"), "content": "x"}
    return run(d, {"hook_event_name": "PreToolUse", "agent_id": aid, "agent_type": "unit_test_agent", "tool_name": tool, "tool_input": ti}, **kw)

def post(d, aid, tool="Bash", cmd="ls"):
    ti = {"command": cmd} if tool == "Bash" else {"file_path": os.path.join(d, "f.txt")}
    return run(d, {"hook_event_name": "PostToolUse", "agent_id": aid, "agent_type": "unit_test_agent", "tool_name": tool, "tool_input": ti})

def denied(out): return bool(out) and out.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"
def reason(out): return (out or {}).get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
def state(d, aid): return json.load(open(os.path.join(d, "agent_state/budget", aid + ".json")))
def policy(d, obj):
    os.makedirs(os.path.join(d, "agent_state/config"), exist_ok=True)
    json.dump(obj, open(os.path.join(d, "agent_state/config/budget-policy.json"), "w"))
def call(d, aid, n, cmd_fn=lambda i: f"echo {i}"):
    last = None
    for i in range(n):
        rc, last = pre(d, aid, cmd=cmd_fn(i)); post(d, aid, cmd=cmd_fn(i))
    return last

print("▶ agent-budget")
# 1. main session: no agent_id, never limited
d = proj()
outs = [pre(d, None, cmd=f"echo {i}")[1] for i in range(120)]
check("main session (no agent_id) is never limited", not any(denied(o) for o in outs))

# 2. spawn BUDGET: line -> SubagentStart card + limits
d = proj()
run(d, {"hook_event_name": "PreToolUse", "tool_name": "Agent", "tool_input": {"subagent_type": "unit_test_agent", "prompt": "do x\nBUDGET: calls=10 minutes=20\n"}})
rc, out = run(d, {"hook_event_name": "SubagentStart", "agent_id": "a1", "agent_type": "unit_test_agent"})
ctx = (out or {}).get("hookSpecificOutput", {}).get("additionalContext", "")
check("SubagentStart injects the budget card", "at most 10 tool calls" in ctx and "20" in ctx, ctx[:120])
check("spawn BUDGET line sets the hard limit", state(d, "a1")["limits"]["calls_hard"] == 10)
check("a tighter hard limit pulls the soft one below it", state(d, "a1")["limits"]["calls_soft"] < 10)
check("pending queue consumed", json.load(open(os.path.join(d, "agent_state/budget/pending.json")))["unit_test_agent"] == [])
# 3. soft warning once, then hard deny
warns = []
for i in range(9):
    pre(d, "a1", cmd=f"echo {i}"); rc, o = post(d, "a1", cmd=f"echo {i}")
    if o: warns.append(o)
check("soft warning delivered once as PostToolUse additionalContext", len(warns) == 1 and "WARNING" in warns[0]["hookSpecificOutput"]["additionalContext"], str(warns)[:200])
rc, o = pre(d, "a1", cmd="pytest")
check("hard call cap denies new work", denied(o) and "PARTIAL budget:calls" in reason(o), reason(o)[:160])
rc, o = pre(d, "a1", cmd="git commit -m wip")
check("wrap-up: git commit still allowed after the cap", not denied(o))
rc, o = pre(d, "a1", tool="Write")
check("wrap-up: writing the checkpoint still allowed", not denied(o))
for i in range(15): pre(d, "a1", cmd="git status")
rc, o = pre(d, "a1", cmd="git status")
check("wrap-up window is finite", denied(o))

# 4. no-progress cap; edits and commits reset it
d = proj(); policy(d, {"defaults": {"no_progress_soft": 3, "no_progress_hard": 5, "repeat_hard": 99}})
run(d, {"hook_event_name": "SubagentStart", "agent_id": "a2", "agent_type": "unit_test_agent"})
o = call(d, "a2", 4)
pre(d, "a2", tool="Write"); post(d, "a2", tool="Write")
o = call(d, "a2", 4)
check("a file edit resets the no-progress counter", not denied(o))
o = call(d, "a2", 2)
check("no-progress cap denies", denied(o) and "no commit or file edit" in reason(o), reason(o)[:120])
d = proj(); policy(d, {"defaults": {"no_progress_hard": 5, "repeat_hard": 99}})
run(d, {"hook_event_name": "SubagentStart", "agent_id": "a2b", "agent_type": "unit_test_agent"})
call(d, "a2b", 4)
open(os.path.join(d, "x"), "w").write("1")
subprocess.run(["git", "-C", d, "add", "x"]); subprocess.run(["git", "-C", d, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x"])
pre(d, "a2b", cmd="git commit -m x"); post(d, "a2b", cmd="git commit -m x")
check("a new commit counts as progress", state(d, "a2b")["commits"] == 1 and state(d, "a2b")["calls_at_progress"] == 5)

# 5. repeated identical command
d = proj(); run(d, {"hook_event_name": "SubagentStart", "agent_id": "a3", "agent_type": "unit_test_agent"})
o = call(d, "a3", 4, lambda i: "kubectl get pods -n x-dev")
check("same command 4x with no progress is stopped", denied(o) and "same command" in reason(o), reason(o)[:120])

# 6. refusals: stop at once, only a commit allowed
d = proj(); run(d, {"hook_event_name": "SubagentStart", "agent_id": "a4", "agent_type": "unit_test_agent"})
for i in range(2):
    run(d, {"hook_event_name": "PermissionDenied", "agent_id": "a4", "agent_type": "unit_test_agent", "tool_name": "Bash", "reason": "Self-Modification"})
rc, o = pre(d, "a4", tool="Write")
check("2 refusals: writes denied too (no working around)", denied(o) and "BLOCKED" in reason(o) and "Self-Modification" in reason(o), reason(o)[:160])
rc, o = pre(d, "a4", cmd="git commit -m done")
check("2 refusals: one commit of finished work still allowed", not denied(o))

# 7. minutes cap
d = proj(); run(d, {"hook_event_name": "SubagentStart", "agent_id": "a5", "agent_type": "unit_test_agent"})
s = state(d, "a5"); s["started"] = time.time() - 46 * 60; json.dump(s, open(os.path.join(d, "agent_state/budget/a5.json"), "w"))
rc, o = pre(d, "a5", cmd="pytest")
check("wall-clock cap denies", denied(o) and "minutes" in reason(o))

# 8. per-type policy override
d = proj(); policy(d, {"types": {"test_runner": {"minutes_hard": 120, "calls_hard": 200}}})
run(d, {"hook_event_name": "SubagentStart", "agent_id": "a6", "agent_type": "test_runner"})
check("policy types override applies per agent_type", state(d, "a6")["limits"]["minutes_hard"] == 120 and state(d, "a6")["limits"]["calls_hard"] == 200)

# 9. switches, resume, fail-open
d = proj(); policy(d, {"defaults": {"calls_hard": 2}})
run(d, {"hook_event_name": "SubagentStart", "agent_id": "a7", "agent_type": "x"})
outs = [pre(d, "a7", cmd=f"e {i}", env={"SDLC_BUDGET": "0"})[1] for i in range(5)]
check("SDLC_BUDGET=0 switches it off", not any(denied(o) for o in outs))
policy(d, {"enabled": False, "defaults": {"calls_hard": 2}})
outs = [pre(d, "a7", cmd=f"e {i}")[1] for i in range(5)]
check("policy enabled:false switches it off", not any(denied(o) for o in outs))
d = proj(); policy(d, {"defaults": {"calls_hard": 5, "repeat_hard": 99}})
run(d, {"hook_event_name": "SubagentStart", "agent_id": "a8", "agent_type": "x"}); call(d, "a8", 3)
run(d, {"hook_event_name": "SubagentStart", "agent_id": "a8", "agent_type": "x"})
check("a resumed agent keeps its count", state(d, "a8")["calls"] == 3)
r = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True, cwd=d)
check("garbage input: exit 0, no output, error logged", r.returncode == 0 and not r.stdout.strip()
      and os.path.exists(os.path.join(d, "agent_state/budget/errors.log")))
check("main-session spawn without BUDGET line queues nothing",
      run(d, {"hook_event_name": "PreToolUse", "tool_name": "Agent", "tool_input": {"subagent_type": "q", "prompt": "x"}})[1] is None)

# 10. status reader
d = proj(); run(d, {"hook_event_name": "SubagentStart", "agent_id": "a9", "agent_type": "unit_test_agent"})
call(d, "a9", 3)
for i in range(2): run(d, {"hook_event_name": "PermissionDenied", "agent_id": "a9", "tool_name": "Bash", "reason": "guard"})
r = subprocess.run([sys.executable, HOOK, "status", "--json"], capture_output=True, text=True, cwd=d)
rows = json.loads(r.stdout)
check("status lists the running agent with calls and refusals", rows and rows[0]["calls"] == 3 and rows[0]["refusals"] == 2 and rows[0]["flag"] == "RUNAWAY", r.stdout[:200])
run(d, {"hook_event_name": "SubagentStop", "agent_id": "a9"})
r = subprocess.run([sys.executable, HOOK, "status"], capture_output=True, text=True, cwd=d)
check("finished agents drop out of the default status", "no running subagents" in r.stdout)
r = subprocess.run([sys.executable, HOOK, "status", "--all", "--json"], capture_output=True, text=True, cwd=d)
check("status --all keeps finished agents", json.loads(r.stdout)[0]["state"] == "done")

# 11. settings wiring
s = json.load(open(os.path.join(REPO, ".claude/settings.json")))
def wired(ev):
    return any("agent-budget.py" in h.get("command", "") for e in s["hooks"].get(ev, []) for h in e["hooks"])
for ev in ("PreToolUse", "PostToolUse", "SubagentStart", "SubagentStop", "PermissionDenied"):
    check(f"settings.json wires agent-budget.py on {ev}", wired(ev))

print("────────────────────────────────────────────")
print(f"agent-budget.test.sh: {P} passed, {F} failed")
sys.exit(1 if F else 0)
PYEOF
