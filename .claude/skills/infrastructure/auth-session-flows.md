---
skill: auth-session-flows
description: Auth session flows — OAuth2/OIDC (auth-code + PKCE), session vs JWT, refresh-token rotation, token storage, logout/revocation
version: "1.0"
tags:
  - auth
  - oauth2
  - oidc
  - jwt
  - sessions
  - pkce
  - infrastructure
---

# Auth session flows — protocol-level authentication and session lifecycle.

This is the **protocol and lifecycle** layer: which OAuth2/OIDC flow, session vs JWT, how tokens are
stored, refreshed, and revoked. It complements the code-level archetypes (`core/security-owasp.md`,
`backend/archetypes/auth-middleware-{lang}.md` for JWT verification middleware) — read those for the
in-request validation code; read this for the flow design.

## Pick the right OAuth2 flow
| Client type | Flow | Why |
|-------------|------|-----|
| SPA / browser JS | **Authorization Code + PKCE** | No client secret can be kept in a browser; PKCE binds the code to the initiator |
| Mobile / native | **Authorization Code + PKCE** | Same — public client, custom-scheme redirect |
| Server-side web app | **Authorization Code** (confidential client, with secret) | Secret is safe on the server; PKCE still recommended |
| Machine-to-machine | **Client Credentials** | No user; service authenticates as itself |

**Do NOT use:** Implicit flow (deprecated — leaks tokens in the URL fragment) or Resource Owner Password
Credentials (the app should never see the user's password). Modern default is **Authorization Code + PKCE
for everyone**, secret added only for confidential clients.

### Authorization Code + PKCE (the canonical flow)
```
1. Client generates:  code_verifier (random 43-128 chars)
                       code_challenge = BASE64URL(SHA256(code_verifier))
2. Redirect to /authorize?response_type=code&client_id=...&redirect_uri=...
      &scope=openid profile&state=<csrf>&code_challenge=<c>&code_challenge_method=S256
3. User authenticates + consents at the IdP.
4. IdP redirects back: redirect_uri?code=<auth_code>&state=<csrf>
      → client MUST verify `state` matches what it sent (CSRF defense).
5. Client exchanges at /token:  code + code_verifier + client_id (+ secret if confidential)
6. IdP verifies SHA256(code_verifier) == stored code_challenge, returns:
      access_token, id_token (OIDC), refresh_token, expires_in
```
- `state` is mandatory and single-use — it defeats CSRF on the redirect.
- `code_verifier` never leaves the client until the token exchange — an intercepted `code` is useless
  without it.
- Authorization codes are one-time-use and short-lived (~60s); reuse must be rejected by the IdP.

### OIDC on top of OAuth2
OAuth2 is authorization; **OIDC adds authentication**. Request scope `openid` to get an `id_token` (a JWT
describing *who* the user is: `sub`, `email`, `aud`, `iss`, `exp`, `nonce`). Validate the `id_token`
signature against the IdP's JWKS, and check `iss`, `aud`, `exp`, and `nonce`. Use the `access_token` to
call APIs; use the `id_token` to establish identity. Don't send the `id_token` to your APIs as a bearer.

## Session vs JWT — choose deliberately
| | Server session (opaque cookie) | Stateless JWT |
|--|--|--|
| Revocation | Immediate (delete server record) | Hard — valid until `exp` unless you add a denylist |
| Scale | Needs shared session store (Redis) | No lookup; scales trivially |
| Payload | Opaque id; data server-side | Claims in the token (readable by client) |
| Best for | First-party web apps, admin | APIs, microservices, cross-service auth |

- **Default for a first-party web app: server-side sessions** with an opaque, `HttpOnly` cookie. Simpler,
  instantly revocable, no token-in-JS to steal.
- **Use JWT** for stateless APIs and service-to-service, and keep access tokens **short-lived (5-15 min)**
  so the un-revocability window is small.
- Do not put a long-lived JWT in `localStorage` and call it a session — that's an XSS-exfiltratable bearer.

## Token storage (browser)
- **Access token:** in memory (JS variable / in-memory store). Never `localStorage`/`sessionStorage` —
  any XSS reads it. Short-lived so a page reload re-fetches via refresh.
- **Refresh token:** `HttpOnly; Secure; SameSite=Strict` (or `Lax`) cookie so JS can't read it and CSRF is
  bounded. Never expose the refresh token to JavaScript.
- **Session cookie:** `HttpOnly; Secure; SameSite`, scoped `Path`/`Domain`, plus a CSRF token (double-submit
  or synchronizer) for state-changing requests.
```
Set-Cookie: refresh_token=<opaque-or-jwt>; HttpOnly; Secure; SameSite=Strict; Path=/auth; Max-Age=1209600
Set-Cookie: session=<opaque-id>; HttpOnly; Secure; SameSite=Lax; Path=/
```

## Refresh-token rotation (mandatory for long-lived sessions)
Every refresh **issues a new refresh token and invalidates the old one** (rotation). Detect replay:
```
On /token (grant_type=refresh_token):
  1. Look up token in store. If not found OR already-used → REVOKE the entire token family
     (someone is replaying a stolen token) and force re-auth.
  2. If valid: issue new access_token + new refresh_token, mark old as used, chain family_id.
  3. Refresh tokens have an absolute max lifetime (e.g. 14-30 days) — rotation extends within that ceiling,
     not forever.
```
- Reuse detection is the whole point: a rotated token used twice means it was stolen → nuke the family.
- Bind refresh tokens to a family/session id so one compromised token invalidates the lineage, not all
  the user's sessions.

## Logout & revocation
- **Session:** delete the server-side session record and clear the cookie (`Max-Age=0`). Instant.
- **JWT access token:** can't be un-issued — rely on short TTL, and for immediate kill add a **denylist**
  (jti in Redis with TTL = token's remaining life) checked by middleware.
- **Refresh token:** delete it from the store (and its family) so no new access tokens can be minted.
- **Global sign-out** (all devices): revoke the whole token family / bump a per-user `token_version` claim
  that every access token carries and middleware checks.
- **OIDC:** support RP-initiated logout (`end_session_endpoint`) so the IdP session is also cleared, and
  respect back-channel logout if the IdP sends it.

## Rules
- Authorization Code + PKCE is the default for browser and mobile; never Implicit, never Password grant.
- Access tokens are short-lived (≤15 min); long life lives only in a rotating, revocable refresh token.
- Refresh tokens rotate on every use, with reuse-detection that revokes the whole family on replay.
- Access tokens in memory, refresh/session in `HttpOnly; Secure; SameSite` cookies — never in `localStorage`.
- Always verify `state` (CSRF) on the redirect and `nonce` on the `id_token`.
- Design revocation in from day one — a session you can't kill is a security incident you can't contain.

## Testing note
Test the flow end-to-end against the IdP (or a mock like a local Keycloak / a stubbed `/authorize` +
`/token`): assert (1) a mismatched `state` is rejected, (2) an auth code cannot be exchanged twice, (3) a
rotated refresh token used a second time revokes the family and forces re-auth, (4) an expired access token
is rejected by middleware, and (5) logout invalidates the session/refresh token so subsequent calls 401.
Cover the negative paths — wrong `aud`, expired `id_token`, tampered signature — since those are the actual
attack surface.
