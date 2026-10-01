#!/usr/bin/env bash
# docker-check.sh — build the Rust Dockerfiles (dockerfile-rust.md, performance-rust.md) for real and
# run each image: numeric USER, the process uid, GET /healthz, GIT_SHA, HEALTHCHECK. See docker-check.py.
#
#   bash tests/archetype-compile/rust/docker-check.sh
#   bash tests/archetype-compile/rust/docker-check.sh --only debian musl-alpine
#
# Needs Docker, network access for the base images and crates, and a Rust toolchain (cargo metadata
# checks docker/Cargo.lock). The first run takes a while (release builds with LTO); later runs are cached.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="$HOME/.cargo/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"
exec python3 "$HERE/docker-check.py" "$@"
