# Requirement Clarity Patterns — Writing Testable, Unambiguous Requirements

## The 5-Part Requirement Template

Every functional requirement MUST include all 5 parts:

```
TRIGGER:  What initiates this behavior (user action, system event, time-based)
ACTOR:    Who performs or experiences it (specific persona, not "the user")
ACTION:   What exactly happens (concrete verb, not vague)
OUTCOME:  What the observable result is (state change, response, navigation)
ERROR:    What happens when it fails (specific error conditions + handling)
```

### Example: Weak → Strong

**Weak:** "Users can search for items"

**Strong:**
```
FR-012: Item Search
TRIGGER: User types in search input and presses Enter or waits 300ms (debounce)
ACTOR:   Authenticated End User
ACTION:  System searches items by name, description, and tags (case-insensitive, partial match)
OUTCOME: Results displayed as paginated list (20 per page), sorted by relevance.
         If >0 results: show result count + list.
         If 0 results: show "No items match your search" + suggestion to broaden terms.
ERROR:   Search service unavailable → show "Search is temporarily unavailable" + cached recent results if available.
         Query > 200 chars → truncate silently to 200.
         Empty query → show all items (unfiltered).
```

## Vague Words Checklist (NEVER USE)

| Vague Word | Problem | Replace With |
|---|---|---|
| "fast" | How fast? | "p95 latency < 200ms" |
| "easy" | For whom? | "Complete in < 3 clicks for [persona]" |
| "user-friendly" | Unmeasurable | "Meets WCAG 2.2 AA, task completion rate > 90%" |
| "reliable" | How reliable? | "99.9% uptime, < 5min recovery" |
| "secure" | How secure? | "OWASP Top 10 mitigated, data encrypted at rest (AES-256)" |
| "scalable" | To what? | "Handle 10K concurrent users, 1M records" |
| "good performance" | No target | "API response < 100ms p95, page load < 2s LCP" |
| "all users" | Which users? | "Admin Users AND End Users" (list explicitly) |
| "should" | Optional or required? | "MUST" (required) or "MAY" (optional) |
| "etc." | Hiding unknowns | List all items explicitly |
| "appropriate" | Who decides? | Specify the exact behavior |
| "seamless" | Meaningless | "No page reload, < 200ms transition" |

## Testability Gate

Before finalizing any requirement, ask:

> "Can this requirement be verified by a single yes/no automated test?"

- **YES** → requirement is clear enough
- **NO** → requirement needs to be split or made more specific

Examples:
- "System must be fast" → **FAILS** (no target, no endpoint)
- "GET /api/v1/users responds in < 200ms p95 under 100 concurrent connections" → **PASSES**

## Requirement Sizing

If a requirement takes > 5 sentences to describe, it's too large. Split it:

```
FR-012: Item Search (base)        → search by name, return paginated results
FR-012a: Item Search (filters)    → filter by category, date range, status
FR-012b: Item Search (sort)       → sort by relevance, date, name
FR-012c: Item Search (typeahead)  → autocomplete suggestions after 2 chars
```

## RFC 2119 Keywords

Use these consistently:
- **MUST** / **REQUIRED** → non-negotiable, blocks release if missing
- **SHOULD** / **RECOMMENDED** → strongly expected, documented reason if skipped
- **MAY** / **OPTIONAL** → nice-to-have, can be deferred

## Anti-Patterns

| Pattern | Problem | Fix |
|---------|---------|-----|
| "Users can manage items" | What does "manage" mean? CRUD? Just view? | Split: "create items", "edit items", "delete items", "view items" |
| "Admin users have full access" | Full access to what? | List each permission explicitly |
| "System sends notifications" | When? To whom? Via what channel? | "When [trigger], system sends email to [actor] containing [content]" |
| "Data is validated" | Which fields? What rules? | "Email: valid format. Name: 2-50 chars. Age: 18-120." |
| "Similar to competitor X" | Competitor changes; requirement is undefined | Describe the specific behavior you want, not the reference |
