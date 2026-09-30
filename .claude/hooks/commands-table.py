#!/usr/bin/env python3
"""commands-table.py — IMPLEMENTATION_GUIDELINES "## Commands and versions" → verify-commands.json.

  commands-table.py docs/IMPLEMENTATION_GUIDELINES.md --out agent_state/config/verify-commands.json

Reads the two tables in that section (| Purpose | Command | and | Component | Version |) and writes
  {"commands": {purpose: cmd}, "versions": {component: version},
   "typecheck": ..., "lint": ..., "test": ..., "timeout_seconds": 900}
The top-level typecheck/lint/test keys are what verify-gate.sh check (e) runs at the gate
(typecheck falls back to build; test = test:unit). Exit 1 if the section or a test:unit command is
missing — the gate should not silently run nothing. Format: .claude/skills/core/commands-and-versions.md
"""
import argparse, json, os, re, sys

PURPOSE_RE = re.compile(r"^(install|build|typecheck|lint|test:(unit|integration|ui|e2e|mobile)|migrate|seed|run|x:[a-z0-9_-]+)$")


def tables(section):
    rows, out = [], []
    for line in section.split("\n") + [""]:
        s = line.strip()
        if s.startswith("|"):
            if re.fullmatch(r"[\s|:-]+", s):
                continue
            rows.append([c.strip() for c in s.strip("|").split("|")])
        elif rows:
            out.append(rows)
            rows = []
    return out


def unquote(cmd):
    cmd = cmd.strip()
    return cmd[1:-1] if len(cmd) > 1 and cmd[0] == cmd[-1] == "`" else cmd.replace("\\|", "|")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("guidelines")
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeout", type=int, default=900)
    a = ap.parse_args()
    text = open(a.guidelines, encoding="utf-8").read()
    m = re.search(r"^##\s+Commands and versions\s*$(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    if not m:
        sys.exit(f"commands-table: no '## Commands and versions' section in {a.guidelines} "
                 "(see ~/.claude/skills/core/commands-and-versions.md)")
    commands, versions, bad = {}, {}, []
    for t in tables(m.group(1)):
        head = [h.lower() for h in t[0]]
        if head[:2] == ["purpose", "command"]:
            for r in t[1:]:
                if len(r) < 2 or not r[0]:
                    continue
                p = r[0].strip("` ").lower()
                (commands.__setitem__(p, unquote("|".join(r[1:]))) if PURPOSE_RE.match(p) else bad.append(p))
        elif head[:2] == ["component", "version"]:
            versions.update({r[0]: r[1] for r in t[1:] if len(r) >= 2 and r[0]})
    if bad:
        sys.exit(f"commands-table: unknown purpose(s) {bad} — use {PURPOSE_RE.pattern}")
    if "test:unit" not in commands:
        sys.exit("commands-table: no test:unit command — the gate would run nothing")
    out = {"commands": commands, "versions": versions, "timeout_seconds": a.timeout,
           "typecheck": commands.get("typecheck") or commands.get("build", ""),
           "lint": commands.get("lint", ""), "test": commands["test:unit"]}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(out, open(a.out, "w"), indent=1)
    print(f"commands-table: {len(commands)} commands, {len(versions)} versions → {a.out}")


if __name__ == "__main__":
    main()
