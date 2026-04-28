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

Core security practices covering OWASP Top 10, authentication, and secrets management.

## OWASP Top 10 — Key Mitigations

**A01 Broken Access Control**
- Enforce authorization on every request server-side; never trust client claims
- Use deny-by-default; explicitly grant permissions
- Validate that user X owns resource Y before any read/write/delete

**A02 Cryptographic Failures**
- Use TLS 1.2+ everywhere; no HTTP for sensitive data
- Hash passwords with bcrypt (cost ≥12), scrypt, or argon2id — never MD5/SHA1
- Encrypt PII at rest using AES-256-GCM; manage keys via vault (AWS KMS, HashiCorp Vault)

**A03 Injection**
- Use parameterized queries / prepared statements — never string concatenation for SQL
- Validate and sanitize all inputs at the API boundary
- Use an ORM or query builder that parameterizes by default

```python
# WRONG
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")

# RIGHT
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
```

**A05 Security Misconfiguration**
- Remove default credentials before deployment
- Disable debug endpoints, stack traces, and verbose errors in production
- Set security headers on every response (see below)

**A06 Vulnerable Components**
- Run dependency scanning in CI: `trivy`, `snyk`, or `npm audit` / `govulncheck`
- Pin dependency versions; review changelogs before upgrading
- Automate dependency updates with Dependabot or Renovate

**A07 Authentication Failures**
- Enforce MFA for admin and sensitive accounts
- Implement account lockout after N failed attempts (5–10)
- Use constant-time comparison for tokens to prevent timing attacks

**A08 Software and Data Integrity**
- Verify signatures on third-party artifacts and containers
- Use SBOM in CI pipeline
- Never deserialize untrusted data without schema validation

## Input Validation

- Validate all inputs: type, format, length, range, allowed values
- Reject at the boundary — do not sanitize and continue on clearly invalid input
- Use allowlists, not denylists, for format validation (e.g., email regex)
- Validate file uploads: MIME type, size, filename, scan for malware

```go
// Validate before processing
if len(input.Email) > 254 || !emailRegex.MatchString(input.Email) {
    return nil, ErrInvalidEmail
}
```

## XSS Prevention

- Escape output in templates — use auto-escaping engines (React JSX, Go html/template)
- Set `Content-Security-Policy` header to restrict script sources
- Never inject user content into `innerHTML`, `eval()`, or `document.write()`
- Use `DOMPurify` for any cases where HTML input is accepted

## CSRF Protection

- Use `SameSite=Strict` or `SameSite=Lax` on session cookies
- For APIs: require custom header (e.g., `X-Requested-With`) or validate `Origin`
- For form-based apps: use CSRF tokens (synchronizer token pattern)
- Stateless APIs using `Authorization: Bearer` header are not CSRF-vulnerable

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

- Sign with RS256 (asymmetric) for public-facing tokens; HS256 acceptable for internal
- Set short expiry: 15 minutes for access tokens, 7 days for refresh tokens
- Validate `iss`, `aud`, `exp`, and `nbf` claims on every request
- Never put sensitive data in the JWT payload — it is only base64-encoded, not encrypted
- Implement token rotation on refresh; revoke via short-lived blocklist in Redis

## Session Management

- Generate cryptographically random session IDs (32+ bytes)
- Store sessions server-side (Redis); do not encode sensitive state in cookies
- Invalidate session on logout, privilege change, and password reset
- Set `HttpOnly`, `Secure`, `SameSite` on session cookies

## Secrets Management

- Never hardcode secrets in source code or commit `.env` files
- Use environment variables injected at runtime, or a secrets manager (Vault, AWS Secrets Manager)
- Rotate secrets regularly; automate rotation where possible
- Use separate secrets per environment (dev/staging/prod)
- Audit secret access; alert on anomalous access patterns

```bash
# .gitignore must include
.env
.env.*
*.pem
*.key
credentials.json
```

## Critical Rules

- Fail closed — on error, deny access; do not default to allowing
- Log security events (failed auth, permission denied) but never log passwords or tokens
- Run SAST (CodeQL, semgrep) and DAST (OWASP ZAP) in CI
- Conduct threat modeling before building auth or payment features
- Apply principle of least privilege to all service accounts and DB users
