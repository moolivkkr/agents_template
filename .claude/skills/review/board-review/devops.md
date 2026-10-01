---
skill: board-hat-devops
description: Board review hat — DevOps / platform. Deployable to the target runtime, one commands-and-versions table, environment parity, reproducible and portable runs, CI correctness, artifact promotion, build hygiene
version: "1.0"
tags:
  - review
  - board-review
  - devops
---

# Hat: DevOps / platform

Follow `protocol.md` in this directory (format, severity, evidence, report-everything). Prefix: `OPS`.

**Your question:** can what these agents produce be built, deployed and promoted the same way on
the developer's machine, in CI and on the cluster, and does every run mean the same thing?

## Read

- every target agent
- `IMPLEMENTATION_GUIDELINES` § Commands and versions (the template) and `commands-table.py`
- the k8s and deploy templates
- the CI skill
- `install.sh` and `new-project.sh`, for anything the agents depend on being installed

## Checklist

1. **Runtime contract.** Check that the code agents know what the image must satisfy:
   - entrypoint subcommands
   - health paths
   - a read-only root filesystem
   - memory limits
   - the user it runs as

   If only the deploy agent knows, the code won't fit.
2. **One commands table.** Build, test, lint, migrate and seed commands should come from one table
   that agents, `test_runner`, CI and the gate all read. Versions that differ between local, CI and
   cluster are findings: name each value.
3. **Reproducible runs.**
   - Test caches must be disabled where they hide work.
   - Tools must be pinned, with no network-dependent steps left unpinned.
   - The same command must give the same counts.
4. **Portability.** Recipes must run on macOS (BSD tools) and Linux. Check `sed -i`, `grep -P`,
   `stat`, `date -d`, `timeout`/`gtimeout`.
5. **Environments.** Tests must target the environment the gate certifies, with the URL passed in a
   way the agent can actually read. An `export` in a throwaway shell is lost to the next one.
6. **Promotion.** Artifacts must be promoted by digest, not rebuilt per environment. Evidence must
   name the digest or sha it ran against.
7. **Build hygiene.** Check that `agent_state/` and scratch output are ignored in build contexts and
   that builds aren't tagged dirty by the framework's own files.
8. **Hooks and installation.** Every hook or script an agent calls must be installed where the agent
   looks: `.claude/hooks/` in the project, staged in `~/.claude/hooks/startup/`. A tool an agent
   calls that isn't copied into projects is a finding.

## Defect classes the 2026-09-30 run found (check they're still fixed)

- code that couldn't run on the k8s lab (no `serve|migrate|seed`, wrong health paths)
- Postgres 16 vs 17 and Go 1.22 vs 1.27 drift
- `TEST_DB_URL` vs `DATABASE_URL`
- five base URLs
- `APP_BASE_URL` exported into a lost shell
