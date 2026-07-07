# EARS Notation — Requirements That Parse Into Test Cases

## Purpose

EARS (Easy Approach to Requirements Syntax) constrains every requirement to one of five sentence templates. Each template has a fixed shape: an optional **trigger/condition/state** and a mandatory **SHALL clause**. That fixed shape is what makes a requirement mechanically testable — the trigger becomes a test **precondition** and the SHALL becomes a test **assertion**.

Requirements still live in `docs/BRD.md` and keep their FR-*/NFR-*/OBJ-* IDs. EARS is the **phrasing standard** for the requirement text and for acceptance criteria — not a new storage location or ID scheme.

Related skills: [acceptance-criteria.md](acceptance-criteria.md), [requirement-clarity.md](requirement-clarity.md), [../testing/test-case-generation.md](../testing/test-case-generation.md).

---

## The Five Templates

| Template | Shape | Use when |
|----------|-------|----------|
| Ubiquitous | `THE SYSTEM SHALL <behavior>` | Always-true property, no trigger |
| Event-driven | `WHEN <trigger> THE SYSTEM SHALL <response>` | Behavior fires on an event/input |
| State-driven | `WHILE <state> THE SYSTEM SHALL <behavior>` | Behavior holds during a sustained state |
| Optional | `WHERE <feature is included> THE SYSTEM SHALL <behavior>` | Behavior applies only when a feature/config is present |
| Unwanted | `IF <undesired condition> THEN THE SYSTEM SHALL <response>` | Error, failure, or abuse handling |

### Concrete Examples

```
# Ubiquitous
FR-012: THE SYSTEM SHALL store passwords hashed with bcrypt (cost ≥ 12).

# Event-driven
FR-007: WHEN an Admin submits the invite form with a valid email
        THE SYSTEM SHALL create a pending member and send an invite email within 5s.

# State-driven
FR-021: WHILE a policy compilation is in progress
        THE SYSTEM SHALL disable the "Deploy" button.

# Optional
FR-030: WHERE SSO is enabled for the tenant
        THE SYSTEM SHALL redirect unauthenticated users to the IdP login.

# Unwanted
FR-007b: IF the invite email is already registered
         THEN THE SYSTEM SHALL reject the request with 409 CONFLICT and message "Email already invited".
```

Note how FR-007 (event) and FR-007b (unwanted) share a root ID — split a compound requirement into one clause per behavior, suffixing the ID (`a`, `b`, `c`) rather than inventing unrelated IDs.

---

## The Mapping Rule (STANDARD)

> **Each EARS clause → exactly one TC-*.**
> **Precondition = the trigger** (the WHEN / WHILE / IF / WHERE part; empty for Ubiquitous → precondition is the default/steady state).
> **Assertion = the SHALL** (the observable behavior after the precondition holds).

```
WHEN <trigger>  THE SYSTEM SHALL <response>
     └── precondition ──┘         └── assertion ──┘
              ▼                          ▼
     TC-<CAT>-NNN: Given <trigger>, assert <response>
```

Worked example:

```
FR-007: WHEN an Admin submits the invite form with a valid email
        THE SYSTEM SHALL create a pending member and send an invite email within 5s.

→ TC-API-014 (integration):
    Precondition: authenticated Admin POSTs /api/v1/team/invite with valid email
    Assertion:    201 + member row status="pending" + invite email dispatched < 5s
```

Because the split is deterministic, the same clause always yields the same TC-* — reviewers can check "one clause, one TC" by counting.

---

## Rewriting Prose FR-*/NFR-* Into EARS (Rubric)

For each existing requirement:

1. **Identify the subject** — force it to `THE SYSTEM` (drop "the app should", "users can", "we need to").
2. **Classify the clause** — is there a trigger (event), a sustained state (state), a feature gate (optional), an error/abuse case (unwanted), or none (ubiquitous)? Pick the one template that fits.
3. **Split compounds** — if the sentence has more than one SHALL / "and also" / a list of behaviors, break it into one EARS clause per behavior, each with its own suffixed ID.
4. **Replace vague verbs** — "handle", "manage", "support", "process" → a concrete, observable outcome ("return 409", "display error toast", "persist row").
5. **Add missing triggers** — an event/unwanted requirement with no WHEN/IF is not testable; supply the precondition.
6. **Keep the ID** — retain the original FR-*/NFR-* verbatim; only rewrite the sentence body. Suffix (`-a`,`-b`) only when splitting.
7. **State the assertion measurably** — every SHALL must be checkable PASS/FAIL (see [acceptance-criteria.md](acceptance-criteria.md) testability rule).

### Before / After

```
BEFORE (prose):
FR-042: The system should handle invalid uploads gracefully and support large files.

AFTER (EARS):
FR-042a: IF an uploaded file exceeds 50 MB
         THEN THE SYSTEM SHALL reject it with 413 and message "File exceeds 50 MB limit".
FR-042b: IF an uploaded file is not one of {pdf, png, jpg}
         THEN THE SYSTEM SHALL reject it with 422 and list the accepted types.
FR-042c: WHEN a valid file ≤ 50 MB is uploaded
         THE SYSTEM SHALL store it and return 201 with the file's UUID.
```

Three testable clauses → three TC-* IDs, versus one un-testable sentence.

---

## Anti-Patterns

| Anti-pattern | Why it breaks the mapping | Fix |
|--------------|---------------------------|-----|
| Vague verb ("handle", "manage", "support") | No observable assertion → can't write PASS/FAIL | Name the concrete outcome |
| Compound SHALL ("SHALL validate and store and notify") | One clause → many assertions → many TC blur into one | Split into one clause per SHALL |
| Missing trigger on an event/unwanted req | No precondition → test can't set up state | Add the WHEN/IF |
| "Users can…" / "The app should…" | Subject isn't the system under test | Force `THE SYSTEM SHALL` |
| WHILE used for a one-shot event | State template implies a sustained condition | Use WHEN for events, WHILE for durations |
| Unbounded assertion ("quickly", "gracefully") | Not measurable | Attach the metric / exact response |
| Inventing a new ID during rewrite | Breaks BRD traceability | Keep the original FR-*; suffix only when splitting |

---

## Reviewer Checklist

Before a spec's requirements are accepted:

- [ ] Every FR-*/NFR-* is written in exactly one of the five EARS templates
- [ ] No clause contains more than one SHALL
- [ ] Every event/unwanted clause has an explicit trigger (WHEN/IF)
- [ ] Every SHALL is measurable (PASS/FAIL, with metrics where relevant)
- [ ] Original FR-*/NFR-* IDs are preserved (suffixes only for splits)
- [ ] Each clause maps to exactly one TC-* (precondition = trigger, assertion = SHALL)
