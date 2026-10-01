

# ── harness: two tests through the doc's `db` fixture — each starts from an empty database ──────────
from sqlalchemy import Engine, func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from harness_stubs.sqlite_models import Note  # noqa: E402


def test_harness_writes_a_row(db: Engine) -> None:
    with Session(db) as s:
        s.add(Note(body="hello"))
        s.commit()
        assert s.scalar(select(func.count()).select_from(Note)) == 1


def test_harness_next_test_starts_empty(db: Engine) -> None:
    with Session(db) as s:
        assert s.scalar(select(func.count()).select_from(Note)) == 0
