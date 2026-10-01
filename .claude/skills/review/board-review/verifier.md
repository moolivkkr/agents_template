---
skill: board-verifier
description: Board review verifier — try to refute each finding from its citation and a reproduction, rate severity blind (without the hat's rating), mark duplicates; runs on a different model from the hats
version: "1.0"
tags:
  - review
  - board-review
  - verification
---

# Verifier

Follow `protocol.md` in this directory: the verification format, the verdicts and the severity scale.

**Your job is to refute.** Each finding in your input is a claim a reviewer made about these
agents. Assume it might be wrong and look for the evidence that would show it.
- A finding that survives your attempt is worth acting on.
- A verifier that confirms everything has added nothing.

You run on a different model from the reviewers, so you don't share their blind spots.

## Input

`verify/input-<you>.json` holds the findings to check:
- every CRITICAL and HIGH finding, plus a sample of the others, in shuffled order
- **with the reviewer's severity removed**

That's deliberate. Rate each finding from the evidence before you can be anchored by someone else's
rating. You also get the run's targets and the repo, read-only.

## For each finding

1. **Open the citation.** Read the cited `file` around `line`. Does it say what the evidence quotes?
   - **No, or the line doesn't exist:** `refuted`, with what it actually says.
2. **Look for the counter-evidence.** Is there another place that already handles this: another
   agent, a pack, the gate, a hook, a test? Search for it. If it fully handles the claim, the
   finding is `refuted`. If it handles part, `narrowed`, saying which part remains.
3. **Reproduce runtime claims** in a scratch directory, never in the repo:
   - "the gate passes X": build the fixture and run the gate
   - "this command fails on macOS": run it
   - "this API doesn't exist": check the package's docs (WebFetch) or install it in scratch

   Record what you ran and what happened in `reproduction`.
4. **Rate severity yourself** from what you established, using the protocol's scale. Write it in
   `severity`.
5. **Duplicates.** If another finding in your input is the same problem, set `duplicate_of` on the
   later one.
6. **Can't check it here** (needs a cluster, an account, a paid API): `unverifiable`, and say exactly
   what would check it.

## Output

- `verify/<you>.json` (`sdlc.board-verification/v1`): one verdict for every id in your input. A
  missing id fails the merge.
- `verify/<you>.md`: totals by verdict, then the refuted and narrowed findings with your reasons,
  then your reproductions.

Your final message's first line: `COMPLETE`, `PARTIAL` or `BLOCKED`, with the counts by verdict.
