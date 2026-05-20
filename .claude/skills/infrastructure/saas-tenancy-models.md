# SaaS Tenancy Models — Pooled, Dedicated, and Hybrid Architecture

## Decision Tree: Choosing Your Tenancy Model

### When to Use Pooled (Shared Infrastructure)
- **Customer profile:** Small/medium, price-sensitive, standard SLAs
- **Scale:** 100-10,000+ tenants on shared infrastructure
- **Cost model:** Low per-tenant cost, high tenant density
- **Trade-off:** Noisy neighbor risk, shared failure domain
- **Best for:** Free tier, starter plans, self-service SaaS

### When to Use Dedicated (Isolated Infrastructure)
- **Customer profile:** Medium/large, compliance-driven, custom SLAs
- **Scale:** 10-100 tenants, each with significant load
- **Cost model:** Higher per-tenant cost, predictable performance
- **Trade-off:** Higher ops complexity, more infrastructure to manage
- **Best for:** Enterprise tier, regulated industries, high-value customers

### When to Use Hybrid (Recommended for SaaS at Scale)
- **Small/Medium customers:** Pooled infrastructure (shared DB + RLS, shared compute)
- **Large/Enterprise customers:** Dedicated infrastructure (separate DB, dedicated compute)
- **Same codebase:** Both modes served by identical application code
- **Runtime routing:** Tenant configuration determines which path

---

## Pooled Architecture Patterns

### Database Isolation: Three-Layer Defense

**Layer 1 — Application-Level Filtering (PRIMARY):**
Every repository query MUST include `WHERE tenant_id = $1`:
```go
// Go example
func (r *Repository) List(ctx context.Context) ([]*Resource, error) {
    tenantID := tenant.IDFromContext(ctx)
    query := `SELECT * FROM resources WHERE tenant_id = $1 AND deleted_at IS NULL`
    return r.pool.Query(ctx, query, tenantID)
}
```
```typescript
// TypeScript example
async list(ctx: RequestContext): Promise<Resource[]> {
    return this.db.query(
        'SELECT * FROM resources WHERE tenant_id = $1 AND deleted_at IS NULL',
        [ctx.tenantId]
    );
}
```
```python
# Python example
def list(self, tenant_id: UUID) -> list[Resource]:
    return self.session.query(Resource).filter(
        Resource.tenant_id == tenant_id,
        Resource.deleted_at.is_(None)
    ).all()
```

**Layer 2 — PostgreSQL Row-Level Security (DEFENSE-IN-DEPTH):**
```sql
-- Enable RLS on every tenant-scoped table
ALTER TABLE resources ENABLE ROW LEVEL SECURITY;
ALTER TABLE resources FORCE ROW LEVEL SECURITY;

-- Policy enforces isolation even if WHERE clause is missing
CREATE POLICY tenant_isolation ON resources
    USING (tenant_id = current_setting('app.tenant_id')::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
```

**Layer 3 — Connection Middleware (SET LOCAL):**
```go
// Middleware sets tenant context on every DB connection
func (m *TenantMiddleware) Handler(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        tenantID := extractTenantID(r) // JWT > API Key > mTLS > Header

        // Set RLS context for this transaction
        _, err := pool.Exec(ctx, "SET LOCAL app.tenant_id = $1", tenantID)
        if err != nil {
            http.Error(w, "tenant context failed", 500)
            return
        }

        ctx = context.WithValue(ctx, tenantIDKey, tenantID)
        next.ServeHTTP(w, r.WithContext(ctx))
    })
}
```

### Composite Unique Constraints
All uniqueness constraints MUST be tenant-scoped:
```sql
-- WRONG: global uniqueness
UNIQUE(serial_number)

-- RIGHT: per-tenant uniqueness
UNIQUE(tenant_id, serial_number)
UNIQUE(tenant_id, name)
UNIQUE(tenant_id, slug)
```

### Noisy Neighbor Protection
```go
// Per-tenant rate limiter
type TenantRateLimiter struct {
    limiters sync.Map // tenant_id → *rate.Limiter
}

func (l *TenantRateLimiter) Allow(tenantID string, tier string) bool {
    limit := tierLimits[tier] // e.g., free=60/min, pro=600/min, enterprise=6000/min
    limiter, _ := l.limiters.LoadOrStore(tenantID,
        rate.NewLimiter(rate.Limit(limit/60), limit))
    return limiter.(*rate.Limiter).Allow()
}

// Per-tenant circuit breaker (failure isolation)
type TenantCircuitBreaker struct {
    breakers sync.Map // tenant_id → *gobreaker.CircuitBreaker
}
```

**Rate Limit Tiers (example):**
| Operation | Free | Pro | Enterprise |
|-----------|------|-----|------------|
| API calls/min | 60 | 600 | 6,000 |
| Write operations/min | 10 | 100 | 1,000 |
| WebSocket connections | 5 | 50 | 500 |
| Bulk operations/hour | 1 | 10 | 100 |

---
## Dedicated Architecture Patterns

### Database Routing
```go
// TenantDBRouter selects the correct connection pool per tenant
type TenantDBRouter struct {
    sharedPool     *pgxpool.Pool             // All pooled tenants share this
    dedicatedPools map[string]*pgxpool.Pool   // tenant_id → dedicated pool
    mu             sync.RWMutex              // Protects dedicatedPools map
    tenantSvc      TenantService
}

func (r *TenantDBRouter) GetPool(ctx context.Context, tenantID string) (*pgxpool.Pool, error) {
    // Fast path: check dedicated pool cache
    r.mu.RLock()
    if pool, ok := r.dedicatedPools[tenantID]; ok {
        r.mu.RUnlock()
        return pool, nil
    }
    r.mu.RUnlock()

    // Look up tenant config
    tenant, err := r.tenantSvc.Get(ctx, tenantID)
    if err != nil {
        return nil, err
    }

    if tenant.DBMode == "shared" {
        return r.sharedPool, nil
    }

    // Lazy-create dedicated pool (double-check locking)
    r.mu.Lock()
    defer r.mu.Unlock()
    if pool, ok := r.dedicatedPools[tenantID]; ok {
        return pool, nil // Another goroutine created it
    }

    dsn := fmt.Sprintf("postgres://%s:%s@%s:%d/%s",
        tenant.DBUser, tenant.DBPass, *tenant.DBHost, 5432, *tenant.DBName)
    pool, err := pgxpool.New(ctx, dsn)
    if err != nil {
        return nil, fmt.Errorf("dedicated pool for %s: %w", tenantID, err)
    }
    r.dedicatedPools[tenantID] = pool
    return pool, nil
}
```

### Tenant Configuration Model
```go
type Tenant struct {
    ID              uuid.UUID
    Slug            string
    Name            string
    Plan            string   // free, starter, pro, enterprise
    Status          string   // active, suspended, deprovisioning
    DBMode          string   // "shared" or "dedicated"
    DBHost          *string  // NULL for shared (uses default)
    DBName          *string  // NULL for shared (uses default DB)
    MaxResources    int      // Tier-based limit
    RateLimit       int      // API calls per minute
    Settings        JSONB    // Tenant-specific configuration
}
```

### Dedicated Compute (Kubernetes)
```yaml
# Kubernetes namespace per premium tenant
apiVersion: v1
kind: Namespace
metadata:
  name: app-tenant-${TENANT_SLUG}
  labels:
    app.io/tenant: ${TENANT_SLUG}
    app.io/tier: enterprise

---
# Dedicated API deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-server
  namespace: app-tenant-${TENANT_SLUG}
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: api
        resources:
          requests: { cpu: "2", memory: "4Gi" }
          limits: { cpu: "4", memory: "8Gi" }
        env:
        - name: TENANT_ID
          value: "${TENANT_ID}"
        - name: TENANT_MODE
          value: "dedicated"
        - name: DATABASE_DSN
          valueFrom:
            secretKeyRef:
              name: tenant-db-credentials
              key: dsn
```

---

## Online Migration: Shared → Dedicated

When a tenant upgrades from pooled to dedicated:

```
Step 1: Provision dedicated database
  CREATE DATABASE app_${tenant_slug};
  Run all migrations against new database

Step 2: Initial data copy
  pg_dump --data-only with WHERE tenant_id = '${id}' per table
  pg_restore into dedicated database

Step 3: Incremental sync (while tenant is still on shared)
  Copy rows WHERE updated_at > ${last_sync_time}
  Handle inserts, updates, deletes

Step 4: Cutover (~5 second pause)
  a. Block writes for this tenant (set status = 'migrating')
  b. Final incremental sync
  c. Verify row counts match between shared and dedicated
  d. Update tenant.db_mode = 'dedicated', set db_host, db_name
  e. Update TenantDBRouter (add to dedicatedPools)
  f. Resume writes (set status = 'active')

Step 5: Cleanup (after 24-hour validation period)
  DELETE FROM shared tables WHERE tenant_id = '${id}'
  VACUUM affected tables
```

**Rollback:** If issues detected within 24 hours:
1. Revert tenant.db_mode to 'shared'
2. Copy any new data from dedicated back to shared
3. Remove dedicated pool from router

---

## Tenant Lifecycle

### Provisioning
```
CREATE TENANT:
  1. Generate tenant UUID
  2. Insert tenant record (status: active, db_mode: shared)
  3. If dedicated: create database + run migrations
  4. Provision encryption keys (Vault Transit or KMS)
  5. Create default admin user
  6. Generate bootstrap API key
  7. Return: tenant_id, admin_credentials, api_key
```

### Deprovisioning
```
DEPROVISION TENANT:
  1. Set status → deprovisioning (block new operations)
  2. Data export window (30 days)
  3. Retention period (read-only access)
  4. Permanent deletion:
     a. Delete all tenant data from DB
     b. Destroy encryption keys (crypto-shredding)
     c. Revoke all API keys and tokens
     d. Purge audit logs (after compliance retention)
  5. If dedicated: DROP DATABASE, remove K8s namespace
```

---

## Tenant ID Extraction Priority

Standard extraction order for multi-method authentication:
```
Priority 1: JWT Bearer token (Authorization header)
  → Extract tenant_id from JWT claims

Priority 2: API Key (X-API-Key header)
  → Look up tenant by key prefix, validate with bcrypt

Priority 3: mTLS Client Certificate
  → Parse tenant_id from certificate SAN URI

Priority 4: X-Tenant-ID header (DEV MODE ONLY)
  → Only when ENABLE_DEV_MODE=true
  → NEVER in production
```

---

## Per-Tenant Encryption

### Key Hierarchy
```
KEK (Key Encryption Key)
├─ Storage: Vault Transit or AWS KMS
├─ Path: transit/keys/tenant-${tenant_id}-kek
├─ Rotation: Every 90 days per tenant
└─ Purpose: Encrypts/decrypts DEKs

    DEK (Data Encryption Key)
    ├─ Storage: Database (encrypted by KEK)
    ├─ Per: component (one DEK per data category)
    ├─ Algorithm: AES-256-GCM
    └─ Purpose: Encrypts/decrypts actual data

        ENCRYPTED DATA
        ├─ Sensitive configuration (API keys, tokens, secrets)
        ├─ PII fields
        └─ Credentials
```

---

## Observability in Multi-Tenant Systems

**Every log line MUST include:**
- `tenant_id` — for filtering and alerting per tenant
- `tenant_tier` — for tier-specific monitoring
- `db_pool` — "shared" or "dedicated_{tenant_id}"
- `trace_id` — OpenTelemetry trace correlation

**Per-tenant metrics:**
- Request rate by tenant (watch for quota violations)
- Error rate by tenant (detect tenant-specific issues)
- Latency percentiles by tenant (detect noisy neighbors)
- DB connection pool usage by tenant (dedicated pools)

**Alerting:**
- High error rate for a single tenant → investigate before it affects others
- Resource exhaustion on shared pool → potential noisy neighbor
- Dedicated pool connection exhaustion → scale dedicated resources

---

## Critical Rules

1. **NEVER** access data without tenant context — every query, every log, every metric includes tenant_id
2. **NEVER** use global unique constraints — always scope with tenant_id
3. **NEVER** trust client-provided tenant_id in production — extract from verified credentials (JWT, API key, mTLS)
4. **ALWAYS** use RLS as defense-in-depth, even with application-level filtering
5. **ALWAYS** rate-limit per tenant, not just globally
6. **ALWAYS** encrypt tenant-specific secrets with per-tenant keys (not a shared key)
7. **NEVER** expose one tenant's data in another tenant's error messages or logs
8. Test with at least 3 tenants: one pooled, one dedicated, one in migration
