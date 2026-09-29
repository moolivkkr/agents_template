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

## Long Sessions and Compaction

The main session runs with a 1M-token context window, and Claude Code compacts the conversation automatically as it nears the limit. Don't pause, wrap up, or skip steps because a session is getting long - that costs more than any context it saves. Only the user can run `/compact`, so never plan around running it.

What keeps a long pipeline safe across a compaction or a `/resume` is the resume summary: at every wave boundary in `/develop`, and after each major step in `/plan`, `/accept`, and `/review`, update `agent_state/phases/${PHASE}/checkpoints/compact-context.md` so it stands on its own:
- `## RESUME INSTRUCTIONS` - read this file and `phase_context.md`, continue with the next wave, don't re-run earlier waves
- `## Completed Waves` - summary and artifacts from each checkpoint JSON
- `## Key Decisions` - architectural choices made during the session
- `## Current State` - git SHA, test status, blocking issues
- `## Next Steps` - what the next wave does and what remains after it

After a compaction or a resumed session, read that file first, then `phase_context.md`, and continue. Subagents start with fresh context windows, so this applies to the parent session only.

## Agent Result Discipline
Every agent ends with the short final message its operating contract defines (status, files written, gate counts, blockers), or with the command-specific return format where a command defines one. The full output is in the file; the parent conversation receives only that summary.
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
