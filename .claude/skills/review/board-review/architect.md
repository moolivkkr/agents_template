---
skill: board-hat-architect
description: Board review hat — architect. Contracts with one source of truth, ownership boundaries, hand-offs that have a producer and a consumer, ordering, bypass paths, stack and project leakage
version: "1.0"
tags:
  - review
  - board-review
  - architecture
---

# Hat: architect

Follow `protocol.md` in this directory (format, severity, evidence, report-everything). Prefix: `ARCH`.

**Your question:** if every target agent does exactly what its file says, do the pieces fit
together into a system that works? You judge boundaries, contracts and flow, not code style.

## Read

- every target agent in full
- the commands that spawn them (`grep -l <agent> .claude/commands/*.md`)
- the skill packs in their `skill_packs` frontmatter
- the artifacts they hand to each other

## Checklist

1. **One source of truth per contract.** For each shared shape (API envelope, pagination, errors,
   data contracts, verdict or report formats, file names), find every definition across agents and
   packs. More than one incompatible definition is a finding. Name each place and quote them side by
   side.
2. **Ownership.** For each artifact a target writes, check whether another agent also writes it.
   Two writers of one file, or two agents owning one concern (handlers, migrations, a verdict), is a
   finding.
3. **Hand-offs exist.**
   - Every **input** a target reads must have a producer that writes that exact path.
   - Every **output** must have a consumer, or be a deliverable.
   - Check names letter by letter: `<topic>-verdict.json` vs `<topic>.verdict.json` is a broken
     hand-off.
   - Run `bash tests/dependency-graph.test.sh` and read its IO findings, but don't stop there: the
     test only sees frontmatter.
4. **Ordering.** Does each agent run after its inputs exist and before its consumers? Look for
   tests that run before the deploy they test, a reviewer spawned before the code it reviews, or a
   checker that reads a file a later wave writes.
5. **Who waits for whom.**
   - When an agent spawns children, check that it waits for them (foreground, or in one message).
   - When an agent "waits for" something, find what actually delivers it. A watcher that doesn't
     exist is a finding.
6. **Bypass paths.** Find paths that skip the normal agents:
   - candidate or fast modes
   - fix agents spawned with no `subagent_type`
   - `--auto` or `--force` flags
   - hotfix routes

   For each, check whether it still produces the artifacts and checks the normal path does.
7. **Decisions made before work starts.** Cross-cutting choices (auth and session, tenancy layer,
   versioning, envelope) should be `D-NNN` entries in `docs/DECISIONS.md` before the agents that
   depend on them run. Agents that decide them ad hoc can each decide differently.
8. **Stack and project leakage.** Templates and core agents shouldn't hard-code one language,
   framework, project name or path (`src/`, `localhost:3000`, a product name) where the stack
   varies.
9. **Cross-phase compatibility.** When a later phase changes a contract, check what notices that
   earlier consumers broke.

## Defect classes the 2026-09-30 run found (check they're still fixed)

- the API envelope defined eight ways
- `ui_developer/manifest.json` required by two agents and written by none
- browser E2E scheduled before the deploy it needs
- candidate mode replacing every role agent
- debate requests written under a name the gate never globbed
