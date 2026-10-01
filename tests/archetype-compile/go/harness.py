#!/usr/bin/env python3
"""Compile-check every Go block in .claude/skills/backend/archetypes/*.md.

Driven by units.json. For each unit it assembles a throwaway Go module (module path `yourapp`, the
path the samples import) from the markdown blocks, as they are in the .md files right now, plus the
stubs listed for the unit, then runs:

    go vet ./...                         (type-checks packages and their tests)
    go build ./...
    go test -count=1 -run '^$' ./...     (compiles and links the test binaries)
    go test -count=1 <pkgs>              (only for units that list "run_tests": mock-based, no DB)

Block assembly:
  * A file whose first block starts with a `package` clause is written verbatim (blocks after it are
    appended): its import list is the sample's own, so a missing or unused import fails the unit.
  * A file whose first block has no package clause is a fragment. The unit gives its package; the
    import block is computed with goimports (pinned in go.mod) from the unit's candidate list, and
    the code is written exactly as in the markdown.
  * Every block is preceded by a `//line <file>.md:<line>` directive, so compiler and vet messages
    point at the markdown line.

Inventory: every ```go block in every archetype must be claimed by a unit or listed in "skip" with a
reason, the block count and headings per file must match units.json (so an inserted or reordered
block fails loudly instead of compiling the wrong code), and a "comment-only" skip must really be
comment-only.

Usage: harness.py [--keep] [--only UNIT ...] [--inventory-only]
Exit status: 0 = every unit PASS and the inventory is complete; 1 otherwise.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True  # no __pycache__ in the repo
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
import mdblocks  # noqa: E402

REF_RE = re.compile(r"^(?P<md>[\w.-]+\.md)#(?P<a>\d+)(?:-(?P<b>\d+))?$")
IMPORT_BLOCK_RE = re.compile(r"^import \((.*?)^\)\n|^import (\"[^\"]+\"|\w+ \"[^\"]+\")\n", re.S | re.M)


def fail(msg):
    print(f"FAIL  {msg}")


def load_config():
    with open(os.path.join(HERE, "units.json"), encoding="utf-8") as f:
        return json.load(f)


def expand(ref):
    m = REF_RE.match(ref)
    if not m:
        raise SystemExit(f"units.json: bad block reference {ref!r} (want file.md#N or file.md#N-M)")
    a = int(m.group("a"))
    b = int(m.group("b") or a)
    return [(m.group("md"), i) for i in range(a, b + 1)]


def is_comment_only(block):
    return all(not l.strip() or l.strip().startswith("//") for l in block.text.split("\n"))


def inventory(cfg):
    """Check the archetype Go blocks against units.json. Returns (blocks_by_ref, problems)."""
    arch = os.path.join(REPO, cfg["archetypes_dir"])
    found = {}
    for name in sorted(os.listdir(arch)):
        if name.endswith(".md"):
            bs = mdblocks.blocks(os.path.join(arch, name))
            if bs:
                found[name] = bs
    problems = []
    files = cfg["files"]
    for name, bs in found.items():
        if name not in files:
            problems.append(f"{name}: has {len(bs)} Go block(s) but no entry in units.json 'files'")
            continue
        want = files[name]
        if len(want) != len(bs):
            problems.append(f"{name}: has {len(bs)} Go blocks, units.json expects {len(want)} — "
                            "a block was added or removed; update units.json so nothing escapes")
            continue
        for b, heading in zip(bs, want):
            if b.heading != heading:
                problems.append(f"{name}#{b.index} (line {b.first_line}): heading is {b.heading!r}, "
                                f"units.json expects {heading!r} — blocks moved; update units.json")
    for name in files:
        if name not in found:
            problems.append(f"{name}: listed in units.json but has no Go blocks (or no longer exists)")
    by_ref = {b.ref(): b for bs in found.values() for b in bs}

    claimed = {}
    for unit in cfg["units"]:
        for fe in unit["files"]:
            for ref in fe["blocks"]:
                for md, i in expand(ref):
                    key = f"{md}#{i}"
                    if key not in by_ref:
                        problems.append(f"unit {unit['name']}: {key} does not exist")
                    claimed.setdefault(key, []).append(unit["name"])
    for key, reason in cfg["skip"].items():
        if key not in by_ref:
            problems.append(f"skip {key}: no such block")
            continue
        if not reason.strip():
            problems.append(f"skip {key}: a skip needs a reason")
        if reason.startswith("comment-only") and not is_comment_only(by_ref[key]):
            problems.append(f"skip {key}: marked comment-only but now contains code — compile it")
        if key in claimed:
            problems.append(f"{key}: both skipped and compiled by {claimed[key]}")
    for key, b in by_ref.items():
        if b.md in files and key not in claimed and key not in cfg["skip"]:
            problems.append(f"{key} (line {b.first_line}, [{b.heading}]): neither compiled by a unit "
                            "nor skipped with a reason")
    return by_ref, problems


def run(cmd, cwd, env=None):
    p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


ARCH_DIR = None  # set in main(): absolute archetypes dir, so //line paths resolve from any unit dir


def line_directive(b):
    return f"//line {os.path.join(ARCH_DIR, b.md)}:{b.first_line}\n"


def shorten(text):
    """Print markdown positions as `file.md:line` instead of the absolute path."""
    return text.replace(ARCH_DIR + os.sep, "")


def assemble(unit, by_ref, root, tools_env):
    """Write one unit's module under root. Returns (fragment_files, error)."""
    for f in ("go.mod", "go.sum"):
        shutil.copy(os.path.join(HERE, f), os.path.join(root, f))
    fragments = []
    for fe in unit["files"]:
        blocks = [by_ref[f"{md}#{i}"] for ref in fe["blocks"] for md, i in expand(ref)]
        path = os.path.join(root, fe["path"])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        head = blocks[0]
        for b in blocks[1:]:
            if b.package:
                return None, f"{fe['path']}: {b.ref()} has its own package clause; give it its own file"
        body = "".join(line_directive(b) + b.text for b in blocks)
        if head.package:
            if fe.get("package") and fe["package"] != head.package:
                return None, f"{fe['path']}: {head.ref()} declares package {head.package}, units.json says {fe['package']}"
            with open(path, "w", encoding="utf-8") as f:
                f.write(body)
        else:
            if not fe.get("package"):
                return None, f"{fe['path']}: {head.ref()} is a fragment (no package clause); units.json must give 'package'"
            cands = unit.get("imports", []) + fe.get("imports", [])
            imp = "import (\n" + "".join(f"\t{c}\n" if " " in c else f"\t\"{c}\"\n" for c in cands) + ")\n" if cands else ""
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"package {fe['package']}\n\n{imp}\n{body}")
            fragments.append((path, fe["package"], body))
    for dst, src in unit.get("stubs", {}).items():
        d = os.path.join(root, dst)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copy(os.path.join(HERE, src), d)
    if unit.get("protoc"):
        err = protoc(unit["protoc"], root, tools_env)
        if err:
            return None, err
    if unit.get("sql_migrations"):
        err = sql_migrations(unit["sql_migrations"], root)
        if err:
            return None, err
    if fragments:
        # goimports computes each fragment's import block; the code itself is written back untouched
        # so the //line mapping stays exact.
        rc, out = run(["go", "tool", "goimports", "-w"] + [p for p, _, _ in fragments], root, tools_env)
        if rc != 0:
            return None, "goimports failed (usually a syntax error in a fragment):\n" + out
        for path, pkg, body in fragments:
            with open(path, encoding="utf-8") as f:
                formatted = f.read()
            imports = "".join(m.group(0) for m in IMPORT_BLOCK_RE.finditer(formatted.split("//line ", 1)[0]))
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"package {pkg}\n\n{imports}\n{body}")
    return fragments, None


def sql_migrations(spec, root):
    """Write the ```sql blocks that start with `-- Migration: <file>.sql` into the unit, so the Go
    code that embeds and runs them runs the documented SQL itself."""
    out = os.path.join(root, spec["out"])
    os.makedirs(out, exist_ok=True)
    written = 0
    for b in mdblocks.blocks(os.path.join(REPO, spec["md"]), lang="sql"):
        m = re.match(r"^--\s*Migration:\s*(\S+\.sql)\s*$", b.text.split("\n", 1)[0])
        if not m:
            continue
        name = m.group(1)
        if os.path.exists(os.path.join(out, name)):
            return f"{spec['md']}: two SQL blocks claim {name}"
        with open(os.path.join(out, name), "w", encoding="utf-8") as f:
            f.write(b.text)
        written += 1
    if written < spec.get("min", 1):
        return f"{spec['md']}: found {written} '-- Migration:' SQL blocks, expected at least {spec.get('min', 1)}"
    return None


def protoc(spec, root, env):
    """Generate Go code from the protobuf blocks of a (language-neutral) archetype, with the pinned
    protoc-gen-go / protoc-gen-go-grpc plugins driven by testdata/protogen (no system protoc)."""
    md = os.path.join(REPO, spec["md"])
    blocks = mdblocks.blocks(md, lang="protobuf")
    files = []
    for i in spec["blocks"]:
        b = blocks[i - 1]
        first = b.text.split("\n", 1)[0].strip()
        m = re.match(r"^//\s*(proto/\S+\.proto)\s*$", first)
        if not m:
            return f"{spec['md']} protobuf block {i}: first line must name its file (// proto/…/x.proto)"
        dst = os.path.join(root, m.group(1))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "w", encoding="utf-8") as f:
            f.write(b.text)
        files.append(os.path.relpath(dst, os.path.join(root, "proto")))
    bindir = env["HARNESS_BIN"]
    cmd = [os.path.join(bindir, "protogen"), "-I", "proto", "-out", spec["out"],
           "-opt", "paths=source_relative",
           "-plugin", f"protoc-gen-go={bindir}/protoc-gen-go",
           "-plugin", f"protoc-gen-go-grpc={bindir}/protoc-gen-go-grpc"] + files
    rc, text = run(cmd, root, env)
    if rc != 0:
        return f"proto generation failed on the {spec['md']} protobuf blocks:\n{text}"
    return None


def check_unit(unit, by_ref, workdir, env):
    root = os.path.join(workdir, unit["name"])
    os.makedirs(root)
    _, err = assemble(unit, by_ref, root, env)
    if err:
        return False, err
    # -gcflags=-e: report every type error, not the first ten.
    steps = [["go", "build", "-gcflags=-e", "./..."]]
    if unit.get("tests", False):
        steps.append(["go", "test", "-count=1", "-run", "^$", "-gcflags=-e", "./..."])
    steps.append(["go", "vet", "./..."])
    for pkgs in unit.get("run_tests", []):
        steps.append(["go", "test", "-count=1", pkgs])
    for pkgs in unit.get("bench_once", []):  # run each benchmark body once: it must not fail
        steps.append(["go", "test", "-count=1", "-run", "^$", "-bench", ".", "-benchtime", "1x", pkgs])
    if os.environ.get("ARCHETYPE_DB_TESTS") == "1":
        for pkgs in unit.get("db_tests", []):
            steps.append(["go", "test", "-count=1", "-p=1", pkgs])
    for cmd in steps:
        rc, out = run(cmd, root, env)
        if rc != 0:
            return False, f"$ {' '.join(cmd)}\n{shorten(out)}"
    return True, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true", help="keep the assembled units (path is printed)")
    ap.add_argument("--only", nargs="*", help="check only these units")
    ap.add_argument("--inventory-only", action="store_true", help="check block coverage, compile nothing")
    args = ap.parse_args()

    cfg = load_config()
    global ARCH_DIR
    ARCH_DIR = os.path.join(REPO, cfg["archetypes_dir"])
    by_ref, problems = inventory(cfg)
    total = sum(len(v) for v in cfg["files"].values())
    print(f"Inventory: {len(by_ref)} Go blocks in {len(cfg['files'])} archetype files; "
          f"{len(cfg['skip'])} skipped with a reason")
    for p in problems:
        fail(f"inventory: {p}")
    if problems:
        print(f"\nInventory incomplete ({len(problems)} problem(s)) — nothing compiled.")
        return 1
    for key, reason in sorted(cfg["skip"].items()):
        print(f"SKIP  {key} — {reason}")
    if args.inventory_only:
        return 0

    workdir = tempfile.mkdtemp(prefix="archetype-go-")
    # -mod=readonly (the default): an import no pinned module provides fails instead of being fetched.
    # CGO_ENABLED=0: static, pure-Go builds (what dockerfile-go.md ships), and no dependence on the
    # host's C linker.
    env = dict(os.environ, GOWORK="off", GOTOOLCHAIN="local", CGO_ENABLED="0")
    bindir = os.path.join(workdir, "_bin")
    for tool in ("google.golang.org/protobuf/cmd/protoc-gen-go", "google.golang.org/grpc/cmd/protoc-gen-go-grpc",
                 "./testdata/protogen"):
        rc, out = run(["go", "build", "-o", bindir + "/", tool], HERE, env)
        if rc != 0:
            fail(f"building {tool}: {out}")
            return 1
    env["HARNESS_BIN"] = bindir

    units = [u for u in cfg["units"] if not args.only or u["name"] in args.only]
    passed = failed = 0
    for unit in units:
        ok, out = check_unit(unit, by_ref, workdir, env)
        if ok:
            passed += 1
            ran_pkgs = unit.get("run_tests", []) + [f"bench {p}" for p in unit.get("bench_once", [])]
            if os.environ.get("ARCHETYPE_DB_TESTS") == "1":
                ran_pkgs += [f"DB {p}" for p in unit.get("db_tests", [])]
            ran = f" (+ ran {', '.join(ran_pkgs)})" if ran_pkgs else ""
            print(f"PASS  {unit['name']}{ran}")
        else:
            failed += 1
            print(f"FAIL  {unit['name']}\n" + "\n".join("      " + l for l in out.split("\n")))
    print(f"\n{passed} PASS / {failed} FAIL / {len(cfg['skip'])} blocks skipped "
          f"({total} Go blocks, Go {subprocess.run(['go', 'env', 'GOVERSION'], capture_output=True, text=True).stdout.strip()})")
    if args.keep or failed:
        print(f"Assembled units kept in {workdir}")
    else:
        shutil.rmtree(workdir, ignore_errors=True)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
