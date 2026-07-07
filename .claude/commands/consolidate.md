---
command: consolidate
description: Off-critical-path memory maintenance — dedup, merge, compress Tier 1 lessons/patterns, recalibrate confidence, and audit Tier 0 facts for drift. Non-destructive.
arguments:
  - name: dry_run
    required: false
    default: false
    description: "Report the proposed changes without writing them."
---

# /consolidate — Sleep-Time Memory Maintenance

> **Read Tier 0 first.** Load `docs/PROJECT_FACTS.md` (ground-truth invariants) before sweeping.
> Honor retired/renamed facts — a lesson referencing a retired component is a supersession candidate,
> not a live pattern.

Memory grows monotonically during a run: every phase appends lessons, patterns bloat, facts pile up.
`/consolidate` is a **background, off-critical-path** pass (Letta "sleep-time compute") that keeps
Tier 1 and Tier 0 healthy **without ever deleting**. It runs *between* phases or on demand, never in
the hot path of `/develop`.

**Non-destructive invariant:** this command **never deletes** an entry. It only **supersedes**,
**merges** (leaving a provenance trail), **archives**, or **recalibrates confidence**. History is
always recoverable from git.

---

## The Novelty Gate (SAGE-style) — applies to every write

Before writing/merging any entry, classify it against existing memory to avoid burning LLM cycles on
obvious cases:

| Verdict | Condition | Action | Cost |
|---|---|---|---|
| **ADD** | Clearly novel — no existing entry shares its `(category, tags)` cluster | Append as new entry | cheap (grep) |
| **NOOP** | Clearly redundant — a near-identical entry already exists (same summary/pattern) | Skip; bump evidence count on the existing entry | cheap (grep) |
| **MERGE** | Uncertain middle — overlaps an existing entry but adds detail | LLM-merge the two into one richer entry | expensive (LLM) |

Only the **uncertain middle** reaches the LLM. In practice ADD/NOOP catch the clear majority, so the
LLM-merge path handles roughly **16-18%** of writes — the rest are decided by grep against the
`Index by Category` / `Index by Tag` (see `structured-lessons.md` and `memory-as-tools.md`).

---

## Step 0 — Snapshot (safety)

```bash
git add -A && git stash list >/dev/null   # ensure clean read
TS=$(date +%Y%m%d-%H%M%S)
mkdir -p agent_state/archive
# Archive current copies before any supersession (non-destructive trail)
cp agent_state/lessons.md  agent_state/archive/lessons.${TS}.md  2>/dev/null || true
cp agent_state/patterns.md agent_state/archive/patterns.${TS}.md 2>/dev/null || true
```

---

## Step 1 — Sweep Tier 1: `lessons.md` + `patterns.md`

Using the structured index (never load whole — retrieve per `memory-as-tools.md`):

1. **Dedup** — entries with matching `(category, tags, summary)` collapse. Apply the novelty gate:
   NOOP the duplicate, increment the survivor's evidence/occurrence note.
2. **Merge superseded/redundant** — where a later lesson refines an earlier one, MERGE (LLM) into a
   single entry; mark the older as `superseded_by: <id>` (kept, not deleted).
3. **Compress bloated sections** — long `Detail:` prose is tightened to its reusable core; the verbose
   original stays in the git-archived copy from Step 0.
4. **Recalibrate confidence** — apply the existing rules from `structured-lessons.md`:
   - Pattern re-used successfully in a later phase → **upgrade** LOW→MEDIUM or MEDIUM→HIGH
   - Pattern that caused issues later → **downgrade** to DEPRECATED with a reason
   - Never silently drop a DEPRECATED pattern — keep it as an anti-pattern signal
5. **Rebuild the index** — regenerate `Index by Category` / `Index by Tag` so retrieval stays accurate.

Each change records provenance: `merged_from: [L-2-003, L-4-001]`, `confidence_change: MEDIUM→HIGH (phase 5 reuse)`.

---

## Step 2 — Sweep Tier 0: `docs/PROJECT_FACTS.md`

Audit for **supersession drift** per `shared-context-protocol.md`'s deterministic rule
(`(subject, relation)` key):

```
For every pair of facts with status: active:
  if fact_A.subject == fact_B.subject AND fact_A.relation == fact_B.relation:
     FLAG — two ACTIVE facts share a (subject, relation) key (invariant violated)
```

- Two ACTIVE facts on the same `(subject, relation)` → **flag drift**. Apply the tie-break (most recent
  `valid_from` wins; the loser is marked `status: superseded`, **not deleted**).
- A fact whose subject no longer exists in the codebase → flag as a candidate for retirement (do not
  auto-retire; surface for human confirmation — facts are ground truth).

`/consolidate` never invents facts. It only detects and repairs the "two active facts, same key"
condition and reports drift.

---

## Step 3 — Report

```
Memory Consolidation — <timestamp>

  Tier 1 lessons/patterns:
    Entries in:  84   →  out: 71   (13 merged/deduped, 0 deleted)
    Novelty gate: ADD 6 · NOOP 22 · MERGE 5   (LLM touched 17% of writes)
    Confidence:  ↑ 3 upgraded · ↓ 1 deprecated
    Index rebuilt: Index by Category, Index by Tag

  Tier 0 facts:
    Active facts: 12   Drift flagged: 1 (subject=queue-svc, relation=port — 2 active)
    Superseded (tie-break, most-recent wins): 1
    Retirement candidates (need human confirm): 1

  Archive: agent_state/archive/{lessons,patterns}.<ts>.md   (git-recoverable)
```

With `--dry_run`, print the report and the proposed diffs **without writing** — no supersession, no
index rebuild, no archive mutation beyond the read snapshot.

---

## When to run

- **Between phases** (post-gate, off critical path) — the natural sleep-time window.
- **Before `/accept`** — enter global acceptance with clean, deduped memory.
- **On demand** when `lessons.md`/`patterns.md` feel bloated or an agent reports stale patterns.

Never run *inside* `/develop`'s waves — consolidation is deliberately off the hot path so it never
competes with implementation for context or time.
