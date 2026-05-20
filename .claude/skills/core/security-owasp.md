---
skill: security-owasp
description: OWASP Top 10, input validation, injection prevention, auth best practices, secrets management, dependency scanning
version: "1.0"
tags:
  - security
  - owasp
  - auth
  - jwt
  - secrets
---

# Security — OWASP

## OWASP Top 10 Mitigations

- **A01 Broken Access Control:** Server-side authz every request; deny-by-default; validate user X owns resource Y
- **A02 Cryptographic Failures:** TLS 1.2+; bcrypt (cost>=12)/scrypt/argon2id for passwords; AES-256-GCM for PII at rest; key management via vault
- **A03 Injection:** Parameterized queries only; validate/sanitize inputs at boundary; use ORM that parameterizes by default
- **A05 Misconfiguration:** Remove defaults; disable debug/stack traces in prod; set security headers
- **A06 Vulnerable Components:** Dependency scanning in CI (trivy/snyk/govulncheck); pin versions; automate updates
- **A07 Auth Failures:** MFA for admin; lockout after 5-10 failures; constant-time token comparison
- **A08 Integrity:** Verify artifact signatures; SBOM in CI; schema validation before deserialization

## Input Validation

> See `backend/archetypes/error-handling.md` for error taxonomy (422 vs 400).

- Validate type, format, length, range, allowed values at boundary
- Reject early — don't sanitize and continue on invalid input
- Allowlists not denylists; validate file uploads (MIME, size, filename, malware scan)

## XSS Prevention

- Auto-escaping templates (React JSX, Go html/template); CSP header
- Never `innerHTML`, `eval()`, `document.write()` with user content; use DOMPurify if HTML input accepted

## CSRF

- `SameSite=Strict/Lax` on session cookies; require custom header or validate Origin for APIs
- CSRF tokens for form apps; Bearer token APIs not CSRF-vulnerable

## Security Headers

```
Content-Security-Policy: default-src 'self'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), camera=()
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

## JWT Best Practices

- RS256 for public-facing; HS256 for internal only
- 15min access tokens, 7d refresh; validate iss/aud/exp/nbf on every request
- No sensitive data in payload (base64, not encrypted); token rotation on refresh; short-lived blocklist in Redis

## Session Management

- Cryptographically random IDs (32+ bytes); server-side storage (Redis)
- Invalidate on logout, privilege change, password reset; `HttpOnly`, `Secure`, `SameSite` cookies

## Secrets Management

- Never hardcode; use env vars or secrets manager (Vault, AWS SM)
- Rotate regularly; separate per environment; audit access
- `.gitignore`: `.env`, `.env.*`, `*.pem`, `*.key`, `credentials.json`

## Critical Rules

- Fail closed — deny on error
- Log security events but never passwords/tokens
- SAST (CodeQL/semgrep) + DAST (OWASP ZAP) in CI
- Threat model before building auth/payment
- Least privilege for all service accounts and DB users
