-- HARNESS STUB (tests/archetype-compile/go, units.json) — not skill-pack code.
-- The init script testing/testcontainers.md's NewTestDB passes to postgres.WithInitScripts
-- ("../../migrations/init.sql" from the helper's package): the table its callers query.
CREATE TABLE users (
    id   bigserial PRIMARY KEY,
    name text NOT NULL
);
