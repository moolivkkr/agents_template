# Ranked Repo Map Protocol (Personalized-PageRank + Tree-sitter)

Downstream agents currently locate code by re-reading directories or dumping whole files into context.
This wastes tokens and buries the ~5 files that actually matter for a task under dozens that don't.

This protocol adapts **Aider's tree-sitter repo map** (a symbol def→ref graph ranked by
**personalized PageRank**, emitted under a **token budget**) plus **Agentless hierarchical narrowing**
(file → skeleton/signatures → exact lines). The output is a compact, *ranked* list of the most
important files+symbols for the current task — not a full dump.

Language-agnostic: the framework targets Go, TypeScript, Python, Java, and Rust. Symbol extraction
uses a **tool fallback ladder** so the same protocol works regardless of what is installed.

---

## When to Use

| Context | Use site | Personalization bias | Budget |
|---|---|---|---|
| `/map` (persistent knowledge base) | Produces `agent_state/codebase/repo-map.md` | Entry points + high-fan-in files (no task) | Larger (~2K tokens) — grow when nothing is in context |
| `codebase_mapper` (per focus area) | Emits def→ref graph + ranked slice for its focus | Files in the focus area's scope | ~1K per focus |
| Audit / localization (`backend_audit_agent`, `/diagnose`, `/develop` audit) | Task-personalized map to find WHERE a change lands | Spec/audit-scope files + task-mentioned symbols | Small (~1K) — shrink when relevant files already in context |

---

## Part A — Build the def→ref Tag Graph

**Nodes** = files. **Edges** = a symbol *defined* in file A is *referenced* in file B (edge B→A, "B depends on A's definition").
Extract two tag kinds per file: **definitions** (functions, methods, classes, types, exported consts) and
**references** (identifiers used but not defined locally).

### Tool Fallback Ladder (use the highest rung available)

Probe once, cache the choice for the run:

| Rung | Tool | Probe | Gives you |
|---|---|---|---|
| 1 | **tree-sitter** (via `ast-grep` / language `-parse` tooling) | `command -v ast-grep` | Precise defs + refs with line numbers, all 5 languages |
| 2 | **ctags** (`universal-ctags`) | `command -v ctags` | Definitions with `kind` + line; refs approximated via grep |
| 3 | **LSP/compiler index** (`gopls`, `tsc --listFiles`, `pyright`) | per-language probe | Defs + call graph when a toolchain is already present |
| 4 | **Grep heuristics** (always available) | — | Language-specific def regexes + identifier cross-reference |

**Rung 4 def regexes** (the guaranteed-available fallback — Grep is a core tool):

| Language | Definition pattern (extract the NAME) |
|---|---|
| Go | `^func (\([^)]*\) )?([A-Z]\w+)`, `^type (\w+) `, `^var ([A-Z]\w+)` |
| TS/JS | `^export (async )?function (\w+)`, `^export (class\|interface\|type\|const) (\w+)`, `(\w+)\s*\(.*\)\s*\{` (methods) |
| Python | `^\s*def (\w+)`, `^\s*class (\w+)` |
| Java | `(public\|protected)\s+.*\s(\w+)\s*\(`, `(class\|interface\|enum) (\w+)` |
| Rust | `^\s*(pub )?fn (\w+)`, `^\s*(pub )?(struct\|enum\|trait) (\w+)` |

**Building edges at rung 4:** for each extracted definition name, `grep -rl '\b<name>\b'` across source
files (excluding the defining file and dependency/build dirs). Each hit file gets an edge → the defining file.
Skip names shorter than 3 chars and common keywords to control noise.

**Always exclude:** `node_modules/`, `vendor/`, `.git/`, `dist/`, `build/`, `__pycache__/`, `.next/`, `target/`,
generated code (protobuf/swagger output), and binaries. Cap graph construction at a stratified sample for
codebases >500 files (100% of entry points + config; 30% of implementation files, stratified by module).

---

## Part B — Rank with Personalized PageRank

Run PageRank over the tag graph. Instead of uniform restart probability, use a **personalization vector**
that biases rank toward files relevant to the *current* context. This is the core Aider insight: the same
graph produces a *different* map depending on what the task is about.

### Personalization Weights

| Signal | Weight | Source |
|---|---|---|
| File already in context / chat / open in the task | **~50x** | The agent already has it — it and its neighbors are the relevant neighborhood |
| Identifier explicitly named in the task/spec/audit scope | **~10x** | FR-*/TC-* mentions, spec method names, the symbol the user asked about |
| "Well-named" identifier (snake_case/CamelCase, not a `tmp`/`x`/single-char) | **~10x** | Aider heuristic — descriptive names are more likely to be the API surface |
| Changed file (from `git diff`) | **~10x** | Recently touched code is where the task is landing |
| Everything else | **1x** | Baseline |

Build the personalization dict as `{file: sum_of_matched_weights}`, normalize, and pass it as the PageRank
restart distribution. When **no** files are in context (fresh `/map`), fall back to biasing toward high
out-degree entry points and high in-degree (high-fan-in) core files so the map still surfaces the backbone.

### Executing PageRank in this framework

You do not need a graph library. Either:
- **Compute directly:** power-iteration over the adjacency you built (10–20 iterations, damping 0.85,
  add personalization at each restart) — feasible in a short script for the file-count involved; or
- **Approximate deterministically:** score each file as
  `0.5*personalization + 0.3*(in_degree/max_in) + 0.2*(out_degree/max_out)`, then propagate one hop
  (a file inherits a fraction of the score of files that reference it). This is the pragmatic fallback when
  a full iteration isn't warranted. State which method was used in the artifact header.

Rank symbols within a file by how many personalized files reference them (definition centrality), so the
map shows *which* functions/types matter, not just which files.

---

## Part C — Token Budget + Dynamic Resize

The map is emitted under a token cap (`map_tokens`), then **dynamically resized** to the context:

| Situation | Resize rule |
|---|---|
| No relevant files in context yet | **Grow** the budget (up to ~2–4x default) — the agent needs orientation |
| Relevant files already loaded in context | **Shrink** (down toward ~0) — avoid re-describing what the agent has |
| Task is narrow (single symbol/FR) | Shrink — a focused map beats a broad one |
| Task is broad (new phase, whole-subsystem audit) | Grow toward the cap |

**Defaults:** persistent `/map` artifact ≈ 2K tokens; per-focus mapper slice ≈ 1K; audit/localization
map ≈ 1K (shrinking as files enter context).

**Fitting to budget:** emit files in descending rank until the budget is hit. Per file, emit the path,
its rank, and only its top-N ranked symbol *signatures* (skeleton), never bodies. If the highest-ranked
file alone would blow the budget, emit its skeleton only. Drop the long tail — the whole point is that
low-rank files are omitted, not summarized.

### Output Shape (ranked, budgeted)

```
src/services/billing.go        rank 0.128
  func ChargeInvoice(ctx, inv *Invoice) error       ← 7 refs
  func (s *Biller) Refund(id string) error          ← 4 refs
src/handlers/invoice.go        rank 0.091
  func CreateInvoice(w, r)                           ← 3 refs
src/domain/invoice.go          rank 0.077
  type Invoice struct { ... }                        ← 9 refs
… (files below budget omitted: 34)
```

---

## Part D — Hierarchical Narrowing (Agentless) for Localization

The audit/localization use site needs more than "which file" — it needs **where the change lands**.
Narrow in three levels, spending tokens only as confidence increases:

1. **File level** — take the top-ranked files from the task-personalized map (Parts A–C).
2. **Skeleton / signatures** — for each candidate file, emit its class/function *signatures only*
   (the ranked-symbol skeleton, no bodies). Pick the class/function whose signature matches the change.
3. **Exact lines** — Read only the chosen symbol's span to pin the precise insertion/edit lines.

Emit the localization result as `file → class/function → line`, e.g.:

```
FR-014 (add proration to refunds) localizes to:
  src/services/billing.go → (*Biller).Refund → lines 88–121   (confidence: Confirmed)
  src/domain/invoice.go   → Invoice.LineItems → lines 22–29    (confidence: Deduced)
```

This keeps localization cheap: file-level ranking prunes the search, skeletons confirm the target
without reading bodies, and only the final span is read in full.

---

## Integration Notes

- `/map` writes the ranked map as a persistent artifact (`agent_state/codebase/repo-map.md`) alongside the
  focus documents, and records the tool rung used + method (iteration vs approximation) in the header so
  downstream agents know the confidence.
- `codebase_mapper` emits the def→ref graph and a ranked slice for its focus area (see its Required Reading).
- Audit/localization consumers (`backend_audit_agent`, `/diagnose`, the `/develop` audit step) load the
  persistent map, re-run Part B with a **task-personalized** vector (spec/audit-scope files + task-mentioned
  symbols weighted up), then apply Part D. They must **shrink** the map as they pull real files into context.
- Grade findings with the same Evidence/Localization grading the consumer already uses (Confirmed requires
  file:line; Deduced shows the reference chain; Inferred/Hypothesized states what would confirm it).
```
