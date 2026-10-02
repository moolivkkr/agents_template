# sdlc-graph: the project graph and TC gate

`.claude/hooks/sdlc-graph.py` builds a graph of each project from the files the pipeline already writes:

- the BRD, PHASE_PLAN, specs, wireframes and contracts
- migrations, source code and tests
- rosters, execution logs and reports
- DECISIONS.md and PROJECT_FACTS.md

The graph is built by scripts, never by an LLM. It is stored in **SQLite** at `agent_state/graph/graph.sqlite`, with
a deterministic `graph.jsonl` export and an **FTS5** full-text index. It uses only the Python 3.9+ standard
library. Agents use it to load only the spec sections and code spans their job needs. The phase gate uses it to
compute the TC inventory. Full command reference: `python3 .claude/hooks/sdlc-graph.py --help`.

## Requirements

- `python3` 3.9 or newer on `PATH`. The hooks run as `python3 .claude/hooks/…`. macOS `/usr/bin/python3` 3.9 works.
- The `sqlite3` module, plus `fcntl` (POSIX: macOS or Linux).
- FTS5 in that sqlite. This is recommended, not required: without it the graph still builds and every pipeline
  command works. Only the interactive `find` ranks with LIKE instead of bm25.

`scripts/graph-preflight.sh` checks all of this and prints one line, for example
`graph preflight: OK — python 3.9.6 (…), sqlite 3.54.0, FTS5 yes`.

## Install and update

| Situation | What to run | What happens |
|---|---|---|
| Framework install / update | `bash install.sh` | Runs the preflight. On a FAIL it warns loudly and installs anyway. Stages the hooks and `.framework-manifest.json` in `~/.claude/hooks/startup/`, installs the project updater to `~/.claude/scripts/startup/`, and prints an `sdlc-graph:` summary line. |
| New project | `bash new-project.sh my-app ~/development` | Runs the preflight first and exits 3 (creating nothing) on a FAIL. Then scaffolds the project and runs the updater, which also builds the graph. |
| **Existing project** | `~/.claude/scripts/startup/startup-project-update.sh --project ~/development/my-app` | See below. `./install.sh --project <dir> [flags]` does a full install, then the same update. |
| During a run | nothing | `/autonomous` Step 0 runs the updater with `--no-build`. `/develop` Wave 0c runs it with `--hooks-only`. Stale hooks are refreshed, not only missing ones. |

Preview an update first:

```bash
~/.claude/scripts/startup/startup-project-update.sh --project ~/development/my-app --dry-run
```

The updater touches only the paths below, and prints the list of files it changed. It runs no git command that
changes the worktree, so uncommitted work is safe.

| Path | Change |
|---|---|
| `.claude/hooks/<framework file>` | A missing file is added and a stale one is refreshed. Files the project added are never touched or deleted. |
| `.claude/hooks/.framework-manifest.json` | Records the framework version/commit and the sha256 of each framework file as installed. Commit it with the hooks. |
| `.claude/settings.json` | Created if absent. Otherwise **merged**: missing framework hook commands (SessionStart facts injection and reorient, Stop verify-gate and autonomous-continue, PostToolUse manifest check, StopFailure) and missing `env` keys are added. User entries are never removed or changed. Re-running changes nothing. |
| `.gitignore` | `agent_state/graph/` is appended unless something already ignores it. The graph writes its own `agent_state/graph/.gitignore`, but that file does not cover the gate outputs (`tc-gate-phase-N.json`, `summary-phase-N.json`), so the root entry is still needed. |
| `agent_state/graph/` | The initial `sdlc-graph.py build`. The updater prints its timing and node, edge and file counts. |
| `agent_state/config/graph-policy.json` | Written only with `--graph-interactive on\|off`. |

**Locally modified hooks.** A framework hook is "locally modified" when its content matches neither:

- the hash recorded at the last update, nor
- any version the framework ever shipped (the staged manifest lists every version from the repo's git history).

The updater keeps such a hook, prints its diff against the framework version, and exits 1. Re-run with `--force`
to overwrite it. Projects whose hooks were copied before the manifest existed are handled by the same
shipped-versions check.

**Flags:**

- `--dry-run`: report what would change and write nothing.
- `--force`: overwrite locally modified hooks.
- `--hooks-only`: hooks and manifest only.
- `--no-build`: skip the graph build.
- `--graph-interactive on|off`: write the interactive switch.
- `--source DIR` / `--settings FILE`: use a different framework copy.
- `--quiet`: print less.

**Exit codes:**

| Code | Meaning |
|---|---|
| 0 | OK |
| 1 | A locally modified hook was kept |
| 2 | Usage error, unreadable `settings.json`, or nothing staged |
| 3 | Preflight FAIL; nothing was changed |
| 4 | The graph build failed; the files were still updated |

## Pipeline commands and who uses them

| Command | Used by |
|---|---|
| `build [--incremental]` | `/develop` Wave 0c, `/accept`, `/map`. Every query also refreshes the graph incrementally first. |
| `context --agent ROLE --phase N` | Developers, test writers, `code_quality_verifier`, `tenant_isolation_verifier`, `migration_safety_reviewer`, `accessibility_auditor`, `ui_standards_auditor`, `spec_impl_reconciler`: their TC rows and the only spec sections to read |
| `diff-context [--base SHA]` | `code_reviewer_I`/`II`, `security_reviewer`: changed symbols and the endpoints, tables, TCs and FRs they touch |
| `consumers` / `impact` / `trace` / `orphans` | `breaking_change_reviewer`, `code_reviewer_II`, `spec_impl_reconciler` |
| `tc --phase N` | `spec_writer`, `e2e_orchestrator`, Wave 0c (`--spec-only` TC priorities for the results converters) |
| `unlocked --phase N` | `e2e_orchestrator`: the e2e scope |
| `gate --phase N [--tc-only]` | `verify-gate.sh` check (h), `spec_test_reconciler`, Wave 6: the one deterministic TC gate |

## The TC gate and D-002 (warn first)

`gate` applies `tc-inventory.py`'s rules (it imports that file's parser, so the two must be the same version), plus
four stricter checks:

- `range_ids`: range-defined IDs
- `malformed_ids`: malformed ID cells
- `results_required`: results mode required
- `base_sha_required`: a diff base required

Per [D-002](DECISIONS.md), these four are **warnings** until the project enforces them:

```bash
python3 .claude/hooks/sdlc-graph.py warnings --phase N              # what would block under strict, per phase
python3 .claude/hooks/sdlc-graph.py policy                           # show agent_state/config/gate-policy.json
python3 .claude/hooks/sdlc-graph.py policy --strict                  # enforce all four
python3 .claude/hooks/sdlc-graph.py policy --strict-check range_ids  # enforce one
SDLC_TC_GATE=strict python3 .claude/hooks/sdlc-graph.py gate --phase N --summary   # one run
```

## Interactive `find` / `status`: off by default

`find <question>` (alias `ask`) and `status` answer the main session's questions about the project. They ship **OFF**.
We measured them on rera with 21 questions × 2 arms × 2 runs (84 runs) before deciding:

- The pre-set bar was a ≥20% drop in median tokens per question with no loss of accuracy.
- Median tokens rose **31.6%** instead (124,589 → 163,994).
- Accuracy was about the same (0.96 → 0.99).

Details: [docs/evals/graph-find/README.md](evals/graph-find/README.md). While the switch is off, those commands print
one line and exit 5. The pipeline commands are never affected.

To turn it on for one project, use any one of these:

```bash
startup-project-update.sh --project DIR --graph-interactive on
python3 .claude/hooks/sdlc-graph.py interactive on      # writes agent_state/config/graph-policy.json
SDLC_GRAPH_INTERACTIVE=1                                # env var: one run only
```

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `sdlc-graph: GRAPH UNAVAILABLE (…)` (exit 4) | sqlite could not open or write `agent_state/graph/graph.sqlite`: a read-only directory, a full disk, or a corrupt file. Agents fall back to reading specs whole and must say so. To rebuild, delete the generated files (`rm agent_state/graph/graph.sqlite*`), then run `python3 .claude/hooks/sdlc-graph.py build`. |
| `tc-inventory.py must sit beside sdlc-graph.py`, or an import/attribute error | A stale or missing `tc-inventory.py`. Run `startup-project-update.sh --project .`. |
| `graph preflight: FAIL` | `python3` is missing, older than 3.9, or has no sqlite3. On macOS run `xcode-select --install` or `brew install python`. On Linux, install the distro's `python3` package (pyenv builds need the sqlite dev headers). Until it is fixed, `verify-gate.sh` check (h) blocks phase gates. |
| `graph preflight: WARN … FTS5 no` | Only `find` ranking degrades. Use a Python whose sqlite has FTS5 (Homebrew, python.org, the distro's python3). |
| Graph looks stale | `python3 .claude/hooks/sdlc-graph.py build` does a full rebuild. The gate always rebuilds in full anyway. |
| Updater exits 1 | A hook was edited in the project. Read the printed diff, then either keep it, or re-run with `--force`. If the edit is a fix, upstream it to the framework. |
