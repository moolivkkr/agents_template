# Memory-as-Tools — Retrieval Discipline for Tier 1 / Tier 2

> **Read Tier 0 first.** `docs/PROJECT_FACTS.md` (ground-truth invariants) is ALWAYS loaded whole —
> it is tiny. Honor retired/renamed facts before retrieving anything below. This skill governs the
> **larger** tiers, which must never be loaded whole.

`shared-context-protocol.md` defines the three memory tiers and states the read discipline:
Tier 0 is always carried; **Tier 1 (`agent_state/lessons.md`, `agent_state/patterns.md`) and
Tier 2 (`agent_state/codebase/`) are retrieved, never loaded whole.** This skill is the **read side**
of `structured-lessons.md` — that skill defines the *Index by Category / Index by Tag* write format;
this one defines how agents *query* it.

Loading whole lessons/patterns/codebase files can be tens of KB of context per agent per session.
Targeted retrieval is roughly a **~90% token reduction** for the same relevance. No vector DB, no
embeddings — **grep over the existing index + git**.

---

## The Retrieval Tools

These are conventions (grep recipes), not new infrastructure. Every agent that would otherwise `cat`
a Tier 1/Tier 2 file uses these instead.

### `memory_search <category|tag|keyword>`

Index-backed lookup that returns **entry IDs**, not full text. Backed by the `Index by Category` /
`Index by Tag` sections that `structured-lessons.md` already maintains.

**Source files.** `agent_state/patterns.md` and `agent_state/lessons.md` are the repo-root indices.
Lessons are authored per-phase (`agent_state/phases/N/lessons.md`) and aggregated into the root
`lessons.md` at each phase gate (develop-orchestrator Post-Gate). Recipes below read the root index
first and fall back to the per-phase files, so retrieval works even if aggregation hasn't run yet.

```bash
# Lesson/pattern sources: root indices + per-phase lesson files (fallback).
_mem_sources() {
  ls agent_state/patterns.md agent_state/lessons.md agent_state/phases/*/lessons.md 2>/dev/null
}

# 1. Resolve IDs from the index (cheap — index is small)
memory_search() {
  local q="$1"
  # Try the category/tag index first (exact section lines)
  grep -iE "^- (${q}):" $(_mem_sources) 2>/dev/null
  # Fall back to a keyword scan over entry summaries only
  grep -inE "^\s*-\s*\*\*(Summary|Pattern|Tags)\:\*\*.*${q}" \
       $(_mem_sources) 2>/dev/null
}
```

Returns lines like `- security: P-005, P-006` or matching summary lines with their entry heading.
The agent then fetches only the IDs it needs.

### `memory_get <id>`

Fetch a single entry block by ID (e.g. `P-005`, `L-3-002`) — the smallest useful unit.

```bash
memory_get() {
  local id="$1"
  # Print from the "### <id>" heading to the next "### " heading
  awk -v id="### ${id}" '
    $0 ~ "^"id"([^0-9]|$)" {p=1}
    p && /^### / && $0 !~ "^"id"([^0-9]|$)" && NR>1 {exit}
    p {print}
  ' agent_state/lessons.md agent_state/patterns.md agent_state/phases/*/lessons.md 2>/dev/null
}
```

### File-scoped priming (Metaswarm "bd prime")

Before an agent starts work on a set of files, **prime** it with only the lessons whose tags match
those files or the task keywords — nothing else. This is the default retrieval for developer/fix/UI
agents at wave start.

```bash
# Derive tags from the task's target files, then retrieve matching lessons only.
# e.g. touching internal/auth/*.go + a "go" project → prime tags: go, auth, security
memory_prime() {
  # $@ = keywords/tags derived from changed files + task language
  for tag in "$@"; do
    memory_search "$tag"
  done | grep -oE '[PL]-[0-9]+(-[0-9]+)?' | sort -u | while read -r id; do
    memory_get "$id"
  done
}
```

Result: an agent editing `internal/auth/session.go` in a Go project loads the ~3 auth/go lessons that
matter, not the 40-entry `patterns.md`.

---

## Retrieval Recipes by Agent

| Agent / phase | Retrieval call | Loads |
|---|---|---|
| `project_planner` (`/plan`) | `memory_search <phase-domain>` then `memory_get` the top IDs | Patterns for this phase's domain only |
| `backend_developer` / `ui_developer` (Wave 2) | `memory_prime <lang> <tags-from-target-files>` | Language + file-scoped patterns |
| `fix` agent (Wave 5) | `memory_search <failure-category>` → `memory_get` matching IDs | Only lessons in the failing category |
| any agent needing structure | Tier 2: read the **one focused doc** under `agent_state/codebase/`, never the whole dir | Single focused KB file |

**Tier 2 rule:** `agent_state/codebase/` is loaded by *focused file*, not directory. If `/map` produced
`codebase/auth.md`, an auth task reads that file only. Use the codebase index/manifest to pick the file,
the same way `memory_search` picks an ID.

---

## Rules

1. **Never `cat` a whole Tier 1/Tier 2 file** in an agent prompt. If you catch yourself loading
   `patterns.md` or `lessons.md` in full, replace it with `memory_search` + `memory_get`.
2. **Index-first.** Query the `Index by Category` / `Index by Tag` sections before scanning bodies —
   the index exists precisely so you don't scan bodies.
3. **Prime by task scope.** Retrieve lessons whose tags intersect the current task's files/keywords;
   ignore the rest. Irrelevant lessons are context pollution, not safety.
4. **Fallback is read-focused, not read-all.** If no structured index exists yet (pre-migration flat
   file), grep the flat file for the task keywords — still targeted, never whole-file.
5. **No new infra.** grep + the existing index + git only. No vector store, no embedding step.

## Why this works without a vector DB

`structured-lessons.md` already forces every entry to carry `Category` + `Tags` and maintains an
inverted index (Index by Category / Index by Tag). That inverted index **is** the retrieval structure —
grep against it gives keyword-precision lookups at near-zero cost. The uncertain-match middle that a
vector DB would help with is rare at project-lesson scale (dozens of entries, not millions), so the
grep index captures ~all the value at none of the infrastructure cost.
