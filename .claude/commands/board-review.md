---
command: board-review
description: Board review of a group of agents — several professional hats review in parallel, verifiers on a different model try to refute every serious finding blind to its severity, then scores and root causes. Re-runnable, so a fix round can show its scores moved.
arguments:
  - name: target
    required: true
    description: "A group (coding-testing, debate, requirements, reconcile, planning, review, ops, all), an agent-file glob (.claude/agents/core/debate_*.md), or a comma list of agent names"
  - name: hats
    required: false
    default: "architect,senior_dev,tester,sre,devops,security,ai_engineer"
    description: "Comma list of hats to run"
  - name: compare
    required: false
    description: "Path to an earlier run's merged.json to show score movement against (default: the latest earlier run of the same target, if any)"
---

# /board-review — review a group of agents through several lenses, then try to refute the findings

The 2026-09-30 board review found real problems in the coding and testing agents, but it couldn't be
re-run: its checklists, prompts and formats weren't saved, every agent ran on one model, and the
verifiers saw each finding's severity before judging it (`docs/DEBATE_AND_BOARD_REVIEW_2026-09-30.md`,
B1–B6). This command is the saved, repeatable form.

- **The checklists** are in `~/.claude/skills/review/board-review/`.
- **The deterministic parts** are in `board-review.py`: resolving targets, checking every citation
  points at a real line, blinding and sampling for verification, merging, scoring and comparing
  runs.

**What it costs:** one agent per hat, plus about one verifier per two hats, plus one synthesis agent.
That's 11 agents with all seven hats. Every hat reads every target, so narrow `--hats` or the target
for a quick look.

**Read-only.** The review changes nothing outside its run directory. Fixing what it finds is a
separate step, after the user has read it.

## Step 0 — Resolve the targets and the run directory

```bash
BR=.claude/hooks/board-review.py; [ -f "$BR" ] || BR="$HOME/.claude/hooks/startup/board-review.py"
python3 "$BR" targets "${ARG_TARGET}" > /tmp/board-targets.json || { cat /tmp/board-targets.json; echo "⛔ unknown agents above"; exit 1; }
SLUG=$(printf '%s' "${ARG_TARGET}" | tr -c 'a-zA-Z0-9-' '-' | sed 's/--*/-/g; s/^-//; s/-$//' | cut -c1-40)
RUN="docs/board-review-$(date +%Y-%m-%d)-${SLUG}"
mkdir -p "$RUN/hats" "$RUN/verify"
git rev-parse --short HEAD > "$RUN/sha"
jq -r '.agents | to_entries[] | "\(.key)\t\(.value)"' /tmp/board-targets.json
jq -r '.context[]' /tmp/board-targets.json
```

If `$RUN` already has files from an earlier run today, add a suffix (`-2`) rather than overwrite it.

## Step 1 — The hats, in parallel, in the foreground

Spawn one `general-purpose` agent per hat in `--hats`. Put all of them in **one message**, each with
**`run_in_background: false`**: they run in parallel, and this turn waits for all of them. Without
that parameter a subagent runs in the background, and this command would merge before the hats
finished.

The checklists:

| Hat | Checklist |
|---|---|
| architect | `~/.claude/skills/review/board-review/architect.md` |
| senior_dev | `~/.claude/skills/review/board-review/senior_dev.md` |
| tester | `~/.claude/skills/review/board-review/tester.md` |
| sre | `~/.claude/skills/review/board-review/sre.md` |
| devops | `~/.claude/skills/review/board-review/devops.md` |
| security | `~/.claude/skills/review/board-review/security.md` |
| ai_engineer | `~/.claude/skills/review/board-review/ai_engineer.md` |

Every hat also follows `~/.claude/skills/review/board-review/protocol.md`.

Hat prompt (fill the brackets):

```
You are the <HAT> reviewer on a board review of these agents. Read your checklist,
~/.claude/skills/review/board-review/<HAT>.md, and the protocol,
~/.claude/skills/review/board-review/protocol.md, first. Follow both.

Run: <RUN>   Repo commit: <sha>
Targets (read each in full):
<agent>  <file>   (one per line, from /tmp/board-targets.json)
Context files (read what your checklist needs):
<context files>

Report every finding you have, each with its severity. Don't filter to the important ones: a
separate verification pass does the filtering. Cite file and line for each. Give every target a
coverage entry.
Write <RUN>/hats/<HAT>.json (sdlc.board-findings/v1) and <RUN>/hats/<HAT>.md (verdict, missing
entirely, for other hats). The repo is read-only: reproduce runtime claims in a scratch
directory. Your final message's first line is COMPLETE, PARTIAL or BLOCKED, with your finding
counts by severity.
```

## Step 2 — Check every hat's return and output

```bash
python3 "$BR" validate "$RUN"/hats/*.json
```

- **The return:** each hat's final message must start with `COMPLETE`, `PARTIAL` or `BLOCKED`, and
  its two files must exist.
- **Progress note instead** ("I'll now…", a plan, an offer to continue): re-spawn that hat in the
  foreground. Give it its original prompt plus `Your previous run ended before finishing (it
  returned: "<first line>"). Files already written: <paths>. Finish in this run.` The current model
  can end a long, multi-part task on a progress note. Don't resume it with SendMessage: a resumed
  agent runs in the background.
- **Validator problems** (a citation past the end of a file, a missing coverage entry, a bad id):
  re-spawn that hat with the validator's output and `Fix exactly these problems in your files;
  change nothing else.`
- **Limit:** at most two re-spawns per hat. After that, record the hat as incomplete in the run's
  README, and leave its findings in, since they're still verified.

## Step 3 — Build the blind verification inputs

```bash
python3 "$BR" select --dir "$RUN"     # writes verify/plan.json and verify/input-V<n>.json
```

Each input holds:
- every CRITICAL and HIGH finding of its hats
- a deterministic sample of their MEDIUM and LOW findings

The severity is **removed** and the order shuffled. A verifier rates each finding from the evidence
before it can be anchored by the hat's rating, and the sample catches a hat that under-rated
something.

## Step 4 — The verifiers, on a different model

For each verifier in `verify/plan.json`, spawn a `general-purpose` agent. Put them all in one
message, each with `run_in_background: false` and **`model: fable`**. Verifying on a different
model from the one that produced the findings avoids sharing its blind spots. This is one of the
uses `~/.claude/skills/core/model-routing.md` sanctions.

```
You are verifier <V> on a board review. Read ~/.claude/skills/review/board-review/verifier.md and
~/.claude/skills/review/board-review/protocol.md first. Follow both.

Run: <RUN>   Repo commit: <sha>
Your input: <RUN>/verify/input-<V>.json (severity removed on purpose: rate each finding yourself).
Targets: <same list as the hats>

Try to refute every finding: open the citation, look for counter-evidence elsewhere, and reproduce
runtime claims in a scratch directory. Write <RUN>/verify/<V>.json (sdlc.board-verification/v1)
with one verdict per input id, and <RUN>/verify/<V>.md. Your final message's first line is
COMPLETE, PARTIAL or BLOCKED, with your counts by verdict.
```

Check the returns as in Step 2, and run `python3 "$BR" validate "$RUN"/verify/V*.json`. A missing
verdict for an input id is a validation problem, and gets re-spawned with the validator's output.

## Step 5 — Merge and score

```bash
python3 "$BR" merge --dir "$RUN"     # merged.json + scorecard.md; exits 2 if a CRITICAL/HIGH has no verdict
```

The scores come from the verified findings, not from the hats' opinions: an agent's score under a
hat is its worst verified finding there. That makes two runs comparable, and it means a refuted
finding stops counting. Read the warnings. A verifier that changed nothing across ten or more
findings may not have tried to refute anything.

## Step 6 — Root causes and the plan

Spawn one `general-purpose` agent in the foreground:

```
Read <RUN>/merged.json, <RUN>/scorecard.md and <RUN>/hats/*.md. Write <RUN>/README.md:
1. Summary: what the board found, in a paragraph, and the scorecard table copied from scorecard.md.
2. Root causes, ranked: group the verified findings that share a cause (most cut across hats).
   For each: what's wrong, the finding ids, the agents, and the fix.
3. Per-agent: the first change for each agent with a score of 2 or lower.
4. What verification changed: refuted findings, severities moved, verifier warnings.
5. Plan: P0 / P1 / P2, each item naming the root cause it removes.
6. Method: hats, verifiers and their model, the commit, the finding counts.
Use merged.json's severities and scores as they are: don't re-rate anything.
```

## Step 7 — Compare with the last run

If `--compare` was given, or an earlier `docs/board-review-*-${SLUG}/merged.json` exists:

```bash
PREV="${ARG_COMPARE:-$(ls -d docs/board-review-*-"${SLUG}"* 2>/dev/null | grep -v "^${RUN}$" | sort | tail -1)/merged.json}"
[ -f "$PREV" ] && python3 "$BR" compare "$PREV" "$RUN/merged.json" | tee -a "$RUN/README.md"
```

## Step 8 — Report

Tell the user:
- the run directory
- the scorecard's lowest five agents
- the top root causes
- how many findings verification refuted or re-rated, and any verifier warning
- the score movement, if Step 7 ran

Offer to implement the plan. Don't start fixing without the go-ahead: the user decides what the
board's findings are worth.
