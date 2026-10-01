#!/usr/bin/env bash
# remember.sh — the DETERMINISTIC engine behind /remember. Turns the bi-temporal fact supersession
# that the framework has always DESCRIBED (shared-context-protocol.md, remember.md) into code that
# actually runs, so two contradictory facts can never both be `status: active`.
#
# The model still does the LANGUAGE part (read the user's sentence → subject, relation, title, fact
# text). This script does the MECHANICAL part atomically:
#   - assign the next F-### id
#   - deterministic supersession on the EXACT (subject, relation) key — never similarity:
#       flip the prior active fact's status → superseded, stamp invalid_at, set superseded_by
#   - append the new active fact to "## Active Facts"
#
# Usage:
#   remember.sh add --subject <s> --relation <lifecycle|name|constraint|environment|boundary> \
#                   --title "<short title>" --date <YYYY-MM-DD> --fact "<instructional fact text>" \
#                   [--confidence confirmed] [--source human:/remember] [--file docs/PROJECT_FACTS.md]
#   remember.sh retire --subject <s> --date <YYYY-MM-DD> --title "<t>" --fact "<t>"   # relation=lifecycle
#   remember.sh list                     # print active fact headings
#   remember.sh history --subject <s>    # print active + superseded blocks for a subject
#   remember.sh decide --title "<t>" --scope <global|phase-N|component:x> --date <YYYY-MM-DD> \
#                   --decision "<what was chosen>" --rationale "<why; runner-up rejected because…>" \
#                   [--source adr|debate|human:/remember|agent:<name>] [--confidence confirmed|reported] \
#                   [--link <path>] [--reverses D-NNN]          # appends to docs/DECISIONS.md
#     The ONLY writer of docs/DECISIONS.md: the sdlc-guard denies direct edits to an existing ledger
#     (board review SEC-04), so ADR/debate agents and the parent record decisions through this.
#     --reverses flips that entry to `status: reversed` and stamps reversed_by deterministically.
#
# Prints the new F-id and what it superseded to stdout. Exit 0 on success, non-zero on usage error.
# Dependencies: bash, awk. No jq (PROJECT_FACTS.md is markdown, not JSON).

set -uo pipefail

FILE="docs/PROJECT_FACTS.md"
TEMPLATE=".claude/templates/PROJECT_FACTS.md.template"

# --- locate project root (mirror verify-gate.sh) so this works from any cwd ---
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-}"
[ -z "$PROJECT_DIR" ] && PROJECT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$PROJECT_DIR" 2>/dev/null || { echo "remember: cannot cd to project dir '$PROJECT_DIR'"; exit 3; }

ACTION="${1:-}"; shift || true

# --- parse flags ---
SUBJECT=""; RELATION=""; TITLE=""; DATE=""; FACT=""; CONFIDENCE="confirmed"; SOURCE="human:/remember"
while [ $# -gt 0 ]; do
  case "$1" in
    --subject)    SUBJECT="${2:-}"; shift 2 ;;
    --relation)   RELATION="${2:-}"; shift 2 ;;
    --title)      TITLE="${2:-}"; shift 2 ;;
    --date)       DATE="${2:-}"; shift 2 ;;
    --fact)       FACT="${2:-}"; shift 2 ;;
    --confidence) CONFIDENCE="${2:-}"; shift 2 ;;
    --source)     SOURCE="${2:-}"; shift 2 ;;
    --file)       FILE="${2:-}"; shift 2 ;;
    --scope)      D_SCOPE="${2:-}"; shift 2 ;;
    --link)       D_LINK="${2:-}"; shift 2 ;;
    --decision)   D_DECISION="${2:-}"; shift 2 ;;
    --rationale)  D_RATIONALE="${2:-}"; shift 2 ;;
    --reverses)   D_REVERSES="${2:-}"; shift 2 ;;
    *) echo "remember: unknown arg '$1'"; exit 3 ;;
  esac
done

# --- decide: append a D-NNN entry to the decision ledger (Tier 0.5) ---
if [ "$ACTION" = "decide" ]; then
  [ "$FILE" = "docs/PROJECT_FACTS.md" ] && FILE="docs/DECISIONS.md"
  for v in TITLE:"$TITLE" DATE:"$DATE" SCOPE:"${D_SCOPE:-}" DECISION:"${D_DECISION:-}" RATIONALE:"${D_RATIONALE:-}"; do
    k="${v%%:*}"; val="${v#*:}"
    if [ -z "$val" ]; then echo "remember decide: --$(printf '%s' "$k" | tr '[:upper:]' '[:lower:]') is required"; exit 3; fi
  done
  exec python3 - "$FILE" "$TITLE" "$DATE" "$D_SCOPE" "$D_DECISION" "$D_RATIONALE" "$SOURCE" "$CONFIDENCE" "${D_LINK:-—}" "${D_REVERSES:-}" <<'PY'
import fcntl, hashlib, os, re, sys, tempfile
path, title, date, scope, decision, rationale, source, confidence, link, reverses = sys.argv[1:11]
# Debates finishing together call this in parallel. Without a lock two callers read the same ledger,
# both take the next D-NNN, and one entry is lost (board review 2026-09-30-debate, ARCH-03: lost in
# 20/20 trials). The lock lives outside the repo, keyed by the ledger's absolute path.
_lock = open(os.path.join(tempfile.gettempdir(), "remember-" + hashlib.sha1(os.path.abspath(path).encode()).hexdigest()[:16] + ".lock"), "w")
fcntl.flock(_lock, fcntl.LOCK_EX)
text = open(path).read() if os.path.exists(path) else "# DECISIONS\n\nSettled decisions with rationale (Tier 0.5). Written only by `.claude/hooks/remember.sh decide`.\n\n"
live = re.sub(r"<!--.*?-->", "", text, flags=re.S)                       # ignore commented examples
ids = [int(n) for n in re.findall(r"^### D-(\d+)", live, re.M)]
new = f"D-{(max(ids) + 1 if ids else 1):03d}"
if reverses:
    m = re.search(rf"^### {re.escape(reverses)}\b.*?(?=^### |\Z)", text, re.M | re.S)
    if not m:
        sys.exit(f"remember decide: --reverses {reverses} not found in {path}")
    block = m.group(0)
    if "- status: active" not in block:
        sys.exit(f"remember decide: {reverses} is not active (nothing to reverse)")
    block2 = block.replace("- status: active", "- status: reversed", 1)
    block2 = re.sub(r"^- reversed_by: .*$", f"- reversed_by: {new}", block2, count=1, flags=re.M)
    text = text[:m.start()] + block2 + text[m.end():]
entry = (f"### {new} — {title}\n- status: active\n- scope: {scope}\n- date: {date}\n- source: {source}\n"
         f"- confidence: {confidence}\n- reverses: {reverses or '—'}\n- reversed_by: —\n- link: {link}\n"
         f"- decision: > {decision}\n- rationale: > {rationale}\n")
text = text.rstrip("\n") + "\n\n" + entry
os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
fd, tmp = tempfile.mkstemp(prefix=".DECISIONS.", suffix=".tmp", dir=os.path.dirname(path) or ".")
with os.fdopen(fd, "w") as fh:
    fh.write(text)
os.replace(tmp, path)
print(f"{new} recorded" + (f"; {reverses} → reversed" if reverses else ""))
PY
fi

ensure_file() {
  if [ ! -f "$FILE" ]; then
    mkdir -p "$(dirname "$FILE")"
    if [ -f "$TEMPLATE" ]; then
      # Strip the pedagogical <!-- Example --> block: the live file must not carry a phantom
      # commented F-001 (it would collide with the first real id and confuse comment-unaware readers).
      awk 'BEGIN{c=0} /<!--/{c=1} c{ if(/-->/) c=0; next } {print}' "$TEMPLATE" > "$FILE"
    else
      printf '# PROJECT_FACTS\n\n## Active Facts\n\n_No facts recorded yet._\n\n---\n\n## Superseded Facts (history — do not act on these)\n\n_None yet._\n' > "$FILE"
    fi
  fi
}

case "$ACTION" in
  list)
    ensure_file
    awk '
      !c && /<!--/{c=1} c{if(/-->/)c=0; next}
      /^### F-/{t=$0} /^- status: active/{if(t){print t; t=""}}' "$FILE"
    exit 0 ;;
  history)
    ensure_file
    [ -z "$SUBJECT" ] && { echo "remember history: --subject required"; exit 3; }
    awk -v s="$SUBJECT" '
      !c && /<!--/{c=1} c{if(/-->/)c=0; next}
      /^### F-/ { if(buf!="" && keep) printf "%s", buf; buf=$0 ORS; keep=0; next }
      { if(buf!="") buf=buf $0 ORS; if($0 ~ ("^- subject: " s "$")) keep=1 }
      END { if(buf!="" && keep) printf "%s", buf }
    ' "$FILE"
    exit 0 ;;
  add|retire) : ;;
  *) echo "remember: usage — add|retire|list|history|decide (got '$ACTION')"; exit 3 ;;
esac

[ "$ACTION" = "retire" ] && RELATION="lifecycle"

# validate required inputs for add/retire
for v in SUBJECT:"$SUBJECT" RELATION:"$RELATION" TITLE:"$TITLE" DATE:"$DATE" FACT:"$FACT"; do
  k="${v%%:*}"; val="${v#*:}"
  # bash 3.2-safe lowercase (macOS /bin/bash): ${k,,} is bash-4 only, and under 3.2 its "bad
  # substitution" skipped this exit, so a missing --fact recorded a blank fact that superseded the
  # real one (review 2026-09-30, D1).
  if [ -z "$val" ]; then echo "remember $ACTION: --$(printf '%s' "$k" | tr '[:upper:]' '[:lower:]') is required"; exit 3; fi
done

ensure_file

# --- next F-id: highest existing F-### + 1, zero-padded to 3. Ignore ids inside <!-- --> comment
#     regions (the template ships a commented F-001 example that is NOT a real fact). ---
MAX=$(awk '
  /<!--/ { c=1 }
  !c && /^### F-[0-9]+/ { s=$0; sub(/^### F-0*/,"",s); sub(/[^0-9].*$/,"",s); if(s=="") s=0; print s+0 }
  /-->/ { c=0 }
' "$FILE" | sort -n | tail -1)
[ -z "$MAX" ] && MAX=0
NEWNUM=$((10#$MAX + 1))
NEWID=$(printf 'F-%03d' "$NEWNUM")

# --- build the new fact block ---
NEWBLOCK="### ${NEWID} — ${TITLE}
- status: active
- subject: ${SUBJECT}
- relation: ${RELATION}
- valid_from: ${DATE}
- invalid_at: —
- superseded_by: —
- source: ${SOURCE}
- confidence: ${CONFIDENCE}
- fact: >
    ${FACT}
"

# --- write the new block to a temp file (multi-line values can't go through `awk -v` reliably) ---
BLOCKFILE="$(mktemp)"; printf '%s\n' "$NEWBLOCK" > "$BLOCKFILE"

# --- Pass 1: deterministic supersession. Buffer each ### block so we can edit the status line
#     (which appears BEFORE subject/relation). Only single-line values go through -v. ---
TMP1="$(mktemp)"; SUPERFILE="$(mktemp)"
awk -v subj="$SUBJECT" -v rel="$RELATION" -v newid="$NEWID" -v date="$DATE" '
  function process_block(   i, n, lines, is_active, is_match_subj, is_match_rel) {
    n = split(blockbuf, lines, "\n")
    is_active = 0; is_match_subj = 0; is_match_rel = 0
    for (i = 1; i <= n; i++) {
      if (lines[i] ~ /^- status: active$/) is_active = 1
      if (lines[i] == "- subject: " subj) is_match_subj = 1
      if (lines[i] == "- relation: " rel) is_match_rel = 1
    }
    if (is_active && is_match_subj && is_match_rel) {
      for (i = 1; i <= n; i++) {
        if (lines[i] ~ /^- status: active$/)     lines[i] = "- status: superseded"
        else if (lines[i] ~ /^- invalid_at:/)    lines[i] = "- invalid_at: " date
        else if (lines[i] ~ /^- superseded_by:/) lines[i] = "- superseded_by: " newid
      }
      print current_id > "/dev/stderr"
    }
    for (i = 1; i <= n; i++) { if (i == n && lines[i] == "") continue; print lines[i] }
  }
  BEGIN { inblock = 0; blockbuf = ""; in_comment = 0 }
  {
    if (!in_comment && $0 ~ /<!--/) in_comment = 1
    if (in_comment) { print $0; if ($0 ~ /-->/) in_comment = 0; next }
    if ($0 ~ /^### F-/) {
      if (inblock) process_block()
      blockbuf = $0; inblock = 1
      current_id = $0; sub(/^### /, "", current_id); sub(/ .*$/, "", current_id)
      next
    }
    if (inblock && ($0 ~ /^### / || $0 ~ /^---[[:space:]]*$/)) {
      process_block(); inblock = 0; blockbuf = ""; print $0; next
    }
    if (inblock) { blockbuf = blockbuf "\n" $0; next }
    print $0
  }
  END { if (inblock) process_block() }
' "$FILE" 2> "$SUPERFILE" > "$TMP1"
SUPERSEDED="$(head -1 "$SUPERFILE" 2>/dev/null)"

# --- Pass 2: insert the new active block at the end of "## Active Facts" (before its closing ---),
#     stripping the "no facts yet" placeholder. Block content comes from a FILE, not -v. ---
TMP2="$(mktemp)"
awk -v blockfile="$BLOCKFILE" '
  BEGIN { seen = 0; done = 0; in_comment = 0 }
  {
    if (!in_comment && $0 ~ /<!--/) in_comment = 1
    if (in_comment) { print $0; if ($0 ~ /-->/) in_comment = 0; next }
    if ($0 ~ /^_No facts recorded yet/) next
    if ($0 ~ /^## Active Facts/) seen = 1
    if (seen && !done && $0 ~ /^---[[:space:]]*$/) {
      while ((getline l < blockfile) > 0) print l
      close(blockfile); done = 1
    }
    print
  }
  END { if (!done) { while ((getline l < blockfile) > 0) print l } }
' "$TMP1" > "$TMP2"

mv "$TMP2" "$FILE"
rm -f "$TMP1" "$SUPERFILE" "$BLOCKFILE"

if [ -n "$SUPERSEDED" ]; then
  echo "remember: recorded ${NEWID} (${SUBJECT}/${RELATION}) — superseded ${SUPERSEDED}"
else
  echo "remember: recorded ${NEWID} (${SUBJECT}/${RELATION}) — no prior active fact on this key"
fi
