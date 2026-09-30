# harness smoke: exercise crud-repository-python.md's WidgetRepository without a database. The session
# is a fake that compiles each statement with the real PostgreSQL dialect, so statement construction
# (cursor predicate, filters, ordering) runs for real; the SQL itself is only checked in --live mode.
import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError, OperationalError

from app.domain.base import ListFilters
from app.errors import BusinessRuleError, ConflictError, InternalError, UnavailableError, ValidationFailedError
from app.repositories.widget import WidgetRepository

R = WidgetRepository

# opaque cursor round trip; a garbage cursor is a 400 on `cursor`
wid = uuid4()
c = R._encode_cursor(datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc), wid)
sv, cid = R._decode_cursor(c)
assert cid == wid, (cid, wid)
try:
    R._decode_cursor("not-a-cursor")
    raise AssertionError("a garbage cursor was accepted")
except ValidationFailedError as exc:
    assert exc.details[0].field == "cursor"


class _PgErr(Exception):
    def __init__(self, sqlstate: str) -> None:
        super().__init__("driver text with idx_widgets_tenant_name_unique")
        self.sqlstate = sqlstate


def _integrity(code: str) -> IntegrityError:
    return IntegrityError("INSERT INTO widgets ...", {}, _PgErr(code))


assert isinstance(R._map_error(_integrity("23505"), "create"), ConflictError)
assert isinstance(R._map_error(_integrity("23503"), "create"), BusinessRuleError)
assert isinstance(R._map_error(OperationalError("SELECT 1", {}, _PgErr("08006")), "get"), UnavailableError)
assert isinstance(R._map_error(RuntimeError("x"), "get"), InternalError)
assert "idx_" not in R._map_error(_integrity("23505"), "create").message


class _Result:
    rowcount = 0

    def scalars(self) -> "_Result":
        return self

    def all(self) -> list[object]:
        return []

    def scalar_one(self) -> int:
        return 0

    def scalar_one_or_none(self) -> None:
        return None


class _Session:
    statements: list[str] = []

    async def __aenter__(self) -> "_Session":
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    async def execute(self, stmt: object, *args: object, **kwargs: object) -> _Result:
        _Session.statements.append(str(stmt.compile(dialect=postgresql.dialect())))  # type: ignore[attr-defined]
        return _Result()


repo = R(session_factory=lambda: _Session())  # type: ignore[arg-type]
for direction in ("desc", "asc"):
    res = asyncio.run(repo.list(uuid4(), ListFilters(cursor=c, page_size=10, sort_by="created_at",
                                                     sort_dir=direction, fields={"status": "active", "x": "y"})))
    assert res.items == [] and res.has_more is False and res.cursor is None
sql = "\n".join(_Session.statements)
# a SQL row comparison on (sort column, id), with the cursor's timestamp bound as a timestamp
assert "(widgets.created_at, widgets.id) <" in sql and "(widgets.created_at, widgets.id) >" in sql, sql
assert "s::TIMESTAMP WITH TIME ZONE, %(" in sql and "created_at_1)s::VARCHAR" not in sql, sql
assert "widgets.status =" in sql and "LIMIT" in sql and "widgets.deleted_at IS NULL" in sql, sql
