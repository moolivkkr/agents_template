-- HARNESS-ONLY tables. No archetype migration defines these; observability-rust.md and
-- performance-rust.md query them with sqlx::query!/query_as!, so their columns follow those samples
-- (and the harness stub structs in stubs/obs_app.rs and stubs/perf_app.rs). A query checked against
-- these tables proves the macro call is well-formed and type-consistent with the sample's own structs —
-- not that it matches any real project's schema.
CREATE TABLE IF NOT EXISTS orders (
    id          TEXT PRIMARY KEY,
    tenant_id   TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    total       BIGINT NOT NULL,       -- minor units
    status      TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS order_items (
    id          TEXT PRIMARY KEY,
    order_id    TEXT NOT NULL REFERENCES orders (id),
    tenant_id   TEXT NOT NULL,
    product_id  TEXT NOT NULL,
    quantity    INT NOT NULL,
    price       BIGINT NOT NULL        -- minor units
);
