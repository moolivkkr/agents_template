"""Extract fenced code blocks from the skill markdown files.

A fence opens with 3+ backticks (indented by at most 3 spaces, as in CommonMark — e.g. inside a list
item) followed by the language, and closes at the next line made only of at least as many backticks.
Every block of the requested language is numbered per file, 1-based, in document order; the number
and the nearest preceding markdown heading identify it in units.json. An indented block's
indentation is removed. An unterminated fence of the requested language is an error; one of
another language (a stray closing fence at the end of a doc) ends the scan.
"""
import os
import re

HEADING_RE = re.compile(r"^#{1,6}\s+(.*?)\s*$")
PACKAGE_RE = re.compile(r"^package\s+(\w+)\s*(//.*)?$", re.M)
FENCE_RE = re.compile(r"^( {0,3})(`{3,})\s*([^`\s]*)[^`]*$")


class Block:
    def __init__(self, md, index, lang, first_line, heading, text):
        self.md = md                  # file name relative to the scanned root, e.g. "crud-handler-go.md"
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


def blocks(path, lang="go", name=None):
    """Return the `lang` blocks of one markdown file, in order. `name` is how the file is referred to
    (default: its base name)."""
    name = name or os.path.basename(path)
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    out, heading, i, n = [], "", 0, 0
    while i < len(lines):
        line = lines[i]
        m = HEADING_RE.match(line)
        if m:
            heading = m.group(1)
        f = FENCE_RE.match(line)
        if f:
            indent, ticks, fence_lang = len(f.group(1)), len(f.group(2)), f.group(3)
            j = i + 1
            while j < len(lines):
                c = lines[j].strip()
                if c and set(c) == {"`"} and len(c) >= ticks and len(lines[j]) - len(lines[j].lstrip()) <= 3:
                    break
                j += 1
            if j >= len(lines):
                if fence_lang == lang:
                    raise SystemExit(f"{name}:{i + 1}: unterminated {lang} code fence")
                break  # a stray fence of another language: nothing more to find
            if fence_lang == lang:
                body = lines[i + 1:j]
                if indent:
                    body = [l[indent:] if l[:indent].strip() == "" else l for l in body]
                n += 1
                out.append(Block(name, n, lang, i + 2, heading, "\n".join(body) + "\n"))
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
