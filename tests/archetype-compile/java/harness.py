#!/usr/bin/env python3
"""Archetype Java compile harness — extraction, layout and reporting.

  harness.py inventory                  check units.py covers every ```java block (no JDK needed)
  harness.py layout <dir>               write the Maven reactor (+ Gradle snippet projects) into <dir>
  harness.py report <dir> <maven-log>   PASS/FAIL per unit, compiler errors mapped back to markdown lines

Blocks are read from the markdown at run time, so a later doc edit is re-verified. units.py says how each
block is laid out (a whole compilation unit, members wrapped in a class, statements wrapped in a method,
or inserted into another block's class) and which Maven module ("unit") compiles it. Stubs under stubs/
stand in for application types the samples leave undefined (repositories, clients, DTOs); they never
stand in for a library API a sample demonstrates.
"""
import json
import os
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ARCH = ROOT / ".claude" / "skills" / "backend" / "archetypes"
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True  # no __pycache__ in the repo
import units as U  # noqa: E402

FENCE = re.compile(r"^```([A-Za-z0-9_+-]*)\s*$")
JVM_LANGS = {"java", "kotlin", "groovy", "xml", "scala"}   # non-Java ones: BUILD_SNIPPETS or SKIP


# ─────────────────────────────── markdown extraction ───────────────────────────────

class Block:
    def __init__(self, md, lang, index, first_line, lines):
        self.md, self.lang, self.index = md, lang, index      # index: 1-based among blocks of this lang
        self.first_line = first_line                            # md line number of the block's first line
        self.lines = lines

    @property
    def id(self):
        return f"{self.md}#{self.index}" if self.lang == "java" else f"{self.md}#{self.lang}{self.index}"

    def md_line(self, i):
        return self.first_line + i


def read_blocks(md_name):
    """All fenced blocks of a markdown file, by language, in order."""
    text = (ARCH / md_name).read_text(encoding="utf-8").split("\n")
    out, counters, i = [], {}, 0
    while i < len(text):
        m = FENCE.match(text[i])
        if m and m.group(1):
            lang = m.group(1)
            j = i + 1
            while j < len(text) and not text[j].startswith("```"):
                j += 1
            counters[lang] = counters.get(lang, 0) + 1
            out.append(Block(md_name, lang, counters[lang], i + 2, text[i + 1:j]))
            i = j
        i += 1
    return out


_cache = {}


def block(block_id):
    md, _, sel = block_id.partition("#")
    if md not in _cache:
        _cache[md] = read_blocks(md)
    m = re.match(r"([a-z]*)(\d+)$", sel)
    lang, idx = (m.group(1) or "java"), int(m.group(2))
    for b in _cache[md]:
        if b.lang == lang and b.index == idx:
            return b
    raise SystemExit(f"FAIL config: {block_id} does not exist (the markdown changed — update units.py)")


# ─────────────────────────────── inventory ───────────────────────────────

def inventory():
    """Every ```java block in every archetype is compiled by exactly one unit or skipped with a reason."""
    errors = []
    found = {}
    for md in sorted(p.name for p in ARCH.glob("*.md")):
        blocks = read_blocks(md)
        n = sum(1 for b in blocks if b.lang == "java")
        jvm = [b for b in blocks if b.lang in JVM_LANGS - {"java"}] if md.endswith("-java.md") else []
        if n or md in U.JAVA_BLOCKS:
            found[md] = n
            want = U.JAVA_BLOCKS.get(md)
            if want is None:
                errors.append(f"{md}: {n} ```java blocks but units.py has no JAVA_BLOCKS entry")
            elif want != n:
                errors.append(f"{md}: units.py expects {want} ```java blocks, the file has {n} "
                              f"(blocks were added/removed — re-map them in units.py)")
        for b in jvm:
            if b.id not in U.BUILD_SNIPPETS and b.id not in U.SKIP:
                errors.append(f"{b.id} ({b.lang}, line {b.first_line - 1}): JVM build/config block is neither "
                              f"checked (BUILD_SNIPPETS) nor skipped (SKIP) in units.py")

    owners = {}
    for unit in U.UNITS:
        for bid in unit.own:
            owners.setdefault(bid, []).append(unit.name)
    for md, n in found.items():
        for i in range(1, n + 1):
            bid = f"{md}#{i}"
            own = owners.get(bid, [])
            if bid in U.SKIP:
                if own:
                    errors.append(f"{bid}: both skipped and compiled by {own}")
                if not U.SKIP[bid].strip():
                    errors.append(f"{bid}: skipped without a reason")
            elif not own:
                errors.append(f"{bid} (line {block(bid).first_line - 1}): not compiled by any unit and not skipped")
            elif len(own) > 1:
                errors.append(f"{bid}: owned by several units {own} — own it once, list it as a dep elsewhere")
    for bid in list(owners) + list(U.SKIP) + [dep_id(d) for u in U.UNITS for d in u.deps]:
        md = bid.partition("#")[0]
        if not (ARCH / md).exists():
            errors.append(f"{bid}: {md} does not exist")
        else:
            block(bid)  # raises if the index is gone
    return found, errors


# ─────────────────────────────── Java text scanning ───────────────────────────────

TYPE_DECL = re.compile(r"\b(class|interface|enum|record)\s+([A-Z]\w*)")
IMPORT = re.compile(r"^\s*import\s+(static\s+)?[\w.]+(\.\*)?\s*;\s*(//.*)?$")


def strip_code(lines):
    """Per line: the code with comments removed and string/char/text-block contents blanked, so braces and
    parentheses can be counted."""
    out = []
    in_block = in_text = False
    for line in lines:
        code, i, n = [], 0, len(line)
        while i < n:
            c = line[i]
            if in_block:
                if line.startswith("*/", i):
                    in_block = False
                    i += 2
                else:
                    i += 1
                continue
            if in_text:
                if line.startswith('"""', i):
                    in_text = False
                    code.append('"')
                    i += 3
                else:
                    i += 1
                continue
            if line.startswith("//", i):
                break
            if line.startswith("/*", i):
                in_block = True
                i += 2
                continue
            if line.startswith('"""', i):
                in_text = True
                code.append('"')
                i += 3
                continue
            if c == '"':
                j = i + 1
                while j < n and line[j] != '"':
                    j += 2 if line[j] == "\\" else 1
                code.append('""')
                i = j + 1
                continue
            if c == "'":
                j = i + 1
                while j < n and line[j] != "'":
                    j += 2 if line[j] == "\\" else 1
                code.append("' '")
                i = j + 1
                continue
            code.append(c)
            i += 1
        out.append("".join(code))
    return out


def chunks(lines):
    """Split source lines into top-level chunks: (kind, start, end_exclusive, name).
    kind: package | import | type | member (a method/field/statement at top level) | blank."""
    code = strip_code(lines)
    res, start, paren, brace = [], 0, 0, 0
    for i, c in enumerate(code):
        for ch in c:
            if ch == "(":
                paren += 1
            elif ch == ")":
                paren -= 1
            elif ch == "{":
                brace += 1
            elif ch == "}":
                brace -= 1
        text = "\n".join(code[start:i + 1]).strip()
        if paren or brace or not text:
            continue
        # a top-level construct ends here if it closed a body or ended with ';'
        if not (c.rstrip().endswith("}") or c.rstrip().endswith(";")):
            continue
        res.append(classify(lines, code, start, i + 1))
        start = i + 1
    if start < len(lines):
        tail = "\n".join(code[start:]).strip()
        res.append(classify(lines, code, start, len(lines)) if tail else ("blank", start, len(lines), None))
    return res


def head_of(text):
    """Text before the first '{' outside parentheses (skips annotation arrays like @Table(indexes = {...}))."""
    depth = 0
    for k, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "{" and depth == 0:
            return text[:k]
    return text


def strip_annotations(text):
    """Remove annotations, including arguments with nested parentheses, before looking for `class X`."""
    out, i, n = [], 0, len(text)
    while i < n:
        m = re.match(r"@(?!interface\b)\w+(\.\w+)*", text[i:])
        if text[i] == "@" and m:
            i += m.end()
            j = i
            while j < n and text[j].isspace():
                j += 1
            if j < n and text[j] == "(":
                depth = 0
                while j < n:
                    depth += (text[j] == "(") - (text[j] == ")")
                    j += 1
                    if depth == 0:
                        break
                i = j
            out.append(" ")
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


def classify(lines, code, s, e):
    text = "\n".join(code[s:e])
    stripped = text.strip()
    head = head_of(stripped)
    head_no_ann = strip_annotations(head)
    if re.fullmatch(r"\s*package\s+[\w.]+\s*;\s*", stripped):
        return ("package", s, e, re.search(r"package\s+([\w.]+)", stripped).group(1))
    if re.fullmatch(r"(\s*import\s+(static\s+)?[\w.]+(\.\*)?\s*;\s*)+", stripped):
        return ("import", s, e, None)
    m = TYPE_DECL.search(head_no_ann)
    if m and "{" in stripped and "=" not in head_no_ann.split(m.group(0))[0]:
        before = head_no_ann[:m.start()]
        # a method returning a type named like a class would still have a '(' before the keyword
        if "(" not in before:
            return ("type", s, e, m.group(2))
    return ("member", s, e, None)


# ─────────────────────────────── layout ───────────────────────────────

class Out:
    """One generated .java file with a line map back to markdown."""

    def __init__(self, rel):
        self.rel, self.lines, self.map = rel, [], []

    def add(self, text, src=None):
        self.lines.append(text)
        self.map.append(src)

    def add_block_lines(self, blk, lo, hi, lines=None):
        src_lines = lines if lines is not None else blk.lines
        for i in range(lo, hi):
            self.add(src_lines[i], [blk.md, blk.md_line(i)])


def transformed(blk, spec):
    lines = list(blk.lines)
    text = "\n".join(lines)
    wanted = list(getattr(spec, "transforms", ()))
    if isinstance(spec, U.Split):   # a part's transforms apply to the block (they only touch placeholder text)
        wanted += [t for _, part in spec.parts for t in getattr(part, "transforms", ()) if t not in wanted]
    for t in wanted:
        if t == "elide":          # `{ ... }` placeholder bodies → empty bodies
            text = re.sub(r"\{\s*\.\.\.\s*\}", "{ }", text)
        elif t == "stub_bodies":  # method bodies holding only comments → throw (keeps annotations/signatures checked)
            text = re.sub(r"(\)\s*(?:throws\s+[\w.,\s]+)?\{)((?:\s*//[^\n]*)*\s*)(\})",
                          r"\1\2throw new UnsupportedOperationException(); \3", text)
        else:
            raise SystemExit(f"unknown transform {t}")
    new = text.split("\n")
    assert len(new) == len(lines), "transforms must keep line numbers"
    return new


def split_segments(blk, spec, lines):
    """Split.parts: [(start_regex_or_None, spec)] → [(lo, hi, spec)]."""
    starts = []
    for rx, sub in spec.parts:
        if rx is None:
            starts.append((0, sub))
            continue
        for i, line in enumerate(lines):
            if re.search(rx, line) and all(i != s for s, _ in starts):
                starts.append((i, sub))
                break
        else:
            raise SystemExit(f"FAIL config: {blk.id}: split marker {rx!r} not found (the block changed)")
    starts.sort(key=lambda t: t[0])
    return [(s, starts[k + 1][0] if k + 1 < len(starts) else len(lines), sub) for k, (s, sub) in enumerate(starts)]


def dep_id(d):
    return d[0] if isinstance(d, tuple) else d


def proto_texts(protos):
    """The .proto blocks as files. Imports/options the protos are missing are added — idempotently, and
    announced as NOTE lines, because those blocks belong to the language-neutral grpc-pattern.md."""
    texts = {path: "\n".join(block(bid).lines) for bid, path in protos}
    notes = []
    defined = {}
    for path, text in texts.items():
        for m in re.finditer(r"^(?:message|enum)\s+(\w+)", text, re.M):
            defined[m.group(1)] = path
    java_pkg = next((m.group(1) for t in texts.values()
                     for m in [re.search(r'option java_package = "([\w.]+)"', t)] if m), None)
    out = {}
    for bid, path in protos:
        lines = texts[path].split("\n")
        code = "\n".join(re.sub(r"//.*", "", l) for l in lines)
        pkg_i = next(i for i, l in enumerate(lines) if l.startswith("package "))
        add = []
        if java_pkg and "java_package" not in code:
            add.append(f'option java_package = "{java_pkg}";')
        if java_pkg and "java_multiple_files" not in code:
            add.append("option java_multiple_files = true;")
        wanted = set()
        if "google.protobuf.Timestamp" in code:
            wanted.add("google/protobuf/timestamp.proto")
        for name, where_ in defined.items():
            if where_ != path and re.search(rf"(?<![\w.]){name}\b", code):
                wanted.add(where_)
        for imp in sorted(wanted):
            if f'import "{imp}";' not in code:
                add.append(f'import "{imp}";')
        if add:
            notes.append(f"NOTE {bid} ({path}): added {' '.join(add)} — missing in grpc-pattern.md, "
                         f"which this Java harness does not edit")
        out[path] = "\n".join(lines[:pkg_i + 1] + add + lines[pkg_i + 1:]) + "\n"
    return out, notes


def layout_unit(unit, dest):
    """Write one Maven module. Returns {generated_path: line_map}."""
    mod = dest / unit.name
    files, hosts, into = {}, {}, []
    for d in list(unit.own) + list(unit.deps):
        bid = dep_id(d)
        blk = block(bid)
        spec = d[1] if isinstance(d, tuple) else U.BLOCKS.get(bid, U.File())
        if bid in U.SKIP:
            raise SystemExit(f"FAIL config: {bid} is skipped but listed in unit {unit.name}")
        lines = transformed(blk, spec)
        segs = split_segments(blk, spec, lines) if isinstance(spec, U.Split) else [(0, len(lines), spec)]
        block_imports = [(i, l) for i, l in enumerate(lines) if IMPORT.match(l)]
        produced = sum(emit(unit, mod, blk, lines, lo, hi, sub, block_imports, files, hosts, into)
                       for lo, hi, sub in segs)
        if produced == 0 and d in unit.own:
            raise SystemExit(f"FAIL layout: {bid} produced no source, so nothing of it would be compiled — "
                             f"skip it with a reason or give it a layout")
    for (host_id, blk, lines, lo, hi, imports) in into:
        if host_id not in hosts:
            raise SystemExit(f"FAIL config: {blk.id} goes Into {host_id}, which is not laid out in {unit.name}")
        out, close_idx = hosts[host_id]
        body = Out("")
        for i, l in imports:
            if not any(l.strip() == x.strip() for x in out.lines):
                out.lines.insert(2, l)
                out.map.insert(2, [blk.md, blk.md_line(i)] if i is not None else None)
                close_idx[0] += 1
        body.add_block_lines(blk, lo, hi, lines)
        k = close_idx[0]
        out.lines[k:k] = [l for l in body.lines if not IMPORT.match(l)]
        out.map[k:k] = [m for l, m in zip(body.lines, body.map) if not IMPORT.match(l)]
        close_idx[0] += len([l for l in body.lines if not IMPORT.match(l)])
    for stub_dir in unit.stubs:
        src = HERE / "stubs" / stub_dir
        if not src.is_dir():
            raise SystemExit(f"FAIL config: stubs/{stub_dir} missing")
        for f in src.rglob("*.java"):
            rel = f.relative_to(src)
            is_test = rel.parts[0] == "test"
            rel = Path(*rel.parts[1:]) if rel.parts[0] in ("main", "test") else rel
            target = mod / ("src/test/java" if is_test else "src/main/java") / rel
            key = str(target.relative_to(mod))
            if key in files:
                raise SystemExit(f"FAIL config: stub {f} collides with {files[key].rel} in unit {unit.name}")
            o = Out(key)
            for l in f.read_text().split("\n"):
                o.add(l, None)
            o.stub = str(f.relative_to(HERE))
            files[key] = o
    if unit.protos:
        texts, notes = proto_texts(unit.protos)
        for path, text in texts.items():
            p = mod / "src/main/protobuf" / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
        for n in notes:
            print(n)
    maps = {}
    for key, o in files.items():
        p = mod / key
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(o.lines) + "\n", encoding="utf-8")
        maps[str(p)] = {"map": o.map, "stub": getattr(o, "stub", None)}
    (mod / "pom.xml").write_text(module_pom(unit), encoding="utf-8")
    return maps


def emit(unit, mod, blk, lines, lo, hi, spec, block_imports, files, hosts, into):
    if isinstance(spec, U.Into):
        extra_imports = [(None, f"import {x};") for x in spec.imports]
        into.append((spec.host, blk, lines, lo, hi, block_imports + extra_imports))
        return 1
    root = "src/test/java" if spec.test else "src/main/java"
    seg = lines[lo:hi]
    extra = [f"import {x};" for x in spec.imports]

    def header(out, pkg):
        out.add(f"package {pkg};")
        out.add("")
        for i, l in block_imports:
            out.add(l.strip(), [blk.md, blk.md_line(i)])
        for x in extra:
            out.add(x)

    def register(rel, out, host_close=None):
        if rel in files:
            prev = files[rel]
            raise SystemExit(f"FAIL layout: unit {unit.name}: {rel} defined twice "
                             f"({blk.id} and {prev.map[-1] if prev.map else '?'}) — split the unit or use File(only=...)")
        files[rel] = out
        if host_close is not None:
            hosts.setdefault(blk.id, (out, host_close))

    if isinstance(spec, U.File):
        parts = chunks(seg)
        pkg = spec.package
        for kind, s, e, name in parts:
            if kind == "package":
                if pkg and pkg != name:
                    raise SystemExit(f"FAIL config: {blk.id} declares package {name}, units.py says {pkg}")
                pkg = name
        if not pkg:
            raise SystemExit(f"FAIL config: {blk.id} has no package; give File(package=...)")
        strays = [(s, e) for kind, s, e, _ in parts if kind == "member"]
        if strays:
            s, e = strays[0]
            raise SystemExit(f"FAIL layout: {blk.id} line {blk.md_line(lo + s)}: top-level code outside a type "
                             f"({lines[lo + s].strip()[:60]!r}) — lay it out as Members/Statements or Split it")
        emitted = 0
        for kind, s, e, name in parts:   # comments above a type are part of its chunk
            if kind != "type" or (spec.only and name not in spec.only):
                continue
            out = Out(f"{root}/{pkg.replace('.', '/')}/{name}.java")
            header(out, pkg)
            out.add("")
            out.add_block_lines(blk, lo + s, lo + e, lines)
            close = [len(out.lines) - 1]   # the type's closing brace: Into blocks are inserted before it
            while close[0] > 0 and "}" not in out.lines[close[0]]:
                close[0] -= 1
            register(out.rel, out, close)
            emitted += 1
        return emitted

    if isinstance(spec, (U.Members, U.Statements)):
        pkg = spec.package
        out = Out(f"{root}/{pkg.replace('.', '/')}/{spec.cls}.java")
        header(out, pkg)
        out.add("")
        for a in spec.annotations:
            out.add(a)
        kind = "interface" if getattr(spec, "interface", False) else "class"
        decl = f"{'abstract ' if spec.abstract else ''}{kind} {spec.cls}"
        if spec.extends:
            decl += f" extends {spec.extends}"
        if spec.implements:
            decl += f" implements {spec.implements}"
        out.add(decl + " {")
        for l in spec.inject:
            out.add("    " + l)
        if isinstance(spec, U.Statements):
            out.add(f"    {spec.method} {{")
        for i in range(lo, hi):
            if IMPORT.match(lines[i]):
                out.add("", [blk.md, blk.md_line(i)])  # hoisted to the header
            else:
                out.add(lines[i], [blk.md, blk.md_line(i)])
        if isinstance(spec, U.Statements):
            out.add("    }")
        out.add("}")
        register(out.rel, out, [len(out.lines) - 1])
        return 1
    raise SystemExit(f"unknown spec {spec!r} for {blk.id}")


def module_pom(unit):
    extra = unit.pom_extra or ""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>archetype.compile</groupId>
    <artifactId>archetype-compile-parent</artifactId>
    <version>0</version>
  </parent>
  <artifactId>{unit.name}</artifactId>
  <name>{unit.name}</name>
{extra}
</project>
"""


def snippet_modules(dest):
    """Maven build snippets become their own modules: a Spring Boot 4 POM embedding the snippet as written."""
    out = []
    for bid, chk in U.BUILD_SNIPPETS.items():
        if chk.tool != "maven":
            continue
        b = block(bid)
        mod = dest / chk.name
        (mod / "src/main/java/snippet").mkdir(parents=True, exist_ok=True)
        (mod / "src/main/java/snippet" / "Probe.java").write_text(chk.probe_java or "package snippet;\nclass Probe {}\n")
        (mod / "pom.xml").write_text(chk.pom.replace("@SNIPPET@", "\n".join(b.lines)))
        out.append({"name": chk.name, "block": bid, "dir": str(mod), "goal": chk.goal, "verify": chk.verify})
    return out


def split_plugins_block(lines):
    """A Gradle snippet's `plugins { ... }` contents, and the rest of the snippet (one plugins block per script)."""
    for i, l in enumerate(lines):
        if re.match(r"^\s*plugins\s*\{", l):
            depth, j = 0, i
            while j < len(lines):
                depth += lines[j].count("{") - lines[j].count("}")
                if depth == 0:
                    break
                j += 1
            inner = lines[i + 1:j] if lines[i].strip().endswith("{") else []
            return inner, lines[:i] + lines[j + 1:]
    return [], lines


def gradle_projects(dest):
    """Gradle build snippets are excerpts of a build file: each is merged into a minimal project (gradle/<template>)
    whose plugins block already applies what the snippet assumes (java, and Spring Boot where the snippet is Boot
    configuration). The snippet's own plugins join that block."""
    out = []
    for bid, chk in U.BUILD_SNIPPETS.items():
        if chk.tool != "gradle":
            continue
        b = block(bid)
        proj = dest / "gradle" / chk.name
        shutil.copytree(HERE / "gradle" / chk.template, proj)
        plugins, rest = split_plugins_block(b.lines)
        build = proj / chk.build_file
        text = build.read_text().replace("@PLUGINS@", "\n".join(plugins)).replace("@SNIPPET@", "\n".join(rest))
        build.write_text(text)
        if chk.protos:
            texts, notes = proto_texts(chk.protos)
            for path, t in texts.items():
                p = proj / "src/main/proto" / path
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(t)
            for n in notes:
                print(n.replace("NOTE", f"NOTE [{chk.name}]"))
        out.append({"name": chk.name, "block": bid, "dir": str(proj), "tasks": list(chk.tasks),
                    "verify": chk.verify})
    return out


def layout(dest):
    dest = Path(dest)
    found, errors = inventory()
    if errors:
        for e in errors:
            print("FAIL inventory:", e)
        sys.exit(2)
    maps, modules = {}, []
    for unit in U.UNITS:
        maps.update(layout_unit(unit, dest))
        modules.append(unit.name)
    snippets = snippet_modules(dest)
    modules += [s["name"] for s in snippets]
    parent = (HERE / "parent-pom.xml").read_text()
    parent = parent.replace("@MODULES@", "\n".join(f"    <module>{m}</module>" for m in modules))
    (dest / "pom.xml").write_text(parent)
    (dest / "linemap.json").write_text(json.dumps(maps))
    gradle = gradle_projects(dest)
    (dest / "gradle.json").write_text(json.dumps(gradle))
    (dest / "snippets.json").write_text(json.dumps(snippets))
    (dest / "units.json").write_text(json.dumps(
        [{"name": u.name, "own": u.own, "kind": "java"} for u in U.UNITS] +
        [{"name": s["name"], "own": [s["block"]], "kind": "snippet"} for s in snippets]))
    print(f"layout: {len(U.UNITS)} Java units, {len(snippets)} Maven build-snippet modules, "
          f"{len(gradle)} Gradle build-snippet projects → {dest}")


# ─────────────────────────────── report ───────────────────────────────

MSG = re.compile(r"^\[(ERROR|WARNING)\] (/\S+\.java):\[(\d+),(\d+)\] (.*)$")
SUMMARY = re.compile(r"^\[INFO\] (\S+) \.+ ?(SUCCESS|FAILURE|SKIPPED)")


def where(maps, path, line):
    info = maps.get(path)
    if not info:
        return path
    m = info["map"][line - 1] if 0 < line <= len(info["map"]) else None
    if m:
        return f"{m[0]}:{m[1]}"
    if info.get("stub"):
        return f"tests/archetype-compile/java/{info['stub']}:{line}"
    return f"{Path(path).name}:{line} (harness wrapper)"


def report(dest, log):
    dest = Path(os.path.realpath(dest))
    maps = {os.path.realpath(k): v for k, v in json.loads((dest / "linemap.json").read_text()).items()}
    units = json.loads((dest / "units.json").read_text())
    status, errs, warns, last = {}, {}, {}, None
    for raw in Path(log).read_text(errors="replace").split("\n"):
        m = SUMMARY.match(raw)
        if m:
            status[m.group(1)] = m.group(2)
            continue
        m = MSG.match(raw)
        if m:
            sev, path, line, _col, msg = m.groups()
            if sev == "WARNING" and "marked for removal" in msg:
                sev = "ERROR"   # an API slated for removal must not be copied into new projects
                msg = "[removal] " + msg
            path = os.path.realpath(path)
            try:
                unit = Path(path).relative_to(dest).parts[0]
            except ValueError:
                unit = "?"
            bucket = (errs if sev == "ERROR" else warns).setdefault(unit, {})
            key = (where(maps, path, int(line)), msg.strip())
            if key in bucket:          # Maven repeats every compiler message in its final summary
                last = None
            else:
                bucket[key] = f"{key[0]}: {key[1]}"
                last = (bucket, key)
            continue
        if last is not None and re.match(r"^\s+symbol:", raw):   # javac's detail line for "cannot find symbol"
            last[0][last[1]] += f" ({' '.join(raw.split())})"
        elif not raw.startswith("  "):
            last = None
    failed, java_failed = 0, 0
    for u in units:
        st = status.get(u["name"], "NOT RUN")
        if st == "SUCCESS" and errs.get(u["name"]):
            st = "uses an API marked for removal"
        ok = st == "SUCCESS"
        failed += not ok
        java_failed += (not ok) and u["kind"] == "java"
        own = ", ".join(sorted({b.split('#')[0] for b in u["own"]}))
        print(f"{'PASS' if ok else 'FAIL'}  {u['name']:<34} {len(u['own']):>3} block(s) from {own}"
              + ("" if ok else f"   [{st}]"))
        for e in errs.get(u["name"], {}).values():
            print(f"        error: {e}")
        for w in warns.get(u["name"], {}).values():
            print(f"        warning: {w}")
    n_java = sum(1 for u in units if u["kind"] == "java")
    n_snip, snip_failed = len(units) - n_java, failed - java_failed
    print(f"java units: {n_java - java_failed} PASS / {java_failed} FAIL; "
          f"maven build-snippet modules: {n_snip - snip_failed} PASS / {snip_failed} FAIL")
    return failed


# ─────────────────────────────── build-snippet checks (called by run.sh) ───────────────────────────────

def vtuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def check_layers(jar):
    """The jar's BOOT-INF/layers.idx exists and uses the four standard layer names, application last."""
    import zipfile
    try:
        idx = zipfile.ZipFile(jar).read("BOOT-INF/layers.idx").decode()
    except (KeyError, FileNotFoundError, zipfile.BadZipFile) as e:
        print(f"no BOOT-INF/layers.idx in {jar} ({e})")
        return 1
    layers = re.findall(r'^- "([^"]+)":', idx, re.M)
    known = {"dependencies", "spring-boot-loader", "snapshot-dependencies", "application"}
    if not layers or set(layers) - known or layers[-1] != "application":
        print(f"unexpected layers.idx layers: {layers}")
        return 1
    print(f"layers.idx: {', '.join(layers)}")
    return 0


def check_otel(tool, text_file):
    """FAIL when dependency management downgrades opentelemetry-api below what the OTel instrumentation
    starter was built against (NoSuchMethodError at startup)."""
    text = Path(text_file).read_text(errors="replace")
    if tool == "maven":
        pairs = re.findall(r"io\.opentelemetry:opentelemetry-api:jar:([\w.-]+):\w+[^\n]*?version managed from ([\w.-]+)", text)
        chosen = re.findall(r"io\.opentelemetry:opentelemetry-api:jar:([\w.-]+)", text)
    else:
        pairs = [(b, a) for a, b in re.findall(r"io\.opentelemetry:opentelemetry-api:([\d.]+) -> ([\d.]+)", text)]
        chosen = [b for _, b in re.findall(r"io\.opentelemetry:opentelemetry-api:([\d.]+) -> ([\d.]+)", text)] or \
            re.findall(r"^io\.opentelemetry:opentelemetry-api:([\d.]+)", text, re.M)
    for got, wanted in pairs:
        if vtuple(got) < vtuple(wanted):
            print(f"opentelemetry-api {wanted} is downgraded to {got} by the Spring Boot BOM")
            return 1
    if not chosen:
        print("opentelemetry-api not found in the resolved graph")
        return 1
    print(f"opentelemetry-api {chosen[0]} (not downgraded)")
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "inventory"
    if cmd == "inventory":
        found, errors = inventory()
        for e in errors:
            print("FAIL inventory:", e)
        total = sum(found.values())
        skipped = sum(1 for b in U.SKIP if b.partition("#")[2].isdigit())
        print(f"inventory: {total} ```java blocks in {len(found)} files; {total - skipped} compiled, {skipped} skipped")
        sys.exit(1 if errors else 0)
    elif cmd == "layout":
        layout(sys.argv[2])
    elif cmd == "report":
        sys.exit(1 if report(sys.argv[2], sys.argv[3]) else 0)
    elif cmd == "check-layers":
        sys.exit(check_layers(sys.argv[2]))
    elif cmd == "check-otel":
        sys.exit(check_otel(sys.argv[2], sys.argv[3]))
    else:
        raise SystemExit(__doc__)
