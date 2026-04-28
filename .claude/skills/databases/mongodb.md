# MongoDB patterns for document-oriented data storage.

## Document Design
```javascript
// Embed for 1:1 and 1:few (read together, updated together)
{
  _id: ObjectId,
  name: "Alice",
  address: { street: "123 Main", city: "Portland" }  // embedded
}

// Reference for 1:many (large arrays, queried independently)
{
  _id: ObjectId,
  userId: ObjectId,  // reference to users collection
  createdAt: ISODate
}
```
- Embed when data is always accessed together
- Reference when sub-documents are > 16MB, frequently updated independently, or queried on their own

## Indexes
```javascript
// Single field
db.users.createIndex({ email: 1 }, { unique: true })

// Compound (order matters — match query field order)
db.orders.createIndex({ userId: 1, status: 1, createdAt: -1 })

// Text search
db.articles.createIndex({ title: "text", body: "text" })

// TTL (auto-delete documents)
db.sessions.createIndex({ expiresAt: 1 }, { expireAfterSeconds: 0 })
```
Rule: index every field used in `find()`, `sort()`, or aggregation `$match`.

## Aggregation Pipeline
```javascript
// Prefer aggregation over multiple queries
db.orders.aggregate([
    { $match: { status: "completed", userId: userId } },
    { $group: { _id: "$product", total: { $sum: "$amount" } } },
    { $sort: { total: -1 } },
    { $limit: 10 }
])
```
Use `$lookup` sparingly — document design should minimize joins.

## Transactions
```javascript
const session = client.startSession()
await session.withTransaction(async () => {
    await orders.insertOne(order, { session })
    await inventory.updateOne({ _id: productId }, { $inc: { qty: -1 } }, { session })
})
```
Transactions require a replica set (even single-node with `--replSet`). Keep transactions short.

## Schema Validation
```javascript
db.createCollection("users", {
    validator: {
        $jsonSchema: {
            required: ["email", "createdAt"],
            properties: {
                email: { bsonType: "string", pattern: "^.+@.+$" }
            }
        }
    }
})
```

## Rules
- `camelCase` field names (JavaScript convention)
- Never store unbounded arrays in a document — use references + pagination
- `ObjectId` for `_id` unless you have a natural unique key
- Connection pool: set `maxPoolSize` explicitly (default 100)
- Use `$set` in updates — never replace entire documents unless intended
