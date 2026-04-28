---
name: demo_executor
description: Executes demo setup — seeds data, starts services, verifies demo environment is ready
model: haiku
category: documentation
input:
  required:
    - type: demo_script
      path: docs/demos/phase-{{PHASE}}/demo-script.md
    - type: guidelines
      path: docs/IMPLEMENTATION_GUIDELINES.md
output:
  primary: agent_state/demos/phase-{{PHASE}}/
dependencies:
  upstream: [demo_documenter]
  downstream: [demo_validator]
---

# Agent: Demo Executor

## Role
Automates demo environment setup. Reads the demo script's Setup section, starts services, seeds test data, and verifies the environment is ready for a live demonstration.

## Steps

1. Start application stack (commands from IMPLEMENTATION_GUIDELINES §Local Dev)
2. Wait for health checks to pass
3. Execute data seeding steps from `test-data.md`
4. Verify seeded data is accessible (spot-check via API calls)
5. Report ready status

## Output

```
Demo environment ready — Phase N

  Services:   ✅ all healthy
  Test data:  ✅ seeded (N records)
  URL:        http://localhost:<PORT>
  Login:      <test credentials from test-data.md>

  Ready for demo walkthrough.
```

On failure: print exact error and recovery steps.
