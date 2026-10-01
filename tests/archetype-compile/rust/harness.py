#!/usr/bin/env python3
# ruff: noqa: E501
# flake8: noqa
"""Compile-check every ```rust block in .claude/skills/backend/archetypes/*.md, plus the skill packs in
units.EXTRA_FILES (languages/rust.md, the axum/actix-web/graphql framework packs, testing/rust-test.md
and the Rust blocks of the shared testing packs) (run via run.sh; run-tests.sh also runs the tests).

What it does, in order, and each step fails the run on its own:
  1. Extracts the ```rust and ```toml blocks from the archetypes at run time (so an edited sample is
     re-verified) and checks each file's block counts against units.py. A count that moved fails, and
     so does any other .claude/skills/**/*.md with a ```rust block that isn't in units.EXTRA_FILES.
  2. Coverage: every Rust block (and every segment of a split block) is compiled by some unit or is
     listed in units.SKIP with a reason. Anything else fails.
  3. Lint: a ``` fence inside a /// or //! doc comment must be ```text or ```ignore. A plain or
     ```rust fence there becomes a doctest that `cargo test` compiles, and a fragment never compiles.
     Also: axum `:param` routes; Dockerfile Rust builders = the pinned toolchain; the Dockerfile
     variants docker-check.py builds (units.DOCKERFILES) still compose and set a numeric USER.
  4. Assembles each unit as a crate of a cargo workspace (units.py says which blocks go in which
     module, plus the glue and harness-only stubs), writes it under target/work, and runs
     `cargo check --all-targets` per unit (tests and benches included) with a shared target dir.
     sqlx macros run offline against the committed .sqlx/ metadata (see prepare-sqlx.sh).
     Errors are mapped back to the archetype file:line they came from.
  5. --run-tests: `cargo test` of each unit with tests (units.Unit.tests) — the samples' own tests plus
     harness smoke tests — when what they need is there (--database-url for #[sqlx::test] / TestApp,
     a Docker daemon for testcontainers); otherwise the unit prints NOT RUN.
  6. Checks every ```toml Cargo manifest in the Rust archetypes: each dependency must be a crate this
     harness compiled against, at a version the doc's requirement accepts, with features that exist;
     [profile.*] / [[bench]] blocks must be accepted by cargo without "unused manifest key".

Prints PASS/FAIL per unit and exits non-zero on any failure.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
# ARCHETYPE_DIR: point the harness at a copy of the archetypes (used to test the harness itself)
ARCH = os.environ.get("ARCHETYPE_DIR") or os.path.join(REPO, ".claude", "skills", "backend", "archetypes")
TARGET = os.environ.get("ARCHETYPE_RUST_TARGET", os.path.join(HERE, "target"))
WORK = os.path.join(TARGET, "work")
SQLX_DIR = os.path.join(HERE, ".sqlx")
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True  # no __pycache__ next to units.py (run-all runs --coverage-only)

import units as cfg  # noqa: E402
from units import B, S, T  # noqa: E402

FENCE = re.compile(r"^(\s*)(`{3,})(.*)$")
BUILD_ONLY = {"tonic-prost-build"}


# ─── extraction ───────────────────────────────────────────────────────────────────────────────────
class Block:
    def __init__(self, file, lang, idx, start, lines):
        self.file, self.lang, self.idx, self.start, self.lines = file, lang, idx, start, lines

    def __repr__(self):
        return f"{self.file}.md {self.lang} #{self.idx} (line {self.start})"


def blocks_of(path):
    """Every fenced block: (lang, first content line number, content lines)."""
    out, cur = [], None
    for i, line in enumerate(open(path, encoding="utf-8").read().split("\n"), 1):
        m = FENCE.match(line)
        if cur is None and m:
            info = m.group(3).strip()
            lang = info.split(",")[0].split()[0].lower() if info else ""
            cur = (m.group(2), lang, i + 1, [])
        elif cur is not None and m and m.group(2) == cur[0] and not m.group(3).strip():
            out.append(cur[1:])
            cur = None
        elif cur is not None:
            cur[3].append(line)
    if cur is not None:
        raise SystemExit(f"{path}: unterminated code fence opened at line {cur[2] - 1}")
    return out


SKILLS = os.path.join(REPO, ".claude", "skills")
RUST_FENCE = re.compile(r"^\s*`{3,}\s*rust\b", re.I)


def unlisted_rust_packs():
    """Every .claude/skills/**/*.md with a ```rust block is an archetype or in units.EXTRA_FILES."""
    if os.environ.get("ARCHETYPE_DIR"):
        return []  # a copied archetype dir (harness self-test): the skill tree isn't the one checked
    out = []
    for base, _dirs, files in os.walk(SKILLS):
        for fn in files:
            path = os.path.join(base, fn)
            rel = os.path.relpath(path, SKILLS)
            if not fn.endswith(".md") or os.path.dirname(path) == ARCH or rel in cfg.EXTRA_FILES:
                continue
            # a plain line scan: other packs' fences are not this harness's to parse (some nest them)
            if any(RUST_FENCE.match(line) for line in open(path, encoding="utf-8")):
                out.append(f".claude/skills/{rel} has ```rust blocks the harness doesn't check: add it to units.EXTRA_FILES")
    return out


def load_blocks():
    """{(file_stem, lang): [Block]} for every archetype file, plus units.EXTRA_FILES (skill packs outside
    backend/archetypes, keyed by their path under .claude/skills without .md, e.g. "languages/rust")."""
    found = {}
    paths = [(fn[:-3], os.path.join(ARCH, fn)) for fn in sorted(os.listdir(ARCH)) if fn.endswith(".md")]
    paths += [(rel[:-3], os.path.join(SKILLS, rel)) for rel in cfg.EXTRA_FILES]
    for stem, path in paths:
        counters = {}
        for lang, start, lines in blocks_of(path):
            if lang in ("rust", "toml", "protobuf", "sql", "dockerfile", "dockerignore"):
                counters[lang] = counters.get(lang, 0) + 1
                found.setdefault((stem, lang), []).append(Block(stem, lang, counters[lang], start, lines))
    return found


# ─── rendering parts ──────────────────────────────────────────────────────────────────────────────
class Ctx:
    def __init__(self, blocks):
        self.blocks = blocks
        self.used = set()  # (file, idx, seg or None)
        self.errors = []

    def block(self, file, idx, lang="rust"):
        lst = self.blocks.get((file, lang), [])
        if not 1 <= idx <= len(lst):
            raise SystemExit(f"units.py references {file}.md {lang} block #{idx}, but the file has {len(lst)}")
        return lst[idx - 1]


def segments(block, split):
    """Split a block at every line matching `split`; segment 0 is what precedes the first match."""
    rx = re.compile(split)
    segs = [[]]
    for k, line in enumerate(block.lines):
        if rx.search(line):
            segs.append([])
        segs[-1].append((block.start + k, line))
    return segs


def render(part, ctx, unit_name):
    """-> [(text, origin)] where origin is 'file.md:LINE' or 'glue' / 'stub:NAME:LINE'."""
    if isinstance(part, T):
        return [(l, f"glue({unit_name})") for l in part.text.strip("\n").split("\n")]
    if isinstance(part, S):
        path = os.path.join(HERE, "stubs", part.name)
        return [(l, f"stub:{part.name}:{i}") for i, l in enumerate(open(path, encoding="utf-8").read().rstrip("\n").split("\n"), 1)]
    assert isinstance(part, B), part
    blk = ctx.block(part.file, part.idx)
    if part.split:
        segs = segments(blk, part.split)
        if part.seg >= len(segs):
            raise SystemExit(f"{blk}: split {part.split!r} gives {len(segs)} segments, units.py wants #{part.seg}")
        lines = segs[part.seg]
        ctx.used.add((part.file, part.idx, part.seg))
    else:
        lines = [(blk.start + k, l) for k, l in enumerate(blk.lines)]
        ctx.used.add((part.file, part.idx, None))
    if part.expect and not any(part.expect in l for _, l in lines):
        ctx.errors.append(f"{blk}: expected to contain {part.expect!r} (units.py) — the block changed; re-check the unit")
    if part.drop_last is not None:
        while lines and not lines[-1][1].strip():
            lines = lines[:-1]
        if not lines or lines[-1][1].strip() != part.drop_last:
            ctx.errors.append(f"{blk}: units.py drops a last line {part.drop_last!r}, but the block ends with "
                              f"{lines[-1][1].strip() if lines else '<nothing>'!r}")
        else:
            lines = lines[:-1]
    for old, new, count in part.subs:
        n = sum(l.count(old) for _, l in lines)
        if n != count:
            ctx.errors.append(f"{blk}: substitution {old!r} matched {n} time(s), units.py expects {count}")
            continue
        lines = [(ln, l.replace(old, new)) for ln, l in lines]
    out = []
    for ln, l in lines:
        for piece in l.split("\n"):
            out.append((piece, f"{part.file}.md:{ln}"))
    return out


# ─── lint: doc-comment fences ─────────────────────────────────────────────────────────────────────
DOC_FENCE = re.compile(r"^\s*//[/!]\s*(`{3,})(.*)$")
SAFE_DOC_LANGS = {"text", "ignore", "rust,ignore", "sh", "bash", "json", "toml", "sql"}


COLON_ROUTE = re.compile(r"\.(route|nest|route_service|nest_service)\(\s*\"[^\"]*/:[A-Za-z_]")


def lint_colon_routes(blocks):
    """axum 0.8 panics when a router is BUILT with a `/:param` segment (`/{param}` since 0.8). cargo
    check can't see it, so a route string with one fails the run."""
    bad = []
    for (file, lang), lst in blocks.items():
        if lang != "rust":
            continue
        for b in lst:
            for k, line in enumerate(b.lines):
                if COLON_ROUTE.search(line):
                    bad.append(f"{file}.md:{b.start + k}: axum 0.8 route with a `:param` segment panics at startup — use `{{param}}`")
    return bad


def lint_doc_fences(blocks):
    bad = []
    for (file, lang), lst in blocks.items():
        if lang != "rust":
            continue
        for b in lst:
            open_ = False
            for k, line in enumerate(b.lines):
                m = DOC_FENCE.match(line)
                if not m:
                    continue
                if not open_:
                    info = m.group(2).strip().replace(" ", "")
                    if info not in SAFE_DOC_LANGS:
                        bad.append(f"{file}.md:{b.start + k}: doc-comment fence ```{info or ''} becomes a doctest "
                                   f"`cargo test` compiles — mark it ```ignore or ```text")
                open_ = not open_
    return bad


# ─── workspace assembly ───────────────────────────────────────────────────────────────────────────
def write_if_changed(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path) and open(path, encoding="utf-8").read() == text:
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def workspace_deps():
    root = tomllib.load(open(os.path.join(HERE, "Cargo.toml"), "rb"))
    return list(root["workspace"]["dependencies"])


def unit_manifest(unit, deps):
    lines = ["[package]", f'name = "{unit.package}"', 'version = "0.0.0"', "edition.workspace = true",
             "rust-version.workspace = true", "publish = false", ""]
    if unit.lib_name:
        lines += ["[lib]", f'name = "{unit.lib_name}"', 'path = "src/lib.rs"', ""]
    for b in unit.bins:
        lines += ["[[bin]]", f'name = "{b}"', f'path = "src/bin/{b}.rs"', ""]
    for b in unit.benches:
        lines += ["[[bench]]", f'name = "{b}"', f'path = "benches/{b}.rs"', "harness = false", ""]
    if unit.features:
        lines.append("[features]")
        lines += [f"{k} = {json.dumps(v)}" for k, v in unit.features.items()]
        lines.append("")
    lines.append("[dependencies]")
    lines += [f"{d} = {{ workspace = true }}" for d in deps if d not in BUILD_ONLY]
    if unit.build_rs:
        lines += ["", "[build-dependencies]"] + [f"{d} = {{ workspace = true }}" for d in deps if d in BUILD_ONLY]
    return "\n".join(lines) + "\n"


def migrations_from_doc(blocks, doc="migration-pattern-rust"):
    """The ```sql migration files of a doc, keyed by their `-- migrations/…` header."""
    out = {}
    for b in blocks.get((doc, "sql"), []):
        head = next((l.strip() for l in b.lines if l.strip()), "")
        m = re.match(r"--\s*migrations/(\S+\.sql)$", head)
        if m:
            out[m.group(1)] = "\n".join(b.lines).strip("\n") + "\n"
    return out


def protos_from_doc(blocks):
    """The ```protobuf files of grpc-pattern.md, keyed by their `// proto/…` header, with the harness
    patches from units.PROTO_PATCHES applied (each one only when its line is missing)."""
    out = {}
    for b in blocks.get(("grpc-pattern", "protobuf"), []):
        head = next((l.strip() for l in b.lines if l.strip()), "")
        m = re.match(r"//\s*proto/(\S+\.proto)$", head)
        if m:
            text = "\n".join(b.lines).strip("\n") + "\n"
            for fname, after, line, _why in cfg.PROTO_PATCHES:
                if m.group(1).endswith(fname) and line not in text:
                    text = text.replace(after, after + "\n" + line, 1)
            out[m.group(1)] = text
    return out


def assemble(ctx, only):
    deps = workspace_deps()
    os.makedirs(WORK, exist_ok=True)
    shutil.copyfile(os.path.join(HERE, "Cargo.toml"), os.path.join(WORK, "Cargo.toml"))
    shutil.copyfile(os.path.join(HERE, "rust-toolchain.toml"), os.path.join(WORK, "rust-toolchain.toml"))
    lock = os.path.join(HERE, "Cargo.lock")
    if os.path.exists(lock):
        shutil.copyfile(lock, os.path.join(WORK, "Cargo.lock"))
    units_dir = os.path.join(WORK, "units")
    wanted = {u.name for u in cfg.UNITS}
    if os.path.isdir(units_dir):
        for d in os.listdir(units_dir):
            if d not in wanted:
                shutil.rmtree(os.path.join(units_dir, d))
    srcmap = {}
    protos = protos_from_doc(ctx.blocks)
    for unit in cfg.UNITS:
        udir = os.path.join(units_dir, unit.name)
        keep = {"Cargo.toml"}
        write_if_changed(os.path.join(udir, "Cargo.toml"), unit_manifest(unit, deps))
        for rel, parts in unit.files.items():
            lines = []
            for p in parts:
                lines += render(p, ctx, unit.name)
                lines.append(("", "glue"))
            text = "\n".join(l for l, _ in lines).rstrip("\n") + "\n"
            write_if_changed(os.path.join(udir, rel), text)
            srcmap[os.path.realpath(os.path.join(udir, rel))] = [o for _, o in lines]
            keep.add(rel)
        if unit.migrations:
            for name, sql in migrations_from_doc(ctx.blocks, cfg.SCHEMAS[unit.schema]["migrations"]).items():
                write_if_changed(os.path.join(udir, "migrations", name), sql)
                keep.add(os.path.join("migrations", name))
        if unit.protos:
            for name, text in protos.items():
                write_if_changed(os.path.join(udir, "proto", name), text)
                keep.add(os.path.join("proto", name))
        # drop files a previous run generated that this config no longer produces
        for base, _dirs, files in os.walk(udir):
            for fn in files:
                rel = os.path.relpath(os.path.join(base, fn), udir)
                if rel not in keep:
                    os.remove(os.path.join(base, fn))
    return srcmap


# ─── cargo ────────────────────────────────────────────────────────────────────────────────────────
def cargo_env(prepare_url=None):
    env = dict(os.environ)
    env["CARGO_TARGET_DIR"] = os.path.join(TARGET, "prepare" if prepare_url else "cargo")
    env["CARGO_TERM_COLOR"] = "never"
    env["SQLX_OFFLINE_DIR"] = SQLX_DIR
    if prepare_url:
        env["DATABASE_URL"] = prepare_url
        env["SQLX_OFFLINE"] = "false"
    else:
        env["SQLX_OFFLINE"] = "true"
        env.pop("DATABASE_URL", None)
    return env


def origin_of(srcmap, file_name, line):
    path = os.path.realpath(file_name if os.path.isabs(file_name) else os.path.join(WORK, file_name))
    origins = srcmap.get(path)
    if origins and 1 <= line <= len(origins):
        return origins[line - 1]
    return None


def registry_packages(lock_path):
    """{(name, version)} of the crates.io packages in a Cargo.lock (workspace members excluded)."""
    if not os.path.exists(lock_path):
        return set()
    lock = tomllib.load(open(lock_path, "rb"))
    return {(p["name"], p["version"]) for p in lock.get("package", []) if "registry" in p.get("source", "")}


def unit_database_url(base_url, unit):
    """The unit's schema lives in its own database (archetype_<schema>) on the prepare server."""
    return base_url.rsplit("/", 1)[0] + f"/archetype_{unit.schema}"


def docker_available():
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def run_unit_tests(unit, database_url):
    """cargo test for one unit. Returns (ok, summary, output). DB units get DATABASE_URL = the server's
    maintenance database: #[sqlx::test] and the TestApp helpers create their own databases on it."""
    env = cargo_env()
    if database_url:
        env["DATABASE_URL"] = database_url
    proc = subprocess.run(["cargo", "test", "-p", unit.package, "--all-features", "--no-fail-fast"] + unit.test_args,
                          cwd=WORK, env=env, capture_output=True, text=True)
    out = proc.stdout + proc.stderr
    passed = sum(int(n) for n in re.findall(r"test result: \w+\. (\d+) passed", out))
    failed = sum(int(n) for n in re.findall(r"(\d+) failed;", out))
    ignored = sum(int(n) for n in re.findall(r"(\d+) ignored;", out))
    return proc.returncode == 0 and failed == 0, f"{passed} passed, {failed} failed, {ignored} ignored", out


def check_unit(unit, srcmap, env, verbose):
    # Not --locked: a new unit adds a workspace member to the lock. Registry versions are compared with
    # the committed Cargo.lock after the run instead (main()).
    cmd = ["cargo", "check", "-p", unit.package, "--all-targets", "--all-features", "--message-format=json"]
    proc = subprocess.run(cmd, cwd=WORK, env=env, capture_output=True, text=True)
    errors, warnings = [], []
    for raw in proc.stdout.splitlines():
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if msg.get("reason") != "compiler-message":
            continue
        m = msg["message"]
        if m["level"] not in ("error", "warning") or m.get("message", "").startswith("aborting due to"):
            continue
        spans = [s for s in m.get("spans", []) if s.get("is_primary")] or m.get("spans", [])
        where = ""
        if spans:
            s = spans[0]
            # a span inside a macro (format!, sqlx::query!) — follow the expansion to the call site
            while origin_of(srcmap, s["file_name"], s["line_start"]) is None and s.get("expansion"):
                s = s["expansion"]["span"]
            origin = origin_of(srcmap, s["file_name"], s["line_start"])
            where = f"{origin or s['file_name']}  [{os.path.relpath(os.path.join(WORK, s['file_name']), WORK) if not os.path.isabs(s['file_name']) else s['file_name']}:{s['line_start']}]"
        entry = (m["level"], m.get("message", ""), where, m.get("rendered", ""))
        bucket = errors if m["level"] == "error" else warnings
        if not any(e[1:3] == entry[1:3] for e in bucket):  # lib and lib-test report the same error twice
            bucket.append(entry)
    ok = proc.returncode == 0 and not errors
    return ok, errors, warnings, proc


# ─── toml manifests ───────────────────────────────────────────────────────────────────────────────
def parse_version(v):
    parts = [int(x) for x in re.findall(r"\d+", v.split("-")[0].split("+")[0])[:3]]
    return tuple(parts + [0] * (3 - len(parts))), len(parts)


def req_matches(req, version):
    """Cargo requirement semantics for the forms the docs use: X, X.Y, X.Y.Z, ^…, ~…, =…, comma lists."""
    ver, _ = parse_version(version)
    for clause in req.split(","):
        clause = clause.strip()
        m = re.match(r"^(\^|~|=|>=|<=|>|<)?\s*([\d.]+(?:-[\w.]+)?)$", clause)
        if not m:
            return False
        op, base = m.group(1) or "^", m.group(2)
        bv, n = parse_version(base)
        if op == "=":
            ok = ver == bv
        elif op == ">=":
            ok = ver >= bv
        elif op == ">":
            ok = ver > bv
        elif op == "<=":
            ok = ver <= bv
        elif op == "<":
            ok = ver < bv
        elif op == "~":
            ok = ver >= bv and ver[: max(n, 1) if n < 3 else 2] == bv[: max(n, 1) if n < 3 else 2]
        else:  # caret
            if bv[0] > 0 or n == 1:
                ok = ver >= bv and ver[0] == bv[0]
            elif bv[1] > 0 or n == 2:
                ok = ver >= bv and ver[:2] == bv[:2]
            else:
                ok = ver == bv
        if not ok:
            return False
    return True


def resolved_packages(env):
    """{crate: (version, set(features))} for every direct workspace dependency, from cargo metadata."""
    proc = subprocess.run(["cargo", "metadata", "--format-version", "1", "--locked"], cwd=WORK, env=env,
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit("cargo metadata failed:\n" + proc.stderr)
    meta = json.loads(proc.stdout)
    by_id = {p["id"]: p for p in meta["packages"]}
    members = set(meta["workspace_members"])
    out = {}
    for node in meta["resolve"]["nodes"]:
        if node["id"] not in members:
            continue
        for dep in node["deps"]:
            p = by_id[dep["pkg"]]
            out[p["name"]] = (p["version"], set(p["features"]) | {d["rename"] or d["name"] for d in p["dependencies"] if d.get("optional")})
    return out


def check_deps(doc, where_prefix, resolved):
    """Every dependency line must name a crate the harness compiled against, with a requirement that
    accepts the checked version, and features that exist in it."""
    failures = []
    for table in ("dependencies", "dev-dependencies", "build-dependencies"):
        for name, spec in doc.get(table, {}).items():
            req = spec if isinstance(spec, str) else spec.get("version")
            feats = [] if isinstance(spec, str) else spec.get("features", [])
            where = f"{where_prefix} [{table}] {name}"
            if name not in resolved:
                failures.append(f"{where}: not a crate this harness compiled against (add it to Cargo.toml)")
                continue
            ver, known = resolved[name]
            if not req:
                failures.append(f"{where}: no version requirement")
            elif not req_matches(req, ver):
                failures.append(f'{where} = "{req}" does not accept {ver}, the version the samples were checked with')
            missing = [f for f in feats if f not in known]
            if missing:
                failures.append(f"{where}: feature(s) {missing} do not exist in {name} {ver}")
    return failures


def pinned_toolchain():
    return tomllib.load(open(os.path.join(HERE, "rust-toolchain.toml"), "rb"))["toolchain"]["channel"]


def check_dockerfile_toolchain(blocks):
    """Builder = toolchain file: every Rust builder in a *-rust.md Dockerfile is the pinned version."""
    pinned, failures, seen = pinned_toolchain(), [], 0
    for (file, lang), lst in sorted(blocks.items()):
        if lang != "dockerfile" or not file.endswith("-rust"):
            continue
        for b in lst:
            text = "\n".join(b.lines)
            args = re.findall(r"^\s*ARG\s+RUST_VERSION=(\S+)", text, re.M)
            for k, line in enumerate(b.lines):
                m = re.match(r"^\s*FROM\s+rust:(\S+)", line)
                if not m:
                    continue
                seen += 1
                tag = m.group(1)
                where = f"{file}.md:{b.start + k}"
                if tag.startswith("${RUST_VERSION}"):
                    if not args:
                        failures.append(f"{where}: FROM rust:${{RUST_VERSION}} with no ARG RUST_VERSION default in the block")
                    continue
                if not re.match(re.escape(pinned) + r"($|-)", tag):
                    failures.append(f"{where}: FROM rust:{tag}, but the samples are checked with Rust {pinned}")
            for v in args:
                if v != pinned:
                    failures.append(f"{file}.md:{b.start}: ARG RUST_VERSION={v}, but the samples are checked with Rust {pinned}")
    # ...and the docs' rust-toolchain.toml blocks name the same channel
    for (file, idx), kind in cfg.TOML.items():
        if kind != "toolchain":
            continue
        lst = blocks.get((file, "toml"), [])
        if idx > len(lst):
            continue  # the block-count check reports it
        channel = tomllib.loads("\n".join(lst[idx - 1].lines)).get("toolchain", {}).get("channel")
        if channel != pinned:
            failures.append(f"{lst[idx - 1]}: rust-toolchain.toml channel = {channel!r}, but the samples are "
                            f"checked with {pinned!r} (tests/archetype-compile/rust/rust-toolchain.toml)")
    return failures, seen


def block_text(blocks, doc, lang, idx):
    lst = blocks.get((doc, lang), [])
    if not 1 <= idx <= len(lst):
        raise ValueError(f"{doc}.md has {len(lst)} ```{lang} block(s); units.py wants #{idx}")
    return "\n".join(lst[idx - 1].lines).strip("\n") + "\n"


def docker_variants(blocks):
    """{name: Dockerfile text} for units.DOCKERFILES (docker-check.py builds them), and the problems
    found composing them — checked on every run, so a doc edit that breaks a variant fails cheaply."""
    out, problems = {}, []
    try:
        frag_doc, frag_idx = cfg.DOCKER_FRAGMENT
        frag = block_text(blocks, frag_doc, "dockerfile", frag_idx).split("\n")
        fragment = "\n".join(frag[next(i for i, l in enumerate(frag) if l.startswith("RUN ")):]).strip("\n")
    except (ValueError, StopIteration) as e:
        return out, [f"units.DOCKER_FRAGMENT: {e or 'no RUN line'}"]
    for name, (doc, idx, subs) in cfg.DOCKERFILES.items():
        try:
            text = block_text(blocks, doc, "dockerfile", idx)
        except ValueError as e:
            problems.append(f"units.DOCKERFILES[{name!r}]: {e}")
            continue
        for old, new, count in subs or []:
            n = text.count(old)
            if n != count:
                problems.append(f"units.DOCKERFILES[{name!r}]: {old!r} matched {n} time(s) in {doc}.md dockerfile #{idx}, expected {count}")
            text = text.replace(old, new.replace("@FRAGMENT@", fragment))
        if not re.search(r"^USER\s+\d+(:\d+)?\s*$", text, re.M):
            problems.append(f"{doc}.md dockerfile #{idx} ({name}): no numeric USER line (non-root, Kubernetes runAsNonRoot)")
        out[name] = text
    return out, problems


def check_manifests(blocks, env):
    failures, notes = [], []
    resolved = resolved_packages(env)
    configured = cfg.TOML
    seen = set()
    for (file, lang), lst in sorted(blocks.items()):
        if lang != "toml" or not file.endswith("-rust"):
            continue
        for b in lst:
            key = (file, b.idx)
            seen.add(key)
            kind = configured.get(key)
            if kind is None:
                failures.append(f"{b}: toml block not listed in units.TOML (say 'deps', 'profile', 'toolchain' or a skip reason)")
                continue
            if isinstance(kind, tuple):
                notes.append(f"{b}: not checked — {kind[1]}")
                continue
            text = "\n".join(b.lines)
            try:
                doc = tomllib.loads(text)
            except tomllib.TOMLDecodeError as e:
                failures.append(f"{b}: invalid TOML: {e}")
                continue
            failures += check_deps(doc, f"{file}.md:{b.start}", resolved)
            if kind == "profile":
                # [profile.*] / [features] / [[bench]]: cargo must accept the whole block as a manifest
                scratch = os.path.join(TARGET, "manifest-check", f"{file}-{b.idx}")
                shutil.rmtree(scratch, ignore_errors=True)
                os.makedirs(os.path.join(scratch, "src"))
                open(os.path.join(scratch, "src", "lib.rs"), "w").close()
                for bench in doc.get("bench", []):
                    os.makedirs(os.path.join(scratch, "benches"), exist_ok=True)
                    open(os.path.join(scratch, "benches", bench["name"] + ".rs"), "w").write("fn main() {}\n")
                manifest = '[package]\nname = "manifest-check"\nversion = "0.0.0"\nedition = "2024"\n\n[workspace]\n\n' + text + "\n"
                open(os.path.join(scratch, "Cargo.toml"), "w").write(manifest)
                proc = subprocess.run(["cargo", "metadata", "--no-deps", "--format-version", "1", "--offline"],
                                      cwd=scratch, env=env, capture_output=True, text=True)
                if proc.returncode != 0 or "unused manifest key" in proc.stderr:
                    failures.append(f"{b}: cargo rejects it: {proc.stderr.strip()[:400]}")
    for key in configured:
        if key not in seen:
            failures.append(f"units.TOML lists {key[0]}.md toml #{key[1]}, which no longer exists")
    return failures, notes


# ─── main ─────────────────────────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--update-lock", action="store_true", help="resolve without --locked and copy Cargo.lock back")
    ap.add_argument("--prepare-sqlx", metavar="DATABASE_URL", help="regenerate .sqlx/ against this database")
    ap.add_argument("--coverage-only", action="store_true", help="steps 1-3 only (no cargo)")
    ap.add_argument("--print-schema", nargs="?", const="default", metavar="SCHEMA",
                    help="print the SQL prepare-sqlx.sh applies for a schema (units.SCHEMAS), and exit")
    ap.add_argument("--list-schemas", action="store_true", help="print the schema names, and exit")
    ap.add_argument("--run-tests", action="store_true",
                    help="after compiling, run `cargo test` for the units that have tests (units.Unit.tests)")
    ap.add_argument("--database-url", metavar="URL",
                    help="with --run-tests: a Postgres server for the DB-backed tests (else they are not run)")
    ap.add_argument("--only", nargs="*", help="check only these units")
    ap.add_argument("-v", "--verbose", action="store_true", help="print full rustc diagnostics and warnings")
    args = ap.parse_args()

    blocks = load_blocks()
    problems = []

    if args.list_schemas:
        print("\n".join(cfg.SCHEMAS))
        return 0
    if args.print_schema:
        schema = cfg.SCHEMAS[args.print_schema]
        migrations = migrations_from_doc(blocks, schema["migrations"])
        if not migrations:
            raise SystemExit(f"schema {args.print_schema}: {schema['migrations']}.md has no `-- migrations/…` sql blocks")
        for name in sorted(migrations):
            if name.endswith(".down.sql") or name in schema.get("exclude", {}):
                continue
            print(f"-- ===== {schema['migrations']}.md: {name}\n{migrations[name]}")
        for name, why in sorted(schema.get("exclude", {}).items()):
            if name not in migrations:
                raise SystemExit(f"schema {args.print_schema} excludes {name}, which {schema['migrations']}.md no longer has")
            print(f"-- excluded {name}: {why}")
        if schema.get("extra"):
            print("-- ===== harness-only tables (no archetype defines them)\n"
                  + open(os.path.join(HERE, "stubs", schema["extra"]), encoding="utf-8").read())
        return 0

    # 1. counts
    for file, n in sorted(cfg.EXPECTED.items()):
        have = len(blocks.get((file, "rust"), []))
        if have != n:
            problems.append(f"{file}.md has {have} rust blocks; units.py was written for {n}. Update units.py "
                            f"(placement, skips) for the added/removed block, then re-run.")
    for (file, lang), lst in blocks.items():
        if lang == "rust" and file not in cfg.EXPECTED:
            problems.append(f"{file}.md has {len(lst)} rust block(s) and no entry in units.EXPECTED")
    problems += unlisted_rust_packs()
    ntoml = {}
    for (file, idx) in cfg.TOML:
        ntoml[file] = max(ntoml.get(file, 0), idx)
    for (file, lang), lst in blocks.items():
        if lang == "toml" and file.endswith("-rust") and len(lst) != ntoml.get(file, 0):
            problems.append(f"{file}.md has {len(lst)} toml block(s); units.TOML covers {ntoml.get(file, 0)}")
    if problems:
        print("FAIL block counts\n  " + "\n  ".join(problems))
        return 1

    # 2. assemble (records which blocks/segments are used) + coverage. --coverage-only assembles into a
    #    throwaway directory: it must not need (or touch) the cargo workspace under target/.
    global WORK
    ctx = Ctx(blocks)
    if args.coverage_only:
        WORK = tempfile.mkdtemp(prefix="archetype-rust-")
        try:
            srcmap = assemble(ctx, args.only)
        finally:
            shutil.rmtree(WORK, ignore_errors=True)
    else:
        srcmap = assemble(ctx, args.only)
    if ctx.errors:
        problems += ctx.errors
    for (file, lang), lst in sorted(blocks.items()):
        if lang != "rust":
            continue
        for b in lst:
            if (file, b.idx, None) in ctx.used:
                continue
            split = next((p for u in cfg.UNITS for parts in u.files.values() for p in parts
                          if isinstance(p, B) and p.file == file and p.idx == b.idx and p.split), None)
            if split is not None:
                for k, seg in enumerate(segments(b, split.split)):
                    if (file, b.idx, k) in ctx.used or not any(l.strip() for _, l in seg):
                        continue
                    if (file, b.idx, k) not in cfg.SKIP:
                        problems.append(f"{b} segment {k} (line {seg[0][0]}) is neither compiled nor in units.SKIP")
                continue
            if (file, b.idx) not in cfg.SKIP:
                problems.append(f"{b} is neither compiled by a unit nor listed in units.SKIP with a reason")
    for key, why in cfg.SKIP.items():
        if not why or len(why) < 15:
            problems.append(f"units.SKIP {key}: give a real reason")

    # 3. lint: doctest-shaped doc-comment fences; Rust Dockerfile builders = the pinned toolchain
    problems += lint_doc_fences(blocks)
    problems += lint_colon_routes(blocks)
    docker_problems, n_builders = check_dockerfile_toolchain(blocks)
    problems += docker_problems
    problems += docker_variants(blocks)[1]

    total_rust = sum(len(l) for (f, lang), l in blocks.items() if lang == "rust")
    skipped = sorted(cfg.SKIP.items())
    structure_ok = not problems
    if problems:
        print("FAIL structure (counts / coverage / units.py / doc-comment fences)\n  " + "\n  ".join(problems))
        if not args.only or args.coverage_only:
            return 1
        print("     (--only: compiling the selected units anyway; the run still fails)")
    else:
        print(f"ok   structure: {total_rust} rust blocks in {len(cfg.EXPECTED)} files; all compiled or skipped "
              f"({len(skipped)} skip entries); no doctest-shaped doc-comment fences or axum `:param` routes; "
              f"{n_builders} Dockerfile Rust builders = toolchain {pinned_toolchain()}")
    if args.coverage_only:
        return 0

    if shutil.which("cargo") is None:
        print("FAIL cargo not found (run.sh puts ~/.cargo/bin on PATH; install rustup first)")
        return 2

    # 4. compile
    env = cargo_env(args.prepare_sqlx)
    if args.prepare_sqlx:
        if not args.only:  # a full prepare rebuilds the whole set; --only adds to it
            shutil.rmtree(SQLX_DIR, ignore_errors=True)
        os.makedirs(SQLX_DIR, exist_ok=True)
        # the macros write metadata only when they expand: make cargo re-expand every unit
        for unit in cfg.UNITS:
            if not args.only or unit.name in args.only:
                subprocess.run(["cargo", "clean", "-p", unit.package], cwd=WORK, env=env, capture_output=True)
    if args.update_lock:
        proc = subprocess.run(["cargo", "generate-lockfile"], cwd=WORK, env=env)
        if proc.returncode != 0:
            return 1
        shutil.copyfile(os.path.join(WORK, "Cargo.lock"), os.path.join(HERE, "Cargo.lock"))
    pinned = registry_packages(os.path.join(HERE, "Cargo.lock"))
    if not pinned:
        print("FAIL no committed Cargo.lock — run with --update-lock once")
        return 1
    rustc = subprocess.run(["rustc", "--version"], cwd=WORK, capture_output=True, text=True).stdout.strip()
    print(f"     toolchain: {rustc}; sqlx macros: {'ONLINE against ' + args.prepare_sqlx if args.prepare_sqlx else 'offline (.sqlx/)'}")
    results = []
    selected = [u for u in cfg.UNITS if not args.only or u.name in args.only]
    for unit in selected:
        if args.prepare_sqlx:  # each schema is its own database on the prepare server
            env["DATABASE_URL"] = unit_database_url(args.prepare_sqlx, unit)
        ok, errors, warnings, proc = check_unit(unit, srcmap, env, args.verbose)
        results.append((unit, ok))
        tag = "PASS" if ok else "FAIL"
        print(f"{tag} {unit.name:26} ({len(warnings)} warning{'s' if len(warnings) != 1 else ''}) — {unit.what}")
        if not ok:
            if not errors:
                print("    " + "\n    ".join(proc.stderr.strip().splitlines()[-25:]))
            for level, text, where, rendered in errors:
                print(f"    error: {text}\n      at {where}")
                if args.verbose:
                    print("      " + rendered.replace("\n", "\n      "))
        if args.verbose and warnings:
            for level, text, where, _ in warnings:
                print(f"    warning: {text}  at {where}")

    drift = registry_packages(os.path.join(WORK, "Cargo.lock")) ^ pinned
    if drift:
        print("FAIL dependency resolution differs from the committed Cargo.lock (run --update-lock if intended): "
              + ", ".join(f"{n} {v}" for n, v in sorted(drift)[:12]))
        results.append((None, False))

    # 5. run the tests (--run-tests) of the units that compiled: each when what it needs is there
    test_fail, test_missing = 0, 0
    if args.run_tests:
        print("\ntests (cargo test):")
        have_docker = docker_available()
        compiled = {u.name for u, ok in results if u is not None and ok}
        for unit in selected:
            if unit.tests is None:
                continue
            missing = [need for need, have in (("--database-url", "db" not in unit.tests or args.database_url),
                                               ("a Docker daemon", "docker" not in unit.tests or have_docker)) if not have]
            if unit.name not in compiled or missing:
                test_missing += 1
                why = "did not compile" if unit.name not in compiled else "needs " + " and ".join(missing)
                print(f"NOT RUN {unit.name:23} {why}")
                continue
            ok, summary, out = run_unit_tests(unit, args.database_url if "db" in unit.tests else None)
            test_fail += not ok
            print(f"{'PASS' if ok else 'FAIL'} {unit.name:26} {summary}")
            if not ok or args.verbose:
                shown = r"^test .* \.\.\. |FAILED|panicked at|^error" if args.verbose else r"FAILED|panicked at|^error"
                for line in out.splitlines():
                    if re.search(shown, line):
                        print("    " + line[:300])

    # 6. manifests
    if args.only:
        return 0 if all(ok for _, ok in results) and structure_ok and not test_fail else 1
    man_fail, man_notes = check_manifests(blocks, cargo_env())
    if man_fail:
        print("FAIL toml manifests\n  " + "\n  ".join(man_fail))
    else:
        print("PASS toml manifests (every dependency line resolves to the checked version; profiles accepted)")
    for n in man_notes:
        print("     " + n)

    npass = sum(ok for _, ok in results)
    nfail = len(results) - npass
    print(f"\nunits: {npass} PASS / {nfail} FAIL; {len(skipped)} skipped block(s)/segment(s):")
    for key, why in skipped:
        seg = f" segment {key[2]}" if len(key) == 3 else ""
        print(f"  skip {key[0]}.md rust #{key[1]}{seg}: {why}")
    if args.prepare_sqlx:
        print(f"\n.sqlx/ now has {len(os.listdir(SQLX_DIR))} query file(s)")
    if args.run_tests and test_missing:
        print(f"\n{test_missing} unit(s)' tests NOT RUN (see above): the run is not a full test pass")
    return 0 if nfail == 0 and not man_fail and not test_fail else 1


if __name__ == "__main__":
    sys.exit(main())
