---
skill: caching-strategies
description: Caching strategies — cache-aside/read-through/write-through, TTL + invalidation, stampede/thundering-herd protection, Redis patterns, cache key design, when NOT to cache
version: "1.0"
tags:
  - caching
  - redis
  - performance
  - invalidation
  - stampede
  - infrastructure
---

# Caching strategies for correct, fast, and non-lying reads.

> Go samples compile-checked (go build + go vet) 2026-09-30 with Go 1.27.1, go-redis v9.22.0 (tests/archetype-compile/go/run.sh).

A cache is a correctness liability you accept for latency. The default posture is **no cache** until a
measured hot path justifies one. Every cached value is a copy that can go stale; the hard part is never
the read, it's the invalidation.

## Patterns

### Cache-aside (lazy — the default)
Application owns the cache. Read: check cache → miss → load from DB → populate → return.
```go
func (s *Service) Get(ctx context.Context, id string) (*Item, error) {
    key := cacheKey(ctx, "item", id)          // tenant-scoped key — see below
    if b, err := s.rdb.Get(ctx, key).Bytes(); err == nil {
        return decode(b)                       // hit
    }
    item, err := s.repo.Get(ctx, id)           // miss → source of truth
    if err != nil {
        return nil, err
    }
    // Fill with a jittered TTL so a class of keys does not expire on the same tick
    s.rdb.Set(ctx, key, encode(item), ttlWithJitter(5*time.Minute))
    return item, nil
}
```
- Only the accessed keys are ever cached — memory tracks the working set, not the whole table.
- On DB write, **invalidate** (delete) the key; do not try to update it in place (races with concurrent reads).
- Never cache the miss silently forever — a bug that returns `nil` then caches `nil` becomes permanent.

### Read-through / write-through
The cache library sits in front of the store and loads/writes on your behalf. Write-through writes cache
+ DB in one call (strong-ish consistency, higher write latency). Use only when the library guarantees the
DB write happens before the cache is considered populated — otherwise you cache data that never persisted.

### Write-behind (write-back)
Cache acks the write, flushes to DB asynchronously. Fastest writes, **but a cache crash loses
un-flushed data**. Only for tolerant data (counters, view stats) with an accepted loss window — never for
money, orders, or audit records.

## Cache key design
- **Always namespace + version + tenant:** `v3:acme-tenant:item:{id}`. A version segment lets you
  invalidate an entire class of keys by bumping `v3→v4` (no scan/delete needed).
- Include every input that changes the value: `item:{id}:lang:{lang}` — a key that omits `lang` serves the
  wrong language to the second caller.
- Never build keys from raw user input without normalizing (case, whitespace, trailing slash) — otherwise
  `Item`/`item` are two cache entries for one row.
- Keep keys short but readable; colon-delimited segments are the Redis convention.

## TTL + invalidation
Two independent mechanisms, use both:
1. **TTL** — a safety net so a missed invalidation self-heals. Every cached value has a TTL; there is no
   such thing as a cache entry that lives forever.
2. **Explicit invalidation on write** — delete (not overwrite) the key inside the same transaction path
   that mutates the row. Prefer delete-on-write over update-on-write: a delete is idempotent and race-free.

```go
func (s *Service) Update(ctx context.Context, id string, patch Patch) error {
    if err := s.repo.Update(ctx, id, patch); err != nil {
        return err
    }
    s.rdb.Del(ctx, cacheKey(ctx, "item", id))           // invalidate AFTER the DB commit
    s.rdb.Incr(ctx, cacheKey(ctx, "item-list", "ver"))  // and bump the list namespace's version:
                                                        // list-page keys include it, so every page is a miss
    return nil
}
```
- Invalidate **after** the DB commit, never before — a delete-then-crash leaves the cache correct (empty),
  a delete-before-commit can repopulate stale data from a concurrent read.
- List/aggregate keys are the hard case: a single row change can invalidate many list pages. Prefer a
  version-bump on the list namespace over trying to enumerate affected pages.

## Stampede / thundering-herd protection
When a hot key expires, thousands of concurrent requests miss simultaneously and all hit the DB.
Three defenses:

1. **Jittered TTL** — never a fixed TTL for a class of keys; add ±10-20% randomness so they don't all
   expire on the same tick.
   ```go
   func ttlWithJitter(base time.Duration) time.Duration {
       jitter := time.Duration(rand.Int63n(int64(base) / 5)) // up to 20%
       return base + jitter
   }
   ```
2. **Single-flight / mutex lock** — on miss, the first request takes a short-lived lock (`SET key:lock NX
   PX 5000`) and recomputes; others wait briefly and re-read, or serve stale. In Go, `golang.org/x/sync/singleflight`
   collapses concurrent identical loads into one.
3. **Probabilistic early recompute** — recompute *before* expiry with a probability that rises as the TTL
   nears zero (XFetch), so one unlucky request refreshes while others still serve the warm value.

## Redis operational notes
- Set a `maxmemory` and an eviction policy (`allkeys-lru` for a pure cache; `volatile-lru` if you mix
  cache + durable keys). Without a policy, Redis OOMs instead of evicting.
- Use pipelining / `MGET` for batch reads; a per-key round trip in a loop is the N+1 of caching.
- Redis is not a database — treat every cached value as disposable and be correct when the cache is empty
  (cold start, flush, failover). "The cache was down so the app 500'd" is a design bug.
- For cross-instance invalidation of in-process caches, publish invalidation events over Redis Pub/Sub or
  a keyspace-notification channel.

## When NOT to cache
- Data that must be strongly consistent and read-your-writes (balances, permissions, inventory at checkout).
- Low-read-ratio data — if writes ≈ reads, the cache is invalidated as fast as it's populated (negative ROI).
- Cheap queries already served by a covering index in <1ms — the network hop to Redis can be *slower*.
- Per-request data with no reuse (one-shot tokens, request-scoped derived values).
- Before you have a measured hot path. Add caching to fix a proven latency/QPS problem, not preemptively.

## Rules
- No cache without a TTL. Ever. TTL is the self-healing floor under every invalidation bug.
- Invalidate by **delete after commit**, not update; deletes are idempotent and race-free.
- Keys are tenant-scoped and versioned — one caller's cache must never serve another tenant's data.
- The application must be correct with an empty/unavailable cache — the cache is an optimization, not a store.
- Jitter every TTL and single-flight every hot-key recompute — otherwise expiry becomes a self-inflicted DDoS.
- Never write-behind for data you cannot afford to lose.

## Testing note
Test the **cold path and the invalidation path**, not just the hit. Assert that (1) a miss populates the
cache, (2) a write deletes the key, (3) a stale read after a write returns fresh data, and (4) the service
still returns correct results with the cache client stubbed to always-miss / always-error. Add a
concurrency test that fires N simultaneous misses on one key and asserts the loader ran once (single-flight).
