#!/bin/bash
# Keeps two generated blocks in every agent file up to date:
#   1. reference-packs   - built from the agent's `skill_packs:` frontmatter. Claude Code ignores that
#                          key, so without this block the packs are never read.
#   2. operating-contract - copied from Block 0 of ~/.claude/skills/core/agent-common.md. Subagents never
#                          load agent-common.md, so each agent carries its own copy.
# Both sit just above the agent's "## Definition of Done". Edit the sources, then re-run:
#   ./_sync-contract.sh              # every agent here and every template in templates/
#   ./_sync-contract.sh a.md b.md    # just these
set -euo pipefail
cd "$(dirname "$0")"
SRC=../skills/core/agent-common.md
CONTRACT=$(awk '/<!-- BEGIN operating-contract -->/,/<!-- END operating-contract -->/' "$SRC")
[ -n "$CONTRACT" ] || { echo "contract block not found in $SRC" >&2; exit 1; }

if [ $# -gt 0 ]; then FILES=("$@"); else
  # Installed layout keeps agents here; the framework repo keeps them in core/. Handle both.
  shopt -s nullglob
  FILES=(); for f in *.md core/*.md templates/*.tmpl; do case "$(basename "$f")" in AGENT_SCHEMA.md|INVENTORY.md) ;; *) FILES+=("$f");; esac; done
fi

for f in "${FILES[@]}"; do
  CONTRACT="$CONTRACT" python3 - "$f" <<'PY'
import os, re, sys
path = sys.argv[1]
text = open(path).read()

def dod_offset(text):
    """Offset of the first '## Definition of Done' heading outside fenced code blocks, or None."""
    fence, pos = False, 0
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            fence = not fence
        elif not fence and line.startswith("## Definition of Done"):
            return pos
        pos += len(line) + 1
    return None

def upsert(text, name, block):
    # Always remove, then re-insert, so a block that landed in the wrong place moves.
    pat = re.compile(r"\n*<!-- BEGIN %s -->.*?<!-- END %s -->\n*" % (name, name), re.S)
    text = pat.sub("\n\n", text)
    if not block:
        return text
    i = dod_offset(text)
    if i is None:
        return text.rstrip("\n") + "\n\n" + block
    return text[:i].rstrip("\n") + "\n\n" + block + "\n" + text[i:]

fm = re.match(r"^---\n(.*?)\n---\n", text, re.S)
packs = re.findall(r'^\s*-\s*"?\.?/?(?:~/)?\.claude/(skills/[^"\s]+)"?\s*$', fm.group(1), re.M) if fm else []
if packs:
    lines = "\n".join(f"- `~/.claude/{p}`" for p in packs)
    refs = ("<!-- BEGIN reference-packs -->\n## Reference packs\n\n"
            "These hold the conventions and patterns for the work you're doing. Before writing or reviewing, "
            "read the ones that apply to this task and skip the rest. `{{VAR}}` placeholders resolve from "
            "`agent_state/agent_registry.json` (for example `{{LANG}}` to `go`); if a resolved file doesn't "
            "exist, note it in your final message and continue.\n\n" + lines + "\n<!-- END reference-packs -->\n")
else:
    refs = ""

new = upsert(text, "reference-packs", refs)
new = upsert(new, "operating-contract", os.environ["CONTRACT"].strip() + "\n")
if new != text:
    open(path, "w").write(new); print("synced   ", path, f"({len(packs)} packs)")
else:
    print("unchanged", path)
PY
done
