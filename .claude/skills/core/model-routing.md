# Complexity-Based Model Routing Protocol

Agents currently use a hardcoded model per role (e.g., spec_impl_reconciler always uses opus).
This protocol enables `model: auto` — the orchestrator selects the model based on task complexity,
saving cost on trivial tasks without sacrificing quality on complex ones.

---

## Routing Tiers

| Tier | Model | Latency | Cost | When to Use |
|------|-------|---------|------|-------------|
| 1 | haiku | ~300ms | Low | Simple, bounded tasks: file existence checks, format validation, small diffs |
| 2 | sonnet | ~1.5s | Medium | Standard work: spec writing, code review, test generation for <10 files |
| 3 | opus | ~3s | High | Complex reasoning: architecture decisions, security audit, multi-file reconciliation |

## Complexity Heuristic

When an agent is defined with `model: auto`, the orchestrator computes a complexity score
before spawning it. The score is based on input size, not agent type.

### Input Signals

| Signal | Measurement | Weight |
|---|---|---|
| Spec file count | `ls docs/design/phases/${PHASE}/specs/*.md \| wc -l` | 3x |
| Source file count (phase diff) | `git diff --name-only \| grep -E '\.(go\|ts\|tsx\|py)$' \| wc -l` | 2x |
| Total LOC changed | `git diff --stat \| tail -1` (insertions + deletions) | 1x |
| Number of FR-* in scope | `grep -c 'FR-' PHASE_PLAN.md` | 2x |
| Has UI components | `ls specs/*.wireframe.md 2>/dev/null \| wc -l` | 1x |
| Previous phase had failures | `test -f agent_state/phases/$((PHASE-1))/reports/collective_feedback.md` | 2x |

### Scoring

```
RAW_SCORE = (spec_count * 3) + (source_files * 2) + (loc_changed / 500) + (fr_count * 2) + (has_ui * 5) + (prev_failures * 10)

if RAW_SCORE <= 10:  model = haiku
elif RAW_SCORE <= 40: model = sonnet
else:                 model = opus
```

### Override Rules (always escalate to opus)

Regardless of score, use opus for:
- `security_reviewer` — security reasoning needs maximum capability
- `acceptance_test_agent` — final validation, cannot afford false positives
- `spec_impl_reconciler` — 4-level verification requires deep code understanding
- `debate_arbitrator` — decision-making needs nuanced reasoning
- Any agent where `quality_gates` contains security-related checks

### Override Rules (can downgrade to haiku)

Regardless of score, haiku is sufficient for:
- `test_runner` — just executes commands and reports output
- `dependency_scanner` — structured tool output parsing
- File existence checks, format validation, JSONL parsing

## How to Apply

### In agent definitions (frontmatter)

```yaml
model: auto  # orchestrator picks based on complexity
```

### In orchestrator (develop-orchestrator, accept)

When spawning an agent with `model: auto`:

```
1. Read phase_context.md for spec count, FR-* count
2. Run: git diff --stat to get LOC changed
3. Compute RAW_SCORE
4. Select model tier
5. Log selection: "Agent ${NAME}: score=${SCORE} → model=${MODEL}"
6. Spawn agent with selected model
```

### Logging

Every model routing decision is logged to `execution.jsonl`:

```json
{"ts":"<ISO>","event":"model_route","agent":"spec_writer","raw_score":25,"model":"sonnet","signals":{"spec_count":3,"source_files":8,"loc_changed":450,"fr_count":4}}
```

This data feeds Post-Gate lessons — if agents routed to sonnet frequently fail and need opus retries, the scoring thresholds need adjustment.

## Gradual Rollout

Phase 1 (now): Document the protocol. All agents keep their current hardcoded models.
Phase 2: Add `model: auto` to low-risk agents first (spec_writer, code_reviewer_I, backend_audit_agent).
Phase 3: Expand to all agents except security and reconciliation.
Phase 4: Full auto-routing with per-project threshold tuning from execution.jsonl data.

## Cost Tracking

After each phase, the orchestrator estimates token cost:

```
Estimated cost (Phase ${PHASE}):
  opus agents:  N × ~$0.15/agent = $X.XX
  sonnet agents: N × ~$0.03/agent = $X.XX
  haiku agents:  N × ~$0.005/agent = $X.XX
  Total: $X.XX (vs $X.XX if all-opus)
  Savings: $X.XX (N%)
```

Written to `manifest.json` under `cost_estimate` field.
