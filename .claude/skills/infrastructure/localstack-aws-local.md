# LocalStack — Local AWS Service Simulation

## Purpose
LocalStack replicates core AWS services locally for development and testing. This eliminates the need for real AWS accounts during development and CI/CD while maintaining API compatibility.

---

## Docker Compose Setup

### Basic LocalStack Service
```yaml
services:
  localstack:
    image: localstack/localstack:4.4
    ports:
      - "4566:4566"      # Edge port (all services)
    environment:
      SERVICES: s3,sqs,kms,iam,route53,secretsmanager,dynamodb,lambda,sns,ses
      DEFAULT_REGION: us-east-1
      EDGE_PORT: 4566
      DEBUG: 0
    volumes:
      - "./localstack/init:/etc/localstack/init/ready.d"  # Auto-run scripts on startup
      - "localstack-data:/var/lib/localstack"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:4566/_localstack/health"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  localstack-data:
```

### Multi-Region Setup
```yaml
services:
  localstack-us-east-1:
    image: localstack/localstack:4.4
    ports:
      - "4566:4566"
    environment:
      SERVICES: s3,kms,route53,iam,secretsmanager
      DEFAULT_REGION: us-east-1
    volumes:
      - "./localstack/init/us-east-1:/etc/localstack/init/ready.d"

  localstack-us-west-1:
    image: localstack/localstack:4.4
    ports:
      - "4567:4566"
    environment:
      SERVICES: s3,kms,secretsmanager
      DEFAULT_REGION: us-west-1
    volumes:
      - "./localstack/init/us-west-1:/etc/localstack/init/ready.d"

  localstack-eu-west-1:
    image: localstack/localstack:4.4
    ports:
      - "4568:4566"
    environment:
      SERVICES: s3,kms,secretsmanager
      DEFAULT_REGION: eu-west-1
    volumes:
      - "./localstack/init/eu-west-1:/etc/localstack/init/ready.d"
```

---

## Environment Configuration

### Application Config (Local Development)
```bash
# .env.local
AWS_ENDPOINT_URL=http://localhost:4566
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_DEFAULT_REGION=us-east-1

# Per-service overrides (if needed)
S3_ENDPOINT=http://localhost:4566
KMS_ENDPOINT=http://localhost:4566
SQS_ENDPOINT=http://localhost:4566
ROUTE53_ENDPOINT=http://localhost:4566
SECRETS_MANAGER_ENDPOINT=http://localhost:4566
```

### SDK Configuration

**Go (aws-sdk-go-v2):**
```go
func NewLocalAWSConfig(ctx context.Context) (aws.Config, error) {
    endpoint := os.Getenv("AWS_ENDPOINT_URL")
    if endpoint == "" {
        // Production: use default AWS config
        return config.LoadDefaultConfig(ctx)
    }

    // LocalStack: custom endpoint resolver
    resolver := aws.EndpointResolverWithOptionsFunc(
        func(service, region string, options ...interface{}) (aws.Endpoint, error) {
            return aws.Endpoint{
                URL:               endpoint,
                HostnameImmutable: true,
                SigningRegion:     region,
            }, nil
        },
    )

    return config.LoadDefaultConfig(ctx,
        config.WithEndpointResolverWithOptions(resolver),
        config.WithCredentialsProvider(credentials.NewStaticCredentialsProvider("test", "test", "")),
        config.WithRegion(os.Getenv("AWS_DEFAULT_REGION")),
    )
}
```

**TypeScript (aws-sdk v3):**
```typescript
import { S3Client } from '@aws-sdk/client-s3';
import { KMSClient } from '@aws-sdk/client-kms';

function createAWSClient<T>(ClientClass: new (config: any) => T): T {
    const endpoint = process.env.AWS_ENDPOINT_URL;

    const config: any = {
        region: process.env.AWS_DEFAULT_REGION || 'us-east-1',
    };

    if (endpoint) {
        // LocalStack
        config.endpoint = endpoint;
        config.credentials = { accessKeyId: 'test', secretAccessKey: 'test' };
        config.forcePathStyle = true; // Required for S3 with LocalStack
    }

    return new ClientClass(config);
}

export const s3 = createAWSClient(S3Client);
export const kms = createAWSClient(KMSClient);
```

**Python (boto3):**
```python
import boto3
import os

def create_aws_client(service_name: str):
    endpoint = os.getenv('AWS_ENDPOINT_URL')

    kwargs = {
        'service_name': service_name,
        'region_name': os.getenv('AWS_DEFAULT_REGION', 'us-east-1'),
    }

    if endpoint:
        # LocalStack
        kwargs['endpoint_url'] = endpoint
        kwargs['aws_access_key_id'] = 'test'
        kwargs['aws_secret_access_key'] = 'test'

    return boto3.client(**kwargs)

s3 = create_aws_client('s3')
kms = create_aws_client('kms')
sqs = create_aws_client('sqs')
```

---

## Service-Specific Patterns

### S3 (Object Storage)
```bash
# Init script: localstack/init/ready.d/01-s3.sh
#!/bin/bash
awslocal s3 mb s3://app-uploads
awslocal s3 mb s3://app-backups
awslocal s3 mb s3://app-exports

# Set CORS for uploads bucket
awslocal s3api put-bucket-cors --bucket app-uploads --cors-configuration '{
  "CORSRules": [{
    "AllowedOrigins": ["http://localhost:3000"],
    "AllowedMethods": ["GET", "PUT", "POST"],
    "AllowedHeaders": ["*"],
    "MaxAgeSeconds": 3600
  }]
}'

# Enable versioning for backups
awslocal s3api put-bucket-versioning --bucket app-backups \
    --versioning-configuration Status=Enabled
```

### KMS (Key Management)
```bash
# Init script: localstack/init/ready.d/02-kms.sh
#!/bin/bash

# Create master key for tenant encryption
KEY_OUTPUT=$(awslocal kms create-key --description "Tenant Master Key" --key-usage ENCRYPT_DECRYPT)
KEY_ID=$(echo $KEY_OUTPUT | jq -r '.KeyMetadata.KeyId')

# Create alias for easy reference
awslocal kms create-alias --alias-name alias/tenant-master-key --target-key-id $KEY_ID

# Create per-tenant keys (for testing)
for TENANT in "tenant-small" "tenant-medium" "tenant-large"; do
    TENANT_KEY=$(awslocal kms create-key --description "KEK for $TENANT")
    TENANT_KEY_ID=$(echo $TENANT_KEY | jq -r '.KeyMetadata.KeyId')
    awslocal kms create-alias --alias-name "alias/$TENANT-kek" --target-key-id $TENANT_KEY_ID
done

echo "KMS keys initialized"
```

### IAM (Identity & Access Management)
```bash
# Init script: localstack/init/ready.d/03-iam.sh
#!/bin/bash

# Create application role
awslocal iam create-role --role-name app-service-role \
    --assume-role-policy-document '{
      "Version": "2012-10-17",
      "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "ec2.amazonaws.com"},
        "Action": "sts:AssumeRole"
      }]
    }'

# KMS policy: app can encrypt/decrypt with tenant keys
awslocal iam put-role-policy --role-name app-service-role \
    --policy-name kms-tenant-access \
    --policy-document '{
      "Version": "2012-10-17",
      "Statement": [{
        "Effect": "Allow",
        "Action": ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey"],
        "Resource": "arn:aws:kms:us-east-1:000000000000:key/*",
        "Condition": {
          "StringEquals": {
            "kms:ViaService": "secretsmanager.us-east-1.amazonaws.com"
          }
        }
      }]
    }'

# S3 policy: app can read/write to app buckets only
awslocal iam put-role-policy --role-name app-service-role \
    --policy-name s3-app-access \
    --policy-document '{
      "Version": "2012-10-17",
      "Statement": [{
        "Effect": "Allow",
        "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"],
        "Resource": [
          "arn:aws:s3:::app-*",
          "arn:aws:s3:::app-*/*"
        ]
      }]
    }'
```

### Route 53 (DNS & Geo-Routing)
```bash
# Init script: localstack/init/ready.d/04-route53.sh
#!/bin/bash

# Create hosted zone
ZONE_OUTPUT=$(awslocal route53 create-hosted-zone \
    --name app.local \
    --caller-reference "local-$(date +%s)")
ZONE_ID=$(echo $ZONE_OUTPUT | jq -r '.HostedZone.Id' | cut -d'/' -f3)

# Geo-routing: US East
awslocal route53 change-resource-record-sets --hosted-zone-id $ZONE_ID \
    --change-batch '{
      "Changes": [{
        "Action": "CREATE",
        "ResourceRecordSet": {
          "Name": "api.app.local",
          "Type": "A",
          "SetIdentifier": "us-east-1",
          "GeoLocation": {"CountryCode": "US", "SubdivisionCode": "VA"},
          "TTL": 60,
          "ResourceRecords": [{"Value": "172.18.0.160"}]
        }
      }]
    }'

# Geo-routing: US West
awslocal route53 change-resource-record-sets --hosted-zone-id $ZONE_ID \
    --change-batch '{
      "Changes": [{
        "Action": "CREATE",
        "ResourceRecordSet": {
          "Name": "api.app.local",
          "Type": "A",
          "SetIdentifier": "us-west-1",
          "GeoLocation": {"CountryCode": "US", "SubdivisionCode": "CA"},
          "TTL": 60,
          "ResourceRecords": [{"Value": "172.18.0.170"}]
        }
      }]
    }'

# Health check
awslocal route53 create-health-check --caller-reference "east-health" \
    --health-check-config '{
      "IPAddress": "172.18.0.160",
      "Port": 9000,
      "Type": "HTTP",
      "ResourcePath": "/health",
      "RequestInterval": 10,
      "FailureThreshold": 3
    }'
```

### Secrets Manager
```bash
# Init script: localstack/init/ready.d/05-secrets.sh
#!/bin/bash

# Database credentials
awslocal secretsmanager create-secret \
    --name "app/database/shared" \
    --secret-string '{"host":"postgres","port":5432,"dbname":"app","user":"app","password":"app"}'

# Per-tenant secrets
awslocal secretsmanager create-secret \
    --name "app/tenant/tenant-large/database" \
    --secret-string '{"host":"postgres-dedicated","port":5432,"dbname":"app_tenant_large","user":"app","password":"app"}'

# API keys for external services
awslocal secretsmanager create-secret \
    --name "app/integrations/stripe" \
    --secret-string '{"api_key":"sk_test_fake","webhook_secret":"whsec_test_fake"}'
```

### SQS (Message Queues)
```bash
# Init script: localstack/init/ready.d/06-sqs.sh
#!/bin/bash

# Standard queues
awslocal sqs create-queue --queue-name app-events
awslocal sqs create-queue --queue-name app-notifications

# Dead letter queue
awslocal sqs create-queue --queue-name app-events-dlq

# Configure DLQ redrive policy
EVENTS_URL=$(awslocal sqs get-queue-url --queue-name app-events --output text --query 'QueueUrl')
DLQ_ARN=$(awslocal sqs get-queue-attributes --queue-url $(awslocal sqs get-queue-url --queue-name app-events-dlq --output text --query 'QueueUrl') --attribute-names QueueArn --output text --query 'Attributes.QueueArn')

awslocal sqs set-queue-attributes --queue-url $EVENTS_URL \
    --attributes "{\"RedrivePolicy\":\"{\\\"deadLetterTargetArn\\\":\\\"$DLQ_ARN\\\",\\\"maxReceiveCount\\\":\\\"3\\\"}\"}"

# FIFO queue (for ordered processing)
awslocal sqs create-queue --queue-name app-tenant-ops.fifo \
    --attributes '{"FifoQueue":"true","ContentBasedDeduplication":"true"}'
```

---

## Multi-Region Simulation with Nginx Geo-Router

### Geo-Router Configuration
```nginx
# config/geo-router.conf — Simulates Route 53 geo-based routing

# Map region header to backend
map $http_x_region $region_backend {
    "us-west-1"  us_west;
    "eu-west-1"  eu_west;
    default       us_east;
}

upstream us_east {
    server 172.18.0.160:9000;  # cp-shared-east
}

upstream us_west {
    server 172.18.0.170:9000;  # cp-shared-west
}

upstream eu_west {
    server 172.18.0.180:9000;  # cp-shared-eu (if deployed)
}

server {
    listen 80;
    server_name *.app.local;

    # Extract tenant from subdomain
    set $tenant_subdomain "";
    if ($host ~* "^(.+)\.app\.local$") {
        set $tenant_subdomain $1;
    }

    location / {
        proxy_pass http://$region_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Region $http_x_region;
        proxy_set_header X-Tenant-Subdomain $tenant_subdomain;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /health {
        proxy_pass http://$region_backend;
    }
}
```

### Regional ALB Configuration
```nginx
# config/alb-us-east-1.conf
upstream api_east {
    server cp-shared-east:9000;
}

upstream ui_east {
    server ui-us-east-1:3000;
}

server {
    listen 80;

    location /api/ {
        proxy_pass http://api_east;
    }

    location / {
        proxy_pass http://ui_east;
    }
}
```

---

## Testing with LocalStack

### Integration Test Setup
```go
func TestWithLocalStack(t *testing.T) {
    // Skip if LocalStack not running
    endpoint := os.Getenv("AWS_ENDPOINT_URL")
    if endpoint == "" {
        t.Skip("LocalStack not running (set AWS_ENDPOINT_URL)")
    }

    cfg, err := NewLocalAWSConfig(context.Background())
    require.NoError(t, err)

    s3Client := s3.NewFromConfig(cfg, func(o *s3.Options) {
        o.UsePathStyle = true
    })

    // Test S3 upload
    _, err = s3Client.PutObject(context.Background(), &s3.PutObjectInput{
        Bucket: aws.String("app-uploads"),
        Key:    aws.String("test/file.txt"),
        Body:   strings.NewReader("test content"),
    })
    assert.NoError(t, err)
}
```

### CI/CD Integration
```yaml
# .github/workflows/test.yml
jobs:
  integration-test:
    runs-on: ubuntu-latest
    services:
      localstack:
        image: localstack/localstack:4.4
        ports:
          - 4566:4566
        env:
          SERVICES: s3,kms,sqs,secretsmanager
          DEFAULT_REGION: us-east-1

    env:
      AWS_ENDPOINT_URL: http://localhost:4566
      AWS_ACCESS_KEY_ID: test
      AWS_SECRET_ACCESS_KEY: test
      AWS_DEFAULT_REGION: us-east-1

    steps:
      - uses: actions/checkout@v4
      - name: Wait for LocalStack
        run: |
          until curl -s http://localhost:4566/_localstack/health | jq -e '.services.s3 == "running"'; do
            sleep 2
          done
      - name: Seed LocalStack
        run: ./scripts/localstack-seed.sh
      - name: Run tests
        run: make test-integration
```

---

## HA / Active-Active Deployment with Route 53 Failover

### Architecture

```
┌─── Region: us-east-1 (primary) ──────────┐  ┌─── Region: us-west-2 (secondary) ────────┐
│  frontend-east:3000                       │  │  frontend-west:3001                       │
│  backend-east:8080   ←── /healthz ──┐     │  │  backend-west:8081   ←── /healthz ──┐     │
│  postgres-east:5432                 │     │  │  postgres-west:5433                 │     │
│  (full app stack)                   │     │  │  (full app stack)                   │     │
└─────────────────────────────────────┼─────┘  └─────────────────────────────────────┼─────┘
                                      │                                               │
                           ┌──────────┴───────────────────────────────────────────────┘
                           │
                ┌──────────▼──────────┐
                │  LocalStack:4566    │
                │  Route 53           │
                │  ┌────────────────┐ │
                │  │ app.local      │ │
                │  │ A: east (50%)  │ │
                │  │ A: west (50%)  │ │
                │  │ Health checks  │ │
                │  └────────────────┘ │
                └─────────────────────┘
```

### docker-compose.ha.yml

```yaml
# Extends base docker-compose.yml with multi-region HA
# Usage: docker compose -f docker-compose.yml -f docker-compose.ha.yml up -d

services:
  # ── Primary Region (us-east-1) ──
  # Uses base services: frontend (3000), backend (8080), postgres (5432)

  # ── Secondary Region (us-west-2) ──
  frontend-west:
    build:
      context: ./frontend
      target: development
    ports:
      - "3001:3000"
    environment:
      VITE_API_URL: http://localhost:8081
    depends_on:
      backend-west:
        condition: service_healthy

  backend-west:
    build: ./backend
    ports:
      - "8081:8080"
    environment:
      DATABASE_URL: postgres://calc:calc@postgres-west:5432/calc?sslmode=disable
      APP_ENV: development
      SESSION_SECRET: dev-secret-west
      OTEL_EXPORTER_OTLP_ENDPOINT: otel-collector:4317
      CORS_ALLOWED_ORIGINS: http://localhost:3001
    depends_on:
      postgres-west:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:8080/healthz"]
      interval: 5s
      timeout: 3s
      retries: 3

  postgres-west:
    image: postgres:16-alpine
    ports:
      - "5433:5432"
    environment:
      POSTGRES_DB: calc
      POSTGRES_USER: calc
      POSTGRES_PASSWORD: calc
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U calc -d calc"]
      interval: 5s
      timeout: 3s
      retries: 5

  # ── LocalStack (Route 53 + Health Checks) ──
  localstack:
    image: localstack/localstack:4.4
    ports:
      - "4566:4566"
    environment:
      SERVICES: route53
      DEFAULT_REGION: us-east-1
    volumes:
      - "./localstack/init:/etc/localstack/init/ready.d"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:4566/_localstack/health"]
      interval: 10s
      timeout: 5s
      retries: 5
```

### Route 53 Init Script

```bash
#!/bin/bash
# localstack/init/ready.d/01-route53-ha.sh
# Creates active-active Route 53 configuration with health checks

set -e

echo "Setting up Route 53 active-active routing..."

# Create hosted zone
ZONE_OUTPUT=$(awslocal route53 create-hosted-zone \
    --name app.local \
    --caller-reference "ha-$(date +%s)")
ZONE_ID=$(echo $ZONE_OUTPUT | jq -r '.HostedZone.Id' | cut -d'/' -f3)
echo "Hosted zone created: $ZONE_ID"

# Health check: us-east-1 (primary)
EAST_HC=$(awslocal route53 create-health-check \
    --caller-reference "east-health-$(date +%s)" \
    --health-check-config '{
      "IPAddress": "host.docker.internal",
      "Port": 8080,
      "Type": "HTTP",
      "ResourcePath": "/healthz",
      "RequestInterval": 10,
      "FailureThreshold": 2
    }')
EAST_HC_ID=$(echo $EAST_HC | jq -r '.HealthCheck.Id')
echo "East health check: $EAST_HC_ID"

# Health check: us-west-2 (secondary)
WEST_HC=$(awslocal route53 create-health-check \
    --caller-reference "west-health-$(date +%s)" \
    --health-check-config '{
      "IPAddress": "host.docker.internal",
      "Port": 8081,
      "Type": "HTTP",
      "ResourcePath": "/healthz",
      "RequestInterval": 10,
      "FailureThreshold": 2
    }')
WEST_HC_ID=$(echo $WEST_HC | jq -r '.HealthCheck.Id')
echo "West health check: $WEST_HC_ID"

# Weighted routing: 50/50 active-active
awslocal route53 change-resource-record-sets --hosted-zone-id $ZONE_ID \
    --change-batch "{
      \"Changes\": [{
        \"Action\": \"CREATE\",
        \"ResourceRecordSet\": {
          \"Name\": \"api.app.local\",
          \"Type\": \"A\",
          \"SetIdentifier\": \"us-east-1\",
          \"Weight\": 50,
          \"TTL\": 10,
          \"ResourceRecords\": [{\"Value\": \"127.0.0.1\"}],
          \"HealthCheckId\": \"$EAST_HC_ID\"
        }
      }]
    }"

awslocal route53 change-resource-record-sets --hosted-zone-id $ZONE_ID \
    --change-batch "{
      \"Changes\": [{
        \"Action\": \"CREATE\",
        \"ResourceRecordSet\": {
          \"Name\": \"api.app.local\",
          \"Type\": \"A\",
          \"SetIdentifier\": \"us-west-2\",
          \"Weight\": 50,
          \"TTL\": 10,
          \"ResourceRecords\": [{\"Value\": \"127.0.0.1\"}],
          \"HealthCheckId\": \"$WEST_HC_ID\"
        }
      }]
    }"

echo "Route 53 active-active routing configured"
echo "  East: port 8080, health check: $EAST_HC_ID"
echo "  West: port 8081, health check: $WEST_HC_ID"
```

### Failover Test Script

```bash
#!/bin/bash
# scripts/failover-test.sh
# Validates HA setup by simulating region failures

set -e
PASS=0
FAIL=0

log_pass() { echo "  ✓ $1"; PASS=$((PASS+1)); }
log_fail() { echo "  ✗ $1"; FAIL=$((FAIL+1)); }

echo "═══ HA Failover Test Suite ═══"
echo ""

# Test 1: Both regions healthy
echo "Test 1: Both regions healthy"
EAST=$(curl -sf -o /dev/null -w "%{http_code}" http://localhost:8080/healthz)
WEST=$(curl -sf -o /dev/null -w "%{http_code}" http://localhost:8081/healthz)
[ "$EAST" = "200" ] && log_pass "East healthy ($EAST)" || log_fail "East unhealthy ($EAST)"
[ "$WEST" = "200" ] && log_pass "West healthy ($WEST)" || log_fail "West unhealthy ($WEST)"

# Test 2: Route 53 returns both records
echo ""
echo "Test 2: Route 53 weighted records"
RECORDS=$(awslocal route53 list-resource-record-sets \
    --hosted-zone-id $(awslocal route53 list-hosted-zones | jq -r '.HostedZones[0].Id' | cut -d'/' -f3) \
    | jq '.ResourceRecordSets | length')
[ "$RECORDS" -ge 2 ] && log_pass "Both regions in Route 53 ($RECORDS records)" || log_fail "Missing records ($RECORDS)"

# Test 3: Stop primary → secondary still serves
echo ""
echo "Test 3: Primary failure → secondary serves"
docker stop calc-backend-1 2>/dev/null || true
sleep 5
WEST_AFTER=$(curl -sf -o /dev/null -w "%{http_code}" http://localhost:8081/healthz)
[ "$WEST_AFTER" = "200" ] && log_pass "West still healthy after east stopped" || log_fail "West also failed"

# Verify east is actually down
EAST_DOWN=$(curl -sf -o /dev/null -w "%{http_code}" http://localhost:8080/healthz 2>/dev/null || echo "000")
[ "$EAST_DOWN" != "200" ] && log_pass "East confirmed down ($EAST_DOWN)" || log_fail "East still up"

# Test 4: Restart primary → both healthy again
echo ""
echo "Test 4: Primary recovery"
docker start calc-backend-1 2>/dev/null || true
sleep 10  # Wait for health check to recover
EAST_RECOVERED=$(curl -sf -o /dev/null -w "%{http_code}" http://localhost:8080/healthz)
[ "$EAST_RECOVERED" = "200" ] && log_pass "East recovered ($EAST_RECOVERED)" || log_fail "East failed to recover"

# Test 5: Stop secondary → primary still serves
echo ""
echo "Test 5: Secondary failure → primary serves"
docker stop calc-backend-west-1 2>/dev/null || true
sleep 5
EAST_ALONE=$(curl -sf -o /dev/null -w "%{http_code}" http://localhost:8080/healthz)
[ "$EAST_ALONE" = "200" ] && log_pass "East still healthy after west stopped" || log_fail "East also failed"

# Test 6: Restart secondary → both healthy
echo ""
echo "Test 6: Full recovery"
docker start calc-backend-west-1 2>/dev/null || true
sleep 10
BOTH_EAST=$(curl -sf -o /dev/null -w "%{http_code}" http://localhost:8080/healthz)
BOTH_WEST=$(curl -sf -o /dev/null -w "%{http_code}" http://localhost:8081/healthz)
[ "$BOTH_EAST" = "200" ] && [ "$BOTH_WEST" = "200" ] && log_pass "Both regions recovered" || log_fail "Recovery incomplete"

# Summary
echo ""
echo "═══ Results: $PASS passed, $FAIL failed ═══"
[ $FAIL -eq 0 ] && echo "HA validation: PASS" || echo "HA validation: FAIL"
exit $FAIL
```

### Deploy Command Integration

```bash
# /deploy --target=ha-local
docker compose -f docker-compose.yml -f docker-compose.ha.yml up -d
# Wait for all services healthy
echo "Waiting for both regions..."
until curl -sf http://localhost:8080/healthz && curl -sf http://localhost:8081/healthz; do sleep 2; done
echo "HA stack ready"

# /deploy --failover-test
./scripts/failover-test.sh
```

---

## Critical Rules

1. **NEVER** hardcode AWS credentials — always use environment variables or IAM roles
2. **ALWAYS** use endpoint configuration that switches between LocalStack and real AWS via env var
3. **NEVER** commit `.env` files with real AWS credentials — only `.env.example` with LocalStack defaults
4. **ALWAYS** create init scripts in `localstack/init/ready.d/` for reproducible setup
5. **ALWAYS** add healthcheck wait before running tests against LocalStack
6. **NEVER** use LocalStack-specific APIs in application code — only standard AWS SDK calls
7. **ALWAYS** test with at least 2 regions locally to catch region-specific assumptions
8. Init scripts MUST be idempotent — safe to run multiple times on container restart
