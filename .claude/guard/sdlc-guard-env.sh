#!/bin/bash
# sdlc-guard-env.sh — SessionStart hook (user settings). For Claude's Bash tool only, it puts the
# guard's kubectl/helm/limactl shims first on PATH and pins KUBECONFIG to the agent kubeconfig named
# in the guard policy, so scripts and subprocesses get the same identity and exec-time checks.
[ -n "${CLAUDE_ENV_FILE:-}" ] || exit 0
SHIMS="${SDLC_GUARD_SHIMS:-$HOME/.claude/hooks/sdlc-guard-shims}"
POLICY="${SDLC_GUARD_POLICY:-$HOME/.config/sdlc-guard/policy.json}"
KC="$(/usr/bin/python3 -c 'import json,os,sys; print(os.path.expanduser(json.load(open(sys.argv[1]))["kube"]["kubeconfig"]))' "$POLICY" 2>/dev/null)"
{
  [ -d "$SHIMS" ] && printf 'export PATH="%s:$PATH"\n' "$SHIMS"
  [ -n "$KC" ] && printf 'export KUBECONFIG="%s"\n' "$KC"
} >> "$CLAUDE_ENV_FILE"
exit 0
