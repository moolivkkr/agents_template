# Load testing patterns for performance validation and capacity planning.

## Test Types

| Type | Purpose | Pattern | Duration |
|------|---------|---------|----------|
| **Load** | Verify system handles expected traffic | Ramp to target, hold steady | 5-15 min |
| **Stress** | Find the breaking point | Ramp beyond capacity until errors | 10-20 min |
| **Soak** | Detect memory leaks, connection pool exhaustion | Steady load for extended period | 1-4 hours |
| **Spike** | Verify recovery from traffic bursts | Sudden jump to 10x, then back | 5-10 min |

## Key Metrics

| Metric | What It Tells You | Healthy Target |
|--------|-------------------|----------------|
| **p50 latency** | Median response time | < 100ms for APIs |
| **p95 latency** | Tail latency (most users) | < 500ms |
| **p99 latency** | Worst-case latency | < 1s |
| **Throughput** | Requests per second (RPS) | Varies by service |
| **Error rate** | Percentage of failed requests | < 0.1% under load |
| **Concurrent users** | Simultaneous active connections | Service-dependent |

## Open vs closed model — and why the gate uses open

A load model decides **when the next request starts**:

| Model | Next request starts… | k6 executors | Use for |
|---|---|---|---|
| **Closed** | when a virtual user's previous request finishes (+ think time) | `constant-vus`, `ramping-vus`, `per-vu-iterations`, `shared-iterations` | "how many concurrent sessions can we hold" |
| **Open** | on a schedule, at a fixed arrival rate, whether earlier requests finished or not | `constant-arrival-rate`, `ramping-arrival-rate` | **NFR targets stated as a rate** ("p95 < 300 ms at 50 req/s"): the pipeline's gated load test |

**Coordinated omission.** In a closed model, a slow server slows the load generator down with it.
Each virtual user waits for its stuck request, so fewer requests are sent exactly while latency is
bad. The slow period is under-sampled, and p95/p99 look better than what users feel. An open model
keeps sending at the target rate, so the queueing shows up in the percentiles (see k6 docs, "Open and
closed models").

When the system can't keep up, k6 reports **`dropped_iterations`**: it had no free VU to start an
iteration on schedule. A run with dropped iterations did not apply the target rate. Treat that as a
failed run (threshold `dropped_iterations: ["count==0"]`) and raise `maxVUs`, not the rate.

## The gated NFR load test (performance_agent)

One scenario per NFR-PERF target, at the NFR's own rate, against the **deployed qa build**, with the
NFR's limits as thresholds. Each scenario has a warm-up first: a short low-rate phase whose samples
are excluded by tag.

```javascript
// tests/perf/nfr-perf.js — committed; run by commands."x:perf" (or `k6 run tests/perf/nfr-perf.js`)
import http from "k6/http";
import { check } from "k6";

const BASE = __ENV.APP_BASE_URL;                     // the deployed build (qa); required
if (!BASE) throw new Error("APP_BASE_URL not set");
const TOKEN = __ENV.PERF_TOKEN;                      // from the environment, never committed

/** @type {import("k6/options").Options} */
export const options = {
  scenarios: {
    // TC-PERF-20101 / NFR-PERF-003: GET /orders at 50 req/s — p95 < 300 ms, p99 < 800 ms, errors < 0.1 %
    warmup_orders: { executor: "constant-arrival-rate", rate: 10, timeUnit: "1s", duration: "30s",
                     preAllocatedVUs: 20, maxVUs: 100, exec: "listOrders", tags: { phase: "warmup" } },
    TC_PERF_20101: { executor: "constant-arrival-rate", rate: 50, timeUnit: "1s", duration: "5m",
                     startTime: "30s", preAllocatedVUs: 50, maxVUs: 400, exec: "listOrders",
                     tags: { tc: "TC-PERF-20101", phase: "measure" } },
  },
  thresholds: {
    "http_req_duration{tc:TC-PERF-20101,phase:measure}": ["p(95)<300", "p(99)<800"],
    "http_req_failed{tc:TC-PERF-20101,phase:measure}": ["rate<0.001"],
    "dropped_iterations{scenario:TC_PERF_20101}": ["count==0"],
  },
  summaryTrendStats: ["avg", "med", "p(90)", "p(95)", "p(99)", "max"],
};

export function listOrders() {
  const r = http.get(`${BASE}/api/v1/orders?limit=20`, { headers: { Authorization: `Bearer ${TOKEN}` } });
  check(r, { "200": (res) => res.status === 200 });
}

/** @param {Record<string, unknown>} data */
export function handleSummary(data) {             // the machine-readable result performance_agent converts
  return { [__ENV.K6_SUMMARY || "k6-summary.json"]: JSON.stringify(data) };
}
```

- **Duration:** at least 5 minutes at the target rate. 100 samples can't give a stable p99. At 50
  req/s, 5 minutes gives 15,000.
- **Thresholds are the NFR, verbatim.** Never loosen a threshold to pass. A miss is a finding for the
  owning developer, or a DECISIONS.md entry that changes the NFR.
- **k6 exits 99 when a threshold fails.** Keep the exit code (`rc=$?`, no pipe into `tee`).
- **Read results from `handleSummary`.** In its data, `metrics["<metric>{<tags>}"].thresholds["<expr>"].ok`
  is `true` when the threshold held. The older `--summary-export` file uses the opposite convention
  (`true` = failed), and k6 marks it for future deprecation.
- **Record the conditions** with the numbers: environment and URL, deployed code sha, replicas, CPU
  and memory limits, the dataset size, and the k6 version.
- Test on qa, never production. qa's resources are small (lab pods request 50m CPU), so a qa pass
  proves the code has no gross inefficiency at the stated rate. It doesn't prove production capacity.

## k6 (JavaScript — Recommended for REST APIs)

### Basic Load Test (closed model — capacity exploration, not the NFR gate)
```javascript
import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

// Custom metrics
const errorRate = new Rate("errors");
const widgetLatency = new Trend("widget_latency", true);

/** @type {import("k6/options").Options} */
export const options = {
  stages: [
    { duration: "1m", target: 50 },   // ramp up to 50 VUs
    { duration: "5m", target: 50 },   // hold at 50 VUs
    { duration: "1m", target: 100 },  // ramp up to 100 VUs
    { duration: "5m", target: 100 },  // hold at 100 VUs
    { duration: "2m", target: 0 },    // ramp down
  ],
  thresholds: {
    http_req_duration: ["p(95)<500", "p(99)<1000"],  // fail if p95 > 500ms
    errors: ["rate<0.01"],                             // fail if error rate > 1%
    widget_latency: ["p(95)<300"],                     // custom metric threshold
  },
};

const BASE_URL = __ENV.APP_BASE_URL;   // the deployed build; no localhost default
const AUTH_TOKEN = __ENV.AUTH_TOKEN;   // from the environment; never a committed default

export default function () {
  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${AUTH_TOKEN}`,
  };

  // Create a widget
  const createRes = http.post(
    `${BASE_URL}/api/v1/widgets`,
    JSON.stringify({ name: `widget-${Date.now()}`, description: "load test" }),
    { headers, tags: { name: "create_widget" } },
  );
  check(createRes, {
    "create: status 201": (r) => r.status === 201,
    "create: has id": (r) => r.json("data.id") !== undefined,
  });
  errorRate.add(createRes.status !== 201);

  if (createRes.status === 201) {
    const widgetId = createRes.json("data.id");

    // Get the widget
    const getRes = http.get(`${BASE_URL}/api/v1/widgets/${widgetId}`, {
      headers,
      tags: { name: "get_widget" },
    });
    check(getRes, { "get: status 200": (r) => r.status === 200 });
    widgetLatency.add(getRes.timings.duration);
    errorRate.add(getRes.status !== 200);
  }

  // List widgets
  const listRes = http.get(`${BASE_URL}/api/v1/widgets?limit=20`, { // cursor pagination: ?cursor=&limit=
    headers,
    tags: { name: "list_widgets" },
  });
  check(listRes, { "list: status 200": (r) => r.status === 200 });
  errorRate.add(listRes.status !== 200);

  sleep(1); // think time between iterations
}
```

### Stress Test
```javascript
/** @type {import("k6/options").Options} */
export const options = {
  stages: [
    { duration: "2m", target: 100 },
    { duration: "5m", target: 200 },
    { duration: "5m", target: 500 },
    { duration: "5m", target: 1000 },  // push beyond expected capacity
    { duration: "2m", target: 0 },
  ],
  thresholds: {
    http_req_duration: ["p(95)<2000"],  // relaxed for stress test
    errors: ["rate<0.10"],               // allow up to 10% errors under extreme load
  },
};
```

### Spike Test
```javascript
/** @type {import("k6/options").Options} */
export const options = {
  stages: [
    { duration: "1m", target: 50 },    // normal load
    { duration: "10s", target: 500 },   // sudden spike (10x)
    { duration: "3m", target: 500 },    // hold spike
    { duration: "10s", target: 50 },    // drop back to normal
    { duration: "3m", target: 50 },     // verify recovery
    { duration: "1m", target: 0 },
  ],
};
```

### Running k6
```bash
# Against the deployed build
k6 run --env APP_BASE_URL="$APP_BASE_URL" load-test.js

# Raw per-request samples (large) for later analysis
k6 run --out json=results.json load-test.js

# CI / pipeline: keep the exit code (99 = a threshold failed); results via handleSummary()
k6 run --quiet --env APP_BASE_URL="$APP_BASE_URL" --env K6_SUMMARY=k6-summary.json tests/perf/nfr-perf.js; rc=$?
```

## Locust (Python)

```python
import os
import time

from locust import HttpUser, task, between

class WidgetUser(HttpUser):
    wait_time = between(1, 3)  # think time between tasks (closed model)
    host = os.environ["APP_BASE_URL"]

    def on_start(self):
        """Called once per simulated user — setup auth and one widget to read."""
        self.headers = {
            "Authorization": f"Bearer {os.environ['AUTH_TOKEN']}",
            "Content-Type": "application/json",
        }
        response = self.client.post(
            "/api/v1/widgets", json={"name": f"widget-{time.time()}", "description": "load test"},
            headers=self.headers,
        )
        self.widget_id = response.json()["data"]["id"] if response.status_code == 201 else None

    @task(3)  # weight: 3x more likely than other tasks
    def list_widgets(self):
        self.client.get("/api/v1/widgets?limit=20", headers=self.headers)  # the envelope's page size

    @task(2)
    def get_widget(self):
        if self.widget_id:
            self.client.get(f"/api/v1/widgets/{self.widget_id}", headers=self.headers)

    @task(1)
    def create_widget(self):
        response = self.client.post(
            "/api/v1/widgets",
            json={"name": f"widget-{time.time()}", "description": "load test"},
            headers=self.headers,
        )
        if response.status_code == 201:
            self.widget_id = response.json()["data"]["id"]
```
```bash
# Run with 100 users, spawn rate 10/sec
locust -f locustfile.py --users=100 --spawn-rate=10 --run-time=10m --headless

# With web UI
locust -f locustfile.py  # opens http://localhost:8089
```

## Gatling (Scala/Java)

```scala
import io.gatling.core.Predef._
import io.gatling.http.Predef._
import scala.concurrent.duration._

class WidgetSimulation extends Simulation {
  val httpProtocol = http
    .baseUrl(sys.env("APP_BASE_URL"))
    .header("Authorization", s"Bearer ${sys.env("AUTH_TOKEN")}")
    .header("Content-Type", "application/json")

  val scn = scenario("Widget CRUD")
    .exec(
      http("Create Widget")
        .post("/api/v1/widgets")
        .body(StringBody("""{"name":"widget-${System.currentTimeMillis()}","description":"test"}"""))
        .check(status.is(201))
        .check(jsonPath("$.data.id").saveAs("widgetId"))
    )
    .pause(1)
    .exec(
      http("Get Widget")
        .get("/api/v1/widgets/${widgetId}")
        .check(status.is(200))
    )
    .pause(1)
    .exec(
      http("List Widgets")
        .get("/api/v1/widgets?page_size=20")
        .check(status.is(200))
    )

  setUp(
    scn.inject(
      rampUsersPerSec(1).to(50).during(2.minutes),
      constantUsersPerSec(50).during(5.minutes),
      rampUsersPerSec(50).to(0).during(1.minute),
    )
  ).protocols(httpProtocol)
    .assertions(
      global.responseTime.percentile3.lt(500),  // p95 < 500ms
      global.failedRequests.percent.lt(1),       // < 1% errors
    )
}
```

## Drill (Rust — Lightweight)

```yaml
# benchmark.yml — drill interpolates {{ VAR }} from the environment (base, url, headers):
#   APP_BASE_URL=http://app-qa.localhost:18080 AUTH_TOKEN="$(…mint a test-user token…)" drill --benchmark benchmark.yml --stats
---
concurrency: 50
base: "{{ APP_BASE_URL }}"
iterations: 1000
rampup: 10

plan:
  - name: List widgets
    request:
      url: /api/v1/widgets?limit=20        # cursor pagination: limit (+ cursor), never page/offset
      method: GET
      headers:
        Authorization: "Bearer {{ AUTH_TOKEN }}"   # from the environment, never committed

  - name: Create widget
    request:
      url: /api/v1/widgets
      method: POST
      headers:
        Authorization: "Bearer {{ AUTH_TOKEN }}"   # from the environment, never committed
        Content-Type: "application/json"
      body: '{"name":"drill-test","description":"bench"}'
```
```bash
drill --benchmark benchmark.yml --stats
```

## CI/CD Integration

### GitHub Actions Example
```yaml
load-test:
  runs-on: ubuntu-latest
  needs: [deploy-staging]
  steps:
    - uses: actions/checkout@v4

    - name: Install k6
      run: |
        sudo gpg -k
        sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg \
          --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D68
        echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" \
          | sudo tee /etc/apt/sources.list.d/k6.list
        sudo apt-get update && sudo apt-get install -y k6

    - name: Run load test
      env:                       # secrets reach the script as env vars, not pasted into its text
        APP_BASE_URL: ${{ secrets.STAGING_URL }}       # the name the k6 script reads (__ENV.APP_BASE_URL)
        AUTH_TOKEN: ${{ secrets.STAGING_AUTH_TOKEN }}
      run: |
        k6 run \
          --env APP_BASE_URL="$APP_BASE_URL" \
          --env AUTH_TOKEN="$AUTH_TOKEN" \
          --env K6_SUMMARY=summary.json \
          tests/load/api-load-test.js       # its handleSummary() writes summary.json, as in the NFR-PERF
                                            # script above (not --summary-export)

    - name: Check thresholds
      if: failure()
      run: |
        echo "Load test failed — p95 latency or error rate exceeded thresholds"
        if [ -f summary.json ]; then jq '.metrics' summary.json; fi
        exit 1
```

### Threshold-Based Pipeline Gating
```javascript
// k6 thresholds that fail the CI pipeline
/** @type {import("k6/options").Options} */
export const options = {
  thresholds: {
    // Abort run early if these are breached
    http_req_duration: [
      { threshold: "p(95)<500", abortOnFail: true, delayAbortEval: "30s" },
    ],
    http_req_failed: [
      { threshold: "rate<0.01", abortOnFail: true, delayAbortEval: "30s" },
    ],
  },
};
```
- `abortOnFail: true` stops the test early when thresholds are breached
- `delayAbortEval` gives the system time to warm up before evaluating

## Defining Scenarios (Virtual Users)
```text
Scenario: E-commerce checkout flow
  70% — Browse products (GET /products, GET /products/:id)
  20% — Add to cart (POST /cart/items)
   8% — Checkout (POST /orders)
   2% — Admin operations (GET /admin/stats)

Think time: 1-3 seconds between actions (simulates real user behavior)
Ramp-up: Start with 10 VUs, add 10 every 30 seconds until target
Duration: Hold steady state for at least 5 minutes before measuring
```

## Rules
- Gate NFR-PERF targets with an **open model** (`constant-arrival-rate`) at the NFR's rate; a closed-model result under-reports tail latency (coordinated omission)
- A run with `dropped_iterations > 0` didn't apply the target load — it's a failed run, not a pass
- Warm up before measuring (a low-rate phase excluded from the thresholds by tag) — cold caches and pools are not the steady state
- Think time (sleep/pause) belongs in closed-model capacity and soak tests; an arrival-rate scenario sets the rate directly
- Credentials and the base URL come from the environment (`APP_BASE_URL`, a token variable) — never a committed default
- Tag requests by name — enables per-endpoint metric analysis
- Set thresholds and fail CI on breach — p95 latency and error rate are the minimum
- Test against staging, not production — unless you have traffic replay capability
- Run soak tests for memory leak detection — 1+ hours at steady load
- Use realistic data — don't test with the same widget ID every time
- Monitor server-side metrics during tests — CPU, memory, DB connections, queue depth
- Baseline first, then optimize — measure current performance before making changes
- k6 for CI/CD integration (scriptable, threshold-based exit codes)
- Locust for exploratory testing (web UI, Python flexibility)
- Gatling for Java/Scala shops (JVM-native, rich HTML reports)

> Config blocks checked 2026-09-30 (`bash tests/archetype-compile/config-packs/run.sh --live`): 3 bash blocks: bash -n (macOS bash 3.2.57) + shellcheck 0.11.0; 2 YAML blocks parsed (duplicate keys fail), actionlint 1.7.12, drill benchmark structure.
