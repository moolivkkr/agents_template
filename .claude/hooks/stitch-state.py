#!/usr/bin/env python3
"""stitch-state.py - the one reader/writer of docs/design/stitch.json (sdlc.stitch-state/v2).

Google Stitch is the core designer (skills/ui/stitch-design.md): every new or changed screen is
designed in Stitch, approved, stored under docs/design/stitch/<screenKey>/ with sha256 hashes, and
only then implemented. This script keeps that record honest. Commands, /design, /ui-audit,
/autonomous and the phase gate call it instead of editing the JSON by hand.

Subcommands
  validate [--check-files]                 schema + cross-field rules (+ render files exist and hashes match)
  gate --phase N                           verify-gate.sh check (g): every UI route this phase changed has a
                                           current approved/conformant screen whose render matches its hash;
                                           no pending_approval / sync_back_pending / drift anywhere; every
                                           stitch_deviations[] entry in the phase's developer manifests resolved
  revise KEY --op OP --screen-id ID --prompt P --source S [--phase N] [--by WHO] [--device D --app A --route R]
                                           append a revision (new screen or new Stitch screen id) -> pending_approval
  render KEY --screenshot PNG --html HTML  copy the fetched render into docs/design/stitch/KEY/ and hash it
  approve KEY --by owner|design_quality_reviewer [--note N]
                                           approve the latest revision (dqr approvals join the owner-review list)
  owner-review KEY --decision accepted|changes_requested [--note N]
  defer KEY --detail D [--run autonomous|interactive] [--device D --app A --route R] [--prompt P]
                                           Stitch unreachable: no_baseline + deferral + queue entry
  deviation KEY --id DEV-N-NNN --phase N --what W --why Y --source S [--resolution fixed|accepted]
                                           record or resolve a developer deviation from the render
  status-set KEY STATUS                     set conformant / drift / design_gap / orphan (ui_standards_auditor results)
  ready [KEY ...] [--phase N]              /develop pre-Wave-2 check: each key (or every key in
                                           docs/design/phases/N/stitch-baseline.md) is approved/conformant at its
                                           latest revision with an intact render; exit 2 otherwise
  review-list                              screens approved by design_quality_reviewer awaiting the owner
  hash FILE                                sha256 of a file

Options: --root DIR (project root, default cwd), --file PATH (default docs/design/stitch.json).
Exit codes: 0 ok, 2 validation/gate failure, 3 usage error.
No third-party dependencies (python3 >= 3.8). The JSON Schema in skills/ui/stitch-state.schema.json
describes the same structure for editors; this script is the authority and also enforces the
cross-field rules a JSON Schema can't express.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import sys

SCHEMA = "sdlc.stitch-state/v2"
DEFAULT_FILE = "docs/design/stitch.json"
RENDER_ROOT = "docs/design/stitch"
KEY_RE = re.compile(r"^[a-z0-9][a-z0-9-]*\.(desktop|mobile|tablet)$")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
DEV_RE = re.compile(r"^DEV-\d+-\d{3,}$")
STATUSES = ["approved", "conformant", "drift", "design_gap", "no_baseline", "import_low_fidelity",
            "pending_approval", "sync_back_pending", "orphan"]
APPROVED = ("approved", "conformant")
NEEDS_RENDER = ("approved", "conformant", "pending_approval", "sync_back_pending", "drift", "design_gap",
                "import_low_fidelity")
DEVICES = ["DESKTOP", "MOBILE", "TABLET"]
APPS = ["web", "mobile"]
ORIGINS = ["generated", "imported", "adopted", "reconstructed", "pending"]
APPROVERS = ["owner", "design_quality_reviewer"]
OPS = ["generate", "edit", "variant_pick", "import", "import_correction", "adopt", "sync_back",
       "apply_design_system", "refresh"]
PROMPT_OPS = ("generate", "edit", "import", "import_correction", "sync_back")
PROMPT_SOURCES = ["owner", "requirement", "change_request", "design_review", "deviation", "import_capture",
                  "import_correction", "audit", "hotfix", "recon", "theme"]
SCREEN_FIELDS = {"screenKey", "screenId", "deviceType", "app", "route", "title", "origin", "status",
                 "approved_by", "approved_at", "approved_rev", "owner_review", "render", "wireframe", "phase",
                 "fidelity", "deferred", "deviations", "history"}
TOP_FIELDS = {"schema", "projectId", "projectTitle", "designSystem", "bootstrap", "screens", "queue", "log"}


def now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


# --------------------------------------------------------------------------------------------- validate
def validate(state, root=None, check_files=False):
    """Return a list of error strings (empty = valid)."""
    errs = []
    e = errs.append
    if not isinstance(state, dict):
        return ["stitch.json is not a JSON object"]
    for k in state:
        if k not in TOP_FIELDS:
            e(f"unknown top-level field '{k}'")
    if state.get("schema") != SCHEMA:
        e(f"schema must be '{SCHEMA}' (got {state.get('schema')!r}) — migrate per stitch-design.md §2")
    pid = state.get("projectId", "MISSING")
    if pid == "MISSING":
        e("projectId is required (null only when Stitch has never been reachable)")
    elif pid is not None and not (isinstance(pid, str) and re.match(r"^\d+$", pid)):
        e(f"projectId must be a digit string or null (got {pid!r})")
    ds = state.get("designSystem")
    if ds is not None:
        if not isinstance(ds, dict) or "assetId" not in ds or "source" not in ds:
            e("designSystem needs assetId and source")
        elif ds["assetId"] is not None and not re.match(r"^\d+$", str(ds["assetId"])):
            e("designSystem.assetId must be digits (the id from assets/<id>)")
    bs = state.get("bootstrap")
    if bs is not None:
        if not isinstance(bs, dict) or bs.get("method") not in ("import", "adopt", "greenfield"):
            e("bootstrap.method must be import | adopt | greenfield")
        elif not ISO_RE.match(str(bs.get("at", ""))):
            e("bootstrap.at must be an ISO-8601 date-time")
    screens = state.get("screens")
    if not isinstance(screens, dict):
        e("screens must be an object keyed <screen-slug>.<device>")
        screens = {}
    if pid is None:
        bad = [k for k, s in screens.items() if isinstance(s, dict) and s.get("status") != "no_baseline"]
        if bad:
            e(f"projectId is null but screens {bad} have a Stitch status — a render needs a project")
    for key, s in screens.items():
        errs.extend(validate_screen(key, s, root, check_files))
    q = state.get("queue", [])
    if not isinstance(q, list):
        e("queue must be an array")
    else:
        for i, item in enumerate(q):
            if not isinstance(item, dict) or not all(item.get(f) for f in ("screenKey", "op", "reason", "ts")):
                e(f"queue[{i}] needs screenKey, op, reason, ts")
            elif item["op"] not in ("generate", "edit", "import", "sync_back", "refresh"):
                e(f"queue[{i}].op '{item['op']}' is not generate | edit | import | sync_back | refresh")
    if "log" in state and not isinstance(state["log"], list):
        e("log must be an array")
    return errs


def validate_screen(key, s, root, check_files):
    errs = []
    p = f"screens['{key}']"

    def e(msg):
        errs.append(f"{p}: {msg}")

    if not isinstance(s, dict):
        return [f"{p}: must be an object"]
    if not KEY_RE.match(key):
        e("key must be <screen-slug>.<desktop|mobile|tablet> (lowercase, e.g. orders-list.desktop)")
    for k in s:
        if k not in SCREEN_FIELDS:
            e(f"unknown field '{k}'")
    for req in ("screenKey", "screenId", "deviceType", "app", "route", "status", "origin"):
        if req not in s:
            e(f"missing required field '{req}'")
    if s.get("screenKey") not in (None, key) and "screenKey" in s:
        e(f"screenKey '{s.get('screenKey')}' does not match its key")
    dev = s.get("deviceType")
    if dev not in DEVICES:
        e(f"deviceType must be one of {DEVICES}")
    elif KEY_RE.match(key) and key.rsplit(".", 1)[1] != dev.lower():
        e(f"key suffix '.{key.rsplit('.', 1)[1]}' does not match deviceType {dev}")
    if s.get("app") not in APPS:
        e(f"app must be one of {APPS}")
    if s.get("app") == "mobile" and dev == "DESKTOP":
        e("a React Native (app: mobile) screen can't be DESKTOP — use MOBILE (or TABLET)")
    status = s.get("status")
    if status not in STATUSES:
        e(f"status must be one of {STATUSES}")
        return errs
    if s.get("origin") not in ORIGINS:
        e(f"origin must be one of {ORIGINS}")
    route = s.get("route")
    if status != "orphan" and not (isinstance(route, str) and route.startswith("/")):
        e("route is required (a path starting with '/'); only an orphan screen may have no route")
    sid = s.get("screenId")
    if status == "no_baseline":
        d = s.get("deferred")
        if d is not None and (not isinstance(d, dict) or d.get("reason") != "stitch_unavailable"
                              or not ISO_RE.match(str(d.get("at", ""))) or len(str(d.get("detail", ""))) < 3):
            e("deferred needs reason 'stitch_unavailable', an ISO 'at' and the probe error as 'detail'")
    elif not (isinstance(sid, str) and sid):
        e(f"status {status} needs a Stitch screenId")
    hist = s.get("history", [])
    if not isinstance(hist, list):
        e("history must be an array")
        hist = []
    if sid and not hist:
        e("a screen with a Stitch screenId needs its revision history (the prompts that produced it)")
    last_rev = 0
    for i, r in enumerate(hist):
        rp = f"history[{i}]"
        if not isinstance(r, dict):
            e(f"{rp} must be an object")
            continue
        if not is_int(r.get("rev")) or r["rev"] <= last_rev:
            e(f"{rp}.rev must be an integer greater than the previous revision ({last_rev})")
        else:
            last_rev = r["rev"]
        if not ISO_RE.match(str(r.get("ts", ""))):
            e(f"{rp}.ts must be an ISO-8601 date-time")
        if r.get("op") not in OPS:
            e(f"{rp}.op must be one of {OPS}")
        if not r.get("screenId"):
            e(f"{rp}.screenId is required")
        if not r.get("by"):
            e(f"{rp}.by is required (which session sent it)")
        if r.get("op") in PROMPT_OPS and not str(r.get("prompt", "")).strip():
            e(f"{rp}: a {r.get('op')} revision must record the prompt sent to Stitch")
        if r.get("prompt_source") is not None and r.get("prompt_source") not in PROMPT_SOURCES:
            e(f"{rp}.prompt_source must be one of {PROMPT_SOURCES}")
    if hist and sid and isinstance(hist[-1], dict) and hist[-1].get("screenId") != sid:
        e(f"screenId {sid} is not the latest revision's screenId ({hist[-1].get('screenId')}) — "
          "edit_screens returns a NEW id; store it")
    render = s.get("render")
    if status in NEEDS_RENDER and not isinstance(render, dict):
        e(f"status {status} needs the fetched render (screenshot + HTML under {RENDER_ROOT}/{key}/)")
    if isinstance(render, dict):
        for f in ("dir", "screenshot", "html", "screenshot_sha256", "html_sha256", "rev", "fetched_at"):
            if f not in render:
                e(f"render.{f} is required")
        if render.get("dir") and render["dir"] != f"{RENDER_ROOT}/{key}":
            e(f"render.dir must be {RENDER_ROOT}/{key}")
        for f in ("screenshot", "html"):
            v = str(render.get(f, ""))
            if v and not v.startswith(f"{RENDER_ROOT}/{key}/"):
                e(f"render.{f} must live under {RENDER_ROOT}/{key}/")
        for f in ("screenshot_sha256", "html_sha256"):
            if f in render and not SHA_RE.match(str(render[f])):
                e(f"render.{f} must be a lowercase sha256 hex digest")
        if "rev" in render and (not is_int(render["rev"]) or (hist and render["rev"] > last_rev)):
            e(f"render.rev {render.get('rev')} is not a revision in history")
        if check_files and root:
            for f, hf in (("screenshot", "screenshot_sha256"), ("html", "html_sha256")):
                path = os.path.join(root, str(render.get(f, "")))
                if not render.get(f) or not os.path.isfile(path):
                    e(f"render.{f} file is missing: {render.get(f)}")
                elif render.get(hf) and sha256_file(path) != render[hf]:
                    e(f"render.{f} {render[f]} does not match its stored sha256 — the file changed after "
                      "approval; re-fetch with get_screen and re-approve")
    if status in APPROVED:
        if s.get("approved_by") not in APPROVERS:
            e(f"status {status} needs approved_by = owner | design_quality_reviewer")
        if not ISO_RE.match(str(s.get("approved_at") or "")):
            e(f"status {status} needs approved_at (ISO-8601)")
        ar = s.get("approved_rev")
        if not is_int(ar):
            e(f"status {status} needs approved_rev")
        elif hist and ar != last_rev:
            e(f"approved_rev {ar} is not the latest revision ({last_rev}) — a newer render is pending_approval")
        if isinstance(render, dict) and is_int(ar) and render.get("rev") != ar:
            e(f"the stored render is rev {render.get('rev')} but rev {ar} was approved — fetch the approved render")
    if s.get("approved_by") is not None and s.get("approved_by") not in APPROVERS:
        e("approved_by must be owner | design_quality_reviewer")
    if s.get("approved_by") == "design_quality_reviewer":
        orv = s.get("owner_review")
        if not isinstance(orv, dict) or orv.get("status") not in ("pending", "accepted", "changes_requested"):
            e("approved by design_quality_reviewer (autonomous) — owner_review {status: pending|accepted|"
              "changes_requested} must list it for the owner")
    fid = s.get("fidelity")
    if s.get("origin") == "imported" or status == "import_low_fidelity":
        if not isinstance(fid, dict):
            e("an imported screen needs its fidelity record (score, threshold, attempts, method)")
    if isinstance(fid, dict):
        for f in ("score", "threshold"):
            if not is_num(fid.get(f)) or not 0 <= fid[f] <= 1:
                e(f"fidelity.{f} must be a number in [0, 1]")
        if not is_int(fid.get("attempts")) or not 1 <= fid["attempts"] <= 4:
            e("fidelity.attempts must be 1..4 (one generation + at most 3 corrections)")
        if not fid.get("method"):
            e("fidelity.method is required (the scorer and its version)")
        if is_num(fid.get("score")) and is_num(fid.get("threshold")):
            low = fid["score"] < fid["threshold"]
            if status == "import_low_fidelity" and not low:
                e("status import_low_fidelity but fidelity.score is not below the threshold")
            if low and status in APPROVED and s.get("approved_by") != "owner":
                e("a low-fidelity import can only be approved by the owner")
            if low and status not in APPROVED and status not in ("import_low_fidelity", "pending_approval",
                                                                  "drift", "design_gap", "sync_back_pending"):
                e(f"fidelity {fid['score']} below threshold {fid['threshold']} — status must be import_low_fidelity")
    devs = s.get("deviations", [])
    if not isinstance(devs, list):
        e("deviations must be an array")
        devs = []
    unsynced = 0
    hist_ops = {r.get("rev"): r.get("op") for r in hist if isinstance(r, dict)}
    for i, d in enumerate(devs):
        dp = f"deviations[{i}]"
        if not isinstance(d, dict):
            e(f"{dp} must be an object")
            continue
        if not DEV_RE.match(str(d.get("id", ""))):
            e(f"{dp}.id must look like DEV-<phase>-<nnn>")
        for f in ("what", "why"):
            if len(str(d.get(f, "")).strip()) < 5:
                e(f"{dp}.{f} must say {'what differs from the render' if f == 'what' else 'why'}")
        if not is_int(d.get("phase")):
            e(f"{dp}.phase is required")
        if d.get("source") not in ("ui_developer", "mobile_developer", "hotfix", "audit"):
            e(f"{dp}.source must be ui_developer | mobile_developer | hotfix | audit")
        res = d.get("resolution")
        if res is not None and res not in ("fixed", "accepted"):
            e(f"{dp}.resolution must be fixed | accepted")
        if res == "accepted":
            if d.get("synced_rev") is None:
                unsynced += 1
            elif hist_ops.get(d["synced_rev"]) != "sync_back":
                e(f"{dp}.synced_rev {d['synced_rev']} is not a sync_back revision in history")
    if status == "sync_back_pending" and unsynced == 0:
        e("status sync_back_pending but no accepted deviation is waiting to be synced back")
    if unsynced and status in APPROVED:
        e(f"{unsynced} accepted deviation(s) not yet synced back to Stitch — status must be sync_back_pending")
    return errs


# ----------------------------------------------------------------------------------------------- gate
def load_manifest(root, phase, agent):
    path = os.path.join(root, "agent_state", "phases", str(phase), agent, "manifest.json")
    if not os.path.isfile(path):
        return None, path
    try:
        with open(path) as f:
            return json.load(f), path
    except (OSError, ValueError) as ex:
        return {"__error__": str(ex)}, path


def gate(root, phase, file):
    """Return (blocking[], warnings[], notes[])."""
    blocking, warnings, notes = [], [], []
    path = os.path.join(root, file)
    if not os.path.isfile(path):
        notes.append(f"no {file} — the Stitch design gate does not apply to this project")
        return blocking, warnings, notes
    try:
        with open(path) as f:
            state = json.load(f)
    except (OSError, ValueError) as ex:
        return [f"{file} is not valid JSON: {ex}"], warnings, notes
    for err in validate(state, root, check_files=True):
        blocking.append(f"{file} invalid — {err}")
    screens = state.get("screens") if isinstance(state.get("screens"), dict) else {}
    # 1. nothing pending anywhere
    for key, s in sorted(screens.items()):
        if not isinstance(s, dict):
            continue
        st = s.get("status")
        if st == "pending_approval":
            blocking.append(f"screen {key} is pending_approval — approve it (/stitch request … approval loop) "
                            "or revert the revision before the gate")
        elif st == "sync_back_pending":
            blocking.append(f"screen {key} has accepted deviations not synced back to Stitch — run /stitch sync-back")
        elif st == "drift":
            blocking.append(f"screen {key} ({s.get('route')}) is in drift from its approved render — fix the code "
                            "or accept the deviation and sync it back")
        if s.get("approved_by") == "design_quality_reviewer" and \
                (s.get("owner_review") or {}).get("status") == "pending":
            notes.append(f"screen {key} was approved autonomously; it is on the owner-review list")
    # 2. every UI route this phase changed has a current approved baseline
    changed = []
    for agent, app in (("ui_developer", "web"), ("mobile_developer", "mobile")):
        m, mpath = load_manifest(root, phase, agent)
        if m is None:
            continue
        if "__error__" in m:
            blocking.append(f"{mpath} is not valid JSON: {m['__error__']}")
            continue
        for sc in m.get("screens", []) or []:
            if isinstance(sc, dict) and sc.get("route"):
                changed.append((agent, app, sc.get("route"), sc.get("stitch_screen")))
        for d in m.get("stitch_deviations", []) or []:
            check_deviation(d, screens, agent, mpath, blocking)
    if not changed:
        notes.append(f"no UI route changed in phase {phase} (no ui_developer / mobile_developer manifest screens)")
    for agent, app, route, explicit in changed:
        if explicit:
            matches = [explicit] if explicit in screens else []
            if not matches:
                blocking.append(f"{agent} route {route} names stitch_screen '{explicit}', which stitch.json lacks")
                continue
        else:
            matches = sorted(k for k, s in screens.items()
                             if isinstance(s, dict) and s.get("app") == app and s.get("route") == route)
        if not matches:
            blocking.append(f"{app} route {route} changed in phase {phase} but has no Stitch screen — design it "
                            "in Stitch first (/stitch request) and approve it")
            continue
        for key in matches:
            s = screens[key]
            st = s.get("status")
            if st in APPROVED:
                notes.append(f"{app} {route} → {key}: {st} (approved by {s.get('approved_by')}, rev {s.get('approved_rev')})")
            elif st == "no_baseline" and isinstance(s.get("deferred"), dict) and \
                    s["deferred"].get("reason") == "stitch_unavailable":
                warnings.append(f"{app} {route} → {key}: no_baseline — Stitch was unreachable "
                                f"({s['deferred'].get('detail')}); queued for Stitch, built from the wireframe")
            elif st in ("pending_approval", "sync_back_pending", "drift"):
                pass  # already reported above
            else:
                blocking.append(f"{app} {route} → {key} is {st}, not approved/conformant — the code was built "
                                "without an approved Stitch baseline")
    return blocking, warnings, notes


def check_deviation(d, screens, agent, mpath, blocking):
    if not isinstance(d, dict) or not d.get("id") or not d.get("screen"):
        blocking.append(f"{mpath}: stitch_deviations entry needs id and screen: {json.dumps(d)[:120]}")
        return
    s = screens.get(d["screen"])
    if not isinstance(s, dict):
        blocking.append(f"{agent} deviation {d['id']} names screen '{d['screen']}', which stitch.json lacks")
        return
    rec = next((x for x in s.get("deviations", []) or [] if isinstance(x, dict) and x.get("id") == d["id"]), None)
    if rec is None or rec.get("resolution") not in ("fixed", "accepted"):
        blocking.append(f"{agent} deviation {d['id']} on {d['screen']} ({d.get('what', '')[:60]}) is unresolved — "
                        "ui_standards_auditor must fix it (drift) or accept it")
    elif rec["resolution"] == "accepted" and rec.get("synced_rev") is None:
        blocking.append(f"deviation {d['id']} on {d['screen']} was accepted but never synced back to Stitch "
                        "(/stitch sync-back)")


# --------------------------------------------------------------------------------------------- writers
def load(path):
    if not os.path.isfile(path):
        return {"schema": SCHEMA, "projectId": None, "screens": {}, "queue": [], "log": []}
    with open(path) as f:
        return json.load(f)


def save(path, state):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def log(state, op, key, result):
    state.setdefault("log", []).append({"ts": now(), "op": op, "key": key, "result": result})


def ensure_screen(state, key, a):
    screens = state.setdefault("screens", {})
    s = screens.get(key)
    if s is None:
        if not KEY_RE.match(key):
            raise SystemExit(f"stitch-state: '{key}' is not a screen key (<slug>.<desktop|mobile|tablet>)")
        for f in ("device", "app", "route"):
            if not getattr(a, f, None):
                raise SystemExit(f"stitch-state: new screen {key} needs --{f}")
        s = screens[key] = {"screenKey": key, "screenId": None, "deviceType": a.device, "app": a.app,
                            "route": a.route, "status": "no_baseline", "origin": "pending", "history": []}
    return s


def cmd_revise(a, path):
    state = load(path)
    s = ensure_screen(state, a.key, a)
    hist = s.setdefault("history", [])
    rev = (hist[-1]["rev"] + 1) if hist else 1
    entry = {"rev": rev, "ts": now(), "op": a.op, "screenId": a.screen_id, "by": a.by,
             "previous_screenId": s.get("screenId")}
    if a.prompt:
        entry["prompt"] = a.prompt
    if a.source:
        entry["prompt_source"] = a.source
    if a.phase is not None:
        entry["phase"] = a.phase
        s["phase"] = a.phase
    if a.fidelity is not None:
        entry["fidelity"] = a.fidelity
    hist.append(entry)
    s["screenId"] = a.screen_id
    s.pop("deferred", None)
    if s.get("origin") == "pending":
        s["origin"] = {"import": "imported", "adopt": "adopted", "generate": "generated"}.get(a.op, "generated")
    s["status"] = "pending_approval"
    state["queue"] = [q for q in state.get("queue", []) if q.get("screenKey") != a.key]
    log(state, a.op, a.key, f"rev {rev} screen {a.screen_id} pending approval")
    save(path, state)
    print(f"{a.key}: rev {rev} ({a.op}) → screen {a.screen_id}, pending_approval")


def cmd_render(a, path, root):
    state = load(path)
    s = state.get("screens", {}).get(a.key)
    if not s or not s.get("history"):
        raise SystemExit(f"stitch-state: {a.key} has no revision — run revise first")
    d = os.path.join(root, RENDER_ROOT, a.key)
    os.makedirs(d, exist_ok=True)
    shot, html = os.path.join(d, "screenshot.png"), os.path.join(d, "screen.html")
    if os.path.abspath(a.screenshot) != os.path.abspath(shot):
        shutil.copyfile(a.screenshot, shot)
    if os.path.abspath(a.html) != os.path.abspath(html):
        shutil.copyfile(a.html, html)
    rel = f"{RENDER_ROOT}/{a.key}"
    s["render"] = {"dir": rel, "screenshot": f"{rel}/screenshot.png", "html": f"{rel}/screen.html",
                   "screenshot_sha256": sha256_file(shot), "html_sha256": sha256_file(html),
                   "rev": s["history"][-1]["rev"], "fetched_at": now()}
    log(state, "render", a.key, f"rev {s['render']['rev']} stored")
    save(path, state)
    print(f"{a.key}: render rev {s['render']['rev']} stored in {rel}/ (sha256 {s['render']['screenshot_sha256'][:12]}…)")


def cmd_approve(a, path):
    state = load(path)
    s = state.get("screens", {}).get(a.key)
    if not s or not s.get("history"):
        raise SystemExit(f"stitch-state: {a.key} has no revision to approve")
    last = s["history"][-1]["rev"]
    if not isinstance(s.get("render"), dict) or s["render"].get("rev") != last:
        raise SystemExit(f"stitch-state: {a.key} rev {last} has no stored render — fetch it (render) before approving")
    fid = s.get("fidelity") or {}
    if a.by != "owner" and fid and fid.get("score", 1) < fid.get("threshold", 0):
        raise SystemExit(f"stitch-state: {a.key} is a low-fidelity import ({fid.get('score')}) — only the owner may approve it")
    s.update({"status": "approved", "approved_by": a.by, "approved_at": now(), "approved_rev": last})
    if a.by == "design_quality_reviewer":
        s["owner_review"] = {"status": "pending", "at": None}
    else:
        s.pop("owner_review", None)
    if a.note:
        s.setdefault("owner_review", {"status": "accepted", "at": now()})["note"] = a.note
    log(state, "approve", a.key, f"rev {last} by {a.by}")
    save(path, state)
    print(f"{a.key}: rev {last} approved by {a.by}")


def cmd_owner_review(a, path):
    state = load(path)
    s = state.get("screens", {}).get(a.key)
    if not s:
        raise SystemExit(f"stitch-state: no screen {a.key}")
    s["owner_review"] = {"status": a.decision, "at": now()}
    if a.note:
        s["owner_review"]["note"] = a.note
    if a.decision == "accepted":
        s["approved_by"], s["approved_at"] = "owner", now()
        s.pop("owner_review", None)
    log(state, "owner_review", a.key, a.decision)
    save(path, state)
    print(f"{a.key}: owner review {a.decision}")


def cmd_defer(a, path):
    state = load(path)
    s = ensure_screen(state, a.key, a)
    if s.get("status") in APPROVED:
        print(f"{a.key}: already has an approved baseline; the change is queued only")
    else:
        s["status"] = "no_baseline"
        s["deferred"] = {"reason": "stitch_unavailable", "at": now(), "detail": a.detail, "run": a.run}
    q = {"screenKey": a.key, "op": "generate" if not s.get("screenId") else "edit",
         "reason": f"stitch_unavailable: {a.detail}", "ts": now()}
    if a.prompt:
        q["prompt"] = a.prompt
    state.setdefault("queue", []).append(q)
    log(state, "defer", a.key, a.detail)
    save(path, state)
    print(f"{a.key}: no_baseline, queued for Stitch ({a.detail})")


def cmd_deviation(a, path):
    state = load(path)
    s = state.get("screens", {}).get(a.key)
    if not s:
        raise SystemExit(f"stitch-state: no screen {a.key}")
    devs = s.setdefault("deviations", [])
    d = next((x for x in devs if x.get("id") == a.id), None)
    if d is None:
        d = {"id": a.id, "phase": a.phase, "what": a.what, "why": a.why, "source": a.source}
        devs.append(d)
    if a.resolution:
        d.update({"resolution": a.resolution, "resolved_by": a.by, "resolved_at": now()})
        if a.resolution == "accepted":
            s["status"] = "sync_back_pending"
            state.setdefault("queue", []).append({"screenKey": a.key, "op": "sync_back",
                                                  "reason": f"{a.id} accepted: {d['what'][:80]}", "ts": now()})
    if a.synced_rev:
        d["synced_rev"] = a.synced_rev
        state["queue"] = [q for q in state.get("queue", [])
                          if not (q.get("screenKey") == a.key and q.get("op") == "sync_back")]
    log(state, "deviation", a.key, f"{a.id} {a.resolution or 'recorded'}")
    save(path, state)
    print(f"{a.key}: deviation {a.id} {a.resolution or 'recorded'}")


def cmd_status_set(a, path):
    state = load(path)
    s = state.get("screens", {}).get(a.key)
    if not s:
        raise SystemExit(f"stitch-state: no screen {a.key}")
    if a.status not in ("conformant", "drift", "design_gap", "orphan"):
        raise SystemExit("stitch-state: status-set takes conformant | drift | design_gap | orphan "
                         "(approval goes through approve, Stitch changes through revise)")
    if a.status == "conformant" and not s.get("approved_by"):
        raise SystemExit(f"stitch-state: {a.key} was never approved — it can't be conformant")
    s["status"] = a.status
    log(state, "audit", a.key, a.status)
    save(path, state)
    print(f"{a.key}: {a.status}")


def cmd_ready(a, path, root):
    keys = list(a.keys)
    if a.phase:
        bl = os.path.join(root, "docs", "design", "phases", str(a.phase), "stitch-baseline.md")
        if not os.path.isfile(bl):
            print(f"NOT READY: {os.path.relpath(bl, root)} is missing — /design (Stitch) never listed this phase's screens")
            return 2
        for line in open(bl):
            if line.lstrip().startswith("|"):
                cell = line.strip().strip("|").split("|")[0].strip().strip("`")
                if KEY_RE.match(cell):
                    keys.append(cell)
    if not keys:
        print("ready: no screen keys given (pass KEYs or --phase N)")
        return 3
    if not os.path.isfile(path):
        print(f"NOT READY: {os.path.relpath(path, root)} is missing")
        return 2
    state = load(path)
    screens = state.get("screens", {})
    bad = 0
    for key in dict.fromkeys(keys):
        s = screens.get(key)
        errs = validate_screen(key, s, root, True) if isinstance(s, dict) else [f"{key}: not in stitch.json"]
        st = s.get("status") if isinstance(s, dict) else None
        deferred = isinstance(s, dict) and st == "no_baseline" and isinstance(s.get("deferred"), dict)
        if isinstance(s, dict) and st in APPROVED and not errs:
            print(f"READY      {key}: rev {s.get('approved_rev')} approved by {s.get('approved_by')} "
                  f"→ {s['render']['screenshot']}")
        elif deferred:
            print(f"DEFERRED   {key}: Stitch was unavailable ({s['deferred'].get('detail')}) — build from the wireframe; queued")
        else:
            bad += 1
            why = "; ".join(errs[:2]) if errs else f"status {st}"
            print(f"NOT READY  {key}: {why}")
    return 2 if bad else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=".")
    ap.add_argument("--file", default=DEFAULT_FILE)
    sub = ap.add_subparsers(dest="cmd")
    v = sub.add_parser("validate")
    v.add_argument("--check-files", action="store_true")
    g = sub.add_parser("gate")
    g.add_argument("--phase", required=True)
    new = argparse.ArgumentParser(add_help=False)
    new.add_argument("--device", choices=DEVICES)
    new.add_argument("--app", choices=APPS)
    new.add_argument("--route")
    r = sub.add_parser("revise", parents=[new])
    r.add_argument("key")
    r.add_argument("--op", required=True, choices=OPS)
    r.add_argument("--screen-id", required=True)
    r.add_argument("--prompt", default="")
    r.add_argument("--source", choices=PROMPT_SOURCES)
    r.add_argument("--phase", type=int)
    r.add_argument("--by", default="parent")
    r.add_argument("--fidelity", type=float)
    rd = sub.add_parser("render")
    rd.add_argument("key")
    rd.add_argument("--screenshot", required=True)
    rd.add_argument("--html", required=True)
    apv = sub.add_parser("approve")
    apv.add_argument("key")
    apv.add_argument("--by", required=True, choices=APPROVERS)
    apv.add_argument("--note")
    orv = sub.add_parser("owner-review")
    orv.add_argument("key")
    orv.add_argument("--decision", required=True, choices=["accepted", "changes_requested"])
    orv.add_argument("--note")
    df = sub.add_parser("defer", parents=[new])
    df.add_argument("key")
    df.add_argument("--detail", required=True)
    df.add_argument("--run", choices=["autonomous", "interactive"], default="autonomous")
    df.add_argument("--prompt")
    dv = sub.add_parser("deviation")
    dv.add_argument("key")
    dv.add_argument("--id", required=True)
    dv.add_argument("--phase", type=int, required=True)
    dv.add_argument("--what", default="")
    dv.add_argument("--why", default="")
    dv.add_argument("--source", choices=["ui_developer", "mobile_developer", "hotfix", "audit"], default="ui_developer")
    dv.add_argument("--resolution", choices=["fixed", "accepted"])
    dv.add_argument("--by", default="ui_standards_auditor")
    dv.add_argument("--synced-rev", type=int)
    ss = sub.add_parser("status-set")
    ss.add_argument("key")
    ss.add_argument("status")
    rdy = sub.add_parser("ready")
    rdy.add_argument("keys", nargs="*")
    rdy.add_argument("--phase")
    sub.add_parser("review-list")
    h = sub.add_parser("hash")
    h.add_argument("path")
    a = ap.parse_args(argv)
    root = os.path.abspath(a.root)
    path = a.file if os.path.isabs(a.file) else os.path.join(root, a.file)

    if a.cmd == "hash":
        print(sha256_file(a.path))
        return 0
    if a.cmd == "validate":
        if not os.path.isfile(path):
            print(f"stitch-state: {path} not found", file=sys.stderr)
            return 3
        try:
            with open(path) as f:
                state = json.load(f)
        except ValueError as ex:
            print(f"INVALID: not JSON — {ex}")
            return 2
        errs = validate(state, root, a.check_files)
        for err in errs:
            print(f"INVALID: {err}")
        if not errs:
            n = len(state.get("screens", {}))
            print(f"OK: {a.file} is a valid {SCHEMA} ({n} screen(s){', files + hashes checked' if a.check_files else ''})")
        return 2 if errs else 0
    if a.cmd == "gate":
        blocking, warnings, notes = gate(root, a.phase, a.file)
        for n in notes:
            print(f"  · {n}")
        for w in warnings:
            print(f"WARNING: {w}")
        for b in blocking:
            print(f"BLOCKING: {b}")
        return 2 if blocking else 0
    if a.cmd == "ready":
        return cmd_ready(a, path, root)
    if a.cmd == "review-list":
        state = load(path)
        rows = [(k, s) for k, s in sorted(state.get("screens", {}).items())
                if (s.get("owner_review") or {}).get("status") in ("pending", "changes_requested")
                or s.get("status") == "import_low_fidelity"]
        for k, s in rows:
            why = "low-fidelity import" if s.get("status") == "import_low_fidelity" else \
                f"approved by {s.get('approved_by')} at {s.get('approved_at')}"
            shot = (s.get("render") or {}).get("screenshot", "-")
            print(f"{k}\t{s.get('route')}\t{why}\t{shot}")
        print(f"{len(rows)} screen(s) awaiting the owner's review", file=sys.stderr)
        return 0
    if a.cmd is None:
        ap.print_help()
        return 3
    handlers = {"revise": lambda: cmd_revise(a, path), "render": lambda: cmd_render(a, path, root),
                "approve": lambda: cmd_approve(a, path), "owner-review": lambda: cmd_owner_review(a, path),
                "defer": lambda: cmd_defer(a, path), "deviation": lambda: cmd_deviation(a, path),
                "status-set": lambda: cmd_status_set(a, path)}
    handlers[a.cmd]()
    errs = validate(load(path), root, False)
    if errs:
        for err in errs:
            print(f"WARNING after write: {err}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
