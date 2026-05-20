---
skill: graphql
description: GraphQL skill pack — schema design, resolvers, DataLoader, auth, pagination, subscriptions, error handling, testing, performance across gqlgen (Go), Strawberry (Python), graphql-java, async-graphql (Rust), Apollo Server (TS)
version: "1.0"
tags: [graphql, api, schema, dataloader, apollo, gqlgen, strawberry, framework]
---

# GraphQL Skill Pack

## Schema-First vs Code-First

| Approach | When to Use | Libraries |
|----------|------------|-----------|
| **Schema-first** (default) | Multi-team, public APIs, client-first | gqlgen (Go), Apollo Server (TS), graphql-java |
| **Code-first** | Single team, rapid iteration | Strawberry (Python), async-graphql (Rust), Nexus (TS) |

## Schema Design

```graphql
type Query {
  widget(id: ID!): Widget
  widgets(first: Int = 20, after: String, filter: WidgetFilter, orderBy: WidgetOrderBy = CREATED_AT_DESC): WidgetConnection!
  me: User!
}

type Mutation {
  createWidget(input: CreateWidgetInput!): CreateWidgetPayload!
  updateWidget(input: UpdateWidgetInput!): UpdateWidgetPayload!
  deleteWidget(id: ID!): DeleteWidgetPayload!
}

type Subscription {
  widgetChanged(filter: WidgetFilter): WidgetEvent!
}

type Widget implements Node {
  id: ID!
  name: String!
  description: String!
  status: WidgetStatus!
  createdAt: DateTime!
  updatedAt: DateTime!
  createdBy: User!       # resolved via DataLoader
  version: Int!
  tags: [Tag!]!           # resolved via DataLoader
  category: Category
}

interface Node { id: ID! }
enum WidgetStatus { ACTIVE INACTIVE ARCHIVED }

input CreateWidgetInput { name: String!; description: String = ""; categoryId: ID; tagIds: [ID!] }
input UpdateWidgetInput { id: ID!; name: String; description: String; version: Int! }  # version for optimistic locking
input WidgetFilter { status: WidgetStatus; categoryId: ID; search: String; createdAfter: DateTime }

# Every mutation returns payload with typed errors
type CreateWidgetPayload { widget: Widget; errors: [UserError!]! }
type UserError { field: String; message: String!; code: ErrorCode! }
enum ErrorCode { VALIDATION_ERROR NOT_FOUND CONFLICT FORBIDDEN }

scalar DateTime
scalar UUID

# Relay cursor pagination
type WidgetConnection { edges: [WidgetEdge!]!; pageInfo: PageInfo!; totalCount: Int! }
type WidgetEdge { node: Widget!; cursor: String! }
type PageInfo { hasNextPage: Boolean!; hasPreviousPage: Boolean!; startCursor: String; endCursor: String }
```

- Default page size 20, max 100; cursors are opaque base64-encoded strings
- `first`+`after` for forward pagination

## Resolver Patterns (per language)

### Go (gqlgen)
```go
func (r *queryResolver) Widget(ctx context.Context, id string) (*model.Widget, error) {
    return r.widgetSvc.Get(ctx, auth.TenantIDFromContext(ctx), id)
}
func (r *widgetResolver) CreatedBy(ctx context.Context, obj *model.Widget) (*model.User, error) {
    return r.userLoader.Load(ctx, obj.CreatedByID)()
}
```

### Python (Strawberry)
```python
@strawberry.type
class Query:
    @strawberry.field
    async def widget(self, info: Info, id: strawberry.ID) -> Widget | None:
        user = get_current_user(info)
        return await info.context.widget_svc.get(user.tenant_id, id)

@strawberry.type
class Widget:
    @strawberry.field
    async def created_by(self, info: Info) -> User:
        return await info.context.user_loader.load(self.created_by_id)
```

### TypeScript (Apollo Server)
```typescript
export const widgetResolvers = {
  Query: {
    widget: async (_: unknown, args: { id: string }, ctx: Context) => ctx.widgetService.get(ctx.tenantId, args.id),
    widgets: async (_: unknown, args: { first?: number; after?: string; filter?: WidgetFilter }, ctx: Context) => {
      return ctx.widgetService.list(ctx.tenantId, Math.min(args.first ?? 20, 100), args.after, args.filter);
    },
  },
  Widget: {
    createdBy: (parent: Widget, _: unknown, ctx: Context) => ctx.loaders.userLoader.load(parent.createdById),
  },
  Mutation: {
    createWidget: async (_: unknown, args: { input: CreateWidgetInput }, ctx: Context) => {
      try { const widget = await ctx.widgetService.create(ctx.tenantId, ctx.userId, args.input); return { widget, errors: [] }; }
      catch (err) { return { widget: null, errors: [mapToUserError(err)] }; }
    },
  },
};
```

### Java (DGS)
```java
@DgsComponent
public class WidgetDataFetcher {
    @DgsQuery
    public Widget widget(@InputArgument String id, DgsDataFetchingEnvironment dfe) {
        return widgetService.findById(UUID.fromString(id), AuthContext.getTenantId(dfe));
    }
    @DgsData(parentType = "Widget", field = "createdBy")
    public CompletableFuture<User> createdBy(DgsDataFetchingEnvironment dfe) {
        return dfe.<String, User>getDataLoader("userLoader").load(((Widget) dfe.getSource()).getCreatedById().toString());
    }
}
```

### Rust (async-graphql)
```rust
#[Object]
impl QueryRoot {
    async fn widget(&self, ctx: &Context<'_>, id: ID) -> Result<Option<Widget>> {
        let tenant_id = ctx.data::<AuthContext>()?.tenant_id;
        Ok(ctx.data::<Arc<WidgetService>>()?.get(tenant_id, &id).await?)
    }
}
#[Object]
impl Widget {
    async fn created_by(&self, ctx: &Context<'_>) -> Result<User> {
        ctx.data::<DataLoader<UserLoader>>()?.load_one(self.created_by_id).await?.ok_or("user not found".into())
    }
}
```

## DataLoader

```
Contract: Input [key1, key2, ...] -> Output [value1, value2, ...] (same order, same length)
- Missing items = null at their index position
- Instances are per-request (not shared across requests)
- Batch function called once per event loop tick
```

```typescript
export function createLoaders(db: Database) {
  return {
    userLoader: new DataLoader<string, User>(async (ids) => {
      const users = await db.users.findByIds([...ids]);
      const map = new Map(users.map(u => [u.id, u]));
      return ids.map(id => map.get(id) ?? null);
    }),
  };
}
```

## Auth
- Authentication in context setup (validate JWT, extract user/tenant)
- Authorization in resolvers or directives
- `tenant_id` from auth context, NEVER from query arguments
- Subscriptions MUST filter by tenant_id

## Error Handling
- **System errors** in top-level `errors` array (auth failures, internal errors)
- **User errors** in mutation payload `errors` field (business rule violations)
- Never expose internal error messages; use error codes for programmatic handling

## Performance
- Query complexity limits (assign cost per field, reject over threshold)
- Depth limiting (default max 10)
- Persisted queries in production (hash instead of full query, prevents arbitrary queries)

## Library Reference

| Language | Schema-First | Code-First | DataLoader |
|----------|-------------|------------|------------|
| Go | gqlgen | — | graph-gophers/dataloader |
| Python | Ariadne | Strawberry | aiodataloader |
| Java | DGS (Netflix) | graphql-java-kickstart | java-dataloader |
| Rust | — | async-graphql | built-in |
| TypeScript | Apollo Server | Nexus, TypeGraphQL | dataloader (npm) |

## Critical Rules
- Relay cursor pagination, not offset
- Every mutation returns payload with `errors: [UserError!]!`
- Every list field MUST use DataLoader
- DataLoader instances are per-request
- Set complexity + depth limits
- Schema changes MUST be backward compatible (GraphQL Inspector in CI)
- Subscriptions filter by tenant_id
- Use persisted queries in production
