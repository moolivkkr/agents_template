---
skill: git-workflow
description: Trunk-based branching strategy, conventional commits, PR process, branch naming, commit message format
version: "1.0"
tags:
  - git
  - workflow
  - ci
  - branching
---

# Git Workflow

Trunk-based development with conventional commits for all projects.

## Branching Strategy

- `main` is always deployable — never commit directly to `main`
- Short-lived feature branches off `main`; merge back within 1–2 days
- No long-lived feature branches; use feature flags for incomplete work
- Delete branches immediately after merge

## Branch Naming

```
<type>/<ticket-id>-<short-description>

feat/AUTH-42-oauth-google-login
fix/BUG-17-null-pointer-session-middleware
chore/INFRA-8-upgrade-go-1-22
docs/DOC-3-api-authentication-guide
refactor/CORE-55-extract-payment-service
```

- Use kebab-case for the description
- Include ticket/issue ID when one exists
- Keep descriptions under 50 characters after the prefix

## Conventional Commits

Format: `<type>(<scope>): <subject>`

```
feat(auth): add Google OAuth login
fix(payments): handle null card token on retry
chore(deps): upgrade Go to 1.22
docs(api): add rate limiting examples to README
refactor(user): extract email validation to shared package
test(orders): add integration tests for refund flow
perf(query): add composite index on orders(user_id, created_at)
ci(github): cache Go modules in workflow
```

### Types

| Type | When to use |
|------|-------------|
| `feat` | New feature for the user |
| `fix` | Bug fix for the user |
| `chore` | Maintenance, tooling, dependency updates |
| `docs` | Documentation only |
| `refactor` | Code change that is neither a fix nor a feature |
| `test` | Adding or updating tests |
| `perf` | Performance improvement |
| `ci` | CI/CD pipeline changes |
| `style` | Formatting, whitespace (no logic change) |
| `revert` | Reverting a previous commit |

### Subject Rules

- Use imperative mood: "add feature" not "added feature"
- No period at end
- 72 characters max
- Lowercase after the colon
- Reference issue/ticket: `fix(auth): handle expired JWT (#142)`

### Commit Body (when needed)

```
feat(billing): implement subscription proration

Calculate prorated charges when users upgrade mid-cycle.
Uses Stripe's proration API to credit unused days before
charging the new plan amount.

Closes #87
```

## Pull Request Process

- PR title must follow conventional commit format
- PR description: what changed, why, how to test, screenshots if UI
- Minimum 1 reviewer approval before merge; 2 for security-sensitive changes
- No self-merge — always get a review
- All CI checks must pass: lint, test, build
- Squash merge for feature branches to keep `main` history clean
- Rebase merge for chores/fixes if commit history is meaningful

## PR Description Template

```markdown
## What
Brief description of the change.

## Why
Context for why this change is needed.

## How to Test
1. Step one
2. Step two

## Checklist
- [ ] Tests added/updated
- [ ] Docs updated if needed
- [ ] No secrets or credentials in code
```

## Tags and Releases

- Tag releases on `main`: `v1.2.3` following semver
- MAJOR: breaking API change
- MINOR: new backward-compatible feature
- PATCH: backward-compatible bug fix
- Generate changelog from conventional commit history

## Critical Rules

- Never force-push to `main` or shared branches
- Never commit secrets, credentials, or `.env` files
- Run `git pull --rebase origin main` before opening a PR
- One logical change per commit — split unrelated changes
- If a branch is stale (>5 days), rebase on `main` before review
