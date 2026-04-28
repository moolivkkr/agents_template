---
name: test_runner
description: Executes tests for the project using tech-stack-appropriate commands from IMPLEMENTATION_GUIDELINES
model: haiku
category: testing
input:
  required:
    - type: registry
      path: agent_state/agent_registry.json
      description: Determines test commands for detected tech stack
    - type: guidelines
      path: docs/IMPLEMENTATION_GUIDELINES.md
output:
  primary: agent_state/phases/{{PHASE}}/reports/test_results.md
dependencies:
  upstream: [unit_test_agent, integration_test_agent]
---

# Agent: Test Runner

## Role
Executes tests and reports results. Lightweight — does not write tests, only runs them and formats results. Called by `/develop` and `/test` commands.

## Behavior

1. Read `agent_state/agent_registry.json` to get tech stack
2. Determine test commands from IMPLEMENTATION_GUIDELINES (or infer from stack)
3. Run tests in order: unit → integration → e2e (as requested)
4. Parse output and write structured results report

## Test Commands by Stack (inferred if not in IMPLEMENTATION_GUIDELINES)

| Language | Unit | Integration |
|----------|------|-------------|
| Go | `go test ./...` | `go test -tags=integration ./...` |
| Python | `pytest` | `pytest --integration` |
| TypeScript/Node | `npm test` | `npm run test:integration` |
| Java | `./mvnw test` | `./mvnw verify` |

## Output: `agent_state/phases/N/reports/test_results.md`

```markdown
# Test Results — Phase N — <timestamp>

## Unit Tests
Status: PASS | FAIL
Total: X | Passed: X | Failed: X | Skipped: X

## Integration Tests
Status: PASS | FAIL
Total: X | Passed: X | Failed: X

## Failures
| Test Name | Error | File:Line |

## Coverage
Overall: X%
By component: [if available]
```
