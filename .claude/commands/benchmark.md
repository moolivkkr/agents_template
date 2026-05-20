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

Captures metrics and compares against NFR-* targets from BRD. Supports per-phase baselines and regression detection.

**Use when:** After implementing a phase, before/after optimization, or investigating performance concerns.

---

## Step 0 — Start Infrastructure

```bash
curl -sf http://localhost:<PORT>/health > /dev/null 2>&1 || {
  echo "Starting infrastructure..."
  docker compose up -d
  for i in $(seq 1 12); do
    curl -sf http://localhost:<PORT>/health > /dev/null 2>&1 && break
    sleep 5
  done
}
```

Read `docs/BRD.md` for NFR-* targets (response time, throughput, memory, bundle size). Read phase manifest for endpoint list.

---

## Step 1 — Run Performance Tests

**Agent:** `performance_agent`

For each endpoint:

- **Latency:** 10 warm-up requests (discard), 100 measured → p50, p95, p99, max
- **Throughput:** N concurrent connections for 30s → req/s, error rate
- **Memory:** `docker stats` before/after → delta
- **Bundle size (UI):** production build → total JS, CSS, largest chunk

Per-endpoint result format:
```yaml
endpoint: GET /api/v1/users
  latency: { p50: 12ms, p95: 45ms, p99: 120ms, max: 230ms }
  throughput: 150 req/s
  error_rate: 0.0%
  nfr_target: p95 < 200ms → PASS
```

---

## Step 2 — Capture Metrics

Collect into structured JSON: timestamp, phase, git SHA, environment (docker version, memory/cpu limits), per-endpoint metrics, system memory, frontend bundle sizes, NFR pass/fail results.

---

## Step 3 — Save Baseline (if `--save-baseline`)

```bash
mkdir -p agent_state/benchmarks
cp agent_state/benchmarks/latest.json "agent_state/benchmarks/phase-${PHASE}.json"
```

Overwrites existing baseline with warning.

---

## Step 4 — Compare Against Baseline (if `--compare`)

Load `agent_state/benchmarks/phase-${PHASE}.json`. No baseline → show absolute results only.

Diff every metric. **Regression threshold: >10% degradation.**

```
| Endpoint | Metric | Baseline | Current | Delta | Status |
| GET /api/v1/users | p95 | 45ms | 52ms | +15.6% | REGRESSION |
| System | memory | 145MB | 180MB | +24.1% | REGRESSION |
```

---

## Step 5 — Report

Write `agent_state/benchmarks/report-${TIMESTAMP}.md`: NFR compliance table, endpoint performance, system resources, frontend bundle, phase-over-phase trend (if baselines exist), regressions, recommendations.

```
✅ Benchmark complete → wrote agent_state/benchmarks/report-${TIMESTAMP}.md
  NFR compliance: N/N PASS
  Regressions: N detected | None
  Baseline: saved | not saved (use --save-baseline)
```

---

## Rules

- Benchmarks run against DEPLOYED application — not mocked services
- Infrastructure must be running before benchmarking
- Always include warm-up requests — cold starts skew results
- Memory uses container stats, not application-level profiling
- Regression threshold: 10% — below is noise, above is a finding
- Baselines are per-phase
- Never modify application code during a benchmark
