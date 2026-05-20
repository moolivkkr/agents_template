---
skill: code-quality
description: Code quality enforcement — self-review, function size, naming, KISS, DRY, incremental development, early returns, nesting limits
version: "1.0"
tags:
  - quality
  - clean-code
  - naming
  - refactoring
  - best-practices
---

# Code Quality

Standards and checkpoints for writing clean, maintainable, production-grade code. Every agent must enforce these rules before marking any task complete.

## Self-Review Checkpoint

Before marking ANY task done, re-read every file you touched. Check for:

1. **Unused imports** — remove them, they cause lint failures and confusion
2. **Dead code** — no commented-out blocks, no unreachable branches
3. **TODO/FIXME placeholders** — replace with real implementation or remove
4. **Hardcoded values** — extract to config, constants, or environment variables
5. **Missing error handling** — every error path must be handled explicitly
6. **Inconsistent naming** — all names in a file should follow the same convention
7. **Missing tests** — new public functions need at least one test

```go
// BAD — left behind after development
// TODO: implement this later
func ProcessOrder(ctx context.Context, order Order) error {
    return nil // placeholder
}

// GOOD — fully implemented or explicitly errored
func ProcessOrder(ctx context.Context, order *Order) error {
    if order == nil {
        return ErrNilOrder
    }
    if err := order.Validate(); err != nil {
        return fmt.Errorf("invalid order: %w", err)
    }
    return s.repo.Save(ctx, order)
}
```

## Function Size — 40 Lines Max

If a function exceeds 40 lines, extract helper functions. Long functions are hard to test, hard to read, and usually violate Single Responsibility.

```go
// BAD — 80+ line monolith
func CreateUser(ctx context.Context, req CreateUserRequest) (*User, error) {
    // 80 lines of validation, creation, notification, logging...
}

// GOOD — decomposed into focused helpers
func CreateUser(ctx context.Context, req CreateUserRequest) (*User, error) {
    if err := validateCreateUserRequest(req); err != nil {
        return nil, err
    }
    user, err := buildUser(req)
    if err != nil {
        return nil, fmt.Errorf("building user: %w", err)
    }
    if err := s.repo.Save(ctx, user); err != nil {
        return nil, fmt.Errorf("saving user: %w", err)
    }
    s.notifyUserCreated(ctx, user)
    return user, nil
}

func validateCreateUserRequest(req CreateUserRequest) error { /* 10 lines */ }
func buildUser(req CreateUserRequest) (*User, error)        { /* 8 lines */ }
```

```typescript
// BAD — massive arrow function
const processPayment = async (req: PaymentRequest): Promise<PaymentResult> => {
  // 60+ lines of validation, processing, notifications...
};

// GOOD — decomposed
const processPayment = async (req: PaymentRequest): Promise<PaymentResult> => {
  validatePaymentRequest(req);
  const charge = await createCharge(req);
  await notifyPaymentProcessed(charge);
  return toPaymentResult(charge);
};
```

## Parameter Count — 4 Max

Functions with more than 4 parameters are hard to call correctly. Use an options struct/object.

```go
// BAD — 6 parameters, easy to mix up argument order
func SendEmail(to, from, subject, body string, isHTML bool, attachments []string) error

// GOOD — options struct
type SendEmailOptions struct {
    To          string
    From        string
    Subject     string
    Body        string
    IsHTML      bool
    Attachments []string
}

func SendEmail(opts SendEmailOptions) error
```

```typescript
// BAD — positional params
function createUser(name: string, email: string, role: string, tenantId: string,
                    isActive: boolean, metadata: Record<string, string>): Promise<User>

// GOOD — options object with defaults
interface CreateUserOptions {
  name: string;
  email: string;
  role: string;
  tenantId: string;
  isActive?: boolean;   // defaults to true
  metadata?: Record<string, string>;
}

function createUser(opts: CreateUserOptions): Promise<User>
```

## Nesting Depth — 2 Levels Max

Deeply nested code is hard to follow. Use early returns and guard clauses to flatten logic.

```go
// BAD — 4 levels deep
func ProcessItem(item *Item) error {
    if item != nil {
        if item.IsValid() {
            if item.Status == Active {
                if err := item.Process(); err != nil {
                    return err
                }
            }
        }
    }
    return nil
}

// GOOD — flat with early returns
func ProcessItem(item *Item) error {
    if item == nil {
        return ErrNilItem
    }
    if !item.IsValid() {
        return ErrInvalidItem
    }
    if item.Status != Active {
        return nil // nothing to process
    }
    return item.Process()
}
```

```typescript
// BAD — nested conditionals
async function handleRequest(req: Request): Promise<Response> {
  if (req.body) {
    if (req.body.userId) {
      const user = await getUser(req.body.userId);
      if (user) {
        if (user.isActive) {
          return processForUser(user);
        }
      }
    }
  }
  return errorResponse("invalid request");
}

// GOOD — guard clauses
async function handleRequest(req: Request): Promise<Response> {
  if (!req.body?.userId) {
    return errorResponse("missing userId");
  }
  const user = await getUser(req.body.userId);
  if (!user) {
    return errorResponse("user not found");
  }
  if (!user.isActive) {
    return errorResponse("user inactive");
  }
  return processForUser(user);
}
```

## Early Returns

Always check error/edge cases first and return early. The "happy path" should be the least-indented code.

```go
// Pattern: guard → guard → guard → happy path
func (s *Service) UpdateProfile(ctx context.Context, id string, req UpdateProfileRequest) (*Profile, error) {
    // Guard: validate input
    if id == "" {
        return nil, ErrEmptyID
    }
    if err := req.Validate(); err != nil {
        return nil, fmt.Errorf("validation: %w", err)
    }

    // Guard: check existence
    profile, err := s.repo.FindByID(ctx, id)
    if err != nil {
        return nil, fmt.Errorf("finding profile: %w", err)
    }
    if profile == nil {
        return nil, ErrProfileNotFound
    }

    // Guard: check permissions
    if !s.authz.CanUpdate(ctx, profile) {
        return nil, ErrForbidden
    }

    // Happy path — least indented
    profile.Apply(req)
    if err := s.repo.Save(ctx, profile); err != nil {
        return nil, fmt.Errorf("saving profile: %w", err)
    }
    return profile, nil
}
```

## KISS Enforcement

Write the simplest solution that satisfies current requirements. Do not build for hypothetical futures.

**Rules:**
- No premature abstraction — don't create an interface until you have 2+ implementations
- No "just in case" code — YAGNI (You Aren't Gonna Need It)
- No clever tricks — straightforward code that any team member can understand
- No unnecessary generics — use concrete types until generalization is proven needed
- Prefer standard library over third-party for simple tasks

```go
// BAD — premature abstraction for one implementation
type UserNotifier interface {
    Notify(ctx context.Context, user *User, event Event) error
}
type EmailNotifier struct{}
type SMSNotifier struct{}   // never actually used
type PushNotifier struct{}  // never actually used

// GOOD — simple and direct, refactor when needed
func notifyUserByEmail(ctx context.Context, user *User, event Event) error {
    // direct implementation
}
// When you actually need SMS: THEN extract the interface
```

```typescript
// BAD — over-engineered factory for one type
class NotificationFactory {
  static create(type: string): Notification { /* switch on 5 types, only 1 used */ }
}

// GOOD — direct construction
const notification = new EmailNotification(user, event);
// Refactor to factory ONLY when you have 3+ notification types
```

## Incremental Development Protocol

Build → Test → Commit. Never write more than ~100 lines without testing.

**Cycle:**
1. Write a small, focused change (one function, one endpoint, one component)
2. Test it immediately — run the test, hit the endpoint, check the output
3. If it works: commit with a descriptive message
4. If it fails: fix immediately — do not move on to the next feature
5. Repeat

**Anti-patterns:**
- Writing 500 lines across 10 files before testing anything
- "I'll test it all at the end" — NO
- Building an entire feature before compiling — NO
- Moving to the next task when the current one has failing tests — NO

```bash
# Good rhythm
git add user_service.go user_service_test.go
git commit -m "feat(users): add CreateUser with validation"

git add user_handler.go user_handler_test.go
git commit -m "feat(users): add POST /users handler"

# Bad rhythm
# ... write 20 files ...
git add .
git commit -m "add user feature"  # untested monolith
```

## DRY With Judgment

Extract shared code only after 3+ repetitions. Premature DRY creates wrong abstractions.

```go
// First occurrence — just write it inline
func CreateUser(ctx context.Context, req CreateUserReq) error {
    now := time.Now()
    req.CreatedAt = now
    req.UpdatedAt = now
    // ...
}

// Second occurrence — note it, but don't extract yet
func CreateTeam(ctx context.Context, req CreateTeamReq) error {
    now := time.Now()
    req.CreatedAt = now
    req.UpdatedAt = now
    // ...
}

// Third occurrence — NOW extract
func setTimestamps(c Timestampable) {
    now := time.Now()
    c.SetCreatedAt(now)
    c.SetUpdatedAt(now)
}
```

**When to extract immediately (even first time):**
- Security logic (auth checks, input sanitization)
- Business rules that must be consistent (pricing, permissions)
- Complex algorithms that are error-prone to duplicate

## Naming Conventions

### Functions — verb + noun

```go
// GOOD
func GetUser(ctx context.Context, id string) (*User, error)
func ValidateInput(req CreateRequest) error
func SendNotification(ctx context.Context, n *Notification) error
func CalculateDiscount(order *Order) decimal.Decimal

// BAD
func User(id string) (*User, error)       // noun only — is this get? create? delete?
func DoStuff(x interface{}) error          // meaningless
func HandleIt(r *http.Request) error       // vague
```

### Booleans — is/has/can/should prefix

```go
// GOOD
isActive    bool
hasPermission bool
canDelete   bool
shouldRetry bool

// BAD
active      bool  // ambiguous — is this a verb or adjective?
permission  bool  // is this the permission string or a flag?
delete      bool  // is this a command or a state?
```

### TypeScript equivalents

```typescript
// Functions
function getUserById(id: string): Promise<User>
function validateEmail(email: string): boolean
function calculateOrderTotal(items: OrderItem[]): number

// Booleans
const isLoading: boolean = false;
const hasUnsavedChanges: boolean = true;
const canEditProfile: boolean = user.role === 'admin';
```

### No abbreviations

```go
// GOOD
userRepository  // clear
httpClient      // universally known abbreviation — OK
requestContext  // explicit
configuration   // no ambiguity

// BAD
usrRepo    // unclear abbreviation
hc         // what is this?
reqCtx     // save 7 characters, lose readability
cfg        // ambiguous — config? configuration? configure?
```

**Allowed abbreviations:** `id`, `url`, `http`, `api`, `db`, `ctx` (Go context only), `err`, `req`, `res`, `msg`, `pkg`, `cmd`, `env`, `src`, `dst`, `max`, `min`, `len`, `num`, `str`, `fmt`

## Critical Rules

- Self-review is mandatory, not optional — run through the checklist before completing any task
- Functions over 40 lines are a code smell — extract helpers
- More than 4 parameters signals a design problem — use options
- Nesting deeper than 2 levels makes code unreadable — flatten with guards
- Happy path should be the least-indented code path
- Test every ~100 lines — never batch-write large untested changes
- Name things for the reader, not the writer — clarity over brevity
- When in doubt, choose the simpler solution
