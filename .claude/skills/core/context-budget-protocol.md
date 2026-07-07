---
skill: context-budget-protocol
description: Context budget discipline — selective loading, summarization, and INDEX/frontmatter-driven skill retrieval to stay within the window
version: "1.0"
tags:
  - context
  - tokens
  - selective-loading
  - efficiency
  - core
---

# Context Budget Protocol

## Core Principle: Quality Over Token Savings

Optimize agent prompts and context for **output quality**, not token efficiency. A/B testing proved verbose context produces measurably better results (+7.7% on judgment tasks). An agent that makes wrong decisions because it lacked context costs far more to fix than a larger context payload.

**Rules:**
- Never truncate acceptance criteria, security requirements, or coding conventions to save tokens
- `phase_context.md` is 6-8K but replaces 30-70K of raw docs — this is the RIGHT trade-off
- When `agent_state/codebase/` exists, load the relevant focus document — the extra 5-10K prevents avoidable implementation errors
- More context for judgment steps (review, acceptance, debugging) > less context for speed

## Auto-Compact Protocol — Context Pressure Relief

Performance degrades sharply once context usage exceeds ~80%. The framework enforces a **75% threshold** — at every wave boundary (and between major pipeline steps), the parent session assesses context pressure and triggers compaction before degradation begins.

### How to detect context pressure (concrete signals)

Claude Code does NOT expose a `context_percentage` API. Use these proxy signals:

| Signal | Threshold | Confidence |
|--------|-----------|------------|
| Waves completed with subagent spawns | 3+ waves | High — each wave adds ~15-25K tokens |
| System compression already triggered | Any "[earlier messages compressed]" notice | Definitive — you are past 75% |
| Total tool calls in this session | 15+ tool calls | Medium — depends on result sizes |
| Estimated cumulative tokens | ~150K consumed (75% of 200K) | High — track per-wave: ~20K per subagent spawn |

**Rule: when in doubt, compact.** Cost of unnecessary compaction: ~5 seconds. Cost of degraded output at 80%+: wrong code, dropped steps, missed reviews.

### When to check
- **Between every wave** in `/develop` orchestrator (after writing the wave checkpoint)
- **Between major steps** in `/plan`, `/accept`, `/review` (after each step completes)
- **Any long-running command** that spawns 3+ sequential subagents

### What to do when triggered

1. **Save state** — write/update the wave checkpoint (should already be written at wave boundary). Add `"compacted_before_next": true` and `"compact_context_path"` to the checkpoint JSON.

2. **Write `compact-context.md`** — a self-contained bootstrap file. This is the ONLY file the orchestrator reads after compaction (plus `phase_context.md`). It MUST include:
   - `## RESUME INSTRUCTIONS` — explicit "read this file, continue to Wave N+1, do NOT re-run earlier waves"
   - `## Completed Waves` — summary + artifacts from each checkpoint JSON
   - `## Key Decisions` — architectural choices made during this session
   - `## Current State` — git SHA, test status, blocking issues
   - `## Next Steps` — what the next wave does and what remains after

3. **Announce:** `"⚡ Context pressure detected — compacting before Wave N. Resuming inline."`

4. **Run `/compact`** — invoke Claude Code's built-in context compression.

5. **Post-compact bootstrap** — immediately read `compact-context.md` (the RESUME INSTRUCTIONS tell exactly what to do) + `phase_context.md`, then continue. Do NOT start a new conversation.

### Key constraints
- **Never compact mid-wave** — only at wave boundaries after checkpoint is written
- **When in doubt, compact** — false positive is cheap; false negative degrades everything after
- **Subagent context is independent** — subagent spawns get fresh context windows. This protocol applies to the PARENT orchestrator session only.
- **compact-context.md is the post-compact source of truth** — it replaces conversation scrollback. That's why it must be self-contained with explicit resume instructions.

## Agent Result Discipline
Every agent (subagent or inline) must end with this exact pattern:
```
✅ <agent-name> complete → wrote <output-file-path>
   Summary: <3 lines max of what was done>
   Issues: none | <count + severity>
```
The full output is in the file. The parent conversation receives only the summary above.
**Never echo file contents back to the parent conversation.**

## Read Discipline
- Read a file → act on it → do not re-read the same file in the same step
- Never load the same document twice in one step
- `phase_context.md` is read once at Step 0 and referenced from memory

## Step Isolation
Each step is a complete unit. After a step writes its output files, the conversation for that step is finished. If the conversation window fills mid-step, the step can be resumed by reading the output files already written.

## Analysis Paralysis Guard
If an agent makes **5+ consecutive read-only tool calls** without any write action:
1. **Stop exploring** — do not make another read call
2. **State the blocker** in 1 line
3. **Take action** — write code to resolve OR return to parent with `status: blocked`

**Exception:** Audit agents (`backend_audit_agent`, `ui_audit_agent`) are read-only by design.
