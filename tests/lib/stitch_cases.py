#!/usr/bin/env python3
"""stitch_cases.py - offline cases for the Stitch-first design tooling (run by tests/stitch-core.test.sh).

  validate : docs/design/stitch.json (sdlc.stitch-state/v2) good and bad fixtures, the doc example, and
             agreement with skills/ui/stitch-state.schema.json when the jsonschema package is installed
  writers  : revise → render → approve / defer / deviation flows through stitch-state.py's CLI
  gate     : stitch-state.py gate PASS and BLOCK cases (verify-gate.sh check (g) calls it)
  fidelity : stitch-fidelity.py on known images (pure-Python PNG decoder, every filter type, Pillow
             agreement when installed) and the structural score on a committed capture fixture
No network, no browser. Exit 0 = all pass.
"""
import copy
import importlib.util
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
HOOKS = os.path.join(ROOT, ".claude", "hooks")
STATE = os.path.join(HOOKS, "stitch-state.py")
FID = os.path.join(HOOKS, "stitch-fidelity.py")
SCHEMA_FILE = os.path.join(ROOT, ".claude", "skills", "ui", "stitch-state.schema.json")
SKILL = os.path.join(ROOT, ".claude", "skills", "ui", "stitch-design.md")
FIX = os.path.join(ROOT, "tests", "fixtures", "stitch")

PASS = FAIL = 0


def check(cond, name, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ FAIL: {name}{(' — ' + detail) if detail else ''}")


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


st = load_module(STATE, "stitch_state")
fid = load_module(FID, "stitch_fidelity")


# ----------------------------------------------------------------------------------------- PNG writer
def write_png(path, w, h, px, filters=(0,)):
    """px(x, y) -> (r, g, b). Rows cycle through `filters` so the decoder sees every filter type."""
    rows, prev = [], bytearray(w * 3)
    for y in range(h):
        line = bytearray()
        for x in range(w):
            line.extend(px(x, y))
        f = filters[y % len(filters)]
        out = bytearray([f])
        for i in range(len(line)):
            a = line[i - 3] if i >= 3 else 0
            b = prev[i]
            c = prev[i - 3] if i >= 3 else 0
            if f == 0:
                v = line[i]
            elif f == 1:
                v = line[i] - a
            elif f == 2:
                v = line[i] - b
            elif f == 3:
                v = line[i] - ((a + b) >> 1)
            else:
                v = line[i] - fid._paeth(a, b, c)
            out.append(v & 0xFF)
        rows.append(bytes(out))
        prev = line

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) \
        + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(data)


def page(kind, dy=0, tint=0):
    """A synthetic 'screenshot': header bar, then a sidebar + table ('table') or a card grid ('cards')."""
    def px(x, y):
        y2 = y - dy
        bg = (248 - tint, 250 - tint, 252)
        if y2 < 40:
            return (255, 255, 255) if y2 < 39 else (226, 232, 240)
        if kind == "table":
            if x < 140:
                return (255, 255, 255) if x < 139 else (226, 232, 240)
            if 60 <= y2 < 84 and 160 <= x < 320:
                return (15, 23, 42)   # heading text block
            if y2 >= 110 and (y2 - 110) % 36 < 2 and 160 <= x < 620:
                return (226, 232, 240)  # table row rules
            if y2 >= 110 and (y2 - 110) % 36 in range(12, 20) and 170 <= x < 600 and (x // 40) % 3 != 2:
                return (51, 65, 85)   # cell text
            return bg
        # cards: 2 x 2 big blue cards
        if 60 <= y2 < 300 and (40 <= x < 300 or 340 <= x < 600):
            return (37 + tint, 99, 235)
        if 330 <= y2 < 570 and (40 <= x < 300 or 340 <= x < 600):
            return (37 + tint, 99, 235)
        return bg
    return px


# ------------------------------------------------------------------------------------------ fixtures
def now():
    return "2026-10-01T10:00:00Z"


def make_project(tmp, screens=("orders-list.desktop",), versioned=False):
    """A project root with a valid stitch.json and real render files for each screen key.

    Default = the format the previous tool version wrote (no version labels, one render per screen).
    versioned=True labels rev 1 v0.1 and rev 2 v0.2, each with its own archived render under <key>/<label>/,
    and the top-level render being a copy of v0.2."""
    state = {"schema": st.SCHEMA, "projectId": "4044680601076201931", "projectTitle": "Acme — UI",
             "designSystem": {"assetId": "15996705518239280238", "source": "docs/design/DESIGN.md", "updated": "2026-10-01"},
             "screens": {}, "queue": [], "log": []}
    for key in screens:
        slug, dev = key.rsplit(".", 1)
        d = os.path.join(tmp, "docs", "design", "stitch", key)
        os.makedirs(d, exist_ok=True)
        write_png(os.path.join(d, "screenshot.png"), 16, 16, lambda x, y: (x * 8, y * 8, 128))
        with open(os.path.join(d, "screen.html"), "w") as f:
            f.write(f"<html><body><main><h1>{slug}</h1><button>New order</button></main></body></html>")
        rel = f"docs/design/stitch/{key}"
        arch = {}
        if versioned:
            for lab, shade in (("v0.1", 40), ("v0.2", 90)):
                ad = os.path.join(d, lab)
                os.makedirs(ad, exist_ok=True)
                write_png(os.path.join(ad, "screenshot.png"), 16, 16, lambda x, y, sh=shade: (x * 8, y * 8, sh))
                with open(os.path.join(ad, "screen.html"), "w") as f:
                    f.write(f"<html><body><main><h1>{slug} {lab}</h1></main></body></html>")
                arch[lab] = {"dir": f"{rel}/{lab}", "screenshot": f"{rel}/{lab}/screenshot.png",
                             "html": f"{rel}/{lab}/screen.html",
                             "screenshot_sha256": st.sha256_file(os.path.join(ad, "screenshot.png")),
                             "html_sha256": st.sha256_file(os.path.join(ad, "screen.html")),
                             "fetched_at": now()}
            for fn in ("screenshot.png", "screen.html"):      # the top-level copy = the latest (v0.2)
                shutil.copyfile(os.path.join(d, "v0.2", fn), os.path.join(d, fn))
        state["screens"][key] = {
            "screenKey": key, "screenId": "98b50e2d11", "deviceType": dev.upper(),
            "app": "mobile" if dev == "mobile" else "web", "route": "/" + slug.split("-")[0],
            "title": slug, "origin": "generated", "status": "approved", "approved_by": "owner",
            "approved_at": now(), "approved_rev": 2, "phase": 1,
            "render": {"dir": rel, "screenshot": f"{rel}/screenshot.png", "html": f"{rel}/screen.html",
                       "screenshot_sha256": st.sha256_file(os.path.join(d, "screenshot.png")),
                       "html_sha256": st.sha256_file(os.path.join(d, "screen.html")), "rev": 2, "fetched_at": now()},
            "wireframe": "docs/design/phases/1/specs/orders-list.wireframe.md",
            "history": [
                {"rev": 1, "ts": "2026-10-01T09:00:00Z", "op": "generate", "screenId": "11aa", "prompt": "Orders list…",
                 "prompt_source": "requirement", "phase": 1, "by": "/design"},
                {"rev": 2, "ts": "2026-10-01T09:30:00Z", "op": "edit", "screenId": "98b50e2d11",
                 "prompt": "Make the status column a badge", "prompt_source": "owner", "phase": 1, "by": "/stitch request",
                 "previous_screenId": "11aa"}]}
        if versioned:
            h = state["screens"][key]["history"]
            h[0].update(version="v0.1", render=arch["v0.1"])
            h[1].update(version="v0.2", render=arch["v0.2"])
            state["screens"][key]["render"].update(
                screenshot_sha256=arch["v0.2"]["screenshot_sha256"], html_sha256=arch["v0.2"]["html_sha256"])
    os.makedirs(os.path.join(tmp, "docs", "design"), exist_ok=True)
    save(tmp, state)
    return state


def save(tmp, state):
    with open(os.path.join(tmp, "docs", "design", "stitch.json"), "w") as f:
        json.dump(state, f, indent=2)


def manifest(tmp, phase, agent, screens, deviations=None):
    d = os.path.join(tmp, "agent_state", "phases", str(phase), agent)
    os.makedirs(d, exist_ok=True)
    m = {"phase": str(phase), "agent": agent, "screens": screens}
    if deviations is not None:
        m["stitch_deviations"] = deviations
    with open(os.path.join(d, "manifest.json"), "w") as f:
        json.dump(m, f)


def run(args, cwd):
    p = subprocess.run([sys.executable, STATE, "--root", cwd] + args, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


# ------------------------------------------------------------------------------------------- validate
def cases_validate():
    print("── stitch.json schema: good and bad fixtures ──")
    with tempfile.TemporaryDirectory() as tmp:
        good = make_project(tmp, ("orders-list.desktop", "orders-list.mobile"))
        errs = st.validate(good, tmp, check_files=True)
        check(not errs, "a complete approved state (web DESKTOP + RN MOBILE) validates with files + hashes", "; ".join(errs))

        def bad(name, mutate, needle, files=False):
            s = copy.deepcopy(good)
            mutate(s)
            errs = st.validate(s, tmp, check_files=files)
            check(any(needle in e for e in errs), f"rejects: {name}", f"wanted '{needle}', got {errs[:3]}")
            return s

        o = "orders-list.desktop"
        bad("wrong schema id", lambda s: s.update(schema="v1"), "schema must be")
        bad("approved without approved_by", lambda s: s["screens"][o].pop("approved_by"), "needs approved_by")
        bad("approved_by someone else", lambda s: s["screens"][o].update(approved_by="ux_designer"), "approved_by")
        bad("approved without approved_at", lambda s: s["screens"][o].update(approved_at=None), "needs approved_at")
        bad("approved rev is not the latest revision",
            lambda s: s["screens"][o].update(approved_rev=1), "not the latest revision")
        bad("autonomous (design_quality_reviewer) approval not on the owner-review list",
            lambda s: s["screens"][o].update(approved_by="design_quality_reviewer"), "owner_review")
        bad("status outside the enum", lambda s: s["screens"][o].update(status="done"), "status must be one of")
        bad("key suffix disagrees with deviceType", lambda s: s["screens"][o].update(deviceType="MOBILE"), "does not match deviceType")
        bad("React Native screen marked DESKTOP",
            lambda s: s["screens"]["orders-list.mobile"].update(deviceType="DESKTOP", app="mobile"), "can't be DESKTOP")
        bad("screenId is not the latest revision's (edit_screens returns a new id)",
            lambda s: s["screens"][o].update(screenId="11aa"), "latest revision's screenId")
        bad("revision without its prompt", lambda s: s["screens"][o]["history"][1].update(prompt=""), "must record the prompt")
        bad("revisions out of order", lambda s: s["screens"][o]["history"][1].update(rev=1), "greater than the previous")
        bad("approved without a stored render", lambda s: s["screens"][o].pop("render"), "needs the fetched render")
        bad("render stored outside docs/design/stitch/<key>/",
            lambda s: s["screens"][o]["render"].update(screenshot="tmp/x.png"), "must live under")
        bad("render file changed after approval (hash mismatch)",
            lambda s: s["screens"][o]["render"].update(screenshot_sha256="0" * 64), "does not match its stored sha256", files=True)
        bad("imported screen without a fidelity record", lambda s: s["screens"][o].update(origin="imported"), "fidelity record")
        bad("low-fidelity import approved by design_quality_reviewer",
            lambda s: s["screens"][o].update(origin="imported", approved_by="design_quality_reviewer",
                                             owner_review={"status": "pending", "at": None},
                                             fidelity={"score": 0.6, "threshold": 0.75, "attempts": 4, "method": "m"}),
            "only be approved by the owner")
        bad("import_low_fidelity whose score is above threshold",
            lambda s: s["screens"][o].update(status="import_low_fidelity", origin="imported",
                                             fidelity={"score": 0.9, "threshold": 0.75, "attempts": 1, "method": "m"}),
            "not below the threshold")
        bad("more than 3 import corrections",
            lambda s: s["screens"][o].update(origin="imported", fidelity={"score": 0.9, "threshold": 0.75, "attempts": 5, "method": "m"}),
            "attempts must be 1..4")
        bad("sync_back_pending with nothing to sync", lambda s: s["screens"][o].update(status="sync_back_pending"),
            "no accepted deviation is waiting")
        bad("approved while an accepted deviation is unsynced",
            lambda s: s["screens"][o].update(deviations=[{"id": "DEV-1-001", "phase": 1, "what": "48px rows",
                                                          "why": "touch target", "source": "ui_developer",
                                                          "resolution": "accepted"}]), "not yet synced back")
        bad("deviation without a reason", lambda s: s["screens"][o].update(deviations=[
            {"id": "DEV-1-001", "phase": 1, "what": "48px rows", "why": "", "source": "ui_developer"}]), ".why must say")
        bad("deviation synced to a revision that isn't a sync_back",
            lambda s: s["screens"][o].update(deviations=[{"id": "DEV-1-001", "phase": 1, "what": "48px rows",
                                                          "why": "touch target", "source": "ui_developer",
                                                          "resolution": "accepted", "synced_rev": 2}]), "not a sync_back revision")
        bad("deferral without the probe error",
            lambda s: s["screens"][o].update(status="no_baseline", deferred={"reason": "stitch_unavailable", "at": now(), "detail": ""}),
            "deferred needs")
        bad("non-orphan screen without a route", lambda s: s["screens"][o].update(route=None), "route is required")
        bad("null projectId with a rendered screen", lambda s: s.update(projectId=None), "projectId is null")
        bad("unknown screen field", lambda s: s["screens"][o].update(pages="x"), "unknown field")

        # no_baseline with a deferral and no project: valid (autonomous run, Stitch never reachable)
        s = {"schema": st.SCHEMA, "projectId": None, "screens": {"settings.desktop": {
            "screenKey": "settings.desktop", "screenId": None, "deviceType": "DESKTOP", "app": "web", "route": "/settings",
            "status": "no_baseline", "origin": "pending",
            "deferred": {"reason": "stitch_unavailable", "at": now(), "detail": "get_project: MCP server not connected", "run": "autonomous"}}},
             "queue": [{"screenKey": "settings.desktop", "op": "generate", "reason": "stitch_unavailable", "ts": now()}]}
        errs = st.validate(s)
        check(not errs, "an autonomous no_baseline deferral (Stitch unreachable, no project yet) validates", "; ".join(errs))

        # JSON Schema agreement (structure) when jsonschema is installed
        try:
            import jsonschema  # noqa: F401
            with open(SCHEMA_FILE) as f:
                schema = json.load(f)
            v = jsonschema.Draft202012Validator(schema)
            ge = [e.message for e in v.iter_errors(good)]
            check(not ge, "skills/ui/stitch-state.schema.json accepts the good fixture", "; ".join(ge[:3]))
            check(not list(v.iter_errors(s)), "the JSON Schema accepts the autonomous deferral fixture")
            for name, mut in (("approved without approved_by", lambda x: x["screens"][o].pop("approved_by")),
                              ("dqr approval without owner_review", lambda x: x["screens"][o].update(approved_by="design_quality_reviewer")),
                              ("unknown status", lambda x: x["screens"][o].update(status="done")),
                              ("imported without fidelity", lambda x: x["screens"][o].update(origin="imported"))):
                b = copy.deepcopy(good)
                mut(b)
                check(bool(list(v.iter_errors(b))), f"the JSON Schema also rejects: {name}")
        except ImportError:
            print("  · jsonschema not installed — schema-file agreement not checked (stitch-state.py is the authority)")

    print("── the stitch.json example in stitch-design.md is valid ──")
    text = open(SKILL).read()
    blocks = [b for b in re.findall(r"```json\n(.*?)```", text, re.S) if st.SCHEMA in b]
    check(bool(blocks), "stitch-design.md shows a sdlc.stitch-state/v2 example")
    for b in blocks[:1]:
        try:
            ex = json.loads(b)
            errs = st.validate(ex)
            check(not errs, "the documented example passes stitch-state.py validate", "; ".join(errs[:3]))
        except ValueError as e:
            check(False, "the documented example is valid JSON", str(e))


# -------------------------------------------------------------------------------------------- writers
def cases_writers():
    print("── stitch-state.py writers: request → render → approve, defer, deviation → sync-back ──")
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "docs", "design"))
        save(tmp, {"schema": st.SCHEMA, "projectId": "123", "screens": {}, "queue": [], "log": []})
        shot, html = os.path.join(tmp, "s.png"), os.path.join(tmp, "s.html")
        write_png(shot, 8, 8, lambda x, y: (10, 20, 30))
        open(html, "w").write("<html><body><h1>Invoices</h1></body></html>")
        k = "invoices.desktop"
        rc, out = run(["revise", k, "--op", "generate", "--screen-id", "555", "--prompt", "Invoices list for finance admins",
                       "--source", "requirement", "--phase", "2", "--device", "DESKTOP", "--app", "web", "--route", "/invoices"], tmp)
        check(rc == 0 and "pending_approval" in out, "revise creates the screen as pending_approval", out)
        rc, out = run(["approve", k, "--by", "owner"], tmp)
        check(rc != 0 and "no stored render" in out, "approve refuses a revision whose render was never fetched", out)
        rc, out = run(["render", k, "--screenshot", shot, "--html", html], tmp)
        check(rc == 0 and os.path.isfile(os.path.join(tmp, "docs/design/stitch/invoices.desktop/screenshot.png")),
              "render copies screenshot + HTML into docs/design/stitch/<key>/ and hashes them", out)
        rc, out = run(["approve", k, "--by", "design_quality_reviewer"], tmp)
        check(rc == 0, "design_quality_reviewer can approve (autonomous mode)", out)
        rc, out = run(["review-list"], tmp)
        check(k in out and "design_quality_reviewer" in out, "an autonomous approval is on the owner-review list", out)
        rc, out = run(["validate", "--check-files"], tmp)
        check(rc == 0, "the written state validates with files + hashes", out)
        rc, out = run(["owner-review", k, "--decision", "accepted"], tmp)
        rc, out = run(["review-list"], tmp)
        check(k not in out, "the owner's acceptance takes it off the review list", out)
        # deviation accepted → sync_back_pending → sync_back revision → approve
        rc, out = run(["deviation", k, "--id", "DEV-2-001", "--phase", "2", "--what", "rows are 48px, not 40px",
                       "--why", "44px touch target on tablet", "--source", "ui_developer", "--resolution", "accepted"], tmp)
        state = json.load(open(os.path.join(tmp, "docs/design/stitch.json")))
        check(state["screens"][k]["status"] == "sync_back_pending" and any(q["op"] == "sync_back" for q in state["queue"]),
              "an accepted deviation makes the screen sync_back_pending and queues the sync-back", out)
        rc, out = run(["revise", k, "--op", "sync_back", "--screen-id", "556", "--prompt", "Rows are 48px tall (as built)",
                       "--source", "deviation", "--phase", "2"], tmp)
        rc, out = run(["deviation", k, "--id", "DEV-2-001", "--phase", "2", "--synced-rev", "2"], tmp)
        write_png(shot, 8, 8, lambda x, y: (11, 21, 31))
        run(["render", k, "--screenshot", shot, "--html", html], tmp)
        rc, out = run(["approve", k, "--by", "owner"], tmp)
        rc, out = run(["validate", "--check-files"], tmp)
        state = json.load(open(os.path.join(tmp, "docs/design/stitch.json")))
        s = state["screens"][k]
        check(rc == 0 and s["status"] == "approved" and s["approved_rev"] == 2 and s["screenId"] == "556"
              and not state["queue"], "sync-back: new revision, new screen id, re-approved, queue drained", out)
        # defer
        rc, out = run(["defer", "settings.mobile", "--detail", "list_projects: tool not found", "--device", "MOBILE",
                       "--app", "mobile", "--route", "/settings"], tmp)
        state = json.load(open(os.path.join(tmp, "docs/design/stitch.json")))
        check(state["screens"]["settings.mobile"]["status"] == "no_baseline"
              and state["screens"]["settings.mobile"]["deferred"]["reason"] == "stitch_unavailable",
              "defer records no_baseline + the probe error, queued for Stitch", out)
        rc, out = run(["status-set", "settings.mobile", "conformant"], tmp)
        check(rc != 0, "a never-approved screen can't be marked conformant", out)


# ----------------------------------------------------------------------------------------------- gate
def cases_gate():
    print("── stitch-state.py gate (verify-gate.sh check (g)) ──")

    def gate_case(name, setup, want_rc, needle=""):
        with tempfile.TemporaryDirectory() as tmp:
            state = make_project(tmp, ("orders-list.desktop", "orders-list.mobile"))
            setup(tmp, state)
            rc, out = run(["gate", "--phase", "1"], tmp)
            ok = rc == want_rc and (needle in out)
            check(ok, name, f"rc={rc} out={out.strip()[-300:]}")

    web = [{"route": "/orders", "component": "src/ui/pages/OrdersPage.tsx"}]
    gate_case("PASS: the changed web + mobile routes have approved, current, hash-matching screens",
              lambda t, s: (manifest(t, 1, "ui_developer", web), manifest(t, 1, "mobile_developer", [{"route": "/orders"}])), 0, "approved")
    gate_case("PASS: no stitch.json → not applicable", lambda t, s: os.remove(os.path.join(t, "docs/design/stitch.json")), 0, "does not apply")
    gate_case("BLOCK: a changed route with no Stitch screen",
              lambda t, s: manifest(t, 1, "ui_developer", web + [{"route": "/invoices"}]), 2, "/invoices changed in phase 1 but has no Stitch screen")

    def pending(t, s):
        s["screens"]["orders-list.desktop"]["status"] = "pending_approval"
        save(t, s)
        manifest(t, 1, "ui_developer", web)
    gate_case("BLOCK: a screen still pending_approval", pending, 2, "pending_approval")

    def tampered(t, s):
        with open(os.path.join(t, "docs/design/stitch/orders-list.desktop/screen.html"), "a") as f:
            f.write("<!-- edited -->")
        manifest(t, 1, "ui_developer", web)
    gate_case("BLOCK: the stored render no longer matches its hash", tampered, 2, "does not match its stored sha256")

    def newer_rev(t, s):
        h = s["screens"]["orders-list.desktop"]["history"]
        h.append({"rev": 3, "ts": now(), "op": "edit", "screenId": "777", "prompt": "add filter", "by": "/stitch request"})
        s["screens"]["orders-list.desktop"]["screenId"] = "777"
        save(t, s)
        manifest(t, 1, "ui_developer", web)
    gate_case("BLOCK: approved baseline is not the latest Stitch revision", newer_rev, 2, "not the latest revision")

    def drift(t, s):
        s["screens"]["orders-list.mobile"]["status"] = "drift"
        save(t, s)
    gate_case("BLOCK: drift left anywhere in the app", drift, 2, "drift")

    def unresolved(t, s):
        manifest(t, 1, "ui_developer", web, [{"id": "DEV-1-001", "screen": "orders-list.desktop", "what": "rows 48px", "why": "touch"}])
    gate_case("BLOCK: a developer deviation nobody resolved", unresolved, 2, "DEV-1-001 on orders-list.desktop")

    def accepted_unsynced(t, s):
        s["screens"]["orders-list.desktop"].update(status="sync_back_pending", deviations=[
            {"id": "DEV-1-001", "phase": 1, "what": "rows are 48px", "why": "touch target", "source": "ui_developer",
             "resolution": "accepted"}])
        save(t, s)
        manifest(t, 1, "ui_developer", web, [{"id": "DEV-1-001", "screen": "orders-list.desktop", "what": "rows 48px", "why": "touch"}])
    gate_case("BLOCK: an accepted deviation not synced back to Stitch", accepted_unsynced, 2, "sync-back")

    def fixed(t, s):
        s["screens"]["orders-list.desktop"]["deviations"] = [
            {"id": "DEV-1-001", "phase": 1, "what": "rows are 48px", "why": "touch target", "source": "ui_developer",
             "resolution": "fixed", "resolved_by": "ui_standards_auditor"}]
        save(t, s)
        manifest(t, 1, "ui_developer", web, [{"id": "DEV-1-001", "screen": "orders-list.desktop", "what": "rows 48px", "why": "touch"}])
    gate_case("PASS: a deviation the auditor sent back as drift and the developer fixed", fixed, 0)

    def deferred(t, s):
        s["screens"]["reports.desktop"] = {"screenKey": "reports.desktop", "screenId": None, "deviceType": "DESKTOP", "app": "web",
                                           "route": "/reports", "status": "no_baseline", "origin": "pending",
                                           "deferred": {"reason": "stitch_unavailable", "at": now(), "detail": "MCP not connected", "run": "autonomous"}}
        save(t, s)
        manifest(t, 1, "ui_developer", web + [{"route": "/reports"}])
    gate_case("PASS with WARNING: autonomous run deferred a screen because Stitch was unreachable", deferred, 0, "WARNING")

    def no_baseline(t, s):
        s["screens"]["reports.desktop"] = {"screenKey": "reports.desktop", "screenId": None, "deviceType": "DESKTOP", "app": "web",
                                           "route": "/reports", "status": "no_baseline", "origin": "pending"}
        save(t, s)
        manifest(t, 1, "ui_developer", web + [{"route": "/reports"}])
    gate_case("BLOCK: no_baseline without a recorded Stitch outage", no_baseline, 2, "not approved/conformant")

    def dqr(t, s):
        s["screens"]["orders-list.desktop"].update(approved_by="design_quality_reviewer", owner_review={"status": "pending", "at": None})
        save(t, s)
        manifest(t, 1, "ui_developer", web)
    def archived_tamper(t, s):
        make_project(t, ("orders-list.desktop", "orders-list.mobile"), versioned=True)
        with open(os.path.join(t, "docs/design/stitch/orders-list.desktop/v0.1/screen.html"), "a") as f:
            f.write("<!-- edited -->")
        manifest(t, 1, "ui_developer", web)
    gate_case("BLOCK: an archived (older version's) render no longer matches its hash", archived_tamper, 2, "archived render html")
    gate_case("PASS: versioned screens with intact archived renders",
              lambda t, s: (make_project(t, ("orders-list.desktop", "orders-list.mobile"), versioned=True), manifest(t, 1, "ui_developer", web)),
              0, "approved")

    gate_case("PASS: an autonomous approval passes and is listed for the owner", dqr, 0, "owner-review list")

    print("── stitch-state.py ready (develop pre-Wave-2 check) ──")
    with tempfile.TemporaryDirectory() as tmp:
        state = make_project(tmp, ("orders-list.desktop", "orders-list.mobile"))
        d = os.path.join(tmp, "docs", "design", "phases", "2")
        os.makedirs(d)
        open(os.path.join(d, "stitch-baseline.md"), "w").write(
            "| Screen | Route | Change |\n|---|---|---|\n| `orders-list.desktop` | /orders | changed |\n| `orders-list.mobile` | /orders | unchanged |\n")
        rc, out = run(["ready", "--phase", "2"], tmp)
        check(rc == 0 and out.count("READY ") == 2, "ready --phase reads stitch-baseline.md; approved current renders are READY", out)
        state["screens"]["orders-list.mobile"]["status"] = "pending_approval"
        save(tmp, state)
        rc, out = run(["ready", "--phase", "2"], tmp)
        check(rc == 2 and "NOT READY  orders-list.mobile" in out, "a pending_approval render blocks UI implementation", out)
        rc, out = run(["ready", "--phase", "3"], tmp)
        check(rc == 2 and "stitch-baseline.md is missing" in out, "a phase never designed in Stitch is NOT READY", out)


# ------------------------------------------------------------------------------------------- versions
def jload(tmp):
    return json.load(open(os.path.join(tmp, "docs", "design", "stitch.json")))


def cases_versions():
    print("── version labels, per-revision renders, versions / diff ──")
    k = "invoices.desktop"
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "docs", "design"))
        save(tmp, {"schema": st.SCHEMA, "projectId": "123", "screens": {}, "queue": [], "log": []})
        imgs = {}
        for n, shade in (("a", 30), ("b", 120), ("c", 200), ("d", 250)):
            imgs[n] = (os.path.join(tmp, n + ".png"), os.path.join(tmp, n + ".html"))
            write_png(imgs[n][0], 8, 8, lambda x, y, sh=shade: (sh, x * 10, y * 10))
            open(imgs[n][1], "w").write(f"<html><body><h1>Invoices {n}</h1></body></html>")
        new = ["--device", "DESKTOP", "--app", "web", "--route", "/invoices"]
        sdir = f"docs/design/stitch/{k}"

        def rev(*a):
            n = len(jload(tmp)["screens"].get(k, {}).get("history", [])) + 1
            return run(["revise", k, "--screen-id", f"s{n}", "--prompt", "p", "--source", "owner"] + list(a), tmp)

        def render(n):
            return run(["render", k, "--screenshot", imgs[n][0], "--html", imgs[n][1]], tmp)

        def sha(rel):
            return st.sha256_file(os.path.join(tmp, rel))

        rc, out = rev("--op", "adopt", *new)
        check(rc == 0 and jload(tmp)["screens"][k]["history"][0].get("version") == "v0.1",
              "revise without --version labels the first revision v0.1", out)
        rc, out = render("a")
        s = jload(tmp)["screens"][k]
        r1 = s["history"][0]["render"]
        check(rc == 0 and r1["dir"] == f"{sdir}/v0.1" and os.path.isfile(os.path.join(tmp, sdir, "v0.1", "screenshot.png"))
              and os.path.isfile(os.path.join(tmp, sdir, "v0.1", "screen.html"))
              and r1["screenshot_sha256"] == st.sha256_file(imgs["a"][0]),
              "render archives the labelled revision under <key>/v0.1/ with its sha256 in the revision", out)
        check(s["render"]["rev"] == 1 and s["render"]["screenshot"] == f"{sdir}/screenshot.png"
              and sha(s["render"]["screenshot"]) == r1["screenshot_sha256"],
              "the top-level render keeps its shape and the top-level files stay as a copy of the latest")
        run(["approve", k, "--by", "owner"], tmp)
        rc, out = rev("--op", "edit")
        check(jload(tmp)["screens"][k]["history"][1].get("version") == "v0.2", "the next revision is auto-labelled v0.2", out)
        rc, out = render("b")
        s = jload(tmp)["screens"][k]
        check(sha(f"{sdir}/v0.1/screenshot.png") == st.sha256_file(imgs["a"][0])
              and sha(f"{sdir}/v0.2/screenshot.png") == st.sha256_file(imgs["b"][0])
              and sha(f"{sdir}/screenshot.png") == st.sha256_file(imgs["b"][0]),
              "two renders archived side by side (v0.1 kept, v0.2 added) with correct hashes; top-level = v0.2")
        check(s["render"]["rev"] == 2 and s["history"][0]["render"]["screenshot_sha256"] == st.sha256_file(imgs["a"][0]),
              "re-rendering did not touch v0.1's recorded hash")
        rc, out = run(["validate", "--check-files"], tmp)
        check(rc == 0, "two archived versions validate with files + hashes", out)

        before = jload(tmp)["screens"][k]["history"]
        for name, args, needle in (("a duplicate label", ["--version", "v0.2"], "already used"),
                                   ("an older label (out of order)", ["--version", "v0.1"], "already used"),
                                   ("an out-of-order label that is new", ["--version", "v0.0"], "must be greater than v0.2"),
                                   ("a malformed label", ["--version", "0.3"], "must look like"),
                                   ("--version with --no-version", ["--version", "v0.3", "--no-version"], "mutually exclusive")):
            rc, out = rev("--op", "edit", *args)
            check(rc != 0 and needle in out and jload(tmp)["screens"][k]["history"] == before,
                  f"revise rejects {name} and writes nothing", out)
        rc, out = rev("--op", "edit", "--version", "v0.5")
        check(rc == 0, "an explicit label above the latest is accepted (v0.5)", out)
        render("c")
        rc, out = rev("--op", "edit", "--no-version")       # rev 4: intermediate, unlabelled
        check(jload(tmp)["screens"][k]["history"][3].get("version") is None, "--no-version leaves an intermediate edit unlabelled", out)
        render("d")
        s = jload(tmp)["screens"][k]
        check(s["history"][3]["render"]["dir"] == f"{sdir}/rev-4" and os.path.isfile(os.path.join(tmp, sdir, "rev-4", "screenshot.png")),
              "an unlabelled revision archives under rev-<N>/")
        rc, out = rev("--op", "edit")                        # rev 5: next minor of the latest LABEL (v0.5)
        check(jload(tmp)["screens"][k]["history"][4].get("version") == "v0.6", "auto label = next minor of the latest labelled revision", out)
        render("b")
        rc, out = run(["versions", k], tmp)
        lines = out.splitlines()
        check(rc == 0 and lines[1].split()[0] == "VERSION" and any(l.startswith("v0.1 ") for l in lines)
              and any(l.startswith("v0.6 ") and "5 (+4)" in l for l in lines) and not any(l.startswith("- ") for l in lines),
              "versions: a table with the unlabelled rev 4 collapsed under the v0.6 it leads to", out)
        check(any(l.startswith("v0.1 ") and "yes (owner)" in l for l in lines) and "RENDER" in out and "APPROVED" in out,
              "versions marks the approved revision and shows the render column", out)
        rc, out = run(["versions", k, "--json"], tmp)
        j = json.loads(out)
        v06 = next(v for v in j["versions"] if v["version"] == "v0.6")
        check(rc == 0 and [v["version"] for v in j["versions"]] == ["v0.1", "v0.2", "v0.5", "v0.6"] and v06["intermediate_revs"] == [4]
              and v06["render"] is True and next(v for v in j["versions"] if v["version"] == "v0.1")["approved"] is True,
              "versions --json lists labelled versions with intermediate_revs, render and approved", out)
        # label: release the final edit of a multi-step change after an unlabelled loop
        rc, out = rev("--op", "edit", "--no-version")
        render("a")
        rc, out = run(["label", k], tmp)
        s = jload(tmp)["screens"][k]
        check(rc == 0 and s["history"][5]["version"] == "v0.7" and s["history"][5]["render"]["dir"].endswith("/v0.7")
              and os.path.isdir(os.path.join(tmp, sdir, "v0.7")) and not os.path.isdir(os.path.join(tmp, sdir, "rev-6")),
              "label releases the final edit of a multi-step change as v0.7 (archive folder renamed rev-6 -> v0.7)", out)
        rc, out = run(["validate", "--check-files"], tmp)
        check(rc == 0, "the state after unlabelled edits + label validates with files + hashes", out)
        rc, out = run(["diff", k, "v0.1", "v0.2"], tmp)
        check(rc == 0 and "s1 -> s2" in out and "1 revision(s) between them" in out and "screenshot" in out and "CHANGED" in out,
              "diff prints screenIds, the revisions/prompts between and which hashes changed", out)
        try:
            import PIL  # noqa: F401
            check("% of pixels differ" in out and not re.search(r"(?<![0-9.])0\.00%", out), "diff reports a pixel-difference percentage (Pillow present)", out)
        except ImportError:
            check("Pillow is not installed" in out, "diff notes Pillow is missing instead of failing", out)
        rc, out = run(["diff", k, "v0.1", "v9.9"], tmp)
        check(rc == 3 and "no version/revision 'v9.9'" in out, "diff on an unknown version is a usage error", out)
        # promotion
        rc, out = run(["approve", k, "--by", "owner", "--promote"], tmp)
        s = jload(tmp)["screens"][k]
        check(rc == 0 and s["history"][-1]["version"] == "v1.0" and s["approved_rev"] == 6
              and os.path.isfile(os.path.join(tmp, sdir, "v1.0", "screenshot.png")),
              "approve --promote labels the approved revision v1.0", out)
        rc, out = run(["validate", "--check-files"], tmp)
        check(rc == 0, "a promoted state validates with files + hashes", out)
        rev("--op", "edit")
        check(jload(tmp)["screens"][k]["history"][-1]["version"] == "v1.1", "after v1.0 the next auto label is v1.1")
        render("c")
        run(["approve", k, "--by", "owner", "--promote"], tmp)
        check(jload(tmp)["screens"][k]["history"][-1]["version"] == "v2.0", "promoting again takes the next major (v1.0 is taken -> v2.0)")

    print("── version rules in validate ──")
    with tempfile.TemporaryDirectory() as tmp:
        good = make_project(tmp, ("orders-list.desktop",), versioned=True)
        o = "orders-list.desktop"
        errs = st.validate(good, tmp, check_files=True)
        check(not errs, "the versioned fixture (v0.1 + v0.2, archived renders) validates with files + hashes", "; ".join(errs))

        def bad(name, mutate, needle, files=False):
            x = copy.deepcopy(good)
            mutate(x)
            errs = st.validate(x, tmp, check_files=files)
            check(any(needle in e for e in errs), f"rejects: {name}", f"wanted '{needle}', got {errs[:3]}")
        h = lambda x: x["screens"][o]["history"]  # noqa: E731
        bad("a duplicate version label", lambda x: (h(x)[1].update(version="v0.1"),
            h(x)[1]["render"].update(dir=f"docs/design/stitch/{o}/v0.1")), "already used")
        bad("labels out of order", lambda x: (h(x)[0].update(version="v0.3"), h(x)[1].update(version="v0.2")),
            "not greater than the previous label")
        bad("a malformed label", lambda x: h(x)[0].update(version="0.1"), "must look like v<major>.<minor>")
        bad("an archived render dir that doesn't match the label",
            lambda x: h(x)[0]["render"].update(dir=f"docs/design/stitch/{o}/v0.9"), "render.dir must be")
        bad("an archived screenshot hash that doesn't match the file (tamper)",
            lambda x: h(x)[0]["render"].update(screenshot_sha256="0" * 64), "archived render screenshot", files=True)
        bad("a labelled earlier revision with no archived render",
            lambda x: h(x)[0].pop("render"), "has no archived render", files=True)
        bad("a top-level render that differs from the latest archived render",
            lambda x: x["screens"][o]["render"].update(html_sha256="1" * 64), "differs from revision 2's archived render")
        os.remove(os.path.join(tmp, f"docs/design/stitch/{o}/v0.1/screen.html"))
        errs = st.validate(good, tmp, check_files=True)
        check(any("archived render html file is missing" in e for e in errs), "rejects: an archived render file that was deleted", "; ".join(errs[:2]))
        try:
            import jsonschema
            v = jsonschema.Draft202012Validator(json.load(open(SCHEMA_FILE)))
            check(not list(v.iter_errors(good)), "the JSON Schema accepts the versioned fixture")
            b = copy.deepcopy(good)
            b["screens"][o]["history"][0]["version"] = "0.1"
            check(bool(list(v.iter_errors(b))), "the JSON Schema rejects a malformed version label")
        except ImportError:
            pass

    print("── back-compat: a stitch.json written by the previous tool version ──")
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copytree(os.path.join(FIX, "legacy"), tmp, dirs_exist_ok=True)
        rc, out = run(["validate", "--check-files"], tmp)
        check(rc == 0, "an old-format file (no labels, one render per screen) still validates with files + hashes", out)
        manifest(tmp, 1, "ui_developer", [{"route": "/orders"}])
        rc, out = run(["gate", "--phase", "1"], tmp)
        check(rc == 0 and "approved" in out, "an old-format file still passes the gate unchanged", out)
        rc, out = run(["versions", "orders-list.desktop"], tmp)
        check(rc == 0 and "yes (owner)" in out, "versions works on an old-format screen (unlabelled revisions, the stored render shown)", out)
        shot, html = os.path.join(tmp, "n.png"), os.path.join(tmp, "n.html")
        write_png(shot, 8, 8, lambda x, y: (1, 2, 3))
        open(html, "w").write("<html><body>n</body></html>")
        run(["revise", "orders-list.desktop", "--op", "edit", "--screen-id", "999", "--prompt", "add filter", "--source", "owner"], tmp)
        run(["render", "orders-list.desktop", "--screenshot", shot, "--html", html], tmp)
        rc, out = run(["validate", "--check-files"], tmp)
        s = json.load(open(os.path.join(tmp, "docs/design/stitch.json")))["screens"]["orders-list.desktop"]
        check(rc == 0 and s["history"][2]["version"] == "v0.1" and s["render"]["rev"] == 3
              and os.path.isfile(os.path.join(tmp, "docs/design/stitch/orders-list.desktop/v0.1/screen.html")),
              "an old-format screen upgrades in place: its next revision is v0.1 and archives beside the old top-level files", out)
        rc, out = run(["gate", "--phase", "1"], tmp)
        check(rc == 2 and "pending_approval" in out, "…and the gate then waits for approval as before", out)


# ------------------------------------------------------------------------------------------- fidelity
def cases_fidelity():
    print("── stitch-fidelity.py on known images ──")
    with tempfile.TemporaryDirectory() as tmp:
        p = lambda n: os.path.join(tmp, n)  # noqa: E731
        grad = lambda x, y: ((x * 7) % 256, (y * 5) % 256, (x * y) % 256)  # noqa: E731
        write_png(p("g.png"), 23, 17, grad, filters=(0, 1, 2, 3, 4))
        w, h, rows = fid.load_rgb(p("g.png"), force_pure=True)
        exact = all(rows[y][x] == grad(x, y) for y in range(h) for x in range(w))
        check(w == 23 and h == 17 and exact, "pure-Python decoder reproduces every pixel across filter types 0-4")
        try:
            import PIL  # noqa: F401
            w2, h2, rows2 = fid.load_rgb(p("g.png"))
            check(rows2 == rows, "Pillow path and pure path decode identically")
        except ImportError:
            print("  · Pillow not installed — pure-Python decoder only")
        write_png(p("table.png"), 640, 700, page("table"))
        write_png(p("table_shift.png"), 640, 712, page("table", dy=12, tint=6))
        write_png(p("cards.png"), 640, 700, page("cards"))
        same = fid.visual_score(p("table.png"), p("table.png"), force_pure=True)
        check(same["visual"] == 1.0, "identical images score visual 1.0", str(same))
        near = fid.visual_score(p("table.png"), p("table_shift.png"), force_pure=True)
        far = fid.visual_score(p("table.png"), p("cards.png"), force_pure=True)
        check(near["visual"] >= 0.8, "same layout shifted 12px and re-tinted still scores >= 0.8 (shift search)", str(near))
        check(far["visual"] <= near["visual"] - 0.2, "a different layout (cards vs table) scores far lower", f"near={near} far={far}")
        half = fid.visual_score(p("table.png"), p("g.png"), force_pure=True)
        check(half["height_ratio"] < 1 and half["visual"] < 0.6, "a page of very different proportions is penalised", str(half))

    print("── structural score on a committed capture (tests/fixtures/stitch) ──")
    cap = json.load(open(os.path.join(FIX, "orders.capture.json")))
    rec = open(os.path.join(FIX, "site", "orders-recreated", "index.html")).read()
    other = open(os.path.join(FIX, "site", "index.html")).read()
    s1 = fid.structural_score(cap, rec)
    check(s1["structural"] == 1.0 and not s1["missing"], "a recreation with every region, heading, button and column scores 1.0", str(s1))
    s2 = fid.structural_score(cap, other)
    check(s2["structural"] < 0.75 and "button: Export CSV" in s2["missing"] and "column: Customer" in s2["missing"],
          "another page misses the toolbar button and table columns, and names them for the edit_screens prompt", str(s2))
    trimmed = rec.replace("<th>Status</th>", "<th>State</th>")
    s3 = fid.structural_score(cap, trimmed)
    check(s3["missing"] == ["column: Status"], "a renamed column is reported by its real label", str(s3))
    r = subprocess.run([sys.executable, FID, "score", "--real", os.path.join(FIX, "..", "..", "..", ".claude", "hooks", "nope.png"),
                        "--stitch", "x.png"], capture_output=True, text=True)
    check(r.returncode == 3, "a missing screenshot is a usage error (exit 3), never a score")


if __name__ == "__main__":
    cases_validate()
    cases_writers()
    cases_gate()
    cases_versions()
    cases_fidelity()
    print(f"stitch_cases.py: {PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
