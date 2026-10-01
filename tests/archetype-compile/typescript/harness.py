#!/usr/bin/env python3
"""Type-check the TypeScript/TSX samples in the archetype skill files and the backend packs.

Every ```typescript / ```ts / ```tsx / ```javascript (…) block in the files
SCAN_GLOBS names (under .claude/skills/):
  backend/archetypes/*.md, ui/archetypes/*.md            — the archetypes
  languages/typescript.md, frameworks/{express,fastify,nestjs,trpc,graphql}.md,
  testing/{vitest,testcontainers,contract-testing,property-based,load-testing}.md,
  core/**/*.md, security/*.md, api/*.md                  — the backend packs agents copy from
is extracted AT RUN TIME (so an edited sample is re-verified), placed into a
throw-away project per unit (see units.py), and type-checked with the pinned
TypeScript (`tsc --noEmit`, strict + noUncheckedIndexedAccess). k6 scripts
(```javascript in testing/load-testing.md) are type-checked as JavaScript
(checkJs) against @types/k6. The React/React Native/UI packs (react.md,
nextjs.md, tanstack-query.md, react-native*.md, ui/*.md, msw.md, playwright.md,
react-native-testing-library.md, detox.md) are another harness's scope.

--inventory-only runs just the coverage checks below (python3 only, no npm, no
tsc): tests/archetype-compile-typescript-inventory.test.sh runs it in run-all.

The run FAILS when:
  * any unit has a type error;
  * a unit declares `vitest` test files and they fail when executed (in-process
    test samples only: mocks/supertest, no database or network);
  * a file's TS block count differs from units.py (a block was added/removed —
    the config must be updated, so nothing goes unchecked silently);
  * a TS block is neither compiled by some unit nor listed in SKIP with a reason;
  * units.py names a file/block that doesn't exist.

Blocks are placed at the path named by their header comment (`// src/foo.ts`).
A block may hold several files: a column-0 `// src/...ts` line after a blank
line starts a new file. Blocks without a header need an explicit `place` entry
(optionally with a prelude/postlude and a `wrap` for statement/JSX fragments).
A unit may also pull a TS block from another skill file (`external`, e.g. the
envelope types in api/response-envelope.md). The Prisma samples compile against
a client generated from shims/prisma/schema.prisma; the gRPC sample against
committed ts-proto output (grpc-codegen/regen.sh). Stubs for project code a
fragment assumes live only in this directory (shims/, units.py) — never stubs
of the library API a sample demonstrates.

--strictest adds exactOptionalPropertyTypes, noImplicitReturns and
noFallthroughCasesInSwitch (the rest of languages/typescript.md's set) as a
report; --no-run skips executing the test samples.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SKILLS = os.path.join(ROOT, ".claude", "skills")
SCAN_GLOBS = [
    "backend/archetypes/*.md",
    "ui/archetypes/*.md",
    "languages/typescript.md",
    "frameworks/express.md",
    "frameworks/fastify.md",
    "frameworks/nestjs.md",
    "frameworks/trpc.md",
    "frameworks/graphql.md",           # its TypeScript blocks (the Python/Java/Go ones are other harnesses')
    "testing/vitest.md",
    "testing/testcontainers.md",       # no TS blocks today; one added later must be covered
    "testing/contract-testing.md",
    "testing/property-based.md",
    "testing/load-testing.md",         # k6 scripts: ```javascript, checked against @types/k6
    "core/**/*.md",
    "security/*.md",
    "api/*.md",
]
TS_LANGS = {"typescript", "ts", "tsx", "javascript", "js", "jsx", "mts", "cts"}
FENCE_OPEN = re.compile(r"^(\s*)```(\S*)\s*$")
FENCE_CLOSE = re.compile(r"^\s*```\s*$")
# `// src/x/y.ts` (optionally followed by " — description") starts a file inside a block.
PATH_HEADER = re.compile(
    r"^//\s+((?:src|prisma|test|tests|e2e|drizzle|scripts)/[\w./\[\]-]+\.(?:ts|tsx|mts|cts|js)"
    r"|[\w.-]+\.config\.(?:ts|mts|js))(?:\s|$)"
)

STRICTEST = False  # set by --strictest

sys.path.insert(0, HERE)
import units as CFG  # noqa: E402


# --------------------------------------------------------------------------- extraction
class Block:
    def __init__(self, relfile: str, idx: int, lang: str, start: int, lines: list[str]):
        self.relfile = relfile          # e.g. backend/archetypes/auth-middleware-typescript.md
        self.idx = idx                  # 1-based index among the file's TS blocks
        self.lang = lang
        self.start = start              # 1-based line number of the first body line
        self.lines = lines

    @property
    def ref(self) -> str:
        return f"{os.path.basename(self.relfile)[:-3]}#{self.idx}"


def extract_blocks() -> dict[str, list[Block]]:
    out: dict[str, list[Block]] = {}
    paths = [p for g in SCAN_GLOBS for p in sorted(glob.glob(os.path.join(SKILLS, g), recursive=True))]
    for path in dict.fromkeys(paths):  # de-duplicated, scan order kept
        rel = os.path.relpath(path, SKILLS)
        lines = open(path, encoding="utf-8").read().split("\n")
        blocks: list[Block] = []
        i = 0
        while i < len(lines):
            m = FENCE_OPEN.match(lines[i])
            if not m:
                i += 1
                continue
            lang, indent = m.group(2), len(m.group(1))
            j = i + 1
            while j < len(lines) and not FENCE_CLOSE.match(lines[j]):
                j += 1
            if lang in TS_LANGS:
                body = [l[indent:] if l[:indent].strip() == "" else l for l in lines[i + 1:j]]
                blocks.append(Block(rel, len(blocks) + 1, lang, i + 2, body))
            i = j + 1
        if blocks:
            out[rel] = blocks
    return out


def split_files(block: Block) -> list[tuple[str | None, int, list[str]]]:
    """Split a block into (path|None, first-line-offset, lines) segments by path headers."""
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


# --------------------------------------------------------------------------- unit assembly
class Source:
    """Collects file contents plus a line → (md file, md line) map for error reporting."""

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


def assemble(unit: dict, blocks_by_ref: dict[str, Block], workdir: str) -> Source:
    src = Source()
    place = unit.get("place", {})
    for ref in unit["blocks"]:
        blk = blocks_by_ref[ref]
        spec = place.get(ref)
        if isinstance(spec, str):
            spec = {"path": spec}
        if spec:
            path = spec["path"]
            body = blk.lines
            origin = origin_for(blk, 0, len(body))
            pre = [l for l in spec.get("prelude", "").split("\n")] if spec.get("prelude") else []
            post = [l for l in spec.get("postlude", "").split("\n")] if spec.get("postlude") else []
            wrap = spec.get("wrap")
            hoisted: list[str] = []
            if wrap:
                # a fragment's own leading import lines stay at module top level, above the wrapper
                k = 0
                while k < len(body) and (not body[k].strip() or body[k].startswith("//") or body[k].startswith("import ")):
                    if body[k].startswith("import ") and "{" in body[k] and "}" not in body[k]:
                        while k < len(body) and "}" not in body[k]:  # multi-line import { … } from "x";
                            k += 1
                    k += 1
                hoisted, body = body[:k], body[k:]
                origin = origin_for(blk, 0, len(hoisted)) + origin_for(blk, len(hoisted), len(body))
                pre = hoisted + pre
            if wrap == "object":       # a property-list excerpt → object literal
                pre, post = pre + [f"export const __sample_{blk.idx} = {{"], ["};"] + post
                body = indent(body)
            elif wrap == "async":      # statements with top-level await → async function body
                pre, post = pre + [f"export async function __sample_{blk.idx}() {{"], ["}"] + post
                body = indent(body)
            elif wrap == "function":   # plain statements → function body
                pre, post = pre + [f"export function __sample_{blk.idx}() {{"], ["}"] + post
                body = indent(body)
            elif wrap == "jsx":        # a JSX expression fragment → component return
                pre, post = pre + [f"export function Sample{blk.idx}() {{", "  return (", "    <>"], ["    </>", "  );", "}"] + post
                body = indent(body, "      ")
            elif wrap == "class":      # class members → class body
                pre, post = pre + [f"export class __Sample{blk.idx} {{"], ["}"] + post
                body = indent(body)
            elif wrap:
                raise SystemExit(f"unknown wrap {wrap!r} for {ref}")
            n_pre_harness = len(pre) - len(hoisted)
            origin_pre = origin[:len(hoisted)] + [f"(harness {unit['name']})"] * n_pre_harness
            origin_body = origin[len(hoisted):]
            src.add(path, pre + body + post, origin_pre + origin_body + [f"(harness {unit['name']})"] * len(post))
            continue
        segs = split_files(blk)
        for path, off, lines in segs:
            if path is None:
                raise SystemExit(f"units.py: {ref} has text before any `// src/...` header — give it a `place` entry")
            src.add(path, lines, origin_for(blk, off, len(lines)))
    if unit.get("modules"):
        # header-less fragments (no import/export) would be global SCRIPTS: their names would collide across
        # files and top-level await would be illegal. Make each one a module, as it is in a project.
        for path, lines in src.files.items():
            if not path.endswith(".d.ts") and not any(re.match(r"\s*(import|export)\b", l) for l in lines):
                src.add(path, ["export {}; // (harness: a module, as in a project)"], [f"(harness {unit['name']})"])
    return src


def base_tsconfig(unit: dict) -> dict:
    ui = unit.get("kind") == "ui"
    opts = {
        "strict": True,
        "noUncheckedIndexedAccess": True,
        "noEmit": True,
        "skipLibCheck": True,
        "target": "es2023",
        "module": "esnext",
        "moduleResolution": "bundler",
        "lib": ["es2023", "dom", "dom.iterable"] if ui else ["es2023"],
        "types": ["node"] if not ui else [],
        "jsx": "react-jsx",
        "esModuleInterop": True,
        "resolveJsonModule": True,
        "allowJs": True,
        "checkJs": True,
        "isolatedModules": False,
    }
    if unit.get("decorators") == "legacy":   # NestJS / class-validator
        opts["experimentalDecorators"] = True
        opts["emitDecoratorMetadata"] = True
    if STRICTEST:  # --strictest: the rest of languages/typescript.md's "non-negotiable" set (report only)
        opts.update({"exactOptionalPropertyTypes": True, "noImplicitReturns": True, "noFallthroughCasesInSwitch": True})
    opts.update(unit.get("compilerOptions", {}))
    return {"compilerOptions": opts, "include": ["**/*.ts", "**/*.tsx", "**/*.js", "**/*.mts"], "exclude": ["node_modules"]}


def external_blocks(doc: str, langs: set[str]) -> list[Block]:
    """TS blocks of a non-archetype skill file (e.g. api/response-envelope.md) used as unit input."""
    path = os.path.join(SKILLS, doc)
    lines = open(path, encoding="utf-8").read().split("\n")
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
            out.append(Block(doc, len(out) + 1, m.group(2), i + 2, lines[i + 1:j]))
        i = j + 1
    return out


def build_unit(unit: dict, blocks_by_ref: dict[str, Block], root: str) -> tuple[str, Source]:
    d = os.path.join(root, unit["name"])
    os.makedirs(d)
    os.symlink(os.path.join(HERE, "node_modules"), os.path.join(d, "node_modules"))
    src = assemble(unit, blocks_by_ref, d)
    for ext in unit.get("external", []):
        found = external_blocks(ext["doc"], set(ext["langs"]))
        if len(found) < ext["index"]:
            raise SystemExit(f"unit {unit['name']}: {ext['doc']} has no {ext['langs']} block #{ext['index']}")
        blk = found[ext["index"] - 1]
        src.add(ext["path"], blk.lines, origin_for(blk, 0, len(blk.lines)))
    for rel, lines in src.files.items():
        p = os.path.join(d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    for shim in unit.get("shims", []):
        s = os.path.join(HERE, "shims", shim)
        if os.path.isdir(s):
            for dirpath, _, files in os.walk(s):
                for fn in files:
                    rel = os.path.relpath(os.path.join(dirpath, fn), s)
                    dst = os.path.join(d, rel)
                    if os.path.exists(dst):
                        raise SystemExit(f"shim {shim}/{rel} would overwrite a sample file in unit {unit['name']}")
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy(os.path.join(dirpath, fn), dst)
        else:
            dst = os.path.join(d, "__shims__", os.path.basename(s))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy(s, dst)
    with open(os.path.join(d, "tsconfig.json"), "w") as f:
        json.dump(base_tsconfig(unit), f, indent=2)
    return d, src


TSC_LINE = re.compile(r"^(?P<file>[^()\s][^()]*?)\((?P<line>\d+),(?P<col>\d+)\): (?P<msg>.*)$")


def run_vitest(d: str, files: list[str], extra_env: dict | None = None) -> tuple[bool, str]:
    """Execute a unit's test samples (in-process: mocks and supertest only — no database, no network)."""
    vitest = os.path.join(HERE, "node_modules", ".bin", "vitest")
    p = subprocess.run([vitest, "run", *files], cwd=d, capture_output=True, text=True,
                       env={**os.environ, "CI": "1", "NO_COLOR": "1", **(extra_env or {})})
    lines = (p.stdout + p.stderr).splitlines()
    summary = " ; ".join(l.strip() for l in lines if l.strip().startswith(("Test Files", "Tests ")))
    if p.returncode == 0:
        return True, summary
    keep = [l for l in lines if not l.startswith('{"level"')]  # drop the samples' own JSON log lines
    return False, "\n".join(keep[-60:])


def run_prisma_validate(d: str, specs: list[dict]) -> tuple[bool, str]:
    """`prisma validate` each ```prisma block named in specs, with the unit's own prisma.config.ts (a doc block).

    The block is written to the config's schema path; DATABASE_URL is a placeholder (validate never connects).
    """
    prisma = os.path.join(HERE, "node_modules", ".bin", "prisma")
    env = {**os.environ, "DATABASE_URL": "postgresql://validate:validate@127.0.0.1:1/validate",
           "PRISMA_HIDE_UPDATE_MESSAGE": "1", "CHECKPOINT_DISABLE": "1"}
    notes = []
    for spec in specs:
        blocks = external_blocks(spec["doc"], set(spec["langs"]))
        if len(blocks) < spec["index"]:
            return False, f"{spec['doc']} has no {spec['langs']} block #{spec['index']}"
        blk = blocks[spec["index"] - 1]
        target = os.path.join(d, spec.get("path", "prisma/schema.prisma"))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write("\n".join(blk.lines) + "\n")
        p = subprocess.run([prisma, "validate"], cwd=d, capture_output=True, text=True, env=env)
        out = p.stdout + p.stderr
        where = f"{blk.relfile}:{blk.start}"
        if p.returncode != 0 or "warning" in out.lower():  # a deprecation warning fails too
            return False, f"prisma validate FAILED for the ```prisma block at {where}:\n{out}"
        notes.append(where.split("/")[-1])
    return True, "prisma validate: " + ", ".join(notes)


def run_node_probe(d: str, entry: str) -> tuple[bool, str]:
    """Emit `entry` (and what it imports) to CommonJS WITH decorator metadata, then run it with node.

    For behaviour tsc can't see — NestJS resolves constructor dependencies from emitted metadata at runtime.
    """
    cfg = {"compilerOptions": {"strict": True, "skipLibCheck": True, "target": "es2022", "module": "nodenext",
                               "moduleResolution": "nodenext", "experimentalDecorators": True,
                               "emitDecoratorMetadata": True, "esModuleInterop": True, "types": ["node"],
                               "rootDir": "src", "outDir": "dist-probe"},
           "files": [entry]}
    with open(os.path.join(d, "tsconfig.probe.json"), "w") as f:
        json.dump(cfg, f)
    tsc = os.path.join(HERE, "node_modules", ".bin", "tsc")
    p = subprocess.run([tsc, "-p", "tsconfig.probe.json", "--pretty", "false"], cwd=d, capture_output=True, text=True)
    if p.returncode != 0:
        return False, "probe emit failed:\n" + p.stdout + p.stderr
    js = os.path.join("dist-probe", os.path.relpath(entry, "src")).rsplit(".", 1)[0] + ".js"
    r = subprocess.run(["node", js], cwd=d, capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    return r.returncode == 0, ("node probe: " + out.splitlines()[-1]) if r.returncode == 0 else ("node probe FAILED:\n" + out)


def run_node_test(d: str, spec: dict) -> tuple[bool, str]:
    """Emit a node:test file (and what it imports) to CommonJS, then run it with `node --test`.

    For test samples written for node:test rather than Vitest (fastify.md's inject() tests). In-process only:
    the unit's shims stand in for project services, so no database or network is needed.
    """
    cfg = {"compilerOptions": {"strict": True, "skipLibCheck": True, "target": "es2022", "module": "nodenext",
                               "moduleResolution": "nodenext", "esModuleInterop": True, "types": ["node"],
                               "rootDir": "src", "outDir": "dist-test"},
           "files": [spec["entry"], *spec.get("files", [])]}
    with open(os.path.join(d, "tsconfig.node-test.json"), "w") as f:
        json.dump(cfg, f)
    tsc = os.path.join(HERE, "node_modules", ".bin", "tsc")
    p = subprocess.run([tsc, "-p", "tsconfig.node-test.json", "--pretty", "false"], cwd=d, capture_output=True,
                       text=True)
    if p.returncode != 0:
        return False, "node:test emit failed:\n" + p.stdout + p.stderr
    js = os.path.join("dist-test", os.path.relpath(spec["entry"], "src")).rsplit(".", 1)[0] + ".js"
    r = subprocess.run(["node", "--test", "--test-reporter=spec", js], cwd=d, capture_output=True, text=True,
                       env={**os.environ, "NO_COLOR": "1", **spec.get("env", {})})
    out = (r.stdout + r.stderr).strip().splitlines()
    summary = " ; ".join(l.strip().lstrip("ℹ ").strip() for l in out if l.strip().lstrip("ℹ ").startswith(("tests ", "pass ", "fail ")))
    return r.returncode == 0, ("node --test: " + summary) if r.returncode == 0 else ("node --test FAILED:\n" + "\n".join(out[-80:]))


def check_unit(unit: dict, d: str, src: Source, run_tests: bool) -> tuple[bool, str]:  # noqa: C901
    ok, out = run_tsc(d, src)
    if ok and run_tests and unit.get("node_test"):
        ok, out = run_node_test(d, unit["node_test"])
        if not ok:
            return ok, out
    if ok and unit.get("prisma_validate"):
        ok, out = run_prisma_validate(d, unit["prisma_validate"])
        if not ok:
            return ok, out
    if ok and run_tests and unit.get("node_probe"):
        probes = unit["node_probe"] if isinstance(unit["node_probe"], list) else [unit["node_probe"]]
        outs = []
        for entry in probes:
            ok, pout = run_node_probe(d, entry)
            if not ok:
                return ok, pout
            outs.append(pout[len("node probe: "):] if pout.startswith("node probe: ") else pout)
        out = "node probe: " + " | ".join(outs)
    if not ok or not run_tests or not unit.get("vitest"):
        return ok, out
    ok, vout = run_vitest(d, unit["vitest"], unit.get("vitest_env", {}))
    return ok, ("vitest: " + vout) if ok else ("tsc passed; the test samples FAILED when run:\n" + vout)


def run_tsc(d: str, src: Source) -> tuple[bool, str]:
    tsc = os.path.join(HERE, "node_modules", ".bin", "tsc")
    p = subprocess.run([tsc, "-p", "tsconfig.json", "--pretty", "false"], cwd=d, capture_output=True, text=True)
    out = []
    for line in (p.stdout + p.stderr).splitlines():
        m = TSC_LINE.match(line)
        if m and m.group("file") in src.maps:
            mp = src.maps[m.group("file")]
            n = int(m.group("line")) - 1
            where = mp[n] if 0 <= n < len(mp) and mp[n] else "?"
            line = f"{line}\n      ↳ {where}"
        out.append(line)
    return p.returncode == 0, "\n".join(out)


# --------------------------------------------------------------------------- prisma
def prisma_generate(tmp: str) -> tuple[bool, str]:
    """Generate the Prisma client the Prisma samples type-check against (harness schema)."""
    schema_dir = os.path.join(tmp, "__prisma__")
    os.makedirs(schema_dir)
    shutil.copy(os.path.join(HERE, "shims", "prisma", "schema.prisma"), os.path.join(schema_dir, "schema.prisma"))
    os.symlink(os.path.join(HERE, "node_modules"), os.path.join(schema_dir, "node_modules"))
    p = subprocess.run(
        [os.path.join(HERE, "node_modules", ".bin", "prisma"), "generate", "--schema", "schema.prisma"],
        cwd=schema_dir, capture_output=True, text=True,
        env={**os.environ, "PRISMA_HIDE_UPDATE_MESSAGE": "1", "CHECKPOINT_DISABLE": "1"},
    )
    return p.returncode == 0, p.stdout + p.stderr


# --------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--unit", action="append", help="run only these units (repeatable)")
    ap.add_argument("--keep", action="store_true", help="keep the temp dir and print its path")
    ap.add_argument("--list", action="store_true", help="list units and exit")
    ap.add_argument("--inventory-only", action="store_true",
                    help="only the coverage checks (block counts, every block compiled or skipped): python3, offline")
    ap.add_argument("-j", "--jobs", type=int, default=max(2, (os.cpu_count() or 4) // 2))
    ap.add_argument("--no-run", action="store_true",
                    help="type-check only; skip executing the units' declared Vitest test samples")
    ap.add_argument("--strictest", action="store_true",
                    help="also exactOptionalPropertyTypes + noImplicitReturns + noFallthroughCasesInSwitch "
                         "(languages/typescript.md's full set) — an informational report, not the gate")
    args = ap.parse_args()
    global STRICTEST
    STRICTEST = args.strictest

    blocks = extract_blocks()
    by_ref = {b.ref: b for bl in blocks.values() for b in bl}
    problems: list[str] = []

    # 0. a block ref is "<file stem>#<n>": two scanned files with one stem would make refs ambiguous
    stems: dict[str, str] = {}
    for rel in blocks:
        stem = os.path.basename(rel)[:-3]
        if stem in stems:
            problems.append(f"{rel} and {stems[stem]} share the stem {stem!r} — block refs would be ambiguous")
        stems[stem] = rel

    # 1. block-count contract per file
    for rel, bl in blocks.items():
        want = CFG.FILES.get(rel)
        if want is None:
            problems.append(f"{rel}: {len(bl)} TS block(s) but the file is not in units.FILES — add it and cover every block")
        elif want != len(bl):
            problems.append(f"{rel}: expected {want} TS blocks, found {len(bl)} — a block was added/removed; update units.py")
    for rel in CFG.FILES:
        if rel not in blocks:
            problems.append(f"units.FILES lists {rel} but it has no TS blocks (or doesn't exist)")

    # 2. every block compiled or skipped with a reason
    used: set[str] = set()
    names = set()
    for u in CFG.UNITS:
        if u["name"] in names:
            problems.append(f"duplicate unit name {u['name']}")
        names.add(u["name"])
        for ref in u["blocks"]:
            if ref not in by_ref:
                problems.append(f"unit {u['name']}: unknown block {ref}")
            used.add(ref)
        for ref in u.get("place", {}):
            if ref not in u["blocks"]:
                problems.append(f"unit {u['name']}: place entry for {ref}, which is not in its blocks")
    for ref, reason in CFG.SKIP.items():
        if ref not in by_ref:
            problems.append(f"SKIP names unknown block {ref}")
        if not reason or len(reason.strip()) < 10:
            problems.append(f"SKIP {ref} needs a real reason")
        if ref in used:
            problems.append(f"{ref} is both compiled and skipped")
    for ref in by_ref:
        if ref not in used and ref not in CFG.SKIP:
            b = by_ref[ref]
            problems.append(f"{ref} ({b.relfile}:{b.start}) is neither compiled by a unit nor listed in SKIP")

    if args.list:
        for u in CFG.UNITS:
            print(f"{u['name']}: {', '.join(u['blocks'])}")
        return 0
    if args.inventory_only:
        for p in problems:
            print("  - " + p)
        print(f"{'INVENTORY FAIL' if problems else 'INVENTORY OK'}: {len(blocks)} files, {len(by_ref)} TS blocks "
              f"({len(used & set(by_ref))} compiled by {len(CFG.UNITS)} units, "
              f"{len(set(CFG.SKIP) & set(by_ref))} skipped with a reason)")
        return 2 if problems else 0
    if problems:
        print("CONFIG FAIL" if not args.unit else "CONFIG PROBLEMS (ignored: --unit run)")
        for p in problems:
            print("  - " + p)
        if not args.unit:
            return 2

    selected = [u for u in CFG.UNITS if not args.unit or u["name"] in args.unit]
    tmp = tempfile.mkdtemp(prefix="archetype-ts-")
    results: dict[str, tuple[bool, str]] = {}
    try:
        if any(u.get("prisma") for u in selected):
            ok, out = prisma_generate(tmp)
            if not ok:
                print("FAIL  prisma generate (harness schema)\n" + out)
                return 1
        built = {u["name"]: build_unit(u, by_ref, tmp) for u in selected}
        with cf.ThreadPoolExecutor(max_workers=args.jobs) as ex:
            futs = {ex.submit(check_unit, u, *built[u["name"]], not args.no_run): u["name"] for u in selected}
            for fut in cf.as_completed(futs):
                results[futs[fut]] = fut.result()
    finally:
        if args.keep:
            print(f"(kept {tmp})")
        else:
            shutil.rmtree(tmp, ignore_errors=True)

    n_pass = n_fail = 0
    for u in selected:
        ok, out = results[u["name"]]
        files = sorted({os.path.basename(by_ref[r].relfile) for r in u["blocks"]})
        blocks_desc = f"{len(u['blocks'])} blocks from {', '.join(files)}"
        if ok:
            n_pass += 1
            print(f"PASS  {u['name']}  ({blocks_desc})" + (f"  [{out}]" if out.startswith(("vitest: ", "prisma validate: ", "node probe: ", "node --test: ")) else ""))
        else:
            n_fail += 1
            print(f"FAIL  {u['name']}  ({blocks_desc})")
            print("\n".join("      " + l for l in out.splitlines()))
    compiled = sorted({r for u in selected for r in u["blocks"]})
    print()
    print(f"units: {n_pass} PASS / {n_fail} FAIL ; blocks compiled: {len(compiled)} ; "
          f"blocks skipped: {len(CFG.SKIP)} ; total TS blocks: {len(by_ref)}")
    if not args.unit:
        for ref, reason in sorted(CFG.SKIP.items()):
            print(f"SKIP  {ref}: {reason}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
