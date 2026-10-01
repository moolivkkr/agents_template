#!/usr/bin/env bash
# k8s-db-roles.sh — proves the lab's two Postgres roles WITHOUT the cluster, on throwaway local
# postgres:17-alpine containers (the image postgres.yaml runs) and the fixture's real image
# (tests/fixtures/k8s-hello) for migrate, seed and serve. The same files the cluster gets: the
# template's db-roles.sh mounted read-only with mode 0555 (= the ConfigMap), deploylib.py db-secrets
# for the passwords. Not part of run-all.sh (needs Docker and, on first run, image pulls; ~1-2 min).
#
#   A fresh volume    initdb runs db-roles.sh; the db-roles Job afterwards changes nothing
#   B two roles       migrate refuses the app role and the superuser; the migrator migrates and seeds
#                     (idempotently); the app role can SELECT/INSERT/UPDATE/DELETE, read the schema
#                     version, and can't CREATE, ALTER, DROP, TRUNCATE or SET ROLE
#   C FORCE RLS       the app role sees only its tenant's rows, none without a tenant, can't write
#                     another tenant's; the migrator sees all; the API serves one tenant's notes only
#   D old volume      one superuser 'app' and objects it made (the old layout) -> the Job converges
#                     it: roles, ownership of every object kind, grants; the new fixture migrates,
#                     seeds and serves on top; a second run changes nothing
#   E secrets         no password in any server log (log_statement=all), Job or fixture output, even
#                     when ALTER ROLE ... PASSWORD fails; a wrong superuser password fails fast
# "Changes nothing" = a catalog snapshot (roles incl. password verifiers, memberships, owners and ACLs
# of the database, schemas, relations, types and routines, default privileges) is identical.
# Containers are named sdlc-dbroles-<pid>-*, Postgres is not published at all (Docker bridge only),
# the API test port binds 127.0.0.1, and everything (containers, fixture image) is removed on exit.
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="$PATH:/Applications/Docker.app/Contents/Resources/bin:/opt/homebrew/bin"
TPL="$REPO/.claude/templates/k8s/app"
DL="$TPL/scripts/k8s/deploylib.py"
P="sdlc-dbroles-$$"; IMG="$P-hello:test"
PASS=0; FAIL=0
ok()  { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad() { echo "  ✗ FAIL: $1"; FAIL=$((FAIL+1)); }
docker info >/dev/null 2>&1 || { echo "docker is not running"; exit 1; }

T="$(mktemp -d "${TMPDIR:-/tmp}/k8s-db-roles.XXXXXX")"; chmod 700 "$T"
cleanup() {
  docker rm -f "$P-a" "$P-b" "$P-api" >/dev/null 2>&1
  docker image rm "$IMG" >/dev/null 2>&1
  rm -rf "$T"
}
trap cleanup EXIT
mkdir "$T/cm" && cp "$TPL/deploy/k8s/base/db-roles.sh" "$T/cm/" && chmod 555 "$T/cm/db-roles.sh" && chmod 755 "$T" "$T/cm"   # = ConfigMap defaultMode 0555

ip()   { docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$1"; }
up()   { local _; for _ in $(seq 1 90); do docker exec "$1" pg_isready -q -h 127.0.0.1 -d app 2>/dev/null && return 0; sleep 1; done; return 1; }
envf() { (umask 077; cat > "$T/$1"); echo "$T/$1"; }   # env files for docker --env-file: values never in argv
# psql as a role over TCP to the container's own bridge IP (pg_hba: scram-sha-256, a real login)
q()    { PGPASSWORD="$3" docker exec -i -e PGPASSWORD "$1" psql -X -q -w -tA -v ON_ERROR_STOP=1 -v VERBOSITY=verbose -h "$(ip "$1")" -U "$2" -d app 2>&1; }
# psql as the bootstrap superuser over the socket (trusted), for setup and snapshots
asu()  { docker exec -i "$1" psql -X -q -tA -v ON_ERROR_STOP=1 -U "$2" -d app 2>&1; }
job()  { docker run --rm --user 70 --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges \
           --env-file "$2" -e PGHOST="$(ip "$1")" -e PGDATABASE=app -v "$T/cm:/db-roles:ro" \
           postgres:17-alpine bash /db-roles/db-roles.sh 2>&1; }
fx()   { docker run --rm --read-only --cap-drop ALL --security-opt no-new-privileges --env-file "$1" "$IMG" "${@:2}" 2>&1; }
url()  { printf 'DATABASE_URL=postgres://%s:%s@%s:5432/app?sslmode=disable\nAPP_ENV=local\n' "$2" "$3" "$(ip "$1")"; }
snapshot() {  # everything db-roles.sh could touch, password verifiers hashed
  asu "$1" "$2" <<'SQL' | shasum | cut -c1-16
SELECT rolname, rolsuper, rolinherit, rolcreaterole, rolcreatedb, rolcanlogin, rolreplication, rolbypassrls, rolconnlimit, md5(coalesce(rolpassword, '')) FROM pg_authid ORDER BY 1;
SELECT roleid::regrole, member::regrole, grantor::regrole, admin_option FROM pg_auth_members ORDER BY 1::text, 2::text;
SELECT datname, datdba::regrole, datacl FROM pg_database ORDER BY 1;
SELECT nspname, nspowner::regrole, nspacl FROM pg_namespace ORDER BY 1;
SELECT c.oid::regclass, c.relkind, c.relowner::regrole, c.relacl, c.relrowsecurity, c.relforcerowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname NOT LIKE 'pg\_%' AND n.nspname <> 'information_schema' ORDER BY 1::text;
SELECT defaclrole::regrole, defaclnamespace, defaclobjtype, defaclacl FROM pg_default_acl ORDER BY 1::text, 2, 3;
SELECT t.oid::regtype, t.typowner::regrole, t.typacl FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace WHERE n.nspname NOT LIKE 'pg\_%' AND n.nspname <> 'information_schema' ORDER BY 1::text;
SELECT p.oid::regprocedure, p.proowner::regrole, p.proacl FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname NOT LIKE 'pg\_%' AND n.nspname <> 'information_schema' ORDER BY 1::text;
SQL
}
LOGS="$T/outputs.log"; : > "$LOGS"
keep() { tee -a "$LOGS"; }   # every Job/fixture/psql output is kept for the secrets scan in E

echo "== build the fixture image (tests/fixtures/k8s-hello)"
if docker build -q -t "$IMG" "$REPO/tests/fixtures/k8s-hello/services/api" >/dev/null 2>"$T/build.err"; then
  ok "fixture image built"
else echo "  ✗ FAIL: docker build: $(tail -5 "$T/build.err")"; exit 1; fi
user="$(docker image inspect -f '{{.Config.User}}' "$IMG")"
[[ "$user" =~ ^[0-9]+(:[0-9]+)?$ ]] && ok "fixture image USER is numeric ($user)" || bad "fixture image USER is '$user' (kubelet needs a numeric uid for runAsNonRoot)"

echo "== A fresh volume: initdb runs db-roles.sh"
python3 "$DL" db-secrets "$T/a.secrets.env" 2>/dev/null
# shellcheck source=/dev/null
. "$T/a.secrets.env"   # DB_{SUPERUSER,MIGRATOR,APP}_{USER,PASSWORD}: hex values, written 0600 by deploylib
A_SU="$DB_SUPERUSER_USER" A_SU_PW="$DB_SUPERUSER_PASSWORD" A_M="$DB_MIGRATOR_USER" A_M_PW="$DB_MIGRATOR_PASSWORD" A_APP="$DB_APP_USER" A_APP_PW="$DB_APP_PASSWORD"
[ "$A_SU/$A_M/$A_APP" = "postgres/app_migrator/app_runtime" ] && ok "deploylib db-secrets: three roles (postgres, app_migrator, app_runtime)" || bad "role names $A_SU/$A_M/$A_APP"
PGA="$(envf a.pg.env <<EOF
POSTGRES_DB=app
POSTGRES_USER=$A_SU
POSTGRES_PASSWORD=$A_SU_PW
DB_MIGRATOR_USER=$A_M
DB_MIGRATOR_PASSWORD=$A_M_PW
DB_APP_USER=$A_APP
DB_APP_PASSWORD=$A_APP_PW
EOF
)"
docker run -d --name "$P-a" --env-file "$PGA" -v "$T/cm:/docker-entrypoint-initdb.d:ro" postgres:17-alpine \
  -c log_statement=all -c shared_preload_libraries=passwordcheck >/dev/null   # passwordcheck: an ALTER ROLE ... PASSWORD that fails (E)
up "$P-a" || { echo "postgres A did not start: $(docker logs "$P-a" 2>&1 | tail -5)"; exit 1; }
init="$(docker logs "$P-a" 2>&1)"
grep -q 'running /docker-entrypoint-initdb.d/db-roles.sh' <<<"$init" && grep -q 'db-roles: converged with' <<<"$init" \
  && ok "initdb ran db-roles.sh: $(grep -o 'db-roles: converged with [0-9]* change(s)' <<<"$init")" || bad "initdb did not run db-roles.sh"
attrs="$(asu "$P-a" "$A_SU" <<<"SELECT string_agg(rolname || ' super=' || rolsuper || ' bypassrls=' || rolbypassrls || ' login=' || rolcanlogin, '; ' ORDER BY rolname) FROM pg_roles WHERE rolname IN ('app_migrator', 'app_runtime')")"
[ "$attrs" = "app_migrator super=false bypassrls=true login=true; app_runtime super=false bypassrls=false login=true" ] \
  && ok "roles: $attrs" || bad "role attributes: $attrs"
JOBA="$(envf a.job.env <<EOF
PGUSER=$A_SU
PGPASSWORD=$A_SU_PW
DB_MIGRATOR_USER=$A_M
DB_MIGRATOR_PASSWORD=$A_M_PW
DB_APP_USER=$A_APP
DB_APP_PASSWORD=$A_APP_PW
EOF
)"
s1="$(snapshot "$P-a" "$A_SU")"; out="$(job "$P-a" "$JOBA" | keep)"; s2="$(snapshot "$P-a" "$A_SU")"
grep -q 'db-roles: no changes' <<<"$out" && [ "$s1" = "$s2" ] && ok "db-roles Job after initdb: 'no changes', catalog snapshot identical ($s1)" || bad "Job after initdb: $out ($s1 -> $s2)"

echo "== B two roles: migrate, seed, rights"
MIG="$(url "$P-a" "$A_M" "$A_M_PW" | envf a.migrator.url)"; APPU="$(url "$P-a" "$A_APP" "$A_APP_PW" | envf a.app.url)"; SUU="$(url "$P-a" "$A_SU" "$A_SU_PW" | envf a.su.url)"
out="$(fx "$APPU" migrate | keep)"; rc=$?
[ $rc -ne 0 ] && grep -q 'must run as the migration role' <<<"$out" && ok "migrate refuses the app role" || bad "migrate as app role: rc=$rc $out"
out="$(fx "$SUU" migrate | keep)"; rc=$?
[ $rc -ne 0 ] && grep -q 'must run as the migration role' <<<"$out" && ok "migrate refuses the superuser" || bad "migrate as superuser: rc=$rc $out"
out="$(fx "$MIG" migrate | keep)"
grep -q 'applied migration 1' <<<"$out" && grep -q 'applied migration 2' <<<"$out" && ok "migrator ran migrations 1 and 2" || bad "migrate as migrator: $out"
out="$(fx "$MIG" migrate | keep)"
grep -q 'migrated to schema version 2' <<<"$out" && ! grep -q 'applied migration' <<<"$out" && ok "migrate re-run applies nothing" || bad "migrate re-run: $out"
out2=""; out="$(fx "$MIG" seed | keep)" && out2="$(fx "$MIG" seed | keep)" && ok "migrator seeds (twice, idempotent)" || bad "seed as migrator: $out $out2"
counts="$(q "$P-a" "$A_M" "$A_M_PW" <<<"SELECT (SELECT count(*) FROM items) || '/' || (SELECT count(*) FROM notes)" | keep)"
[ "$counts" = "3/2" ] && ok "after two seeds: 3 items, 2 notes (migrator, BYPASSRLS, sees both tenants)" || bad "counts as migrator: $counts"
out="$(fx "$APPU" seed | keep)"; rc=$?
[ $rc -ne 0 ] && ok "seed as the app role is refused (no tenant context for notes): $(grep -o 'unrecognized configuration parameter[^(]*' <<<"$out" | head -1)" || bad "seed as app role succeeded"
owners="$(asu "$P-a" "$A_SU" <<<"SELECT string_agg(DISTINCT tableowner, ',') FROM pg_tables WHERE schemaname = 'public'")"
[ "$owners" = app_migrator ] && ok "every table is owned by app_migrator" || bad "table owners: $owners"
out="$(q "$P-a" "$A_APP" "$A_APP_PW" <<'SQL' | keep
SELECT max(version) FROM schema_migrations;
INSERT INTO items (name) VALUES ('rights-check');
UPDATE items SET name = 'rights-check-2' WHERE name = 'rights-check';
DELETE FROM items WHERE name = 'rights-check-2';
SELECT 'dml-ok';
SQL
)"
[ "$(printf '%s\n' "$out" | paste -sd' ' -)" = "2 dml-ok" ] && ok "app role reads the schema version (2) and can SELECT, INSERT (sequence), UPDATE, DELETE" || bad "app role DML: $out"
for stmt in "CREATE TABLE intruder (x int)" "CREATE SCHEMA intruder" "CREATE TEMP TABLE intruder (x int)" "ALTER TABLE items ADD COLUMN intruder int" \
            "DROP TABLE items" "TRUNCATE items" "ALTER TABLE notes NO FORCE ROW LEVEL SECURITY" "CREATE INDEX intruder ON items (name)" "SET ROLE app_migrator"; do
  out="$(q "$P-a" "$A_APP" "$A_APP_PW" <<<"$stmt;" | keep)"; rc=$?
  [ $rc -ne 0 ] && grep -q '42501' <<<"$out" && ok "app role refused (42501): $stmt" || bad "app role: '$stmt' -> rc=$rc $out"
done

echo "== C FORCE row-level security applies to the app role"
[ "$(asu "$P-a" "$A_SU" <<<"SELECT relrowsecurity::text || relforcerowsecurity::text FROM pg_class WHERE oid = 'notes'::regclass")" = truetrue ] \
  && ok "notes: ENABLE + FORCE ROW LEVEL SECURITY" || bad "notes RLS flags"
out="$(q "$P-a" "$A_APP" "$A_APP_PW" <<'SQL' | keep
BEGIN;
SELECT set_config('app.current_tenant_id', 'acme', true) \g /dev/null
SELECT string_agg(body, ',' ORDER BY id) FROM notes;
COMMIT;
SQL
)"
[ "$out" = "acme roadmap" ] && ok "app role in tenant acme sees only acme's note (no WHERE clause)" || bad "app role as acme: '$out'"
out="$(q "$P-a" "$A_APP" "$A_APP_PW" <<<"SELECT count(*) FROM notes;" | keep)"; rc=$?
[ $rc -ne 0 ] && grep -q '42704' <<<"$out" && ok "app role with no tenant set: refused (42704), fails closed" || bad "app role without tenant: rc=$rc $out"
out="$(q "$P-a" "$A_APP" "$A_APP_PW" <<'SQL' | keep
BEGIN;
SELECT set_config('app.current_tenant_id', 'acme', true) \g /dev/null
INSERT INTO notes (tenant_id, body) VALUES ('globex', 'planted by acme');
COMMIT;
SQL
)"; rc=$?
[ $rc -ne 0 ] && grep -q 'row-level security' <<<"$out" && ok "app role in acme can't write a globex row (WITH CHECK)" || bad "cross-tenant insert: rc=$rc $out"
docker run -d --name "$P-api" --read-only --cap-drop ALL --security-opt no-new-privileges -p 127.0.0.1::8080 --env-file "$APPU" "$IMG" serve >/dev/null
PORT="$(docker port "$P-api" 8080/tcp | head -1 | sed 's/.*://')"; API="http://127.0.0.1:$PORT"
for _ in $(seq 1 30); do curl -sf -m 2 "$API/healthz" >/dev/null && break; sleep 0.5; done
get() { curl -s -m 5 "$API$1" | python3 -c "import json,sys; print(','.join(json.load(sys.stdin)['$2']))" 2>/dev/null; }
[ "$(curl -s -o /dev/null -w '%{http_code}' -m 5 "$API/readyz")" = 200 ] && ok "API as the app role: /readyz 200 (reads schema_migrations)" || bad "/readyz as app role"
[ "$(get /api/items items)" = "alpha,beta,gamma" ] && ok "API /api/items: alpha,beta,gamma" || bad "/api/items: $(get /api/items items)"
[ "$(get /api/tenants/acme/notes notes)" = "acme roadmap" ] && [ "$(get /api/tenants/globex/notes notes)" = "globex payroll" ] && [ -z "$(get /api/tenants/nobody/notes notes)" ] \
  && ok "API /api/tenants/{acme,globex,nobody}/notes: one tenant's note each, none for nobody" || bad "API tenant notes"
docker rm -f "$P-api" >/dev/null
docker run -d --name "$P-api" --read-only -p 127.0.0.1::8080 --env-file "$MIG" "$IMG" serve >/dev/null   # negative control
PORT="$(docker port "$P-api" 8080/tcp | head -1 | sed 's/.*://')"; API="http://127.0.0.1:$PORT"
for _ in $(seq 1 30); do curl -sf -m 2 "$API/healthz" >/dev/null && break; sleep 0.5; done
[ "$(get /api/tenants/acme/notes notes)" = "acme roadmap,globex payroll" ] \
  && ok "control: the same API as the migrator (BYPASSRLS) returns both tenants, so the isolation above is RLS on the app role" || bad "control as migrator: $(get /api/tenants/acme/notes notes)"
docker rm -f "$P-api" >/dev/null
s1="$(snapshot "$P-a" "$A_SU")"; out="$(job "$P-a" "$JOBA" | keep)"; s2="$(snapshot "$P-a" "$A_SU")"
grep -q 'db-roles: no changes' <<<"$out" && [ "$s1" = "$s2" ] && ok "db-roles Job after migrate+seed: 'no changes', snapshot identical (it leaves the migrator's tables alone)" || bad "Job after migrate: $out"

echo "== D old volume (one superuser 'app', objects it made) converges without a reset"
printf 'DB_USER=app\nDB_PASSWORD=%s\n' "$(openssl rand -hex 24)" | (umask 077; cat > "$T/b.secrets.env")   # the old secrets.env
# shellcheck source=/dev/null
. "$T/b.secrets.env"; OLD_PW="$DB_PASSWORD"
PGB="$(envf b.pg.env <<EOF
POSTGRES_DB=app
POSTGRES_USER=app
POSTGRES_PASSWORD=$OLD_PW
EOF
)"
docker run -d --name "$P-b" --env-file "$PGB" postgres:17-alpine -c log_statement=all >/dev/null   # the old postgres.yaml: no initdb script
up "$P-b" || { echo "postgres B did not start"; exit 1; }
# The old fixture's migrate + seed, as the old Jobs ran them (as the superuser), then objects of every
# kind an app's earlier migrations may have made as that superuser.
asu "$P-b" app <<'SQL' >/dev/null || bad "legacy setup"
CREATE TABLE IF NOT EXISTS schema_migrations (version int PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS items (id serial PRIMARY KEY, name text UNIQUE NOT NULL);
INSERT INTO schema_migrations (version) VALUES (1) ON CONFLICT DO NOTHING;
INSERT INTO items (name) VALUES ('alpha'), ('beta'), ('gamma') ON CONFLICT (name) DO NOTHING;
CREATE TYPE mood AS ENUM ('ok', 'meh');
CREATE DOMAIN short_text AS text CHECK (length(VALUE) < 50);
CREATE TYPE pair AS (a int, b int);
CREATE TYPE floatrange AS RANGE (subtype = float8);
CREATE TABLE events (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, mood mood, note short_text);
CREATE TABLE metrics (at date NOT NULL, v int) PARTITION BY RANGE (at);
CREATE TABLE metrics_2026 PARTITION OF metrics FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');
CREATE SEQUENCE invoice_no;
CREATE VIEW item_names AS SELECT name FROM items;
CREATE MATERIALIZED VIEW item_count AS SELECT count(*) AS n FROM items;
CREATE FUNCTION touch() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$;
CREATE PROCEDURE noop() LANGUAGE sql AS $$ SELECT 1 $$;
CREATE AGGREGATE total(int) (sfunc = int4pl, stype = int);
CREATE STATISTICS items_stats ON id, name FROM items;
CREATE SCHEMA reporting;
CREATE TABLE reporting.daily (day date PRIMARY KEY, n int);
CREATE EXTENSION pg_trgm;
SQL
LEG="$(asu "$P-b" app <<<"SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname IN ('public', 'reporting') AND c.relowner = 'app'::regrole")"
ok "old volume: superuser 'app' owns $LEG relations, pg_trgm installed, no migrator/app roles"
python3 "$DL" db-secrets "$T/b.secrets.env" 2>"$T/b.notes"   # what deploy.sh does to an old secrets.env
grep -q 'kept the old DB_USER/DB_PASSWORD as the superuser pair' "$T/b.notes" && ok "deploylib db-secrets upgraded the old secrets.env: $(sed 's/.*secrets.env: //' "$T/b.notes")" || bad "db-secrets legacy upgrade: $(cat "$T/b.notes")"
unset DB_USER DB_PASSWORD
# shellcheck source=/dev/null
. "$T/b.secrets.env"
[ "$DB_SUPERUSER_USER" = app ] && [ "$DB_SUPERUSER_PASSWORD" = "$OLD_PW" ] && ok "the superuser pair is the one the volume was initialised with" || bad "superuser pair changed"
B_M_PW="$DB_MIGRATOR_PASSWORD" B_APP_PW="$DB_APP_PASSWORD"
JOBB="$(envf b.job.env <<EOF
PGUSER=$DB_SUPERUSER_USER
PGPASSWORD=$DB_SUPERUSER_PASSWORD
DB_MIGRATOR_USER=$DB_MIGRATOR_USER
DB_MIGRATOR_PASSWORD=$DB_MIGRATOR_PASSWORD
DB_APP_USER=$DB_APP_USER
DB_APP_PASSWORD=$DB_APP_PASSWORD
EOF
)"
out="$(job "$P-b" "$JOBB" | keep)"; rc=$?
[ $rc -eq 0 ] && grep -q 'db-roles: converged with' <<<"$out" && ok "db-roles Job on the old volume: $(grep -o 'converged with [0-9]* change(s)' <<<"$out")" || bad "Job on old volume: rc=$rc $out"
echo "$out" | grep -o 'NOTICE:  db-roles: .*' | sed 's/^NOTICE:  /      /' | head -40
left="$(asu "$P-b" app <<'SQL'
WITH ns AS (SELECT oid FROM pg_namespace WHERE nspname IN ('public', 'reporting'))
SELECT string_agg(x, ', ') FROM (
  SELECT 'relation ' || c.oid::regclass AS x FROM pg_class c WHERE c.relnamespace IN (SELECT oid FROM ns) AND c.relkind IN ('r','p','v','m','S') AND c.relowner <> 'app_migrator'::regrole
  UNION ALL SELECT 'type ' || t.oid::regtype FROM pg_type t WHERE t.typnamespace IN (SELECT oid FROM ns) AND t.typtype IN ('e','d','c','r') AND t.typowner <> 'app_migrator'::regrole
        AND NOT (t.typtype = 'c' AND (SELECT relkind FROM pg_class WHERE oid = t.typrelid) <> 'c')
        AND NOT EXISTS (SELECT FROM pg_depend d WHERE d.classid = 'pg_type'::regclass AND d.objid = t.oid AND d.deptype = 'e')
  UNION ALL SELECT 'routine ' || p.oid::regprocedure FROM pg_proc p WHERE p.pronamespace IN (SELECT oid FROM ns) AND p.proowner <> 'app_migrator'::regrole
        AND NOT EXISTS (SELECT FROM pg_depend d WHERE d.classid = 'pg_proc'::regclass AND d.objid = p.oid AND d.deptype IN ('e', 'i'))
  UNION ALL SELECT 'statistics ' || s.stxname FROM pg_statistic_ext s WHERE s.stxowner <> 'app_migrator'::regrole
  UNION ALL SELECT 'schema reporting' FROM pg_namespace WHERE nspname = 'reporting' AND nspowner <> 'app_migrator'::regrole
  UNION ALL SELECT 'database app' FROM pg_database WHERE datname = 'app' AND datdba <> 'app_migrator'::regrole) z
SQL
)"
[ -z "$left" ] && ok "every object of the old volume (tables, partitions, identity/serial/standalone sequences, views, matview, enum, domain, composite, range, function, procedure, aggregate, statistics, schema reporting, the database) is owned by app_migrator" || bad "still not owned by app_migrator: $left"
ext="$(asu "$P-b" app <<<"SELECT count(*) FROM pg_proc p JOIN pg_depend d ON d.classid = 'pg_proc'::regclass AND d.objid = p.oid AND d.deptype = 'e' WHERE d.refobjid = (SELECT oid FROM pg_extension WHERE extname = 'pg_trgm') AND p.proowner = 'app'::regrole")"
[ "${ext:-0}" -gt 0 ] && ok "pg_trgm's $ext functions stay with the extension (owner app), not taken over" || bad "extension members were altered ($ext)"
out="$(q "$P-b" app_runtime "$B_APP_PW" <<'SQL' | keep
SELECT max(version) FROM schema_migrations;
INSERT INTO items (name) VALUES ('after-takeover');
INSERT INTO events (mood, note) VALUES ('ok', 'x');
SELECT nextval('invoice_no') > 0;
SELECT count(*) FROM reporting.daily;
SELECT 'ok';
SQL
)"
[ "$(printf '%s\n' "$out" | paste -sd' ' -)" = "1 t 0 ok" ] && ok "app role on the old tables: reads the schema version, inserts (serial + identity), uses a standalone sequence, reads the other schema" || bad "app role on old tables: $out"
out="$(q "$P-b" app_runtime "$B_APP_PW" <<<"ALTER TABLE items ADD COLUMN intruder int;" | keep)"; rc=$?
[ $rc -ne 0 ] && grep -q 42501 <<<"$out" && ok "app role can't ALTER the old tables (42501)" || bad "app role altered an old table: $out"
MIGB="$(url "$P-b" app_migrator "$B_M_PW" | envf b.migrator.url)"; APPB="$(url "$P-b" app_runtime "$B_APP_PW" | envf b.app.url)"
out="$(fx "$MIGB" migrate | keep)"
grep -q 'applied migration 2' <<<"$out" && ! grep -q 'applied migration 1' <<<"$out" && ok "new fixture migrate as the migrator on the old volume: applies only migration 2" || bad "migrate on old volume: $out"
fx "$MIGB" seed | keep >/dev/null && ok "new fixture seed as the migrator on the old volume" || bad "seed on old volume"
docker run -d --name "$P-api" --read-only --cap-drop ALL -p 127.0.0.1::8080 --env-file "$APPB" "$IMG" serve >/dev/null
PORT="$(docker port "$P-api" 8080/tcp | head -1 | sed 's/.*://')"; API="http://127.0.0.1:$PORT"
for _ in $(seq 1 30); do curl -sf -m 2 "$API/healthz" >/dev/null && break; sleep 0.5; done
[ "$(curl -s -o /dev/null -w '%{http_code}' -m 5 "$API/readyz")" = 200 ] && [ "$(get /api/tenants/globex/notes notes)" = "globex payroll" ] \
  && ok "API as the app role on the converted volume: /readyz 200, globex sees only its note" || bad "API on old volume: readyz/notes"
docker rm -f "$P-api" >/dev/null
s1="$(snapshot "$P-b" app)"; out="$(job "$P-b" "$JOBB" | keep)"; s2="$(snapshot "$P-b" app)"
grep -q 'db-roles: no changes' <<<"$out" && [ "$s1" = "$s2" ] && ok "second db-roles Job on the converted volume: 'no changes', snapshot identical" || bad "second Job on old volume: $out"
[ "$(q "$P-b" app "$OLD_PW" <<<"SELECT rolsuper FROM pg_roles WHERE rolname = current_user;")" = t ] && ok "the old superuser still logs in with its password (volume not locked out)" || bad "old superuser login"

echo "== E secrets: never logged, auth errors fail fast"
start=$(date +%s)
out="$(sed "s/^PGPASSWORD=.*/PGPASSWORD=wrong-$$/" "$JOBA" | envf a.badsu.env >/dev/null; job "$P-a" "$T/a.badsu.env" | keep)"; rc=$?
took=$(( $(date +%s) - start ))
[ $rc -ne 0 ] && grep -q 'superuser login refused' <<<"$out" && [ "$took" -lt 15 ] && ok "wrong superuser password: refused in ${took}s, not retried for 60 s" || bad "wrong superuser password: rc=$rc ${took}s $out"
CANARY="app_runtime$(openssl rand -hex 12)"   # passwordcheck rejects a password containing the user name
out="$(sed "s/^DB_APP_PASSWORD=.*/DB_APP_PASSWORD=$CANARY/" "$JOBA" | envf a.canary.env >/dev/null; job "$P-a" "$T/a.canary.env" | keep)"; rc=$?
[ $rc -ne 0 ] && grep -q 'password must not contain user name' <<<"$out" && ok "a failing ALTER ROLE ... PASSWORD fails the Job: $(grep -o 'ERROR: .*' <<<"$out" | head -1)" || bad "canary Job: rc=$rc $out"
leaks=0
for s in "$A_SU_PW" "$A_M_PW" "$A_APP_PW" "$OLD_PW" "$B_M_PW" "$B_APP_PW" "$CANARY"; do
  for c in "$P-a" "$P-b"; do docker logs "$c" 2>&1 | grep -qF "$s" && { leaks=$((leaks+1)); echo "      password found in $c server log"; }; done
  grep -qF "$s" "$LOGS" && { leaks=$((leaks+1)); echo "      password found in Job/fixture/psql output"; }
done
lines=$(( $(docker logs "$P-a" 2>&1 | wc -l) + $(docker logs "$P-b" 2>&1 | wc -l) ))
[ "$leaks" = 0 ] && ok "7 passwords (incl. the rejected canary) appear in none of $lines server log lines (log_statement=all) or $(wc -l < "$LOGS" | tr -d ' ') output lines" || bad "$leaks password leak(s)"
docker logs "$P-a" 2>&1 | grep -q "PASSWORD '" && bad "an ALTER ROLE ... PASSWORD '...' statement reached the server log" || ok "no ALTER ROLE ... PASSWORD statement in the server log (the password session turns statement logging off)"

echo "────────────────────────────────────────────"
echo "k8s-db-roles.sh: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
