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
Automates demo environment setup: starts services, seeds test data, verifies readiness for live demonstration.

## Steps
1. Start application stack (commands from IMPLEMENTATION_GUIDELINES Local Dev)
2. Wait for health checks to pass
3. Execute data seeding from `test-data.md`
4. Verify seeded data accessible via API spot-checks
5. Report ready status or exact error + recovery steps
