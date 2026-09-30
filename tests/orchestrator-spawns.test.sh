#!/usr/bin/env bash
# orchestrator-spawns.test.sh — every agent spawn in a command or develop-step file names its
# subagent_type, and the named agent exists. An untyped spawn runs a generic agent that never loads the
# role's instructions, skill packs or Definition of Done (board review 2026-09-30: DEV-08, the Wave 4
# acceptance spawn). Run: bash tests/orchestrator-spawns.test.sh
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 - "$REPO" <<'PY'
import os, re, sys
repo = sys.argv[1]
agents = set()
for d in (".claude/agents/core", ".claude/agents/templates"):
    for f in os.listdir(os.path.join(repo, d)):
        m = re.search(r"^name:\s*(\S+)", open(os.path.join(repo, d, f)).read(), re.M)
        if m: agents.add(m.group(1).strip("'\""))
agents |= {"general-purpose", "Explore", "Plan"}
files = [os.path.join(".claude/commands", f) for f in os.listdir(os.path.join(repo, ".claude/commands")) if f.endswith(".md")]
steps = os.path.join(repo, ".claude/skills/core/develop-steps")
if os.path.isdir(steps):
    files += [os.path.join(".claude/skills/core/develop-steps", f) for f in os.listdir(steps) if f.endswith(".md")]
fails = spawns = 0
for rel in sorted(files):
    for i, line in enumerate(open(os.path.join(repo, rel)), 1):
        if not re.match(r"\s*(Agent prompt|Agent\()", line):
            continue
        spawns += 1
        m = re.search(r"subagent_type:\s*`?<?([A-Za-z_][\w-]*)", line)
        if not m:
            print(f"  ✗ FAIL: {rel}:{i} spawns an agent without subagent_type"); fails += 1
        elif m.group(1) not in agents and m.group(1) not in ("role", "agent_name", "reconciler", "owning"):
            print(f"  ✗ FAIL: {rel}:{i} names unknown subagent_type '{m.group(1)}'"); fails += 1
print(f"  {'✓' if not fails else '✗'} {spawns} spawns checked, {fails} untyped/unknown")
print(f"orchestrator-spawns.test.sh: {spawns - fails} passed, {fails} failed")
sys.exit(1 if fails else 0)
PY
