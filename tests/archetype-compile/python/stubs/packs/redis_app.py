"""harness: the app-level names databases/redis.md's fragments leave to the reader (a database handle,
the cache codec, a user, the session TTL setting)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

SESSION_TTL_SECONDS = 1800


def serialize(value: object) -> str:
    return json.dumps(value)


def deserialize(data: Any) -> object:
    return json.loads(data)


@dataclass
class Db:
    """Counts reads and writes so a test can see what the cache saved."""

    rows: dict[str, object] = field(default_factory=dict)
    reads: int = 0
    writes: int = 0

    def query(self, *args: object) -> object:
        self.reads += 1
        return self.rows.get("widget", {"id": "w1", "name": "from the database"})

    def update(self, *args: object) -> None:
        self.writes += 1


@dataclass
class User:
    role: str = "member"
    id: UUID = field(default_factory=uuid4)
