# frameworks/graphql.md: the doc's Query and Widget types in a real Strawberry schema, executed.
import asyncio

import strawberry

from app.graphql.schema import Query
from harness_stubs.strawberry_app import make_context

schema = strawberry.Schema(query=Query)


def run(query: str, tenant: str = "t1"):
    ctx, calls = make_context(tenant)
    return asyncio.run(schema.execute(query, context_value=ctx)), calls


# one widget, its creator and tags through the DataLoaders
res, _ = run('{ widget(id: "t1-w1") { id name status createdBy { name } tags { name } } }')
assert res.errors is None, res.errors
assert res.data == {"widget": {"id": "t1-w1", "name": "widget 1", "status": "ACTIVE",
                               "createdBy": {"name": "user u1"}, "tags": [{"name": "tag-of-t1-w1"}]}}, res.data
# another tenant's id is not found (null, not an error)
res, _ = run('{ widget(id: "t2-w1") { id } }')
assert res.errors is None and res.data == {"widget": None}, (res.errors, res.data)

# first outside 1..100 is a VALIDATION_FAILED error and no data — never a clamped page
for first in (0, -1, 101):
    res, calls = run(f"{{ widgets(first: {first}) {{ totalCount }} }}")
    assert res.data is None, (first, res.data)
    assert res.errors is not None and len(res.errors) == 1, (first, res.errors)
    ext = res.errors[0].extensions or {}
    assert ext.get("code") == "VALIDATION_FAILED", (first, ext)
    assert ext["details"] == [{"field": "first", "code": "out_of_range", "message": "This value is out of range."}], ext
    assert res.errors[0].path == ["widgets"], res.errors[0].path
    assert calls.lists == [], "the service must not be called for an invalid page size"
    print(f"graphql first={first}: error VALIDATION_FAILED (details[0].code out_of_range), data=None")

# the bounds themselves succeed; the DataLoaders batch one call per level for the whole page
for first in (1, 100):
    res, calls = run(f"{{ widgets(first: {first}) {{ totalCount edges {{ node {{ id createdBy {{ name }} tags {{ name }} }} }} }} }}")
    assert res.errors is None, (first, res.errors)
    assert res.data is not None and res.data["widgets"]["totalCount"] == first, res.data
    assert len(res.data["widgets"]["edges"]) == first
    assert calls.lists == [("t1", first)], calls.lists
    assert len(calls.users) == 1 and len(calls.tags) == 1, (calls.users, calls.tags)  # batched, not N+1
    print(f"graphql first={first}: ok, {first} edge(s), users loaded in {len(calls.users)} batch")
