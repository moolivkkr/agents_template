"""Extract the non-application code blocks (sql, sh, yaml, json, dockerfile, hcl, ngql) from the skill packs.

Fences follow CommonMark: an opening fence is 3+ backticks or tildes (optionally indented, e.g. inside a
list item) with an info string; the block ends at the next fence of the same character that is at least
as long and has no info string. A ```markdown / ````markdown block is a template of a document, so the
blocks nested inside it are extracted too (implementation-guidelines-template.md is built that way).

Every block gets a key "<path under .claude/skills>#<lang><n>", n counting that language's blocks in the
file from 1, and keeps the markdown line of its first content line, so every finding maps back to
file.md:line.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

# info string (first word, case-insensitive) -> the checker family it belongs to
LANGS = {
    "sql": "sql", "postgresql": "sql", "postgres": "sql", "pgsql": "sql", "plpgsql": "sql",
    "mysql": "sql", "sqlite": "sql",
    "bash": "sh", "sh": "sh", "shell": "sh", "zsh": "sh",
    "yaml": "yaml", "yml": "yaml",
    "json": "json", "jsonc": "json", "json5": "json",
    "dockerfile": "dockerfile", "docker": "dockerfile", "containerfile": "dockerfile",
    "hcl": "hcl", "terraform": "hcl", "tf": "hcl",
    "ngql": "ngql", "nebula": "ngql",
}
TEMPLATE_LANGS = {"markdown", "md"}
OPEN_RE = re.compile(r"^(?P<ind>[ \t]*)(?P<fence>`{3,}|~{3,})[ \t]*(?P<info>[^`]*?)[ \t]*$")
HEADING_RE = re.compile(r"^#{1,6}\s+(.*?)\s*$")


@dataclass
class Block:
    path: str            # path under .claude/skills, e.g. "databases/postgres.md"
    lang: str            # checker family: sql | sh | yaml | json | dockerfile | hcl | ngql
    info: str            # the fence's own info word, e.g. "bash"
    index: int           # 1-based among this file's blocks of the same family
    first_line: int      # markdown line (1-based) of the first content line
    indent: int          # columns stripped from every content line (fence indentation)
    heading: str         # nearest heading above the fence
    lines: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.path}#{self.lang}{self.index}"

    @property
    def text(self) -> str:
        return "\n".join(self.lines) + "\n"

    @property
    def anchor(self) -> str:
        """First non-empty line, stripped: what the config pins a block to, so a moved block is noticed."""
        return next((ln.strip() for ln in self.lines if ln.strip()), "")

    def md_line(self, rel: int) -> int:
        """Markdown line of the block's rel-th line (1-based)."""
        return self.first_line + rel - 1


def _fences(lines, offset, heading, path, out, counters):
    i = 0
    while i < len(lines):
        line = lines[i]
        h = HEADING_RE.match(line)
        if h:
            heading = h.group(1)
        m = OPEN_RE.match(line)
        if not m:
            i += 1
            continue
        ind, fence, info = m.group("ind"), m.group("fence"), m.group("info")
        word = info.split()[0].lower() if info.split() else ""
        close = re.compile(r"^[ \t]*" + re.escape(fence[0]) + "{%d,}[ \t]*$" % len(fence))
        j = i + 1
        while j < len(lines) and not close.match(lines[j]):
            j += 1
        if j >= len(lines):
            raise SystemExit(f"{path}:{offset + i + 1}: unterminated code fence")
        body = lines[i + 1:j]
        n = len(ind.expandtabs(4)) if "\t" in ind else len(ind)
        stripped = [b[n:] if b[:n].strip() == "" else b.lstrip() for b in body]
        fam = LANGS.get(word)
        if fam:
            counters[fam] = counters.get(fam, 0) + 1
            out.append(Block(path, fam, word, counters[fam], offset + i + 2, n, heading, stripped))
        elif word in TEMPLATE_LANGS:
            _fences(stripped, offset + i + 1, heading, path, out, counters)
        i = j + 1
    return heading


def extract(md_file: str, rel: str) -> list[Block]:
    with open(md_file, encoding="utf-8") as f:
        lines = f.read().split("\n")
    out: list[Block] = []
    _fences(lines, 0, "", rel, out, {})
    return out


def skill_files(skills_dir: str) -> list[str]:
    """Every skill markdown file in scope: all of .claude/skills except the two archetype folders."""
    found = []
    for dp, dns, fns in os.walk(skills_dir):
        rel_dir = os.path.relpath(dp, skills_dir)
        if rel_dir in ("backend/archetypes", "ui/archetypes") or rel_dir.startswith(("backend/archetypes/", "ui/archetypes/")):
            dns[:] = []
            continue
        dns.sort()
        for fn in sorted(fns):
            if fn.endswith(".md"):
                found.append(os.path.relpath(os.path.join(dp, fn), skills_dir))
    return found


def all_blocks(skills_dir: str) -> list[Block]:
    out = []
    for rel in skill_files(skills_dir):
        out.extend(extract(os.path.join(skills_dir, rel), rel))
    return out


if __name__ == "__main__":
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "..", "..", ".claude", "skills")
    for b in all_blocks(root):
        print(f"{b.key}\tL{b.first_line}\t{b.info}\t{b.anchor[:80]}")
