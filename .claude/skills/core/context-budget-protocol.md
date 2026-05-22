# Context Budget Protocol

## Core Principle: Quality Over Token Savings

Optimize agent prompts and context for **output quality**, not token efficiency. A/B testing proved verbose context produces measurably better results (+7.7% on judgment tasks). An agent that makes wrong decisions because it lacked context costs far more to fix than a larger context payload.

**Rules:**
- Never truncate acceptance criteria, security requirements, or coding conventions to save tokens
- `phase_context.md` is 6-8K but replaces 30-70K of raw docs — this is the RIGHT trade-off
- When `agent_state/codebase/` exists, load the relevant focus document — the extra 5-10K prevents avoidable implementation errors
- More context for judgment steps (review, acceptance, debugging) > less context for speed

## Auto-Compact Protocol — Context Pressure Relief

Performance degrades sharply once context usage exceeds ~80%. The framework enforces a **75% threshold** — at every wave boundary (and between major pipeline steps), the parent session checks context pressure and triggers compaction before degradation begins.

### When to check
- **Between every wave** in `/develop` orchestrator (after writing the wave checkpoint)
- **Between major steps** in `/plan`, `/accept`, `/review` (after each step completes)
- **Any long-running command** that spawns 3+ sequential subagents

### What to do at 75%

When context usage reaches 75%, execute this sequence **immediately** — do not start the next wave/step:

1. **Save state** — write/update the wave checkpoint (should already be written at wave boundary):
   ```
   agent_state/phases/${PHASE}/checkpoints/wave-${WAVE_NUM}.json
   ```
   Include `"compacted_at_wave": ${WAVE_NUM}` in the checkpoint so `/resume` knows compaction occurred.

2. **Write a compact context summary** — a single structured file that captures everything the next wave needs:
   ```
   agent_state/phases/${PHASE}/checkpoints/compact-context.md
   ```
   Contents:
   ```markdown
   # Compact Context — Phase ${PHASE} (post-Wave ${WAVE_NUM})
   Generated: <timestamp>
   Reason: context window at 75% — auto-compacted before Wave ${NEXT_WAVE}

   ## Phase Goal
   <1 line from phase_context.md>

   ## Completed Waves
   - Wave 1: <summary from checkpoint> — artifacts: [list]
   - Wave 2: <summary from checkpoint> — artifacts: [list]
   ...

   ## Key Decisions Made This Session
   - <any architectural decisions or deviations noted during implementation>

   ## Current State
   - Last git SHA: <sha>
   - Tests passing: <yes/no/not-yet-run>
   - Blocking issues: <none or list>

   ## Next Steps
   - Wave ${NEXT_WAVE}: <what needs to happen>
   - Remaining waves: [list]
   ```

3. **Run `/compact`** — invoke Claude Code's built-in context compression.

4. **Resume inline** — after compaction, read `compact-context.md` + `phase_context.md` and continue from Wave ${NEXT_WAVE}. Do NOT start a new conversation — compaction is a mid-session refresh, not a session break.

### Key constraints
- **Never compact mid-wave** — only at wave boundaries after checkpoint is written
- **Never skip compaction** — if 75% is reached, compact before proceeding. The 5% gap before 80% is your safety margin.
- **Subagent context is independent** — subagent spawns get fresh context windows. This protocol applies to the PARENT orchestrator session only.
- **compact-context.md replaces scrollback** — after compaction, the parent reads this file instead of relying on conversation history. This is why it must be complete.

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
