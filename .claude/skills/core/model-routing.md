---
skill: model-routing
description: Model and effort policy for spawned agents - Opus 5.5 everywhere with per-agent effort, Fable only for escalation and cross-model verification; the complexity score that other skills consume
version: "2.0"
tags:
  - model-routing
  - effort
  - cost
  - complexity
  - core
---

# Model and Effort Routing

## Policy

Every agent runs on Claude Opus 5.5 (`model: opus` in its frontmatter) at the `effort` its frontmatter sets: `high` for reviewers, verifiers, security and implementation agents, `medium` for writers and planners, `low` for mechanical runners. One model family means one prompt-cache namespace across the pipeline, and on current models the strongest model at a lower effort matches or beats a smaller model at a higher one, at a similar cost per completed task.

**When spawning an agent, don't pass a `model` parameter.** A per-launch `model` overrides the agent's frontmatter, so passing one silently undoes the policy above. The two exceptions are the only times to pass it:

| Situation | Pass | Why |
|---|---|---|
| Retry after the agent's first attempt failed on an external signal (failing tests, a reviewer's blocking finding, a gate miss) | `model: fable` | The most capable model on the second attempt; the failure is the evidence the task needs it. Log it (below). |
| Layer 3 adversarial verification in `gate-verification.md` | `model: fable` | Work is produced on Opus; verifying on a different model avoids sharing its blind spots. |

Don't escalate pre-emptively on a high score - high complexity is handled by workflow depth (`scale-adaptive-depth.md`) and by candidate selection (`candidate-selection.md`), which pay for more attempts only where they help.

## Complexity score

The orchestrator still computes a complexity score once per phase and persists it in `agent_state/phases/${PHASE}/complexity.json` as `raw_score`; `scale-adaptive-depth.md` and `candidate-selection.md` (trigger `RAW_SCORE > 60`) read it.

| Signal | Measurement | Weight |
|---|---|---|
| Spec file count | `ls docs/design/phases/${PHASE}/specs/*.md \| wc -l` | 3x |
| Source file count (phase diff) | `git diff --name-only \| grep -E '\.(go\|ts\|tsx\|py)$' \| wc -l` | 2x |
| Total LOC changed | `git diff --stat \| tail -1` (insertions + deletions) | 1x per 500 |
| Number of FR-* in scope | `grep -c 'FR-' PHASE_PLAN.md` | 2x |
| Has UI components | `ls specs/*.wireframe.md 2>/dev/null \| wc -l` | 5 if any |
| Previous phase had failures | `test -f agent_state/phases/$((PHASE-1))/reports/collective_feedback.md` | 10 if present |

```text
RAW_SCORE = (spec_count * 3) + (source_files * 2) + (loc_changed / 500) + (fr_count * 2) + (has_ui * 5) + (prev_failures * 10)
```

Rough bands for reading it: up to 10 is small, 11-40 is typical, above 40 is large, above 60 triggers candidate selection.

## Logging

Log every escalation to `execution.jsonl`, so post-gate lessons can show which agents need it repeatedly - an agent that escalates often needs a better prompt or a higher frontmatter effort:

```json
{"ts":"<ISO>","event":"model_escalation","agent":"backend_developer","from":"opus","to":"fable","reason":"integration tests failed after first attempt"}
```

## Cost check after a phase

`/usage` in the session shows the phase's spend and attributes it to subagents, skills, and MCP servers. Record the total in `manifest.json` under `cost_estimate`, along with the number of escalations.

> Config blocks checked 2026-09-30 (`bash tests/archetype-compile/config-packs/run.sh --live`): 1 JSON block parsed.
