---
skill: message-queue-pattern
description: Language-neutral message queue archetype — producer/consumer, exactly-once, fan-out, saga, DLQ, schema evolution, observability across Kafka, RabbitMQ, SQS, Redis Streams, NATS
version: "1.0"
tags:
  - message-queue
  - kafka
  - rabbitmq
  - sqs
  - nats
  - redis-streams
  - event-driven
  - archetype
  - backend
---

# Message Queue Pattern

Complete production-ready message queue patterns for event-driven architectures. Technology-agnostic with notes on where patterns differ per broker.

## Core Concepts

Message queues decouple producers from consumers, enabling asynchronous communication, load leveling, and fault tolerance.

```
Producer                    Broker                    Consumer
   |                          |                          |
   |-- publish(msg) --------->|                          |
   |                          |-- deliver(msg) --------->|
   |                          |                          |-- process
   |                          |<-- ack ------------------|
   |                          |                          |
   |                          |-- deliver(msg2) -------->|
   |                          |                          |-- FAIL
   |                          |<-- nack/reject ----------|
   |                          |                          |
   |                          |-- redeliver(msg2) ------>| (retry)
   |                          |                          |
   |                          |-- move to DLQ ---------->| (after max retries)
```

## Message Envelope

Every message MUST follow a standard envelope for consistency across services.

```json
{
    "id": "msg-uuid-v7",
    "type": "order.created",
    "source": "order-service",
    "tenant_id": "tenant-uuid",
    "correlation_id": "trace-uuid",
    "causation_id": "parent-msg-uuid",
    "timestamp": "2024-01-15T09:30:00Z",
    "version": "1.0",
    "data": {
        "order_id": "order-uuid",
        "customer_id": "customer-uuid",
        "total": 150.00,
        "currency": "USD"
    },
    "metadata": {
        "idempotency_key": "order-uuid-created",
        "content_type": "application/json",
        "schema": "order.created.v1"
    }
}
```

| Field | Purpose |
|-------|---------|
| `id` | Unique message ID — used for deduplication |
| `type` | Event type — dot-notation: `{aggregate}.{event}` |
| `source` | Publishing service name |
| `tenant_id` | Tenant isolation — consumers filter by this |
| `correlation_id` | Trace ID for distributed tracing |
| `causation_id` | ID of the message that caused this one (for event chains) |
| `timestamp` | When the event occurred (not when it was published) |
| `version` | Schema version — enables evolution |
| `data` | Event-specific payload |
| `metadata.idempotency_key` | Consumer deduplication key |

## Producer Pattern

```
function publish(event_type, tenant_id, data, options={}):
    message = {
        id:             generate_uuid_v7(),
        type:           event_type,
        source:         service_name,
        tenant_id:      tenant_id,
        correlation_id: options.correlation_id or current_trace_id(),
        causation_id:   options.causation_id,
        timestamp:      now_utc(),
        version:        schema_registry.current_version(event_type),
        data:           data,
        metadata: {
            idempotency_key: options.idempotency_key or generate_uuid(),
            content_type:    "application/json",
            schema:          event_type + ".v" + version,
        }
    }

    // Serialize
    payload = serialize(message, format=config.serialization_format)

    // Publish with delivery guarantee
    broker.publish(
        topic:       event_type_to_topic(event_type),
        key:         options.partition_key or tenant_id,  // ensures ordering per tenant
        payload:     payload,
        headers:     extract_trace_headers(),
    )

    logger.info("message.published",
        message_id=message.id,
        type=event_type,
        tenant_id=tenant_id,
        topic=topic,
    )

    metrics.increment("messages.published", tags={type: event_type})
```

### Transactional Outbox Pattern

For exactly-once publishing when the event must be consistent with a database write:

```
function create_order_with_event(ctx, tenant_id, order_data):
    // Single transaction: write entity + outbox event
    transaction:
        order = orders_table.insert(order_data)

        outbox_table.insert({
            id:          generate_uuid(),
            topic:       "orders",
            type:        "order.created",
            key:         tenant_id,
            payload:     serialize(order),
            tenant_id:   tenant_id,
            created_at:  now(),
            published:   false,
        })

    // Background process reads outbox and publishes
    // (Debezium CDC or polling publisher)
    return order

// Outbox publisher (runs periodically or via CDC)
function publish_outbox():
    unpublished = outbox_table.select(published=false, limit=100, order_by=created_at)
    for entry in unpublished:
        broker.publish(topic=entry.topic, key=entry.key, payload=entry.payload)
        outbox_table.update(entry.id, published=true, published_at=now())
```

## Consumer Pattern

```
function consume(ctx, topic, handler):
    consumer = broker.subscribe(topic, group=service_name)

    while not ctx.cancelled():
        message = consumer.receive(timeout=30s)
        if message is null:
            continue

        logger.info("message.received",
            message_id=message.id,
            type=message.type,
            tenant_id=message.tenant_id,
        )

        span = tracer.start_span("consumer." + message.type,
            parent=extract_trace_context(message))

        try:
            // Idempotency check
            if idempotency_store.is_processed(message.metadata.idempotency_key):
                logger.info("message.duplicate_skipped", message_id=message.id)
                consumer.ack(message)
                continue

            // Process
            handler.handle(ctx, message)

            // Mark as processed
            idempotency_store.mark_processed(
                message.metadata.idempotency_key,
                ttl=7d,  // longer TTL for messages than for jobs
            )

            consumer.ack(message)
            metrics.increment("messages.processed", tags={type: message.type, status: "success"})

        catch RetryableError:
            consumer.nack(message)  // will be redelivered
            metrics.increment("messages.processed", tags={type: message.type, status: "retry"})

        catch NonRetryableError:
            consumer.send_to_dlq(message, error)
            metrics.increment("messages.processed", tags={type: message.type, status: "dlq"})

        finally:
            span.end()
            metrics.histogram("message.processing_duration", elapsed, tags={type: message.type})
```

## Exactly-Once Processing (Idempotency Keys)

```
True exactly-once delivery is impossible in distributed systems.
Instead, achieve exactly-once PROCESSING via idempotency.

Strategy 1: Idempotency Key Store (Redis/DB)
    - Store processed idempotency keys with TTL
    - Check before processing, mark after success
    - TTL must be longer than the max redelivery window

Strategy 2: Unique Constraint
    - If processing creates a DB record, use a unique constraint
    - ON CONFLICT DO NOTHING — the second attempt is a no-op
    - Works well for "create" events

Strategy 3: Version Check
    - If processing updates a record, check the version
    - Only apply if message.version > current.version
    - Naturally idempotent for "update" events

Recommendation: Use Strategy 1 as the default. Add Strategy 2 or 3
for specific handlers where the DB operation provides natural idempotency.
```

## Fan-Out Pattern

One message triggers processing by multiple independent consumers.

```
Pattern 1: Topic-based fan-out (Kafka, NATS)
    Producer publishes to topic "order.created"
    Consumer Group A (email-service) subscribes → sends confirmation email
    Consumer Group B (analytics-service) subscribes → updates metrics
    Consumer Group C (inventory-service) subscribes → reserves stock

    Each consumer group gets its own copy of every message.

Pattern 2: Exchange-based fan-out (RabbitMQ)
    Producer publishes to fanout exchange "order-events"
    Exchange routes to:
        - queue "email-order-created" → email-service
        - queue "analytics-order-created" → analytics-service
        - queue "inventory-order-created" → inventory-service

Pattern 3: SNS + SQS fan-out (AWS)
    Producer publishes to SNS topic "order-created"
    SNS fans out to:
        - SQS queue "email-order-created" → email-service
        - SQS queue "analytics-order-created" → analytics-service
```

## Saga / Choreography Pattern

Multi-step workflows coordinated via events (no central orchestrator).

```
Order Saga (choreography):

1. order-service publishes "order.created"
2. payment-service subscribes:
    - processes payment
    - publishes "payment.completed" or "payment.failed"
3. inventory-service subscribes to "payment.completed":
    - reserves inventory
    - publishes "inventory.reserved" or "inventory.insufficient"
4. shipping-service subscribes to "inventory.reserved":
    - creates shipment
    - publishes "shipment.created"
5. order-service subscribes to all:
    - "payment.completed" → update order status to "paid"
    - "inventory.reserved" → update to "fulfilling"
    - "shipment.created" → update to "shipped"
    - "payment.failed" → update to "cancelled"
    - "inventory.insufficient" → publish "payment.refund_requested"

Compensating events (rollback):
    payment.failed       → cancel order, release inventory
    inventory.insufficient → refund payment, cancel order
    shipment.failed       → refund payment, release inventory, cancel order
```

### Saga Rules

- Every step MUST have a compensating action
- Events MUST carry enough data for compensation (don't rely on querying)
- Use `causation_id` to link events in the saga chain
- Set a saga timeout — if the saga doesn't complete in N minutes, trigger compensation
- Monitor for stuck sagas — alert when events are missing

## Error Handling

```
Error Classification:
    Transient (retryable):
        - Network timeout
        - Database connection lost
        - Rate limited by downstream
        → Retry with exponential backoff

    Permanent (non-retryable):
        - Invalid message format
        - Business rule violation
        - Unknown message type
        → Send to DLQ immediately

    Poison Message:
        - Causes consumer to crash repeatedly
        - Detected by retry count exceeding threshold
        → Send to DLQ, alert on-call

DLQ Strategy:
    1. Dead-letter after max_retries (default: 5)
    2. Include original message, error, attempt count, timestamp
    3. Monitor DLQ depth — alert if > 0
    4. Provide manual replay tool for ops team
    5. Replay with original ordering when possible
```

## Schema Evolution

```
Strategy: Schema Registry (Avro/Protobuf recommended for high-throughput)

Compatibility modes:
    BACKWARD  — new schema can read old data (add optional fields)
    FORWARD   — old schema can read new data (remove optional fields)
    FULL      — both backward and forward compatible

Safe changes (backward compatible):
    - Add a new optional field
    - Add a new enum value
    - Widen a numeric type (int32 → int64)

Unsafe changes (breaking):
    - Remove a required field
    - Change a field type
    - Rename a field

For JSON messages without schema registry:
    - Always add fields, never remove
    - Consumers MUST ignore unknown fields
    - Include "version" in the envelope
    - Version-specific deserialization:
        if message.version == "1.0": parse_v1(message.data)
        if message.version == "2.0": parse_v2(message.data)
```

## Broker-Specific Notes

### Kafka

```
Ordering:          Per-partition (use tenant_id as partition key)
Retention:         Time-based (7d default) or size-based
Consumer groups:   Built-in, auto-rebalancing
Exactly-once:      Idempotent producer + transactional consumer
Dead letter:       Manual — consume, process, forward to DLQ topic
At-rest encryption: TLS + disk encryption
Message size:      1MB default (configurable, keep small)
```

### RabbitMQ

```
Ordering:          Per-queue (single consumer) or best-effort
Retention:         Until consumed (or TTL)
Consumer groups:   Multiple consumers on same queue = competing consumers
Exactly-once:      Publisher confirms + consumer ack
Dead letter:       Built-in DLX (dead letter exchange)
At-rest encryption: Disk encryption
Message size:      128MB max (keep under 1MB)
Routing:           Flexible — direct, topic, fanout, headers exchanges
```

### AWS SQS/SNS

```
Ordering:          FIFO queues (with deduplication), or best-effort (standard)
Retention:         4d default (up to 14d)
Consumer groups:   Multiple SQS queues subscribed to SNS
Exactly-once:      FIFO with deduplication ID
Dead letter:       Built-in redrive policy
At-rest encryption: AWS KMS
Message size:      256KB (use S3 for larger)
Visibility timeout: Must be > processing time
```

### Redis Streams

```
Ordering:          Per-stream (append-only log)
Retention:         MAXLEN or MINID trimming
Consumer groups:   Built-in XREADGROUP, auto-ack tracking
Exactly-once:      Idempotency key in consumer
Dead letter:       Manual — XCLAIM for stuck messages, move to DLQ stream
At-rest encryption: Redis encryption at rest
Message size:      512MB max per entry (keep under 1MB)
Pending list:      XPENDING for monitoring unacked messages
```

### NATS / NATS JetStream

```
Ordering:          Per-subject (JetStream)
Retention:         Limits or interest-based (JetStream)
Consumer groups:   Queue groups (core NATS) or durable consumers (JetStream)
Exactly-once:      JetStream with dedup window
Dead letter:       Manual — max delivery count, then advisory
At-rest encryption: File store encryption (JetStream)
Message size:      1MB default
Lightweight:       Single binary, no ZooKeeper, no Raft
```

## Observability

```
Metrics:
    messages_published_total{topic, type}              # counter
    messages_consumed_total{topic, type, status}       # counter
    messages_dlq_total{topic, type}                    # counter
    message_processing_duration_seconds{topic, type}   # histogram
    message_lag{topic, consumer_group}                 # gauge (Kafka)
    queue_depth{queue_name}                            # gauge
    consumer_rebalance_total                           # counter (Kafka)

Logging:
    Every message publish/consume MUST log:
    - message_id
    - type
    - tenant_id
    - correlation_id
    - topic/queue
    - processing duration (on consume)
    - error (on failure)

Tracing:
    - Producer creates a span: "publish.{type}"
    - Consumer creates a child span: "consume.{type}"
    - Trace context propagated via message headers/metadata
    - Enables end-to-end latency tracking across services

Alerting:
    - Consumer lag > threshold → alert (Kafka)
    - DLQ depth > 0 → alert
    - Processing error rate > 5% → alert
    - No messages processed in 5 minutes (when queue not empty) → alert
```

## Topic/Queue Naming Convention

```
Pattern: {domain}.{aggregate}.{event}.{version}

Examples:
    orders.order.created.v1
    payments.payment.completed.v1
    users.user.registered.v1
    inventory.stock.reserved.v1

Queue naming (for consumer-specific queues):
    {consumer-service}.{topic}
    email-service.orders.order.created.v1
    analytics-service.orders.order.created.v1
```

## Critical Rules

- Every message MUST have a unique `id` and `idempotency_key` — consumers MUST deduplicate
- Every message MUST include `tenant_id` — consumers MUST respect tenant isolation
- Every message MUST include `correlation_id` — enables distributed tracing across services
- Use partition keys (Kafka) or routing keys (RabbitMQ) for ordering guarantees per tenant
- Consumers MUST be idempotent — processing the same message twice produces the same result
- Failed messages MUST go to a DLQ after max retries — never drop messages silently
- Schema changes MUST be backward compatible — or use versioned topics
- Transactional outbox pattern for consistency between DB writes and event publishing
- Compensating events MUST exist for every saga step — enable rollback
- Message payload MUST be self-contained — do not require lookups to process
- Monitor consumer lag and DLQ depth — alert on-call when thresholds are breached
- Message size SHOULD stay under 1MB — use blob storage (S3) for larger payloads
- Consumers MUST ignore unknown fields — forward compatibility
