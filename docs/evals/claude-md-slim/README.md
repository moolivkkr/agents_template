# A slim CLAUDE.md: A/B token measurement (rera, 2026-10-01)

**Result.** Median total tokens per question fell by 44% (120,830 → 67,346), and median cost per question fell
from $0.206 to $0.091. Accuracy went from 0.99 to 0.96: arm B gave 3 partial answers to arm A's 1, and neither
arm gave a wrong answer.

The harness's pre-set rule is "keep only if tokens drop ≥ 20% **and** accuracy does not drop". On accuracy alone,
that rule prints `VERDICT: DISABLE` (last line of `report.md`). The project kept the slim CLAUDE.md anyway, and
fixed the cause of the q15 partials with a one-line pointer (see "Follow-up").

## Method

- **Project:** rera (built with this framework).
  - Arm A: commit `3cfbcca`, with a 62,406-byte CLAUDE.md.
  - Arm B: branch `claude-md-slim` at `5f6e9e6`, with a 12,720-byte CLAUDE.md. The runbooks moved verbatim
    into ten `docs/ops/*.md` files, and CLAUDE.md gained an index saying when to read each one. In rera this
    is commit `20607d0`.
  - Everything else in the two throwaway clones was identical.
- **Questions:** 28, in `questions-rera.json`.
  - q01–q21 come from the graph-find eval (`../graph-find/`).
  - o01–o07 are ops questions. Their answer keys were written from the original CLAUDE.md before any run.
- **Runs:** 76 in all, 38 per arm (ops questions and q14/q15/q21 twice per arm, the rest once).
  - Each run was a fresh, unpersisted, read-only `claude -p` session, with A and B interleaved per question.
  - Model: `claude-opus-5-5`.
  - Harness: `scripts/eval-question-tokens.py run`. The flags and token accounting are in the script's header
    and in `../graph-find/README.md` § Method.
- **Grading:** blind, from `eval-question-tokens.py sheet`. Grades are in `grades.json`, against the pre-written
  keys.
- **Total tokens** = input + cache read + cache creation + output, summed over every model in the run.

## Results

Full per-question table: `report.md`.

| Question kind | Median Δ tokens (B vs A) | n |
|---|---|---|
| status | −65% | 2 |
| fact | −57% | 1 |
| requirement | −55% | 3 |
| decision | −47% | 4 |
| ops | −47% | 7 |
| code-open | −44% | 3 |
| test-coverage | −42% | 3 |
| cross-cutting | −38% | 2 |
| endpoint | −33% | 3 |

The only question that got worse is o05, at +19%: arm B took a median of 6.5 steps against arm A's 3.

## Why

Each API step re-reads the fixed context: CLAUDE.md, the system prompt and the tools, mostly as cache reads. The
median number of steps was the same in both arms (3). So cutting about 50 KB from CLAUDE.md cut the cost of every
step, and that saving is what shows up in the totals.

## Follow-up

The two q15 partial answers in arm B came from a phase-gate row that no longer pointed at the manifest's blocker
list. rera fixed this in commit `15658c6`. Two re-runs of q15 on arm B used 71,031 and 71,091 tokens, and both
named the blockers listed in the manifest. Those re-runs were not graded into `report.md`.

## Limitations

- One project, one question set, one grader: the LLM that ran the eval, blind to the arm but not independent.
- The raw transcripts (`runs.jsonl`, per-run stream-json) are not committed: they hold full answers about the
  project. They lived in a scratch directory on the machine that ran the eval.
