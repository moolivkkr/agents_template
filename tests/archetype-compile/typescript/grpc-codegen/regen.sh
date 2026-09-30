#!/usr/bin/env bash
# Regenerate shims/grpc/src/gen (ts-proto output for the grpc-pattern.md protos) — run after the
# protos in grpc-pattern.md change. The generated code is committed so run.sh needs no compiler.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
rm -rf proto ../shims/grpc/src/gen
python3 extract_protos.py
../node_modules/.bin/buf generate
echo "regenerated ../shims/grpc/src/gen"
