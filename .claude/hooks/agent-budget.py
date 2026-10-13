#!/usr/bin/env python3
"""agent-budget.py — per-subagent budgets, enforced by hooks instead of by the prompt.

Why: in ZoneOS phase 1 one subagent made ~400 tool calls over 7 h, another retried a guard refusal for ~3 h,
and the orchestrator kept answering "still running". A brief that says "keep it small" is a suggestion; a
hook that counts is not. This hook counts every subagent's tool calls, wall-clock minutes, calls since its
last progress (a commit or a file edit), repeated identical commands and permission refusals, and:
  - warns the subagent (PostToolUse additionalContext) at the soft limits: wrap up, commit, checkpoint;
  - at a hard limit denies further work (PreToolUse deny), leaving a short wrap-up window for git
    add/commit/status/diff and writing the checkpoint file, so the agent returns PARTIAL with a checkpoint;
  - after `refusals_hard` permission refusals, stops the agent at once: an external blocker (guard,
    classifier, RBAC, quota) is reported, never retried.
The main session is never limited (no agent_id). The parent reads `agent-budget.py status`.

Hook mode (stdin = hook JSON, dispatch on hook_event_name):
  PreToolUse Agent|Task (main session)  queue the BUDGET: line of the spawn prompt for that subagent_type
  SubagentStart                         start the agent's record, inject its budget card (additionalContext)
  PreToolUse  (inside a subagent)       count; deny at hard limits (wrap-up tools excepted for a few calls)
  PostToolUse (inside a subagent)       progress (HEAD moved / file edited); soft-limit warning once per limit
  PermissionDenied                      count refusals
  SubagentStop                          mark finished
Budget line in a spawn prompt (optional; defaults from policy):
  BUDGET: calls=60 minutes=30 no_progress=30
Policy: agent_state/config/budget-policy.json {"enabled": true, "defaults": {...}, "types": {"<agent_type>": {...}}}
Env: SDLC_BUDGET=0 switches it off.  State: agent_state/budget/<agent_id>.json, pending.json, errors.log
Reader: agent-budget.py status [--json] [--all]
Failure policy: any internal error -> one line in errors.log, exit 0 (fail open: a bug never blocks work).
"""
import fcntl, hashlib, json, os, re, subprocess, sys, time

STATE_DIR = os.path.join("agent_state", "budget")
POLICY = os.path.join("agent_state", "config", "budget-policy.json")
DEFAULTS = {
    "calls_soft": 60, "calls_hard": 90,            # tool calls
    "minutes_soft": 30, "minutes_hard": 45,        # wall clock since start
    "no_progress_soft": 30, "no_progress_hard": 45,  # calls since the last commit or file edit
    "repeat_hard": 4,                              # the same Bash command, with no progress in between
    "refusals_hard": 2,                            # permission refusals (guard, classifier, rules)
    "wrapup_calls": 12,                            # calls allowed after a hard limit, wrap-up tools only
}
SPAWN_TOOLS = ("Agent", "Task")
EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
BUDGET_RE = re.compile(r"^\s*BUDGET:\s*(.+)$", re.M)
KV_RE = re.compile(r"([a-z_]+)=(\d+)")
ALIASES = {"calls": "calls_hard", "minutes": "minutes_hard", "no_progress": "no_progress_hard",
           "refusals": "refusals_hard"}
WRAPUP_BASH = re.compile(r"^\s*(git\s+(-C\s+\S+\s+)?(add|commit|status|diff|log|stash\s+list|rev-parse)\b|mkdir\s)")


def now():
    return time.time()


def read_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def policy():
    p = read_json(POLICY, {})
    return p if isinstance(p, dict) else {}


def enabled():
    if os.environ.get("SDLC_BUDGET") == "0":
        return False
    return policy().get("enabled", True) is not False


def limits_for(agent_type, override=None):
    p = policy()
    lim = dict(DEFAULTS)
    lim.update({k: v for k, v in (p.get("defaults") or {}).items() if k in DEFAULTS})
    lim.update({k: v for k, v in ((p.get("types") or {}).get(agent_type or "") or {}).items() if k in DEFAULTS})
    for k, v in (override or {}).items():
        lim[k] = v
        soft = k.replace("_hard", "_soft")
        if k.endswith("_hard") and soft in lim and lim[soft] >= v:
            lim[soft] = max(1, int(v * 2 / 3))      # a tighter hard limit pulls the soft one down
    return lim


def parse_budget(prompt):
    m = BUDGET_RE.search(prompt or "")
    if not m:
        return None
    out = {}
    for k, v in KV_RE.findall(m.group(1)):
        k = ALIASES.get(k, k)
        if k in DEFAULTS:
            out[k] = int(v)
    return out or None


class Locked:
    """Exclusive lock on the state dir: parallel subagents fire hooks concurrently."""
    def __enter__(self):
        os.makedirs(STATE_DIR, exist_ok=True)
        self.f = open(os.path.join(STATE_DIR, ".lock"), "a+")
        fcntl.flock(self.f, fcntl.LOCK_EX)
        return self

    def __exit__(self, *a):
        fcntl.flock(self.f, fcntl.LOCK_UN)
        self.f.close()


def safe_id(aid):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(aid))[:80]


def agent_path(aid):
    return os.path.join(STATE_DIR, safe_id(aid) + ".json")


def save(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, path)


def git_head(cwd):
    try:
        r = subprocess.run(["git", "-C", cwd or ".", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=3)
        return r.stdout.strip() or None
    except Exception:
        return None


def new_record(aid, atype, override, cwd):
    return {"agent_id": aid, "agent_type": atype, "started": now(), "updated": now(), "finished": None,
            "limits": limits_for(atype, override), "budget_line": override, "calls": 0,
            "calls_at_progress": 0, "last_progress": now(), "head": git_head(cwd), "commits": 0, "edits": 0,
            "refusals": [], "last_cmd": None, "repeat": 0, "warned": [], "capped": None, "wrapup_used": 0}


def load_agent(aid, atype, cwd):
    rec = read_json(agent_path(aid), None)
    if not isinstance(rec, dict):
        rec = new_record(aid, atype, None, cwd)
    return rec


def card(rec):
    L = rec["limits"]
    return (f"BUDGET (enforced by a hook, not advisory): at most {L['calls_hard']} tool calls, {L['minutes_hard']} "
            f"minutes, and {L['no_progress_hard']} calls without progress (a commit or a file edit). You get a "
            f"warning at {L['calls_soft']} calls / {L['minutes_soft']} min. At a warning: finish the current unit, "
            "commit, write your checkpoint (done / todo / the next command to run) and return PARTIAL. At the hard "
            "limit every tool except git add/commit/status/diff and writing files is denied, and only for a few "
            "calls. ON ANY PERMISSION REFUSAL (guard, auto-mode classifier, RBAC, quota): do not retry or route "
            "around it; stop and return BLOCKED with the exact refusal text — after "
            f"{L['refusals_hard']} refusals the hook stops you anyway. Don't sleep through long runs: start them "
            "as background scripts and return; don't poll.")


def over(rec):
    """-> (kind, detail) for the first hard limit crossed, else None."""
    L, mins = rec["limits"], (now() - rec["started"]) / 60
    if len(rec["refusals"]) >= L["refusals_hard"]:
        return "refusals", f"{len(rec['refusals'])} permission refusals (last: {rec['refusals'][-1][:160]})"
    if rec["calls"] >= L["calls_hard"]:
        return "calls", f"{rec['calls']} tool calls (limit {L['calls_hard']})"
    if mins >= L["minutes_hard"]:
        return "minutes", f"{mins:.0f} minutes (limit {L['minutes_hard']})"
    if rec["calls"] - rec["calls_at_progress"] >= L["no_progress_hard"]:
        return "no_progress", f"{rec['calls'] - rec['calls_at_progress']} calls with no commit or file edit"
    if rec["repeat"] >= L["repeat_hard"]:
        return "repeat", f"the same command {rec['repeat']} times with no progress in between"
    return None


def soft(rec):
    L, mins = rec["limits"], (now() - rec["started"]) / 60
    out = []
    if rec["calls"] >= L["calls_soft"]:
        out.append(("calls", f"{rec['calls']}/{L['calls_hard']} tool calls"))
    if mins >= L["minutes_soft"]:
        out.append(("minutes", f"{mins:.0f}/{L['minutes_hard']} minutes"))
    if rec["calls"] - rec["calls_at_progress"] >= L["no_progress_soft"]:
        out.append(("no_progress", f"{rec['calls'] - rec['calls_at_progress']} calls without a commit or edit"))
    return out


def is_wrapup(tool, ti):
    if tool in EDIT_TOOLS:
        return True
    if tool == "Bash":
        return bool(WRAPUP_BASH.match(str(ti.get("command", ""))))
    return False


def emit(obj):
    print(json.dumps(obj))


# ─── hook handlers ───────────────────────────────────────────────────────────────────────────────
def on_spawn(d):
    ti = d.get("tool_input") or {}
    b = parse_budget(str(ti.get("prompt", "")))
    if not b:
        return
    with Locked():
        pp = os.path.join(STATE_DIR, "pending.json")
        pend = read_json(pp, {})
        pend.setdefault(ti.get("subagent_type") or "general-purpose", []).append({"budget": b, "ts": now()})
        save(pp, pend)


def on_start(d):
    aid, atype = d.get("agent_id"), d.get("agent_type")
    if not aid:
        return
    with Locked():
        pp = os.path.join(STATE_DIR, "pending.json")
        pend = read_json(pp, {})
        q = pend.get(atype or "general-purpose") or []
        override = q.pop(0)["budget"] if q else None
        save(pp, pend)
        rec = read_json(agent_path(aid), None)
        if isinstance(rec, dict) and not rec.get("finished"):
            return                                      # resumed: keep counting against the same budget
        rec = new_record(aid, atype, override, d.get("cwd"))
        save(agent_path(aid), rec)
    emit({"hookSpecificOutput": {"hookEventName": "SubagentStart", "additionalContext": card(rec)}})


def on_pre(d):
    aid = d.get("agent_id")
    tool, ti = d.get("tool_name", ""), d.get("tool_input") or {}
    if not aid:
        if tool in SPAWN_TOOLS:
            on_spawn(d)
        return
    with Locked():
        rec = load_agent(aid, d.get("agent_type"), d.get("cwd"))
        rec["calls"] += 1
        rec["updated"] = now()
        if tool == "Bash":
            h = hashlib.sha256(str(ti.get("command", "")).strip().encode()).hexdigest()[:16]
            rec["repeat"] = rec["repeat"] + 1 if h == rec.get("last_cmd") else 1
            rec["last_cmd"] = h
        hit = over(rec)
        decision = None
        if hit:
            if not rec["capped"]:
                rec["capped"] = {"kind": hit[0], "detail": hit[1], "ts": now()}
            if is_wrapup(tool, ti) and rec["wrapup_used"] < rec["limits"]["wrapup_calls"] and hit[0] != "refusals":
                rec["wrapup_used"] += 1
            elif hit[0] == "refusals" and tool == "Bash" and WRAPUP_BASH.match(str(ti.get("command", ""))) \
                    and rec["wrapup_used"] < 4:
                rec["wrapup_used"] += 1                 # one commit of finished work, nothing else
            else:
                decision = hit
        save(agent_path(aid), rec)
    if decision:
        kind, detail = decision
        if kind == "refusals":
            why = (f"agent-budget: STOP — {detail}. An external blocker is not yours to work around. End your turn "
                   "now with first line `BLOCKED <the refusal>` and what you were trying to do; the parent routes it "
                   "to the human.")
        else:
            why = (f"agent-budget: hard limit reached — {detail}. No further work in this run. If you haven't: "
                   "commit, and write your checkpoint (done / todo / the exact next command). Then end your turn "
                   "with first line `PARTIAL budget:" + kind + "` and the checkpoint path. The parent relaunches a "
                   "smaller task from it.")
        emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                     "permissionDecisionReason": why}})


def on_post(d):
    aid = d.get("agent_id")
    if not aid:
        return
    tool = d.get("tool_name", "")
    msgs = []
    with Locked():
        rec = load_agent(aid, d.get("agent_type"), d.get("cwd"))
        progressed = False
        if tool in EDIT_TOOLS:
            rec["edits"] += 1
            progressed = True
        if tool == "Bash":
            head = git_head(d.get("cwd"))
            if head and head != rec.get("head"):
                rec["head"], rec["commits"] = head, rec["commits"] + 1
                progressed = True
        if progressed:
            rec["calls_at_progress"], rec["last_progress"], rec["repeat"] = rec["calls"], now(), 0
        if not rec["capped"]:
            for kind, detail in soft(rec):
                if kind not in rec["warned"]:
                    rec["warned"].append(kind)
                    msgs.append(detail)
        save(agent_path(aid), rec)
    if msgs:
        emit({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext":
              "agent-budget WARNING: " + "; ".join(msgs) + ". Finish the unit you are on, commit, write your "
              "checkpoint (done / todo / next command) and return PARTIAL. Don't start new work."}})


def on_denied(d):
    aid = d.get("agent_id")
    if not aid:
        return
    reason = str(d.get("reason") or d.get("permission_decision_reason") or d.get("message") or
                 d.get("tool_name") or "permission denied")
    with Locked():
        rec = load_agent(aid, d.get("agent_type"), d.get("cwd"))
        rec["refusals"].append(f"{d.get('tool_name', '?')}: {reason}"[:400])
        rec["updated"] = now()
        save(agent_path(aid), rec)


def on_stop(d):
    aid = d.get("agent_id")
    if not aid:
        return
    with Locked():
        rec = read_json(agent_path(aid), None)
        if isinstance(rec, dict):
            rec["finished"] = now()
            save(agent_path(aid), rec)


# ─── reader ──────────────────────────────────────────────────────────────────────────────────────
def status(argv):
    import glob
    as_json, show_all = "--json" in argv, "--all" in argv
    rows = []
    for p in sorted(glob.glob(os.path.join(STATE_DIR, "*.json"))):
        if p.endswith(("pending.json",)):
            continue
        r = read_json(p, None)
        if not isinstance(r, dict) or "agent_id" not in r:
            continue
        if r.get("finished") and not show_all:
            continue
        L = r["limits"]
        mins = ((r.get("finished") or now()) - r["started"]) / 60
        idle = (now() - r.get("last_progress", r["started"])) / 60
        flag = "CAPPED:" + r["capped"]["kind"] if r.get("capped") else (
            "RUNAWAY" if (idle >= 20 and r["calls"] - r["calls_at_progress"] >= 10) or len(r["refusals"]) else
            "WARN" if r.get("warned") else "ok")
        rows.append({"agent_id": r["agent_id"], "type": r.get("agent_type"), "state": "done" if r.get("finished") else "running",
                     "flag": flag, "calls": r["calls"], "calls_limit": L["calls_hard"], "minutes": round(mins, 1),
                     "minutes_limit": L["minutes_hard"], "since_progress": r["calls"] - r["calls_at_progress"],
                     "min_since_progress": round(idle, 1), "commits": r["commits"], "edits": r["edits"],
                     "refusals": len(r["refusals"]), "last_refusal": (r["refusals"] or [None])[-1]})
    if as_json:
        print(json.dumps(rows, indent=1))
        return 0
    if not rows:
        print("agent-budget: no running subagents" + ("" if show_all else " (--all includes finished ones)"))
        return 0
    print(f"{'agent':<20} {'type':<24} {'flag':<20} {'calls':>9} {'min':>9} {'no-prog':>8} {'commits':>7} {'refusals':>8}")
    for x in rows:
        print(f"{x['agent_id'][:20]:<20} {str(x['type'])[:24]:<24} {x['flag']:<20} "
              f"{x['calls']:>4}/{x['calls_limit']:<4} {x['minutes']:>4}/{x['minutes_limit']:<4} "
              f"{x['since_progress']:>8} {x['commits']:>7} {x['refusals']:>8}")
        if x["last_refusal"]:
            print(f"    last refusal: {x['last_refusal'][:150]}")
    return 0


HANDLERS = {"SubagentStart": on_start, "PreToolUse": on_pre, "PostToolUse": on_post,
            "PermissionDenied": on_denied, "SubagentStop": on_stop}


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        sys.exit(status(sys.argv[2:]))
    try:
        d = json.load(sys.stdin)
        # state lives in the project, even when a subagent works in its own worktree (git_head uses d["cwd"])
        root = os.environ.get("CLAUDE_PROJECT_DIR") or d.get("cwd")
        if root:
            os.chdir(root)
        if not enabled():
            return
        h = HANDLERS.get(d.get("hook_event_name", ""))
        if h:
            h(d)
    except Exception as e:                               # fail open, but leave a trace
        try:
            os.makedirs(STATE_DIR, exist_ok=True)
            with open(os.path.join(STATE_DIR, "errors.log"), "a") as f:
                f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {type(e).__name__}: {e}\n")
        except Exception:
            pass
    sys.exit(0)


if __name__ == "__main__":
    main()
