# Contract testing patterns for microservice API evolution.

## What Is Contract Testing?
Contract testing verifies that two services (consumer and provider) agree on the API shape. Instead of running full integration tests, each side tests against a shared contract independently.

**Consumer-Driven Contracts (CDC):** The consumer defines what it expects from the provider. The provider verifies it can fulfill those expectations. This ensures providers never break existing consumers.

## When to Use It
- Microservices communicating via REST/gRPC
- API evolution where multiple consumers depend on one provider
- Team boundaries where provider and consumer are developed independently
- Replacing slow, flaky end-to-end integration tests
- Preventing breaking changes during API version upgrades

## When NOT to Use It
- Monolith with single deployment unit
- Public APIs with unknown consumers (use OpenAPI validation instead)
- Simple request/response with no schema evolution

## Pact Workflow

```
1. Consumer writes a test defining expected interactions
2. Pact generates a contract file (pact.json)
3. Contract is published to Pact Broker
4. Provider runs verification against the contract
5. Both sides deploy independently with confidence
```

## Consumer Side (Define Expectations)

### Go (pact-go v2)
```go
import (
    "testing"
    "github.com/pact-foundation/pact-go/v2/consumer"
    "github.com/pact-foundation/pact-go/v2/matchers"
)

func TestWidgetConsumer(t *testing.T) {
    mockProvider, err := consumer.NewV4Pact(consumer.MockHTTPProviderConfig{
        Consumer: "widget-dashboard",
        Provider: "widget-service",
    })
    require.NoError(t, err)

    // Define expected interaction
    err = mockProvider.
        AddInteraction().
        Given("a widget with ID abc-123 exists").
        UponReceiving("a request to get widget abc-123").
        WithRequest("GET", "/api/v1/widgets/abc-123", func(b *consumer.V4RequestBuilder) {
            b.Header("Authorization", matchers.Like("Bearer token"))
        }).
        WillRespondWith(200, func(b *consumer.V4ResponseBuilder) {
            b.Header("Content-Type", "application/json")
            b.JSONBody(matchers.Map{
                "data": matchers.Map{
                    "id":     matchers.Like("abc-123"),
                    "name":   matchers.Like("My Widget"),
                    "status": matchers.Like("active"),
                },
                "meta": matchers.Map{
                    "request_id": matchers.Like("req-123"),
                },
            })
        }).
        ExecuteTest(t, func(config consumer.MockServerConfig) error {
            // Test your client against the mock provider
            client := NewWidgetClient(config.URL)
            widget, err := client.GetWidget("abc-123")
            assert.NoError(t, err)
            assert.Equal(t, "My Widget", widget.Name)
            return nil
        })
    require.NoError(t, err)
}
```

### Python (pact-python)
```python
import atexit
from pact import Consumer, Provider

pact = Consumer("widget-dashboard").has_pact_with(
    Provider("widget-service"),
    pact_dir="./pacts",
)
pact.start_service()
atexit.register(pact.stop_service)

def test_get_widget():
    expected = {
        "data": {
            "id": "abc-123",
            "name": "My Widget",
            "status": "active",
        }
    }

    (pact
     .given("a widget with ID abc-123 exists")
     .upon_receiving("a request to get widget abc-123")
     .with_request("GET", "/api/v1/widgets/abc-123")
     .will_respond_with(200, body=Like(expected)))

    with pact:
        client = WidgetClient(base_url=pact.uri)
        widget = client.get_widget("abc-123")
        assert widget.name == "My Widget"
```

### TypeScript (pact-js)
```typescript
import { PactV4 } from "@pact-foundation/pact";
import { MatchersV3 } from "@pact-foundation/pact";

const { like } = MatchersV3;

const provider = new PactV4({
  consumer: "widget-dashboard",
  provider: "widget-service",
  dir: "./pacts",
});

describe("Widget API Consumer", () => {
  it("gets a widget by ID", async () => {
    await provider
      .addInteraction()
      .given("a widget with ID abc-123 exists")
      .uponReceiving("a request to get widget abc-123")
      .withRequest("GET", "/api/v1/widgets/abc-123", (builder) => {
        builder.headers({ Authorization: like("Bearer token") });
      })
      .willRespondWith(200, (builder) => {
        builder.headers({ "Content-Type": "application/json" });
        builder.jsonBody({
          data: {
            id: like("abc-123"),
            name: like("My Widget"),
            status: like("active"),
          },
        });
      })
      .executeTest(async (mockServer) => {
        const client = new WidgetClient(mockServer.url);
        const widget = await client.getWidget("abc-123");
        expect(widget.name).toBe("My Widget");
      });
  });
});
```

### Java (pact-jvm)
```java
@ExtendWith(PactConsumerTestExt.class)
@PactTestFor(providerName = "widget-service", port = "8080")
class WidgetConsumerTest {

    @Pact(consumer = "widget-dashboard")
    V4Pact getWidgetPact(PactDslWithProvider builder) {
        return builder
            .given("a widget with ID abc-123 exists")
            .uponReceiving("a request to get widget abc-123")
            .method("GET")
            .path("/api/v1/widgets/abc-123")
            .willRespondWith()
            .status(200)
            .headers(Map.of("Content-Type", "application/json"))
            .body(new PactDslJsonBody()
                .object("data")
                    .stringType("id", "abc-123")
                    .stringType("name", "My Widget")
                    .stringType("status", "active")
                .closeObject())
            .toPact(V4Pact.class);
    }

    @Test
    @PactTestFor(pactMethod = "getWidgetPact")
    void getWidget(MockServer mockServer) {
        var client = new WidgetClient(mockServer.getUrl());
        var widget = client.getWidget("abc-123");
        assertEquals("My Widget", widget.getName());
    }
}
```

## Provider Side (Verify Contracts)

### Go Provider Verification
```go
func TestWidgetProvider(t *testing.T) {
    verifier := provider.NewVerifier()

    // Start your real provider service
    server := startTestServer()
    defer server.Close()

    err := verifier.VerifyProvider(t, provider.VerifyRequest{
        ProviderBaseURL: server.URL,
        Provider:        "widget-service",
        // Pull contracts from Pact Broker
        BrokerURL:       "https://pact-broker.example.com",
        BrokerToken:     os.Getenv("PACT_BROKER_TOKEN"),
        PublishVerificationResults: true,
        ProviderVersion: os.Getenv("GIT_SHA"),
        // State handlers set up test data for provider states
        StateHandlers: map[string]models.StateHandler{
            "a widget with ID abc-123 exists": func(setup bool, state models.ProviderState) (models.ProviderStateResponse, error) {
                if setup {
                    seedWidget("abc-123", "My Widget", "active")
                }
                return models.ProviderStateResponse{}, nil
            },
        },
    })
    assert.NoError(t, err)
}
```

## Pact Broker
```bash
# Publish contract from consumer CI
pact-broker publish ./pacts \
  --consumer-app-version=$(git rev-parse HEAD) \
  --branch=$(git branch --show-current) \
  --broker-base-url=https://pact-broker.example.com \
  --broker-token=$PACT_BROKER_TOKEN

# Can I Deploy? — check before deployment
pact-broker can-i-deploy \
  --pacticipant=widget-dashboard \
  --version=$(git rev-parse HEAD) \
  --to-environment=production \
  --broker-base-url=https://pact-broker.example.com
```
- Pact Broker stores contracts and verification results
- `can-i-deploy` checks if a version is safe to deploy based on verified contracts
- Integrate `can-i-deploy` into CI/CD pipeline — block deployment on failure
- Use environments (dev, staging, production) for deployment tracking
- Self-hosted or use PactFlow (SaaS) for hosted broker

## CI/CD Integration
```yaml
# Consumer CI pipeline
consumer-tests:
  steps:
    - run: npm test          # generates pact files
    - run: pact-broker publish ./pacts --consumer-app-version=$GIT_SHA
    - run: pact-broker can-i-deploy --pacticipant=widget-dashboard --version=$GIT_SHA --to=production

# Provider CI pipeline
provider-verify:
  steps:
    - run: go test ./... -run TestWidgetProvider   # verifies against broker contracts
    # Results auto-published to broker via PublishVerificationResults: true
```

## Rules
- Consumer defines the contract — provider verifies it can fulfill expectations
- Use `Like()` / `matchers` for flexible matching — don't assert exact values unless required
- Provider states (`given`) set up test data — keep them simple and idempotent
- Publish contracts to Pact Broker from consumer CI — verify from provider CI
- `can-i-deploy` before every deployment — block if contracts are unverified
- One pact file per consumer-provider pair — not per endpoint
- Contract tests replace integration tests at service boundaries — not unit tests
- Keep contract scope narrow — test API shape, not business logic
- Provider version should be the git SHA — enables traceability
