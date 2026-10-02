#!/usr/bin/env python3
"""ledger.py — the PHASE LEDGER: hook-written, OBSERVE-ONLY record of subagents, tasks and orchestration.

Why: tracking that lives in prompts (execution.jsonl lines an agent chooses to write) disappears the moment work
is driven interactively. Hooks fire however the work is driven, so the ledger is written ONLY by this hook —
never by an agent. Step 1 observes; it never blocks, never changes a tool call, never fails a session.

Hook mode (no arguments; Claude Code pipes the event JSON on stdin; dispatch on hook_event_name):
  PreToolUse  Agent|Task                      spawn_requested  subagent_type, TASK: <id> tag, prompt sha256 + 200 chars
  PostToolUse Agent|Task                      spawn_returned   tool_use_id <-> agentId (exact link), status, tokens
  PostToolUse Edit|Write|MultiEdit|NotebookEdit  files         paths touched, by agent_id or "main"
  PostToolUse Bash                            bash             command, first 200 chars (obvious secrets masked)
  PostToolUse TodoWrite                       todos            counts by status
  SubagentStart                               started          agent_id/type + provisional task match (FIFO by type)
                                                               + optional task card (additionalContext)
  SubagentStop                                finished         duration, exact tool_use_id from the subagent's
                                                               .meta.json, transcript size (bytes only)
  TaskCreated / TaskCompleted                 task_created / task_completed  task_id, subject (200 chars)
  Stop / StopFailure                          turn_end / turn_error
Every entry: ts, session_id, phase, head, event, agent, agent_type, plan_version (null in step 1), facts_v,
decisions_v. Storage: agent_state/ledger/events-<YYYY-MM-DD>.jsonl, append-only, fcntl-locked, rotated at 20 MB.

Reader:
  ledger.py report [--phase N] [--since YYYY-MM-DD] [--json] [--compare-roster] [--root DIR] [--max-chars N]

Switches: agent_state/config/ledger-policy.json {"enabled": true, "task_card": true, "phase": null}
          env SDLC_LEDGER=0|1 (whole ledger), SDLC_LEDGER_CARD=0|1 (task card), SDLC_PHASE=<n> (pin the phase).
Failure policy: any exception -> one line in agent_state/ledger/errors.log (capped) and exit 0. Docs: docs/PHASE_LEDGER.md
"""
import fcntl, hashlib, json, os, re, sys, time

LEDGER_DIR = os.path.join("agent_state", "ledger")
POLICY = os.path.join("agent_state", "config", "ledger-policy.json")
ROTATE_BYTES = int(os.environ.get("SDLC_LEDGER_ROTATE_BYTES", str(20 * 1024 * 1024)))
ERRLOG_CAP = 256 * 1024
LOCK_WAIT_S = 3.0
HEAD_CHARS = 200
CARD_MAX_CHARS = 3200          # ~800 tokens
SPAWN_TOOLS = ("Agent", "Task")
FILE_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
TASK_RE = re.compile(r"\bTASK:\s*([A-Za-z0-9](?:[A-Za-z0-9._:/-]{0,62}[A-Za-z0-9])?)")
SECRET_RES = (
    (re.compile(r"(?i)(authorization:\s*(?:bearer|basic|token)\s+)\S+"), r"\1***"),
    (re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/=-]{8,}"), r"\1***"),
    (re.compile(r"(?i)((?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key)[\"']?\s*[=:]\s*[\"']?)[^\s\"'&]+"),
     r"\1***"),
    (re.compile(r"(?i)(--(?:password|token|secret|api-key)[= ])\S+"), r"\1***"),
    (re.compile(r"\b(sk-[A-Za-z0-9_-]{6})[A-Za-z0-9_-]+"), r"\1***"),
    (re.compile(r"\b(AKIA|ASIA)[A-Z0-9]{16}\b"), r"\1***"),
    (re.compile(r"(://[^:/\s]+:)[^@\s]+@"), r"\1***@"),
)


# ─── small helpers ───────────────────────────────────────────────────────────────────────────────
def now_iso():
    t = time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + ".%03dZ" % int((t % 1) * 1000)


def short_sha(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:8]
    except OSError:
        return None


def read_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def head(s, n=HEAD_CHARS):
    s = s if isinstance(s, str) else ("" if s is None else str(s))
    return s if len(s) <= n else s[:n]


def mask(s):
    for rx, rep in SECRET_RES:
        s = rx.sub(rep, s)
    return s


def find_root(payload):
    for cand in (os.environ.get("CLAUDE_PROJECT_DIR"), (payload or {}).get("cwd")):
        if cand and os.path.isdir(cand):
            d = os.path.abspath(cand)
            break
    else:
        d = os.getcwd()
    probe = d
    while True:                                   # nearest dir that looks like a project root
        if any(os.path.exists(os.path.join(probe, m)) for m in (".claude", ".git", "agent_state")):
            return probe
        parent = os.path.dirname(probe)
        if parent == probe:
            return d
        probe = parent


def git_head(root):
    """Short HEAD sha without spawning git (works for worktrees, packed refs, detached HEAD)."""
    try:
        gd = os.path.join(root, ".git")
        if os.path.isfile(gd):
            with open(gd) as f:
                line = f.read().strip()
            if not line.startswith("gitdir:"):
                return None
            gd = os.path.normpath(os.path.join(root, line[7:].strip()))
        with open(os.path.join(gd, "HEAD")) as f:
            h = f.read().strip()
        if not h.startswith("ref:"):
            return h[:7] or None
        ref = h[4:].strip()
        common = gd
        cd = os.path.join(gd, "commondir")
        if os.path.isfile(cd):
            with open(cd) as f:
                common = os.path.normpath(os.path.join(gd, f.read().strip()))
        for base in (gd, common):
            p = os.path.join(base, ref)
            if os.path.isfile(p):
                with open(p) as f:
                    return f.read().strip()[:7] or None
        pr = os.path.join(common, "packed-refs")
        if os.path.isfile(pr):
            with open(pr) as f:
                for line in f:
                    parts = line.split()
                    if len(parts) == 2 and parts[1] == ref:
                        return parts[0][:7]
    except OSError:
        pass
    return None


def as_phase(v):
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    s = str(v).strip()
    return int(s) if s.isdigit() else s


def policy(root):
    p = read_json(os.path.join(root, POLICY), {}) or {}
    if not isinstance(p, dict):
        p = {}
    enabled = p.get("enabled", True) is not False
    card = p.get("task_card", True) is not False
    env = os.environ.get("SDLC_LEDGER")
    if env in ("0", "1"):
        enabled = env == "1"
    envc = os.environ.get("SDLC_LEDGER_CARD")
    if envc in ("0", "1"):
        card = envc == "1"
    pin = as_phase(os.environ.get("SDLC_PHASE")) or as_phase(p.get("phase"))
    return enabled, card, pin


# ─── phase derivation (deterministic) ─────────────────────────────────────────────────────────────
CLOSED_STATES = ("PASSED", "PASS", "NOT_APPLICABLE", "CLOSED", "COMPLETE", "COMPLETED", "DONE", "STUB")


def phase_closed(pdir):
    if os.path.exists(os.path.join(pdir, "gate.passed")):
        return True
    m = read_json(os.path.join(pdir, "manifest.json"), None)
    if not isinstance(m, dict):
        return False
    g = m.get("gate")
    if g is True:
        return True
    if isinstance(g, dict):
        if g.get("passed") is True:
            return True
        if str(g.get("state") or g.get("status") or "").upper() in CLOSED_STATES:
            return True
    st = str(m.get("status") or "").upper()
    return any(st == c or st.startswith(c + "_") for c in CLOSED_STATES)


def phase_signature(root):
    sig = []
    for rel in (os.path.join("agent_state", "phases"), os.path.join("agent_state", "autonomous", "run.json"), POLICY):
        try:
            sig.append(os.stat(os.path.join(root, rel)).st_mtime_ns)
        except OSError:
            sig.append(0)
    phases = os.path.join(root, "agent_state", "phases")
    try:
        for n in sorted(os.listdir(phases)):
            if n.isdigit():
                try:
                    sig.append(os.stat(os.path.join(phases, n)).st_mtime_ns)
                except OSError:
                    pass
    except OSError:
        pass
    return hashlib.sha256(repr(sig).encode()).hexdigest()[:16]


def derive_phase(root, pin=None):
    """pin (SDLC_PHASE / policy.phase) > active /autonomous run > highest open phase dir with a manifest
    > latest phase dir > "unscoped"."""
    if pin is not None:
        return pin
    run = read_json(os.path.join(root, "agent_state", "autonomous", "run.json"), None)
    if isinstance(run, dict) and run.get("active") is True and as_phase(run.get("phase")) is not None:
        return as_phase(run.get("phase"))
    phases = os.path.join(root, "agent_state", "phases")
    try:
        nums = sorted((int(n) for n in os.listdir(phases) if n.isdigit() and os.path.isdir(os.path.join(phases, n))),
                      reverse=True)
    except OSError:
        nums = []
    for n in nums:
        pdir = os.path.join(phases, str(n))
        if os.path.isfile(os.path.join(pdir, "manifest.json")) and not phase_closed(pdir):
            return n
    return nums[0] if nums else "unscoped"


# ─── storage ──────────────────────────────────────────────────────────────────────────────────────
class Lock:
    def __init__(self, path):
        self.path, self.fd = path, None

    def __enter__(self):
        self.fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
        deadline = time.time() + LOCK_WAIT_S
        while True:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except (BlockingIOError, PermissionError):
                if time.time() > deadline:
                    os.close(self.fd)
                    raise TimeoutError("ledger lock busy for %.0fs" % LOCK_WAIT_S)
                time.sleep(0.005)

    def __exit__(self, *a):
        try:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
        finally:
            os.close(self.fd)


def events_file(ldir, day):
    base = os.path.join(ldir, "events-%s.jsonl" % day)
    i, path = 0, base
    while True:
        try:
            if os.path.getsize(path) < ROTATE_BYTES:
                return path
        except OSError:
            return path
        i += 1
        path = os.path.join(ldir, "events-%s.%d.jsonl" % (day, i))


def log_error(root, msg):
    try:
        ldir = os.path.join(root, LEDGER_DIR)
        os.makedirs(ldir, exist_ok=True)
        p = os.path.join(ldir, "errors.log")
        try:
            if os.path.getsize(p) > ERRLOG_CAP:
                os.replace(p, p + ".1")
        except OSError:
            pass
        with open(p, "a") as f:
            f.write("%s %s\n" % (now_iso(), head(msg.replace("\n", " | "), 600)))
    except Exception:
        pass


def state_path(ldir, sid):
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", sid or "nosession")[:80]
    return os.path.join(ldir, ".state", safe + ".json")


def load_state(p):
    s = read_json(p, None)
    if not isinstance(s, dict):
        s = {}
    s.setdefault("pending", [])           # spawn_requested not yet claimed by a SubagentStart
    s.setdefault("agents", {})            # agent_id -> {type, start, task, tool_use_id}
    s.setdefault("spawns", {})            # tool_use_id -> {task, type}
    s.setdefault("claimed", {})           # agent_id -> tool_use_id, when the spawn returned before SubagentStart
    return s


def save_state(p, s):
    s["pending"] = s["pending"][-200:]
    if len(s["agents"]) > 500:
        for k in sorted(s["agents"], key=lambda k: s["agents"][k].get("start", 0))[:-500]:
            del s["agents"][k]
    if len(s["claimed"]) > 200:
        for k in list(s["claimed"])[:-200]:
            del s["claimed"][k]
    if len(s["spawns"]) > 500:
        for k in list(s["spawns"])[:-500]:
            del s["spawns"][k]
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(s, f, separators=(",", ":"))
    os.replace(tmp, p)


# ─── task card ────────────────────────────────────────────────────────────────────────────────────
def task_card(root, phase, rec, facts_v, decisions_v):
    lines = []
    pdir = os.path.join(root, "agent_state", "phases", str(phase)) if phase != "unscoped" else None
    base = None
    if pdir:
        try:
            with open(os.path.join(pdir, "base_sha")) as f:
                base = f.read().strip()[:12] or None
        except OSError:
            pass
    known = phase != "unscoped" or rec.get("task") or facts_v or decisions_v
    if not known:
        return None
    hdr = ["phase %s" % phase]
    if rec.get("task"):
        hdr.append("task %s" % rec["task"])
    if rec.get("head"):
        hdr.append("HEAD %s" % rec["head"])
    if base:
        hdr.append("base_sha %s" % base)
    lines.append("[phase ledger] " + " · ".join(hdr))
    if facts_v or decisions_v:
        lines.append("Ground truth: PROJECT_FACTS %s, DECISIONS %s. Read docs/PROJECT_FACTS.md and docs/DECISIONS.md "
                     "if you have not this session." % (facts_v or "absent", decisions_v or "absent"))
    if pdir:
        roster = read_json(os.path.join(pdir, "roster.json"), None)
        if isinstance(roster, dict) and isinstance(roster.get("required"), list):
            req = [str(x) for x in roster["required"]]
            at = rec.get("agent_type") or ""
            if at in req:
                lines.append("Roster: %s is a REQUIRED agent for phase %s (%d required). Expected output: the report "
                             "your agent definition names, under agent_state/phases/%s/." % (at, phase, len(req), phase))
    lines.append("Tracking is hook-written (agent_state/ledger/); do not write to it.")
    card = "\n".join(lines)
    return card[:CARD_MAX_CHARS]


# ─── hook mode ────────────────────────────────────────────────────────────────────────────────────
def relpath(root, p):
    if not isinstance(p, str) or not p:
        return None
    ap = os.path.abspath(os.path.join(root, p))
    rr = os.path.realpath(root)
    for r in (root, rr):
        if ap == r or ap.startswith(r + os.sep):
            return os.path.relpath(ap, r)
    return ap


def build_record(root, ev, d):
    """Event-specific fields (no state needed). Returns None for events the ledger ignores."""
    tool = d.get("tool_name") or ""
    ti = d.get("tool_input") if isinstance(d.get("tool_input"), dict) else {}
    r = {}
    if ev == "PreToolUse":
        if tool not in SPAWN_TOOLS:
            return None
        prompt = ti.get("prompt") if isinstance(ti.get("prompt"), str) else ""
        m = TASK_RE.search(prompt)
        r.update(event="spawn_requested", tool_use_id=d.get("tool_use_id"),
                 subagent_type=ti.get("subagent_type") or "general-purpose",
                 description=head(ti.get("description"), 120), task=m.group(1) if m else None,
                 prompt_sha256=hashlib.sha256(prompt.encode("utf-8", "replace")).hexdigest(),
                 prompt_head=mask(head(prompt)), background=bool(ti.get("run_in_background")))
    elif ev == "PostToolUse":
        if tool in SPAWN_TOOLS:
            tr = d.get("tool_response") if isinstance(d.get("tool_response"), dict) else {}
            r.update(event="spawn_returned", tool_use_id=d.get("tool_use_id"), spawned_agent_id=tr.get("agentId"),
                     status=tr.get("status"), total_ms=tr.get("totalDurationMs"), total_tokens=tr.get("totalTokens"),
                     tool_uses=tr.get("totalToolUseCount"))
        elif tool in FILE_TOOLS:
            p = ti.get("file_path") or ti.get("notebook_path")
            r.update(event="files", tool=tool, files=[x for x in [relpath(root, p)] if x])
        elif tool == "Bash":
            r.update(event="bash", command=mask(head(ti.get("command"))), background=bool(ti.get("run_in_background")))
        elif tool == "TodoWrite":
            counts = {}
            for t in ti.get("todos") or []:
                if isinstance(t, dict):
                    counts[str(t.get("status"))] = counts.get(str(t.get("status")), 0) + 1
            r.update(event="todos", counts=counts)
        else:
            return None
    elif ev == "SubagentStart":
        r.update(event="started")
    elif ev == "SubagentStop":
        tp = d.get("agent_transcript_path")
        size = None
        meta = None
        if isinstance(tp, str) and tp:
            try:
                size = os.path.getsize(tp)
            except OSError:
                pass
            if tp.endswith(".jsonl"):
                meta = read_json(tp[:-6] + ".meta.json", None)
        r.update(event="finished", transcript_bytes=size,
                 tool_use_id=(meta or {}).get("toolUseId") if isinstance(meta, dict) else None,
                 shape=(meta or {}).get("requestShape") if isinstance(meta, dict) else None,
                 last_message_chars=len(d.get("last_assistant_message") or ""))
    elif ev in ("TaskCreated", "TaskCompleted"):
        r.update(event="task_created" if ev == "TaskCreated" else "task_completed", task_id=d.get("task_id"),
                 subject=head(d.get("task_subject") or d.get("title"), HEAD_CHARS))
    elif ev == "Stop":
        r.update(event="turn_end", background_tasks=len(d.get("background_tasks") or []),
                 stop_hook_active=bool(d.get("stop_hook_active")))
    elif ev == "StopFailure":
        r.update(event="turn_error", error=d.get("error") or d.get("error_type") or "unknown",
                 details=mask(head(d.get("error_details") or d.get("error_message") or "", HEAD_CHARS)))
    else:
        return None
    return r


def hook_main(raw):
    root = None
    try:
        d = json.loads(raw) if raw.strip() else {}
        if not isinstance(d, dict):
            return 0
        root = find_root(d)
        enabled, card_on, pin = policy(root)
        if not enabled:
            return 0
        ev = d.get("hook_event_name") or ""
        rec = build_record(root, ev, d)
        if rec is None:
            return 0
        sid = str(d.get("session_id") or "nosession")
        aid = d.get("agent_id")
        base = {"ts": now_iso(), "session_id": sid, "phase": None, "head": git_head(root), "event": rec.pop("event"),
                "agent": aid or "main", "agent_type": d.get("agent_type"), "plan_version": None,
                "facts_v": short_sha(os.path.join(root, "docs", "PROJECT_FACTS.md")),
                "decisions_v": short_sha(os.path.join(root, "docs", "DECISIONS.md"))}
        base.update(rec)
        ldir = os.path.join(root, LEDGER_DIR)
        os.makedirs(ldir, exist_ok=True)
        out = None
        with Lock(os.path.join(ldir, ".lock")):
            sp = state_path(ldir, sid)
            st = load_state(sp)
            sig = phase_signature(root) if pin is None else "pin:%s" % pin
            if st.get("phase_sig") == sig and "phase" in st:
                base["phase"] = st["phase"]
            else:
                base["phase"] = derive_phase(root, pin)
                st["phase"], st["phase_sig"] = base["phase"], sig
            e = base["event"]
            t = time.time()
            if e == "spawn_requested":
                st["pending"].append({"tuid": base.get("tool_use_id"), "type": base["subagent_type"],
                                      "task": base.get("task"), "ts": t})
                if base.get("tool_use_id"):
                    st["spawns"][base["tool_use_id"]] = {"task": base.get("task"), "type": base["subagent_type"]}
            elif e == "spawn_returned":
                sa = base.get("spawned_agent_id")
                tu = base.get("tool_use_id")
                if sa and tu:
                    info = st["spawns"].get(tu) or {}
                    base["task"] = info.get("task")
                    a = st["agents"].get(sa)
                    if a is not None:                     # foreground: SubagentStart already ran (FIFO guess)
                        a["tool_use_id"], a["task"] = tu, info.get("task")
                    else:                                 # background: the spawn returned before SubagentStart
                        st["claimed"][sa] = tu
                    st["pending"] = [p for p in st["pending"] if p.get("tuid") != tu]
            elif e == "started":
                at = base.get("agent_type")
                match, how = None, "none"
                tu = st["claimed"].pop(aid, None) if aid else None
                if tu:                                       # exact: the spawn already returned this agent_id
                    info = st["spawns"].get(tu) or {}
                    match, how = {"task": info.get("task"), "tuid": tu}, "exact"
                else:
                    for i, p in enumerate(st["pending"]):    # oldest unclaimed spawn of the same type
                        if p.get("type") == at:
                            match, how = st["pending"].pop(i), "fifo"
                            break
                base["task"] = match.get("task") if match else None
                base["tool_use_id"] = match.get("tuid") if match else None
                base["match"] = how
                if aid:
                    st["agents"][aid] = {"type": at, "start": t, "task": base["task"], "tool_use_id": base["tool_use_id"]}
                if card_on:
                    card = task_card(root, base["phase"], base, base["facts_v"], base["decisions_v"])
                    if card:
                        out = {"hookSpecificOutput": {"hookEventName": "SubagentStart", "additionalContext": card}}
                        base["card_chars"] = len(card)
            elif e == "finished":
                a = st["agents"].pop(aid, None) if aid else None
                if a:
                    base["duration_s"] = round(t - a.get("start", t), 3)
                exact = base.get("tool_use_id")
                if exact and exact in st["spawns"]:
                    base["task"] = st["spawns"][exact].get("task")
                    base["match"] = "exact"
                elif a:
                    base["task"], base["tool_use_id"] = a.get("task"), a.get("tool_use_id")
                    base["match"] = "fifo" if a.get("tool_use_id") else "none"
                else:
                    base["match"] = "none"
            elif e == "turn_end":
                _gc_states(ldir, sp)
            save_state(sp, st)
            line = json.dumps(base, separators=(",", ":"), ensure_ascii=False, default=str) + "\n"
            day = base["ts"][:10]
            fd = os.open(events_file(ldir, day), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
            try:
                os.write(fd, line.encode("utf-8"))
            finally:
                os.close(fd)
        if out:
            sys.stdout.write(json.dumps(out))
    except Exception as ex:   # never break a session
        log_error(root or os.getcwd(), "%s: %s" % (type(ex).__name__, ex))
    return 0


def _gc_states(ldir, keep):
    sdir = os.path.join(ldir, ".state")
    cutoff = time.time() - 7 * 86400
    try:
        for n in os.listdir(sdir):
            p = os.path.join(sdir, n)
            if p != keep and os.path.getmtime(p) < cutoff:
                os.remove(p)
    except OSError:
        pass


# ─── report ───────────────────────────────────────────────────────────────────────────────────────
def load_events(root, since=None):
    ldir = os.path.join(root, LEDGER_DIR)
    evs, bad = [], 0
    try:
        names = sorted(n for n in os.listdir(ldir) if n.startswith("events-") and n.endswith(".jsonl"))
    except OSError:
        names = []
    for n in names:
        day = n[7:17]
        if since and day < since[:10]:
            continue
        with open(os.path.join(ldir, n), errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except ValueError:
                    bad += 1
                    continue
                if isinstance(e, dict) and (not since or str(e.get("ts", "")) >= since):
                    evs.append(e)
    evs.sort(key=lambda e: str(e.get("ts", "")))
    return evs, bad


def _secs(ts):
    try:
        import calendar
        return calendar.timegm(time.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S")) + float("0" + ts[19:23].rstrip("Z"))
    except (ValueError, TypeError):
        return None


def summarize(root, evs, compare_roster=False):
    phases = {}
    for e in evs:
        phases.setdefault(str(e.get("phase")), []).append(e)
    out = {}
    for ph, es in phases.items():
        spawns = {e.get("tool_use_id"): e for e in es if e.get("event") == "spawn_requested"}
        linked = set()
        starts, finishes = {}, {}
        for e in es:
            ev = e.get("event")
            if ev == "spawn_returned" and e.get("spawned_agent_id"):
                linked.add(e.get("tool_use_id"))
            elif ev == "started" and e.get("agent") != "main":
                starts[e["agent"]] = e
                if e.get("tool_use_id"):
                    linked.add(e["tool_use_id"])
            elif ev == "finished" and e.get("agent") != "main":
                finishes[e["agent"]] = e
                if e.get("tool_use_id"):
                    linked.add(e["tool_use_id"])
        agents = []
        for aid, s in starts.items():
            f = finishes.get(aid)
            agents.append({"agent_id": aid, "type": s.get("agent_type"), "task": (f or {}).get("task") or s.get("task"),
                           "started": s.get("ts"), "finished": (f or {}).get("ts"),
                           "duration_s": (f or {}).get("duration_s"), "session": s.get("session_id")})
        for aid, f in finishes.items():          # finished but the start was in another phase/window
            if aid not in starts:
                agents.append({"agent_id": aid, "type": f.get("agent_type"), "task": f.get("task"), "started": None,
                               "finished": f.get("ts"), "duration_s": f.get("duration_s"), "session": f.get("session_id")})
        by_type = {}
        for a in agents:
            t = by_type.setdefault(a["type"] or "?", {"started": 0, "finished": 0, "durations": []})
            t["started"] += 1 if a["started"] else 0
            t["finished"] += 1 if a["finished"] else 0
            if isinstance(a["duration_s"], (int, float)):
                t["durations"].append(a["duration_s"])
        types = {}
        for k, v in by_type.items():
            ds = sorted(v["durations"])
            types[k] = {"started": v["started"], "finished": v["finished"],
                        "median_s": ds[len(ds) // 2] if ds else None, "max_s": ds[-1] if ds else None}
        unfinished = [a for a in agents if a["started"] and not a["finished"]]
        unmatched = [{"tool_use_id": k, "type": s.get("subagent_type"), "task": s.get("task"), "ts": s.get("ts"),
                      "description": s.get("description")}
                     for k, s in spawns.items() if k not in linked]
        # overlap: a file touched by >1 agent while their windows overlapped
        win = {}
        for a in agents:
            st_, fi = _secs(a["started"] or ""), _secs(a["finished"] or "") if a["finished"] else None
            win[a["agent_id"]] = (st_, fi)
        touches = {}
        for e in es:
            if e.get("event") == "files":
                for p in e.get("files") or []:
                    touches.setdefault(p, []).append((e.get("agent"), _secs(e.get("ts", ""))))
        overlaps = []
        for p, ts_ in touches.items():
            who = sorted({a for a, _ in ts_})
            if len(who) < 2:
                continue
            hit = set()
            for i, a in enumerate(who):
                for b in who[i + 1:]:
                    if _concurrent(a, b, ts_, win):
                        hit.update((a, b))
            if hit:
                overlaps.append({"file": p, "agents": sorted(hit)})
        tasks = {}
        for e in es:
            if e.get("event") in ("task_created", "task_completed"):
                t = tasks.setdefault("%s/%s" % (e.get("session_id", "")[:8], e.get("task_id")),
                                     {"subject": e.get("subject"), "created": None, "completed": None})
                t["created" if e["event"] == "task_created" else "completed"] = e.get("ts")
        r = {"events": len(es), "sessions": len({e.get("session_id") for e in es}),
             "first": es[0].get("ts"), "last": es[-1].get("ts"),
             "heads": sorted({e.get("head") for e in es if e.get("head")}),
             "turns": sum(1 for e in es if e.get("event") == "turn_end"),
             "errors": [{"ts": e.get("ts"), "error": e.get("error"), "details": e.get("details")}
                        for e in es if e.get("event") == "turn_error"],
             "spawns": len(spawns), "agents_started": sum(1 for a in agents if a["started"]),
             "agents_finished": sum(1 for a in agents if a["finished"]),
             "by_type": types, "unfinished": unfinished, "unmatched_spawns": unmatched,
             "overlaps": overlaps, "files_touched": len(touches),
             "bash_commands": sum(1 for e in es if e.get("event") == "bash"),
             "subagent_tokens": sum(e.get("total_tokens") or 0 for e in es if e.get("event") == "spawn_returned"),
             "todo_items": {"created": sum(1 for t in tasks.values() if t["created"]),
                            "completed": sum(1 for t in tasks.values() if t["completed"]),
                            "open": [t["subject"] for t in tasks.values() if t["created"] and not t["completed"]]},
             "facts_versions": sorted({e.get("facts_v") for e in es if e.get("facts_v")}),
             "decisions_versions": sorted({e.get("decisions_v") for e in es if e.get("decisions_v")})}
        if compare_roster and ph.isdigit():
            roster = read_json(os.path.join(root, "agent_state", "phases", ph, "roster.json"), None)
            if isinstance(roster, dict) and isinstance(roster.get("required"), list):
                done = {a["type"] for a in agents if a["finished"]}
                req = [str(x) for x in roster["required"]]
                r["roster"] = {"required": len(req), "finished": [x for x in req if x in done],
                               "missing": [x for x in req if x not in done and not x.startswith("deploy_")],
                               "not_agents": [x for x in req if x.startswith("deploy_")]}
            else:
                r["roster"] = None
        out[ph] = r
    return out


def _concurrent(a, b, touches, win):
    """True when a and b both touched the file while both were live. main has no window: a main touch counts
    when it falls inside the subagent's window; two subagents count when their windows overlap."""
    def live(x, t):
        if x == "main":
            return True
        s, f = win.get(x, (None, None))
        return s is not None and t is not None and s <= t and (f is None or t <= f)
    if a != "main" and b != "main":
        sa, fa = win.get(a, (None, None))
        sb, fb = win.get(b, (None, None))
        if sa is None or sb is None:
            return False
        return sa <= (fb if fb is not None else float("inf")) and sb <= (fa if fa is not None else float("inf"))
    other = b if a == "main" else a
    return any(x == "main" and live(other, t) for x, t in touches)


def render(summary, max_chars, bad):
    L = []

    def lst(items, n, fmt):
        for x in items[:n]:
            L.append("    " + fmt(x))
        if len(items) > n:
            L.append("    … +%d more (use --json)" % (len(items) - n))

    def key(p):
        return (0, int(p)) if p.isdigit() else (1, p)
    for ph in sorted(summary, key=key):
        r = summary[ph]
        L.append("phase %s — %d events, %d session(s), %s → %s, HEAD %s" % (
            ph, r["events"], r["sessions"], (r["first"] or "")[:16], (r["last"] or "")[:16],
            ",".join(r["heads"][-3:]) or "?"))
        L.append("  main turns %d · spawns %d · subagents started %d / finished %d · files %d · bash %d · "
                 "subagent tokens %d" % (r["turns"], r["spawns"], r["agents_started"], r["agents_finished"],
                                         r["files_touched"], r["bash_commands"], r["subagent_tokens"]))
        if r["by_type"]:
            parts = ["%s %d/%d%s" % (k, v["finished"], v["started"],
                                     " (med %.0fs, max %.0fs)" % (v["median_s"], v["max_s"]) if v["median_s"] is not None else "")
                     for k, v in sorted(r["by_type"].items(), key=lambda kv: -kv[1]["started"])]
            L.append("  agent types (finished/started): " + "; ".join(parts[:12])
                     + (" … +%d" % (len(parts) - 12) if len(parts) > 12 else ""))
        if r["unfinished"]:
            L.append("  ⚠ unfinished (started, no finish): %d" % len(r["unfinished"]))
            lst(r["unfinished"], 6, lambda a: "%s %s%s started %s" % (a["type"], a["agent_id"][:10],
                                                                     " task " + a["task"] if a["task"] else "",
                                                                     (a["started"] or "")[:19]))
        if r["unmatched_spawns"]:
            L.append("  ⚠ spawns with no subagent start: %d" % len(r["unmatched_spawns"]))
            lst(r["unmatched_spawns"], 5, lambda s: "%s%s %s — %s" % (s["type"], " task " + s["task"] if s["task"] else "",
                                                                     (s["ts"] or "")[:19], s["description"] or ""))
        if r["overlaps"]:
            L.append("  ⚠ files touched by more than one live agent: %d" % len(r["overlaps"]))
            lst(r["overlaps"], 6, lambda o: "%s ← %s" % (o["file"], ", ".join(x[:10] for x in o["agents"])))
        if r["errors"]:
            L.append("  ⚠ turn errors: %d" % len(r["errors"]))
            lst(r["errors"], 3, lambda e: "%s %s %s" % ((e["ts"] or "")[:19], e["error"], (e["details"] or "")[:80]))
        td = r["todo_items"]
        if td["created"] or td["completed"]:
            L.append("  todo items: %d created, %d completed, %d open" % (td["created"], td["completed"], len(td["open"])))
        if len(r["facts_versions"]) > 1 or len(r["decisions_versions"]) > 1:
            L.append("  ground truth changed during the window: facts %s, decisions %s" % (
                "→".join(r["facts_versions"]) or "-", "→".join(r["decisions_versions"]) or "-"))
        if "roster" in r:
            ro = r["roster"]
            if ro is None:
                L.append("  roster: no agent_state/phases/%s/roster.json" % ph)
            else:
                L.append("  roster: %d required, %d finished per the ledger, missing %d%s" % (
                    ro["required"], len(ro["finished"]), len(ro["missing"]),
                    (": " + ", ".join(ro["missing"])) if ro["missing"] else ""))
                if ro["not_agents"]:
                    L.append("    not agents (logged by deploy.sh, not checked here): " + ", ".join(ro["not_agents"]))
    if bad:
        L.append("(%d unparseable ledger line(s) skipped)" % bad)
    if not summary:
        L.append("phase ledger: no events" + (" for that filter" if bad == 0 else ""))
    text = "\n".join(L)
    if len(text) > max_chars:
        text = text[:max_chars].rsplit("\n", 1)[0] + "\n… output budget reached — narrow with --phase N / --since, or --json"
    return text


def report_main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog="ledger.py report")
    ap.add_argument("--phase", action="append", help="only these phase(s); repeatable; 'unscoped' allowed")
    ap.add_argument("--since", help="YYYY-MM-DD or an ISO timestamp (UTC)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--compare-roster", action="store_true")
    ap.add_argument("--root", default=None)
    ap.add_argument("--max-chars", type=int, default=6000, help="text budget (~1.5k tokens by default)")
    a = ap.parse_args(argv)
    root = os.path.abspath(a.root) if a.root else find_root({})
    evs, bad = load_events(root, a.since)
    if a.phase:
        want = {str(p) for p in a.phase}
        evs = [e for e in evs if str(e.get("phase")) in want]
    s = summarize(root, evs, a.compare_roster)
    if a.json:
        print(json.dumps({"root": root, "unparseable_lines": bad, "phases": s}, indent=2, default=str))
    else:
        print(render(s, a.max_chars, bad))
    return 0


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "report":
        return report_main(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    try:
        raw = sys.stdin.read()
    except Exception:
        return 0
    return hook_main(raw)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        if len(sys.argv) > 1 and sys.argv[1] == "report":
            raise
        sys.exit(0)
