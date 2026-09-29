<!-- Part of /develop (~/.claude/commands/startup/develop.md). Read when executing this step. -->

## Step 7b — Phase Post-Mortem (ALWAYS runs, even on forced gates)

**Purpose:** Analyze patterns from this phase's development to improve future phases.

**Gate impact:** NONE — post-mortem is informational only, never blocks.

**Analysis:**

### 1. Failure Pattern Analysis

Read all reports in `agent_state/phases/${PHASE}/reports/`:
- Count total BLOCKING/CRITICAL/HIGH findings across all reviewers
- Group findings by category: security, architecture, style, testing, contract
- Identify repeat patterns: "Did the same type of issue appear in multiple components?"
- Example: "3 of 5 handlers missing tenantID in WHERE clause -> systemic pattern, not one-off"

### 2. Retry Analysis

Read `agent_state/phases/${PHASE}/execution.jsonl`:
- Count agents that required retries
- Identify which steps had the most failures
- Calculate: `retry_rate = agents_retried / agents_run`
- If retry_rate > 30%: flag `"⚠ High retry rate — consider improving specs or skill packs"`

```bash
# Calculate retry rate from execution log
AGENTS_RUN=$(grep '"status":"completed"' agent_state/phases/${PHASE}/execution.jsonl | wc -l)
AGENTS_RETRIED=$(grep '"status":"failed"' agent_state/phases/${PHASE}/execution.jsonl | jq -r '.agent' 2>/dev/null | sort -u | wc -l)
if [ "$AGENTS_RUN" -gt 0 ]; then
  RETRY_RATE=$(( AGENTS_RETRIED * 100 / AGENTS_RUN ))
  echo "Retry rate: ${RETRY_RATE}% (${AGENTS_RETRIED} of ${AGENTS_RUN} agents retried)"
  if [ "$RETRY_RATE" -gt 30 ]; then
    echo "⚠ High retry rate — consider improving specs or skill packs"
  fi
fi
```

### 3. Time Distribution

From `execution.jsonl`, calculate:
- % time in implementation vs testing vs review
- Ideal: ~40% implementation, ~30% testing, ~20% review, ~10% other
- Flag deviations: if review > 40%, suggest "specs may be underspecified"
- Flag: if testing > 50%, suggest "implementation quality may need improvement"

```bash
# Parse execution.jsonl for time distribution
python3 -c "
import json, sys

steps = {'implement': 0, 'test': 0, 'review': 0, 'other': 0}
step_map = {
    'audit': 'other', 'orient': 'other', 'gate': 'other', 'documentation': 'other',
    'implement': 'implement', 'database': 'implement', 'migration': 'implement',
    'backend_developer': 'implement', 'api_developer': 'implement', 'ui_developer': 'implement',
    'unit_test': 'test', 'integration_test': 'test', 'e2e': 'test', 'acceptance': 'test',
    'reconcil': 'test', 'optimiz': 'test',
    'review': 'review', 'security': 'review', 'tenant': 'review', 'quality': 'review'
}

for line in open('agent_state/phases/${PHASE}/execution.jsonl'):
    try:
        entry = json.loads(line.strip())
        if 'duration_s' in entry:
            agent = entry.get('agent', entry.get('step', 'other')).lower()
            category = 'other'
            for key, cat in step_map.items():
                if key in agent:
                    category = cat
                    break
            steps[category] += entry['duration_s']
    except: pass

total = sum(steps.values()) or 1
for cat, secs in steps.items():
    pct = int(secs * 100 / total)
    print(f'  {cat}: {pct}% ({secs:.0f}s)')

if steps['review'] * 100 / total > 40:
    print('⚠ Review time > 40% — specs may be underspecified')
if steps['test'] * 100 / total > 50:
    print('⚠ Test time > 50% — implementation quality may need improvement')
" 2>/dev/null || echo "  (time distribution unavailable — execution.jsonl missing or malformed)"
```

### 4. Carried-Forward Trend

Compare current phase's `known_issues[]` + `carried_forward[]` against previous phase:
- Are issues accumulating or being resolved?
- Severity trend: are issues getting more or less severe?
- If carried_forward count is increasing phase-over-phase: flag `"⚠ Technical debt accumulating"`

```bash
# Carried-forward trend analysis
python3 -c "
import json, os

trend = []
phase = ${PHASE}
for p in range(1, phase + 1):
    manifest_path = f'agent_state/phases/{p}/manifest.json'
    if os.path.exists(manifest_path):
        m = json.load(open(manifest_path))
        cf = len(m.get('carried_forward', []))
        ki = len(m.get('known_issues', []))
        trend.append({'phase': p, 'carried_forward': cf, 'known_issues': ki, 'total': cf + ki})
        print(f'  Phase {p}: {cf + ki} issues ({cf} carried forward, {ki} known issues)')

if len(trend) >= 2:
    prev = trend[-2]['total']
    curr = trend[-1]['total']
    if curr > prev:
        print('  Trend: DEGRADING ⚠ Technical debt accumulating')
    elif curr < prev:
        print('  Trend: IMPROVING')
    else:
        print('  Trend: STABLE')
elif len(trend) == 1:
    print(f'  Trend: BASELINE (first phase tracked)')
" 2>/dev/null || echo "  (trend analysis unavailable)"
```

### 5. Gate Health

- Did the gate pass on first attempt?
- How many gate items required fixes?
- Was the gate forced? If so, what was forced and why?

```bash
# Gate health analysis
GATE_FORCED=$(ls agent_state/phases/${PHASE}/gate.forced 2>/dev/null)
GATE_FAILED=$(ls agent_state/phases/${PHASE}/gate.failed* 2>/dev/null | wc -l | tr -d ' ')
if [ -n "$GATE_FORCED" ]; then
  echo "  Gate: FORCED — review agent_state/phases/${PHASE}/gate.forced for details"
elif [ "$GATE_FAILED" -gt 0 ]; then
  echo "  Gate: PASSED on attempt $((GATE_FAILED + 1)) (${GATE_FAILED} previous failure(s))"
else
  echo "  Gate: PASSED on first attempt"
fi
```

### Output

Write the post-mortem report to `agent_state/phases/${PHASE}/reports/postmortem.md`:

```markdown
## Phase ${PHASE} Post-Mortem

### Summary
- Gate: PASSED (attempt ${N}) | FORCED (${N} blockers overridden)
- Total findings: ${N} blocking, ${N} warning, ${N} info
- Retry rate: ${N}% (${N} of ${N} agents retried)
- Time distribution: impl ${N}% | test ${N}% | review ${N}% | other ${N}%

### Systemic Patterns
${patterns found, or "None detected"}

### Recommendations for Next Phase
- ${actionable recommendations based on patterns}

### Carried-Forward Trend
Phase 1: 0 issues -> Phase 2: 2 issues -> Phase 3 (current): 1 issue
Trend: STABLE | IMPROVING | DEGRADING

### Gate Items That Required Fixes
| Gate Item | Fix Rounds | Root Cause |
|-----------|-----------|------------|
| ${item} | ${N} | ${cause} |
```

### Manifest Addition

Add post-mortem data to the phase manifest:

```json
"postmortem": {
  "retry_rate_pct": N,
  "systemic_patterns": N,
  "carried_forward_trend": "stable|improving|degrading",
  "recommendations": ["..."]
}
```

### Execution Log Entry

```bash
echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"postmortem_complete\",\"phase\":${PHASE},\"retry_rate_pct\":${RETRY_RATE:-0},\"systemic_patterns\":${PATTERN_COUNT:-0},\"carried_forward_trend\":\"${CF_TREND:-baseline}\"}" >> agent_state/phases/${PHASE}/execution.jsonl
```
