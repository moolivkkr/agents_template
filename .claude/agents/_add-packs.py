#!/usr/bin/env python3
"""_add-packs.py — append skill packs to agents' `skill_packs:` frontmatter (idempotent).

Usage: python3 _add-packs.py <agent-file> <skills-relative-path> [...]
Creates the `skill_packs:` key if the agent has none. Refuses a pack that doesn't exist under
../skills/ (no dangling references). Run ./_sync-contract.sh on the same files afterwards so the
Reference-packs body block is regenerated.
"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.join(HERE, "..", "skills")
path, packs = sys.argv[1], sys.argv[2:]
text = open(path, encoding="utf-8").read()
m = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
fm, body = m.group(1), text[m.end():]
for rel in packs:
    if not os.path.isfile(os.path.join(SKILLS, rel)):
        sys.exit(f"refusing: skills/{rel} does not exist")
    line = f'  - "~/.claude/skills/{rel}"'
    if line in fm:
        continue
    if re.search(r"^skill_packs:\s*$", fm, re.M):
        # append after the last list item of skill_packs
        fm = re.sub(r"(^skill_packs:\s*\n(?:  - .*\n?)*)", lambda k: k.group(1).rstrip("\n") + "\n" + line + "\n", fm, count=1, flags=re.M).rstrip("\n")
    else:
        fm = fm.rstrip("\n") + "\nskill_packs:\n" + line
open(path, "w", encoding="utf-8").write("---\n" + fm + "\n---\n" + body)
print(f"{os.path.basename(path)}: {len(packs)} pack(s) ensured")
