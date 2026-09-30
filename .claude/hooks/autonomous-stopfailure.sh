#!/usr/bin/env bash
# autonomous-stopfailure.sh — StopFailure hook: record API errors into the /autonomous run state.
#
# When a turn ends because of an API error, Claude Code runs StopFailure instead of Stop (and
# ignores this hook's output). Without it the run stays "running" with nothing to resume it
# (review 2026-09-30, A5). This records the error so a supervisor, `/autonomous --resume`, or a
# human can act:
#   transient (rate_limit, overloaded, server_error, max_output_tokens, unknown): error recorded,
#     status stays "running" so a resume/supervisor continues it;
#   permanent (authentication_failed, oauth_org_not_allowed, account_on_hold, billing_error,
#     invalid_request, model_not_found, cloud_credential_error): status → "paused" with the reason.
set -uo pipefail
INPUT="$(cat 2>/dev/null || true)"
command -v jq >/dev/null 2>&1 || exit 0
field() { printf '%s' "$INPUT" | jq -r "$1" 2>/dev/null; }
DIR="$(field '.cwd // empty')"; DIR="${DIR:-${CLAUDE_PROJECT_DIR:-$PWD}}"
RUN="$DIR/agent_state/autonomous/run.json"
[ -f "$RUN" ] && jq -e . "$RUN" >/dev/null 2>&1 || exit 0
[ "$(jq -r '.active // false' "$RUN")" = "true" ] || exit 0

SESSION="$(field '.session_id // empty')"
bound="$(jq -r '.session_id // empty' "$RUN")"
[ -n "$bound" ] && [ -n "$SESSION" ] && [ "$bound" != "$SESSION" ] && exit 0

err="$(field '.error // "unknown"')"
details="$(field '.error_details // .last_assistant_message // ""')"
now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
case "$err" in
  authentication_failed|oauth_org_not_allowed|account_on_hold|billing_error|invalid_request|model_not_found|cloud_credential_error)
    kind=permanent ;;
  *) kind=transient ;;
esac

tmp="$(mktemp)"
jq --arg e "$err" --arg d "$details" --arg k "$kind" --arg now "$now" '
  .last_error = {type: $e, kind: $k, details: $d, at: $now}
  | .error_count = ((.error_count // 0) + 1)
  | if $k == "permanent" and .status == "running"
    then .status = "paused" | .reason = ("API error: " + $e + " — fix it, then /autonomous --resume")
    else . end' "$RUN" > "$tmp" && mv "$tmp" "$RUN"
exit 0
