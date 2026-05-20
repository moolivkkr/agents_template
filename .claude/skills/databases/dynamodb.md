# DynamoDB patterns for serverless, high-scale key-value and document storage.

## Table Design
```
Table: Widgets
  Partition Key (PK): TENANT#<tenant_id>
  Sort Key (SK):      WIDGET#<widget_id>

  GSI1 (Global Secondary Index):
    GSI1PK: TENANT#<tenant_id>
    GSI1SK: STATUS#<status>#<created_at>
    → Query: "all active widgets for tenant, sorted by creation date"

  LSI1 (Local Secondary Index):
    Same PK, alternate SK: UPDATED#<updated_at>
    → Query: "widgets for tenant, sorted by last update"
```
- Partition key determines data distribution — choose high-cardinality keys (tenant_id)
- Sort key enables range queries within a partition — encode hierarchy or time ordering
- GSI for alternate access patterns — each GSI is a full copy of projected attributes
- LSI for alternate sort orders within the same partition — must be created at table creation time
- Design tables around access patterns, not entity relationships

## Single-Table Design
```
PK                      | SK                          | Type    | Data
TENANT#abc              | METADATA                    | Tenant  | {name, plan, ...}
TENANT#abc              | WIDGET#w1                   | Widget  | {name, status, ...}
TENANT#abc              | WIDGET#w1#COMPONENT#c1      | Comp    | {type, config, ...}
TENANT#abc              | WIDGET#w1#COMPONENT#c2      | Comp    | {type, config, ...}
TENANT#abc              | WIDGET#w2                   | Widget  | {name, status, ...}
TENANT#abc              | USER#u1                     | User    | {email, role, ...}

GSI1PK                  | GSI1SK
TENANT#abc              | STATUS#active#2026-01-15    | Widget  | → all active widgets sorted by date
TENANT#abc              | ROLE#admin                  | User    | → all admins for tenant
```
- Single-table design stores multiple entity types in one table
- Use PK/SK prefixes to distinguish entity types: `WIDGET#`, `USER#`, `COMPONENT#`
- Hierarchical sort keys enable fetching parent + children: `begins_with(SK, "WIDGET#w1")`
- GSI overloading: different entity types use the same GSI with different prefix patterns
- Use single-table design for related entities accessed together — separate tables for independent entities

## Query vs Scan
```typescript
// ALWAYS prefer Query — O(items returned), reads only matching partition
const result = await client.send(new QueryCommand({
  TableName: "Widgets",
  KeyConditionExpression: "PK = :pk AND begins_with(SK, :skPrefix)",
  ExpressionAttributeValues: {
    ":pk": { S: `TENANT#${tenantId}` },
    ":skPrefix": { S: "WIDGET#" },
  },
  Limit: 21, // pageSize + 1 for has_more detection
  ExclusiveStartKey: cursor ? JSON.parse(Buffer.from(cursor, "base64").toString()) : undefined,
}));

// NEVER use Scan in production — O(entire table), expensive, slow
// Only acceptable for: one-time data migrations, analytics exports, admin tooling
```
- Query reads a single partition — cost proportional to items returned
- Scan reads the entire table — cost proportional to table size
- Filter expressions reduce returned items but do NOT reduce read capacity consumed
- Always design GSIs to avoid Scan — if you need Scan, your data model is wrong

## Conditional Writes (Optimistic Locking)
```typescript
// Create — fail if item already exists
await client.send(new PutItemCommand({
  TableName: "Widgets",
  Item: marshall(widget),
  ConditionExpression: "attribute_not_exists(PK)",
}));

// Update with version check — optimistic locking
await client.send(new UpdateItemCommand({
  TableName: "Widgets",
  Key: marshall({ PK: pk, SK: sk }),
  UpdateExpression: "SET #name = :name, #version = :newVersion, #updatedAt = :now",
  ConditionExpression: "#version = :expectedVersion",
  ExpressionAttributeNames: {
    "#name": "name",
    "#version": "version",
    "#updatedAt": "updatedAt",
  },
  ExpressionAttributeValues: marshall({
    ":name": input.name,
    ":newVersion": currentVersion + 1,
    ":expectedVersion": currentVersion,
    ":now": new Date().toISOString(),
  }),
}));
// Throws ConditionalCheckFailedException on version mismatch
```
- `ConditionExpression` on every write — prevents race conditions
- `attribute_not_exists(PK)` for create — prevents duplicate inserts
- Version attribute for updates — increment on every write, reject stale writes
- Conditional writes are atomic — no separate read-then-write needed

## DynamoDB Streams for Event Processing
```typescript
// Lambda handler for DynamoDB Streams (event-driven processing)
export const handler = async (event: DynamoDBStreamEvent) => {
  for (const record of event.Records) {
    const eventName = record.eventName; // INSERT, MODIFY, REMOVE
    const newImage = record.dynamodb?.NewImage
      ? unmarshall(record.dynamodb.NewImage)
      : null;
    const oldImage = record.dynamodb?.OldImage
      ? unmarshall(record.dynamodb.OldImage)
      : null;

    switch (eventName) {
      case "INSERT":
        await handleWidgetCreated(newImage);
        break;
      case "MODIFY":
        await handleWidgetUpdated(oldImage, newImage);
        break;
      case "REMOVE":
        await handleWidgetDeleted(oldImage);
        break;
    }
  }
};
```
- Streams capture item-level changes — use for event sourcing, sync, audit
- Enable `NEW_AND_OLD_IMAGES` stream view type for change detection
- Lambda triggers process stream records — at-least-once delivery
- Use for: search index sync, cross-region replication, audit logging, notifications

## Pagination
```typescript
// Cursor-based pagination with ExclusiveStartKey
async function listWidgets(tenantId: string, cursor?: string, pageSize = 20) {
  const params: QueryCommandInput = {
    TableName: "Widgets",
    KeyConditionExpression: "PK = :pk AND begins_with(SK, :prefix)",
    ExpressionAttributeValues: marshall({
      ":pk": `TENANT#${tenantId}`,
      ":prefix": "WIDGET#",
    }),
    Limit: pageSize + 1,
    ScanIndexForward: false, // descending order
  };

  if (cursor) {
    params.ExclusiveStartKey = JSON.parse(
      Buffer.from(cursor, "base64url").toString(),
    );
  }

  const result = await client.send(new QueryCommand(params));
  const items = (result.Items ?? []).map(unmarshall);
  const hasMore = items.length > pageSize;
  if (hasMore) items.pop();

  const nextCursor = hasMore && result.LastEvaluatedKey
    ? Buffer.from(JSON.stringify(result.LastEvaluatedKey)).toString("base64url")
    : undefined;

  return { items, hasMore, cursor: nextCursor };
}
```
- Use `ExclusiveStartKey` / `LastEvaluatedKey` for pagination — never offset
- Encode `LastEvaluatedKey` as opaque base64 cursor — never expose raw DynamoDB keys
- Request `Limit + 1` to detect `hasMore` without extra query

## Cost Optimization
```
On-Demand Mode:
  - Pay per request — no capacity planning
  - Best for: unpredictable traffic, new workloads, dev/staging
  - ~$1.25 per million write request units, ~$0.25 per million read request units

Provisioned Mode:
  - Set read/write capacity units (RCU/WCU)
  - Best for: predictable traffic, steady-state production
  - ~5x cheaper than on-demand at sustained load
  - Use auto-scaling: min/max capacity with target utilization (70%)

Reserved Capacity:
  - 1-year or 3-year commitment for additional ~50-75% savings
  - Best for: stable production workloads with predictable baseline
```
- Start with on-demand, switch to provisioned when traffic patterns stabilize
- One read capacity unit (RCU) = one strongly consistent read per second for items up to 4KB
- One write capacity unit (WCU) = one write per second for items up to 1KB
- Batch operations (`BatchWriteItem`, `BatchGetItem`) for bulk reads/writes — up to 25 items
- Use `ProjectionExpression` to read only needed attributes — reduces RCU consumption

## Local Development with DynamoDB Local
```bash
# Docker
docker run -d -p 8000:8000 amazon/dynamodb-local

# Create table locally
aws dynamodb create-table \
  --endpoint-url http://localhost:8000 \
  --table-name Widgets \
  --attribute-definitions \
    AttributeName=PK,AttributeType=S \
    AttributeName=SK,AttributeType=S \
  --key-schema \
    AttributeName=PK,KeyType=HASH \
    AttributeName=SK,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST
```
```typescript
// SDK configuration for local
const client = new DynamoDBClient({
  endpoint: process.env.DYNAMODB_ENDPOINT ?? "http://localhost:8000",
  region: "us-east-1",
  credentials: { accessKeyId: "local", secretAccessKey: "local" },
});
```

## SDK Patterns by Language

### TypeScript (AWS SDK v3)
```typescript
import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient, PutCommand, QueryCommand } from "@aws-sdk/lib-dynamodb";

const ddbClient = new DynamoDBClient({});
const docClient = DynamoDBDocumentClient.from(ddbClient, {
  marshallOptions: { removeUndefinedValues: true },
});

await docClient.send(new PutCommand({ TableName: "Widgets", Item: widget }));
```

### Python (boto3)
```python
import boto3
from boto3.dynamodb.conditions import Key

table = boto3.resource("dynamodb").Table("Widgets")

# Query
response = table.query(
    KeyConditionExpression=Key("PK").eq(f"TENANT#{tenant_id}") & Key("SK").begins_with("WIDGET#"),
    Limit=21,
)

# Put with condition
table.put_item(
    Item=widget,
    ConditionExpression="attribute_not_exists(PK)",
)
```

### Go (aws-sdk-go-v2)
```go
import (
    "github.com/aws/aws-sdk-go-v2/service/dynamodb"
    "github.com/aws/aws-sdk-go-v2/feature/dynamodb/attributevalue"
)

input := &dynamodb.QueryInput{
    TableName:              aws.String("Widgets"),
    KeyConditionExpression: aws.String("PK = :pk AND begins_with(SK, :prefix)"),
    ExpressionAttributeValues: map[string]types.AttributeValue{
        ":pk":     &types.AttributeValueMemberS{Value: "TENANT#" + tenantID},
        ":prefix": &types.AttributeValueMemberS{Value: "WIDGET#"},
    },
    Limit: aws.Int32(21),
}
result, err := client.Query(ctx, input)
```

## Rules
- Design around access patterns — not entity relationships (this is NOT relational modeling)
- Query over Scan — always. If you need Scan, add a GSI
- Conditional writes on every mutation — prevent race conditions and duplicates
- Version attribute for optimistic locking — increment on every update
- Single-table design for related entities — separate tables for independent domains
- Opaque cursors for pagination — never expose raw DynamoDB keys to clients
- Start with on-demand pricing — switch to provisioned when traffic stabilizes
- DynamoDB Local for development — never hit production tables from dev
- `ProjectionExpression` to limit returned attributes — reduces cost and latency
- Item size limit: 400KB — design items to stay well under this (< 50KB recommended)
