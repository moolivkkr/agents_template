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

The LANGUAGE step (classify the fact) is yours; the MECHANICAL step (id assignment, deterministic
supersession, atomic append, file creation) is done by `.claude/hooks/remember.sh` — do NOT hand-edit
`docs/PROJECT_FACTS.md`. This is deliberate: the script does the exact `(subject, relation)` key match
and status-flip atomically, so two contradictory facts can never both be `active` (a hand edit can
silently skip the supersession).

### Step 1 — Classify the fact
From the user's text, extract:
- **subject** — the entity the fact is about (e.g. `vertix-gateway`). Lowercase, kebab.
- **relation** — one of: `lifecycle` (retired/active/deprecated), `name` (renamed/canonical),
  `constraint` (a rule), `environment` (a gotcha), `boundary` (off-limits).
- **title** — a short human heading (e.g. "vertix-gateway is RETIRED").
- **fact text** — phrased as an INSTRUCTION: what agents must NOT do, and what to do instead. If it
  retires something, tell agents to STOP and flag any task that references it.

### Step 2 — Record it deterministically (script does supersession + append + id assignment)
```bash
.claude/hooks/remember.sh add \
  --subject "<subject>" --relation "<lifecycle|name|constraint|environment|boundary>" \
  --title "<short title>" --date "<today YYYY-MM-DD from the environment context>" \
  --fact "<the instructional fact text>"
```
The script prints the new `F-id` and what it superseded (the exact `(subject, relation)` match — never
semantic similarity; embeddings cannot distinguish a contradiction from a duplicate, the key can). It
creates `docs/PROJECT_FACTS.md` from the template (stripping the example) on first use, flips any prior
active fact on the same key to `superseded` with `invalid_at`/`superseded_by` stamped, and appends the
new active block. Use today's date from the environment context (do not invent one).

`/remember --retire <subject>` → `remember.sh retire --subject <subject> --date <today> --title ... --fact ...`

### Step 3 — Commit with a "why" message
```bash
git add docs/PROJECT_FACTS.md
git commit -m "facts: <subject> — <one-line why> (F-0NN, supersedes F-0MM if any)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Step 4 — Confirm to the user
Report: the new F-id (from the script's stdout), what it supersedes (if anything), and a one-line
reminder that it now loads into every session and subagent automatically.

---

## Variants
- `/remember --list` — show all `active` facts.
- `/remember --history <subject>` — show the full active + superseded timeline for a subject.
- `/remember --retire <subject>` — shortcut to mark a subject's lifecycle fact as retired.
