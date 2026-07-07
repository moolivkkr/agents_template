---
command: remember
description: "Record a ground-truth fact that every session and subagent must honor (retired/renamed components, hard constraints, environment gotchas). Deterministically supersedes any prior conflicting fact."
arguments:
  - name: fact
    required: true
    description: "The fact to record, in plain language. E.g. 'vertix-gateway is retired, traffic moved to edge-router'."
---

# /remember — Record a Tier 0 Ground-Truth Fact

Writes a durable fact to `docs/PROJECT_FACTS.md` so it is loaded by every future session and
injected into every subagent — stated once, honored everywhere. Fixes the "I have to repeat
this to every session" problem.

Full model: `.claude/skills/core/shared-context-protocol.md`.

---

## When to use
- A service/component was **retired, deprecated, or renamed** ("vertix-gateway is retired").
- A **hard constraint** all agents must respect ("never call the DB directly — go through the repo layer").
- An **environment fact** that trips agents up ("Docker is not on PATH", "use port 5433 for the test PG").
- An **off-limits zone** ("`legacy/` is frozen — do not modify").

Do NOT use for requirements (→ BRD), tech conventions (→ IMPLEMENTATION_GUIDELINES), or
phase-specific lessons (→ `agent_state/lessons.md`). Keep Tier 0 tiny.

---

## Procedure (the parent session runs this inline — no subagent)

### Step 1 — Ensure the file exists
```bash
if [ ! -f docs/PROJECT_FACTS.md ]; then
  mkdir -p docs
  cp .claude/templates/PROJECT_FACTS.md.template docs/PROJECT_FACTS.md
  # replace {{PROJECT_NAME}} if known, else leave as-is
fi
```

### Step 2 — Classify the fact
From the user's text, extract:
- **subject** — the entity the fact is about (e.g. `vertix-gateway`). Lowercase, kebab.
- **relation** — one of: `lifecycle` (retired/active/deprecated), `name` (renamed/canonical),
  `constraint` (a rule), `environment` (a gotcha), `boundary` (off-limits).
- **confidence** — `confirmed` (human stated it directly via this command).

### Step 3 — Apply deterministic supersession (NOT semantic similarity)
Search existing active facts for the same `(subject, relation)` key:
```bash
grep -nE "^- subject: <subject>$" docs/PROJECT_FACTS.md
```
If an **active** fact with the same `(subject, relation)` exists, mark it superseded:
- set its `status: superseded`
- set its `invalid_at:` to today
- set its `superseded_by:` to the new F-id
- move its block to the "Superseded Facts" section (do NOT delete it)

> Never match on meaning/similarity — only the exact `(subject, relation)` key. Embeddings
> cannot distinguish a contradiction from a duplicate; the deterministic key can.

### Step 4 — Append the new fact
Next id = highest existing `F-###` + 1. Append to "Active Facts":
```markdown
### F-0NN — <short title>
- status: active
- subject: <subject>
- relation: <relation>
- valid_from: <today, YYYY-MM-DD>
- invalid_at: —
- superseded_by: —
- source: human:/remember
- confidence: confirmed
- fact: >
    <the fact, phrased as an instruction: what agents must NOT do, and what to do instead.
    If it retires something, tell agents to STOP and flag any task that references it.>
```

Use today's date from the environment context (do not invent one).

### Step 5 — Commit with a "why" message
```bash
git add docs/PROJECT_FACTS.md
git commit -m "facts: <subject> — <one-line why> (F-0NN, supersedes F-0MM if any)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Step 6 — Confirm to the user
Report: the new F-id, what it supersedes (if anything), and a one-line reminder that it now
loads into every session and subagent automatically.

---

## Variants
- `/remember --list` — show all `active` facts.
- `/remember --history <subject>` — show the full active + superseded timeline for a subject.
- `/remember --retire <subject>` — shortcut to mark a subject's lifecycle fact as retired.
