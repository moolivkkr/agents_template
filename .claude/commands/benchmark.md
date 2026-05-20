---
command: benchmark
description: "Performance tracking and regression detection. Captures latency, throughput, memory, and bundle size metrics against NFR-* targets. Supports baselines and phase-over-phase comparison."
arguments:
  - name: phase
    required: false
    description: "Phase to benchmark. Omit to benchmark current deployed state."
  - name: save-baseline
    required: false
    default: false
    description: "Save results as the baseline for this phase. Overwrites any existing baseline."
  - name: compare
    required: false
    default: false
    description: "Compare results against the saved baseline. Flags regressions >10%."
  - name: endpoints
    required: false
    description: "Comma-separated list of specific endpoints to benchmark (e.g. '/api/v1/users,/api/v1/auth/login'). Omit to benchmark all endpoints in the phase manifest."
---

# /benchmark — Performance Tracking

Captures performance metrics and compares against NFR-* targets from the BRD. Supports saving baselines per phase and detecting regressions between runs.

**Use when:** After implementing a phase, before/after optimization, or when investigating performance concerns.

---

## Step 0 — Start Infrastructure

Ensure the application is running:

```bash
# Check if services are up
curl -sf http://localhost:<PORT>/health > /dev/null 2>&1
if [ $? -ne 0 ]; then
  echo "Services not running. Starting infrastructure..."
  docker compose up -d
  # Wait for health
  for i in $(seq 1 12); do
    curl -sf http://localhost:<PORT>/health > /dev/null 2>&1 && break
    sleep 5
  done
fi
```

Read `docs/BRD.md` for NFR-* performance targets:
- Response time targets (e.g. NFR-001: p95 < 200ms)
- Throughput targets (e.g. NFR-002: 100 req/s sustained)
- Memory limits
- Bundle size limits (if frontend)

Read phase manifest (if `--phase` specified) for endpoint list, or use `--endpoints` if provided.

```
Benchmark configuration:
  Phase:     ${PHASE:-current}
  Endpoints: [list]
  NFR targets:
    p95 latency: <target>ms
    throughput:   <target> req/s
    memory:       <target>MB
    bundle size:  <target>KB (if frontend)
```

---

## Step 1 — Run Performance Tests

**Agent:** `performance_agent`

For each endpoint in scope:

### Latency profiling
```bash
# Warm-up: 10 requests (discard results)
# Measurement: 100 requests, capture response times
# Calculate: p50, p95, p99, max
```

### Throughput testing
```bash
# Sustained load: N concurrent connections for 30 seconds
# Capture: requests/second, error rate
```

### Memory profiling
```bash
# Before benchmark: record container memory usage
docker stats --no-stream --format "{{.MemUsage}}" <container>

# After benchmark: record container memory usage
# Delta = growth during load
```

### Bundle size (if frontend exists)
```bash
# Build production bundle
# Measure: total JS, total CSS, largest chunk
# Compare against NFR target
```

### Per-endpoint results
```yaml
endpoint: GET /api/v1/users
  latency:
    p50: 12ms
    p95: 45ms
    p99: 120ms
    max: 230ms
  throughput: 150 req/s
  error_rate: 0.0%
  nfr_target: p95 < 200ms → PASS
```

---

## Step 2 — Capture Metrics

Collect all results into a structured format:

```json
{
  "timestamp": "<ISO-8601>",
  "phase": "${PHASE}",
  "git_sha": "<current HEAD>",
  "environment": {
    "container_runtime": "<docker version>",
    "memory_limit": "<container memory limit>",
    "cpu_limit": "<container cpu limit>"
  },
  "endpoints": [
    {
      "route": "GET /api/v1/users",
      "latency_p50_ms": 12,
      "latency_p95_ms": 45,
      "latency_p99_ms": 120,
      "latency_max_ms": 230,
      "throughput_rps": 150,
      "error_rate_pct": 0.0
    }
  ],
  "system": {
    "memory_before_mb": 120,
    "memory_after_mb": 145,
    "memory_delta_mb": 25
  },
  "frontend": {
    "bundle_total_kb": 280,
    "bundle_js_kb": 210,
    "bundle_css_kb": 35,
    "largest_chunk_kb": 95
  },
  "nfr_results": {
    "NFR-001": { "target": "p95 < 200ms", "actual": "45ms", "status": "PASS" },
    "NFR-002": { "target": "100 req/s", "actual": "150 req/s", "status": "PASS" }
  }
}
```

---

## Step 3 — Save Baseline (if `--save-baseline`)

```bash
mkdir -p agent_state/benchmarks
cp agent_state/benchmarks/latest.json "agent_state/benchmarks/phase-${PHASE}.json"
```

```
✅ Baseline saved: agent_state/benchmarks/phase-${PHASE}.json
   Git SHA: <sha>
   Timestamp: <timestamp>
```

If a baseline already exists for this phase, overwrite it:
```
⚠ Overwriting existing baseline for phase ${PHASE}
   Previous: <old timestamp> (<old git sha>)
   New:      <new timestamp> (<new git sha>)
```

---

## Step 4 — Compare Against Baseline (if `--compare`)

Load previous baseline:
```bash
BASELINE="agent_state/benchmarks/phase-${PHASE}.json"
```

If no baseline exists:
```
⚠ No baseline found for phase ${PHASE}
   Run with --save-baseline first, then --compare on subsequent runs.
   Showing absolute results only.
```

If baseline exists, diff every metric:

```
Performance Comparison — Phase ${PHASE}
Baseline: <baseline timestamp> (<baseline sha>)
Current:  <current timestamp> (<current sha>)

| Endpoint | Metric | Baseline | Current | Delta | Status |
|----------|--------|----------|---------|-------|--------|
| GET /api/v1/users | p95 | 45ms | 52ms | +15.6% | ⚠ REGRESSION |
| GET /api/v1/users | throughput | 150 rps | 155 rps | +3.3% | ✅ OK |
| POST /api/v1/auth | p95 | 80ms | 75ms | -6.3% | ✅ IMPROVED |
| System | memory | 145MB | 180MB | +24.1% | ⚠ REGRESSION |
```

**Regression threshold:** >10% degradation = flagged as regression.

```
Regressions detected: N
  1. GET /api/v1/users p95: 45ms → 52ms (+15.6%)
  2. System memory: 145MB → 180MB (+24.1%)

  Recommend: investigate with /diagnose or optimize with /develop --phase=${PHASE}
```

---

## Step 5 — Report

Write `agent_state/benchmarks/report-${TIMESTAMP}.md`:

```markdown
# Benchmark Report
Timestamp: ${TIMESTAMP}
Phase: ${PHASE}
Git SHA: ${GIT_SHA}

## NFR Compliance
| NFR | Target | Actual | Status |
|-----|--------|--------|--------|
| NFR-001 | p95 < 200ms | 45ms | ✅ PASS |
| NFR-002 | 100 req/s | 150 req/s | ✅ PASS |

## Endpoint Performance
| Endpoint | p50 | p95 | p99 | Max | Throughput | Errors |
|----------|-----|-----|-----|-----|------------|--------|
| GET /api/v1/users | 12ms | 45ms | 120ms | 230ms | 150 rps | 0.0% |
| POST /api/v1/auth | 25ms | 80ms | 150ms | 310ms | 120 rps | 0.0% |

## System Resources
| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Memory | 120MB | 145MB | +25MB |

## Frontend Bundle (if applicable)
| Asset | Size | Target | Status |
|-------|------|--------|--------|
| Total JS | 210KB | < 500KB | ✅ PASS |
| Total CSS | 35KB | < 100KB | ✅ PASS |
| Largest chunk | 95KB | < 200KB | ✅ PASS |

## Phase-over-Phase Trend (if baselines exist)
| Phase | p95 avg | Throughput avg | Memory |
|-------|---------|----------------|--------|
| Phase 1 | 30ms | 180 rps | 100MB |
| Phase 2 | 42ms | 165 rps | 130MB |
| Phase 3 | 48ms | 155 rps | 145MB |

## Regressions
[List or "None detected"]

## Recommendations
[Optimization suggestions based on results]
```

Output summary:
```
✅ Benchmark complete → wrote agent_state/benchmarks/report-${TIMESTAMP}.md

  NFR compliance: N/N PASS
  Regressions:    N detected | None
  Baseline:       saved | not saved (use --save-baseline)
```

---

## Rules

- Benchmarks run against the DEPLOYED application — not unit tests or mocked services
- Infrastructure must be running before benchmarking — Step 0 ensures this
- Always include warm-up requests before measurement — cold starts skew results
- Memory measurements use container stats, not application-level profiling
- Regression threshold is 10% — below that is noise, above that is a finding
- Baselines are per-phase — each phase can have its own performance expectations
- Never modify application code during a benchmark run — measure what exists
