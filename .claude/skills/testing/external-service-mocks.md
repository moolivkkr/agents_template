---
skill: external-service-mocks
description: Mock patterns for common SaaS services in tests — Stripe, Auth0/Clerk, SendGrid/Postmark, AWS S3, Twilio, OpenAI/Claude API with examples for MSW (TS), WireMock (Java), httptest (Go), pytest-httpx (Python), wiremock (Rust)
version: "1.0"
tags:
  - testing
  - mocking
  - stripe
  - auth0
  - sendgrid
  - s3
  - twilio
  - openai
  - msw
  - wiremock
  - httptest
---

# External Service Mock Patterns

Production-grade mock patterns for common SaaS integrations in tests. Each service includes realistic response shapes and examples in all 5 language ecosystems.

## General Principles

```
1. Mock at the HTTP boundary — not at the SDK level
   (ensures your SDK configuration is also tested)

2. Use realistic response shapes — copy from official API docs
   (catches deserialization bugs)

3. Verify request bodies — not just that a call was made
   (catches incorrect API usage)

4. Test error paths — timeouts, 4xx, 5xx responses
   (ensures graceful degradation)

5. Test webhook verification — signature validation is critical
   (prevents accepting forged webhooks)
```

---

## Stripe

### Mock Response Shapes

```json
// POST /v1/payment_intents
{
    "id": "pi_3MtwBwLkdIwHu7ix28a3tqPa",
    "object": "payment_intent",
    "amount": 2000,
    "currency": "usd",
    "status": "requires_payment_method",
    "client_secret": "pi_3MtwBwLkdIwHu7ix28a3tqPa_secret_YrKJUKribcBjcG8HVhfZluoGH",
    "created": 1680800504,
    "livemode": false,
    "metadata": {},
    "payment_method_types": ["card"]
}

// POST /v1/customers
{
    "id": "cus_NffrFeUfNV2Hib",
    "object": "customer",
    "email": "test@example.com",
    "name": "Test User",
    "created": 1680893993,
    "livemode": false
}

// Webhook event
{
    "id": "evt_1MqqbyLkdIwHu7ixNSJTatGx",
    "object": "event",
    "type": "payment_intent.succeeded",
    "data": {
        "object": {
            "id": "pi_3MtwBwLkdIwHu7ix28a3tqPa",
            "object": "payment_intent",
            "amount": 2000,
            "currency": "usd",
            "status": "succeeded"
        }
    },
    "created": 1680064028
}
```

### TypeScript (MSW)

```typescript
import { http, HttpResponse } from 'msw';

export const stripeHandlers = [
  // Create payment intent
  http.post('https://api.stripe.com/v1/payment_intents', async ({ request }) => {
    const body = await request.text();
    const params = new URLSearchParams(body);

    return HttpResponse.json({
      id: 'pi_test_' + Date.now(),
      object: 'payment_intent',
      amount: parseInt(params.get('amount') ?? '0'),
      currency: params.get('currency') ?? 'usd',
      status: 'requires_payment_method',
      client_secret: 'pi_test_secret_' + Date.now(),
      created: Math.floor(Date.now() / 1000),
      livemode: false,
      metadata: {},
      payment_method_types: ['card'],
    });
  }),

  // Create customer
  http.post('https://api.stripe.com/v1/customers', async ({ request }) => {
    const body = await request.text();
    const params = new URLSearchParams(body);

    return HttpResponse.json({
      id: 'cus_test_' + Date.now(),
      object: 'customer',
      email: params.get('email') ?? 'test@example.com',
      name: params.get('name') ?? 'Test User',
      created: Math.floor(Date.now() / 1000),
      livemode: false,
    });
  }),

  // Simulate Stripe error (card declined)
  http.post('https://api.stripe.com/v1/payment_intents/:id/confirm', () => {
    return HttpResponse.json(
      {
        error: {
          type: 'card_error',
          code: 'card_declined',
          message: 'Your card was declined.',
          param: 'payment_method',
        },
      },
      { status: 402 },
    );
  }),
];
```

### Go (httptest)

```go
func newStripeServer(t *testing.T) *httptest.Server {
    mux := http.NewServeMux()

    mux.HandleFunc("/v1/payment_intents", func(w http.ResponseWriter, r *http.Request) {
        if r.Method != http.MethodPost {
            http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
            return
        }

        r.ParseForm()
        amount := r.FormValue("amount")

        w.Header().Set("Content-Type", "application/json")
        json.NewEncoder(w).Encode(map[string]any{
            "id":             "pi_test_" + uuid.New().String()[:8],
            "object":         "payment_intent",
            "amount":         amount,
            "currency":       r.FormValue("currency"),
            "status":         "requires_payment_method",
            "client_secret":  "pi_test_secret_" + uuid.New().String()[:8],
            "created":        time.Now().Unix(),
            "livemode":       false,
        })
    })

    mux.HandleFunc("/v1/customers", func(w http.ResponseWriter, r *http.Request) {
        r.ParseForm()
        w.Header().Set("Content-Type", "application/json")
        json.NewEncoder(w).Encode(map[string]any{
            "id":      "cus_test_" + uuid.New().String()[:8],
            "object":  "customer",
            "email":   r.FormValue("email"),
            "name":    r.FormValue("name"),
            "created": time.Now().Unix(),
        })
    })

    srv := httptest.NewServer(mux)
    t.Cleanup(srv.Close)
    return srv
}

// Usage: override Stripe base URL in test
func TestCreatePayment(t *testing.T) {
    srv := newStripeServer(t)
    stripeClient := stripe.New("sk_test_fake", stripe.WithBaseURL(srv.URL))
    // ... test with stripeClient
}
```

### Python (pytest-httpx)

```python
import pytest
from pytest_httpx import HTTPXMock

@pytest.fixture
def mock_stripe(httpx_mock: HTTPXMock):
    """Mock Stripe API endpoints."""

    httpx_mock.add_response(
        method="POST",
        url="https://api.stripe.com/v1/payment_intents",
        json={
            "id": "pi_test_123",
            "object": "payment_intent",
            "amount": 2000,
            "currency": "usd",
            "status": "requires_payment_method",
            "client_secret": "pi_test_secret_123",
        },
    )

    httpx_mock.add_response(
        method="POST",
        url="https://api.stripe.com/v1/customers",
        json={
            "id": "cus_test_123",
            "object": "customer",
            "email": "test@example.com",
        },
    )

    return httpx_mock

async def test_create_payment(mock_stripe, payment_service):
    result = await payment_service.create_intent(amount=2000, currency="usd")
    assert result.id == "pi_test_123"
    assert result.status == "requires_payment_method"
```

### Java (WireMock)

```java
import static com.github.tomakehurst.wiremock.client.WireMock.*;

@WireMockTest
class StripeIntegrationTest {

    @Test
    void createPaymentIntent(WireMockRuntimeInfo wmInfo) {
        stubFor(post("/v1/payment_intents")
            .willReturn(okJson("""
                {
                    "id": "pi_test_123",
                    "object": "payment_intent",
                    "amount": 2000,
                    "currency": "usd",
                    "status": "requires_payment_method",
                    "client_secret": "pi_test_secret_123"
                }
            """)));

        var client = new StripeClient(wmInfo.getHttpBaseUrl(), "sk_test_fake");
        var intent = client.createPaymentIntent(2000, "usd");

        assertThat(intent.getId()).isEqualTo("pi_test_123");

        verify(postRequestedFor(urlEqualTo("/v1/payment_intents"))
            .withRequestBody(containing("amount=2000")));
    }
}
```

### Rust (wiremock)

```rust
use wiremock::{MockServer, Mock, ResponseTemplate};
use wiremock::matchers::{method, path};

#[tokio::test]
async fn test_create_payment_intent() {
    let mock_server = MockServer::start().await;

    Mock::given(method("POST"))
        .and(path("/v1/payment_intents"))
        .respond_with(ResponseTemplate::new(200).set_body_json(serde_json::json!({
            "id": "pi_test_123",
            "object": "payment_intent",
            "amount": 2000,
            "currency": "usd",
            "status": "requires_payment_method",
            "client_secret": "pi_test_secret_123"
        })))
        .mount(&mock_server)
        .await;

    let client = StripeClient::new(&mock_server.uri(), "sk_test_fake");
    let intent = client.create_payment_intent(2000, "usd").await.unwrap();

    assert_eq!(intent.id, "pi_test_123");
}
```

---

## Auth0 / Clerk

### Mock Response Shapes

```json
// GET /.well-known/jwks.json (JWKS endpoint)
{
    "keys": [{
        "kty": "RSA",
        "kid": "test-key-id",
        "use": "sig",
        "alg": "RS256",
        "n": "0vx7agoebGc...",
        "e": "AQAB"
    }]
}

// GET /userinfo
{
    "sub": "auth0|user123",
    "email": "test@example.com",
    "email_verified": true,
    "name": "Test User",
    "picture": "https://example.com/avatar.jpg"
}
```

### Token Generation for Tests

```typescript
// TypeScript — generate test JWTs with jose
import { SignJWT, importPKCS8, exportJWK, generateKeyPair } from 'jose';

export async function createTestJwt(claims: Record<string, unknown> = {}) {
  const { privateKey, publicKey } = await generateKeyPair('RS256');

  const token = await new SignJWT({
    sub: 'user-123',
    tenant_id: 'tenant-456',
    email: 'test@example.com',
    roles: ['admin'],
    ...claims,
  })
    .setProtectedHeader({ alg: 'RS256', kid: 'test-key-id' })
    .setIssuedAt()
    .setExpirationTime('1h')
    .setIssuer('https://test.auth0.com/')
    .setAudience('https://api.example.com')
    .sign(privateKey);

  const jwk = await exportJWK(publicKey);
  jwk.kid = 'test-key-id';
  jwk.use = 'sig';
  jwk.alg = 'RS256';

  return { token, jwks: { keys: [jwk] } };
}
```

```go
// Go — generate test JWTs for httptest
import (
    "crypto/rsa"
    "crypto/rand"
    "github.com/golang-jwt/jwt/v5"
)

func generateTestJWT(t *testing.T) (string, *rsa.PublicKey) {
    privKey, _ := rsa.GenerateKey(rand.Reader, 2048)

    claims := jwt.MapClaims{
        "sub":       "user-123",
        "tenant_id": "tenant-456",
        "email":     "test@example.com",
        "roles":     []string{"admin"},
        "iss":       "https://test.auth0.com/",
        "aud":       "https://api.example.com",
        "exp":       time.Now().Add(time.Hour).Unix(),
        "iat":       time.Now().Unix(),
    }

    token := jwt.NewWithClaims(jwt.SigningMethodRS256, claims)
    token.Header["kid"] = "test-key-id"

    signed, _ := token.SignedString(privKey)
    return signed, &privKey.PublicKey
}
```

### JWKS Mock Server

```typescript
// MSW handler for JWKS endpoint
const jwksHandler = http.get('https://test.auth0.com/.well-known/jwks.json', () => {
  return HttpResponse.json(testJwks); // from createTestJwt()
});

const userinfoHandler = http.get('https://test.auth0.com/userinfo', ({ request }) => {
  const auth = request.headers.get('Authorization');
  if (!auth?.startsWith('Bearer ')) {
    return HttpResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  return HttpResponse.json({
    sub: 'auth0|user123',
    email: 'test@example.com',
    email_verified: true,
    name: 'Test User',
  });
});
```

---

## SendGrid / Postmark

### Mock Response Shapes

```json
// POST /v3/mail/send (SendGrid)
// Returns 202 Accepted with empty body on success

// POST /email (Postmark)
{
    "To": "test@example.com",
    "SubmittedAt": "2024-01-15T09:30:00Z",
    "MessageID": "b7bc2f4a-e38e-4336-af7d-e6c392c2f817",
    "ErrorCode": 0,
    "Message": "OK"
}
```

### TypeScript (MSW)

```typescript
export const emailHandlers = [
  // SendGrid
  http.post('https://api.sendgrid.com/v3/mail/send', async ({ request }) => {
    const body = await request.json();

    // Verify expected fields
    if (!body.personalizations?.[0]?.to?.[0]?.email) {
      return HttpResponse.json({ errors: [{ message: 'to is required' }] }, { status: 400 });
    }

    return new HttpResponse(null, { status: 202 });
  }),

  // Postmark
  http.post('https://api.postmarkapp.com/email', async ({ request }) => {
    const body = await request.json();

    return HttpResponse.json({
      To: body.To,
      SubmittedAt: new Date().toISOString(),
      MessageID: crypto.randomUUID(),
      ErrorCode: 0,
      Message: 'OK',
    });
  }),
];
```

### Go (httptest)

```go
func newSendGridServer(t *testing.T) *httptest.Server {
    mux := http.NewServeMux()
    mux.HandleFunc("/v3/mail/send", func(w http.ResponseWriter, r *http.Request) {
        // Verify API key
        auth := r.Header.Get("Authorization")
        if !strings.HasPrefix(auth, "Bearer ") {
            http.Error(w, "unauthorized", http.StatusUnauthorized)
            return
        }

        var body map[string]any
        json.NewDecoder(r.Body).Decode(&body)

        // Verify structure
        personalizations, _ := body["personalizations"].([]any)
        if len(personalizations) == 0 {
            http.Error(w, "missing personalizations", http.StatusBadRequest)
            return
        }

        w.WriteHeader(http.StatusAccepted)
    })

    srv := httptest.NewServer(mux)
    t.Cleanup(srv.Close)
    return srv
}
```

---

## AWS S3

### Mock Response Shapes

```
// PUT /{bucket}/{key} (upload)
// Returns 200 with ETag header

// GET /{bucket}/{key} (download)
// Returns 200 with file content and Content-Type header

// Presigned URL (generated client-side, no mock needed for URL generation)
// But the presigned URL itself points to S3 — mock the actual upload/download
```

### TypeScript (MSW)

```typescript
const s3Handlers = [
  // Upload
  http.put('https://test-bucket.s3.amazonaws.com/*', async ({ request }) => {
    const key = new URL(request.url).pathname;
    return new HttpResponse(null, {
      status: 200,
      headers: {
        ETag: '"d41d8cd98f00b204e9800998ecf8427e"',
        'x-amz-request-id': 'test-request-id',
      },
    });
  }),

  // Download
  http.get('https://test-bucket.s3.amazonaws.com/*', ({ request }) => {
    const key = new URL(request.url).pathname;
    return new HttpResponse('file content here', {
      status: 200,
      headers: { 'Content-Type': 'application/octet-stream' },
    });
  }),

  // List objects
  http.get('https://test-bucket.s3.amazonaws.com/', ({ request }) => {
    const url = new URL(request.url);
    const prefix = url.searchParams.get('prefix') ?? '';

    return HttpResponse.xml(`
      <ListBucketResult>
        <Name>test-bucket</Name>
        <Prefix>${prefix}</Prefix>
        <Contents>
          <Key>${prefix}file1.txt</Key>
          <Size>1024</Size>
          <LastModified>2024-01-15T09:30:00Z</LastModified>
        </Contents>
      </ListBucketResult>
    `);
  }),
];
```

### Go (httptest)

```go
func newS3Server(t *testing.T) *httptest.Server {
    storage := make(map[string][]byte)

    mux := http.NewServeMux()

    // Upload
    mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
        switch r.Method {
        case http.MethodPut:
            body, _ := io.ReadAll(r.Body)
            storage[r.URL.Path] = body
            w.Header().Set("ETag", `"test-etag"`)
            w.WriteHeader(http.StatusOK)

        case http.MethodGet:
            data, ok := storage[r.URL.Path]
            if !ok {
                http.Error(w, "NoSuchKey", http.StatusNotFound)
                return
            }
            w.Header().Set("Content-Type", "application/octet-stream")
            w.Write(data)

        case http.MethodDelete:
            delete(storage, r.URL.Path)
            w.WriteHeader(http.StatusNoContent)
        }
    })

    srv := httptest.NewServer(mux)
    t.Cleanup(srv.Close)
    return srv
}
```

### Python (pytest-httpx)

```python
@pytest.fixture
def mock_s3(httpx_mock: HTTPXMock):
    """Mock S3 upload and download."""
    httpx_mock.add_response(
        method="PUT",
        url=re.compile(r"https://test-bucket\.s3\.amazonaws\.com/.*"),
        status_code=200,
        headers={"ETag": '"test-etag"'},
    )

    httpx_mock.add_response(
        method="GET",
        url=re.compile(r"https://test-bucket\.s3\.amazonaws\.com/.*"),
        content=b"file content here",
        headers={"Content-Type": "application/octet-stream"},
    )

    return httpx_mock
```

---

## Twilio

### Mock Response Shapes

```json
// POST /2010-04-01/Accounts/{sid}/Messages.json
{
    "sid": "SM1234567890abcdef1234567890abcdef",
    "account_sid": "ACtest123",
    "to": "+15551234567",
    "from": "+15559876543",
    "body": "Your verification code is 123456",
    "status": "queued",
    "date_created": "Mon, 15 Jan 2024 09:30:00 +0000",
    "direction": "outbound-api",
    "price": null,
    "error_code": null
}
```

### TypeScript (MSW)

```typescript
const twilioHandlers = [
  http.post(
    'https://api.twilio.com/2010-04-01/Accounts/:sid/Messages.json',
    async ({ request, params }) => {
      const body = await request.text();
      const formData = new URLSearchParams(body);

      return HttpResponse.json({
        sid: 'SM' + crypto.randomUUID().replace(/-/g, '').slice(0, 32),
        account_sid: params.sid,
        to: formData.get('To'),
        from: formData.get('From'),
        body: formData.get('Body'),
        status: 'queued',
        date_created: new Date().toUTCString(),
        direction: 'outbound-api',
      });
    },
  ),
];
```

### Webhook Signature Verification Test

```typescript
import crypto from 'crypto';

function generateTwilioSignature(url: string, params: Record<string, string>, authToken: string): string {
  const data = url + Object.keys(params).sort().reduce((acc, key) => acc + key + params[key], '');
  return crypto.createHmac('sha1', authToken).update(data).digest('base64');
}

test('verifies Twilio webhook signature', () => {
  const authToken = 'test-auth-token';
  const url = 'https://example.com/webhooks/twilio';
  const params = { MessageSid: 'SM123', From: '+1555123', Body: 'Hello' };

  const signature = generateTwilioSignature(url, params, authToken);
  const isValid = twilioWebhookHandler.verifySignature(url, params, signature, authToken);

  expect(isValid).toBe(true);
});
```

---

## OpenAI / Claude API

### Mock Response Shapes

```json
// POST /v1/chat/completions (OpenAI)
{
    "id": "chatcmpl-abc123",
    "object": "chat.completion",
    "created": 1705301400,
    "model": "gpt-4",
    "choices": [{
        "index": 0,
        "message": {
            "role": "assistant",
            "content": "The answer to your question is 42."
        },
        "finish_reason": "stop"
    }],
    "usage": {
        "prompt_tokens": 56,
        "completion_tokens": 31,
        "total_tokens": 87
    }
}

// POST /v1/messages (Claude/Anthropic)
{
    "id": "msg_01XFDUDYJgAACzvnptvVoYEL",
    "type": "message",
    "role": "assistant",
    "content": [{
        "type": "text",
        "text": "The answer to your question is 42."
    }],
    "model": "claude-sonnet-4-20250514",
    "stop_reason": "end_turn",
    "usage": {
        "input_tokens": 56,
        "output_tokens": 31
    }
}
```

### TypeScript (MSW)

```typescript
const aiHandlers = [
  // OpenAI
  http.post('https://api.openai.com/v1/chat/completions', async ({ request }) => {
    const body = await request.json();

    // Simulate streaming if requested
    if (body.stream) {
      const encoder = new TextEncoder();
      const stream = new ReadableStream({
        start(controller) {
          const chunks = [
            'data: {"id":"chatcmpl-123","choices":[{"delta":{"content":"The "},"index":0}]}\n\n',
            'data: {"id":"chatcmpl-123","choices":[{"delta":{"content":"answer"},"index":0}]}\n\n',
            'data: {"id":"chatcmpl-123","choices":[{"delta":{"content":" is 42."},"index":0}]}\n\n',
            'data: {"id":"chatcmpl-123","choices":[{"delta":{},"finish_reason":"stop","index":0}]}\n\n',
            'data: [DONE]\n\n',
          ];
          chunks.forEach((chunk, i) => {
            setTimeout(() => {
              controller.enqueue(encoder.encode(chunk));
              if (i === chunks.length - 1) controller.close();
            }, i * 10);
          });
        },
      });

      return new HttpResponse(stream, {
        headers: { 'Content-Type': 'text/event-stream' },
      });
    }

    return HttpResponse.json({
      id: 'chatcmpl-test-' + Date.now(),
      object: 'chat.completion',
      created: Math.floor(Date.now() / 1000),
      model: body.model ?? 'gpt-4',
      choices: [{
        index: 0,
        message: { role: 'assistant', content: 'Mock response for testing.' },
        finish_reason: 'stop',
      }],
      usage: { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 },
    });
  }),

  // Claude/Anthropic
  http.post('https://api.anthropic.com/v1/messages', async ({ request }) => {
    const body = await request.json();

    return HttpResponse.json({
      id: 'msg_test_' + Date.now(),
      type: 'message',
      role: 'assistant',
      content: [{ type: 'text', text: 'Mock response for testing.' }],
      model: body.model ?? 'claude-sonnet-4-20250514',
      stop_reason: 'end_turn',
      usage: { input_tokens: 10, output_tokens: 5 },
    });
  }),
];
```

### Go (httptest)

```go
func newOpenAIServer(t *testing.T) *httptest.Server {
    mux := http.NewServeMux()

    mux.HandleFunc("/v1/chat/completions", func(w http.ResponseWriter, r *http.Request) {
        var req map[string]any
        json.NewDecoder(r.Body).Decode(&req)

        w.Header().Set("Content-Type", "application/json")
        json.NewEncoder(w).Encode(map[string]any{
            "id":      "chatcmpl-test",
            "object":  "chat.completion",
            "created": time.Now().Unix(),
            "model":   req["model"],
            "choices": []map[string]any{{
                "index": 0,
                "message": map[string]any{
                    "role":    "assistant",
                    "content": "Mock response for testing.",
                },
                "finish_reason": "stop",
            }},
            "usage": map[string]any{
                "prompt_tokens":     10,
                "completion_tokens": 5,
                "total_tokens":      15,
            },
        })
    })

    srv := httptest.NewServer(mux)
    t.Cleanup(srv.Close)
    return srv
}
```

### Python (pytest-httpx)

```python
@pytest.fixture
def mock_openai(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="POST",
        url="https://api.openai.com/v1/chat/completions",
        json={
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 1705301400,
            "model": "gpt-4",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": "Mock response."},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        },
    )
    return httpx_mock

@pytest.fixture
def mock_anthropic(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="POST",
        url="https://api.anthropic.com/v1/messages",
        json={
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Mock response."}],
            "model": "claude-sonnet-4-20250514",
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        },
    )
    return httpx_mock
```

---

## Webhook Verification Patterns

### Stripe Webhook Verification Test

```typescript
import Stripe from 'stripe';
import crypto from 'crypto';

function generateStripeSignature(payload: string, secret: string): string {
  const timestamp = Math.floor(Date.now() / 1000);
  const signedPayload = `${timestamp}.${payload}`;
  const signature = crypto
    .createHmac('sha256', secret)
    .update(signedPayload)
    .digest('hex');
  return `t=${timestamp},v1=${signature}`;
}

test('processes Stripe webhook with valid signature', async () => {
  const webhookSecret = 'whsec_test_secret';
  const payload = JSON.stringify({
    type: 'payment_intent.succeeded',
    data: { object: { id: 'pi_123', amount: 2000 } },
  });

  const signature = generateStripeSignature(payload, webhookSecret);

  const response = await request(app)
    .post('/webhooks/stripe')
    .set('stripe-signature', signature)
    .set('content-type', 'application/json')
    .send(payload);

  expect(response.status).toBe(200);
});

test('rejects Stripe webhook with invalid signature', async () => {
  const response = await request(app)
    .post('/webhooks/stripe')
    .set('stripe-signature', 't=123,v1=invalid')
    .set('content-type', 'application/json')
    .send('{}');

  expect(response.status).toBe(400);
});
```

### Go Webhook Verification

```go
func TestStripeWebhookVerification(t *testing.T) {
    secret := "whsec_test_secret"
    payload := `{"type":"payment_intent.succeeded","data":{"object":{"id":"pi_123"}}}`

    // Generate valid signature
    ts := time.Now().Unix()
    signedPayload := fmt.Sprintf("%d.%s", ts, payload)
    mac := hmac.New(sha256.New, []byte(secret))
    mac.Write([]byte(signedPayload))
    sig := fmt.Sprintf("t=%d,v1=%s", ts, hex.EncodeToString(mac.Sum(nil)))

    req := httptest.NewRequest(http.MethodPost, "/webhooks/stripe", strings.NewReader(payload))
    req.Header.Set("Stripe-Signature", sig)
    req.Header.Set("Content-Type", "application/json")

    w := httptest.NewRecorder()
    handler.ServeHTTP(w, req)

    assert.Equal(t, http.StatusOK, w.Code)
}
```

---

## Critical Rules

- Mock at the HTTP boundary, not the SDK — test your actual HTTP client configuration
- Use realistic response shapes copied from official API documentation
- Always test error responses (4xx, 5xx) — not just happy paths
- Always test webhook signature verification — both valid and invalid signatures
- Create mock servers per test (or per test suite) — avoid shared mutable state
- Verify request bodies in mocks — catch incorrect API usage early
- Use `httptest.Server` (Go), `MSW` (TS), `pytest-httpx` (Python), `WireMock` (Java), `wiremock` (Rust)
- For streaming responses (SSE/OpenAI), mock the chunked response format
- Clean up mock servers in test teardown — prevent port leaks
- Mock the authentication endpoint (JWKS) alongside the service endpoints
