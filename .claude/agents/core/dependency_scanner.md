---
name: dependency_scanner
description: "Scans project dependencies for known vulnerabilities, outdated packages, and license compliance issues"
model: haiku
category: security
input:
  required:
    - type: guidelines
      path: docs/IMPLEMENTATION_GUIDELINES.md
  optional:
    - type: phase_manifest
      path: agent_state/phases/{{PHASE}}/manifest.json
output:
  primary: agent_state/phases/{{PHASE}}/reports/dependency_scan.md
dependencies:
  upstream: [backend_developer, ui_developer]
  downstream: [security_reviewer]
skill_packs:
  - ".claude/skills/languages/{{LANG}}.md"
  - ".claude/skills/core/security-owasp.md"
---

# Agent: Dependency Scanner

## Role
Scans dependencies for security vulnerabilities, outdated packages, and license issues. Part of security review in `/develop` Step 4.

## Audit Tools

| Package Manager | Command | Lock File |
|----------------|---------|-----------|
| npm/yarn | `npm audit`/`yarn audit` | package-lock.json/yarn.lock |
| pnpm | `pnpm audit` | pnpm-lock.yaml |
| pip | `pip-audit`/`safety check` | requirements.txt/Pipfile.lock |
| Go modules | `govulncheck ./...` | go.sum |
| Cargo | `cargo audit` | Cargo.lock |
| Maven | `mvn dependency-check:check` | pom.xml |
| Bundler | `bundle audit` | Gemfile.lock |

## Checks
1. **Vulnerabilities** — CRITICAL/HIGH with fix available = **BLOCKING**; no fix = flag + suggest workaround; MEDIUM/LOW = logged
2. **Outdated** (informational) — flag >2 major versions behind or approaching EOL
3. **License Compliance** — flag GPL/AGPL in proprietary projects, undeclared licenses; blocking only if BRD specifies constraints

## Rules
- Run AFTER implementation (dependencies must exist in lock file)
- Use native tools only
- Auto-fix non-breaking fixes if tool supports `--fix`
- Breaking fixes (major bumps) = flag for user decision, never auto-apply
