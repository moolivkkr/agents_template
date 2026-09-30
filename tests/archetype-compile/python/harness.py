#!/usr/bin/env python3
"""Compile-check the ```python samples in .claude/skills/backend/archetypes/*.md.

Run through run.sh (it provisions the pinned venv). What happens, deterministically, on every run:

1. Every archetype markdown file is scanned. Each ```python block is extracted with its markdown line
   numbers. A file's block count must equal EXPECTED in units.py; a block's first non-empty line must
   equal the anchor its unit references it by. Either mismatch fails loudly: the doc changed, so the
   config has to be looked at again rather than silently checking the wrong code.
2. Every block must be referenced by a unit, listed in COMMENT_ONLY (verified to hold no code), or
   listed in SKIPS with a reason. Anything else fails.
3. Each unit is assembled into .build/<unit>/ from blocks (+ minimal harness stubs for names a
   fragment deliberately leaves to the reader). A line map ties every generated line back to its
   markdown file and line, so every error is reported at the markdown location.
4. Per unit: pre-steps (e.g. protoc), pyright (standard mode + reportDeprecated) on the files built
   from the unit's own markdown, a runtime import of its modules (every import must resolve against
   the real libraries; a DeprecationWarning raised from sample code fails), an optional smoke script,
   pytest --collect-only or a full run for test samples that need no database, and post-steps.

Stubs never stand in for a library a sample demonstrates: they only provide app-level names (an
Order model, a settings object, a repository) that a fragment assumes exists.
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
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
# ARCHETYPE_DIR: check another copy of the docs (used to prove the harness fails on a bad sample)
ARCH = Path(os.environ.get("ARCHETYPE_DIR") or REPO / ".claude" / "skills" / "backend" / "archetypes")
STUBS = HERE / "stubs"
BUILD = HERE / ".build"

sys.path.insert(0, str(HERE))
import units as cfg  # noqa: E402  (the unit configuration lives next to this file)
from units import MD, B, S, T, Unit  # noqa: E402

FENCE_OPEN = re.compile(r"^```python\s*$")
FENCE_CLOSE = re.compile(r"^```\s*$")
# Anything that looks like a Python fence but isn't the exact form above would be silently ignored,
# so it is an error: normalise the fence or teach the extractor.
FENCE_SUSPECT = re.compile(r"^\s*`{3,}\s*(py|python3?|Python|PYTHON)\b")
PYRIGHT_CMD = shlex.split(os.environ.get("PYRIGHT_CMD", "npx --yes pyright@1.1.414"))


class HarnessError(Exception):
    pass


@dataclass
class Block:
    md: str
    index: int
    first_line: int  # markdown line number (1-based) of the block's first content line
    lines: list[str]

    @property
    def anchor(self) -> str:
        return next((ln.strip() for ln in self.lines if ln.strip()), "")


def extract_other(md_path: Path, lang: str) -> list[Block]:
    """Fenced blocks of another language (read-only inputs such as alembic.ini or .proto files)."""
    lines = md_path.read_text(encoding="utf-8").split("\n")
    out: list[Block] = []
    i = 0
    while i < len(lines):
        if lines[i].rstrip() == "```" + lang:
            j = i + 1
            while j < len(lines) and not FENCE_CLOSE.match(lines[j]):
                j += 1
            out.append(Block(md_path.name, len(out), i + 2, lines[i + 1 : j]))
            i = j + 1
            continue
        i += 1
    return out


def extract(md_path: Path) -> list[Block]:
    lines = md_path.read_text(encoding="utf-8").split("\n")
    blocks: list[Block] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if FENCE_OPEN.match(line):
            start = i + 1
            j = start
            while j < len(lines) and not FENCE_CLOSE.match(lines[j]):
                j += 1
            if j == len(lines):
                raise HarnessError(f"{md_path.name}:{i + 1}: unterminated ```python block")
            blocks.append(Block(md_path.name, len(blocks), start + 1, lines[start:j]))
            i = j + 1
            continue
        if FENCE_SUSPECT.match(line):
            raise HarnessError(
                f"{md_path.name}:{i + 1}: Python fence in a form the extractor doesn't read ({line.strip()!r}); "
                "use exactly ```python at column 0"
            )
        i += 1
    return blocks


# ── assembly ───────────────────────────────────────────────────────────────────────────────────────


@dataclass
class Origin:
    md: str | None  # None → a harness line
    line: int
    where: str  # printable location

    @property
    def is_doc(self) -> bool:
        return self.md is not None


class Assembled:
    """One generated file: its lines and, for each, where it came from."""

    def __init__(self, rel: str) -> None:
        self.rel = rel
        self.lines: list[str] = []
        self.origins: list[Origin] = []

    def add_harness(self, text: str, label: str) -> None:
        for k, ln in enumerate(text.rstrip("\n").split("\n")):
            self.lines.append(ln)
            self.origins.append(Origin(None, k + 1, f"harness:{label}:{k + 1}"))

    def add_block(self, blk: Block, part: B) -> None:
        body = list(blk.lines)
        for old, new in part.subs:
            # Exact whole-line substitution, e.g. give a fragment's class a harness base that declares
            # the collaborators (self._repo, ...) the fragment leaves out. Must match exactly once.
            hits = [k for k, ln in enumerate(body) if ln == old]
            if len(hits) != 1:
                raise HarnessError(f"{blk.md} block #{blk.index}: substitution target {old!r} matched {len(hits)} lines")
            body[hits[0]] = new
        indent = ""
        if part.wrap:
            # Fragment that is only valid inside a function (e.g. a bare `await`): the harness wraps it.
            self.add_harness(part.wrap, f"{self.rel} (wrap)")
            indent = "    "
        for k, ln in enumerate(body):
            self.lines.append((indent + ln) if ln.strip() else ln)
            self.origins.append(Origin(blk.md, blk.first_line + k, f"{blk.md}:{blk.first_line + k}"))
        if part.wrap:
            self.lines.append(indent + "pass")
            self.origins.append(Origin(None, 0, f"harness:{self.rel} (wrap)"))

    def text(self) -> str:
        return "\n".join(self.lines) + "\n"

    def origin(self, line_1based: int) -> Origin:
        if 1 <= line_1based <= len(self.origins):
            return self.origins[line_1based - 1]
        return Origin(None, line_1based, f"{self.rel}:{line_1based}")


class Build:
    def __init__(self, unit: Unit, blocks: dict[str, list[Block]], root: Path) -> None:
        self.unit = unit
        self.blocks = blocks
        self.root = root
        self.files: dict[str, Assembled] = {}

    def block(self, part: B) -> Block:
        if part.md not in self.blocks:
            raise HarnessError(f"unit {self.unit.name}: unknown markdown file {part.md}")
        bl = self.blocks[part.md]
        if part.index >= len(bl):
            raise HarnessError(f"unit {self.unit.name}: {part.md} has no python block #{part.index}")
        blk = bl[part.index]
        if blk.anchor != part.anchor:
            raise HarnessError(
                f"unit {self.unit.name}: {part.md} python block #{part.index} (line {blk.first_line}) "
                f"starts with {blk.anchor!r}, the config expects {part.anchor!r}. The doc changed: re-check "
                "which block this unit should use, then update the anchor in units.py."
            )
        return blk

    def assemble(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root)
        self.root.mkdir(parents=True)
        for rel, parts in self.unit.files.items():
            f = Assembled(rel)
            for n, part in enumerate(parts):
                if isinstance(part, B):
                    if f.lines:
                        f.lines.append("")
                        f.origins.append(Origin(None, 0, f"harness:{rel} (joint)"))
                    f.add_block(self.block(part), part)
                elif isinstance(part, T):
                    f.add_harness(part.text, f"{rel} (text #{n})")
                elif isinstance(part, S):
                    f.add_harness((STUBS / part.path).read_text(encoding="utf-8"), f"stubs/{part.path}")
                elif isinstance(part, MD):
                    other = extract_other(ARCH / part.md, part.lang)
                    if part.index >= len(other) or other[part.index].anchor != part.anchor:
                        raise HarnessError(
                            f"unit {self.unit.name}: {part.md} ```{part.lang} block #{part.index} no longer starts "
                            f"with {part.anchor!r}; update units.py"
                        )
                    blk = other[part.index]
                    for k, ln in enumerate(blk.lines):
                        f.lines.append(ln)
                        f.origins.append(Origin(blk.md, blk.first_line + k, f"{blk.md}:{blk.first_line + k}"))
                else:
                    raise HarnessError(f"unit {self.unit.name}: bad part {part!r}")
            self.files[rel] = f
            dest = self.root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(f.text(), encoding="utf-8")
        # Packages: every directory holding generated .py files gets an __init__.py unless the unit
        # provides one. Never for alembic/ (it would shadow the alembic library).
        for rel in list(self.files):
            parent = Path(rel).parent
            while str(parent) not in (".", ""):
                if parent.parts[0] != "alembic":
                    init = self.root / parent / "__init__.py"
                    if not init.exists():
                        init.write_text("", encoding="utf-8")
                parent = parent.parent
        (self.root / "pytest.ini").write_text(
            "[pytest]\n"
            "pythonpath = .\n"
            "filterwarnings =\n"
            "    error::DeprecationWarning:app\\.\n"
            "    error::DeprecationWarning:tests\\.\n",
            encoding="utf-8",
        )

    def own_files(self) -> list[str]:
        if self.unit.typecheck is not None:
            return list(self.unit.typecheck)
        own = set(self.unit.own)
        return [
            rel
            for rel, parts in self.unit.files.items()
            if rel.endswith(".py") and any(isinstance(p, B) and p.md in own for p in parts)
        ]

    def locate(self, path: str, line: int) -> Origin:
        try:
            rel = str(Path(path).resolve().relative_to(self.root.resolve()))
        except ValueError:
            return Origin(None, line, f"{path}:{line}")
        f = self.files.get(rel)
        return f.origin(line) if f else Origin(None, line, f"{rel}:{line}")

    def annotate(self, text: str) -> str:
        """Append [markdown:line] to every build-path:line reference in tool output."""
        root = str(self.root.resolve())

        def sub(m: re.Match[str]) -> str:
            p, ln = m.group(1), int(m.group(2))
            full = p if os.path.isabs(p) else os.path.join(root, p)
            o = self.locate(full, ln)
            short = p.replace(root + os.sep, "")
            return f"{short}:{ln} [{o.where}]" if o.md else f"{short}:{ln}"

        return re.sub(r"((?:/[^\s:\"']+|[\w./-]+)\.py):(\d+)", sub, text)


# ── checks ─────────────────────────────────────────────────────────────────────────────────────────


@dataclass
class Result:
    unit: str
    ok: bool
    lines: list[str]
    summary: str


def run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None, timeout: int = 900) -> subprocess.CompletedProcess[str]:
    e = dict(os.environ)
    e.update(env or {})
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        return subprocess.run(cmd, cwd=cwd, env=e, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        # A hang is a failure of this unit, not of the whole run
        def text(b: str | bytes | None) -> str:
            return b.decode(errors="replace") if isinstance(b, bytes) else (b or "")

        return subprocess.CompletedProcess(cmd, 124, text(exc.stdout), text(exc.stderr) + f"\nTIMED OUT after {timeout}s")


def fill(cmd: list[str], build: Build) -> list[str]:
    return [c.replace("{py}", sys.executable).replace("{root}", str(build.root)) for c in cmd]


def doc_line(o: Origin) -> str:
    """The markdown line an origin points at ("" for harness lines)."""
    if not o.md:
        return ""
    lines = (ARCH / o.md).read_text(encoding="utf-8").split("\n")
    return lines[o.line - 1] if 0 < o.line <= len(lines) else ""


def check_pyright(build: Build, out: list[str]) -> tuple[bool, str]:
    files = build.own_files()
    if not files:
        return True, "pyright: nothing to check"
    conf = {
        "include": files,
        "pythonVersion": "3.12",
        "typeCheckingMode": "standard",
        "reportDeprecated": "error",
        "reportMissingModuleSource": "none",
        **build.unit.pyright,
    }
    (build.root / "pyrightconfig.json").write_text(json.dumps(conf, indent=2), encoding="utf-8")
    p = run([*PYRIGHT_CMD, "--outputjson", "-p", "pyrightconfig.json", "--pythonpath", sys.executable], build.root)
    try:
        data = json.loads(p.stdout)
    except json.JSONDecodeError:
        out.append("  pyright did not produce JSON:\n" + (p.stdout + p.stderr)[-3000:])
        return False, "pyright: crashed"
    errors = 0
    for d in data.get("generalDiagnostics", []):
        if d["severity"] not in ("error", "warning"):
            continue
        o = build.locate(d["file"], d["range"]["start"]["line"] + 1)
        rule = f" ({d['rule']})" if d.get("rule") else ""
        msg = d["message"].replace("\n", " ")
        ignored = next(
            (why for md, text, code, why in build.unit.pyright_ignore
             if o.md == md and " ".join(d["message"].split()).startswith(text) and code in doc_line(o)),
            None,
        )
        if ignored:
            out.append(f"  {o.where}  IGNORED pyright {d['severity']}: {msg}{rule} — {ignored}")
            continue
        if d["severity"] == "error":
            errors += 1
            out.append(f"  {o.where}  pyright error: {msg}{rule}" + ("" if o.md else "  <- harness line"))
        else:
            out.append(f"  {o.where}  pyright warning: {msg}{rule}")
    return errors == 0, f"pyright: {errors} error(s) in {len(files)} file(s)"


def check_runtime(build: Build, out: list[str]) -> tuple[bool, str]:
    mods = build.unit.imports
    if mods is None:
        mods = [
            rel[:-3].replace("/", ".").removesuffix(".__init__")
            for rel in build.own_files()
            if not rel.startswith(("tests/", "alembic/")) and "/test_" not in rel
        ]
    if not mods and not build.unit.smoke:
        return True, "import: nothing to import"
    spec = {"imports": mods, "smoke": build.unit.smoke or ""}
    with tempfile.NamedTemporaryFile("r", suffix=".json", delete=False) as tf:
        result_path = tf.name
    try:
        p = run([sys.executable, str(HERE / "runtime_check.py"), str(build.root), json.dumps(spec), result_path],
                build.root, build.unit.env, timeout=300)
        try:
            res = json.loads(Path(result_path).read_text() or "{}")
        except json.JSONDecodeError:
            res = {}
    finally:
        os.unlink(result_path)
    if not res:
        out.append("  runtime check crashed:\n" + build.annotate((p.stdout + p.stderr)[-3000:]))
        return False, "import: crashed"
    ok = True
    for err in res.get("errors", []):
        ok = False
        out.append(f"  {err['what']}: {err['type']}: {err['message']}")
        for fr in err["frames"]:
            o = build.locate(fr["file"], fr["line"])
            if o.md or str(build.root) in fr["file"]:
                out.append(f"      at {o.where}: {fr['code']}")
    dep = 0
    for w in res.get("warnings", []):
        o = build.locate(w["filename"], w["lineno"])
        if o.md and w["category"] in ("DeprecationWarning", "PendingDeprecationWarning", "FutureWarning"):
            ok = False
            dep += 1
            out.append(f"  {o.where}  {w['category']}: {w['message']}")
    what = "smoke" if build.unit.smoke else "import"
    n = len(res.get("imported", []))
    return ok, (f"{what}: ok ({n} module(s))" if ok else f"{what}: FAILED")


def check_pytest(build: Build, out: list[str], live: bool) -> tuple[bool, str]:
    mode = build.unit.live if (live and build.unit.live) else build.unit.pytest
    if not mode:
        return True, ""
    args = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-c", "pytest.ini", "--rootdir", "."]
    if mode == "collect":
        args.append("--collect-only")
    args += build.unit.pytest_args
    env = dict(build.unit.env)
    if live and build.unit.live:
        # testcontainers' reaper image isn't needed: the samples stop their containers themselves
        env.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")
    p = run(args, build.root, env, timeout=1800)
    tail = (p.stdout + p.stderr).strip().splitlines()
    last = tail[-1] if tail else ""
    if p.returncode != 0:
        out.append("  pytest output (tail):")
        out.extend("    " + ln for ln in build.annotate("\n".join(tail[-80:])).splitlines())
        return False, f"pytest {mode}: FAILED ({last})"
    return True, f"pytest {mode}: {last}"


def check_steps(build: Build, steps: list[list[str]], out: list[str], label: str) -> tuple[bool, str]:
    for cmd in steps:
        c = fill(cmd, build)
        p = run(c, build.root, build.unit.env)
        if p.returncode != 0:
            out.append(f"  {label} step failed: {' '.join(shlex.quote(x) for x in c)}")
            out.extend("    " + ln for ln in build.annotate((p.stdout + p.stderr)[-4000:]).splitlines())
            return False, f"{label}: FAILED"
    return True, (f"{label}: {len(steps)} step(s) ok" if steps else "")


def check_unit(unit: Unit, blocks: dict[str, list[Block]], live: bool) -> Result:
    build = Build(unit, blocks, BUILD / unit.name)
    out: list[str] = []
    build.assemble()
    parts: list[str] = []
    ok = True
    for fn in (
        lambda: check_steps(build, unit.pre, out, "pre"),
        lambda: check_pyright(build, out),
        lambda: check_runtime(build, out),
        lambda: check_pytest(build, out, live),
        lambda: check_steps(build, unit.post, out, "post"),
    ):
        good, s = fn()
        ok = ok and good
        if s:
            parts.append(s)
        if not good and s.startswith("pre"):
            break
    return Result(unit.name, ok, out, "; ".join(parts))


# ── coverage ───────────────────────────────────────────────────────────────────────────────────────


def load_blocks() -> tuple[dict[str, list[Block]], list[str]]:
    problems: list[str] = []
    blocks: dict[str, list[Block]] = {}
    for md in sorted(ARCH.glob("*.md")):
        try:
            bl = extract(md)
        except HarnessError as exc:
            problems.append(str(exc))
            continue
        want = cfg.EXPECTED.get(md.name, 0)
        if len(bl) != want:
            problems.append(
                f"{md.name}: {len(bl)} python block(s), units.py EXPECTED says {want}. The doc changed: "
                "add/re-map the blocks in units.py (and re-run) before trusting this check."
            )
        if bl:
            blocks[md.name] = bl
    for name in cfg.EXPECTED:
        if not (ARCH / name).exists():
            problems.append(f"units.py EXPECTED lists {name}, which no longer exists")
    return blocks, problems


def coverage(blocks: dict[str, list[Block]]) -> tuple[list[str], dict[tuple[str, int], str], int]:
    problems: list[str] = []
    used: set[tuple[str, int]] = set()
    for u in cfg.UNITS:
        for parts in u.files.values():
            for p in parts:
                if isinstance(p, B):
                    used.add((p.md, p.index))
    skipped: dict[tuple[str, int], str] = {}
    for (md, idx, anchor), reason in cfg.SKIPS.items():
        bl = blocks.get(md, [])
        if idx >= len(bl) or bl[idx].anchor != anchor:
            problems.append(f"SKIPS entry {md}#{idx} ({anchor!r}) doesn't match the doc any more")
        skipped[(md, idx)] = reason
    for md, idx, anchor in cfg.COMMENT_ONLY:
        bl = blocks.get(md, [])
        if idx >= len(bl) or bl[idx].anchor != anchor:
            problems.append(f"COMMENT_ONLY entry {md}#{idx} ({anchor!r}) doesn't match the doc any more")
            continue
        code = [ln for ln in bl[idx].lines if ln.strip() and not ln.strip().startswith("#")]
        if code:
            problems.append(f"{md}:{bl[idx].first_line}: COMMENT_ONLY block now contains code ({code[0].strip()!r}); give it a unit")
        skipped[(md, idx)] = "comment-only (no executable code; verified to contain only comments)"
    for md, bl in blocks.items():
        for b in bl:
            key = (md, b.index)
            if key not in used and key not in skipped:
                problems.append(f"{md}:{b.first_line}: python block #{b.index} ({b.anchor!r}) is neither checked by a unit nor skipped with a reason")
    checked = sum(1 for md, bl in blocks.items() for b in bl if (md, b.index) in used)
    return problems, skipped, checked


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--unit", action="append", help="only run the named unit(s)")
    ap.add_argument("--live", action="store_true", help="also run DB samples against Docker Postgres")
    ap.add_argument("--keep", action="store_true", help="keep .build/ afterwards")
    ap.add_argument("--list", action="store_true", help="list units and exit")
    a = ap.parse_args()

    if a.list:
        for u in cfg.UNITS:
            print(f"{u.name:28} {', '.join(u.own)}")
        return 0

    blocks, problems = load_blocks()
    cov_problems, skipped, checked = coverage(blocks)
    problems += cov_problems
    total_blocks = sum(len(b) for b in blocks.values())

    units = [u for u in cfg.UNITS if not a.unit or u.name in a.unit]
    if a.unit and len(units) != len(set(a.unit)):
        print(f"unknown unit in {a.unit}; see --list", file=sys.stderr)
        return 2

    results: list[Result] = []
    for u in units:
        try:
            r = check_unit(u, blocks, a.live)
        except HarnessError as exc:
            r = Result(u.name, False, [f"  {exc}"], "harness: config/doc mismatch")
        results.append(r)
        print(f"{'PASS' if r.ok else 'FAIL'}  {r.unit:28} {r.summary}", flush=True)
        for ln in r.lines:
            print(ln)

    if not a.keep and not a.unit and BUILD.exists():
        shutil.rmtree(BUILD)

    print()
    for (md, idx), reason in sorted(skipped.items()):
        b = blocks[md][idx]
        print(f"SKIP  {md}:{b.first_line} (block #{idx}): {reason}")
    for pr in problems:
        print(f"ERROR {pr}")
    n_pass = sum(r.ok for r in results)
    n_fail = len(results) - n_pass
    print(
        f"\nunits: {n_pass} PASS / {n_fail} FAIL; python blocks: {total_blocks} in {len(blocks)} file(s), "
        f"{checked} checked, {len(skipped)} skipped with a reason; config problems: {len(problems)}"
    )
    return 0 if (n_fail == 0 and not problems) else 1


if __name__ == "__main__":
    sys.exit(main())
