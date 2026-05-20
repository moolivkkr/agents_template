# Firestore patterns for document-oriented cloud-native data storage.

## Document Model
```
// Collection / Document / Subcollection hierarchy
tenants/
  {tenantId}/
    widgets/
      {widgetId}          → { name, description, status, createdAt, ... }
        components/
          {componentId}   → { type, config, sortOrder, ... }
    users/
      {userId}            → { email, role, ... }
```
- Documents contain fields (key-value pairs) — max 1MB per document
- Collections contain documents — collections are created implicitly
- Subcollections for 1:many relationships accessed together (widget -> components)
- Document references for loose relationships (widget.createdBy -> users/{userId})
- Collection group queries can search across all subcollections with the same name

## Data Modeling Decisions

| Pattern | When to Use | Example |
|---------|------------|---------|
| **Subcollection** | Parent-child, always queried together | Widget -> Components |
| **Root collection** | Independent entities, queried separately | Users, Tenants |
| **Embedded map** | Small, rarely updated, always read with parent | Widget.metadata |
| **Document reference** | Loose coupling, independent lifecycle | Widget.createdBy |

```typescript
// Subcollection — components belong to a widget
const componentRef = db
  .collection("tenants").doc(tenantId)
  .collection("widgets").doc(widgetId)
  .collection("components").doc(componentId);

// Root collection — users are independent
const userRef = db.collection("tenants").doc(tenantId)
  .collection("users").doc(userId);

// Embedded map — small metadata stored directly
interface Widget {
  name: string;
  status: "active" | "draft" | "archived";
  metadata: {                // embedded, not a subcollection
    priority: number;
    tags: string[];
  };
  createdBy: DocumentReference; // reference to user document
  createdAt: Timestamp;
  updatedAt: Timestamp;
  version: number;
}
```

## Security Rules
```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {

    // Tenant isolation — all data scoped under /tenants/{tenantId}
    match /tenants/{tenantId} {

      // Only authenticated users belonging to this tenant
      function isTenantMember() {
        return request.auth != null
            && request.auth.token.tenant_id == tenantId;
      }

      function isAdmin() {
        return isTenantMember()
            && request.auth.token.role == "admin";
      }

      // Tenant document — read by members, write by admins
      allow read: if isTenantMember();
      allow write: if isAdmin();

      // Widgets — CRUD for tenant members
      match /widgets/{widgetId} {
        allow read: if isTenantMember();
        allow create: if isTenantMember()
            && request.resource.data.keys().hasAll(["name", "status", "createdAt"])
            && request.resource.data.name is string
            && request.resource.data.name.size() > 0
            && request.resource.data.name.size() <= 255;
        allow update: if isTenantMember()
            && request.resource.data.version == resource.data.version + 1;
        allow delete: if isAdmin();

        // Components — nested under widgets
        match /components/{componentId} {
          allow read, write: if isTenantMember();
        }
      }

      // Users — read by members, write by admins
      match /users/{userId} {
        allow read: if isTenantMember();
        allow write: if isAdmin() || request.auth.uid == userId;
      }
    }
  }
}
```
- Rules are deny-by-default — no match = denied
- Always validate required fields and types in rules — defense in depth
- `request.auth.token.tenant_id` comes from custom claims set during auth
- Optimistic locking in rules: `request.resource.data.version == resource.data.version + 1`
- Never use wildcard rules (`match /{document=**}`) in production

## Real-Time Listeners
```typescript
// Listen to a single document
const unsubscribe = db
  .collection("tenants").doc(tenantId)
  .collection("widgets").doc(widgetId)
  .onSnapshot(
    (snapshot) => {
      if (snapshot.exists) {
        const widget = { id: snapshot.id, ...snapshot.data() };
        updateUI(widget);
      }
    },
    (error) => {
      console.error("Snapshot listener error:", error);
    },
  );

// Listen to a collection with query
const unsubscribeList = db
  .collection("tenants").doc(tenantId)
  .collection("widgets")
  .where("status", "==", "active")
  .orderBy("createdAt", "desc")
  .limit(50)
  .onSnapshot((snapshot) => {
    snapshot.docChanges().forEach((change) => {
      switch (change.type) {
        case "added":
          addWidgetToUI(change.doc.data());
          break;
        case "modified":
          updateWidgetInUI(change.doc.data());
          break;
        case "removed":
          removeWidgetFromUI(change.doc.id);
          break;
      }
    });
  });

// IMPORTANT: Always unsubscribe when component unmounts
unsubscribe();
unsubscribeList();
```
- `onSnapshot` provides real-time updates — no polling needed
- `docChanges()` provides granular change types: added, modified, removed
- Always unsubscribe listeners when they are no longer needed — prevents memory leaks
- First snapshot includes all matching documents — subsequent snapshots are incremental

## Batch Writes and Transactions
```typescript
// Batch write — atomic, up to 500 operations, no reads
const batch = db.batch();

const widgetRef = db.collection("tenants").doc(tenantId)
  .collection("widgets").doc();
batch.set(widgetRef, {
  name: "New Widget",
  status: "active",
  createdAt: FieldValue.serverTimestamp(),
  version: 1,
});

const statsRef = db.collection("tenants").doc(tenantId);
batch.update(statsRef, {
  widgetCount: FieldValue.increment(1),
});

await batch.commit(); // atomic — all succeed or all fail

// Transaction — atomic reads + writes (for optimistic locking)
await db.runTransaction(async (transaction) => {
  const widgetRef = db.collection("tenants").doc(tenantId)
    .collection("widgets").doc(widgetId);
  const snapshot = await transaction.get(widgetRef);

  if (!snapshot.exists) {
    throw new Error("Widget not found");
  }

  const current = snapshot.data()!;
  if (current.version !== expectedVersion) {
    throw new Error("Version conflict — reload and retry");
  }

  transaction.update(widgetRef, {
    name: newName,
    updatedAt: FieldValue.serverTimestamp(),
    version: current.version + 1,
  });
});
```
- Batch writes: up to 500 operations, atomic, no reads — use for bulk mutations
- Transactions: read-then-write atomic operations — use for optimistic locking
- Transactions retry automatically on contention (up to 5 times by default)
- `FieldValue.serverTimestamp()` for consistent timestamps — never use client time
- `FieldValue.increment(n)` for atomic counters — no read-modify-write needed

## Offline Support
```typescript
// Enable persistence (web)
firebase.firestore().enablePersistence({ synchronizeTabs: true })
  .catch((err) => {
    if (err.code === "failed-precondition") {
      // Multiple tabs open — persistence can only be enabled in one tab
    } else if (err.code === "unimplemented") {
      // Browser doesn't support persistence
    }
  });

// Enable persistence (mobile — enabled by default on iOS/Android)
// No additional configuration needed

// Check online status
firebase.firestore().enableNetwork();  // go online
firebase.firestore().disableNetwork(); // force offline (for testing)

// Writes while offline are queued and synced when online
// Reads while offline use cached data
// onSnapshot listeners fire with cached data (metadata.fromCache = true)
```
- Persistence enabled by default on mobile, opt-in on web
- Offline writes are queued and committed when connection restores
- `synchronizeTabs: true` shares cache across browser tabs
- `snapshot.metadata.fromCache` indicates whether data came from cache or server

## Indexing
```
// firestore.indexes.json — required for composite queries
{
  "indexes": [
    {
      "collectionGroup": "widgets",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "status", "order": "ASCENDING" },
        { "fieldPath": "createdAt", "order": "DESCENDING" }
      ]
    },
    {
      "collectionGroup": "widgets",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "status", "order": "ASCENDING" },
        { "fieldPath": "priority", "order": "DESCENDING" },
        { "fieldPath": "createdAt", "order": "DESCENDING" }
      ]
    }
  ]
}
```
- Single-field indexes are created automatically — no configuration needed
- Composite indexes (2+ fields) must be explicitly defined
- Firestore error messages include a direct link to create the missing index
- Deploy indexes: `firebase deploy --only firestore:indexes`
- Index merging: Firestore combines single-field indexes for some queries automatically

## Emulator for Local Development
```bash
# Install Firebase CLI
npm install -g firebase-tools

# Start emulator
firebase emulators:start --only firestore

# Emulator runs at http://localhost:8080
# Emulator UI at http://localhost:4000
```
```typescript
// Connect to emulator in development
if (process.env.NODE_ENV === "development") {
  db.useEmulator("localhost", 8080);
}

// Import/export data for reproducible tests
firebase emulators:start --import=./test-data --export-on-exit=./test-data
```
- Emulator provides full Firestore API locally — no cloud project needed
- Security rules are enforced by the emulator — test rules locally
- Import/export for reproducible test data sets
- Emulator UI for visual data inspection and rule testing

## Rules
- Tenant isolation via document path: `/tenants/{tenantId}/...` — enforced by security rules
- Security rules validate structure, types, and required fields — defense in depth
- `onSnapshot` for real-time — always unsubscribe when done
- Transactions for read-modify-write (optimistic locking) — batch writes for bulk mutations
- `FieldValue.serverTimestamp()` for all timestamps — never trust client clocks
- Composite indexes must be explicitly defined — single-field indexes are automatic
- Subcollections for parent-child relationships — root collections for independent entities
- Embedded maps for small, rarely-updated data — subcollections for growing lists
- Emulator for all local development and testing — never use production in dev
- Max 1 write per second per document — shard counters for high-write fields
