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

Trunk-based development with conventional commits.

## Branching

- `main` always deployable — never commit directly
- Short-lived feature branches off `main`; merge within 1-2 days
- No long-lived branches; use feature flags for incomplete work; delete after merge

## Branch Naming

```
<type>/<ticket-id>-<short-description>
feat/AUTH-42-oauth-google-login
fix/BUG-17-null-pointer-session-middleware
```
Kebab-case, include ticket ID, description <50 chars.

## Conventional Commits

Format: `<type>(<scope>): <subject>`

| Type | When |
|------|------|
| `feat` | New feature | `fix` | Bug fix |
| `chore` | Maintenance/deps | `docs` | Documentation |
| `refactor` | Neither fix nor feat | `test` | Tests |
| `perf` | Performance | `ci` | CI/CD |
| `style` | Formatting only | `revert` | Reverting |

**Subject:** imperative mood, no period, 72 chars max, lowercase after colon. Reference issues: `fix(auth): handle expired JWT (#142)`

**Body (when needed):** Explain why, not what. Include `Closes #N`.

## PR Process

- Title = conventional commit format; description: what, why, how to test
- Min 1 reviewer (2 for security); no self-merge; all CI must pass
- Squash merge for features; rebase merge for meaningful history

## Tags & Releases

`v1.2.3` semver: MAJOR=breaking, MINOR=feature, PATCH=fix. Changelog from commit history.

## Critical Rules

- Never force-push main; never commit secrets/.env
- `git pull --rebase origin main` before PR
- One logical change per commit; rebase stale branches (>5 days)
