# Conflict Detection Patterns — Finding Contradictions Before They Reach Code

## Conflict Types

| Type | Description | Example |
|---|---|---|
| **Contradictory actions** | Two requirements demand opposite behaviors | FR-003: "Users can delete records" vs FR-010: "All records are permanent" |
| **Incompatible constraints** | NFRs that can't both be satisfied | NFR-SEC: "Encrypt all data at rest" vs NFR-PERF: "Search returns in < 50ms" (full-table scans on encrypted data) |
| **Exclusive features** | Two features that are mutually exclusive | FR-020: "Single sign-on only" vs FR-021: "Local username/password auth" |
| **Temporal conflicts** | Requirements that conflict at different stages | FR-030: "Users must verify email before access" vs FR-031: "Users can use the system immediately after registration" |
| **Permission conflicts** | Access rules that contradict | FR-040: "Admins see all tenant data" vs FR-041: "Tenant data is isolated per-tenant with no cross-tenant access" |
| **Priority conflicts** | Two high-priority items that can't both be MVP | OBJ-001: "Launch in 4 weeks" vs scope of 30 FR-* requirements |

## Detection Method

### Step 1: Keyword Scan
Flag requirements containing opposing keywords:

| Keyword Pair | Conflict Signal |
|---|---|
| "always" / "never" | Absolute rules may contradict |
| "all users" / "only [role]" | Access scope conflict |
| "delete" / "permanent" / "retain" | Data lifecycle conflict |
| "immediately" / "after [condition]" | Timing conflict |
| "required" / "optional" | Same field described both ways |
| "single" / "multiple" | Cardinality conflict |
| "public" / "authenticated" / "restricted" | Access level conflict |

### Step 2: Cross-Reference Matrix
For each pair of FR-* that touch the same entity/feature, verify they don't contradict:

```markdown
| FR-A | FR-B | Same Entity? | Conflict? | Resolution |
|------|------|-------------|-----------|------------|
| FR-003 Delete records | FR-010 Permanent records | Records | YES — contradictory | Soft delete: mark as deleted, retain in DB |
| FR-020 SSO only | FR-021 Password auth | Auth | YES — exclusive | SSO primary, password as fallback |
| FR-030 Email verify first | FR-031 Immediate access | Registration | YES — temporal | Grace period: limited access until verified |
```

### Step 3: NFR Impact Assessment
For each NFR, check if it conflicts with any FR or other NFR:

```
NFR-SEC-001: All PII encrypted at rest
  Impact on FR-012 (Search items by name):
    If name is PII, encrypted search is slow → conflict with NFR-PERF-001
  Resolution: Use encrypted search index (pgcrypto + partial index) or
    classify name as non-PII
```

## Resolution Strategies

| Strategy | When to Use | Example |
|---|---|---|
| **Priority override** | One requirement clearly more important | Security > performance → encrypt, accept latency |
| **Scope narrowing** | Both valid but for different contexts | "Delete" for end users = soft delete; "Delete" for admin = hard purge |
| **Temporal separation** | Both valid at different times | "Immediate access" during grace period; "Verified access" after 24h |
| **Feature flagging** | Both valid for different deployments | SSO for enterprise; password auth for self-service |
| **Escalate to user** | Can't resolve without business input | Present options with tradeoffs, let user decide |

## Conflict Resolution Template

```markdown
## Conflict: [FR-NNN] vs [FR-NNN]
- **Nature:** [contradictory / incompatible / exclusive / temporal / permission]
- **Entity affected:** [which data/feature/flow]
- **Option A:** [keep FR-NNN, modify FR-NNN]
  - Tradeoff: [what's lost]
- **Option B:** [keep FR-NNN, modify FR-NNN]
  - Tradeoff: [what's lost]
- **Option C:** [compromise — both partially satisfied]
  - Tradeoff: [complexity added]
- **Recommendation:** [A/B/C with reasoning]
- **Decision:** [user's choice — recorded here]
```

## Anti-Patterns

| Pattern | Problem | Fix |
|---------|---------|-----|
| Ignoring conflicts ("we'll figure it out") | Discovered during Phase 3 → expensive rework | Resolve ALL Critical conflicts before BRD finalization |
| Resolving in favor of newest requirement | Earlier requirement may be more important | Use priority framework, not recency |
| Removing conflicting requirement entirely | Loses valid business need | Scope-narrow or compromise instead |
| Documenting conflict but not resolving | Downstream agents can't implement | Every conflict needs a decision before BRD is "done" |
