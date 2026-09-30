# Secure coding — rules for the agents that WRITE code

Loaded by `api_developer`, `backend_developer`, `database_agent`, `migration_agent`, `ui_developer`
and `mobile_developer`. `security_reviewer` checks the same list afterwards, so write to it the first
time. Each rule names the test that proves it (the abuse-case matrix in
`testing/test-case-generation.md`).

Baseline references: OWASP Top 10:2025, OWASP ASVS 5.0, and the OWASP API Security Top 10. The
project's own threat model (`docs/design/phases/N/threat_model.md`) adds mitigations and `TC-SEC-*` IDs
that are **in scope for the phase**. Implement them, don't just note them.

## 1. Access control (the #1 class of real vulnerabilities)

- **Deny by default.** Every route is authenticated unless the spec marks it public, and the auth
  middleware is on the router, not remembered per handler.
- **Object-level authorization on every ID the client sends,** from the path, query, body or
  headers. Load the record *scoped by the caller* (`WHERE id = $1 AND tenant_id = $2 AND owner_id =
  $3` where ownership applies), and return **404** when it isn't theirs (see the envelope).
  - Tenant scoping alone is not enough: same-tenant users must not read or edit each other's records
    unless the spec says so.
- **Function-level authorization:** role/permission checks on every privileged operation, enforced
  on the server. Hiding a UI button is not a control.
- **Mass assignment:** decode request bodies into explicit input DTOs listing the writable fields.
  Never bind a request onto a DB model. `role`, `tenant_id`, `owner_id`, `is_admin`, prices and
  status transitions are never client-writable unless the spec says so.
- **Proof:** abuse-matrix rows `AUTHZ-OBJ` (other user's ID → 404), `AUTHZ-TENANT` (other tenant's ID
  → 404), `AUTHZ-FN` (lower role → 403), `MASS-ASSIGN` (extra privileged field → ignored or 400).

## 2. Input and injection

- **Validate at the boundary** against a schema: type, length, range, format, enum and allowlist.
  Reject, don't "clean up".
- **SQL:** parameterized queries or the query builder only. Never build SQL with string
  concatenation or format strings, including `ORDER BY` / column names. Map a sort key to an
  allowlisted column.
- **OS commands:** avoid them. If unavoidable, use exec with an argument array, never a shell
  string, and never pass user input as a flag.
- **Templates:** use the framework's auto-escaping, and never compile a template from user input.
- **Paths:** join them to a fixed base directory, clean, and verify the result is still under the
  base. Reject `..`, absolute paths and NUL bytes.
- **SSRF:** outbound requests to user-supplied URLs go through an allowlist of hosts. Resolve and
  block private, loopback, link-local and metadata addresses (`169.254.169.254`, `fd00::/8`, …) after
  DNS resolution, and disable redirects or re-check each hop.
- **Deserialization:** use JSON only, into typed structs, with size limits. No native object
  deserialization (pickle, Java serialization, YAML with tags).
- **File upload:** size limit, content-type sniffing plus an extension allowlist, stored outside the
  web root with a generated name, and never executed.
- **Proof:** `INJ` rows (SQL/command/path payloads → 400 or inert), `SSRF` (metadata IP → rejected),
  `UPLOAD` (oversized or wrong type → 400/413).

## 3. Authentication, sessions and tokens

- **Passwords:** argon2id (or bcrypt cost ≥ 12) via the standard library or a vetted package. Never
  write your own crypto or comparison; use constant-time compare for secrets.
- **Web clients:**
  - Keep session tokens in an **httpOnly, Secure, SameSite=Lax/Strict cookie**, or in memory only.
    **Never in `localStorage`/`sessionStorage`**, never in URLs or query strings, never in logs.
  - With cookie auth, protect state-changing requests with SameSite plus a CSRF token (or a custom
    header the server requires).
- **WebSockets:** authenticate with a short-lived, single-use ticket fetched over an authenticated
  request, or with the session cookie. Never put a bearer token in the WS URL.
- **Mobile clients:** tokens live in Keychain (iOS) / Keystore-backed storage (Android) via the
  platform's secure-storage module. Never in AsyncStorage, never in the JS bundle.
- **Token validation:** verify signature, `exp`, `nbf`, issuer and audience, and pin the algorithm
  (reject `none` and algorithm switching). Rotate refresh tokens, and revoke on logout and password
  change.
- **Rate limits:** apply them to login, password reset, OTP and any expensive or enumerable endpoint,
  returning 429 with `Retry-After`.
- **Proof:** `TOKEN-TAMPER` (modified signature → 401), `TOKEN-EXPIRED` → 401, `RATE-LIMIT` (N+1th
  attempt → 429), `SESSION-STORAGE` (UI test: no token in localStorage).

## 4. Output, browser and headers

- **XSS:** render text through the framework's escaping. The full UI rules (sinks, URL schemes,
  markdown, redirects, postMessage) and the test are in `~/.claude/skills/ui/secure-rendering.md`.
  - `dangerouslySetInnerHTML` / `v-html` / `[innerHTML]` / `bypassSecurityTrust*` only on HTML
    sanitized with a maintained sanitizer (DOMPurify), and each use is commented with the reason.
  - Never build URLs for `href`/`src` from user input without allowing only `https:`/`mailto:` schemes.
- **Headers:** a strict CSP (no `unsafe-inline` for scripts), `X-Content-Type-Options: nosniff`,
  `Referrer-Policy`, and `frame-ancestors`/`X-Frame-Options`.
- **CORS:** explicit origins from config. Never `*` with credentials, and never reflect the request
  origin.
- **Proof:** `XSS-RENDER` (UI/e2e: a stored `<img src=x onerror=…>` renders as text, no script runs),
  `CORS` (a foreign origin gets no ACAO header).

## 5. Errors, logging and secrets

- **Error bodies** follow the envelope: a user-safe message plus `request_id`. No stack traces, SQL,
  paths or upstream errors.
- **Logs** are structured, carry `request_id`/`trace_id`, and never contain passwords, tokens,
  session IDs, full card or bank numbers, or secrets. Redact by field name at the logger, not per
  call site.
- **Secrets** come from the environment or a secret store at startup.
  - **No default secrets compiled into code, and no fallback values.**
  - If a required secret is missing, the service refuses to start **unless `APP_ENV` is exactly
    `local`, `dev` or `test`**. Fail closed for every other value, including unset, `qa`, `staging`,
    `prod`, `prd` and `production`.
- **Dependencies:** add only what the task needs.
  - Before adding a new package, run `python3 ~/.claude/hooks/vet-package.py -e <npm|pypi|go|crates>
    <name>` (in the framework repo: `.claude/guard/vet-package.py`) and add the package only if it
    exits 0; if it fails or can't reach the registry, use the well-known package it names or record
    the name, the vet output and your reason under `new_dependencies[]` in your manifest for the
    reviewer, and don't install it.
  - Pin it via the lockfile. Install with lifecycle scripts disabled where the ecosystem allows
    (`npm ci --ignore-scripts`, `pnpm install --ignore-scripts`, `pip install --only-binary=:all:`
    where wheels exist), then run the needed build steps explicitly.
- **Proof:** `ERR-LEAK` (forced 500 → body has no stack or SQL), `SECRET-FAILCLOSED` (start with
  `APP_ENV=qa` and no secret → exits non-zero).

## 6. Timeouts and resource limits (security *and* reliability)

- Every inbound request, outbound call and DB query has a timeout. Request bodies have a size limit.
  Pagination has a maximum `limit`.
- Unbounded loops over user-controlled counts, regex on user input with nested quantifiers (ReDoS),
  and decompressing user input without a size cap are all denial-of-service bugs.

## When a rule can't apply

Write the reason in your progress file under **Security deviations**, naming the rule number.
`security_reviewer` treats an undocumented deviation as a finding.
