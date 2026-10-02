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
#   4 RLS          FORCE RLS + a policy TO the migrator: the migrator migrates and seeds across tenants;
#                  the app role sees one tenant, can't write another's, can't SET ROLE, ALTER, or lift RLS
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
mkdir "$T/cm" && cp "$TPL/deploy/k8s/base/db-roles.sh" "$T/cm/" && chmod 555 "$T/cm/db-roles.sh" && chmod 755 "$T" "$T/cm"

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

echo "== 4 RLS with a NOBYPASSRLS migrator"
out="$(q app_migrator "$MIG_PW" <<'SQL'
CREATE TABLE notes (id bigserial PRIMARY KEY, tenant text NOT NULL, body text NOT NULL);
ALTER TABLE notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE notes FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON notes USING (tenant = current_setting('app.tenant', true)) WITH CHECK (tenant = current_setting('app.tenant', true));
CREATE POLICY migrator_all ON notes TO app_migrator USING (true) WITH CHECK (true);
INSERT INTO notes (tenant, body) VALUES ('a', 'note a'), ('b', 'note b');
SELECT count(*) FROM notes;
SQL
)"
[ "$out" = 2 ] && ok "migrator (owner, FORCE RLS, policy TO app_migrator) migrates and seeds both tenants: sees 2 rows" || bad "migrator: $out"
out="$(q app_runtime "$APP_PW" <<<"SELECT count(*) FROM notes")"
[ "$out" = 0 ] && ok "app_runtime without a tenant sees 0 rows" || bad "app_runtime no tenant: $out"
out="$(q app_runtime "$APP_PW" <<<"SET app.tenant = 'a'; SELECT string_agg(body, ',') FROM notes")"
[ "$out" = "note a" ] && ok "app_runtime as tenant a sees only 'note a'" || bad "app_runtime tenant a: $out"
for stmt in "SET app.tenant = 'a'; INSERT INTO notes (tenant, body) VALUES ('b', 'x')" "SET ROLE app_migrator" \
            "ALTER TABLE notes NO FORCE ROW LEVEL SECURITY" "ALTER TABLE notes DISABLE ROW LEVEL SECURITY" "DROP POLICY tenant_isolation ON notes" \
            "SET row_security = off; SELECT count(*) FROM notes" "CREATE TABLE intruder (x int)"; do
  out="$(q app_runtime "$APP_PW" <<<"$stmt")"; rc=$?
  { [ $rc -ne 0 ] || grep -qiE 'error|denied|violates|must be owner' <<<"$out"; } && ok "app_runtime refused: $stmt" || bad "app_runtime allowed: $stmt -> $out"
done

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
