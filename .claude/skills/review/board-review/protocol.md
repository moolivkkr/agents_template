---
skill: board-review-protocol
description: How a /board-review runs and what every hat and verifier writes — findings format, severity and type, evidence rules, report-everything, blind verification, scoring from verified findings
version: "1.0"
tags:
  - review
  - board-review
  - agents
  - verification
---

# Board review protocol

A board review checks a group of agents through several professional lenses ("hats"), then has
independent verifiers try to refute what the hats found. `/board-review` runs it; `board-review.py`
validates, blinds, merges and scores it. The first review (2026-09-30, `docs/AGENT_BOARD_REVIEW_2026-09-30.md`)
found real problems but couldn't be re-run, because its checklists, prompts and formats weren't
saved (`docs/DEBATE_AND_BOARD_REVIEW_2026-09-30.md`, B1–B6). This file and the hat files are that
saved form.

## Rules for every hat

1. **Read-only.** Don't edit anything outside your output files in the run directory. Reproduce
   runtime claims in a scratch directory, never in the repo.
2. **Report everything you find, each with its severity.** Don't filter to "only the important
   ones" and don't be conservative. Severity filtering happens later, in verification and merge.
   Asking a reviewer to report only high-severity issues makes it report less (Anthropic's guidance
   for Opus 5 review prompts), and a MEDIUM you leave out can't be promoted by a verifier who
   reproduces it.
3. **Cite every finding** as `file` + `line` you read in this session, plus a short quote or the
   command and its output. `board-review.py validate` rejects a citation whose file doesn't exist or
   whose line is past the end of the file.
4. **Cover every target.** Each target agent gets a `coverage` entry saying you read it, with one
   line on what you looked at. A target with no coverage entry gets no score, rather than a clean 5.
5. **Stay in your lens.** Things outside it go under "For other hats" in your markdown report, not in
   your findings.
6. **Claims about tools, vendors and versions** need a source checked in this session (WebSearch or
   WebFetch, or a command you ran). Otherwise mark them `[unverified]` in the evidence.
7. **Finish in this run.** Your final message's first line is `COMPLETE`, `PARTIAL` or `BLOCKED`. A
   progress note isn't a result; the orchestrator re-spawns you if you return one.

## Severity (pick by consequence, not by how sure you are)

| Severity | Meaning |
|---|---|
| CRITICAL | Following the instruction ships a defect, an exploitable hole or data loss, or lets the gate pass broken work, with no human in the loop to catch it |
| HIGH | A likely failure in normal use: a wrong instruction, a missing step the pipeline depends on, or a check that exists but doesn't enforce |
| MEDIUM | A real gap with a workaround, or one that fails only in some stacks, projects or situations |
| LOW | Clarity, consistency or maintainability; no behaviour changes |

## Type

- **a — wrong instruction:** the text tells the agent to do the wrong thing.
- **b — missing:** something the agent needs isn't there.
- **c — present but unenforced:** the rule exists, but nothing makes it happen or checks it.

Combine them with `+` (`a+c`) when both apply.

## Files a hat writes (in the run directory, `docs/board-review-<date>-<group>/`)

**`hats/<hat>.json`, format `sdlc.board-findings/v1`:**

```json
{
  "schema": "sdlc.board-findings/v1",
  "hat": "architect",
  "run": "2026-10-01-debate",
  "targets": ["debate_moderator", "debate_arbitrator"],
  "coverage": [
    { "agent": "debate_moderator", "note": "read in full; checked spawns, hand-off, verdict ownership" }
  ],
  "findings": [
    {
      "id": "ARCH-01",
      "severity": "HIGH",
      "type": "a",
      "agents": ["debate_moderator"],
      "file": ".claude/agents/core/debate_moderator.md",
      "line": 66,
      "evidence": "\"Spawn researchers (PARALLEL)… Wait for ALL\" — Agent calls default to background",
      "problem": "the failure scenario, concretely: what happens, to whom, when",
      "fix": "the smallest change that removes it"
    }
  ]
}
```

- `id` prefix by hat:

  | Hat | Prefix |
  |---|---|
  | architect | `ARCH` |
  | senior_dev | `DEV` |
  | tester | `TEST` |
  | sre | `SRE` |
  | devops | `OPS` |
  | security | `SEC` |
  | ai_engineer | `AI` |

- Numbers are sequential (`-01`, `-02`, …).
- `file` is relative to the repo root.

**`hats/<hat>.md`, the narrative:**
1. **Verdict:** your top five problems, most important first.
2. **Missing entirely:** what's absent, and where you looked for it.
3. **For other hats.**

The findings table lives in the JSON, so don't repeat it here.

## Verification (blind)

`board-review.py select` builds each verifier's input:
- every CRITICAL and HIGH finding
- a deterministic sample of MEDIUM and LOW (at least 3 per hat, or 25%)

It **removes the hat's severity** and shuffles the order. A verifier who reads "HIGH" before checking
the claim is anchored to it (review B4), and including some MEDIUM/LOW means a hat that under-rated
something gets caught.

Verifiers run on a different model from the hats (`model: fable`). That way they don't share the
reviewers' blind spots (`model-routing.md`, review B3). They write `verify/<verifier>.json`, format
`sdlc.board-verification/v1`:

```json
{
  "schema": "sdlc.board-verification/v1",
  "verifier": "V1",
  "model": "fable",
  "hats": ["security", "architect"],
  "verdicts": [
    { "id": "SEC-01", "verdict": "confirmed", "severity": "HIGH",
      "reproduction": "what you opened or ran, and what it showed",
      "note": "why, especially when you narrowed or refuted it", "duplicate_of": null }
  ]
}
```

| verdict | Meaning |
|---|---|
| `confirmed` | the claim holds as stated |
| `narrowed` | it holds in a smaller scope or for fewer cases than claimed. Say which |
| `refuted` | the citation doesn't say that, or the reproduction shows the claim is false |
| `unverifiable` | it can't be checked here (needs a cluster, a vendor account…). Say what would check it |

`severity` is **your own rating**, made from the evidence before you know the hat's. `duplicate_of`
names another finding's id when two hats found the same thing.

## Merge and scores

`board-review.py merge` writes `merged.json` and `scorecard.md`:

- **Final severity:**
  - `confirmed` or `narrowed`: the verifier's severity
  - `refuted`: dropped (listed separately)
  - `unverifiable` or not sampled: the hat's severity, marked unverified
- **Duplicates** fold into their target.
- **The merge fails** if any CRITICAL or HIGH finding has no verdict.
- **Score per agent per hat:** the agent's worst final finding under that hat, using the scale below.
  It's derived, not judged, so two runs are comparable and a hat can't anchor its own scores. An
  agent missing from a hat's coverage has no score.

  | Worst final finding | Score |
  |---|---|
  | CRITICAL | 1 |
  | HIGH | 2 |
  | MEDIUM | 3 |
  | LOW | 4 |
  | none | 5 ("would ship as-is") |

- **Verifier statistics:** confirmed, narrowed, refuted and unverifiable counts, plus severity moved
  up or down. A verifier that changed nothing across 10 or more findings is flagged: it may not have
  tried to refute anything.

`board-review.py compare <before>/merged.json <after>/merged.json` shows each agent's score movement.
This is how you show that a fix round actually helped.
