"""harness: the app-level names frameworks/graphql.md's Strawberry schema leaves to the reader — the other
GraphQL types (User, Tag, WidgetStatus, WidgetFilter, the Relay connection), the request context with the
widget service and the per-request DataLoaders, and the auth helper that reads the verified user."""
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Annotated, Any

import strawberry
from strawberry.dataloader import DataLoader
from strawberry.types import Info

if TYPE_CHECKING:
    from app.graphql.schema import Widget


@strawberry.type
class User:
    id: strawberry.ID
    name: str


@strawberry.type
class Tag:
    name: str


@strawberry.enum
class WidgetStatus(Enum):
    ACTIVE = "active"
    DRAFT = "draft"


@strawberry.input
class WidgetFilter:
    status: WidgetStatus | None = None


@strawberry.type
class WidgetEdge:
    node: Annotated["Widget", strawberry.lazy("app.graphql.schema")]
    cursor: str


@strawberry.type
class PageInfo:
    has_next_page: bool
    end_cursor: str | None


@strawberry.type
class WidgetConnection:
    edges: list[WidgetEdge]
    page_info: PageInfo
    total_count: int


@dataclass
class CurrentUser:
    id: str
    tenant_id: str


def get_current_user(info: Info) -> CurrentUser:
    """The user the auth middleware verified (the tenant comes from the token, never the client)."""
    return info.context.user


@dataclass
class Calls:
    users: list[list[str]] = field(default_factory=list)
    tags: list[list[str]] = field(default_factory=list)
    lists: list[tuple[str, int]] = field(default_factory=list)


def UserLoader(calls: Calls) -> DataLoader[str, User]:  # noqa: N802 — the doc imports these names
    async def load(ids: list[str]) -> list[User]:
        calls.users.append(list(ids))
        return [User(id=strawberry.ID(i), name=f"user {i}") for i in ids]
    return DataLoader(load_fn=load)


def TagLoader(calls: Calls) -> DataLoader[str, list[Tag]]:  # noqa: N802
    async def load(ids: list[str]) -> list[list[Tag]]:
        calls.tags.append(list(ids))
        return [[Tag(name=f"tag-of-{i}")] for i in ids]
    return DataLoader(load_fn=load)


class WidgetService:
    """Tenant-scoped widget reads (a widget of another tenant is simply not found)."""

    def __init__(self, calls: Calls) -> None:
        self.calls = calls

    @staticmethod
    def _widget(tenant_id: str, n: int) -> Any:
        from app.graphql.schema import Widget

        return Widget(id=strawberry.ID(f"{tenant_id}-w{n}"), name=f"widget {n}", description="",
                      status=WidgetStatus.ACTIVE, created_by_id=f"u{n % 2}")

    async def get(self, tenant_id: str, widget_id: str) -> Any:
        return self._widget(tenant_id, 1) if widget_id.startswith(f"{tenant_id}-") else None

    async def list(self, tenant_id: str, first: int, after: str | None, filter: WidgetFilter | None) -> WidgetConnection:
        self.calls.lists.append((tenant_id, first))
        edges = [WidgetEdge(node=self._widget(tenant_id, n), cursor=f"c{n}") for n in range(first)]
        return WidgetConnection(edges=edges, page_info=PageInfo(has_next_page=False, end_cursor=None),
                                total_count=first)


@dataclass
class Context:
    user: CurrentUser
    widget_svc: WidgetService
    user_loader: DataLoader[str, User]
    tag_loader: DataLoader[str, list[Tag]]


def make_context(tenant_id: str = "t1") -> tuple[Context, Calls]:
    calls = Calls()
    return Context(CurrentUser("u0", tenant_id), WidgetService(calls), UserLoader(calls), TagLoader(calls)), calls
