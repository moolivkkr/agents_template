# throwaway-pg.sh — sourced by prepare-sqlx.sh and run-tests.sh: starts a postgres:17-alpine container
# on a random 127.0.0.1 port, removes it on exit, and sets PG_NAME / PG_PORT / PG_URL (the server's
# maintenance database). Needs Docker.
export PATH="$HOME/.cargo/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"
PG_IMAGE="${ARCHETYPE_PG_IMAGE:-postgres:17-alpine}"
PG_NAME="archetype-rust-pg-$$"

docker run -d --rm --name "$PG_NAME" -e POSTGRES_PASSWORD=postgres -p 127.0.0.1::5432 "$PG_IMAGE" >/dev/null
trap 'docker rm -f "$PG_NAME" >/dev/null 2>&1 || true' EXIT
PG_PORT="$(docker port "$PG_NAME" 5432/tcp | head -1 | sed 's/.*://')"

# The image runs a socket-only server during init; TCP answers once the real server is up.
for _ in $(seq 1 60); do
  docker exec "$PG_NAME" pg_isready -h 127.0.0.1 -U postgres >/dev/null 2>&1 && break
  sleep 1
done
docker exec "$PG_NAME" pg_isready -h 127.0.0.1 -U postgres >/dev/null
PG_URL="postgres://postgres:postgres@127.0.0.1:$PG_PORT/postgres"
