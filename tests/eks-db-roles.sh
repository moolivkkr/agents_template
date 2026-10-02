#!/usr/bin/env bash
# eks-db-roles.sh — proves db-roles.sh's MANAGED-Postgres mode (Amazon RDS / Aurora PostgreSQL, the EKS
# staging/prod targets) on a throwaway local postgres:17-alpine container set up like an RDS instance:
# the connecting role is a NON-superuser master (LOGIN NOSUPERUSER INHERIT CREATEDB CREATEROLE, member
# of a NOLOGIN rds_superuser role, owner of database app), exactly the attributes AWS documents for the
# RDS master user. The real superuser here stands in for AWS's internal rdsadmin and is used only for
# setup and snapshots. This is a stock-PostgreSQL simulation, not RDS itself: anything RDS patches in
# its fork (it documents none for BYPASSRLS) is not covered. Not part of run-all.sh (needs Docker).
#
#   1 premise      the master user cannot create a BYPASSRLS role (PostgreSQL's rule)
#   2 converge     the Job (same script, same mount as the ConfigMap) creates both roles NOBYPASSRLS,
#                  warns about the migrator, hands the database to the migrator, sets default privileges
#   3 idempotent   a second run prints "no changes" and the catalog snapshot is identical
#   4 RLS          D-001: a tenant table made with the skill's own block (databases/postgres.md: FORCE RLS,
#                  tenant policy, app_grant_migrator() -> migrator-only policy): the NOBYPASSRLS migrator
#                  seeds and backfills both tenants; the app role sees one tenant, can't write another's,
#                  can't touch the policies, SET ROLE, ALTER or lift RLS; without the policy the
#                  migrator's backfill reaches 0 rows (control)
#   4b db-rls-check the deploy's app-role Job: fails on a FORCE-RLS table with no migrator policy and on
#                  every unconditional policy that reaches the app role; passes on the archetype schema
#   5 secrets      no password in the server log (default log_statement=none, as on RDS) or Job output;
#                  the "can't turn logging off" note is printed; a wrong master password fails fast
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="$PATH:/Applications/Docker.app/Contents/Resources/bin:/opt/homebrew/bin"
TPL="$REPO/.claude/templates/k8s/app"
P="sdlc-eksdbroles-$$"
PASS=0; FAIL=0
ok()  { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad() { echo "  ✗ FAIL: $1"; FAIL=$((FAIL+1)); }
docker info >/dev/null 2>&1 || { echo "docker is not running"; exit 1; }
T="$(mktemp -d "${TMPDIR:-/tmp}/eks-db-roles.XXXXXX")"; chmod 700 "$T"
cleanup() { docker rm -f "$P" >/dev/null 2>&1; rm -rf "$T"; }
trap cleanup EXIT
mkdir "$T/cm" "$T/rls" && cp "$TPL/deploy/k8s/base/db-roles.sh" "$T/cm/" && cp "$TPL/deploy/k8s/base/db-rls-check.sh" "$T/rls/" \
  && chmod 555 "$T/cm/db-roles.sh" "$T/rls/db-rls-check.sh" && chmod 755 "$T" "$T/cm" "$T/rls"

pw() { python3 -c 'import secrets; print(secrets.token_hex(24))'; }
ROOT_PW="$(pw)"; MASTER_PW="$(pw)"; MIG_PW="$(pw)"; APP_PW="$(pw)"
envf() { (umask 077; cat > "$T/$1"); echo "$T/$1"; }
ip()  { docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$P"; }
asu() { docker exec -i "$P" psql -X -q -tA -v ON_ERROR_STOP=1 -U rdsadmin -d app 2>&1; }      # setup/snapshots only
q()   { PGPASSWORD="$2" docker exec -i -e PGPASSWORD "$P" psql -X -q -w -tA -v ON_ERROR_STOP=1 -h "$(ip)" -U "$1" -d app 2>&1; }
job() { docker run --rm --user 70 --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges \
          --env-file "$1" -e PGHOST="$(ip)" -e PGDATABASE=app -e PGSSLMODE=prefer -v "$T/cm:/db-roles:ro" \
          postgres:17-alpine bash /db-roles/db-roles.sh 2>&1; }
snapshot() { asu <<'SQL' | shasum | cut -c1-16
SELECT rolname, rolsuper, rolinherit, rolcreaterole, rolcreatedb, rolcanlogin, rolbypassrls, md5(coalesce(rolpassword, '')) FROM pg_authid ORDER BY 1;
SELECT roleid::regrole, member::regrole, grantor::regrole, admin_option, inherit_option, set_option FROM pg_auth_members ORDER BY 1::text, 2::text;
SELECT datname, datdba::regrole, datacl FROM pg_database ORDER BY 1;
SELECT nspname, nspowner::regrole, nspacl FROM pg_namespace ORDER BY 1;
SELECT defaclrole::regrole, defaclnamespace, defaclobjtype, defaclacl FROM pg_default_acl ORDER BY 1::text, 2, 3;
SQL
}

PGENV="$(envf pg.env <<EOF
POSTGRES_DB=app
POSTGRES_USER=rdsadmin
POSTGRES_PASSWORD=$ROOT_PW
EOF
)"
docker run -d --name "$P" --env-file "$PGENV" postgres:17-alpine >/dev/null   # default logging, as on RDS
for _ in $(seq 1 60); do docker exec "$P" pg_isready -q -h 127.0.0.1 -d app 2>/dev/null && break; sleep 1; done
# the RDS layout: predefined NOLOGIN roles, a NOSUPERUSER master in rds_superuser that owns the database
MASTER_PW="$MASTER_PW" docker exec -i -e MASTER_PW "$P" psql -X -q -v ON_ERROR_STOP=1 -U rdsadmin -d app >/dev/null 2>&1 <<'SQL' || { echo "setup failed"; exit 1; }
\getenv mpw MASTER_PW
CREATE ROLE rds_superuser NOLOGIN;
CREATE ROLE rds_password NOLOGIN;
CREATE ROLE app_admin WITH LOGIN NOSUPERUSER INHERIT CREATEDB CREATEROLE NOREPLICATION PASSWORD :'mpw';
GRANT rds_superuser TO app_admin;
GRANT rds_password TO rds_superuser;
ALTER DATABASE app OWNER TO app_admin;
SQL

echo "== 1 premise"
out="$(q app_admin "$MASTER_PW" <<<"CREATE ROLE probe_bypass BYPASSRLS")"
grep -qi 'permission denied' <<<"$out" && ok "the master user can't create a BYPASSRLS role: $(head -1 <<<"$out" | cut -c1-110)" || bad "master created a BYPASSRLS role: $out"

echo "== 2 converge as the master user"
JOB="$(envf job.env <<EOF
PGUSER=app_admin
PGPASSWORD=$MASTER_PW
DB_MIGRATOR_USER=app_migrator
DB_MIGRATOR_PASSWORD=$MIG_PW
DB_APP_USER=app_runtime
DB_APP_PASSWORD=$APP_PW
EOF
)"
out="$(job "$JOB")"; rc=$?; echo "$out" > "$T/job1.out"
[ $rc -eq 0 ] && grep -q 'db-roles: converged with' <<<"$out" && ok "Job exits 0: $(grep -o 'converged with [0-9]* change(s)' <<<"$out")" || bad "Job rc=$rc: $out"
grep -q 'WARNING:.*app_migrator is NOBYPASSRLS' <<<"$out" && ok "Job warns that the migrator has no BYPASSRLS on managed Postgres" || bad "no NOBYPASSRLS warning: $out"
grep -q 'does not let app_admin turn statement logging off' <<<"$out" && ok "Job notes it can't switch statement logging off (parameter group must keep log_statement=none)" || bad "no logging note"
attrs="$(asu <<<"SELECT string_agg(rolname || ' super=' || rolsuper || ' bypassrls=' || rolbypassrls || ' login=' || rolcanlogin, '; ' ORDER BY rolname) FROM pg_roles WHERE rolname IN ('app_migrator', 'app_runtime')")"
[ "$attrs" = "app_migrator super=false bypassrls=false login=true; app_runtime super=false bypassrls=false login=true" ] && ok "roles: $attrs" || bad "role attributes: $attrs"
own="$(asu <<<"SELECT datdba::regrole FROM pg_database WHERE datname = 'app'")"
[ "$own" = app_migrator ] && ok "database app is owned by app_migrator" || bad "database owner: $own"
mem="$(asu <<<"SELECT pg_has_role('app_admin', 'app_migrator', 'SET') AND pg_has_role('app_admin', 'app_migrator', 'USAGE'), pg_has_role('app_runtime', 'app_migrator', 'MEMBER'), pg_has_role('app_runtime', 'rds_superuser', 'MEMBER')")"
[ "$mem" = "t|f|f" ] && ok "master administers the migrator; app_runtime is a member of neither app_migrator nor rds_superuser" || bad "memberships: $mem"
conn="$(asu <<<"SELECT has_database_privilege('public', 'app', 'CONNECT'), has_database_privilege('app_runtime', 'app', 'CONNECT'), has_schema_privilege('app_runtime', 'public', 'CREATE')")"
[ "$conn" = "f|t|f" ] && ok "PUBLIC can't connect; app_runtime can connect but not CREATE in public" || bad "privileges: $conn"

echo "== 3 idempotent"
s1="$(snapshot)"; out="$(job "$JOB")"; rc=$?; s2="$(snapshot)"; echo "$out" > "$T/job2.out"
[ $rc -eq 0 ] && grep -q 'db-roles: no changes' <<<"$out" && [ "$s1" = "$s2" ] && ok "second run: 'no changes', catalog snapshot identical ($s1)" || bad "second run rc=$rc: $out ($s1 -> $s2)"

echo "== 4 RLS with a NOBYPASSRLS migrator: the archetype's migrator policy (D-001)"
# The SQL under test is the skill's own block (databases/postgres.md, Row-Level Security): the helper
# app_grant_migrator() and the tenant table's ENABLE/FORCE/tenant policy/migrator policy, run as the migrator.
python3 "$REPO/tests/lib/rls_pattern.py" > "$T/rls.sql" || { bad "could not extract the RLS block from databases/postgres.md"; }
uuid_a=aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa; uuid_b=bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb
out="$( { echo "CREATE TABLE certificates (id bigserial PRIMARY KEY, tenant_id uuid NOT NULL, serial text NOT NULL);"
          cat "$T/rls.sql"
          echo "SELECT app_grant_migrator('certificates');"   # a re-run changes nothing (idempotent)
          echo "INSERT INTO certificates (tenant_id, serial) VALUES ('$uuid_a', 'a-1'), ('$uuid_b', 'b-1'), ('$uuid_b', 'b-2');"
          echo "UPDATE certificates SET serial = upper(serial);"   # cross-tenant backfill, no tenant set
          echo "SELECT count(*) || ' ' || string_agg(serial, ',' ORDER BY serial) FROM certificates;"; } | q app_migrator "$MIG_PW" | grep -v '^$')"
[ "$out" = "3 A-1,B-1,B-2" ] && ok "migrator (owner, NOBYPASSRLS, FORCE RLS): creates the table with the archetype block, seeds and backfills both tenants with no tenant set: $out" || bad "migrator backfill: $out"
pol="$(asu <<<"SELECT string_agg(polname || ' TO ' || array_to_string(polroles::regrole[], ',') || ' ' || pg_get_expr(polqual, polrelid), '; ' ORDER BY polname) FROM pg_policy WHERE polrelid = 'certificates'::regclass")"
[ "$pol" = "certificates_migrator_all TO app_migrator true; tenant_isolation TO - (tenant_id = (current_setting('app.current_tenant_id'::text))::uuid)" ] \
  && ok "policies: the migrator-only policy names app_migrator alone (from the table owner, no role in the SQL), the tenant policy is for everyone" || bad "policies: $pol"
out="$(q app_runtime "$APP_PW" <<<"BEGIN; SELECT set_config('app.current_tenant_id', '$uuid_b', true) \g /dev/null
SELECT string_agg(serial, ',' ORDER BY serial) FROM certificates; COMMIT;")"
[ "$out" = "B-1,B-2" ] && ok "app_runtime as tenant b sees only b's rows (B-1,B-2), no WHERE clause" || bad "app_runtime tenant b: $out"
out="$(q app_runtime "$APP_PW" <<<"SELECT count(*) FROM certificates")"; rc=$?
[ $rc -ne 0 ] && grep -q 'unrecognized configuration parameter' <<<"$out" && ok "app_runtime with no tenant set is refused (fails closed)" || bad "app_runtime no tenant: rc=$rc $out"
for stmt in "INSERT INTO certificates (tenant_id, serial) VALUES ('$uuid_b', 'planted')" "UPDATE certificates SET serial = 'x' WHERE tenant_id = '$uuid_b' RETURNING 1" \
            "SELECT app_grant_migrator('certificates')" "DROP POLICY certificates_migrator_all ON certificates" "ALTER POLICY certificates_migrator_all ON certificates TO PUBLIC"; do
  out="$(q app_runtime "$APP_PW" <<<"BEGIN; SELECT set_config('app.current_tenant_id', '$uuid_a', true) \g /dev/null
$stmt; COMMIT;")"; rc=$?
  { [ $rc -ne 0 ] || [ -z "$out" ]; } && ok "app_runtime as tenant a can't: $stmt ($(grep -oE 'violates row-level security|permission denied|must be owner' <<<"$out" | head -1 || echo 'no rows'))" || bad "app_runtime as a: $stmt -> $out"
done
[ "$(asu <<<"SELECT count(*) FROM certificates WHERE serial = 'planted' OR serial = 'x'")" = 0 ] && ok "no row of tenant b was written or changed by tenant a" || bad "tenant a wrote into b"
out="$(q app_runtime "$APP_PW" <<'SQL'
CREATE TABLE notes (id bigserial PRIMARY KEY, tenant text NOT NULL, body text NOT NULL);
SET ROLE app_migrator;
ALTER TABLE certificates NO FORCE ROW LEVEL SECURITY;
SET row_security = off; SELECT count(*) FROM certificates;
SQL
)"; rc=$?
[ $rc -ne 0 ] && ok "app_runtime can't CREATE, SET ROLE the migrator, lift FORCE or turn row_security off" || bad "app_runtime: $out"

# Without the migrator policy a NOBYPASSRLS migrator is blind: the reason D-001 exists (negative control)
out="$(q app_migrator "$MIG_PW" <<SQL
CREATE TABLE legacy (id bigserial PRIMARY KEY, tenant_id uuid NOT NULL, n int NOT NULL DEFAULT 0);
INSERT INTO legacy (tenant_id) VALUES ('$uuid_a'), ('$uuid_b');
ALTER TABLE legacy ENABLE ROW LEVEL SECURITY; ALTER TABLE legacy FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON legacy USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
WITH u AS (UPDATE legacy SET n = n + 1 RETURNING 1) SELECT count(*) FROM u;
SQL
)"
[ "$(tail -1 <<<"$out")" = 0 ] && ok "control: without the migrator policy the NOBYPASSRLS migrator's backfill updates 0 of 2 rows" || bad "control backfill: $out"

echo "== 4b the db-rls-check Job (as app_runtime) on this database"
RLSJOB="$(envf rls.env <<EOF
PGUSER=app_runtime
PGPASSWORD=$APP_PW
EOF
)"
rls() { docker run --rm --user 70 --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges \
          --env-file "$RLSJOB" -e PGHOST="$(ip)" -e PGDATABASE=app -e PGSSLMODE=prefer -v "$T/rls:/db-rls-check:ro" \
          postgres:17-alpine bash /db-rls-check/db-rls-check.sh 2>&1; }
out="$(rls)"; rc=$?
[ $rc -ne 0 ] && grep -q 'FAIL legacy has FORCE ROW LEVEL SECURITY but no migrator policy' <<<"$out" && ! grep -q 'FAIL.*certificates' <<<"$out" \
  && ok "db-rls-check fails the deploy on the table without a migrator policy (legacy), and only on it" || bad "db-rls-check on legacy: rc=$rc $out"
out="$(q app_migrator "$MIG_PW" <<<"SELECT app_grant_migrator('legacy'); WITH u AS (UPDATE legacy SET n = n + 1 RETURNING 1) SELECT count(*) FROM u;" | grep -v '^$')"
[ "$out" = 2 ] && ok "adopting D-001 on an existing table: app_grant_migrator('legacy') in a new migration, and the backfill reaches both rows" || bad "legacy after the helper: $out"
out="$(rls)"; rc=$?
[ $rc -eq 0 ] && grep -q 'db-rls-check: ok: 2 FORCE-RLS table(s)' <<<"$out" && ok "db-rls-check passes: $(tail -1 <<<"$out" | cut -c1-120)" || bad "db-rls-check clean: rc=$rc $out"
for leak in "CREATE POLICY leak ON certificates TO PUBLIC USING (true)" "CREATE POLICY leak ON certificates TO app_runtime USING (true)" \
            "CREATE POLICY leak ON certificates FOR SELECT USING (tenant_id IS NOT NULL)" "ALTER POLICY certificates_migrator_all ON certificates TO PUBLIC"; do
  q app_migrator "$MIG_PW" <<<"$leak" >/dev/null
  out="$(rls)"; rc=$?
  [ $rc -ne 0 ] && grep -q 'db-rls-check: FAIL' <<<"$out" && ok "db-rls-check refuses: $leak ($(grep -m1 -o 'FAIL [^(:]*' <<<"$out" | cut -c1-90))" || bad "db-rls-check let through: $leak -> $out"
  q app_migrator "$MIG_PW" <<<"DROP POLICY IF EXISTS leak ON certificates; SELECT app_grant_migrator('certificates');" >/dev/null
done
out="$(rls)"; [ $? -eq 0 ] && ok "db-rls-check passes again once the leaks are gone (app_grant_migrator re-points its policy to the owner)" || bad "db-rls-check after cleanup: $out"

echo "== 5 secrets"
logs="$(docker logs "$P" 2>&1)"; all="$logs $(cat "$T/job1.out" "$T/job2.out")"
leaks=0; for s in "$MASTER_PW" "$MIG_PW" "$APP_PW"; do grep -qF "$s" <<<"$all" && leaks=$((leaks+1)); done
[ "$leaks" = 0 ] && ok "no password in the server log ($(wc -l <<<"$logs" | tr -d ' ') lines) or Job output" || bad "$leaks password leak(s)"
WRONG="$(sed "s/^PGPASSWORD=.*/PGPASSWORD=wrongpassword000000000000/" "$JOB" | envf wrong.env)"
start=$(date +%s); out="$(job "$WRONG")"; rc=$?; took=$(( $(date +%s) - start ))
[ $rc -ne 0 ] && grep -q 'not retrying' <<<"$out" && [ "$took" -lt 20 ] && ok "wrong master password fails fast (${took}s, no retries)" || bad "wrong password: rc=$rc ${took}s $out"

echo "────────────────────────────────────────────"
echo "eks-db-roles.sh: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
