"""Extract fenced code blocks from the archetype markdown files.

A block is a fence that opens at column 0 with ```<lang> and closes at the next line that is exactly
``` (column 0). Every Go block is numbered per file, 1-based, in document order; the number and the
nearest preceding markdown heading identify it in units.json.
"""
import os
import re

HEADING_RE = re.compile(r"^#{1,6}\s+(.*?)\s*$")
PACKAGE_RE = re.compile(r"^package\s+(\w+)\s*(//.*)?$", re.M)


class Block:
    def __init__(self, md, index, lang, first_line, heading, text):
        self.md = md                  # file name, e.g. "crud-handler-go.md"
        self.index = index            # 1-based among blocks of this language in the file
        self.lang = lang
        self.first_line = first_line  # 1-based markdown line of the first code line
        self.heading = heading        # nearest heading above the fence ("" if none)
        self.text = text              # code, without the fences, ending in "\n"

    @property
    def package(self):
        """The package clause's name if the block declares one (before any other code), else None."""
        for line in self.text.split("\n"):
            s = line.strip()
            if not s or s.startswith("//"):
                continue
            m = PACKAGE_RE.match(s)
            return m.group(1) if m else None
        return None

    def ref(self):
        return f"{self.md}#{self.index}"


def blocks(path, lang="go"):
    """Return the `lang` blocks of one markdown file, in order."""
    name = os.path.basename(path)
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    out, heading, i, n = [], "", 0, 0
    while i < len(lines):
        line = lines[i]
        m = HEADING_RE.match(line)
        if m:
            heading = m.group(1)
        if line.startswith("```"):
            fence_lang = line[3:].strip().split()[0] if line[3:].strip() else ""
            j = i + 1
            while j < len(lines) and lines[j] != "```":
                j += 1
            if j >= len(lines):
                raise SystemExit(f"{name}:{i + 1}: unterminated code fence")
            if fence_lang == lang:
                n += 1
                out.append(Block(name, n, lang, i + 2, heading, "\n".join(lines[i + 1:j]) + "\n"))
            i = j + 1
            continue
        i += 1
    return out


if __name__ == "__main__":
    import sys
    for p in sys.argv[1:]:
        for b in blocks(p):
            first = next((l for l in b.text.split("\n") if l.strip()), "")
            print(f"{b.md}#{b.index}\tL{b.first_line}\tpkg={b.package or '-'}\t[{b.heading}]\t{first[:70]}")
