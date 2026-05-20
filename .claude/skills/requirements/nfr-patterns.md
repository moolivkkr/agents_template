# Non-Functional Requirement Patterns — Scoping, Measuring, Testing

## NFR Anatomy (All Parts Required)

```
ID:          NFR-PERF-001
Category:    Performance
Requirement: API response time under load
Target:      p95 latency < 200ms
Applies To:  All GET endpoints under /api/v1/ (excludes batch/export endpoints)
Measurement: Load test with 100 concurrent users, 1000 requests/endpoint
Verification: Automated load test in CI pipeline
Priority:    MUST (RFC 2119)
```

## NFR Categories with Templates

### Performance
```
NFR-PERF-NNN: [Endpoint/Operation] response time
  Target: p95 < [X]ms, p99 < [Y]ms
  Applies to: [list endpoints or "all read endpoints"]
  Under load: [N concurrent users, N requests]
  Excludes: [batch operations, file uploads, reports]
```

### Availability
```
NFR-AVAIL-NNN: System uptime
  Target: [99.9%] monthly uptime
  Measurement: [health check endpoint, monitoring tool]
  Planned maintenance: [excluded/included from calculation]
  Recovery: RTO < [X minutes], RPO < [X minutes]
```

### Security
```
NFR-SEC-NNN: [Security control]
  Requirement: [specific control — not "system is secure"]
  Applies to: [which data, endpoints, user types]
  Standard: [OWASP Top 10, SOC2, HIPAA, GDPR — be specific]
  Verification: [penetration test, automated scan, code review]
```

### Scalability
```
NFR-SCALE-NNN: [Growth dimension]
  Current: [N users, N records, N requests/day]
  Target: [10x current within 12 months]
  Approach: [horizontal scaling, caching, read replicas]
  Bottleneck: [database writes, file storage, API gateway]
```

### Data
```
NFR-DATA-NNN: [Data requirement]
  Retention: [how long data is kept]
  Deletion: [GDPR right-to-delete, soft delete + hard purge after N days]
  Backup: [frequency, retention, tested restore procedure]
  Export: [user can export their data in [format] within [timeframe]]
```

## Scoping Rules

Every NFR must answer: **"Applies to WHAT, specifically?"**

| Vague Scope | Specific Scope |
|---|---|
| "System must be fast" | "GET endpoints under /api/v1/ must respond < 200ms p95" |
| "Data must be encrypted" | "PII fields (email, phone, address) encrypted at rest with AES-256" |
| "System must scale" | "Handle 10K concurrent users with < 500ms p95 response" |
| "System must be available" | "99.9% uptime measured monthly, excluding planned maintenance windows" |

## NFR Conflict Resolution

When NFRs conflict, use this priority order (unless project overrides):

```
1. Security / Compliance  (legal requirements, cannot compromise)
2. Data Integrity         (no data loss, no corruption)
3. Availability           (system must be reachable)
4. Performance            (system must be responsive)
5. Scalability            (system must handle growth)
6. Usability              (system must be easy to use)
```

Example conflict: "Encrypt all API responses" (security) vs "API responds < 100ms" (performance).
Resolution: Encrypt at rest + TLS in transit (handles both); don't encrypt response body twice.

## Verification Methods

| NFR Type | Verification | When |
|---|---|---|
| Performance | Load test (k6, Artillery) | CI pipeline + pre-release |
| Security | OWASP scan + code review | Every phase review |
| Availability | Health checks + monitoring | Continuous |
| Scalability | Load test at 10x capacity | Pre-release |
| Data retention | Audit query + deletion test | Quarterly |
| Accessibility | axe-core + manual audit | Every UI phase |

## Anti-Patterns

| Pattern | Problem | Fix |
|---------|---------|-----|
| "System must be performant" | No target, no scope | "GET /users: p95 < 200ms at 100 concurrent" |
| NFR with no measurement method | Can't verify compliance | Add "Measured by: [tool/method]" |
| NFR applies to "everything" | Unrealistic, never verified | Scope to specific endpoints/components |
| Security NFR without standard | Ambiguous what to check | Reference OWASP, SOC2, or specific controls |
| Performance target without load | Meaningless without context | "< 200ms at 100 concurrent users" not just "< 200ms" |
