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

## k6 (JavaScript — Recommended for REST APIs)

### Basic Load Test
```javascript
import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

// Custom metrics
const errorRate = new Rate("errors");
const widgetLatency = new Trend("widget_latency", true);

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

const BASE_URL = __ENV.BASE_URL || "http://localhost:8080";
const AUTH_TOKEN = __ENV.AUTH_TOKEN || "test-token";

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
    "create: has id": (r) => JSON.parse(r.body).data.id !== undefined,
  });
  errorRate.add(createRes.status !== 201);

  if (createRes.status === 201) {
    const widgetId = JSON.parse(createRes.body).data.id;

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
  const listRes = http.get(`${BASE_URL}/api/v1/widgets?page_size=20`, {
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
# Local execution
k6 run --env BASE_URL=http://localhost:8080 load-test.js

# With HTML report
k6 run --out json=results.json load-test.js
# Convert to HTML: k6-reporter results.json

# CI execution with exit code
k6 run --quiet --summary-export=summary.json load-test.js
# Exit code 99 if thresholds fail — use in CI to fail the pipeline
```

## Locust (Python)

```python
from locust import HttpUser, task, between

class WidgetUser(HttpUser):
    wait_time = between(1, 3)  # think time between tasks
    host = "http://localhost:8080"

    def on_start(self):
        """Called once per simulated user — setup auth."""
        self.headers = {
            "Authorization": f"Bearer {self.environment.parsed_options.auth_token}",
            "Content-Type": "application/json",
        }

    @task(3)  # weight: 3x more likely than other tasks
    def list_widgets(self):
        self.client.get("/api/v1/widgets?page_size=20", headers=self.headers)

    @task(2)
    def get_widget(self):
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
    .baseUrl("http://localhost:8080")
    .header("Authorization", "Bearer test-token")
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
# benchmark.yml
---
concurrency: 50
base: "http://localhost:8080"
iterations: 1000
rampup: 10

plan:
  - name: List widgets
    request:
      url: /api/v1/widgets?page_size=20
      method: GET
      headers:
        Authorization: "Bearer test-token"

  - name: Create widget
    request:
      url: /api/v1/widgets
      method: POST
      headers:
        Authorization: "Bearer test-token"
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
        sudo apt-get update && sudo apt-get install k6

    - name: Run load test
      run: |
        k6 run \
          --env BASE_URL=${{ secrets.STAGING_URL }} \
          --env AUTH_TOKEN=${{ secrets.STAGING_AUTH_TOKEN }} \
          --summary-export=summary.json \
          tests/load/api-load-test.js

    - name: Check thresholds
      if: failure()
      run: |
        echo "Load test failed — p95 latency or error rate exceeded thresholds"
        cat summary.json | jq '.metrics'
        exit 1
```

### Threshold-Based Pipeline Gating
```javascript
// k6 thresholds that fail the CI pipeline
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
```
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
- Always ramp up gradually — never start at full load (cold caches, connection pools)
- Include think time (sleep/pause) — real users don't fire requests continuously
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
