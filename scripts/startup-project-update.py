#!/usr/bin/env python3
"""startup-project-update.py — bring a project's framework files up to date (run via startup-project-update.sh,
which runs graph-preflight.sh first). Python 3.9+ standard library only.

  update [--project DIR] [--source DIR] [--settings FILE] [--dry-run] [--force] [--hooks-only | --ledger-only]
         [--graph-interactive on|off] [--no-build] [--quiet]
  manifest --hooks-dir DIR [--repo DIR] --out FILE        (install.sh: the staged manifest)

What `update` touches in the project (and nothing else; it runs no git command that changes the worktree):
  .claude/hooks/<framework file>        refreshed from the source when stale; never deleted; project-added files
                                        are never looked at. A file whose content is not a version the framework
                                        shipped (and not the hash recorded at the last update) is LOCALLY MODIFIED:
                                        it is kept and its diff printed, unless --force.
  .claude/hooks/.framework-manifest.json  framework version/commit + sha256 of each framework file as installed
  .claude/settings.json                 merged: framework hook commands and env keys that are missing are added;
                                        user entries are never removed or changed
  .gitignore                            `agent_state/graph/` appended when not already ignored
  agent_state/config/graph-policy.json  only with --graph-interactive (absent = interactive find/status OFF)
  agent_state/graph/                    the initial `sdlc-graph.py build` (skipped by --dry-run/--no-build/--hooks-only)

--ledger-only installs the phase ledger and NOTHING else (docs/PHASE_LEDGER.md): .claude/hooks/ledger.py, its
entry in the hooks manifest, only the ledger's hook entries in .claude/settings.json (created with just those when
absent — the framework's other hooks such as the Stop gate check are NOT enabled), and `agent_state/ledger/` in
.gitignore. No graph build, no env keys, no other hook file. Same guarantees: merge-only, idempotent, --dry-run,
a locally modified ledger.py is kept unless --force.

Exit: 0 up to date, 1 a locally modified hook was kept (re-run with --force to replace it), 2 usage / unreadable
input (e.g. settings.json is not valid JSON), 4 the graph build failed (files were still updated).
"""
import argparse, datetime, difflib, hashlib, json, os, shutil, subprocess, sys, time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = ".framework-manifest.json"
HOOK_EXT = (".sh", ".py", ".mjs")
GRAPH_IGNORE = "agent_state/graph/"
LEDGER_IGNORE = "agent_state/ledger/"
LEDGER_HOOK = "ledger.py"


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(p):
    with open(p, "rb") as f:
        return sha256_bytes(f.read())


def framework_files(hooks_dir):
    return sorted(f for f in os.listdir(hooks_dir)
                  if f.endswith(HOOK_EXT) and not f.startswith(".") and os.path.isfile(os.path.join(hooks_dir, f)))


def git(repo, *args, binary=False):
    """Read-only git query; None when repo is not a git checkout or git is missing."""
    try:
        r = subprocess.run(["git", "-C", repo, *args], capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    return r.stdout if binary else r.stdout.decode("utf-8", "replace").strip()


def build_manifest(hooks_dir, repo=None):
    """{version, commit, files: {name: sha256}, known: {name: [every sha256 the framework ever shipped]}}.
    `known` comes from the repo's git history of .claude/hooks (read-only), so a project whose hooks were copied
    by an older install (no project manifest yet) can tell a stale copy from a locally edited one."""
    files = {f: sha256_file(os.path.join(hooks_dir, f)) for f in framework_files(hooks_dir)}
    known = {f: {s} for f, s in files.items()}
    commit = version = None
    if repo:
        commit = git(repo, "rev-parse", "HEAD")
        version = git(repo, "describe", "--tags", "--always", "--dirty")
        rel = os.path.relpath(os.path.abspath(hooks_dir), os.path.abspath(repo))
        raw = git(repo, "log", "--raw", "--no-abbrev", "--no-renames", "--format=", "--", rel) if commit else None
        blobs = {}
        for line in (raw or "").splitlines():
            parts = line.split("\t")
            if len(parts) != 2 or not parts[0].startswith(":"):
                continue
            meta, path = parts[0].split(), parts[1]
            name = os.path.basename(path)
            if name in files and meta[3] != "0" * 40:          # meta[3] = blob after the change
                blobs.setdefault(meta[3], set()).add(name)
        if blobs:
            p = subprocess.run(["git", "-C", repo, "cat-file", "--batch"], input="\n".join(blobs).encode() + b"\n",
                               capture_output=True, timeout=120)
            out, i = p.stdout, 0
            while i < len(out):
                nl = out.index(b"\n", i)
                head = out[i:nl].split()
                if len(head) < 3:                           # "<sha> missing"
                    i = nl + 1
                    continue
                size = int(head[2])
                content = out[nl + 1: nl + 1 + size]
                for name in blobs.get(head[0].decode(), ()):
                    known[name].add(sha256_bytes(content))
                i = nl + 1 + size + 1
    return {"schema": 1, "version": version, "commit": commit,
            "generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "files": files, "known": {f: sorted(s) for f, s in known.items()}}


def load_json(path):
    with open(path) as f:
        return json.load(f)


def write_atomic(path, data, mode=None):
    tmp = path + ".tmp-update"
    with open(tmp, "wb") as f:
        f.write(data if isinstance(data, bytes) else data.encode())
    if mode is not None:
        os.chmod(tmp, mode)
    os.replace(tmp, path)


# ─── settings.json merge ───────────────────────────────────────────────────────────────────────────
def _script_of(cmd):
    """The hook script a command runs (basename), so `"$CLAUDE_PROJECT_DIR"/.claude/hooks/x.sh` and a user's
    `.claude/hooks/x.sh` count as the same hook."""
    for tok in cmd.replace('"', " ").replace("'", " ").split():
        if "/.claude/hooks/" in tok or tok.startswith(".claude/hooks/"):
            return os.path.basename(tok)
    return cmd.strip()


def merge_settings(project, framework):
    """Return (merged, changes). Adds missing env keys and missing hook commands; never removes or edits."""
    merged = json.loads(json.dumps(project))
    changes = []
    for k, v in (framework.get("env") or {}).items():
        env = merged.setdefault("env", {})
        if k not in env:
            env[k] = v
            changes.append(f"env.{k} = {json.dumps(v)}")
    for event, groups in (framework.get("hooks") or {}).items():
        mhooks = merged.setdefault("hooks", {})
        mgroups = mhooks.setdefault(event, [])
        present = {_script_of(h.get("command", "")) for g in mgroups for h in (g.get("hooks") or [])
                   if isinstance(h, dict)}
        for g in groups:
            missing = [h for h in g.get("hooks", []) if _script_of(h.get("command", "")) not in present]
            if not missing:
                continue
            target = next((mg for mg in mgroups if mg.get("matcher") == g.get("matcher")), None)
            if target is None:
                target = {k: v for k, v in g.items() if k != "hooks"}
                target["hooks"] = []
                mgroups.append(target)
            for h in missing:
                target.setdefault("hooks", []).append(h)
                present.add(_script_of(h.get("command", "")))
                where = f" (matcher {g['matcher']})" if g.get("matcher") else ""
                changes.append(f"hooks.{event}{where}: + {_script_of(h.get('command', ''))}")
    return merged, changes


# ─── .gitignore ────────────────────────────────────────────────────────────────────────────────────
def dir_ignored(project, rel, probes):
    path = os.path.join(project, ".gitignore")
    lines = open(path).read().splitlines() if os.path.exists(path) else []
    if any(l.strip().rstrip("/").lstrip("/") in (rel.rstrip("/"), "agent_state") for l in lines):
        return True
    # some other rule (a global excludes file, a broader pattern) already ignores what the dir holds?
    out = git(project, "check-ignore", "--no-index", *probes)
    return out is not None and len(out.splitlines()) == len(probes)


def graph_ignored(project):
    return dir_ignored(project, GRAPH_IGNORE, ["agent_state/graph/graph.sqlite", "agent_state/graph/tc-gate-phase-1.json"])


def ledger_ignored(project):
    return dir_ignored(project, LEDGER_IGNORE, ["agent_state/ledger/events-2026-01-01.jsonl", "agent_state/ledger/.lock"])


def ensure_ignored(project, rel, comment, dry, say, touched):
    if (graph_ignored if rel == GRAPH_IGNORE else ledger_ignored)(project):
        say(f"  .gitignore: {rel} already ignored")
        return
    say(f"  .gitignore: + {rel}")
    touched.append(".gitignore")
    if not dry:
        gi = os.path.join(project, ".gitignore")
        cur = open(gi).read() if os.path.exists(gi) else ""
        sep = "" if not cur or cur.endswith("\n") else "\n"
        write_atomic(gi, cur + sep + comment + "\n" + rel + "\n")


def only_ledger(framework):
    """The framework settings reduced to the hook entries that run ledger.py (no env, no other hooks)."""
    hooks = {}
    for event, groups in (framework.get("hooks") or {}).items():
        for g in groups:
            hs = [h for h in g.get("hooks", []) if isinstance(h, dict) and _script_of(h.get("command", "")) == LEDGER_HOOK]
            if hs:
                ng = {k: v for k, v in g.items() if k != "hooks"}
                ng["hooks"] = hs
                hooks.setdefault(event, []).append(ng)
    return {"hooks": hooks}


def main_update(a):
    project = os.path.abspath(a.project)
    if not os.path.isdir(project):
        print(f"startup-project-update: no such project directory: {project}", file=sys.stderr)
        return 2
    repo_hooks = os.path.join(os.path.dirname(HERE), ".claude", "hooks")
    if a.source:
        src = os.path.abspath(a.source)
    elif os.path.isfile(os.path.join(repo_hooks, "sdlc-graph.py")):      # run from the framework repo's scripts/
        src = repo_hooks
    else:
        src = os.path.join(os.path.expanduser("~"), ".claude", "hooks", "startup")
    if not os.path.isfile(os.path.join(src, "sdlc-graph.py")):
        print(f"⛔ BLOCKED: no framework hooks staged in {src} (run ./install.sh from the framework repo)", file=sys.stderr)
        return 2
    dst = os.path.join(project, ".claude", "hooks")
    if os.path.realpath(src) == os.path.realpath(dst):
        print("startup-project-update: the project IS the framework source — nothing to update", file=sys.stderr)
        return 0
    settings_src = a.settings or next((p for p in (os.path.join(src, "project-settings.json"),
                                                   os.path.join(os.path.dirname(src), "settings.json"))
                                       if os.path.isfile(p)), None)
    # the source manifest: staged by install.sh, else computed now (from the repo's git history when src is a checkout)
    smf = os.path.join(src, MANIFEST)
    if os.path.isfile(smf):
        source_manifest = load_json(smf)
    else:
        top = git(src, "rev-parse", "--show-toplevel")
        source_manifest = build_manifest(src, top)
    pmf = os.path.join(dst, MANIFEST)
    try:
        project_manifest = load_json(pmf) if os.path.isfile(pmf) else {}
    except ValueError:
        project_manifest = {}
    recorded = project_manifest.get("files", {})
    dry = a.dry_run
    say = (lambda *x: None) if a.quiet else print
    tag = "[dry-run] " if dry else ""
    say(f"{tag}startup-project-update: {project}")
    fv = source_manifest.get("version") or (source_manifest.get("commit") or "")[:12] or "unversioned"
    say(f"  framework hooks from {src} ({fv})")

    touched, rc = [], 0
    actions = {"added": [], "updated": [], "current": [], "modified-kept": [], "forced": []}
    new_record = dict(recorded)
    files = framework_files(src)
    if a.ledger_only:
        if LEDGER_HOOK not in files:
            print(f"⛔ BLOCKED: {LEDGER_HOOK} is not in {src} (re-run ./install.sh from a framework checkout that has it)",
                  file=sys.stderr)
            return 2
        files = [LEDGER_HOOK]
    if not dry:
        os.makedirs(dst, exist_ok=True)
    for name in files:
        sp, dp = os.path.join(src, name), os.path.join(dst, name)
        s_sha = sha256_file(sp)
        if not os.path.exists(dp):
            act = "added"
        else:
            p_sha = sha256_file(dp)
            if p_sha == s_sha:
                act = "current"
            elif p_sha == recorded.get(name) or p_sha in set(source_manifest.get("known", {}).get(name, [])):
                act = "updated"
            else:
                act = "forced" if a.force else "modified-kept"
        actions[act].append(name)
        if act == "modified-kept":
            rc = 1
            if True:                     # shown even with --quiet: the user must see why a file was kept
                old = open(dp, errors="replace").read().splitlines(keepends=True)
                new = open(sp, errors="replace").read().splitlines(keepends=True)
                diff = list(difflib.unified_diff(old, new, f"project/.claude/hooks/{name}", f"framework/{name}"))
                print(f"  ⚠ {name}: locally modified (not a version the framework shipped) — KEPT; diff to the framework "
                      f"version ({len(diff)} lines):")
                for line in diff[:60]:
                    print("    " + line.rstrip("\n"))
                if len(diff) > 60:
                    print(f"    … {len(diff) - 60} more lines")
            continue
        new_record[name] = s_sha
        if act in ("added", "updated", "forced"):
            touched.append(os.path.join(".claude", "hooks", name))
            if not dry:
                with open(sp, "rb") as f:
                    write_atomic(dp, f.read(), os.stat(sp).st_mode & 0o777)
        elif not dry and not os.access(dp, os.X_OK) and os.access(sp, os.X_OK):
            os.chmod(dp, os.stat(sp).st_mode & 0o777)
    for act, label in (("added", "added"), ("updated", "refreshed (stale)"), ("forced", "OVERWRITTEN (--force, was locally modified)")):
        if actions[act]:
            say(f"  hooks {label}: {', '.join(actions[act])}")
    say(f"  hooks current: {len(actions['current'])}/{len(files)}"
        + (f"; locally modified, kept: {', '.join(actions['modified-kept'])} (re-run with --force to replace)"
           if actions["modified-kept"] else ""))
    manifest_doc = {"schema": 1, "framework_version": source_manifest.get("version"),
                    "framework_commit": source_manifest.get("commit"), "source": src,
                    "updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "files": {k: new_record[k] for k in sorted(new_record)}}
    old_doc = {k: v for k, v in project_manifest.items() if k not in ("updated", "source")}
    if {k: v for k, v in manifest_doc.items() if k not in ("updated", "source")} != old_doc:
        touched.append(os.path.join(".claude", "hooks", MANIFEST))
        if not dry:
            write_atomic(pmf, json.dumps(manifest_doc, indent=2) + "\n")

    build_rc = 0
    if not a.hooks_only:
        # settings.json
        sp_ = os.path.join(project, ".claude", "settings.json")
        if settings_src:
            fw = load_json(settings_src)
            if a.ledger_only:
                fw = only_ledger(fw)
                if not fw["hooks"]:
                    print(f"  ⛔ the framework settings ({settings_src}) have no {LEDGER_HOOK} hook entries — "
                          "settings left untouched", file=sys.stderr)
                    return 2
            if not os.path.exists(sp_):
                say("  settings.json: created with " + ("the phase-ledger hooks only" if a.ledger_only
                                                         else "the framework settings"))
                touched.append(".claude/settings.json")
                if not dry:
                    os.makedirs(os.path.dirname(sp_), exist_ok=True)
                    write_atomic(sp_, (json.dumps(fw, indent=2) + "\n") if a.ledger_only else open(settings_src).read())
            else:
                try:
                    cur = load_json(sp_)
                    if not isinstance(cur, dict):
                        raise ValueError("top level is not an object")
                except ValueError as e:
                    print(f"  ⛔ .claude/settings.json is not valid JSON ({e}) — left untouched; fix it and re-run",
                          file=sys.stderr)
                    return 2
                merged, changes = merge_settings(cur, fw)
                if changes:
                    say("  settings.json: added " + "; ".join(changes))
                    touched.append(".claude/settings.json")
                    if not dry:
                        write_atomic(sp_, json.dumps(merged, indent=2, ensure_ascii=False) + "\n")
                else:
                    say("  settings.json: already has every framework hook")
        else:
            say("  settings.json: no framework settings found next to the hooks — skipped")
        # .gitignore
        ensure_ignored(project, LEDGER_IGNORE, "# phase ledger: hook-written observation log (docs/PHASE_LEDGER.md; "
                       "remove this line to commit it at phase end)", dry, say, touched)
        if a.ledger_only:
            say(f"{tag}files {'that would change' if dry else 'written'}: " + (", ".join(dict.fromkeys(touched)) if touched else "none"))
            say("  phase ledger enabled — report: python3 .claude/hooks/ledger.py report --phase N; "
                "off: SDLC_LEDGER=0 or agent_state/config/ledger-policy.json {\"enabled\": false}")
            return rc
        ensure_ignored(project, GRAPH_IGNORE, "# sdlc-graph store + gate outputs (rebuildable: python3 .claude/hooks/sdlc-graph.py build)",
                       dry, say, touched)
        graph = os.path.join(dst, "sdlc-graph.py")
        if a.graph_interactive:
            touched.append("agent_state/config/graph-policy.json")
            say(f"  interactive find/status: {a.graph_interactive}")
            if not dry:
                subprocess.run([sys.executable, graph, "--root", project, "interactive", a.graph_interactive],
                               cwd=project, check=False, stdout=subprocess.DEVNULL)
        if dry or a.no_build:
            say(f"  graph: {'would build' if dry else 'build skipped (--no-build)'} "
                f"(python3 .claude/hooks/sdlc-graph.py build)")
        elif not os.path.isfile(graph):
            say("  graph: sdlc-graph.py not installed (kept a locally modified copy?) — build skipped")
        else:
            t0 = time.time()
            b = subprocess.run([sys.executable, graph, "--root", project, "build"], cwd=project,
                               capture_output=True, text=True)
            dt = time.time() - t0
            if b.returncode != 0:
                print(f"  ⚠ graph build FAILED in {dt:.1f}s (exit {b.returncode}): "
                      f"{(b.stderr or b.stdout).strip().splitlines()[-1:] or ''}", file=sys.stderr)
                print("    agents will report GRAPH UNAVAILABLE and use the pre-graph procedure; "
                      "see docs/SDLC_GRAPH.md § Troubleshooting", file=sys.stderr)
                build_rc = 4
            else:
                touched.append("agent_state/graph/ (graph.sqlite, graph.jsonl, .gitignore)")
                st = subprocess.run([sys.executable, graph, "--root", project, "--no-refresh", "--json", "stats"],
                                    cwd=project, capture_output=True, text=True)
                try:
                    s = json.loads(st.stdout)
                    n, e = sum(s["nodes"].values()), sum(s["edges"].values())
                    top = ", ".join(f"{k} {v}" for k, v in sorted(s["nodes"].items(), key=lambda x: -x[1])[:5])
                    say(f"  graph: built in {dt:.1f}s — {n} nodes, {e} edges, {sum(s['files'].values())} files"
                        + (f" ({top})" if top else "") + f"; {os.path.relpath(s['graph'], project)}")
                except (ValueError, KeyError, TypeError):
                    say(f"  graph: built in {dt:.1f}s (stats unreadable: {st.stderr.strip()[:200]})")
    say(f"{tag}files {'that would change' if dry else 'written'}: " + (", ".join(dict.fromkeys(touched)) if touched else "none"))
    return rc or build_rc


def main(argv=None):
    ap = argparse.ArgumentParser(prog="startup-project-update", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    u = sub.add_parser("update")
    u.add_argument("--project", default=os.getcwd())
    u.add_argument("--source", help="framework hooks dir (default: this repo's .claude/hooks when run from a checkout, "
                                    "else ~/.claude/hooks/startup)")
    u.add_argument("--settings", help="framework settings.json to merge from (default: beside the source)")
    u.add_argument("--dry-run", action="store_true")
    u.add_argument("--force", action="store_true", help="overwrite locally modified framework hooks")
    u.add_argument("--hooks-only", action="store_true", help="refresh hooks + manifest only (no settings/.gitignore/build)")
    u.add_argument("--ledger-only", action="store_true",
                   help="install ONLY the phase ledger: ledger.py + its settings hook entries + .gitignore line")
    u.add_argument("--graph-interactive", choices=("on", "off"))
    u.add_argument("--no-build", action="store_true")
    u.add_argument("--quiet", action="store_true")
    m = sub.add_parser("manifest")
    m.add_argument("--hooks-dir", required=True)
    m.add_argument("--repo")
    m.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "manifest":
        doc = build_manifest(a.hooks_dir, a.repo)
        write_atomic(a.out, json.dumps(doc, indent=2) + "\n")
        print(f"manifest: {len(doc['files'])} framework hooks, "
              f"{sum(len(v) for v in doc['known'].values())} known versions ({doc.get('version') or 'no git'})")
        return 0
    if a.cmd != "update":
        ap.print_help()
        return 2
    if a.ledger_only and (a.hooks_only or a.graph_interactive):
        print("startup-project-update: --ledger-only cannot be combined with --hooks-only or --graph-interactive",
              file=sys.stderr)
        return 2
    return main_update(a)


if __name__ == "__main__":
    sys.exit(main())
