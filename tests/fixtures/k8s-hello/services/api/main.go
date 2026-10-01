// hello-api: a throwaway fixture that exercises the framework's k8s deploy flow end to end
// (build -> push -> roles -> migrate -> seed -> rollout -> smoke -> promote -> reset). Not a product.
//
// It runs under the lab's two database roles: migrate and seed as the MIGRATOR (owns the tables,
// NOSUPERUSER BYPASSRLS), serve as the APP role (owns nothing, NOBYPASSRLS), so the notes table's
// FORCE ROW LEVEL SECURITY really applies to the API: /api/tenants/{tenant}/notes has no WHERE clause.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

const schemaVersion = 2

// migrations are forward-only: each runs once, in order, in the transaction that records its version.
var migrations = []struct {
	version int
	sql     string
}{
	{1, `CREATE TABLE IF NOT EXISTS items (id serial PRIMARY KEY, name text UNIQUE NOT NULL)`},
	{2, `CREATE TABLE notes (id serial PRIMARY KEY, tenant_id text NOT NULL, body text NOT NULL, UNIQUE (tenant_id, body));
	     ALTER TABLE notes ENABLE ROW LEVEL SECURITY;
	     ALTER TABLE notes FORCE ROW LEVEL SECURITY;
	     CREATE POLICY tenant_isolation ON notes
	         USING (tenant_id = current_setting('app.current_tenant_id'))
	         WITH CHECK (tenant_id = current_setting('app.current_tenant_id'))`},
}

func main() {
	cmd := "serve"
	if len(os.Args) > 1 {
		cmd = os.Args[1]
	}
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	pool, err := pgxpool.New(ctx, os.Getenv("DATABASE_URL"))
	cancel()
	if err != nil {
		log.Fatalf("db: %v", err)
	}
	defer pool.Close()

	switch cmd {
	case "migrate":
		run(migrate, pool)
	case "seed":
		run(seed, pool)
	case "serve":
		serve(pool)
	default:
		log.Fatalf("unknown command %q (want serve|migrate|seed)", cmd)
	}
}

// run retries the first connection for up to 60s: a new pod can be refused briefly while the
// cluster's network-policy controller admits its IP, and the database may still be starting.
func run(fn func(context.Context, *pgxpool.Pool) error, pool *pgxpool.Pool) {
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()
	for deadline := time.Now().Add(60 * time.Second); ; time.Sleep(2 * time.Second) {
		err := pool.Ping(ctx)
		if err == nil {
			break
		}
		if strings.Contains(err.Error(), "SQLSTATE 28") || time.Now().After(deadline) { // 28xxx = auth: retrying won't help
			log.Fatalf("database unreachable: %v", err)
		}
		log.Printf("waiting for database: %v", err)
	}
	if err := fn(ctx, pool); err != nil {
		log.Fatal(err)
	}
}

// migrate is forward-only and idempotent. It refuses the app role (row-level security applies to it,
// and it can't create or alter anything anyway) and a superuser (tables it created would belong to the
// superuser, out of the app role's default privileges): only the migrator migrates.
func migrate(ctx context.Context, pool *pgxpool.Pool) error {
	var who string
	var super, bypass bool
	if err := pool.QueryRow(ctx, `SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user`).Scan(&who, &super, &bypass); err != nil {
		return err
	}
	if super || !bypass {
		return fmt.Errorf("migrate must run as the migration role (NOSUPERUSER BYPASSRLS, owner of the tables), not %q: DATABASE_URL has the wrong credentials", who)
	}
	return pgx.BeginFunc(ctx, pool, func(tx pgx.Tx) error {
		if _, err := tx.Exec(ctx, `SELECT pg_advisory_xact_lock(7140001)`); err != nil { // one migrate at a time
			return err
		}
		if _, err := tx.Exec(ctx, `CREATE TABLE IF NOT EXISTS schema_migrations (version int PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())`); err != nil {
			return err
		}
		for _, m := range migrations {
			var done bool
			if err := tx.QueryRow(ctx, `SELECT EXISTS (SELECT 1 FROM schema_migrations WHERE version = $1)`, m.version).Scan(&done); err != nil {
				return err
			}
			if done {
				continue
			}
			if _, err := tx.Exec(ctx, m.sql); err != nil {
				return fmt.Errorf("migration %d: %w", m.version, err)
			}
			if _, err := tx.Exec(ctx, `INSERT INTO schema_migrations (version) VALUES ($1)`, m.version); err != nil {
				return err
			}
			log.Printf("applied migration %d", m.version)
		}
		log.Printf("migrated to schema version %d as %s", schemaVersion, who)
		return nil
	})
}

// seed loads static reference data; safe to run on every deploy. As the migrator (BYPASSRLS) it writes
// every tenant's rows without a tenant context; as the app role the notes insert would be refused.
func seed(ctx context.Context, pool *pgxpool.Pool) error {
	_, err := pool.Exec(ctx, `
		INSERT INTO items (name) VALUES ('alpha'), ('beta'), ('gamma') ON CONFLICT (name) DO NOTHING;
		INSERT INTO notes (tenant_id, body) VALUES ('acme', 'acme roadmap'), ('globex', 'globex payroll') ON CONFLICT (tenant_id, body) DO NOTHING;`)
	if err == nil {
		log.Print("seeded reference data")
	}
	return err
}

func serve(pool *pgxpool.Pool) {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, _ *http.Request) { w.Write([]byte("ok\n")) })
	mux.HandleFunc("GET /readyz", func(w http.ResponseWriter, r *http.Request) {
		var v int
		if err := pool.QueryRow(r.Context(), `SELECT coalesce(max(version), 0) FROM schema_migrations`).Scan(&v); err != nil || v < schemaVersion {
			http.Error(w, "not ready", http.StatusServiceUnavailable)
			return
		}
		w.Write([]byte("ready\n"))
	})
	mux.HandleFunc("GET /api/version", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, map[string]string{"git_sha": os.Getenv("GIT_SHA"), "env": os.Getenv("APP_ENV")})
	})
	mux.HandleFunc("GET /api/items", func(w http.ResponseWriter, r *http.Request) {
		rows, err := pool.Query(r.Context(), `SELECT name FROM items ORDER BY id`)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		defer rows.Close()
		names := []string{}
		for rows.Next() {
			var n string
			if err := rows.Scan(&n); err != nil {
				http.Error(w, err.Error(), http.StatusInternalServerError)
				return
			}
			names = append(names, n)
		}
		writeJSON(w, map[string]any{"items": names})
	})
	// No WHERE clause: row-level security scopes the rows, because the API connects as the app role.
	// Connected as the migrator or a superuser it would return every tenant's notes. (The tenant comes
	// from the path only because this is a fixture; a real service takes it from the verified token.)
	mux.HandleFunc("GET /api/tenants/{tenant}/notes", func(w http.ResponseWriter, r *http.Request) {
		var notes []string
		err := pgx.BeginFunc(r.Context(), pool, func(tx pgx.Tx) error {
			if _, err := tx.Exec(r.Context(), `SELECT set_config('app.current_tenant_id', $1, true)`, r.PathValue("tenant")); err != nil {
				return err
			}
			rows, err := tx.Query(r.Context(), `SELECT body FROM notes ORDER BY id`)
			if err != nil {
				return err
			}
			notes, err = pgx.CollectRows(rows, pgx.RowTo[string])
			return err
		})
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		if notes == nil {
			notes = []string{}
		}
		writeJSON(w, map[string]any{"tenant": r.PathValue("tenant"), "notes": notes})
	})
	srv := &http.Server{Addr: ":8080", Handler: mux, ReadHeaderTimeout: 5 * time.Second}
	log.Printf("listening on :8080 (env=%s sha=%s)", os.Getenv("APP_ENV"), os.Getenv("GIT_SHA"))
	log.Fatal(srv.ListenAndServe())
}

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(v)
}
