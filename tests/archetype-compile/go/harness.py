#!/usr/bin/env python3
"""Compile-check every Go block in .claude/skills/** — the backend archetypes and every other pack.

Driven by units.json. For each unit it assembles a throwaway Go module (module path `yourapp`, the
path the samples import) from the markdown blocks, as they are in the .md files right now, plus the
stubs listed for the unit, then runs:

    go build ./...                       (with -gcflags=-e: every type error, not the first ten)
    go test -count=1 -exec true ./...    (compiles and links the test binaries without running them)
    go vet ./...
    go test -count=1 <pkgs>              (units that list "run_tests": no external service needed)
    go test ... "db_tests"               (ARCHETYPE_DB_TESTS=1: testcontainers start Docker containers)
    go test ... "pact_tests"             (ARCHETYPE_PACT_TESTS=1, CGO_ENABLED=1: needs libpact_ffi,
                                          e.g. `pact-go -l DEBUG install --libDir /tmp`, and a cgo
                                          linker; on macOS 27 with Command Line Tools 27, whose ld
                                          can't read the 27.0 SDK, set SDKROOT to MacOSX26.5.sdk)

Files are named by key: an archetype by its base name ("crud-handler-go.md"), any other skill file
by its path under .claude/skills ("languages/go.md").

Block assembly:
  * A file whose first block starts with a `package` clause is written verbatim (blocks after it are
    appended): its import list is the sample's own, so a missing or unused import fails the unit.
  * A file whose first block has no package clause is a fragment. The unit gives its package; the
    import block is computed with goimports (pinned in go.mod) from the unit's candidate list, and
    the code is written exactly as in the markdown.
  * A "wrap" file puts a statement-level snippet inside the function the unit names, e.g.
    `func _(ctx context.Context, tx pgx.Tx)`: its parameters declare what the snippet assumes, so
    every call is still type-checked against the real API. Import lines at the top of the snippet are
    hoisted to the file. "prelude"/"postlude" add harness lines before/after the snippet (e.g. the
    `return` a snippet that ends mid-function leaves out).
  * Every block is preceded by a `//line <file>.md:<line>` directive, so compiler and vet messages
    point at the markdown line.

Inventory: every ```go block in .claude/skills/** must be claimed by a unit or listed in "skip" with a
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

REF_RE = re.compile(r"^(?P<md>[\w./-]+\.md)#(?P<a>\d+)(?:-(?P<b>\d+))?$")
IMPORT_BLOCK_RE = re.compile(r"^import \((.*?)^\)\n|^import (\"[^\"]+\"|\w+ \"[^\"]+\")[ \t]*(//[^\n]*)?\n", re.S | re.M)
STUB_HEADER = "// HARNESS STUB (tests/archetype-compile/go, units.json) — not skill-pack code.\n"

ARCH_DIR = SKILLS_DIR = None  # set in main()


def fail(msg):
    print(f"FAIL  {msg}")


def load_config():
    with open(os.path.join(HERE, "units.json"), encoding="utf-8") as f:
        return json.load(f)


def path_of(key):
    """An archetype key is a base name; any other skill file is keyed by its path under skills/."""
    return os.path.join(SKILLS_DIR if "/" in key else ARCH_DIR, key)


def expand(ref):
    m = REF_RE.match(ref)
    if not m:
        raise SystemExit(f"units.json: bad block reference {ref!r} (want file.md#N or file.md#N-M)")
    a = int(m.group("a"))
    b = int(m.group("b") or a)
    return [(m.group("md"), i) for i in range(a, b + 1)]


def is_comment_only(block):
    return all(not l.strip() or l.strip().startswith("//") for l in block.text.split("\n"))


def scan():
    """Every markdown file under .claude/skills with Go blocks, keyed as in units.json."""
    found = {}
    for name in sorted(os.listdir(ARCH_DIR)):
        if name.endswith(".md"):
            bs = mdblocks.blocks(os.path.join(ARCH_DIR, name), name=name)
            if bs:
                found[name] = bs
    for root, dirs, files in os.walk(SKILLS_DIR):
        dirs.sort()
        if os.path.abspath(root).startswith(os.path.abspath(ARCH_DIR)):
            continue
        for name in sorted(files):
            if name.endswith(".md"):
                key = os.path.relpath(os.path.join(root, name), SKILLS_DIR)
                bs = mdblocks.blocks(os.path.join(root, name), name=key)
                if bs:
                    found[key] = bs
    return found


def inventory(cfg):
    """Check every skill-pack Go block against units.json. Returns (blocks_by_ref, problems)."""
    found = scan()
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
            for ref in fe.get("blocks", []):
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


def line_directive(b):
    return f"//line {path_of(b.md)}:{b.first_line}\n"


def shorten(text):
    """Print markdown positions as `file.md:line` / `dir/file.md:line` instead of absolute paths."""
    return text.replace(ARCH_DIR + os.sep, "").replace(SKILLS_DIR + os.sep, "")


def hoist_imports(text):
    """Split leading import declarations off a snippet. The removed lines become blank lines, so the
    //line mapping of the remaining code is unchanged."""
    lines = text.split("\n")
    hoisted, i = [], 0
    while i < len(lines):
        s = lines[i].strip()
        if not s or s.startswith("//"):
            i += 1
            continue
        if s.startswith("import ("):
            j = i
            while j < len(lines) and lines[j].strip() != ")":
                j += 1
            hoisted.extend(lines[i:j + 1])
            for k in range(i, j + 1):
                lines[k] = ""
            i = j + 1
            continue
        if s.startswith("import "):
            hoisted.append(lines[i])
            lines[i] = ""
            i += 1
            continue
        break
    return "\n".join(hoisted), "\n".join(lines)


def assemble(unit, by_ref, root, tools_env):
    """Write one unit's module under root. Returns (fragment_files, error)."""
    for f in ("go.mod", "go.sum"):
        shutil.copy(os.path.join(HERE, f), os.path.join(root, f))
    fragments, stubs = [], []
    for fe in unit["files"]:
        path = os.path.join(root, fe["path"])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if "code" in fe:  # an inline harness stub
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"{STUB_HEADER}\npackage {fe['package']}\n\n{fe['code']}\n")
            stubs.append(path)
            continue
        blocks = [by_ref[f"{md}#{i}"] for ref in fe["blocks"] for md, i in expand(ref)]
        head = blocks[0]
        for b in blocks[1:]:
            if b.package:
                return None, f"{fe['path']}: {b.ref()} has its own package clause; give it its own file"
        if fe.get("wrap") or not head.package:
            # A fragment's own import lines move to the file header (goimports then sees one import
            # area); their lines stay as blanks so the //line mapping is unchanged.
            hoisted, parts = [], []
            for b in blocks:
                imp, code = hoist_imports(b.text)
                hoisted.append(imp)
                parts.append(line_directive(b) + code)
            extra = "\n".join(h for h in hoisted if h)
            if fe.get("wrap"):
                body = (f"{fe['wrap']} {{\n{fe.get('prelude', '')}\n" + "".join(parts)
                        + f"{fe.get('postlude', '')}\n}}\n")
            else:
                body = "".join(parts)
        else:
            body = "".join(line_directive(b) + b.text for b in blocks)
            extra = ""
        if head.package and not fe.get("wrap"):
            if fe.get("package") and fe["package"] != head.package:
                return None, f"{fe['path']}: {head.ref()} declares package {head.package}, units.json says {fe['package']}"
            with open(path, "w", encoding="utf-8") as f:
                f.write(body)
        else:
            if not fe.get("package"):
                return None, f"{fe['path']}: {head.ref()} is a fragment (no package clause); units.json must give 'package'"
            # a candidate the fragment imports itself would be declared twice
            cands = [c for c in unit.get("imports", []) + fe.get("imports", [])
                     if f'"{c.split()[-1].strip(chr(34))}"' not in extra]
            imp = "import (\n" + "".join(f"\t{c}\n" if " " in c else f"\t\"{c}\"\n" for c in cands) + ")\n" if cands else ""
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"package {fe['package']}\n\n{imp}{extra}\n{body}")
            fragments.append((path, fe["package"], body))
    for dst, src in unit.get("stubs", {}).items():
        d = os.path.join(root, dst)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        if isinstance(src, dict):  # a stub template: `package PKG` becomes the given package
            text = open(os.path.join(HERE, src["from"]), encoding="utf-8").read()
            text = re.sub(r"^package PKG$", f"package {src['package']}", text, count=1, flags=re.M)
            with open(d, "w", encoding="utf-8") as f:
                f.write(text)
        else:
            shutil.copy(os.path.join(HERE, src), d)
    if unit.get("protoc"):
        err = protoc(unit["protoc"], root, tools_env)
        if err:
            return None, err
    if unit.get("sql_migrations"):
        err = sql_migrations(unit["sql_migrations"], root)
        if err:
            return None, err
    if stubs:
        rc, out = run(["go", "tool", "goimports", "-w"] + stubs, root, tools_env)
        if rc != 0:
            return None, "goimports failed on an inline stub:\n" + out
    for spec in unit.get("mockgen", []):  # mocks generated from the (stubbed) interfaces, as a project would
        dst = os.path.join(root, spec["destination"])
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        rc, out = run(["go", "tool", "mockgen", f"-source={spec['source']}", f"-destination={spec['destination']}",
                       f"-package={spec['package']}"], root, tools_env)
        if rc != 0:
            return None, f"mockgen {spec['source']} failed:\n{out}"
    if fragments:
        # goimports computes each fragment's import block; the code itself is written back untouched
        # so the //line mapping stays exact.
        rc, out = run(["go", "tool", "goimports", "-w"] + [p for p, _, _ in fragments], root, tools_env)
        if rc != 0:
            return None, "goimports failed (usually a syntax error in a fragment):\n" + shorten(out)
        for path, pkg, body in fragments:
            with open(path, encoding="utf-8") as f:
                formatted = f.read()
            # The import declarations come before the first top-level declaration. go/printer can
            # pull a //line directive (and a comment after it) into the import block when the
            # snippet starts with a comment; those lines belong to the body, which is written back
            # as-is, so they are dropped here.
            first_decl = re.search(r"^(func|type|var|const)\b", formatted, re.M)
            header = formatted[:first_decl.start()] if first_decl else formatted.split("//line ", 1)[0]
            imports = "".join(m.group(0) for m in IMPORT_BLOCK_RE.finditer(header))
            imports = "\n".join(re.sub(r"\s*//line .*$", "", l) for l in imports.split("\n")
                                if not l.strip().startswith("//"))
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
    def args(pkgs):  # "./pkg/" or ["./pkg/", "-run", "^TestX$"]
        return pkgs if isinstance(pkgs, list) else [pkgs]

    cgo_env = dict(env, CGO_ENABLED="1")
    if unit.get("cgo_typecheck_only"):
        # The package links a native library through cgo (pact-go: libpact_ffi). `go vet` runs cgo
        # and type-checks every file, tests included, without linking — so the API use is checked
        # against the pinned module even where the library isn't installed. "pact_tests" below
        # links and runs them when it is.
        steps = [(["go", "vet", "./..."], cgo_env)]
    else:
        steps = [(["go", "build", "-gcflags=-e", "./..."], env)]
        if unit.get("tests", False):
            # -exec true links every test binary without running it: `-run '^$'` alone still executes
            # TestMain, and crud-repository-test-go.md's TestMain starts a Postgres container, which
            # made the default (Docker-free) run depend on Docker.
            steps.append((["go", "test", "-count=1", "-exec", "true", "-gcflags=-e", "./..."], env))
        steps.append((["go", "vet", "./..."], env))
    for pkgs in unit.get("run_tests", []):
        steps.append((["go", "test", "-count=1"] + args(pkgs), env))
    for pkgs in unit.get("bench_once", []):  # run each benchmark body once: it must not fail
        steps.append((["go", "test", "-count=1", "-run", "^$", "-bench", ".", "-benchtime", "1x", pkgs], env))
    if os.environ.get("ARCHETYPE_DB_TESTS") == "1":  # Docker: testcontainers start postgres/redis/...
        for pkgs in unit.get("db_tests", []):
            steps.append((["go", "test", "-count=1", "-p=1"] + args(pkgs), env))
    if os.environ.get("ARCHETYPE_PACT_TESTS") == "1":  # libpact_ffi installed + a working cgo linker
        for pkgs in unit.get("pact_tests", []):
            steps.append((["go", "test", "-count=1", "-p=1"] + args(pkgs), cgo_env))
    for cmd, step_env in steps:
        rc, out = run(cmd, root, step_env)
        if rc != 0:
            return False, f"$ {' '.join(cmd)}\n{shorten(out)}"
    return True, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true", help="keep the assembled units (path is printed)")
    ap.add_argument("--only", nargs="*", help="check only these units")
    ap.add_argument("--inventory-only", action="store_true", help="check block coverage, compile nothing")
    ap.add_argument("--partial", action="store_true", help=argparse.SUPPRESS)  # development: warn, don't stop
    args = ap.parse_args()

    cfg = load_config()
    global ARCH_DIR, SKILLS_DIR
    ARCH_DIR = os.path.join(REPO, cfg["archetypes_dir"])
    SKILLS_DIR = os.path.join(REPO, cfg["skills_dir"])
    by_ref, problems = inventory(cfg)
    n_arch = sum(1 for k in cfg["files"] if "/" not in k)
    print(f"Inventory: {len(by_ref)} Go blocks in {len(cfg['files'])} skill files "
          f"({n_arch} backend archetypes + {len(cfg['files']) - n_arch} other packs); "
          f"{len(cfg['skip'])} skipped with a reason")
    for p in problems:
        fail(f"inventory: {p}")
    if problems and not args.partial:
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
            ran_pkgs = [" ".join(p) if isinstance(p, list) else p for p in unit.get("run_tests", [])]
            ran_pkgs += [f"bench {p}" for p in unit.get("bench_once", [])]
            if unit.get("cgo_typecheck_only"):
                ran_pkgs.append("type-check only: cgo")
            if os.environ.get("ARCHETYPE_DB_TESTS") == "1":
                ran_pkgs += [f"DB {' '.join(p) if isinstance(p, list) else p}" for p in unit.get("db_tests", [])]
            if os.environ.get("ARCHETYPE_PACT_TESTS") == "1":
                ran_pkgs += [f"pact {' '.join(p) if isinstance(p, list) else p}" for p in unit.get("pact_tests", [])]
            ran = f" (+ ran {', '.join(ran_pkgs)})" if ran_pkgs else ""
            print(f"PASS  {unit['name']}{ran}")
        else:
            failed += 1
            print(f"FAIL  {unit['name']}\n" + "\n".join("      " + l for l in out.split("\n")))
    print(f"\n{passed} PASS / {failed} FAIL / {len(cfg['skip'])} blocks skipped "
          f"({len(by_ref)} Go blocks, Go {subprocess.run(['go', 'env', 'GOVERSION'], capture_output=True, text=True).stdout.strip()})")
    if args.keep or failed:
        print(f"Assembled units kept in {workdir}")
    else:
        shutil.rmtree(workdir, ignore_errors=True)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
