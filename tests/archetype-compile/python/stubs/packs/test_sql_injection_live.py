"""harness (--live): core/security-owasp.md's WRONG/RIGHT pair run against PostgreSQL through psycopg 3."""
from __future__ import annotations

import psycopg
import pytest

from docs_fragments.sql_injection import query_user


@pytest.fixture
def cursor(pg_dsn: str):
    with psycopg.connect(pg_dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS users")
        cur.execute("CREATE TABLE users (id int PRIMARY KEY, name text NOT NULL)")
        cur.execute("INSERT INTO users VALUES (1, 'alice'), (2, 'bob')")
        yield cur


def test_both_statements_run(cursor: psycopg.Cursor) -> None:
    query_user(cursor, "1")  # the WRONG line, then the RIGHT line
    assert cursor.fetchall() == [(1, "alice")]


def test_bound_parameter_is_data_not_sql(cursor: psycopg.Cursor) -> None:
    # The f-string line splices "0 OR 1=1" into the SQL (every row matches); the bound parameter is a
    # value for an int column, so PostgreSQL rejects it instead of running it.
    with pytest.raises(psycopg.errors.InvalidTextRepresentation):
        query_user(cursor, "0 OR 1=1")
    cursor.execute(f"SELECT * FROM users WHERE id = {'0 OR 1=1'}")
    assert len(cursor.fetchall()) == 2
