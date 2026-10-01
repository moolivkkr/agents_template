#!/usr/bin/env python3
"""Check every non-application code block in .claude/skills (outside the two archetype folders).

Families: sql (PostgreSQL / MySQL / SQLite), sh (bash), yaml, json, dockerfile, hcl, ngql. The blocks
are extracted from the markdown at run time (blocks.py), so an edit to a sample is re-verified.

1. Inventory. units.py pins, per file, how many blocks of each family exist (EXPECTED) and, per block,
   its first non-empty line (the anchor) and what checks it. A block nobody checks or skips with a
   reason, a count that changed, or an anchor that moved fails the run: the config has to be looked
   at again rather than silently checking the wrong code.
2. Checks. Default run (offline, local CLI tools only):
     sh          bash -n under every bash found (macOS /bin/bash 3.2 and the PATH bash), shellcheck
                 -S info, and the exec scenarios units.py defines (the block runs in a fixture dir)
     sql/pg      parsed with libpg_query 17 (pglast), i.e. the PostgreSQL 17 grammar
     sql/sqlite  executed statement by statement on SQLite (Python's sqlite3) with the fixture schema
     yaml        strict parse (duplicate keys fail), then per block: actionlint, docker compose config,
                 Maestro flow structure, OpenAPI 3.1 validation, golangci-lint v2 config shape
     json        strict parse (templates: the declared substitutions only), then the schema it claims
     dockerfile  hadolint
     hcl         fmt -check (terraform, else OpenTofu)
   --live adds what needs Docker or the network:
     sql/pg      every block executed on postgres:17 (+ the EXPLAIN plan-shape claims in CLAIMS)
     sql/mysql   executed on mysql:8.4
     sh          the exec scenarios again on Linux (bash 5 + GNU coreutils/grep/sed, in postgres:17)
     yaml        kubeconform -strict against the Kubernetes JSON schemas; golangci-lint config verify
     dockerfile  docker build with a minimal context
     hcl         init -backend=false + validate
     ngql        executed on NebulaGraph 3.8 (metad + storaged + graphd sharing one network namespace)
   Blocks whose only meaningful check is live are reported "live-only" in the default run.
3. .claude/commands and .claude/agents: every ```bash block gets bash -n + shellcheck -S error (with
   <placeholders> and {{fields}} turned into words) and the portability lint (grep -P, BSD-first stat),
   which the inventory also runs over every skill bash block and .claude/hooks/*.sh. units.SNIPPETS runs
   the lines those fixes changed, macOS always and Linux with --live. No skill fence may lack a language tag.
4. Every finding is printed as .claude/<path>.md:<line>: <check>: <message>.

Usage: run.sh [--live] [--only SUBSTR ...] [--family F ...] [--keep] [--inventory-only] [--list]
Exit 0 = everything passed; 1 = a check failed; 2 = a required tool is missing.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SKILLS = Path(os.environ.get("CONFIG_PACKS_SKILLS_DIR") or REPO / ".claude" / "skills")
sys.path.insert(0, str(HERE))
import blocks as B  # noqa: E402
import units as U  # noqa: E402

FAMILIES = ("sql", "sh", "yaml", "json", "dockerfile", "hcl", "ngql")
CLAUDE = Path(os.environ.get("CONFIG_PACKS_CLAUDE_DIR") or REPO / ".claude")
EXTRA_SH_TREES = ("commands", "agents")   # their ```bash blocks: one uniform check, skips listed in units.CMD_SKIPS
# Fail-open bug classes found on 2026-09-30, linted in every bash block and every .claude/hooks/*.sh
PORTABILITY = [
    (re.compile(r"\bgrep\s+(-[A-Za-z]*P[A-Za-z]*|--perl-regexp)\b"),
     "grep -P: BSD/macOS grep rejects it (exit 2), so the pipeline yields nothing; use -E or sed -n -E"),
    (re.compile(r"stat\s+-f\s+%m[^|\n]*\|\|\s*stat\s+-c"),
     "BSD-first stat: on Linux `stat -f %m` prints file-system info to stdout before the GNU fallback runs"),
]
PLACEHOLDER = re.compile(r"(?<![<\w])<(?![<(])[A-Za-z{][^<>\n]*>")   # <the command you ran>, not <<EOF or <(cmd)
MUSTACHE = re.compile(r"\{\{[A-Za-z_][A-Za-z0-9_.]*\}\}")
DOCKER = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"


class Finding(Exception):
    pass


# ───────────────────────────────────────────────────────────── utilities ──
def run(cmd, *, cwd=None, env=None, input=None, timeout=600):
    e = dict(os.environ)
    if env:
        e.update(env)
    return subprocess.run(cmd, cwd=cwd, env=e, input=input, capture_output=True, text=True, timeout=timeout)


def apply_subst(text: str, subst) -> str:
    """Declared substitutions only: (old, new) literal, or ("re", pattern, repl). Line count must not change."""
    for s in subst or ():
        before = text.count("\n")
        if len(s) == 3 and s[0] == "re":
            text, n = re.subn(s[1], s[2], text, flags=re.M)
        else:
            n = text.count(s[0])
            text = text.replace(s[0], s[1])
        if n == 0:
            raise Finding(f"harness: substitution {s!r} matched nothing (the block changed?)")
        if text.count("\n") != before:
            raise Finding(f"harness: substitution {s!r} changed the line count")
    return text


def wrap(text: str, spec) -> tuple[str, int]:
    """Embed a fragment in a harness wrapper ("...{}..."), indenting it by spec['indent']. Returns
    (full text, number of wrapper lines before the block) so findings map back to the block."""
    w = spec.get("wrap")
    if not w:
        return text, 0
    ind = " " * spec.get("indent", 0)
    body = "\n".join((ind + ln) if ln.strip() else ln for ln in text.rstrip("\n").split("\n"))
    pre, post = w.split("{}", 1)
    return pre + body + post, pre.count("\n")


class Ctx:
    def __init__(self, args, tmp: Path):
        self.args = args
        self.live = args.live
        self.tmp = tmp
        self.pg = None
        self.mysql = None
        self.nebula = None
        self.linux = None
        self.tf = None
        self.started: list[str] = []
        self.bashes = []
        seen = set()
        for cand in ("/bin/bash", shutil.which("bash")):
            if cand and os.path.exists(cand):
                v = run([cand, "-c", 'echo "$BASH_VERSION"']).stdout.strip()
                if v not in seen:
                    seen.add(v)
                    self.bashes.append((cand, v))

    def path(self, b, ext):
        p = self.tmp / (re.sub(r"[^A-Za-z0-9]+", "_", b.key) + ext)
        return p

    # containers --------------------------------------------------------------------------------------
    def docker(self, *a, **kw):
        return run([DOCKER, *a], **kw)

    def start(self, name, *args):
        self.docker("rm", "-f", name)
        r = self.docker("run", "-d", "--rm", "--name", name, *args)
        if r.returncode:
            raise SystemExit(f"harness: cannot start {name}: {r.stderr.strip()}")
        self.started.append(name)

    def port(self, name, p):
        out = self.docker("port", name, str(p)).stdout.strip().splitlines()
        return int(out[0].rsplit(":", 1)[1])

    def block_text(self, key):
        b = self.blocks_by_key[key]
        return apply_subst(b.text, U.BLOCKS[key].get("subst"))

    def linux_container(self):
        """bash 5 + GNU coreutils/grep/sed, mawk and python3: the official python:3.12-slim image (Debian), idle."""
        if self.linux is None:
            self.start("cfgpk-linux", "--entrypoint", "sleep", "python:3.12-slim", "7200")
            self.linux = "cfgpk-linux"
        return self.linux

    def stop_all(self):
        for name in reversed(self.started):
            self.docker("rm", "-f", "-v", name)


# ─────────────────────────────────────────────────────────────── checkers ──
def check_sh(b, spec, ctx, out):
    text = apply_subst(b.text, spec.get("subst"))
    f = ctx.path(b, ".sh")
    f.write_text(text)
    errs = []
    for bash, ver in ctx.bashes:
        r = run([bash, "-n", str(f)])
        for line in r.stderr.splitlines():
            m = re.search(r"line (\d+): (.*)", line)
            errs.append((b.md_line(int(m.group(1))) if m else b.first_line, f"bash {ver} -n: {m.group(2) if m else line}"))
    out["steps"].append("bash -n (" + ", ".join(v for _, v in ctx.bashes) + ")")
    excl = spec.get("sc_exclude", {})
    for code, why in excl.items():
        if not why:
            errs.append((b.first_line, f"harness: shellcheck exclusion {code} has no reason"))
    cmd = ["shellcheck", "-s", spec.get("shell", "bash"), "-S", "info", "-f", "json1"]
    if excl:
        cmd += ["-e", ",".join(excl)]
    r = run(cmd + [str(f)])
    try:
        comments = json.loads(r.stdout or "{}").get("comments", [])
    except json.JSONDecodeError:
        comments = [{"line": 1, "code": "?", "level": "error", "message": r.stderr.strip() or r.stdout.strip()}]
    for c in comments:
        errs.append((b.md_line(c["line"]), f"shellcheck SC{c['code']} ({c['level']}): {c['message']}"))
    out["steps"].append("shellcheck")
    for sc in spec.get("exec", ()):
        errs += run_exec(b, text, sc, ctx, linux=False)
        out["steps"].append(f"exec[{sc['name']}] macOS")
        if ctx.live and sc.get("linux", True):
            errs += run_exec(b, text, sc, ctx, linux=True)
            out["steps"].append(f"exec[{sc['name']}] Linux")
    return errs


def check_sh_tree(b, ctx, out):
    """commands/ and agents/ bash blocks: they hold <placeholders> and {{template}} fields for the agent to fill,
    so those become plain words first; then bash -n (macOS bash 3.2) and shellcheck at error severity."""
    text = MUSTACHE.sub("${HARNESS_TEMPLATE_FIELD}", PLACEHOLDER.sub("HARNESS_PLACEHOLDER", b.text))
    f = ctx.path(b, ".sh")
    f.write_text(text)
    errs = []
    for bash, ver in ctx.bashes:
        r = run([bash, "-n", str(f)])
        for line in r.stderr.splitlines():
            m = re.search(r"line (\d+): (.*)", line)
            errs.append((b.md_line(int(m.group(1))) if m else b.first_line, f"bash {ver} -n: {m.group(2) if m else line}"))
    r = run(["shellcheck", "-s", "bash", "-S", "error", "-f", "json1", str(f)])
    try:
        comments = json.loads(r.stdout or "{}").get("comments", [])
    except json.JSONDecodeError:
        comments = [{"line": 1, "code": "?", "level": "error", "message": (r.stdout + r.stderr).strip()}]
    for c in comments:
        errs.append((b.md_line(c["line"]), f"shellcheck SC{c['code']} ({c['level']}): {c['message']}"))
    errs += [(b.first_line, m) for m in portability(b.text)]
    out["steps"] += ["bash -n (placeholders as words)", "shellcheck -S error", "portability lint"]
    return errs


def run_snippets(ctx):
    """The exact lines the 2026-09-30 portability fixes changed (grep -P, BSD-first stat), cut out of the
    command/agent/hook files and run in fixture dirs: macOS bash 3.2 always, Linux bash 5 with --live."""
    results = []
    for sn in U.SNIPPETS:
        src = CLAUDE / sn["file"]
        lines = src.read_text(encoding="utf-8").split("\n")
        idx = [i for i, ln in enumerate(lines) if sn["contains"] in ln]
        if len(idx) != 1:
            results.append((sn, src, 1, [f"snippet {sn['name']!r}: {len(idx)} lines contain {sn['contains']!r} (moved/changed?)"], []))
            continue
        i = idx[0]
        j = i
        if sn.get("until"):
            while j < len(lines) and not re.search(sn["until"], lines[j]):
                j += 1
        while lines[j].rstrip().endswith("\\"):
            j += 1
        text = "\n".join(ln.strip() if sn.get("dedent", True) else ln for ln in lines[i:j + 1]) + "\n"
        fake = B.Block(sn["file"], "sh", "bash", 0, i + 1, 0, "", text.rstrip("\n").split("\n"), prefix=".claude/")
        errs, where = [], ["macOS"]
        errs += [m for _, m in run_exec(fake, text, sn, ctx, linux=False)]
        if ctx.live and sn.get("linux", True):
            errs += [m for _, m in run_exec(fake, text, sn, ctx, linux=True)]
            where.append("Linux")
        results.append((sn, src, i + 1, errs, where))
    return results


def run_exec(b, text, sc, ctx, linux):
    """Run the block in a throwaway directory after the scenario's setup script, then assert on the
    exit code and output. The setup only builds fixtures; the block is never edited beyond the
    scenario's declared subst. `prepend` blocks (same file) run first in the same script; with `post`,
    the block is sourced so post sees its variables and functions (an `exit` in the block ends it)."""
    where = "Linux" if linux else "macOS"
    for tool in sc.get("needs", ()):
        if not shutil.which(tool):
            return [(b.first_line, f"exec[{sc['name']}] {where}: needs {tool}, which is not installed")]
    d = Path(tempfile.mkdtemp(prefix="exec-", dir=ctx.tmp))
    w = d / "w"
    w.mkdir()
    pre = "".join(ctx.block_text(k) for k in sc.get("prepend", ()))
    (d / "setup.sh").write_text(sc.get("setup") or "")
    (d / "block.sh").write_text(pre + apply_subst(text, sc.get("subst")))
    root = f"/tmp/{d.name}" if linux else str(d)
    env_lines = "".join(f"export {k}={shlex.quote(str(v).replace('{cwd}', root + '/w'))}\n" for k, v in sc.get("env", {}).items())
    post = sc.get("post")
    if post and sc.get("same_shell"):     # post reads the block's variables/functions; an exit ends it all
        body = '. ../block.sh\n__rc=$?\n' + post + '\nexit $__rc\n'
    elif post:                            # post inspects files; it runs even when the block exits
        body = '( . ../block.sh )\n__rc=$?\n' + post + '\nexit $__rc\n'
    else:
        body = 'bash ../block.sh\n'
    (d / "run.sh").write_text(
        'cd "$(dirname "$0")/w" || exit 98\n' + env_lines +
        "bash ../setup.sh >/dev/null 2>&1 || { echo 'HARNESS: setup failed'; exit 97; }\n" + body)
    if linux:
        ctr = ctx.linux_container()
        ctx.docker("cp", str(d), f"{ctr}:{root}")
        r = ctx.docker("exec", ctr, "bash", f"{root}/run.sh")
    else:
        r = run(["/bin/bash", str(d / "run.sh")], env={"HOME": str(d)})
    outp = r.stdout + r.stderr
    errs = []
    want = sc.get("rc", 0)
    rc_ok = (r.returncode != 0) if want == "nonzero" else (r.returncode == want)
    if r.returncode == 97:
        errs.append((b.first_line, f"exec[{sc['name']}] {where}: harness setup failed"))
    elif not rc_ok:
        errs.append((b.first_line, f"exec[{sc['name']}] {where}: exit {r.returncode}, expected {want}; output: {outp.strip()[:400]}"))
    for pat in sc.get("expect", ()):
        if not re.search(pat, outp, re.M):
            errs.append((b.first_line, f"exec[{sc['name']}] {where}: output lacks /{pat}/; output: {outp.strip()[:400]}"))
    for pat in sc.get("reject", ()):
        if re.search(pat, outp, re.M):
            errs.append((b.first_line, f"exec[{sc['name']}] {where}: output has /{pat}/; output: {outp.strip()[:400]}"))
    return errs


# ── SQL ──────────────────────────────────────────────────────────────────────────────────────────────
def sql_statements_pg(full: str):
    """(start offset of first token, statement text) per statement, via the PostgreSQL 17 parser."""
    import pglast
    out = []
    for sl in pglast.split(full, with_parser=True, only_slices=True):
        s = full[sl]
        lead = re.match(r"(\s|--[^\n]*\n)*", s).end()
        out.append((sl.start + lead, s[lead:]))
    return out


def line_of(text, off):
    return text.count("\n", 0, off) + 1


def map_line(b, prefix, full_line):
    rel = full_line - prefix
    if rel < 1 or rel > len(b.lines):
        return b.first_line, " (in the harness wrapper)"
    return b.md_line(rel), ""


def check_sql(b, spec, ctx, out):
    dialect = spec["check"]
    text = apply_subst(b.text, spec.get("subst"))
    full, prefix = wrap(text, spec)
    errs = []
    if dialect == "pg":
        import pglast
        try:
            pglast.parse_sql(full)
        except pglast.parser.ParseError as e:
            loc = e.args[1] if len(e.args) > 1 and isinstance(e.args[1], int) else 0   # ParseError(message, offset)
            # pglast 7.18 reports char offset minus the extra UTF-8 bytes before it (2 per em dash):
            # find the char index c with c - (bytes(c) - c) == loc
            c = loc
            while c < len(full) and 2 * c - len(full[:c].encode()) < loc:
                c += 1
            loc = c
            ln, note = map_line(b, prefix, line_of(full, loc))
            errs.append((ln, f"PostgreSQL 17 grammar (libpg_query): {e.args[0]}{note}"))
        out["steps"].append("pg17 parse")
        if ctx.live and not errs:
            errs += pg_exec(b, spec, ctx, full, prefix)
            out["steps"].append("executed on postgres:17")
        elif not ctx.live:
            out["deferred"].append("postgres:17 execution")
    elif dialect == "sqlite":
        errs += sqlite_exec(b, spec, full, prefix)
        import sqlite3
        out["steps"].append(f"executed on SQLite {sqlite3.sqlite_version}")
    elif dialect == "mysql":
        if ctx.live:
            errs += mysql_exec(b, spec, ctx, full, prefix)
            out["steps"].append("executed on mysql:8.4")
        else:
            out["deferred"].append("mysql:8.4 execution (no offline MySQL parser)")
    return errs


def pg_connect(ctx, db="postgres", user="postgres"):
    import psycopg
    if ctx.pg is None:
        ctx.start("cfgpk-pg", "-e", "POSTGRES_PASSWORD=harness", "-p", "127.0.0.1::5432", "postgres:17",
                  "-c", "shared_preload_libraries=pg_stat_statements")
        port = ctx.port("cfgpk-pg", 5432)
        for _ in range(120):
            try:
                psycopg.connect(f"host=127.0.0.1 port={port} user=postgres password=harness dbname=postgres",
                                autocommit=True, connect_timeout=2).close()
                break
            except Exception:
                time.sleep(0.5)
        ctx.pg = port
        v = psycopg.connect(f"host=127.0.0.1 port={port} user=postgres password=harness dbname=postgres", autocommit=True)
        ctx.pg_version = v.execute("show server_version").fetchone()[0]
        v.close()
    pw = "harness"
    return psycopg.connect(f"host=127.0.0.1 port={ctx.pg} user={user} password={pw} dbname={db}", autocommit=True)


def pg_fresh_db(ctx, name):
    c = pg_connect(ctx)
    c.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
    c.execute(f'CREATE DATABASE "{name}"')
    c.close()
    return pg_connect(ctx, name)


def pg_exec(b, spec, ctx, full, prefix):
    import psycopg
    errs = []
    dbname = "b_" + re.sub(r"[^a-z0-9]+", "_", b.key.lower())[-55:]
    conn = pg_fresh_db(ctx, dbname)
    fixture = U.SQL_FIXTURES.get(spec.get("fixture", ""), "")
    try:
        if fixture:
            conn.execute(fixture)
    except psycopg.Error as e:
        return [(b.first_line, f"harness fixture {spec.get('fixture')!r} failed: {e}")]
    notices = []
    conn.add_notice_handler(lambda d: notices.append(d))
    if spec.get("role"):
        conn.execute(f"SET ROLE {spec['role']}")
    for k, (off, stmt) in enumerate(sql_statements_pg(full)):
        start = line_of(full, off)
        sent = stmt
        if spec.get("params") and re.search(r"\$\d", stmt) and not re.match(r"(?i)\s*(prepare|create)\b", stmt):
            sent = f"PREPARE harness_p{k} AS {stmt}"
        notices.clear()
        try:
            conn.execute(sent.encode())
        except psycopg.Error as e:
            pos = e.diag.statement_position
            rel = int(pos) - (len(sent) - len(stmt)) if pos else 1
            ln, note = map_line(b, prefix, start + stmt.count("\n", 0, max(rel - 1, 0)))
            errs.append((ln, f"postgres {ctx.pg_version}: {e.diag.message_primary or e}{note}"))
            break
        for n in notices:
            if n.severity in ("WARNING",) and not spec.get("allow_warning"):
                ln, note = map_line(b, prefix, start)
                errs.append((ln, f"postgres {ctx.pg_version} WARNING: {n.message_primary}{note}"))
        if spec.get("rollback_between") and conn.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
            conn.execute("ROLLBACK")
    conn.close()
    return errs


def claim_line(cl):
    """(markdown path, line) of the text a claim is about; a claim may sit in prose, not a block."""
    path = cl["block"].split("#")[0]
    lines = (SKILLS / path).read_text(encoding="utf-8").split("\n")
    hit = next((i for i, ln in enumerate(lines, 1) if cl["at"] and cl["at"] in ln), None)
    return path, hit or 1, hit is not None


def judge_claim(cl, engine, out, err):
    """Compare one claim's result (output text, or the error it raised) with what the doc says."""
    msgs = []
    if cl.get("error"):
        if err is None:
            msgs.append(f"expected an error /{cl['error']}/ on {engine}, the statement succeeded: {out}")
        elif not re.search(cl["error"], err):
            msgs.append(f"expected /{cl['error']}/ on {engine}, got: {err}")
        return msgs
    if err is not None:
        return [f"{engine}: {err}"]
    for pat in cl.get("expect", ()):
        if not re.search(pat, out, re.M):
            msgs.append(f"not true on {engine}: result lacks /{pat}/:\n{out}")
    for pat in cl.get("reject", ()):
        if re.search(pat, out, re.M):
            msgs.append(f"not true on {engine}: result has /{pat}/:\n{out}")
    return msgs


def run_claims(ctx, families):
    """What a doc claims about engine behaviour (plan shapes, defaults, errors), proven on the engine.
    SQLite claims run in every run; PostgreSQL and MySQL claims with --live."""
    results = []
    sets = []
    if "sql" in families:
        sets.append(("sqlite", U.SQLITE_CLAIMS))
        if ctx.live:
            sets += [("pg", U.CLAIMS), ("mysql", U.MYSQL_CLAIMS)]
    if "ngql" in families and ctx.live:
        sets.append(("ngql", U.NGQL_CLAIMS))
    for engine, claims in sets:
        for cl in claims:
            path, ln, found = claim_line(cl)
            if not found:
                results.append((cl, path, [(ln, f"claim text {cl['at']!r} not found in the doc (moved/reworded?)")], ""))
                continue
            out, err, label = "", None, engine
            if engine == "pg":
                import psycopg
                conn = pg_fresh_db(ctx, "claim_" + re.sub(r"[^a-z0-9]+", "_", cl["name"].lower())[:50])
                label = f"postgres {ctx.pg_version}"
                try:
                    import pglast
                    setup = cl.get("setup", "SELECT 1")
                    if cl.get("block_sql"):
                        setup = setup.replace("{BLOCK}", ctx.block_text(cl["block_sql"]))
                    for st in pglast.split(setup):   # one by one: VACUUM can't run in a block
                        conn.execute(st.encode())
                    out = "\n".join(str(r[0]) for r in conn.execute(cl["query"].encode()).fetchall())
                except psycopg.Error as e:
                    err = e.diag.message_primary or str(e)
                conn.close()
                # roles are cluster-wide: drop the claim's database so no grant keeps its role alive
                adm = pg_connect(ctx)
                adm.execute(f'DROP DATABASE IF EXISTS "claim_{re.sub(r"[^a-z0-9]+", "_", cl["name"].lower())[:50]}" WITH (FORCE)')
                adm.close()
            elif engine == "mysql":
                import pymysql
                mysql_connect(ctx)
                label = f"mysql {ctx.mysql_version}"
                db = "claim_" + re.sub(r"[^a-z0-9]+", "_", cl["name"].lower())[:50]
                conn = pymysql.connect(host="127.0.0.1", port=ctx.mysql, user="root", password="harness", autocommit=True)
                try:
                    with conn.cursor() as cur:
                        cur.execute(f"DROP DATABASE IF EXISTS `{db}`")
                        cur.execute(f"CREATE DATABASE `{db}`")
                        cur.execute(f"USE `{db}`")
                        for st in cl.get("setup", ()):
                            cur.execute(st)
                        cur.execute(cl["query"])
                        out = "\n".join(str(r[0]) for r in cur.fetchall())
                except pymysql.MySQLError as e:
                    err = str(e)
                conn.close()
            elif engine == "ngql":
                nebula_up(ctx)
                label = f"NebulaGraph {U.NEBULA_VERSION}"
                for st in cl.get("setup", ()):
                    if st == "SLEEP":
                        time.sleep(4)
                        continue
                    o = ngql_raw(ctx, st)
                    if "[ERROR" in o:
                        err = "setup: " + re.search(r"\[ERROR.*", o).group(0)
                        break
                if err is None:
                    o = ngql_raw(ctx, cl["query"])
                    m = re.search(r"\[ERROR.*", o)
                    err = m.group(0) if m else None
                    out = "\n".join(l for l in o.splitlines() if l.startswith("|") or "Empty set" in l or "Got " in l)
            else:
                import sqlite3
                label = f"SQLite {sqlite3.sqlite_version}"
                conn = sqlite3.connect(":memory:")
                try:
                    conn.executescript(cl.get("setup", ""))
                    out = "\n".join(str(r[0]) for r in conn.execute(cl["query"]).fetchall())
                except sqlite3.Error as e:
                    err = str(e)
                conn.close()
            msgs = judge_claim(cl, label, out, err)
            first = (out.strip().splitlines() or [err or "ok"])[0] if not msgs else ""
            results.append((cl, path, [(ln, f"claim '{cl['name']}' {m}") for m in msgs], f"{label}: {first.strip()}"))
    return results


def sqlite_exec(b, spec, full, prefix):
    import sqlite3
    errs = []
    conn = sqlite3.connect(":memory:")
    conn.isolation_level = None
    try:
        conn.executescript(U.SQL_FIXTURES.get(spec.get("fixture", ""), ""))
    except sqlite3.Error as e:
        return [(b.first_line, f"harness fixture failed: {e}")]
    buf, start = "", None
    for i, line in enumerate(full.split("\n"), 1):
        if start is None and line.strip() and not line.strip().startswith("--"):
            start = i
        buf += line + "\n"
        if sqlite3.complete_statement(buf):
            try:
                conn.execute(buf)
            except sqlite3.Error as e:
                ln, note = map_line(b, prefix, start or i)
                errs.append((ln, f"sqlite {sqlite3.sqlite_version}: {e}{note}"))
                break
            buf, start = "", None
    if buf.strip() and not all(l.strip().startswith("--") or not l.strip() for l in buf.splitlines()):
        errs.append((b.md_line(len(b.lines)), "sqlite: incomplete statement at end of block"))
    conn.close()
    return errs


def mysql_exec(b, spec, ctx, full, prefix):
    import pymysql
    mysql_connect(ctx)
    return mysql_run(b, spec, ctx, full, prefix)


def mysql_connect(ctx):
    import pymysql
    if ctx.mysql is None:
        ctx.start("cfgpk-mysql", "-e", "MYSQL_ROOT_PASSWORD=harness", "-p", "127.0.0.1::3306", "mysql:8.4")
        port = ctx.port("cfgpk-mysql", 3306)
        for _ in range(240):
            try:
                pymysql.connect(host="127.0.0.1", port=port, user="root", password="harness").close()
                break
            except Exception:
                time.sleep(0.5)
        ctx.mysql = port
        c = pymysql.connect(host="127.0.0.1", port=port, user="root", password="harness")
        with c.cursor() as cur:
            cur.execute("select version()")
            ctx.mysql_version = cur.fetchone()[0]
        c.close()


def mysql_run(b, spec, ctx, full, prefix):
    import pymysql
    db = "b_" + re.sub(r"[^a-z0-9]+", "_", b.key.lower())[-50:]
    conn = pymysql.connect(host="127.0.0.1", port=ctx.mysql, user="root", password="harness", autocommit=True)
    errs = []
    with conn.cursor() as cur:
        cur.execute(f"DROP DATABASE IF EXISTS `{db}`")
        cur.execute(f"CREATE DATABASE `{db}`")
        cur.execute(f"USE `{db}`")
        for st in split_semicolon(U.SQL_FIXTURES.get(spec.get("fixture", ""), "")):
            cur.execute(st[1])
        for start, stmt in split_semicolon(full):
            sent = stmt
            if "?" in stmt and spec.get("params"):
                sent = "PREPARE harness_p FROM " + conn.escape(stmt)
            try:
                cur.execute(sent)
                cur.fetchall()
                cur.execute("SHOW WARNINGS")
                for lvl, code, msg in cur.fetchall():
                    if lvl in ("Warning", "Error") and code not in spec.get("allow_codes", ()):
                        ln, note = map_line(b, prefix, start)
                        errs.append((ln, f"mysql {ctx.mysql_version} {lvl} {code}: {msg}{note}"))
            except pymysql.MySQLError as e:
                ln, note = map_line(b, prefix, start)
                errs.append((ln, f"mysql {ctx.mysql_version}: {e.args[1] if len(e.args) > 1 else e}{note}"))
                break
    conn.close()
    return errs


def split_semicolon(text):
    """(line, statement) for simple scripts: statements end with ';' at end of line, '--' comments."""
    out, buf, start = [], [], None
    for i, line in enumerate(text.split("\n"), 1):
        code = line.split("--", 1)[0] if "--" in line and "'" not in line.split("--", 1)[0] else line
        if start is None and code.strip():
            start = i
        if code.strip():
            buf.append(code)
        if code.rstrip().endswith(";"):
            out.append((start, "\n".join(buf).rstrip().rstrip(";")))
            buf, start = [], None
    if buf:
        out.append((start, "\n".join(buf)))
    return out


# ── YAML ─────────────────────────────────────────────────────────────────────────────────────────────
def yaml_loader():
    import yaml

    class Strict(yaml.SafeLoader):
        pass

    def mapping(loader, node, deep=False):
        seen = set()
        for k, _ in node.value:
            key = loader.construct_object(k, deep=deep)
            if key in seen:
                raise yaml.constructor.ConstructorError(None, None, f"duplicate key {key!r}", k.start_mark)
            seen.add(key)
        return yaml.SafeLoader.construct_mapping(loader, node, deep)

    Strict.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    return Strict


def check_yaml(b, spec, ctx, out):
    import yaml
    text = apply_subst(b.text, spec.get("subst"))
    errs = []
    try:
        docs = list(yaml.load_all(text, Loader=yaml_loader()))
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None) or getattr(e, "context_mark", None)
        return [(b.md_line(mark.line + 1) if mark else b.first_line, f"YAML: {str(e).splitlines()[0]} {getattr(e, 'problem', '') or ''}")]
    out["steps"].append("yaml parse (duplicate keys fail)")
    full, prefix = wrap(text, spec)
    if spec.get("gha"):
        f = ctx.path(b, ".yml")
        f.write_text(full)
        r = run(["actionlint", "-format", "{{json .}}", "-no-color", str(f)])
        try:
            found = json.loads(r.stdout or "[]")
        except json.JSONDecodeError:
            found = [{"line": 1, "message": (r.stdout + r.stderr).strip(), "kind": "?"}]
        for e in found:
            ln, note = map_line(b, prefix, e.get("line", 1))
            errs.append((ln, f"actionlint [{e.get('kind')}]: {e.get('message')}{note}"))
        out["steps"].append("actionlint (+shellcheck on run:)")
    if spec.get("compose"):
        f = ctx.path(b, ".compose.yml")
        f.write_text(full)
        r = run([DOCKER, "compose", "-f", str(f), "config", "-q"], env=spec.get("env"))
        if r.returncode:
            errs.append((b.first_line, f"docker compose config: {(r.stderr or r.stdout).strip()}"))
        out["steps"].append("docker compose config")
    if spec.get("maestro"):
        errs += maestro_check(b, docs, spec)
        out["steps"].append("Maestro flow structure")
    if spec.get("drill"):
        errs += drill_check(b, docs)
        out["steps"].append("drill benchmark structure; credentials from the environment")
    if spec.get("openapi"):
        from openapi_spec_validator import validate
        from openapi_spec_validator.readers import read_from_filename  # noqa: F401
        try:
            validate(yaml.safe_load(full))
        except Exception as e:
            errs.append((b.first_line, f"OpenAPI 3.1: {str(e).splitlines()[0]}"))
        out["steps"].append("openapi-spec-validator (3.1)")
    if spec.get("spring"):
        meta = U.spring_metadata(ctx)
        if meta is None:
            out["deferred"].append(f"Spring Boot {U.SPRING_BOOT} property check (configuration metadata jars not in ~/.m2)")
        else:
            for k, (ln, why) in U.spring_unknown_keys(docs, meta, text).items():
                errs.append((b.md_line(ln), f"Spring Boot {U.SPRING_BOOT}: unknown property {k}{why}"))
            out["steps"].append(f"every key a Spring Boot {U.SPRING_BOOT} property ({len(meta)} in its configuration metadata)")
    if spec.get("golangci"):
        d = docs[0] if docs else {}
        if str(d.get("version")) != "2":
            errs.append((b.first_line, 'golangci-lint v2 refuses this config: no `version: "2"` key ("unsupported version of the configuration")'))
        out["steps"].append("golangci-lint v2 config shape")
        if ctx.live:
            gd = Path(tempfile.mkdtemp(prefix="golangci-", dir=ctx.tmp))
            (gd / ".golangci.yml").write_text(text)
            (gd / "go.mod").write_text("module example.com/harness\n\ngo 1.25\n")
            r = run(["golangci-lint", "config", "verify", "-c", ".golangci.yml"], cwd=gd)
            if r.returncode:
                errs.append((b.first_line, f"golangci-lint config verify: {(r.stderr or r.stdout).strip()}"))
            out["steps"].append("golangci-lint config verify")
    if spec.get("k8s"):
        if ctx.live:
            f = ctx.path(b, ".k8s.yaml")
            f.write_text(full)
            cache = HERE / ".cache" / "kubeconform"
            cache.mkdir(parents=True, exist_ok=True)
            r = run(["kubeconform", "-strict", "-summary", "-output", "json", "-kubernetes-version", U.K8S_VERSION,
                     "-cache", str(cache), str(f)])
            try:
                res = json.loads(r.stdout or "{}").get("resources", [])
            except json.JSONDecodeError:
                res = [{"status": "statusError", "msg": (r.stdout + r.stderr).strip()}]
            for e in res:
                if e.get("status") not in ("statusValid", "statusSkipped"):
                    errs.append((b.first_line, f"kubeconform k8s {U.K8S_VERSION} {e.get('kind', '')}/{e.get('name', '')}: {e.get('msg')}"))
            if r.returncode and not res:
                errs.append((b.first_line, f"kubeconform: {(r.stdout + r.stderr).strip()[:300]}"))
            out["steps"].append(f"kubeconform -strict (k8s {U.K8S_VERSION})")
        else:
            out["deferred"].append("kubeconform (schemas are fetched)")
    return errs


MAESTRO_CONFIG_KEYS = {"appId", "url", "name", "tags", "env", "onFlowStart", "onFlowComplete", "jsEngine", "properties"}
# Commands documented at https://docs.maestro.dev/api-reference/commands (checked 2026-09-30)
MAESTRO_COMMANDS = {
    "addMedia", "assertNotVisible", "assertTrue", "assertVisible", "assertNoDefectsWithAI", "assertWithAI",
    "back", "clearKeychain", "clearState", "copyTextFrom", "doubleTapOn", "eraseText", "evalScript",
    "extendedWaitUntil", "extractTextWithAI", "hideKeyboard", "inputText", "inputRandomEmail",
    "inputRandomPersonName", "inputRandomNumber", "inputRandomText", "killApp", "launchApp", "longPressOn",
    "openLink", "pasteText", "pressKey", "repeat", "retry", "runFlow", "runScript", "scroll", "scrollUntilVisible",
    "setAirplaneMode", "setLocation", "setOrientation", "startRecording", "stopApp", "stopRecording", "swipe",
    "takeScreenshot", "tapOn", "toggleAirplaneMode", "travel", "waitForAnimationToEnd", "setPermissions",
}


DRILL_KEYS = {"base", "concurrency", "iterations", "rampup", "plan"}
DRILL_ACTIONS = {"request", "assign", "delay", "exec", "assert"}   # github.com/fcsonline/drill README


def drill_check(b, docs):
    """drill (fcsonline/drill) benchmark: known top-level keys, one action per plan item, and no static
    credential — an Authorization header has to interpolate it ({{ VAR }} reads the environment)."""
    errs = []
    doc = docs[-1] if docs else {}
    for k in set(doc) - DRILL_KEYS:
        errs.append((b.first_line, f"drill: unknown top-level key {k!r}"))
    for item in doc.get("plan", []):
        acts = set(item) & DRILL_ACTIONS
        if "name" not in item or len(acts) != 1:
            errs.append((b.first_line, f"drill: plan item needs a name and exactly one of {sorted(DRILL_ACTIONS)}: {item}"))
            continue
        req = item.get("request") or {}
        for h, v in (req.get("headers") or {}).items():
            if h.lower() == "authorization" and "{{" not in str(v):
                errs.append((b.first_line, f"drill: static credential in {item['name']!r} ({h}: {v}); interpolate it from the environment"))
    return errs


def maestro_check(b, docs, spec):
    errs = []
    if spec.get("maestro") == "commands":
        cfg, cmds = {}, docs[0] if docs else []
    else:
        if len(docs) != 2:
            return [(b.first_line, f"Maestro flow: expected a config document and a command list separated by ---, got {len(docs)} document(s)")]
        cfg, cmds = docs
        if not isinstance(cfg, dict) or "appId" not in cfg and "url" not in cfg:
            errs.append((b.first_line, "Maestro flow config needs appId (or url)"))
        for k in (cfg or {}):
            if k not in MAESTRO_CONFIG_KEYS:
                errs.append((b.first_line, f"Maestro flow config: unknown key {k!r}"))
    if not isinstance(cmds, list):
        return errs + [(b.first_line, "Maestro flow: the command section must be a list")]

    def walk(items):
        for it in items:
            name = it if isinstance(it, str) else (next(iter(it)) if isinstance(it, dict) and len(it) == 1 else None)
            if name not in MAESTRO_COMMANDS:
                errs.append((b.first_line, f"Maestro: unknown or malformed command {it!r}"))
                continue
            if isinstance(it, dict) and isinstance(it[name], dict) and isinstance(it[name].get("commands"), list):
                walk(it[name]["commands"])
    walk(cmds)
    return errs


# ── JSON ─────────────────────────────────────────────────────────────────────────────────────────────
def strip_jsonc(text):
    """Blank out // comments outside strings, keeping every line and column (so errors map back)."""
    out, in_str, esc, i = [], False, False, 0
    while i < len(text):
        c = text[i]
        if in_str:
            out.append(c)
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
            out.append(c)
        elif text.startswith("//", i):
            j = text.find("\n", i)
            j = len(text) if j < 0 else j
            out.append(" " * (j - i))
            i = j
            continue
        else:
            out.append(c)
        i += 1
    return "".join(out)


def json_values(text, b, prefix):
    """All JSON values in text (one or several), with // comments blanked (JSONC)."""
    clean = strip_jsonc(text)
    dec = json.JSONDecoder()
    vals, i = [], 0
    while True:
        while i < len(clean) and clean[i].isspace():
            i += 1
        if i >= len(clean):
            break
        try:
            v, j = dec.raw_decode(clean, i)
        except json.JSONDecodeError as e:
            ln, note = map_line(b, prefix, e.lineno)
            raise Finding(f"{ln}\x00JSON: {e.msg} (column {e.colno}){note}")
        vals.append(v)
        i = j
    return vals


def console_requests(text, b):
    """Kibana/Elasticsearch Dev Tools console format: 'METHOD /path' lines, each followed by an
    optional JSON body (NDJSON lines for _bulk). Bodies must parse; // lines are comments."""
    reqs, cur = [], None
    for i, ln in enumerate(text.split("\n"), 1):
        s = ln.strip()
        if not s or s.startswith("//"):
            continue
        m = re.match(r"^(GET|POST|PUT|DELETE|HEAD)\s+(\S+)(\s+(.*))?$", s)
        if m:
            cur = {"method": m.group(1), "path": m.group(2), "line": i, "body": [], "inline": m.group(4)}
            reqs.append(cur)
            if m.group(4):
                cur["body"].append((i, m.group(4)))
            continue
        if cur is None:
            raise Finding(f"{b.md_line(i)}\x00console: body line before any request line")
        cur["body"].append((i, ln))
    return reqs


def check_json(b, spec, ctx, out):
    text = apply_subst(b.text, spec.get("subst"))
    mode = spec.get("mode", "strict")
    errs = []
    try:
        if mode == "console":
            reqs = console_requests(text, b)
            for rq in reqs:
                lines = rq["body"]
                if not lines:
                    continue
                if rq["path"].rstrip("/").endswith("_bulk"):
                    for i, ln in lines:
                        try:
                            json.loads(ln)
                        except json.JSONDecodeError as e:
                            errs.append((b.md_line(i), f"NDJSON (_bulk) line: {e.msg}"))
                else:
                    body = "\n".join(ln for _, ln in lines)
                    try:
                        json.loads(body)
                    except json.JSONDecodeError as e:
                        errs.append((b.md_line(lines[0][0] + e.lineno - 1), f"request body of {rq['method']} {rq['path']}: {e.msg}"))
            vals = []
            out["steps"].append(f"Dev Tools console: {len(reqs)} request(s), bodies parse")
        else:
            full, prefix = wrap(text, spec)
            vals = json_values(full, b, prefix)
            if mode == "strict" and (len(vals) != 1 or re.search(r"^\s*//", text, re.M)):
                errs.append((b.first_line, f"JSON: expected exactly one value and no comments, got {len(vals)} value(s)"))
            if spec.get("count") and len(vals) != spec["count"]:
                errs.append((b.first_line, f"JSON: expected {spec['count']} values, got {len(vals)}"))
            out["steps"].append("json parse" + (" (template: declared substitutions)" if spec.get("subst") else "")
                                + (" (// comments, several values)" if mode == "jsonc" else ""))
    except Finding as f:
        ln, msg = str(f).split("\x00", 1)
        return [(int(ln), msg)]
    schemas = spec.get("schema") or []
    for name in [schemas] if isinstance(schemas, str) else schemas:
        errs += U.SCHEMA_CHECKS[name](b, vals, spec)
        live = {"eslint_rules": " (+ ESLint 10 with eslint-plugin-jsx-a11y loads it and reports a violation)",
                "tsconfig": " (+ tsc --showConfig keeps every option)"}.get(name, "") if ctx.live else ""
        out["steps"].append(f"schema: {name}{live}")
    return errs


# ── Dockerfile ───────────────────────────────────────────────────────────────────────────────────────
def check_dockerfile(b, spec, ctx, out):
    text = apply_subst(b.text, spec.get("subst"))
    full, prefix = wrap(text, spec)
    f = ctx.path(b, ".Dockerfile")
    f.write_text(full)
    errs = []
    cmd = ["hadolint", "--no-color", "--format", "json"]
    for code in spec.get("hadolint_ignore", {}):
        cmd += ["--ignore", code]
    r = run(cmd + [str(f)])
    try:
        found = json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        found = [{"line": 1, "code": "?", "message": (r.stdout + r.stderr).strip(), "level": "error"}]
    for e in found:
        ln, note = map_line(b, prefix, e.get("line", 1))
        errs.append((ln, f"hadolint {e.get('code')} ({e.get('level')}): {e.get('message')}{note}"))
    out["steps"].append("hadolint")
    if ctx.live:
        ctxdir = Path(tempfile.mkdtemp(prefix="docker-", dir=ctx.tmp))
        for rel, content in U.DOCKER_CONTEXTS[spec["context"]].items():
            p = ctxdir / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
        tag = "cfgpk-" + re.sub(r"[^a-z0-9]+", "-", b.key.lower()).strip("-")[-60:]
        args = [x for k, v in spec.get("build_args", {}).items() for x in ("--build-arg", f"{k}={v}")]
        r = run([DOCKER, "build", "-q", "-f", str(f), "-t", tag, *args, str(ctxdir)], timeout=1800)
        if r.returncode:
            errs.append((b.first_line, f"docker build: {(r.stderr or r.stdout).strip()[-1200:]}"))
        else:
            out["steps"].append("docker build")
            for probe in spec.get("run_checks", ()):
                rr = run([DOCKER, "run", "--rm", *probe["args"], tag, *probe.get("cmd", [])], timeout=120)
                if not re.search(probe["expect"], rr.stdout + rr.stderr):
                    errs.append((b.first_line, f"docker run {probe['name']}: output lacks /{probe['expect']}/: {(rr.stdout + rr.stderr).strip()[:300]}"))
                else:
                    out["steps"].append(f"docker run: {probe['name']}")
            run([DOCKER, "image", "rm", "-f", tag])
    else:
        out["deferred"].append("docker build")
    return errs


# ── HCL ──────────────────────────────────────────────────────────────────────────────────────────────
def tf_bin():
    return shutil.which("terraform") or shutil.which("tofu")


def check_hcl(b, spec, ctx, out):
    tf = tf_bin()
    name = os.path.basename(tf)
    text = apply_subst(b.text, spec.get("subst"))
    root = Path(tempfile.mkdtemp(prefix="hcl-", dir=ctx.tmp))
    d = root / U.HCL_LAYOUT.get(spec.get("fixture", ""), ".")   # where the block's own relative paths resolve
    d.mkdir(parents=True, exist_ok=True)
    (d / "block.tf").write_text(text)
    errs = []
    r = run([tf, "fmt", "-check", "-diff", "-no-color", "block.tf"], cwd=d)
    if r.returncode:
        errs.append((b.first_line, f"{name} fmt -check: not canonical:\n{r.stdout.strip()[:800]}"))
    out["steps"].append(f"{name} fmt -check")
    if ctx.live:
        for rel, content in U.HCL_FIXTURES.get(spec.get("fixture", ""), {}).items():
            p = (root if "/" in rel else d) / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
        env = {"TF_PLUGIN_CACHE_DIR": str(HERE / ".cache" / "tf-plugins"), "TF_IN_AUTOMATION": "1"}
        (HERE / ".cache" / "tf-plugins").mkdir(parents=True, exist_ok=True)
        r = run([tf, "init", "-backend=false", "-input=false", "-no-color"], cwd=d, env=env)
        if r.returncode:
            errs.append((b.first_line, f"{name} init: {(r.stderr or r.stdout).strip()[-600:]}"))
        else:
            r = run([tf, "validate", "-json", "-no-color"], cwd=d, env=env)
            res = json.loads(r.stdout or "{}")
            for dg in res.get("diagnostics", []):
                rng = dg.get("range") or {}
                ln = b.md_line(rng["start"]["line"]) if rng.get("filename") == "block.tf" else b.first_line
                errs.append((ln, f"{name} validate {dg.get('severity')}: {dg.get('summary')} {dg.get('detail', '')}".strip()))
            out["steps"].append(f"{name} init -backend=false + validate")
    else:
        out["deferred"].append(f"{name} init + validate (providers are downloaded)")
    return errs


# ── nGQL ─────────────────────────────────────────────────────────────────────────────────────────────
def nebula_up(ctx):
    if ctx.nebula:
        return
    v = U.NEBULA_VERSION
    hb = ["--heartbeat_interval_secs=1"]
    ctx.start("cfgpk-nebula-metad", "-p", "127.0.0.1::9669", f"vesoft/nebula-metad:{v}",
              "--meta_server_addrs=127.0.0.1:9559", "--local_ip=127.0.0.1", "--ws_ip=127.0.0.1", "--port=9559",
              "--data_path=/data/meta", "--log_dir=/logs", *hb)
    net = "--network=container:cfgpk-nebula-metad"
    ctx.start("cfgpk-nebula-storaged", net, f"vesoft/nebula-storaged:{v}", "--meta_server_addrs=127.0.0.1:9559",
              "--local_ip=127.0.0.1", "--ws_ip=127.0.0.1", "--port=9779", "--data_path=/data/storage", "--log_dir=/logs", *hb)
    ctx.start("cfgpk-nebula-graphd", net, f"vesoft/nebula-graphd:{v}", "--meta_server_addrs=127.0.0.1:9559",
              "--local_ip=127.0.0.1", "--ws_ip=127.0.0.1", "--port=9669", "--log_dir=/logs", *hb)
    ctx.nebula = net
    deadline = time.time() + 300
    while time.time() < deadline:
        o = ngql_raw(ctx, "SHOW HOSTS;")
        if re.search(r'"127\.0\.0\.1"\s*\|\s*9779\s*\|\s*"ONLINE"', o):
            return
        if "Got " in o or "Empty set" in o:      # graphd answers: (re)register storaged until it is ONLINE
            ngql_raw(ctx, 'ADD HOSTS "127.0.0.1":9779;')
        time.sleep(2)
    raise SystemExit("harness: NebulaGraph storaged never came ONLINE (300s)")


def ngql_raw(ctx, stmts):
    r = ctx.docker("run", "--rm", ctx.nebula, f"vesoft/nebula-console:{U.NEBULA_VERSION}", "-addr", "127.0.0.1",
                   "-port", "9669", "-u", "root", "-p", "nebula", "-e", stmts, timeout=120)
    return r.stdout + r.stderr


def check_ngql(b, spec, ctx, out):
    if not ctx.live:
        out["deferred"].append(f"NebulaGraph {U.NEBULA_VERSION} execution (no offline nGQL parser)")
        return []
    nebula_up(ctx)
    text = apply_subst(b.text, spec.get("subst"))
    errs = []
    for stmt in U.NGQL_SETUP.get(spec.get("fixture", ""), []):
        if stmt == "SLEEP":      # schema changes reach graphd/storaged on the next heartbeats
            time.sleep(4)
            continue
        o = ngql_raw(ctx, stmt)
        if "[ERROR" in o:
            return [(b.first_line, f"harness nGQL fixture failed: {stmt}: {o.strip()[-300:]}")]
    prefix = spec.get("use", "")
    for start, stmt in split_semicolon(text):
        stmt = " ".join(stmt.split())            # one line: the console takes -e as a single line
        if re.match(r"(?i)USE\s+\w+$", stmt):   # each call is a new session: carry the block's USE forward
            prefix = stmt + ";"
        o = ngql_raw(ctx, (prefix + " " if prefix and not stmt.upper().startswith("USE ") else "") + stmt + ";")
        if "[ERROR" in o:
            msg = re.search(r"\[ERROR.*", o).group(0)
            errs.append((b.md_line(start), f"NebulaGraph {U.NEBULA_VERSION}: {msg}"))
        elif spec.get("after_ddl_wait"):
            time.sleep(spec["after_ddl_wait"])
    out["steps"].append(f"executed on NebulaGraph {U.NEBULA_VERSION}")
    return errs


CHECKERS = {"sh": check_sh, "sql": check_sql, "yaml": check_yaml, "json": check_json,
            "dockerfile": check_dockerfile, "hcl": check_hcl, "ngql": check_ngql}


# ─────────────────────────────────────────────────────────────── inventory ──
def portability(text):
    """Bug-class matches in shell text, with comments stripped (a comment may name the bad form)."""
    code = "\n".join(re.sub(r"(^|\s)#.*$", "", ln) for ln in text.split("\n"))
    return [msg for rx, msg in PORTABILITY if rx.search(code)]


def hook_scripts():
    return sorted((CLAUDE / "hooks").glob("*.sh"))


def inventory(all_b, extra_b=()):
    problems = []
    for path, line in B.untagged_fences(str(SKILLS)):
        problems.append(f".claude/skills/{path}:{line}: code fence without a language tag (use the real one, or text)")
    for b in list(all_b) + list(extra_b):
        if b.lang == "sh":
            for msg in portability(b.text):
                problems.append(f"{b.display}:{b.first_line}: [{b.key}] {msg}")
    for h in hook_scripts():
        for msg in portability(h.read_text(encoding="utf-8")):
            problems.append(f".claude/hooks/{h.name}: {msg}")
    extra_keys = {b.key: b for b in extra_b}
    for k, sk in U.CMD_SKIPS.items():
        b = extra_keys.get(k)
        if b is None:
            problems.append(f"units.CMD_SKIPS has {k}, which no longer exists")
        elif sk.get("anchor") != b.anchor:
            problems.append(f"{b.display}:{b.first_line}: {k} drifted: first line is now {b.anchor!r}, units.CMD_SKIPS pins {sk.get('anchor')!r}")
        elif not str(sk.get("skip", "")).strip():
            problems.append(f"{b.display}:{b.first_line}: {k} is skipped without a reason")
    counts = {}
    for b in all_b:
        counts.setdefault(b.path, {}).setdefault(b.lang, 0)
        counts[b.path][b.lang] += 1
    for path, fam in sorted(counts.items()):
        exp = U.EXPECTED.get(path)
        if exp is None:
            problems.append(f".claude/skills/{path}: has {fam} in-scope block(s) but is not in units.EXPECTED")
            continue
        for lang in set(fam) | set(exp):
            if fam.get(lang, 0) != exp.get(lang, 0):
                problems.append(f".claude/skills/{path}: {fam.get(lang, 0)} {lang} block(s), units.EXPECTED says {exp.get(lang, 0)} — re-check the config")
    for path in U.EXPECTED:
        if path not in counts:
            problems.append(f".claude/skills/{path}: units.EXPECTED lists it but it has no in-scope blocks (moved/deleted?)")
    keys = set()
    for b in all_b:
        keys.add(b.key)
        spec = U.BLOCKS.get(b.key)
        loc = f"{b.display}:{b.first_line}"
        if spec is None:
            problems.append(f"{loc}: {b.key} ({b.info}) is neither checked nor skipped — add it to units.BLOCKS")
            continue
        if spec.get("anchor") != b.anchor:
            problems.append(f"{loc}: {b.key} drifted: first line is now {b.anchor!r}, units.py pins {spec.get('anchor')!r}")
        if "skip" in spec:
            if not str(spec["skip"]).strip():
                problems.append(f"{loc}: {b.key} is skipped without a reason")
        elif b.lang == "sql" and spec.get("check") not in ("pg", "mysql", "sqlite"):
            problems.append(f"{loc}: {b.key}: sql blocks need check = pg | mysql | sqlite")
    for k in U.BLOCKS:
        if k not in keys:
            problems.append(f"units.BLOCKS has {k}, which no longer exists")
    return problems


# ─────────────────────────────────────────────────────────────────── main ──
def require_tools(args, fams):
    need = {"sh": ["shellcheck"], "yaml": ["actionlint"], "dockerfile": ["hadolint"], "hcl": []}
    missing = []
    for fam in fams:
        for t in need.get(fam, []):
            if not shutil.which(t):
                missing.append(t)
    if "hcl" in fams and not tf_bin():
        missing.append("terraform or tofu")
    if "yaml" in fams and run([DOCKER, "compose", "version"]).returncode:
        missing.append("docker compose (CLI only; no daemon needed)")
    if args.live:
        if "yaml" in fams and not shutil.which("kubeconform"):
            missing.append("kubeconform")
        if "yaml" in fams and not shutil.which("golangci-lint"):
            missing.append("golangci-lint")
        if run([DOCKER, "info"]).returncode:
            missing.append("a running Docker daemon (--live)")
    if missing:
        print("run.sh: missing tools: " + ", ".join(sorted(set(missing))), file=sys.stderr)
        print("  brew install shellcheck actionlint hadolint opentofu kubeconform golangci-lint; Docker Desktop", file=sys.stderr)
        sys.exit(2)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--live", action="store_true", help="also run what needs Docker / the network")
    ap.add_argument("--only", nargs="*", default=[], help="only blocks whose key contains one of these")
    ap.add_argument("--family", nargs="*", default=[], choices=FAMILIES)
    ap.add_argument("--keep", action="store_true", help="keep the work directory")
    ap.add_argument("--inventory-only", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--json-report", help="write per-block results (steps run, deferred, failures) to this file")
    args = ap.parse_args()

    all_b = B.all_blocks(str(SKILLS))
    extra_b = [b for t in EXTRA_SH_TREES for b in B.tree_blocks(str(CLAUDE), t)]
    problems = inventory(all_b, extra_b)
    if args.list:
        for b in all_b:
            spec = U.BLOCKS.get(b.key, {})
            print(f"{b.key}\t{b.display}:{b.first_line}\t{spec.get('check') or ('skip: ' + spec['skip'] if 'skip' in spec else '?')}")
    if problems:
        print("INVENTORY FAILED:")
        for p in problems:
            print("  " + p)
        sys.exit(1)
    by_fam = {}
    for b in all_b:
        by_fam[b.lang] = by_fam.get(b.lang, 0) + 1
    print("inventory OK: " + ", ".join(f"{k} {v}" for k, v in sorted(by_fam.items())) + f" ({len(all_b)} blocks in {len(U.EXPECTED)} files)"
          f"; commands+agents: {len(extra_b)} bash blocks ({len(U.CMD_SKIPS)} skipped with a reason); no untagged fences;"
          f" portability lint clean (+ {len(hook_scripts())} hook scripts)")
    if args.inventory_only or args.list:
        return 0

    fams = args.family or list(FAMILIES)
    sel = [b for b in all_b + extra_b if b.lang in fams and (not args.only or any(o in b.key for o in args.only))]
    require_tools(args, {b.lang for b in sel})
    tmp = Path(tempfile.mkdtemp(prefix="config-packs-"))
    ctx = Ctx(args, tmp)
    ctx.blocks_by_key = {b.key: b for b in all_b}
    U.bind(ctx)
    failed, stats, report = 0, {}, []
    try:
        for b in sel:
            spec = U.BLOCKS.get(b.key) or U.CMD_SKIPS.get(b.key) or {"tree": True}
            st = stats.setdefault(b.lang, {"checked": 0, "skipped": 0, "executed": 0, "live-only": 0, "failed": 0})
            loc = f"{b.display}:{b.first_line}"
            if "skip" in spec:
                st["skipped"] += 1
                print(f"SKIP {loc} {b.key}: {spec['skip']}")
                report.append({"key": b.key, "path": b.path, "lang": b.lang, "line": b.first_line, "skip": spec["skip"]})
                continue
            out = {"steps": [], "deferred": []}
            try:
                errs = check_sh_tree(b, ctx, out) if spec.get("tree") else CHECKERS[b.lang](b, spec, ctx, out)
            except Finding as f:
                errs = [(b.first_line, str(f))]
            except subprocess.TimeoutExpired as e:
                errs = [(b.first_line, f"timeout: {e.cmd}")]
            if errs:
                failed += 1
                st["failed"] += 1
                for ln, msg in errs:
                    print(f"FAIL {b.display}:{ln}: [{b.key}] {msg}")
                continue
            if out["steps"]:
                st["checked"] += 1
            else:
                st["live-only"] += 1
            if any(s.startswith(("executed", "exec[", "docker build")) for s in out["steps"]):
                st["executed"] += 1
            tail = f"  (live-only: {', '.join(out['deferred'])})" if out["deferred"] else ""
            print(f"PASS {loc} {b.key}: {'; '.join(out['steps']) or '-'}{tail}")
            report.append({"key": b.key, "path": b.path, "lang": b.lang, "line": b.first_line,
                           "steps": out["steps"], "deferred": out["deferred"]})
        if "sh" in fams and not args.only:
            for sn, src, ln, errs, where in run_snippets(ctx):
                st = stats.setdefault("snippets", {"checked": 0, "skipped": 0, "executed": 0, "live-only": 0, "failed": 0})
                rel = src.relative_to(CLAUDE)
                report.append({"snippet": sn["name"], "path": str(rel), "ok": not errs, "where": where})
                if errs:
                    failed += 1
                    st["failed"] += 1
                    for m in errs:
                        print(f"FAIL .claude/{rel}:{ln}: [snippet {sn['name']}] {m}")
                else:
                    st["checked"] += 1
                    st["executed"] += 1
                    print(f"PASS snippet .claude/{rel}:{ln} {sn['name']} ({' + '.join(where)})")
        if ("sql" in fams or "ngql" in fams) and not args.only:
            for cl, path, errs, summary in run_claims(ctx, fams):
                report.append({"claim": cl["name"], "path": path, "ok": not errs, "engine": summary.split(":")[0]})
                st = stats.setdefault("claims", {"checked": 0, "skipped": 0, "executed": 0, "live-only": 0, "failed": 0})
                if errs:
                    failed += 1
                    st["failed"] += 1
                    for ln, msg in errs:
                        print(f"FAIL .claude/skills/{path}:{ln}: [claim] {msg}")
                else:
                    st["checked"] += 1
                    st["executed"] += 1
                    print(f"PASS claim '{cl['name']}' — {summary}")
            if not args.live:
                n = (len(U.CLAIMS) + len(U.MYSQL_CLAIMS) if "sql" in fams else 0) + (len(U.NGQL_CLAIMS) if "ngql" in fams else 0)
                stats.setdefault("claims", {"checked": 0, "skipped": 0, "executed": 0, "live-only": 0, "failed": 0})["live-only"] += n
                print(f"(live-only: {n} PostgreSQL/MySQL/NebulaGraph claims)")
    finally:
        ctx.stop_all()
        if args.json_report:
            Path(args.json_report).write_text(json.dumps({"live": args.live, "failed": failed, "blocks": report,
                                                          "tools": U.tool_versions(ctx)}, indent=1))
        if args.keep:
            print(f"(work directory kept: {tmp})")
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    print("\nsummary (per family: checked / skipped / executed / live-only / failed):")
    for fam in FAMILIES + ("claims", "snippets"):
        if fam in stats:
            s = stats[fam]
            print(f"  {fam:10} {s['checked']:3} checked  {s['skipped']:3} skipped  {s['executed']:3} executed  {s['live-only']:3} live-only  {s['failed']:3} failed")
    tools = U.tool_versions(ctx)
    print("tools: " + "; ".join(tools))
    if failed:
        print(f"\nFAILED: {failed} block(s)/claim(s)")
        return 1
    print("\nALL PASS" + (" (live)" if args.live else " (default run; --live adds Docker/network checks)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
