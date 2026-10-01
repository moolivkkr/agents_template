#!/usr/bin/env bash
# db-roles.sh — create or converge the app database's two roles. One script, two callers (ConfigMap db-roles):
#   1. Postgres's /docker-entrypoint-initdb.d: once, on an EMPTY data directory, over the init server's
#      unix socket as POSTGRES_USER (postgres.yaml).
#   2. the db-roles Job: on every deploy, before db-migrate, as the bootstrap superuser over TCP
#      (PGHOST=postgres; jobs.yaml). This is what converges a volume initialised before the roles
#      existed (the old one-superuser layout) or one whose roles drifted, without a reset.
#
# Roles (names and passwords from the db-credentials secret):
#   DB_MIGRATOR_USER  owns the database, its schemas and every object in them; runs migrate and seed.
#                     LOGIN NOSUPERUSER BYPASSRLS: data migrations and seeds reach every tenant's rows
#                     without lifting FORCE ROW LEVEL SECURITY, so they take no table-wide exclusive locks.
#   DB_APP_USER       the running service. LOGIN NOSUPERUSER NOBYPASSRLS, owns nothing: CONNECT, USAGE on
#                     schema public, and DML through ALTER DEFAULT PRIVILEGES FOR ROLE <migrator> (tables:
#                     SELECT/INSERT/UPDATE/DELETE, sequences: USAGE/SELECT), so FORCE RLS applies to it.
#   The bootstrap superuser is used only by Postgres itself and by this script.
#
# Idempotent: it checks before it changes anything, passwords included (it tries a login with the
# password before resetting it), so on a converged database it prints "no changes" and alters nothing.
# It never prints or logs a password: values come from the environment (psql \getenv, never argv), and
# the session that sets them turns server statement logging off first. Needs psql 15+ (\getenv).
set -euo pipefail

for v in DB_MIGRATOR_USER DB_MIGRATOR_PASSWORD DB_APP_USER DB_APP_PASSWORD; do
  [ -n "${!v:-}" ] || { echo "db-roles: $v is not set" >&2; exit 1; }
done
export PGUSER="${PGUSER:-${POSTGRES_USER:-postgres}}" PGDATABASE="${PGDATABASE:-${POSTGRES_DB:-app}}"
psql_su() { psql -X -q -w -v ON_ERROR_STOP=1 "$@"; }
major="$(psql --version | sed -nE 's/^psql \(PostgreSQL\) ([0-9]+).*/\1/p')"
[ "${major:-0}" -ge 15 ] || { echo "db-roles: needs psql 15+ for \\getenv (found '$(psql --version)')" >&2; exit 1; }

# Job: a new pod's first connections can be refused for a few seconds (lab rule 4). Retry those for
# ~60 s; an authentication error is fatal at once, since retrying won't fix a wrong password.
if [ -n "${PGHOST:-}" ]; then
  for i in $(seq 1 30); do
    if err="$(psql_su -tAc 'SELECT 1' 2>&1 >/dev/null)"; then break; fi
    case "$err" in
      *"password authentication failed"*|*"does not exist"*|*"no pg_hba.conf entry"*)
        echo "db-roles: superuser login refused, not retrying (SQLSTATE 28xxx/3D000): $err" >&2; exit 1 ;;
    esac
    [ "$i" -lt 30 ] || { echo "db-roles: database unreachable after 60 s: $err" >&2; exit 1; }
    echo "db-roles: waiting for the database: $err" >&2; sleep 2
  done
fi

# Roles, memberships, database, schema public, default privileges, and objects created before the
# migrator existed. NOTICE lines name every change; the last line of stdout is the number of changes.
sql_changes="$(psql_su -tA <<'SQL'
\getenv migrator DB_MIGRATOR_USER
\getenv app DB_APP_USER
SELECT set_config('db_roles.migrator', :'migrator', false) AS _m, set_config('db_roles.app', :'app', false) AS _a \gset
DO $do$
DECLARE
  m      text := current_setting('db_roles.migrator');
  a      text := current_setting('db_roles.app');
  db     text := current_database();
  m_oid  oid;
  a_oid  oid;
  r      record;
  s      record;
  attrs  text;
  n      int := 0;
BEGIN
  IF NOT (SELECT rolsuper FROM pg_roles WHERE rolname = current_user) THEN
    RAISE EXCEPTION 'db-roles: must run as a superuser (connected as %)', current_user;
  END IF;
  IF m = a OR m IN ('', current_user) OR a IN ('', current_user) THEN
    RAISE EXCEPTION 'db-roles: the migrator (%), app (%) and superuser (%) must be three different roles', m, a, current_user;
  END IF;

  -- 1. the two roles, with exactly these attributes
  FOR r IN SELECT * FROM (VALUES (m, true), (a, false)) v(name, bypass) LOOP
    attrs := 'LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION ' || CASE WHEN r.bypass THEN 'BYPASSRLS' ELSE 'NOBYPASSRLS' END;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = r.name) THEN
      EXECUTE format('CREATE ROLE %I %s', r.name, attrs);
      RAISE NOTICE 'db-roles: created role % (%)', r.name, attrs; n := n + 1;
    ELSIF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = r.name AND rolcanlogin AND NOT rolsuper AND NOT rolcreatedb
                        AND NOT rolcreaterole AND NOT rolreplication AND rolbypassrls = r.bypass) THEN
      EXECUTE format('ALTER ROLE %I %s', r.name, attrs);
      RAISE NOTICE 'db-roles: reset role % to %', r.name, attrs; n := n + 1;
    END IF;
  END LOOP;
  m_oid := (SELECT oid FROM pg_roles WHERE rolname = m);
  a_oid := (SELECT oid FROM pg_roles WHERE rolname = a);

  -- 2. neither role can SET ROLE into something stronger: the app role into the migrator or any
  --    BYPASSRLS/superuser role, the migrator into a superuser
  FOR r IN SELECT g.rolname AS grp, u.rolname AS member, gr.rolname AS grantor
           FROM pg_auth_members am JOIN pg_roles g ON g.oid = am.roleid JOIN pg_roles u ON u.oid = am.member
           JOIN pg_roles gr ON gr.oid = am.grantor
           WHERE (am.member = a_oid AND (am.roleid = m_oid OR g.rolsuper OR g.rolbypassrls))
              OR (am.member = m_oid AND g.rolsuper) LOOP
    EXECUTE format('REVOKE %I FROM %I GRANTED BY %I', r.grp, r.member, r.grantor);
    RAISE NOTICE 'db-roles: revoked membership of % in %', r.member, r.grp; n := n + 1;
  END LOOP;

  -- 3. the database belongs to the migrator; only roles granted CONNECT may connect (no TEMP for PUBLIC)
  IF (SELECT datdba FROM pg_database WHERE datname = db) <> m_oid THEN
    EXECUTE format('ALTER DATABASE %I OWNER TO %I', db, m);
    RAISE NOTICE 'db-roles: database % now owned by %', db, m; n := n + 1;
  END IF;
  IF has_database_privilege('public', db, 'CONNECT') OR has_database_privilege('public', db, 'TEMPORARY') THEN
    EXECUTE format('REVOKE CONNECT, TEMPORARY ON DATABASE %I FROM PUBLIC', db);
    RAISE NOTICE 'db-roles: revoked CONNECT, TEMPORARY on database % from PUBLIC', db; n := n + 1;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_database d, aclexplode(d.datacl) x
                 WHERE d.datname = db AND x.grantee = a_oid AND x.privilege_type = 'CONNECT') THEN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO %I', db, a);
    RAISE NOTICE 'db-roles: granted CONNECT on database % to %', db, a; n := n + 1;
  END IF;

  -- 4. schema public: the migrator creates in it (it owns the database, so on 15+ it owns public too),
  --    the app role only uses it
  IF has_schema_privilege('public', 'public', 'CREATE') THEN
    REVOKE CREATE ON SCHEMA public FROM PUBLIC;
    RAISE NOTICE 'db-roles: revoked CREATE on schema public from PUBLIC'; n := n + 1;
  END IF;
  IF NOT has_schema_privilege(m, 'public', 'CREATE') THEN
    EXECUTE format('GRANT USAGE, CREATE ON SCHEMA public TO %I', m);
    RAISE NOTICE 'db-roles: granted USAGE, CREATE on schema public to %', m; n := n + 1;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_namespace ns, aclexplode(ns.nspacl) x
                 WHERE ns.nspname = 'public' AND x.grantee = a_oid AND x.privilege_type = 'USAGE') THEN
    EXECUTE format('GRANT USAGE ON SCHEMA public TO %I', a);
    RAISE NOTICE 'db-roles: granted USAGE on schema public to %', a; n := n + 1;
  END IF;

  -- 5. whatever the migrator creates in public, the app role can read and write (not alter or drop)
  IF (SELECT count(DISTINCT x.privilege_type) FROM pg_default_acl d, aclexplode(d.defaclacl) x
      WHERE d.defaclrole = m_oid AND d.defaclnamespace = 'public'::regnamespace AND d.defaclobjtype = 'r'
        AND x.grantee = a_oid AND x.privilege_type IN ('SELECT', 'INSERT', 'UPDATE', 'DELETE')) < 4 THEN
    EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO %I', m, a);
    RAISE NOTICE 'db-roles: default privileges: tables % creates in public grant SELECT, INSERT, UPDATE, DELETE to %', m, a; n := n + 1;
  END IF;
  IF (SELECT count(DISTINCT x.privilege_type) FROM pg_default_acl d, aclexplode(d.defaclacl) x
      WHERE d.defaclrole = m_oid AND d.defaclnamespace = 'public'::regnamespace AND d.defaclobjtype = 'S'
        AND x.grantee = a_oid AND x.privilege_type IN ('USAGE', 'SELECT')) < 2 THEN
    EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO %I', m, a);
    RAISE NOTICE 'db-roles: default privileges: sequences % creates in public grant USAGE, SELECT to %', m, a; n := n + 1;
  END IF;

  -- 6. objects owned by anyone else (made before the migrator existed, e.g. by the old single
  --    superuser): the migrator takes them over, and the app role gets what step 5 would have given it.
  --    Extension members stay with the extension; objects internal to another (a range's constructor)
  --    and sequences owned by a column move with their parent.
  FOR r IN
    WITH ns AS (SELECT oid FROM pg_namespace WHERE nspname <> 'information_schema' AND nspname NOT LIKE 'pg\_%'),
    owned(classid, objid, owner) AS (
      SELECT 'pg_namespace'::regclass, oid, nspowner FROM pg_namespace WHERE oid IN (SELECT oid FROM ns) AND nspname <> 'public'
      UNION ALL
      SELECT 'pg_class'::regclass, c.oid, c.relowner FROM pg_class c
      WHERE c.relnamespace IN (SELECT oid FROM ns) AND c.relkind IN ('r', 'p', 'v', 'm', 'f', 'S')
        AND NOT (c.relkind = 'S' AND EXISTS (SELECT FROM pg_depend d WHERE d.classid = 'pg_class'::regclass
                   AND d.objid = c.oid AND d.refclassid = 'pg_class'::regclass AND d.deptype IN ('a', 'i')))
      UNION ALL
      SELECT 'pg_type'::regclass, t.oid, t.typowner FROM pg_type t
      WHERE t.typnamespace IN (SELECT oid FROM ns)
        AND (t.typtype IN ('e', 'd', 'r') OR (t.typtype = 'c' AND (SELECT relkind FROM pg_class WHERE oid = t.typrelid) = 'c'))
      UNION ALL SELECT 'pg_proc'::regclass, oid, proowner FROM pg_proc WHERE pronamespace IN (SELECT oid FROM ns)
      UNION ALL SELECT 'pg_statistic_ext'::regclass, oid, stxowner FROM pg_statistic_ext WHERE stxnamespace IN (SELECT oid FROM ns)
      UNION ALL SELECT 'pg_collation'::regclass, oid, collowner FROM pg_collation WHERE collnamespace IN (SELECT oid FROM ns)
      UNION ALL SELECT 'pg_conversion'::regclass, oid, conowner FROM pg_conversion WHERE connamespace IN (SELECT oid FROM ns)
      UNION ALL SELECT 'pg_operator'::regclass, oid, oprowner FROM pg_operator WHERE oprnamespace IN (SELECT oid FROM ns)
      UNION ALL SELECT 'pg_opfamily'::regclass, oid, opfowner FROM pg_opfamily WHERE opfnamespace IN (SELECT oid FROM ns)
      UNION ALL SELECT 'pg_opclass'::regclass, oid, opcowner FROM pg_opclass WHERE opcnamespace IN (SELECT oid FROM ns)
      UNION ALL SELECT 'pg_ts_config'::regclass, oid, cfgowner FROM pg_ts_config WHERE cfgnamespace IN (SELECT oid FROM ns)
      UNION ALL SELECT 'pg_ts_dict'::regclass, oid, dictowner FROM pg_ts_dict WHERE dictnamespace IN (SELECT oid FROM ns)
    )
    SELECT o.classid, o.objid, i.type, i.identity
    FROM owned o, pg_identify_object(o.classid, o.objid, 0) i
    WHERE o.owner <> m_oid
      AND NOT EXISTS (SELECT FROM pg_depend d WHERE d.classid = o.classid AND d.objid = o.objid AND d.objsubid = 0
                        AND d.deptype IN ('e', 'i'))   -- objsubid 0: a partition key column depends 'i' on its own table
    ORDER BY o.classid <> 'pg_namespace'::regclass, i.type = 'sequence', i.identity
  LOOP
    EXECUTE format('ALTER %s %s OWNER TO %I',
                   CASE r.type WHEN 'composite type' THEN 'TYPE' WHEN 'statistics object' THEN 'STATISTICS' ELSE upper(r.type) END,
                   r.identity, m);
    IF r.type = 'schema' THEN
      EXECUTE format('GRANT USAGE ON SCHEMA %s TO %I', r.identity, a);
    ELSIF r.type = 'sequence' THEN
      EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE %s TO %I', r.identity, a);
    ELSIF r.type IN ('table', 'view', 'materialized view', 'foreign table') THEN
      EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON %s TO %I', r.identity, a);
      FOR s IN SELECT format('%I.%I', sn.nspname, sc.relname) AS name
               FROM pg_depend d JOIN pg_class sc ON sc.oid = d.objid JOIN pg_namespace sn ON sn.oid = sc.relnamespace
               WHERE d.classid = 'pg_class'::regclass AND d.refclassid = 'pg_class'::regclass AND d.refobjid = r.objid
                 AND d.deptype IN ('a', 'i') AND sc.relkind = 'S' LOOP
        EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE %s TO %I', s.name, a);
      END LOOP;
    END IF;
    RAISE NOTICE 'db-roles: % % now owned by %', r.type, r.identity, m; n := n + 1;
  END LOOP;

  PERFORM set_config('db_roles.changes', n::text, false);
END
$do$;
SELECT current_setting('db_roles.changes');
SQL
)"
sql_changes="$(printf '%s\n' "$sql_changes" | tail -1)"

# Passwords. Over TCP to a non-loopback address a login proves the current one; the init server's
# socket (and loopback) are trusted by pg_hba, so there the password is always (re)set.
login_ok() {
  case "${PGHOST:-}" in ''|/*|localhost|127.*|::1) return 1 ;; esac
  PGPASSWORD="$2" psql -X -w -h "$PGHOST" -U "$1" -d "$PGDATABASE" -tAc 'SELECT 1' >/dev/null 2>&1
}
set_password() {
  ROLE_NAME="$1" ROLE_PASSWORD="$2" psql_su <<'SQL'
SET log_statement = 'none';
SET log_min_error_statement = 'panic';
SET log_min_duration_statement = -1;
SET log_min_duration_sample = -1;
SET log_transaction_sample_rate = 0;
SET log_error_verbosity = 'terse';
\set VERBOSITY terse
\set SHOW_CONTEXT never
\getenv role_name ROLE_NAME
\getenv role_password ROLE_PASSWORD
ALTER ROLE :"role_name" PASSWORD :'role_password';
SQL
}
pw_changes=0
for role in MIGRATOR APP; do
  user_var="DB_${role}_USER"; pw_var="DB_${role}_PASSWORD"
  if ! login_ok "${!user_var}" "${!pw_var}"; then
    set_password "${!user_var}" "${!pw_var}"
    echo "db-roles: set the password of ${!user_var}" >&2; pw_changes=$((pw_changes + 1))
  fi
done

total=$((sql_changes + pw_changes))
if [ "$total" -eq 0 ]; then
  echo "db-roles: no changes (already converged): ${DB_MIGRATOR_USER} owns ${PGDATABASE}, ${DB_APP_USER} is RLS-bound"
else
  echo "db-roles: converged with $total change(s): ${DB_MIGRATOR_USER} owns ${PGDATABASE}, ${DB_APP_USER} is RLS-bound"
fi
