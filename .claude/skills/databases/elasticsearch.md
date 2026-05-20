# Elasticsearch patterns for full-text search, analytics, and log aggregation.

## Index Design
```json
// Create index with explicit mappings — never rely on dynamic mapping in production
PUT /widgets
{
  "settings": {
    "number_of_shards": 3,
    "number_of_replicas": 1,
    "refresh_interval": "1s",
    "analysis": {
      "analyzer": {
        "widget_analyzer": {
          "type": "custom",
          "tokenizer": "standard",
          "filter": ["lowercase", "asciifolding", "edge_ngram_filter"]
        }
      },
      "filter": {
        "edge_ngram_filter": {
          "type": "edge_ngram",
          "min_gram": 2,
          "max_gram": 20
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "tenant_id":   { "type": "keyword" },
      "name":        { "type": "text", "analyzer": "widget_analyzer", "fields": { "raw": { "type": "keyword" } } },
      "description": { "type": "text", "analyzer": "standard" },
      "status":      { "type": "keyword" },
      "priority":    { "type": "integer" },
      "tags":        { "type": "keyword" },
      "config":      { "type": "object", "enabled": false },
      "created_at":  { "type": "date" },
      "updated_at":  { "type": "date" },
      "deleted":     { "type": "boolean" }
    }
  }
}
```
- `keyword` for exact match, filtering, aggregations — never analyzed
- `text` for full-text search — tokenized, analyzed
- Multi-fields (`name.raw`) for both search and exact match on the same field
- Custom analyzers for autocomplete (edge_ngram), language-specific stemming
- `"enabled": false` on objects you only store but never query (config blobs)
- Set `dynamic: "strict"` to reject unmapped fields — prevents mapping explosions

## Search Patterns

### Full-Text Search
```json
POST /widgets/_search
{
  "query": {
    "bool": {
      "must": [
        { "term": { "tenant_id": "abc-123" } },
        { "multi_match": {
            "query": "dashboard widget",
            "fields": ["name^3", "description"],
            "type": "best_fields",
            "fuzziness": "AUTO"
        }}
      ],
      "filter": [
        { "term": { "deleted": false } },
        { "term": { "status": "active" } }
      ]
    }
  },
  "highlight": {
    "fields": { "name": {}, "description": {} },
    "pre_tags": ["<mark>"],
    "post_tags": ["</mark>"]
  }
}
```
- `must` contributes to relevance score — use for search terms
- `filter` does NOT contribute to score — use for exact matches (tenant, status)
- `filter` clauses are cached — much faster than `must` for static filters
- `^3` boosts name matches 3x over description matches
- `fuzziness: "AUTO"` handles typos — 1 edit for 3-5 char terms, 2 for 6+

### Fuzzy / Autocomplete Search
```json
POST /widgets/_search
{
  "query": {
    "bool": {
      "must": [
        { "term": { "tenant_id": "abc-123" } }
      ],
      "should": [
        { "match": { "name": { "query": "dashb", "analyzer": "widget_analyzer" } } },
        { "prefix": { "name.raw": { "value": "dashb", "boost": 2 } } }
      ],
      "minimum_should_match": 1
    }
  },
  "size": 10
}
```

### Aggregations
```json
POST /widgets/_search
{
  "size": 0,
  "query": {
    "bool": {
      "filter": [
        { "term": { "tenant_id": "abc-123" } },
        { "term": { "deleted": false } }
      ]
    }
  },
  "aggs": {
    "by_status": {
      "terms": { "field": "status", "size": 20 }
    },
    "by_priority": {
      "histogram": { "field": "priority", "interval": 1 }
    },
    "created_over_time": {
      "date_histogram": {
        "field": "created_at",
        "calendar_interval": "month"
      }
    },
    "avg_priority": {
      "avg": { "field": "priority" }
    }
  }
}
```
- `size: 0` skips hits — only return aggregation results
- `terms` aggregation for faceted search (status counts, tag counts)
- `date_histogram` for time-series analytics (created per month)
- Always filter by tenant_id — aggregations respect the query context

## Query DSL Reference

| Query Type | Use Case | Example |
|-----------|----------|---------|
| `term` | Exact keyword match | `{"term": {"status": "active"}}` |
| `terms` | Match any of multiple values | `{"terms": {"status": ["active", "draft"]}}` |
| `match` | Full-text search (analyzed) | `{"match": {"name": "dashboard"}}` |
| `multi_match` | Search across multiple fields | `{"multi_match": {"query": "q", "fields": ["name", "desc"]}}` |
| `range` | Numeric/date ranges | `{"range": {"created_at": {"gte": "2026-01-01"}}}` |
| `prefix` | Prefix match on keyword | `{"prefix": {"name.raw": "dash"}}` |
| `bool` | Combine queries | `{"bool": {"must": [...], "filter": [...], "should": [...]}}` |
| `exists` | Field exists check | `{"exists": {"field": "tags"}}` |

## Indexing Patterns

### Bulk Indexing
```json
POST /_bulk
{"index": {"_index": "widgets", "_id": "w1"}}
{"tenant_id": "abc", "name": "Widget 1", "status": "active", "created_at": "2026-01-15T00:00:00Z"}
{"index": {"_index": "widgets", "_id": "w2"}}
{"tenant_id": "abc", "name": "Widget 2", "status": "draft", "created_at": "2026-01-16T00:00:00Z"}
```
- Use `_bulk` API for indexing multiple documents — 10-100x faster than individual requests
- Batch size: 5-15MB per request or 1000-5000 documents
- Set `refresh_interval: "30s"` during bulk imports — reset to `1s` after

### Index Aliases for Zero-Downtime Reindexing
```json
// Create new index with updated mappings
PUT /widgets-v2 { ... }

// Reindex from old to new
POST /_reindex
{
  "source": { "index": "widgets-v1" },
  "dest": { "index": "widgets-v2" }
}

// Swap alias atomically
POST /_aliases
{
  "actions": [
    { "remove": { "index": "widgets-v1", "alias": "widgets" } },
    { "add": { "index": "widgets-v2", "alias": "widgets" } }
  ]
}
```
- Always query through aliases — never reference index names directly in application code
- Alias swap is atomic — no downtime during reindexing
- Keep old index until you verify the new one works correctly

## Pagination

### from/size (Offset — for small result sets)
```json
POST /widgets/_search
{
  "from": 0,
  "size": 20,
  "query": { ... },
  "sort": [{ "created_at": "desc" }, { "_id": "asc" }]
}
```
- Maximum `from + size` <= 10000 (default `index.max_result_window`)
- Acceptable for: admin UIs with < 10000 total results

### search_after (Cursor — for large result sets)
```json
// Page 1
POST /widgets/_search
{
  "size": 20,
  "query": { ... },
  "sort": [{ "created_at": "desc" }, { "_id": "asc" }]
}

// Page 2 — use sort values from last hit of page 1
POST /widgets/_search
{
  "size": 20,
  "query": { ... },
  "sort": [{ "created_at": "desc" }, { "_id": "asc" }],
  "search_after": ["2026-01-15T10:30:00.000Z", "w42"]
}
```
- `search_after` uses sort values as cursor — no depth limit
- Always include a tiebreaker field (`_id`) in sort — ensures deterministic ordering
- Encode `search_after` values as opaque base64 cursor for API consumers

### scroll (Deep pagination — for data export only)
```json
POST /widgets/_search?scroll=5m
{
  "size": 1000,
  "query": { ... }
}

// Subsequent pages
POST /_search/scroll
{
  "scroll": "5m",
  "scroll_id": "DXF1ZXJ5QW5..."
}
```
- Scroll creates a point-in-time snapshot — use for data exports, not real-time search
- Always clear scroll contexts when done: `DELETE /_search/scroll`
- Prefer `search_after` for user-facing pagination

## Performance
- Refresh interval: `1s` default (near real-time). Set to `30s` for write-heavy workloads
- Shard sizing: 10-50GB per shard. Under-sharding causes hot spots, over-sharding wastes overhead
- Replica count: 1 for production (fault tolerance), 0 for dev/test
- Use `filter` context for non-scoring queries — enables caching, skips scoring
- `_source` filtering: return only needed fields to reduce network transfer
- Avoid wildcard queries at the start of terms (`*widget`) — very expensive
- Use `index: false` on fields that are stored but never queried

## Testing
```typescript
// Testcontainers for integration tests
import { ElasticsearchContainer } from "@testcontainers/elasticsearch";

const container = await new ElasticsearchContainer("elasticsearch:8.12.0")
  .withEnvironment({ "xpack.security.enabled": "false" })
  .start();

const client = new Client({ node: container.getHttpUrl() });

// Create index, index test data, refresh, then search
await client.indices.create({ index: "widgets", body: indexSettings });
await client.bulk({ body: bulkData, refresh: true }); // refresh: true for immediate searchability
const result = await client.search({ index: "widgets", body: searchQuery });
```
- Use testcontainers or embedded ES for integration tests — never mock the search engine
- `refresh: true` on bulk operations in tests — makes documents immediately searchable
- Verify: result count, relevance ordering, highlight presence, aggregation values

## Rules
- Always query through index aliases — never hardcode index names
- `filter` context for non-scoring queries (tenant_id, status, deleted) — enables caching
- `must` context only for relevance-scored queries (full-text search)
- Bulk API for all multi-document indexing — never individual index calls in loops
- `search_after` for API pagination — never `from/size` beyond 10000
- Explicit mappings on all indices — never rely on dynamic mapping in production
- Set `refresh_interval` appropriately — 1s for search-heavy, 30s for write-heavy
- Shard size 10-50GB — monitor and reindex when shards grow too large
- Tenant isolation via `filter` clause on every query — never return cross-tenant results
- Custom analyzers for search quality — edge_ngram for autocomplete, language analyzers for stemming
