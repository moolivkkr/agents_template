-- HARNESS FIXTURE (tests/archetype-compile/go): gives the migration runner's
-- //go:embed migrations/*.sql pattern a file to match.
CREATE TABLE IF NOT EXISTS widgets (id UUID PRIMARY KEY);
