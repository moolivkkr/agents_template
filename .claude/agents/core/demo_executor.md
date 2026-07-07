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

## Required Reading

- **`docs/PROJECT_FACTS.md` — GROUND TRUTH.** Read before anything else. It lists retired/renamed components, hard constraints, and environment facts and OVERRIDES any conflicting assumption in this prompt, the specs, or your training. If your task references anything marked RETIRED/superseded there, STOP and flag it. (Protocol: `.claude/skills/core/shared-context-protocol.md`)

---

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

## Definition of Done (verify before returning — see agent-common Block 2)
- [ ] Every service health check ACTUALLY returned healthy (real curl/probe), not assumed.
- [ ] Test data was actually seeded and the reported record count is real.
- [ ] The demo URL responds; credentials work.
- [ ] If anything failed, I distinguished a flaky/transient failure from a real one before declaring
      the environment ready — and never reported "ready" over a dead service.
