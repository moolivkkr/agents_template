---
command: docs
description: "Show and set which OPTIONAL documents the pipeline maintains (lean by default: architecture diagrams, ADR files, developer docs, phase sketches, the traceability-matrix file and user stories are off), or generate a fresh, sha-stamped snapshot of one on demand."
arguments:
  - name: what
    required: false
    description: "Generate a snapshot now: architecture | adr | developer. Omit to show the policy."
  - name: enable
    required: false
    description: "Turn an optional document on for this project (a docs-policy key, e.g. adr_files)."
  - name: disable
    required: false
    description: "Turn an optional document off for this project."
  - name: profile
    required: false
    description: "lean (default: only what gates and agents read, plus the regenerated summaries) or full (every optional document)."
---

# /docs — Optional documents: policy and on-demand snapshots

> **Read Tier 0 first.** `docs/PROJECT_FACTS.md` and `docs/DECISIONS.md`.

The pipeline maintains only the documents a gate or an agent reads: `PROJECT_FACTS`, `DECISIONS`,
the BRD (FR IDs + EARS acceptance criteria), `IMPLEMENTATION_GUIDELINES`, each phase's
`PHASE_PLAN`/`phase_context`, the specs with their TC inventory, data-contracts, UI wireframes, and
the committed acceptance tests. Those stay current because the gates depend on them, and `/recon`
reconciles them with the code in both directions.

Everything else is optional narrative. Written once and maintained by hand, it drifts from the code
faster than anyone re-reads it. So by default the pipeline doesn't produce it, and this command gives
you a fresh copy when you want one, stamped with the commit it describes.

## Show the policy (no arguments)

```bash
S=.claude/hooks/docs-policy.py; [ -f "$S" ] || S="$HOME/.claude/hooks/startup/docs-policy.py"
python3 "$S" show
```
Prints each optional document: on/off, where the setting came from, what produces it, and, when a
copy is on disk, **how many code commits have landed since it was last updated**. That count is the
staleness signal. For a document that's off and still on disk, suggest `/docs <what>` to refresh it
or deleting it; don't delete it yourself.

| Key | Lean | Produced by | Output |
|---|---|---|---|
| `architecture_diagrams` | off | `architecture_orchestrator` (c4/sequence/deployment/eagle) | `docs/architecture/` |
| `adr_files` | off | `adr_agent` (off = ledger-only: the decision still goes to `docs/DECISIONS.md`) | `docs/adr/` |
| `developer_docs` | off | `documentation_agent` (/develop Step 6b) | `docs/api/`, `docs/developer-guide.md` |
| `phase_sketches` | off | `/plan` Step 4d | `docs/design/phases/N+1/SKETCH.md` |
| `traceability_matrix_file` | off | `brd_writer` | `docs/traceability-matrix.md` (the live trace is `agent_state/accept/acceptance_map.md`) |
| `user_stories` | off | `product_manager` | `docs/user-stories/` (criteria live on the FR in the BRD) |
| `phase_summary` | on | `/develop` post-gate 4a | `agent_state/phases/N/PHASE_SUMMARY.md` (rebuilt from reports) |
| `worklog` | on | `/worklog` | `docs/WORKLOG.md` (rebuilt from artifacts) |
| `release_notes` | on | `/accept` Step 6 | `docs/RELEASE_NOTES.md` (generated from manifests) |

## Change it

```bash
python3 "$S" set <key> on|off          # --enable=<key> / --disable=<key>
python3 "$S" profile lean|full         # --profile=...; add --reset to drop per-key overrides
```
The setting lives in `agent_state/config/docs-policy.json` (commit it). For one run only:
`SDLC_DOCS=full /develop …`.

## Generate a snapshot now (`/docs <what>`)

Whatever the policy says, a snapshot is written fresh from the current code and starts with
`> Snapshot of <git sha> on <date>. Not maintained by the pipeline; regenerate with /docs <what>.`

| `what` | Spawn | Notes |
|---|---|---|
| `architecture` | `architecture_orchestrator` (subagent_type: architecture_orchestrator) | reads the code map (`agent_state/codebase/`, run `/map --incremental` first if `.last-mapped` is stale), BRD and guidelines; `adr_agent` runs ledger-only unless `adr_files` is on |
| `adr` | `adr_agent` (subagent_type: adr_agent) | writes long-form ADRs for the active `docs/DECISIONS.md` entries that have none |
| `developer` | `documentation_agent` (subagent_type: documentation_agent) | README sections, `docs/api/`, `docs/developer-guide.md` from the code and specs |

Prepend the ground-truth line to each prompt, and tell the agent it is producing a **snapshot**: it
describes the code at `git rev-parse --short HEAD` and must not be cited by specs or gates.
Commit the snapshot on its own: `docs: <what> snapshot at <sha>`.

## Output

```
Docs policy: lean (agent_state/config/docs-policy.json)
  off  architecture_diagrams   on disk: 41 code commits since last update → /docs architecture to refresh
  ...
▶ Next: /docs architecture  (or /docs --enable=adr_files)
```
