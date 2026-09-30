#!/usr/bin/env bash
# prepare-sqlx.sh — regenerate .sqlx/, the offline metadata the sqlx::query! / query_as! macros in the
# Rust archetypes are checked against. Run it after changing a query or the schema, then commit .sqlx/.
#
# Starts a throwaway postgres:17-alpine container on a random localhost port, applies the schema
# (`harness.py --print-schema`: the migration-pattern-rust.md migrations minus units.SCHEMA_EXCLUDE,
# plus stubs/harness_schema.sql), runs every unit's cargo check with the macros ONLINE against it
# (they write .sqlx/query-*.json), and removes the container. Needs Docker.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="$HOME/.cargo/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"
IMAGE="${ARCHETYPE_PG_IMAGE:-postgres:17-alpine}"
NAME="archetype-rust-sqlx-$$"

docker run -d --rm --name "$NAME" -e POSTGRES_PASSWORD=postgres -p 127.0.0.1::5432 "$IMAGE" >/dev/null
trap 'docker rm -f "$NAME" >/dev/null 2>&1 || true' EXIT
PORT="$(docker port "$NAME" 5432/tcp | head -1 | sed 's/.*://')"

# The image runs a socket-only server during init; TCP answers once the real server is up.
for _ in $(seq 1 60); do
  docker exec "$NAME" pg_isready -h 127.0.0.1 -U postgres >/dev/null 2>&1 && break
  sleep 1
done
docker exec "$NAME" pg_isready -h 127.0.0.1 -U postgres >/dev/null

python3 "$HERE/harness.py" --print-schema \
  | docker exec -i "$NAME" psql -v ON_ERROR_STOP=1 -q -U postgres -d postgres
python3 "$HERE/harness.py" --prepare-sqlx "postgres://postgres:postgres@127.0.0.1:$PORT/postgres" "$@"
