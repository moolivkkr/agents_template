#!/usr/bin/env bash
# prepare-sqlx.sh — regenerate .sqlx/, the offline metadata the sqlx::query! / query_as! macros in the
# Rust samples are checked against. Run it after changing a query or a schema, then commit .sqlx/.
#
# Starts a throwaway postgres:17-alpine container on a random localhost port (throwaway-pg.sh) and
# creates one database per units.SCHEMAS entry (archetype_<name>), each holding that schema
# (`harness.py --print-schema NAME`: a doc's ```sql migrations, plus harness-only tables). Then runs
# every unit's cargo check with the macros ONLINE against its schema's database (they write
# .sqlx/query-*.json), and removes the container. Needs Docker.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=throwaway-pg.sh
source "$HERE/throwaway-pg.sh"

for schema in $(python3 "$HERE/harness.py" --list-schemas); do
  docker exec "$PG_NAME" psql -v ON_ERROR_STOP=1 -q -U postgres -d postgres -c "CREATE DATABASE archetype_$schema"
  python3 "$HERE/harness.py" --print-schema "$schema" \
    | docker exec -i "$PG_NAME" psql -v ON_ERROR_STOP=1 -q -U postgres -d "archetype_$schema"
done
python3 "$HERE/harness.py" --prepare-sqlx "$PG_URL" "$@"
