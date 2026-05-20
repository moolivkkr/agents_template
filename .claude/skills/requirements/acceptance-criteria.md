# Acceptance Criteria Patterns — Testable, Complete, Automatable

## The AC Formula: Happy Path + 3 Error Paths + Boundary

Every FR-* needs acceptance criteria covering at minimum:

1. **Happy path** — the expected successful flow
2. **Auth failure** — what happens without auth or wrong permissions
3. **Validation failure** — what happens with invalid input
4. **Service failure** — what happens when a dependency is down
5. **Boundary values** — edge cases at limits (empty, max, zero)

## Gherkin Format (When to Use)

Use Given/When/Then for behavior that has clear preconditions:

```gherkin
# Happy path
Given an authenticated Admin user
And at least one active team member exists
When the Admin navigates to /settings/team
Then the team member list displays with columns: Name, Email, Role, Status
And each row has Edit and Remove action buttons
And the list is sorted by name ascending by default

# Auth failure
Given an unauthenticated user
When they navigate to /settings/team
Then they are redirected to /login
And the original URL is preserved for post-login redirect

# Validation failure — create member
Given an authenticated Admin on the team settings page
When they submit the invite form with an invalid email "not-an-email"
Then the email field shows error "Enter a valid email address"
And the form is NOT submitted
And the user's input is preserved

# Service failure
Given an authenticated Admin on the team settings page
When the API returns 500 for GET /api/v1/team/members
Then the page shows "Unable to load team members" with a Retry button
And clicking Retry re-fetches the data

# Boundary — empty state
Given an authenticated Admin with no team members
When they navigate to /settings/team
Then the page shows empty state: Users icon + "No team members yet" + "Invite your first member" button
```

## Acceptance Criteria Checklist

For EACH FR-*, verify these are covered:

```
□ Happy path defined (exact user steps + expected result)
□ Auth required? If yes: unauthenticated → redirect to login
□ Permission required? If yes: unauthorized → "You don't have permission"
□ Input validation: at least 1 invalid input scenario
□ Empty state: what shows when there's no data
□ Error state: what shows when the API fails
□ Boundary: empty string, max length, zero, null
□ Concurrency: what if two users act simultaneously (if applicable)
□ Idempotency: what if user double-clicks submit (if applicable)
```

## Criteria by Feature Type

### List/Table Features
```
□ Empty list behavior (no items exist)
□ Filtered empty (items exist but none match filter)
□ Pagination: first page, last page, beyond-last page
□ Sort: each sortable column + default sort
□ Search: partial match, empty query, no results
□ Concurrent deletion (item deleted while viewing list)
□ Loading state (skeleton matching layout)
```

### Form Features
```
□ Each field validation rule (type, min, max, pattern)
□ Required vs optional fields
□ Submit with all valid → success toast + redirect/reset
□ Submit with invalid → field-level error messages
□ Server returns 422 → map field errors to form
□ Submit while pending → button disabled + spinner
□ Dirty form + navigate away → confirm dialog
□ Edit form → pre-populated from API data
```

### CRUD Operations
```
□ Create: success creates resource + shows in list
□ Read: single resource load + not-found handling
□ Update: optimistic update + rollback on failure
□ Delete: confirmation dialog + soft/hard delete behavior
□ Bulk operations: select all, deselect, bulk delete
```

## Testability Validation

Every acceptance criterion must pass this test:

> "Can a QA engineer write a single automated test for this criterion that returns PASS or FAIL?"

**FAILS testability:**
- "The page should load quickly" → no metric
- "The form works correctly" → no specific behavior
- "Users have a good experience" → unmeasurable

**PASSES testability:**
- "GET /api/v1/users responds 200 with `data: User[]` in < 200ms"
- "Submitting the form with empty name shows 'Name is required' below the field"
- "Clicking Delete shows confirmation dialog; confirming removes item from list"

## Anti-Patterns

| Pattern | Problem | Fix |
|---------|---------|-----|
| "It works" | Not testable | Define exact input → output |
| Happy path only | Misses 80% of bugs | Add auth, validation, service failure, boundary |
| "User sees error" | Which error? Where? | "Error toast: 'Failed to save. Try again.'" |
| Copy-paste from wireframe | Wireframe describes UI, not behavior | Criteria describe BEHAVIOR with expected outcomes |
| "Same as competitor" | Undefined, changing target | Specify the exact behavior |
