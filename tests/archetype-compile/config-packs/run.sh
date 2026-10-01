#!/usr/bin/env bash
# run.sh — check every non-application code block (sql, sh, yaml, json, dockerfile, hcl, ngql) in
# .claude/skills outside backend/archetypes and ui/archetypes.
#
# The blocks are extracted from the markdown at run time; units.py says how each one is checked (or
# why it is skipped). The run fails on any finding (printed as .claude/skills/<file>.md:<line>), on a
# block nobody checks or skips with a reason, and on a block count or first line that changed.
# Also: every ```bash block in .claude/commands and .claude/agents (bash -n + shellcheck -S error +
# the portability lint), no untagged fence in .claude/skills, no grep -P / BSD-first stat in any bash
# block or .claude/hooks/*.sh, and the lines those fixes changed run on macOS bash 3.2 (+ Linux, --live).
#
# Usage:
#   bash tests/archetype-compile/config-packs/run.sh                  # default: local tools, no network
#   bash tests/archetype-compile/config-packs/run.sh --live           # + Docker/network checks (below)
#   bash tests/archetype-compile/config-packs/run.sh --inventory-only # coverage only (python3, no venv)
#   bash tests/archetype-compile/config-packs/run.sh --only step-6 --family sh --keep
#   bash tests/archetype-compile/config-packs/run.sh --selftest     # proves the harness catches bugs
#
# Default run needs: python3 + uv (pinned venv: pglast 7 = the PostgreSQL 17 parser, PyYAML,
#   jsonschema, openapi-spec-validator), bash, shellcheck, actionlint, hadolint, terraform or tofu,
#   jq, git, go, curl, and the docker CLI for `docker compose config` (no daemon needed).
# --live also needs a running Docker daemon and the network: postgres:17, mysql:8.4 and NebulaGraph
#   v3.8.0 containers, Linux re-runs of the exec scenarios, docker build of the Dockerfiles (pulls
#   golang/node/distroless base images), kubeconform schemas, terraform/tofu providers, golangci-lint
#   config verify, and npm (ESLint 10 + eslint-plugin-jsx-a11y, typescript) for the config checks.
#   Containers are named cfgpk-* and removed at the end.
# Exit 0 = everything passed.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${CONFIG_PACKS_VENV:-$HERE/.venv}"
command -v python3 >/dev/null || { echo "run.sh: python3 not found" >&2; exit 2; }
if [[ " $* " == *" --inventory-only "* ]]; then
  exec python3 "$HERE/harness.py" "$@"
fi
command -v uv >/dev/null || { echo "run.sh: uv is required (https://docs.astral.sh/uv/)" >&2; exit 2; }
[ -x "$VENV/bin/python" ] || uv venv -q --python 3.12 "$VENV"
uv pip install -q --python "$VENV/bin/python" -r "$HERE/requirements.txt"
# docker is not on PATH on every macOS install (Docker Desktop keeps the CLI in the app bundle)
if ! command -v docker >/dev/null && [ -x /Applications/Docker.app/Contents/Resources/bin/docker ]; then
  export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"
fi
if [[ " $* " == *" --selftest "* ]]; then
  exec "$VENV/bin/python" "$HERE/selftest.py"     # puts known bugs back into a copy of the docs; each must fail
fi
exec "$VENV/bin/python" "$HERE/harness.py" "$@"
