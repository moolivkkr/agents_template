---
skill: secrets-management
description: Secrets management — Vault/cloud secret managers, rotation, never-in-env-file, runtime injection, least-privilege, detecting committed secrets
version: "1.0"
tags:
  - secrets
  - vault
  - kms
  - rotation
  - security
  - infrastructure
---

# Secrets management — keep credentials out of code, disk, and git history.

A secret is any value whose disclosure grants access: DB passwords, API keys, signing keys, OAuth client
secrets, tokens, TLS private keys. The governing rule is **secrets never touch source control, never live
in a committed file, and are injected at runtime from a managed store**.

## Storage: use a managed secret store, not files
Order of preference:
1. **Cloud secret manager** — AWS Secrets Manager / SSM Parameter Store (SecureString), GCP Secret
   Manager, Azure Key Vault. Native IAM, audit logging, versioning, rotation hooks.
2. **HashiCorp Vault** — when multi-cloud, dynamic secrets, or transit encryption are needed.
3. **Kubernetes Secrets** — acceptable only with encryption-at-rest enabled (`EncryptionConfiguration`)
   and RBAC scoping; by default they are base64, **not** encrypted. Prefer External Secrets Operator to
   sync from a real manager rather than committing sealed manifests as the source of truth.

```hcl
# Vault: reference, never inline the value
data "vault_generic_secret" "db" {
  path = "secret/data/prod/api/database"
}
# The value is fetched at apply/runtime — the literal never appears in code or state diffs.
```

## Never in an env file (the most common leak)
- A committed `.env` with real values is a breach. `.env*` (except `.env.example` with placeholder values)
  belongs in `.gitignore` in every repo, day one.
- `.env.example` documents the **shape** (`DATABASE_URL=`, `STRIPE_KEY=`) with empty or dummy values only.
- Environment variables are acceptable as the *injection channel* into a process, but the value must
  originate from the secret store at boot — not from a file baked into an image or checked into git.
- Never pass secrets as Docker `--build-arg` or bake them into image layers (they persist in history and
  `docker history`). Use BuildKit `--secret` mounts for build-time, runtime injection for run-time.

## Runtime injection
The process receives secrets at start, from the store, scoped to its identity:
```yaml
# Kubernetes: inject from a manager via External Secrets / CSI driver, not a committed Secret
env:
  - name: DATABASE_PASSWORD
    valueFrom:
      secretKeyRef: { name: api-db, key: password }   # populated by External Secrets Operator
```
```go
// App: read from env (populated at boot) or fetch directly from the manager with the pod's IAM role.
dsn := mustGetSecret(ctx, "prod/api/database")   // AWS/GCP SDK call, uses instance identity — no static key
```
- Fetch on startup; cache in memory only, never write the resolved secret to disk or a log.
- For short-lived / dynamic secrets (Vault DB engine, IAM RDS auth), fetch per-connection so credentials
  are ephemeral and auto-expire.
- Reload on rotation (SIGHUP handler, TTL-based re-fetch, or restart) — see below.

## Rotation
- **Every long-lived secret has a rotation policy** (e.g. 90 days) and an owner. A key that "can't be
  rotated without downtime" is an incident waiting to happen — design for rotation from the start.
- **Dual-secret (grace) rotation** to rotate without downtime: introduce the new secret, make the app
  accept *both* old and new, cut writers to new, then retire the old. Signing keys use a key-id (`kid`) so
  a token signed with the old key still verifies during the overlap window.
- Automate it: Secrets Manager rotation Lambdas, Vault leases, or a scheduled job — manual rotation is
  rotation that never happens.
- Rotate immediately (not on schedule) on any suspected exposure or team-member offboarding.

## Least-privilege
- Each service gets an identity (IAM role, Vault role, service account) that can read **only its own**
  secrets — not a shared "app" credential with `secret/*`.
- Read-only where possible; write access to the secret store is a separate, rarely-granted permission.
- Prefer keyless identity (IAM instance/pod role, OIDC workload identity, IRSA) over a static access key
  stored somewhere — the best secret is the one that doesn't exist.
- Scope blast radius: prod and non-prod secrets live in separate stores/paths with separate IAM.

## Detecting committed secrets
- **Pre-commit hook** with `gitleaks` or `trufflehog` blocks secrets before they land.
- **CI scan** on every PR (`gitleaks detect --source . --redact`) as the backstop for anyone without the hook.
- **Server-side** push protection (GitHub secret scanning + push protection) as the final net.
- If a secret was committed: treat it as **compromised** — rotate/revoke it first, *then* scrub history
  (`git filter-repo` / BFG). Removing it from HEAD is not enough; it lives in the reflog and every clone.

```bash
gitleaks detect --source . --redact           # scan working tree + history
gitleaks protect --staged --redact            # pre-commit: block the staged diff
```

## Rules
- Secrets never enter git — not in code, not in `.env`, not in a Dockerfile, not in Terraform state diffs.
- Everything comes from a managed store at runtime, scoped by a per-service least-privilege identity.
- Every long-lived secret is rotatable and rotated on a schedule; design for dual-secret grace rotation.
- Prefer workload identity over static keys; prefer dynamic/short-lived secrets over long-lived ones.
- A leaked secret is rotated/revoked FIRST, scrubbed from history SECOND — never the reverse.
- Never log a secret, never put it in an error message, never echo it in CI output.

## Testing note
Add a CI job that fails the build on any `gitleaks` finding, and a unit/lint check that asserts no
committed file matches the `.env` pattern (only `.env.example` allowed). Test the app's boot path with the
secret store stubbed to verify it fails **loudly and refuses to start** on a missing secret rather than
falling back to a hardcoded default. For rotation, test that the app accepts both old and new secret during
the overlap window (dual-secret acceptance).
