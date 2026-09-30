#!/usr/bin/env python3
"""Extract a skill pack's code blocks into a scaffolded project so a real compiler checks them.

Every fenced block in the pack must be accounted for, one of two ways:
  * CHECKED: its first non-empty line names a file under src/ —
        // file: src/api/client.ts          (TS/JS)
        <!-- file: src/lib/X.svelte -->     (Vue/Svelte/HTML)
    and the block is written there, verbatim (marker line included; it's a comment).
  * SKIPPED: skips.tsv has a row `<pack>\t<first non-empty line of the block>\t<reason>`.
A block that is neither, a skip row that matches no block, two blocks naming the same file, or a path
outside src/ fails the run: a pack can't gain an unchecked example, or keep a stale excuse.

Also used to pull ONE block out of a shared pack by the start of its first line (--block-prefix), so
the harness compiles against the real envelope types and MSW helpers, not copies.

Usage:
  extract.py pack  --pack PATH --dest DIR --skips skips.tsv --manifest OUT.tsv
  extract.py block --pack PATH --block-prefix TEXT --out FILE [--append]
Exit 0 = ok; 1 = an accounting error (printed).
"""
import argparse
import os
import re
import sys

FILE_RE = re.compile(r"^\s*(?://|<!--|#)\s*file:\s*(\S+?)\s*(?:-->)?\s*$")


def code_blocks(text):
    """[(start_line, lang, [lines])] for every fenced block — same rule as tests/lib/skills_security_cases.py."""
    out, cur, fence, lang, start = [], None, None, "", 0
    for i, line in enumerate(text.split("\n"), 1):
        m = re.match(r"^\s*(`{3,})(.*)$", line)
        if cur is None and m:
            fence, lang, cur, start = m.group(1), m.group(2).strip(), [], i + 1
        elif cur is not None and m and m.group(1) == fence and not m.group(2).strip():
            out.append((start, lang, cur))
            cur = None
        elif cur is not None:
            cur.append(line)
    return out


def first_line(lines):
    return next((l.strip() for l in lines if l.strip()), "")


def load_skips(path, pack_name):
    rows = {}
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8") as f:
        for n, raw in enumerate(f, 1):
            raw = raw.rstrip("\n")
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            parts = raw.split("\t")
            if len(parts) != 3 or not parts[2].strip():
                sys.exit(f"skips.tsv:{n}: need 3 tab-separated fields (pack, first line, reason): {raw!r}")
            if parts[0] == pack_name:
                rows[parts[1].strip()] = parts[2].strip()
    return rows


def cmd_pack(a):
    pack_name = os.path.basename(a.pack)
    text = open(a.pack, encoding="utf-8").read()
    skips = load_skips(a.skips, pack_name)
    used, written, errors, manifest = set(), {}, [], []
    for start, lang, lines in code_blocks(text):
        head = first_line(lines)
        m = FILE_RE.match(head)
        if m:
            rel = m.group(1)
            norm = os.path.normpath(rel)
            if not norm.startswith("src" + os.sep) or ".." in norm.split(os.sep):
                errors.append(f"{pack_name}:{start}: file path must be under src/: {rel}")
                continue
            if norm in written:
                errors.append(f"{pack_name}:{start}: {rel} already written by the block at line {written[norm]}")
                continue
            written[norm] = start
            dest = os.path.join(a.dest, norm)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w", encoding="utf-8") as f:
                f.write("\n".join(lines).rstrip("\n") + "\n")
            manifest.append(("CHECKED", start, norm, ""))
        elif head in skips:
            used.add(head)
            manifest.append(("SKIPPED", start, head[:80], skips[head]))
        else:
            errors.append(f"{pack_name}:{start}: block ({lang or 'no lang'}) is neither checked (no `file:` marker) "
                          f"nor listed in skips.tsv — first line: {head[:90]!r}")
    for stale in sorted(set(skips) - used):
        errors.append(f"skips.tsv: {pack_name}: no block starts with {stale!r} (stale skip — remove it)")
    with open(a.manifest, "w", encoding="utf-8") as f:
        for status, start, what, reason in manifest:
            f.write(f"{status}\t{pack_name}:{start}\t{what}\t{reason}\n")
    for e in errors:
        print(f"EXTRACT-FAIL {e}")
    return 1 if errors else 0


def cmd_block(a):
    text = open(a.pack, encoding="utf-8").read()
    hits = [lines for _s, _l, lines in code_blocks(text) if first_line(lines).startswith(a.block_prefix)]
    if len(hits) != 1:
        print(f"EXTRACT-FAIL {os.path.basename(a.pack)}: expected exactly one block starting with "
              f"{a.block_prefix!r}, found {len(hits)} — the shared pack changed; update run.sh")
        return 1
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "a" if a.append else "w", encoding="utf-8") as f:
        f.write("\n".join(hits[0]).rstrip("\n") + "\n")
    return 0


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    pk = sub.add_parser("pack")
    pk.add_argument("--pack", required=True)
    pk.add_argument("--dest", required=True)
    pk.add_argument("--skips", required=True)
    pk.add_argument("--manifest", required=True)
    bl = sub.add_parser("block")
    bl.add_argument("--pack", required=True)
    bl.add_argument("--block-prefix", required=True)
    bl.add_argument("--out", required=True)
    bl.add_argument("--append", action="store_true")
    a = p.parse_args()
    sys.exit(cmd_pack(a) if a.cmd == "pack" else cmd_block(a))


if __name__ == "__main__":
    main()
