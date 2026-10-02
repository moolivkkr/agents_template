# sdlc-graph `find` / `status` for main-session questions: A/B token measurement

**Decision: the capability ships OFF by default.** The bar was set before measuring: keep it on only if the median
total tokens per question drop by at least 20% and accuracy does not drop. Instead, the median rose by 31.6%
(124,589 → 163,994 tokens per question). Accuracy was about the same (0.96 → 0.99). The code stays in place behind
`agent_state/config/graph-policy.json` `{"interactive": true}` or `SDLC_GRAPH_INTERACTIVE=1`.

## Method

- **Project:** a throwaway `git clone --local` of rera at `b25dfb9`, under `/tmp/graph-eval/`. Its CLAUDE.md is 62 KB
  and its PROJECT_FACTS.md is 35 KB. The graph index has 2,399 files, 42k nodes and 40k find rows, and builds in 9 s.
- **Arms:**
  - A: `graph-policy.json` set to `interactive:false`, with the rera CLAUDE.md unchanged.
  - B: `interactive:true`, plus the template's "Asking about this project" block (the version that was on before this
    decision) added under the H1.
  - Everything else was byte-identical, including the built graph.
- **Model and runs:**
  - Model `claude-opus-5-5`, the `claude -p` default, with Claude Code 2.1.285. A `claude-haiku-4-5` helper call
    appears in every run and is counted.
  - 21 questions × 2 arms × 2 reps = 84 runs. Each run was a fresh, unpersisted session, and A and B ran
    interleaved for each question.
- **Read-only harness** (`scripts/eval-question-tokens.py`): flags
  `--tools Read,Grep,Glob,Bash --allowedTools Read Grep Glob "Bash(python3 .claude/hooks/sdlc-graph.py *)"
  --permission-mode dontAsk --permission-prompts none --setting-sources project --no-session-persistence
  --max-budget-usd 1.5`, with `CLAUDE_CODE_PROMPT_CACHE_TTL=5m`. The TTL setting affects cost only.
  - The flags were checked against https://code.claude.com/docs/en/cli-reference,
    https://code.claude.com/docs/en/headless and https://code.claude.com/docs/en/permission-modes.
  - The usage fields were checked against https://code.claude.com/docs/en/agent-sdk/cost-tracking. Totals come from
    the result message's `modelUsage`, summed over all models: input + cache read + cache creation + output. API
    steps are counted as distinct main-loop message ids.
- **Grading:**
  - Each question's answer key was derived from the files using grep/sed and the graph, then checked by hand, and was
    written before any run.
  - `sheet` shuffled the 84 answers and hid the arm and the tool name. Grading followed the pre-set rule per question.
  - Two keys were corrected while grading, and both corrections are recorded in `questions-rera.json`:
    - q07: the first key missed TC-NORM-030..034, which the test file names but no spec defines.
    - q05: the 133 count excludes malformed IDs. Answers counting 147–152 got "partial" under the pre-set ±10% rule.
      Under a lenient key all four would be correct, which would favour neither arm (3 of those 4 were arm A).
- **Spend:** $20.21 for the 84 runs plus $0.73 for 2 setup probes, $20.94 in total against a $25 cap.

## Results

Full table: `report.md`. Raw records: `runs.jsonl`. Grades and the blind map: `grades.json`, `grading-map.json`.

| arm | median tokens/question | mean | median $ | total $ | median API steps | median tool calls | median wall s | accuracy |
|---|---|---|---|---|---|---|---|---|
| A (explore) | 124,589 | 166,683 | 0.217 | 9.92 | 3 | 3 | 15.2 | 0.96 (39 c / 3 p) |
| B (find/status) | 163,994 | 193,088 | 0.230 | 10.29 | 4 | 4 | 18.7 | 0.99 (41 c / 1 p) |

**Change in median tokens by question kind (B vs A):**

| Kind | Change | Questions |
|---|---|---|
| status | -3% | q14 "which phases passed / current phase" -49%; q15 "why isn't phase 7 gated" +44% |
| test-coverage | -1% | q06 -18%; q05 -1%; q07 +35% |
| code-open | 0% | q20 -20%; q18 0%; q19 +57% |
| endpoint | +2% | n=3 |
| decision | +15% | n=4 |
| requirement | +33% | n=3 |
| fact | +39% | n=1 |
| cross-cutting | +43% | n=2 |

The fixed context the runs did not load (user-level agents, commands and hooks, about 21.7k tokens per step) is
modelled in `report-overhead21700.md`. With it added, the result is the same: +32.2%.

## Why it did not save tokens

- **Each API step re-reads about 35–40k tokens of fixed context** (rera's CLAUDE.md, the system prompt and tools),
  mostly as cache reads. The total therefore tracks the number of steps, not how much text the model reads.
- **Arm A answered in a median of 3 steps.** rera's CLAUDE.md already maps the project, and Grep plus one Read finds
  most answers.
- **Arm B added a step:** the `find` call. Its output is about 1.5–2k tokens. The model then still opened or grepped
  the spans to verify them before answering, so the call replaced little.
- **The graph won only where one call fully answers the question:**
  - q14 "where are we": `status` alone, 2 steps instead of 4.
  - q06 "which test covers TC-x".
  - q20, a broad code question, where a ranked span list cut the search.

## Limitations

- **Sample size:** one project, 21 questions, 2 reps. Run-to-run variance within an arm was up to ±25% on some
  questions (q05, q09, q15, q18, q20), but the aggregate gap (+32%) is well outside it.
- **Context sensitivity:** rera has an unusually rich CLAUDE.md. A project with a thin CLAUDE.md may explore more and
  benefit more. Not measured.
- **Grader:** grading was done by one LLM grader (the agent that built the feature), blind to the arm but not
  independent.
- **Guidance wording:** only one wording of the guidance was tested. A "use `status` for where-are-we questions only"
  variant may pass on its own: q14 saved 49%. But n=2 for status, and q15 got worse, so it was not enabled.
