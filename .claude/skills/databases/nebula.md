# NebulaGraph patterns for distributed graph data (nGQL, NebulaGraph 3.x).

> The Vertix graph stack is **NebulaGraph, never Neo4j** (threatmatrix, storage). Research and
> write NebulaGraph/nGQL patterns — do not port Cypher-only idioms blindly. See ground truth in
> `docs/PROJECT_FACTS.md`.

## Data Model
NebulaGraph is a distributed property graph. Core objects:
- **Space** — an isolated graph (like a database). Queries never cross spaces.
- **Vertex** — identified by a user-supplied **VID** (`FIXED_STRING(n)` or `INT64` — chosen per
  space, immutable). A vertex carries one or more **TAGs** (label + property schema).
- **Edge** — a directed, typed relationship with properties and an optional **rank** (int) that
  lets multiple edges of the same type exist between the same two vertices.

```ngql
CREATE SPACE IF NOT EXISTS threatmatrix (partition_num=15, replica_factor=3, vid_type=FIXED_STRING(64));
USE threatmatrix;

CREATE TAG IF NOT EXISTS asset(name string, kind string, created_at timestamp);
CREATE TAG IF NOT EXISTS actor(handle string, confidence double);
CREATE EDGE IF NOT EXISTS communicates_with(protocol string, first_seen timestamp, last_seen timestamp);
```
- Pick the VID scheme deliberately: a natural key (`FIXED_STRING`) makes upserts idempotent; a
  hash keeps VIDs uniform. VID type is set at space creation and cannot change.
- Prefer several focused TAGs over one wide TAG — a vertex composes multiple TAGs.

## Insert / Upsert
```ngql
INSERT VERTEX asset(name, kind, created_at) VALUES "asset:10.0.0.5":("web-01","host", now());
INSERT EDGE communicates_with(protocol, first_seen, last_seen)
  VALUES "asset:10.0.0.5" -> "asset:8.8.8.8"@0:("dns", now(), now());
UPSERT VERTEX ON asset "asset:10.0.0.5" SET kind = "host";   -- idempotent write
```
The `@0` is the edge rank. Use it (e.g. a time bucket) when the same edge type can legitimately
repeat between two vertices; otherwise leave it 0 so re-inserts overwrite.

## Querying — pick the right primitive
- **`GO`** — native, fastest traversal from known VIDs (BFS-style hops). Use for "N hops from X".
- **`MATCH`** — openCypher-style pattern matching. Use for pattern/variable-length queries.
- **`FETCH`** — read properties of known vertices/edges.
- **`LOOKUP`** — find VIDs by **indexed** property (the only way to start from a property, not a VID).

```ngql
-- 2-hop neighbors via native traversal (bind the starting VID, don't scan)
GO 2 STEPS FROM "asset:10.0.0.5" OVER communicates_with YIELD dst(edge) AS peer;

-- pattern match
MATCH (a:asset)-[:communicates_with]->(b:asset) WHERE a.asset.kind == "host" RETURN a, b LIMIT 100;

-- start from a property (REQUIRES an index on asset.name)
LOOKUP ON asset WHERE asset.name == "web-01" YIELD id(vertex) AS vid;
```

## Indexes (mandatory for property lookups — and a footgun)
```ngql
CREATE TAG INDEX IF NOT EXISTS idx_asset_name ON asset(name(32));
REBUILD TAG INDEX idx_asset_name;   -- REQUIRED after creating an index on existing data
```
- `LOOKUP` and property-anchored `MATCH` **cannot run without an index** — plan indexes up front.
- Creating an index does not backfill; you **must `REBUILD`** or existing rows are invisible to it.
- Index only the properties you actually filter on; each index adds write cost. For `string`
  properties specify a prefix length (`name(32)`).

## TTL (auto-expiry)
```ngql
CREATE TAG session(created_at timestamp) TTL_DURATION = 86400, TTL_COL = "created_at";
```
A TAG/EDGE has at most one TTL column; expired data is filtered on read and removed by compaction.

## Rules
- **Never cross spaces in one query** — model related data in the same space or resolve in app code.
- **Bind starting VIDs whenever possible** (`GO ... FROM <vid>`); property-first queries need an
  index and are slower — design VIDs so hot lookups start from a known id.
- **Set `vid_type` and `partition_num` at creation** — both are immutable; size `partition_num`
  for the cluster (a common default is 10–20 × storaged count).
- After schema DDL, remember NebulaGraph applies changes **asynchronously** — wait/ retry before
  inserting against a brand-new TAG/EDGE in tests.
- Use **parameterized statements / batches** for bulk load; single-row `INSERT` per call does not scale.
- Migrations: version nGQL DDL like SQL (create space/tag/edge/index, then `REBUILD`). There is no
  built-in ORM — access via the official client (Go `nebula-go`, Python `nebula3-python`).
- `snake_case` property names to match the Go/service stack.
