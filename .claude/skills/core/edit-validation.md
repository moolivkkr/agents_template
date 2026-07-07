# Edit-Validation Protocol — Reject Malformed Edits Before Writing

> **Read Tier 0 first.** `docs/PROJECT_FACTS.md` (ground-truth invariants) is loaded whole before any
> edit. Honor retired/renamed facts — never "fix" code to reference a component a fact has retired.

Agents propose edits as search/replace blocks or diffs. A malformed edit — a search block that matches
zero times, matches many times, or produces a file that no longer parses — is a silent corruption if
written blindly. Borrowed from SWE-agent's Agentic Computer Interface (ACI): **validate the edit as a
gate, and reject-before-write**. A rejected edit is retried, not applied.

Applies to every agent that mutates source: `backend_developer`, `api_developer`, `ui_developer`, and
the Wave 5 `fix` agent.

---

## The Reject-Before-Write Rule

> An edit is **applied only after it passes every rung of the validation ladder below.**
> If any rung fails, the edit is **rejected** (not written to disk), the failure is reported back to
> the proposing agent, and the agent retries with a corrected edit. Never write a failing edit "to see
> if it works."

This inverts the default (write, then run tests, then discover breakage). Here breakage that is
*statically detectable* is caught **before** the write, so the working tree never enters a broken state.

---

## The Validation Ladder

Run in order. Stop at the first failure and reject.

### Rung 1 — Uniqueness (search/replace edits)

The `old_string` / search block must match **exactly once** in the target file.

```bash
COUNT=$(grep -Fc "$SEARCH_BLOCK" "$FILE" 2>/dev/null || echo 0)
```

| Match count | Verdict |
|---|---|
| 0 | **REJECT** — search block not found. The agent's mental model of the file is stale; re-read the file and re-propose. |
| 1 | Pass to Rung 2. |
| >1 | **REJECT** — ambiguous. Widen the search block with surrounding context until it is unique, or use `replace_all` intentionally. |

For diff/patch edits, the equivalent check is `git apply --check` (the hunk must apply cleanly).

### Rung 2 — Parse / compile check (result must still parse)

Apply the edit to a **scratch copy**, then syntax-check that copy. Never the live file.

```bash
TMP=$(mktemp)
# produce the edited content into $TMP (do NOT touch $FILE yet)

case "$FILE" in
  *.go)          gofmt -e "$TMP" >/dev/null ;;                    # parse check (no build needed)
  *.ts|*.tsx)    npx --no-install tsc --noEmit "$TMP" 2>/dev/null || npx --no-install eslint "$TMP" ;;
  *.js|*.jsx)    node --check "$TMP" ;;
  *.py)          python -m py_compile "$TMP" ;;
  *.json)        jq empty "$TMP" ;;
  *.yaml|*.yml)  python -c "import yaml,sys; yaml.safe_load(open('$TMP'))" ;;
  *)             : ;;  # no known checker — skip (uniqueness + deletion guard still applied)
esac
```

Non-zero exit → **REJECT** — the edit introduces a syntax/parse error. A prefer-cheap check (parse/lint)
is used over a full build; the full build still runs later in the wave. The point is to catch the
*obvious* breakage — unbalanced braces, bad indentation, broken JSON — before it lands.

### Rung 3 — Accidental-deletion guard

Compare pre/post line counts and byte size on the scratch copy.

```bash
ORIG_LINES=$(wc -l < "$FILE")
NEW_LINES=$(wc -l < "$TMP")
DELETED=$(( ORIG_LINES - NEW_LINES ))
```

| Condition | Verdict |
|---|---|
| Net deletion > 30% of the file **and** the edit was not declared a deletion/refactor | **REJECT** — likely a runaway replace that ate surrounding code. Require the agent to confirm the deletion is intentional. |
| Result is empty but source was non-empty | **REJECT** — never blank a file via edit. |
| File truncated mid-token (last line unterminated where original wasn't) | **REJECT** — partial write. |

The threshold is advisory: an explicit "remove dead function X" edit that declares its intent bypasses
the percentage guard but still runs Rungs 1-2.

---

## After Rejection

```
Edit rejected at Rung <n> (<reason>).
  → Rung 1: re-read the file, re-derive a unique search block.
  → Rung 2: fix the syntax the edit introduced; re-propose.
  → Rung 3: confirm the deletion is intended, or narrow the edit.
Retry budget: 2 corrected attempts per edit. After 2 rejections, escalate the edit to the
orchestrator as a blocked change rather than forcing a write.
```

Only after all rungs pass is the edit committed to the live file. Then normal wave testing proceeds.

---

## Why this belongs in the pipeline

- **No broken working tree.** Statically-detectable breakage never lands, so Wave 3 tests fail for
  *real* reasons, not for a mangled edit.
- **Cheaper than a test cycle.** A parse check is milliseconds; discovering the same breakage via a
  failed build + fix loop is minutes.
- **Deterministic.** grep/gofmt/tsc/jq — no LLM judgment, no new infra. Pure ACI guardrail.
