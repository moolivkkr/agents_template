# Context Budget Protocol

## Core Principle: Quality Over Token Savings

Optimize agent prompts and context for **output quality**, not token efficiency. A/B testing proved verbose context produces measurably better results (+7.7% on judgment tasks). An agent that makes wrong decisions because it lacked context costs far more to fix than a larger context payload.

**Rules:**
- Never truncate acceptance criteria, security requirements, or coding conventions to save tokens
- `phase_context.md` is 6-8K but replaces 30-70K of raw docs — this is the RIGHT trade-off
- When `agent_state/codebase/` exists, load the relevant focus document — the extra 5-10K prevents avoidable implementation errors
- More context for judgment steps (review, acceptance, debugging) > less context for speed

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
