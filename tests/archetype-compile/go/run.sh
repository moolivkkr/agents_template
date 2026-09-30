#!/usr/bin/env bash
# run.sh — compile-check every ```go block in .claude/skills/backend/archetypes/*.md.
#
# The blocks are extracted from the markdown at run time (so an edit to a sample is re-verified),
# assembled into throwaway Go modules (units.json says which blocks form which files and packages),
# and checked with `go build` + `go vet` (+ `go test -run '^$'` for units with tests). Units whose
# tests need no external service also RUN them (service/handler mocks, the error mapper, a WebSocket
# round trip, the OTel resource). Library versions are the ones pinned in go.mod here.
#
# It fails if any unit fails, and also if any Go block is neither compiled by a unit nor listed in
# units.json "skip" with a reason, or if a file's block count/headings no longer match units.json.
#
# Usage:
#   bash tests/archetype-compile/go/run.sh                 # all units
#   bash tests/archetype-compile/go/run.sh --only grpc     # some units
#   bash tests/archetype-compile/go/run.sh --keep          # keep the assembled modules for debugging
#   bash tests/archetype-compile/go/run.sh --inventory-only   # coverage check only (no Go needed)
#   ARCHETYPE_DB_TESTS=1 bash tests/archetype-compile/go/run.sh --only crud-postgres
#       # also run the repository integration tests (testcontainers: needs a Docker daemon)
#
# Needs: Go (1.27.1 when last verified) and python3. No system protoc: protos are compiled by
# testdata/protogen with the pinned protocompile + protoc-gen-go(-grpc). The first run downloads the
# pinned modules. Exit 0 = everything PASS.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
command -v python3 >/dev/null || { echo "run.sh: python3 not found" >&2; exit 2; }
if [[ " $* " != *" --inventory-only "* ]]; then
  command -v go >/dev/null || { echo "run.sh: go not found (https://go.dev/dl/)" >&2; exit 2; }
fi
exec python3 "$DIR/harness.py" "$@"
