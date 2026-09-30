// hello-api: a throwaway fixture that exercises the framework's k8s deploy flow end to end
// (build -> push -> migrate -> seed -> rollout -> smoke -> promote -> reset). Not a product.
package main

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

const schemaVersion = 1

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

// migrate is forward-only and idempotent.
func migrate(ctx context.Context, pool *pgxpool.Pool) error {
	_, err := pool.Exec(ctx, `
		CREATE TABLE IF NOT EXISTS schema_migrations (version int PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());
		CREATE TABLE IF NOT EXISTS items (id serial PRIMARY KEY, name text UNIQUE NOT NULL);
		INSERT INTO schema_migrations (version) VALUES (1) ON CONFLICT DO NOTHING;`)
	if err == nil {
		log.Printf("migrated to schema version %d", schemaVersion)
	}
	return err
}

// seed loads static reference data; safe to run on every deploy.
func seed(ctx context.Context, pool *pgxpool.Pool) error {
	_, err := pool.Exec(ctx, `INSERT INTO items (name) VALUES ('alpha'), ('beta'), ('gamma') ON CONFLICT (name) DO NOTHING`)
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
	srv := &http.Server{Addr: ":8080", Handler: mux, ReadHeaderTimeout: 5 * time.Second}
	log.Printf("listening on :8080 (env=%s sha=%s)", os.Getenv("APP_ENV"), os.Getenv("GIT_SHA"))
	log.Fatal(srv.ListenAndServe())
}

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(v)
}
