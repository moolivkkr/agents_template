#!/usr/bin/env bash
# db-rls-check.sh — after migrate and seed, prove from the RUNTIME role's own session that row-level
# security still confines it (decision D-001, skill databases/postgres.md "The migrator policy").
# Run by the db-rls-check Job (jobs.yaml) as DB_APP_USER, the role every service connects as; it holds no
# other credentials (deploylib.py db-access refuses a render in which it does). Read-only: one
# BEGIN READ ONLY transaction that is rolled back, no SET outside it (safe through a transaction pooler).
#
# Facts it proves, for every table in a non-system schema with FORCE ROW LEVEL SECURITY:
#   1 the runtime role is NOSUPERUSER NOBYPASSRLS, owns no such table and is not a member of its owner
#     (otherwise RLS does not bind it, or it can SET ROLE out of it)
#   2 the table has the migrator policy: PERMISSIVE, FOR ALL, TO exactly the table owner (= the migrator,
#     which owns every object: db-roles.sh), USING (true) WITH CHECK (true). Without it a NOBYPASSRLS
#     migrator (RDS/Aurora) sees no rows in cross-tenant migrations and seeds
#   3 no policy that grants every row (USING or WITH CHECK is `true`) applies to anyone but the owner:
#     one TO PUBLIC, TO the runtime role or TO a role it is a member of hands it every tenant's rows
#   4 with no tenant set, the runtime role reads no row: the query either fails (the tenant policy's
#     current_setting() has no default) or returns 0 rows
# Any violation prints "db-rls-check: FAIL ..." and the Job exits 1, which fails the deploy.
set -euo pipefail
: "${PGUSER:?db-rls-check: PGUSER (DB_APP_USER) is not set}"
export PGDATABASE="${PGDATABASE:-app}"
psql_app() { psql -X -q -w -tA -v ON_ERROR_STOP=1 "$@"; }

# Job: a new pod's first connections can be refused for a few seconds (lab rule 4). Retry those for
# ~60 s; an authentication error is fatal at once, since retrying won't fix a wrong password.
if [ -n "${PGHOST:-}" ]; then
  for i in $(seq 1 30); do
    if err="$(psql_app -c 'SELECT 1' 2>&1 >/dev/null)"; then break; fi
    case "$err" in
      *"password authentication failed"*|*"does not exist"*|*"no pg_hba.conf entry"*)
        echo "db-rls-check: login refused, not retrying (SQLSTATE 28xxx/3D000): $err" >&2; exit 1 ;;
    esac
    [ "$i" -lt 30 ] || { echo "db-rls-check: database unreachable after 60 s: $err" >&2; exit 1; }
    echo "db-rls-check: waiting for the database: $err" >&2; sleep 2
  done
fi

check_sql() {
  cat <<'SQL'
\set VERBOSITY terse
BEGIN READ ONLY;
DO $do$
DECLARE
  me     oid := (SELECT oid FROM pg_roles WHERE rolname = current_user);
  r      record;
  p      record;
  n      bigint;
  bad    int := 0;
  tables int := 0;
BEGIN
  IF (SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE oid = me) THEN
    RAISE WARNING 'db-rls-check: FAIL the runtime role % is SUPERUSER or BYPASSRLS: row-level security does not apply to it', current_user;
    bad := bad + 1;
  END IF;
  FOR r IN SELECT c.oid, c.oid::regclass AS tbl, c.relowner, pg_get_userbyid(c.relowner) AS owner
           FROM pg_class c JOIN pg_namespace ns ON ns.oid = c.relnamespace
           WHERE c.relkind IN ('r', 'p') AND c.relforcerowsecurity
             AND ns.nspname <> 'information_schema' AND ns.nspname NOT LIKE 'pg\_%'
           ORDER BY 2::text LOOP
    tables := tables + 1;
    -- 1 the runtime role must not be, or be able to become, the owner
    IF r.relowner = me OR pg_has_role(me, r.relowner, 'MEMBER') THEN
      RAISE WARNING 'db-rls-check: FAIL % is owned by %, which the runtime role % is or can become: it can turn RLS off', r.tbl, r.owner, current_user;
      bad := bad + 1;
    END IF;
    -- 2 the migrator policy (D-001)
    IF NOT EXISTS (SELECT FROM pg_policy pol WHERE pol.polrelid = r.oid AND pol.polpermissive AND pol.polcmd = '*'
                     AND pol.polroles = ARRAY[r.relowner]
                     AND pg_get_expr(pol.polqual, pol.polrelid) = 'true'
                     AND pg_get_expr(pol.polwithcheck, pol.polrelid) = 'true') THEN
      RAISE WARNING 'db-rls-check: FAIL % has FORCE ROW LEVEL SECURITY but no migrator policy (PERMISSIVE FOR ALL TO % USING (true) WITH CHECK (true)): the migration that created it must call app_grant_migrator(''%'') (D-001)', r.tbl, r.owner, r.tbl;
      bad := bad + 1;
    END IF;
    -- 3 every policy that grants every row is for the owner alone
    FOR p IN SELECT pol.polname, pol.polroles,
                    (SELECT string_agg(CASE WHEN x = 0 THEN 'PUBLIC' ELSE pg_get_userbyid(x) END, ', ') FROM unnest(pol.polroles) x) AS roles
             FROM pg_policy pol
             WHERE pol.polrelid = r.oid AND pol.polpermissive
               AND (pg_get_expr(pol.polqual, pol.polrelid) = 'true' OR pg_get_expr(pol.polwithcheck, pol.polrelid) = 'true')
               AND pol.polroles <> ARRAY[r.relowner] LOOP
      RAISE WARNING 'db-rls-check: FAIL policy % on % grants every row TO % (only the table owner % may hold an unconditional policy)%',
        p.polname, r.tbl, p.roles, r.owner,
        CASE WHEN 0 = ANY (p.polroles) OR EXISTS (SELECT FROM unnest(p.polroles) x WHERE x <> 0 AND pg_has_role(me, x, 'MEMBER'))
             THEN format(': the runtime role %s gets every tenant''s rows', current_user) ELSE '' END;
      bad := bad + 1;
    END LOOP;
    -- 4 behaviour: no tenant set, no rows
    IF has_table_privilege(me, r.oid, 'SELECT') THEN
      BEGIN
        EXECUTE format('SELECT count(*) FROM %s', r.tbl) INTO n;
      EXCEPTION WHEN OTHERS THEN
        n := 0;   -- the tenant policy refused (e.g. 42704: no tenant setting): confined
      END;
      IF n > 0 THEN
        RAISE WARNING 'db-rls-check: FAIL the runtime role % reads % row(s) of % with no tenant set', current_user, n, r.tbl;
        bad := bad + 1;
      END IF;
    END IF;
  END LOOP;
  PERFORM set_config('db_rls_check.result', bad || ' ' || tables, true);
END
$do$;
SELECT current_setting('db_rls_check.result');
ROLLBACK;
SQL
}
res="$(check_sql | psql_app 2>&1)" || { printf '%s\n' "$res" >&2; echo "db-rls-check: the check itself failed" >&2; exit 1; }
printf '%s\n' "$res" | grep 'db-rls-check: FAIL' | sed 's/^.*\(db-rls-check: FAIL\)/\1/' >&2 || true
last="$(printf '%s\n' "$res" | tail -1)"
bad="${last%% *}" tables="${last#* }"
case "$bad$tables" in *[!0-9]*|'') printf '%s\n' "$res" >&2; echo "db-rls-check: unexpected output" >&2; exit 1 ;; esac
if [ "$bad" -gt 0 ]; then
  echo "db-rls-check: $bad problem(s) in $tables FORCE-RLS table(s) as $PGUSER" >&2; exit 1
fi
echo "db-rls-check: ok: $tables FORCE-RLS table(s); $PGUSER is RLS-bound, reads no row without a tenant, and every unconditional policy is the owner's (migrator) alone"
