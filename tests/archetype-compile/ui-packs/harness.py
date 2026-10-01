#!/usr/bin/env python3
"""Compile-check, and where possible run, the React / Next.js / React Native / UI / UI-test code samples.

Every ```tsx / ```ts / ```typescript / ```jsx / ```javascript / ```js block in the files listed in
units.FILES is extracted AT RUN TIME, placed into a throw-away project per unit (units.py) under
<project>/.units/<unit>/, and checked with the pinned toolchain of its project:

  web     React 19 + Next.js + TanStack Query + RHF + Zod + MSW + Vitest + Playwright
          tsc --noEmit (TS 7, strict + noUncheckedIndexedAccess); `vitest run` for units with tests;
          `next build` for the Next.js app unit; `playwright test` (system Chrome) against a stub server
  rn      React Native 0.87 + RNTL 14 + Jest (the versions the RN 0.87 app template pins) + MSW
          tsc --noEmit; `jest` for units with tests
  device  Detox + WebdriverIO (Appium): tsc --noEmit only — no simulator, emulator or Appium server

The run FAILS when:
  * a unit has a type error (or, for an `expect_errors` unit, any error other than the expected ones);
  * a unit's tests / build fail when executed;
  * a file's TS block count differs from units.FILES (a block was added or removed: update units.py);
  * a TS block is neither used by a unit nor listed in units.SKIP with a reason;
  * a file in units.SCOPE has TS blocks but is missing from units.FILES;
  * units.py names a block or a file that doesn't exist.

Placement: a block whose lines start with a path comment (`// lib/api-client.ts`, `// src/mocks/server.ts`,
`// e2e/pages/login.page.ts`, `// playwright.config.ts` …, at the top or after a blank line) is split into
those files (a unit's `remap` moves e.g. `lib/` to `src/lib/`). Fragments get a `place` entry: a path,
an optional line slice, a prelude (imports and declarations of APP-LEVEL names the excerpt assumes) and
a wrap (function / async / jsx / component / class / object). In JSX wraps, `// comment` lines are turned
into `{/* comment */}` so a doc excerpt's prose comments stay comments. Stubs live only in shims/ and
units.py and stand in for project code (shadcn/ui components copied into a project, app screens, test
fixtures) — never for a library API a sample demonstrates.

Every diagnostic is mapped back to `<pack>.md:<line>` (or "(harness <unit>)" for harness lines).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import glob
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SKILLS = os.path.join(ROOT, ".claude", "skills")
TS_LANGS = {"typescript", "ts", "tsx", "javascript", "js", "jsx"}
FENCE_OPEN = re.compile(r"^(\s*)```(\S*)\s*$")
FENCE_CLOSE = re.compile(r"^\s*```\s*$")
PATH_HEADER = re.compile(
    r"^//\s+((?:src|app|lib|components|hooks|e2e|test|tests)/[\w./\[\]()@-]+\.(?:ts|tsx|js|jsx|mts)"
    r"|[\w.-]+\.config\.(?:ts|js|mts)|\.detoxrc\.js|jest\.setup\.ts)(?:\s|$)"
)
DIRECTIVE = re.compile(r"""^["']use (?:client|server)["'];?\s*(?://.*)?$""")

sys.path.insert(0, HERE)
import units as CFG  # noqa: E402


# ----------------------------------------------------------------------------------------- extraction
class Block:
    def __init__(self, relfile: str, idx: int, lang: str, start: int, lines: list[str]):
        self.relfile = relfile   # path under .claude/skills, e.g. ui/shadcn.md
        self.idx = idx           # 1-based index among the file's TS blocks
        self.lang = lang
        self.start = start       # 1-based line number of the block's first body line
        self.lines = lines

    @property
    def ref(self) -> str:
        return f"{os.path.basename(self.relfile)[:-3]}#{self.idx}"

    def first_line(self) -> str:
        return next((l.strip() for l in self.lines if l.strip()), "")


def blocks_of(relfile: str, langs: set[str] = TS_LANGS) -> list[Block]:
    lines = open(os.path.join(SKILLS, relfile), encoding="utf-8").read().split("\n")
    out: list[Block] = []
    i = 0
    while i < len(lines):
        m = FENCE_OPEN.match(lines[i])
        if not m:
            i += 1
            continue
        j = i + 1
        while j < len(lines) and not FENCE_CLOSE.match(lines[j]):
            j += 1
        if m.group(2) in langs:
            pad = len(m.group(1))
            body = [l[pad:] if l[:pad].strip() == "" else l for l in lines[i + 1:j]]
            out.append(Block(relfile, len(out) + 1, m.group(2), i + 2, body))
        i = j + 1
    return out


def scope_files() -> list[str]:
    files: set[str] = set()
    for g in CFG.SCOPE:
        for p in glob.glob(os.path.join(SKILLS, g)):
            files.add(os.path.relpath(p, SKILLS))
    return sorted(files)


# ----------------------------------------------------------------------------------------- assembly
class Source:
    """File contents plus a line -> 'pack.md:line' map for error reporting."""

    def __init__(self):
        self.files: dict[str, list[str]] = {}
        self.maps: dict[str, list[str]] = {}

    def add(self, path: str, lines: list[str], origin: list[str]):
        buf = self.files.setdefault(path, [])
        mp = self.maps.setdefault(path, [])
        if buf:
            buf.append("")
            mp.append("")
        buf.extend(lines)
        mp.extend(origin)


def origin_for(block: Block, offset: int, n: int) -> list[str]:
    return [f"{block.relfile}:{block.start + offset + k}" for k in range(n)]


def indent(lines: list[str], pad: str = "  ") -> list[str]:
    return [pad + l if l.strip() else l for l in lines]


def jsx_comments(lines: list[str]) -> list[str]:
    """`// text` lines inside a JSX excerpt become JSX comments (they are prose in the doc)."""
    out = []
    for l in lines:
        m = re.match(r"^(\s*)//\s?(.*)$", l)
        out.append(f"{m.group(1)}{{/* {m.group(2).replace('*/', '* /')} */}}" if m else l)
    return out


def split_header_imports(body: list[str]) -> int:
    """Index of the first line after the excerpt's leading comments / imports / directives."""
    k = 0
    while k < len(body):
        s = body[k].strip()
        if not s or s.startswith("//") or DIRECTIVE.match(s):
            k += 1
            continue
        if body[k].startswith("import "):
            while k < len(body) and not re.search(r"""from\s+["'][^"']+["'];?\s*(//.*)?$|^import\s+["'][^"']+["'];?\s*$""", body[k]):
                k += 1
            k += 1
            continue
        break
    # leave trailing comment lines (they describe the code that follows) with the body
    while k > 0 and body[k - 1].strip().startswith("//"):
        k -= 1
    return k


STRING_OR_COMMENT = re.compile(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'|`(?:\\.|[^`\\])*`', re.S)


def code_only(text: str) -> str:
    """The text with comments and string literals blanked, so a word in prose or a string isn't 'used'."""
    return STRING_OR_COMMENT.sub(lambda m: " " * 0 + ("" if m.group(0).startswith("/") else '""'), text)


def auto_imports(names: dict, text: str, own_imports: str, extra: str) -> list[str]:
    """Import lines for the LIBRARY / shadcn names (a unit's `auto` map) an excerpt uses but doesn't import.

    A name counts as used when it appears as a word in the excerpt, and as provided when the excerpt's own
    imports or the unit's prelude mention it, or the excerpt declares it (function/const/class/type X)."""
    by_module: dict[tuple[str, str], list[str]] = {}
    text, extra, own_imports = code_only(text), code_only(extra), code_only(own_imports)
    for name, (module, kind) in names.items():
        n = re.escape(name)
        if not re.search(rf"(?<![\w.$]){n}\b", text + "\n" + extra):
            continue
        if re.search(rf"\b{n}\b", own_imports):
            continue
        if re.search(rf"^\s*import\b[^;]*\b{n}\b", extra, re.M):
            continue
        if re.search(rf"\b(?:function|const|let|var|class|interface|type|enum)\s+{n}\b", text + "\n" + extra):
            continue
        by_module.setdefault((module, kind), []).append(name)
    out = []
    for (module, kind), names in sorted(by_module.items()):
        if kind == "default":
            out += [f'import {n} from "{module}";' for n in names]
        elif kind == "namespace":
            out += [f'import * as {n} from "{module}";' for n in names]
        else:
            out.append(f'import {"type " if kind == "type" else ""}{{ {", ".join(sorted(names))} }} from "{module}";')
    return out


def line_no(blk: Block, at: int | str, default: int) -> int:
    """A 1-based line in the block: an int, or the first line whose stripped text starts with the string."""
    if at is None:
        return default
    if isinstance(at, int):
        return at
    for n, l in enumerate(blk.lines, 1):
        if l.strip().startswith(at):
            return n
    raise SystemExit(f"units.py: {blk.ref} has no line starting with {at!r} ({blk.relfile}:{blk.start}) — the doc changed")


def slice_of(blk: Block, spec: dict | None) -> tuple[int, int]:
    """(first, last) 1-based lines of a place spec: `from` (inclusive) / `until` (exclusive), ints or prefixes."""
    if not isinstance(spec, dict):
        return 1, len(blk.lines)
    a = line_no(blk, spec.get("from"), 1)
    b = line_no(blk, spec.get("until"), len(blk.lines) + 1) - 1
    return a, b


def place_one(src: Source, unit: dict, blk: Block, spec: dict):
    path = spec["path"]
    a, b = slice_of(blk, spec)
    body = blk.lines[a - 1:b]
    origin = origin_for(blk, a - 1, len(body))
    harness = f"(harness {unit['name']})"
    pre = spec["prelude"].split("\n") if spec.get("prelude") else []
    post = spec["postlude"].split("\n") if spec.get("postlude") else []
    wrap = spec.get("wrap") if spec.get("wrap") != "none" else None
    # The excerpt's own header (comments, "use client", imports) stays on top; the prelude follows it.
    k = split_header_imports(body)
    hoisted, hoisted_origin, body, origin = body[:k], origin[:k], body[k:], origin[k:]
    auto = spec.get("auto", unit.get("auto"))
    if auto:
        # names already imported/declared earlier in the same file (several blocks can share one file) count too
        already = "\n".join(src.files.get(path, []))
        used = "\n".join(body) + "\n" + spec.get("open", "") + "\n" + spec.get("close", "")
        pre = auto_imports(auto, used, "\n".join(hoisted), "\n".join(pre) + "\n" + already) + pre
    name = re.sub(r"\W", "_", blk.ref)
    if wrap == "function":
        pre, post, body = pre + [f"export function __sample_{name}() {{"], ["}"] + post, indent(body)
    elif wrap == "async":
        pre, post, body = pre + [f"export async function __sample_{name}() {{"], ["}"] + post, indent(body)
    elif wrap == "class":
        pre, post, body = pre + [f"export class __Sample_{name} {{"], ["}"] + post, indent(body)
    elif wrap == "object":
        pre, post, body = pre + [f"export const __sample_{name} = {{"], ["};"] + post, indent(body)
    elif wrap == "custom":     # e.g. a test(...) around an excerpt of test statements
        pre, post, body = pre + spec["open"].split("\n"), spec["close"].split("\n") + post, indent(body)
    elif wrap == "jsx":
        pre = pre + [f"export function Sample_{name}() {{", "  return (", "    <>"]
        post = ["    </>", "  );", "}"] + post
        body = indent(jsx_comments(body), "      ")
    elif wrap == "component":
        # statements, then the JSX the component renders (from the first line that starts with "<")
        j = next((n for n, l in enumerate(body) if l.lstrip().startswith("<")), len(body))
        stmts, jsx = body[:j], body[j:]
        pre = pre + [f"export function Sample_{name}() {{"]
        body = indent(stmts) + ["  return (", "    <>"] + indent(jsx_comments(jsx), "      ") + ["    </>", "  );"]
        origin = origin[:j] + [harness, harness] + origin[j:] + [harness, harness]
        post = ["}"] + post
    elif wrap:
        raise SystemExit(f"unknown wrap {wrap!r} for {blk.ref}")
    lines = hoisted + pre + body + post
    orig = hoisted_origin + [harness] * len(pre) + origin + [harness] * len(post)
    assert len(lines) == len(orig), (blk.ref, len(lines), len(orig))
    src.add(path, lines, orig)


def remap(unit: dict, path: str) -> str:
    for old, new in unit.get("remap", {}).items():
        if path.startswith(old):
            return new + path[len(old):]
    return path


def split_files(block: Block) -> list[tuple[str | None, int, list[str]]]:
    segs: list[tuple[str | None, int, list[str]]] = []
    cur_path, cur_start, cur = None, 0, []
    for k, line in enumerate(block.lines):
        m = PATH_HEADER.match(line)
        prev_blank = k == 0 or all(not l.strip() for l in block.lines[:k]) or not block.lines[k - 1].strip()
        if m and prev_blank:
            if any(l.strip() for l in cur):
                segs.append((cur_path, cur_start, cur))
            cur_path, cur_start, cur = m.group(1), k, [line]
        else:
            cur.append(line)
    if any(l.strip() for l in cur):
        segs.append((cur_path, cur_start, cur))
    return segs


def assemble(unit: dict, by_ref: dict[str, Block]) -> Source:
    src = Source()
    place = unit.get("place", {})
    for ref in unit["blocks"]:
        blk = by_ref[ref]
        spec = place.get(ref)
        if spec is not None:
            for s in spec if isinstance(spec, list) else [spec]:
                place_one(src, unit, blk, {"path": s} if isinstance(s, str) else s)
            continue
        for path, off, lines in split_files(blk):
            if path is None:
                raise SystemExit(f"units.py: {ref} has text before any path header — give it a `place` entry")
            src.add(remap(unit, path), lines, origin_for(blk, off, len(lines)))
    for ext in unit.get("external", []):
        hits = [b for b in blocks_of(ext["doc"], set(ext.get("langs", TS_LANGS))) if b.first_line().startswith(ext["prefix"])]
        if len(hits) != 1:
            raise SystemExit(f"unit {unit['name']}: expected one block in {ext['doc']} starting with {ext['prefix']!r}, found {len(hits)}")
        b = hits[0]
        src.add(ext["path"], b.lines, origin_for(b, 0, len(b.lines)))
        if ext.get("append"):
            extra = ext["append"].strip("\n").split("\n")
            src.add(ext["path"], extra, [f"(harness {unit['name']})"] * len(extra))
    return src


def tsconfig_for(unit: dict) -> dict:
    project = unit["project"]
    opts = {
        "strict": True,
        "noUncheckedIndexedAccess": True,
        "noEmit": True,
        "skipLibCheck": True,
        "target": "es2023",
        "module": "esnext",
        "moduleResolution": "bundler",
        "lib": ["es2023", "dom", "dom.iterable"],
        "types": [],
        "jsx": "react-jsx",
        "esModuleInterop": True,
        "resolveJsonModule": True,
        "allowJs": True,
        "checkJs": True,
        "isolatedModules": True,
        "paths": {"@/*": ["./src/*"]},
    }
    if project == "rn":
        opts["lib"] = ["es2023"]
        opts["types"] = ["jest"]
        opts["customConditions"] = ["react-native"]
    opts.update(unit.get("compilerOptions", {}))
    return {"compilerOptions": opts, "include": unit.get("include", ["**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx", "**/*.mts"]),
            "exclude": ["node_modules", ".next", "dist", "playwright-report", "test-results"]}


def copy_tree(src_dir: str, dst_dir: str, unit_name: str, written: dict[str, list[str]]):
    for dirpath, _, files in os.walk(src_dir):
        for fn in files:
            rel = os.path.relpath(os.path.join(dirpath, fn), src_dir)
            if rel in written:
                raise SystemExit(f"shim {src_dir}/{rel} would overwrite a sample file in unit {unit_name}")
            dst = os.path.join(dst_dir, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy(os.path.join(dirpath, fn), dst)


def build_unit(unit: dict, by_ref: dict[str, Block]) -> tuple[str, Source]:
    d = os.path.join(HERE, unit["project"], ".units", unit["name"])
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    src = assemble(unit, by_ref)
    for rel, lines in src.files.items():
        p = os.path.join(d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    for shim in unit.get("shims", []):
        copy_tree(os.path.join(HERE, "shims", shim), d, unit["name"], src.files)
    for rel, content in unit.get("files", {}).items():
        if rel in src.files:
            raise SystemExit(f"unit {unit['name']}: inline file {rel} would overwrite a sample file")
        p = os.path.join(d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content.lstrip("\n"))
    # expect_errors: [{"ref": block, "line": start of the line that must fail, "code": "TSnnnn"}] → pack.md:line
    unit["_expected"] = [(f"{by_ref[e['ref']].relfile}:{by_ref[e['ref']].start + line_no(by_ref[e['ref']], e['line'], 0) - 1}",
                          e["code"]) for e in unit.get("expect_errors", [])]
    with open(os.path.join(d, "tsconfig.json"), "w") as f:
        json.dump(tsconfig_for(unit), f, indent=2)
    return d, src


# ----------------------------------------------------------------------------------------- checks
TSC_LINE = re.compile(r"^(?P<file>[^()\s][^()]*?(?:\([^)]*\)[^()]*?)*)\((?P<line>\d+),(?P<col>\d+)\): error (?P<code>TS\d+): (?P<msg>.*)$")
RUNTIME_REF = re.compile(r"(?P<file>(?:src|e2e|app|test)/[\w./\[\]()@-]+\.(?:tsx?|jsx?|mts)):(?P<line>\d+)")


def where(src: Source, file: str, line: int) -> str | None:
    mp = src.maps.get(file)
    if mp and 0 < line <= len(mp):
        return mp[line - 1] or None
    return None


def annotate(text: str, src: Source) -> str:
    out = []
    for line in text.splitlines():
        hits = []
        for m in RUNTIME_REF.finditer(line):
            w = where(src, m.group("file"), int(m.group("line")))
            if w:
                hits.append(w)
        out.append(line + (f"   ↳ {', '.join(dict.fromkeys(hits))}" if hits else ""))
    return "\n".join(out)


def bin_of(unit: dict, name: str) -> str:
    return os.path.join(HERE, unit["project"], "node_modules", ".bin", name)


def run_tsc(unit: dict, d: str, src: Source) -> tuple[bool, str]:
    p = subprocess.run([bin_of(unit, "tsc"), "-p", "tsconfig.json", "--pretty", "false"], cwd=d, capture_output=True, text=True)
    errors: list[tuple[str, str, str]] = []  # (origin, code, line)
    out = []
    for line in (p.stdout + p.stderr).splitlines():
        m = TSC_LINE.match(line)
        if m:
            w = where(src, m.group("file"), int(m.group("line"))) or f"{m.group('file')}:{m.group('line')} (shim)"
            errors.append((w, m.group("code"), line))
            out.append(f"{line}\n      ↳ {w}")
        elif line.strip():
            out.append(line)
    expected = unit.get("_expected", [])   # resolved by build_unit: [(pack.md:line, TS code)]
    if expected:
        want = sorted(expected)
        got = sorted((w, c) for w, c, _ in errors)
        if want == got:
            return True, "tsc: the expected errors only — " + "; ".join(f"{c} at {w}" for w, c in got)
        return False, f"expected exactly {want}, got {got}\n" + "\n".join(out)
    return p.returncode == 0, "\n".join(out)


def summarize(text: str, patterns: tuple[str, ...]) -> str:
    keep = [l.strip() for l in text.splitlines() if l.strip().startswith(patterns)]
    return " ; ".join(dict.fromkeys(keep))


def run_vitest(unit: dict, d: str, src: Source) -> tuple[bool, str, int]:
    files = unit["vitest"]
    cfg = os.path.join(d, "vitest.config.mts")
    if not os.path.exists(cfg):
        setup = unit.get("vitest_setup", [])
        with open(cfg, "w") as f:
            f.write(
                'import { defineConfig } from "vitest/config";\n'
                'import { fileURLToPath } from "node:url";\n'
                "export default defineConfig({\n"
                '  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },\n'
                f"  test: {{ environment: \"jsdom\", setupFiles: {json.dumps(setup)}, allowOnly: false, retry: 0,\n"
                '          environmentOptions: { jsdom: { url: "http://localhost:3000/" } } },\n'
                "});\n"
            )
    p = subprocess.run([bin_of(unit, "vitest"), "run", "--config", "vitest.config.mts", *files], cwd=d,
                       capture_output=True, text=True, env={**os.environ, "CI": "1", "NO_COLOR": "1", "FORCE_COLOR": "0"})
    text = p.stdout + p.stderr
    m = re.search(r"Tests\s+(\d+) passed", text)
    n = int(m.group(1)) if m else 0
    if p.returncode == 0:
        return True, "vitest: " + summarize(text, ("Test Files", "Tests ")), n
    return False, "vitest FAILED:\n" + annotate("\n".join(text.splitlines()[-120:]), src), n


def run_jest(unit: dict, d: str, src: Source) -> tuple[bool, str, int]:
    p = subprocess.run([bin_of(unit, "jest"), "--ci", "--colors=false", *unit["jest"]], cwd=d,
                       capture_output=True, text=True, env={**os.environ, "CI": "1", "NO_COLOR": "1", "FORCE_COLOR": "0"})
    text = p.stdout + p.stderr
    m = re.search(r"Tests:\s+(?:.*?)(\d+) passed", text)
    n = int(m.group(1)) if m else 0
    if p.returncode == 0:
        return True, "jest: " + summarize(text, ("Test Suites:", "Tests:")), n
    return False, "jest FAILED:\n" + annotate("\n".join(text.splitlines()[-150:]), src), n


def run_next_build(unit: dict, d: str, src: Source) -> tuple[bool, str, int]:
    env = {**os.environ, "NEXT_TELEMETRY_DISABLED": "1", "CI": "1", "NO_COLOR": "1",
           "API_INTERNAL_URL": "http://127.0.0.1:9"}
    p = subprocess.run([bin_of(unit, "next"), "build"], cwd=d, capture_output=True, text=True, env=env)
    text = p.stdout + p.stderr
    if p.returncode == 0:
        routes = [l.strip() for l in text.splitlines() if re.match(r"^[├└┌]\s", l.strip())]
        return True, f"next build: OK ({len(routes)} routes)", 0
    return False, "next build FAILED:\n" + annotate("\n".join(text.splitlines()[-80:]), src), 0


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def run_playwright(unit: dict, d: str, src: Source) -> tuple[bool, str, int]:
    pw = unit["playwright"]
    port = free_port()
    server = subprocess.Popen(["node", pw["server"], str(port)], cwd=d, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              env={**os.environ, **pw.get("env", {})})
    try:
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                with socket.create_connection(("localhost", port), timeout=0.5):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            return False, "stub server did not start", 0
        env = {**{k: v for k, v in os.environ.items() if k != "FORCE_COLOR"}, "APP_BASE_URL": f"http://localhost:{port}", "CI": "1", "NO_COLOR": "1",
               "PHASE": "harness", **pw.get("env", {})}
        p = subprocess.run([bin_of(unit, "playwright"), "test", "--config", pw["config"]], cwd=d,
                           capture_output=True, text=True, env=env, timeout=600)
        text = p.stdout + p.stderr
        m = re.search(r"(\d+) passed", text)
        n = int(m.group(1)) if m else 0
        junit = os.path.join(d, "agent_state", "phases", "harness", "junit", "e2e.xml")
        note = f" ; junit written: {os.path.relpath(junit, d)}" if os.path.exists(junit) else " ; junit NOT written"
        if p.returncode == 0 and "flaky" not in text:
            return True, "playwright: " + summarize(text, ("Running", )) + f" ; {n} passed" + note, n
        return False, "playwright FAILED:\n" + annotate("\n".join(text.splitlines()[-120:]), src), n
    finally:
        server.send_signal(signal.SIGTERM)
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()


def check_unit(unit: dict, d: str, src: Source, run: bool) -> tuple[bool, str, int]:
    tests = 0
    notes = []
    if unit.get("tsc", True):
        ok, out = run_tsc(unit, d, src)
        if not ok:
            return False, out, 0
        if out.startswith("tsc:"):
            notes.append(out)
    if not run:
        return True, " ; ".join(notes), 0
    for key, fn in (("vitest", run_vitest), ("jest", run_jest), ("next_build", run_next_build), ("playwright", run_playwright)):
        if unit.get(key):
            ok, out, n = fn(unit, d, src)
            tests += n
            if not ok:
                return False, out, tests
            notes.append(out)
    return True, " ; ".join(notes), tests


# ----------------------------------------------------------------------------------------- main
def account(blocks: dict[str, list[Block]], by_ref: dict[str, Block]) -> list[str]:
    problems: list[str] = []
    for rel in scope_files():
        n = len(blocks.get(rel, []))
        if rel not in CFG.FILES:
            if n:
                problems.append(f"{rel}: {n} TS block(s) but the file is not in units.FILES — add it and cover every block")
        elif CFG.FILES[rel] != n:
            problems.append(f"{rel}: expected {CFG.FILES[rel]} TS blocks, found {n} — a block was added or removed; update units.py")
    for rel in CFG.FILES:
        if not os.path.exists(os.path.join(SKILLS, rel)):
            problems.append(f"units.FILES lists {rel}, which doesn't exist")
    used: dict[str, str] = {}   # a block may sit in several units (e.g. the real api-client under every hook)
    names = set()
    for u in CFG.UNITS:
        if u["name"] in names:
            problems.append(f"duplicate unit name {u['name']}")
        names.add(u["name"])
        if u["project"] not in ("web", "rn", "device"):
            problems.append(f"unit {u['name']}: unknown project {u['project']}")
        for ref in u["blocks"]:
            if ref not in by_ref:
                problems.append(f"unit {u['name']}: unknown block {ref}")
            used.setdefault(ref, u["name"])
        for ref in u.get("place", {}):
            if ref not in u["blocks"]:
                problems.append(f"unit {u['name']}: place entry for {ref}, which is not in its blocks")
    for ref, reason in CFG.SKIP.items():
        if ref not in by_ref:
            problems.append(f"SKIP names unknown block {ref}")
        if not reason or len(reason.strip()) < 15:
            problems.append(f"SKIP {ref} needs a real reason")
        if ref in used:
            problems.append(f"{ref} is both checked and skipped")
    for ref, b in by_ref.items():
        if ref not in used and ref not in CFG.SKIP:
            problems.append(f"{ref} ({b.relfile}:{b.start}) is neither checked by a unit nor listed in units.SKIP")
    # a block placed in slices must have every non-blank line placed by some unit
    covered: dict[str, set[int]] = {}
    for u in CFG.UNITS:
        for ref in u["blocks"]:
            if ref not in by_ref:
                continue
            spec = u.get("place", {}).get(ref)
            specs = (spec if isinstance(spec, list) else [spec]) if spec is not None else [None]
            for s in specs:
                a, b = slice_of(by_ref[ref], s)
                covered.setdefault(ref, set()).update(range(a, b + 1))
    for ref, lines in covered.items():
        for n, l in enumerate(by_ref[ref].lines, 1):
            if l.strip() and n not in lines:
                problems.append(f"{ref} line {n} ({by_ref[ref].relfile}:{by_ref[ref].start + n - 1}) is placed by no unit")
    return problems


CHECKED_LINE = re.compile(r"compile-checked.*\([^()]*\b20\d\d-\d\d-\d\d\)", re.I)


def inventory(blocks: dict[str, list[Block]], by_ref: dict[str, Block], problems: list[str]) -> int:
    """The offline half of the gate (tests/archetype-ui-packs-inventory.test.sh): no npm, no compiler."""
    fails = 0

    def check(ok: bool, label: str):
        nonlocal fails
        print(f"  {'✓' if ok else '✗'} {label}")
        fails += 0 if ok else 1

    for p in problems:
        check(False, p)
    check(not problems, f"every TS/JS block of the {len(blocks)} files in scope is checked by a unit or skipped "
                        f"with a reason, and block counts match units.FILES ({len(by_ref)} blocks)")
    used = {r for u in CFG.UNITS for r in u["blocks"]}
    for rel, bl in blocks.items():
        if any(b.ref in used for b in bl):
            text = open(os.path.join(SKILLS, rel), encoding="utf-8").read()
            check(bool(CHECKED_LINE.search(text)), f"{rel}: states what it was compile-checked against, with the date")
    for project in ("web", "rn", "device"):
        check(os.path.exists(os.path.join(HERE, project, "package.json"))
              and os.path.exists(os.path.join(HERE, project, "package-lock.json")),
              f"{project}/ is pinned (package.json + package-lock.json)")
        pkg = json.load(open(os.path.join(HERE, project, "package.json")))
        loose = [f"{k}@{v}" for k, v in pkg.get("devDependencies", {}).items() if not re.fullmatch(r"\d+\.\d+\.\d+", v)]
        check(not loose, f"{project}/package.json pins exact versions{' — ' + ', '.join(loose) if loose else ''}")
    for shim_dir in sorted(os.listdir(os.path.join(HERE, "shims"))):
        stubbed = []
        for dirpath, _, files in os.walk(os.path.join(HERE, "shims", shim_dir)):
            for fn in files:
                head = open(os.path.join(dirpath, fn), encoding="utf-8").read(400)
                if "HARNESS" not in head:
                    stubbed.append(os.path.relpath(os.path.join(dirpath, fn), HERE))
        check(not stubbed, f"shims/{shim_dir}: every file says it is a HARNESS stub/probe{' — ' + ', '.join(stubbed) if stubbed else ''}")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--unit", action="append", help="run only these units (repeatable)")
    ap.add_argument("--project", action="append", choices=["web", "rn", "device"], help="run only these projects")
    ap.add_argument("--list", action="store_true", help="list blocks and units and exit")
    ap.add_argument("--inventory", action="store_true",
                    help="offline check only (no npm): every block checked or skipped, counts match, files dated")
    ap.add_argument("--no-run", action="store_true", help="type-check only (skip vitest / jest / next build / playwright)")
    ap.add_argument("--keep", action="store_true", help="keep <project>/.units/ for debugging")
    ap.add_argument("-j", "--jobs", type=int, default=max(2, (os.cpu_count() or 4) // 2))
    args = ap.parse_args()

    blocks = {rel: blocks_of(rel) for rel in sorted(set(scope_files()) | set(CFG.FILES)) if os.path.exists(os.path.join(SKILLS, rel))}
    by_ref = {b.ref: b for bl in blocks.values() for b in bl}
    try:
        problems = account(blocks, by_ref)
    except SystemExit as e:  # a place spec names a line the doc no longer has
        problems = [str(e)]
    if args.inventory:
        return inventory(blocks, by_ref, problems)
    if args.list:
        for rel, bl in blocks.items():
            for b in bl:
                print(f"{b.ref:40s} {b.relfile}:{b.start:<5d} {b.lang:10s} {b.first_line()[:70]}")
        for u in CFG.UNITS:
            print(f"UNIT {u['name']} [{u['project']}]: {', '.join(u['blocks'])}")
        return 0
    if problems:
        print("CONFIG FAIL" if not (args.unit or args.project) else "CONFIG PROBLEMS (ignored for a partial run)")
        for p in problems:
            print("  - " + p)
        if not (args.unit or args.project):
            return 2

    selected = [u for u in CFG.UNITS if (not args.unit or u["name"] in args.unit) and (not args.project or u["project"] in args.project)]
    built = {u["name"]: build_unit(u, by_ref) for u in selected}
    results: dict[str, tuple[bool, str, int]] = {}
    serial = [u for u in selected if u.get("next_build") or u.get("playwright")]
    parallel = [u for u in selected if u not in serial]
    with cf.ThreadPoolExecutor(max_workers=args.jobs) as ex:
        futs = {ex.submit(check_unit, u, *built[u["name"]], not args.no_run): u["name"] for u in parallel}
        for u in serial:  # heavy, port-binding steps run one at a time
            results[u["name"]] = check_unit(u, *built[u["name"]], not args.no_run)
        for fut in cf.as_completed(futs):
            results[futs[fut]] = fut.result()

    n_pass = n_fail = 0
    checked: dict[str, set[str]] = {rel: set() for rel in blocks}
    ran: dict[str, set[str]] = {rel: set() for rel in blocks}
    for u in selected:
        ok, out, tests = results[u["name"]]
        executed = not args.no_run and any(u.get(k) for k in ("vitest", "jest", "next_build", "playwright"))
        files = sorted({os.path.basename(by_ref[r].relfile) for r in u["blocks"]})
        desc = f"[{u['project']}] {len(u['blocks'])} blocks from {', '.join(files)}"
        if ok:
            for r in u["blocks"]:
                checked[by_ref[r].relfile].add(r)
                if executed and r in u.get("executed_blocks", u["blocks"]):
                    ran[by_ref[r].relfile].add(r)
        if ok:
            n_pass += 1
            print(f"PASS  {u['name']}  {desc}" + (f"\n      {out}" if out else ""))
        else:
            n_fail += 1
            print(f"FAIL  {u['name']}  {desc}")
            print("\n".join("      " + l for l in out.splitlines()))
    if not args.keep:
        for u in selected:
            shutil.rmtree(os.path.join(HERE, u["project"], ".units", u["name"]), ignore_errors=True)
    if not (args.unit or args.project):
        skipped: dict[str, int] = {}
        for ref in CFG.SKIP:
            skipped[by_ref[ref].relfile] = skipped.get(by_ref[ref].relfile, 0) + 1
        print("\nper file (TS/JS blocks): checked = type-checked in a passing unit; "
              "run = also inside a passing unit whose tests / build / e2e ran")
        for rel in blocks:
            total = len(blocks[rel])
            if total:
                print(f"  {rel:48s} {total:3d} blocks: {len(checked[rel]):3d} checked, {len(ran[rel]):3d} run, "
                      f"{skipped.get(rel, 0):2d} skipped")
        for ref, reason in sorted(CFG.SKIP.items()):
            print(f"SKIP  {ref} ({by_ref[ref].relfile}:{by_ref[ref].start}): {reason}")
    total_tests = sum(r[2] for r in results.values())
    n_checked = len({r for u in selected for r in u["blocks"]})
    print(f"\nunits: {n_pass} PASS / {n_fail} FAIL ; blocks checked: {n_checked} ; "
          f"skipped: {len(CFG.SKIP)} ; total TS blocks in scope: {len(by_ref)} ; tests executed: {total_tests}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
