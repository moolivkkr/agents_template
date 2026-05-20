---
skill: websocket-pattern
description: Language-neutral WebSocket archetype — connection lifecycle, rooms/channels, broadcasting, reconnection, auth, rate limiting, graceful degradation
version: "1.0"
tags:
  - websocket
  - real-time
  - rooms
  - broadcasting
  - archetype
  - backend
---

# WebSocket Pattern

Complete production-ready WebSocket pattern for real-time communication. Every generated WebSocket handler MUST follow this pattern.

> **Language-specific variants**: See `websocket-pattern-go.md`, `websocket-pattern-python.md`, `websocket-pattern-java.md`, `websocket-pattern-rust.md`, `websocket-pattern-typescript.md` for idiomatic implementations.

## Core Concepts

WebSockets provide full-duplex communication between client and server over a single TCP connection. Use them for real-time features where low latency matters.

```
Client                          Server
  |                                |
  |--- HTTP Upgrade Request ------>|
  |    (with JWT in query/header)  |
  |<-- 101 Switching Protocols ----|
  |                                |
  |--- Subscribe {room: "abc"} --->|
  |<-- Subscribed {room: "abc"} ---|
  |                                |
  |<-- Message {from: "user2"} ----|
  |<-- Message {from: "user3"} ----|
  |                                |
  |--- Ping ---------------------->|
  |<-- Pong -----------------------|
  |                                |
  |--- Close --------------------->|
  |<-- Close ----------------------|
```

## Connection Lifecycle

```
1. UPGRADE       — Client sends HTTP upgrade request with auth token
2. AUTHENTICATE  — Server validates JWT, extracts tenant/user, rejects if invalid
3. REGISTER      — Server registers connection in connection manager
4. HEARTBEAT     — Periodic ping/pong to detect dead connections
5. SUBSCRIBE     — Client joins rooms/channels for targeted messages
6. MESSAGE       — Bidirectional message exchange
7. DISCONNECT    — Clean close or timeout; server unregisters and cleans up
```

### Connection Manager

```
ConnectionManager:
    connections: map[connectionID] -> Connection
    rooms:       map[roomID] -> set[connectionID]
    users:       map[userID] -> set[connectionID]  // user may have multiple tabs

    register(conn):
        connections[conn.id] = conn
        users[conn.userID].add(conn.id)

    unregister(conn):
        connections.delete(conn.id)
        users[conn.userID].remove(conn.id)
        for room in conn.rooms:
            rooms[room].remove(conn.id)

    subscribe(conn, roomID):
        rooms[roomID].add(conn.id)
        conn.rooms.add(roomID)

    unsubscribe(conn, roomID):
        rooms[roomID].remove(conn.id)
        conn.rooms.remove(roomID)
```

## Message Protocol

All messages use a consistent JSON envelope:

```json
// Client -> Server
{
    "type": "subscribe",
    "payload": { "room": "project-123" },
    "id": "msg-uuid"
}

// Server -> Client
{
    "type": "message",
    "payload": { "text": "Hello", "from": "user-456" },
    "room": "project-123",
    "timestamp": "2024-01-15T09:30:00Z"
}

// Server -> Client (acknowledgement)
{
    "type": "ack",
    "ref": "msg-uuid"
}

// Server -> Client (error)
{
    "type": "error",
    "code": "RATE_LIMITED",
    "message": "Too many messages, slow down",
    "ref": "msg-uuid"
}
```

### Message Types

| Type | Direction | Purpose |
|------|-----------|---------|
| `subscribe` | C -> S | Join a room |
| `unsubscribe` | C -> S | Leave a room |
| `message` | C -> S | Send message to room |
| `ack` | S -> C | Acknowledge client message |
| `error` | S -> C | Report error to client |
| `message` | S -> C | Broadcast message to client |
| `ping` | C -> S | Heartbeat (or use protocol-level ping) |
| `pong` | S -> C | Heartbeat response |

## Broadcasting Patterns

```
// Send to a specific room (most common)
broadcast_to_room(room_id, message):
    for conn_id in rooms[room_id]:
        connections[conn_id].send(message)

// Send to a specific user (all their connections/tabs)
send_to_user(user_id, message):
    for conn_id in users[user_id]:
        connections[conn_id].send(message)

// Send to all connected clients (rare — use sparingly)
broadcast_all(message):
    for conn_id, conn in connections:
        conn.send(message)

// Send to room except sender
broadcast_to_room_except(room_id, sender_id, message):
    for conn_id in rooms[room_id]:
        if conn_id != sender_id:
            connections[conn_id].send(message)
```

## Authentication on Upgrade

```
// Option 1: Token in query parameter (simpler, but token in access logs)
ws://example.com/ws?token=eyJhbG...

// Option 2: Token in first message after connect (more secure)
// Client connects, then immediately sends: { "type": "auth", "token": "eyJhbG..." }

// Option 3: Cookie-based (for same-origin only)
// Browser sends cookies automatically on upgrade

Recommended: Option 1 for simplicity with short-lived tokens,
             or Option 2 for maximum security.

Authentication flow:
    1. Extract token from query param or first message
    2. Validate JWT (check signature, expiry, audience)
    3. Extract user_id, tenant_id, roles
    4. If invalid: close connection with 4001 code and reason
    5. If valid: register connection with user context
```

### WebSocket Close Codes

| Code | Meaning | When to Use |
|------|---------|-------------|
| 1000 | Normal Closure | Clean disconnect |
| 1001 | Going Away | Server shutting down |
| 1008 | Policy Violation | Auth failed |
| 1009 | Message Too Big | Payload exceeds limit |
| 1011 | Internal Error | Server error |
| 4001 | Unauthorized | Invalid/expired token |
| 4003 | Forbidden | No permission for room |
| 4029 | Rate Limited | Too many messages |

## Heartbeat / Ping-Pong

```
Server-side heartbeat:
    ping_interval = 30s
    pong_timeout  = 10s

    every ping_interval:
        send ping frame
        start pong_timeout timer

        if pong not received within pong_timeout:
            close connection (dead client)
            unregister

Client-side heartbeat:
    // Respond to server pings automatically (browser WebSocket API does this)
    // Or implement application-level ping/pong for frameworks that need it
```

## Reconnection Handling (Client-Side)

```javascript
// Client reconnection with exponential backoff
class ReconnectingWebSocket {
    maxRetries = 10
    baseDelay  = 1000   // 1 second
    maxDelay   = 30000  // 30 seconds
    attempt    = 0

    connect():
        try:
            ws = new WebSocket(url)
            ws.onopen = () => {
                attempt = 0  // reset on success
                reconcileState()  // fetch missed messages
            }
            ws.onclose = (event) => {
                if event.code != 1000:  // not a clean close
                    scheduleReconnect()
            }
        catch:
            scheduleReconnect()

    scheduleReconnect():
        if attempt >= maxRetries:
            fallbackToPolling()
            return

        delay = min(baseDelay * 2^attempt, maxDelay)
        delay = delay + random(0, delay * 0.1)  // jitter
        attempt++
        setTimeout(connect, delay)
```

## State Reconciliation on Reconnect

```
When a client reconnects, it may have missed messages during the disconnection period.

Strategy 1: Last-Event-ID
    - Client sends last received message ID/timestamp on reconnect
    - Server replays messages since that point
    - Works for ordered, persisted message streams

Strategy 2: Full State Sync
    - On reconnect, client requests current state snapshot
    - Server sends full current state
    - Works for dashboard/status-style data

Strategy 3: Delta Sync
    - Client sends its version number
    - Server computes and sends only the diff
    - Works for document collaboration

Recommended: Strategy 1 for most real-time features.
```

## Rate Limiting

```
Per-connection rate limiting:
    max_messages_per_second = 10
    max_messages_per_minute = 100
    max_message_size_bytes  = 65536  // 64KB

    on_message(conn, message):
        if message.size > max_message_size_bytes:
            send_error(conn, "MESSAGE_TOO_LARGE")
            return

        if not rate_limiter.allow(conn.id):
            send_error(conn, "RATE_LIMITED", "Too many messages")
            return

        // Process message normally

    // Use token bucket or sliding window algorithm
    // Track per-connection, not per-IP (one user may have multiple connections)
```

## Graceful Degradation

```
When WebSocket is unavailable (corporate proxies, load balancers):

1. Attempt WebSocket connection
2. If fails or disconnects too quickly:
    - Fall back to Server-Sent Events (SSE) for server→client
    - Use regular HTTP POST for client→server
3. If SSE also unavailable:
    - Fall back to long polling

Client detection:
    if ("WebSocket" in window):
        try WebSocket
    else:
        try SSE
    fallback to polling
```

## Multi-Instance Scaling

```
Problem: In a multi-instance deployment, connections are distributed across instances.
Broadcasting to a room requires cross-instance communication.

Solution: Use a pub/sub backbone (Redis Pub/Sub, NATS, Kafka).

    Instance A              Redis Pub/Sub           Instance B
    [conn 1, 2]  ----publish---->  <----subscribe---- [conn 3, 4]
                                   ---->  deliver to conn 3, 4

    On message to room "abc":
        1. Publish to Redis channel "room:abc"
        2. All instances subscribed to "room:abc" receive it
        3. Each instance delivers to its local connections in that room
```

## Observability

```
Metrics:
    websocket_connections_active{tenant_id}       # gauge
    websocket_connections_total{status=open|close} # counter
    websocket_messages_sent_total{type}           # counter
    websocket_messages_received_total{type}       # counter
    websocket_message_size_bytes{direction}       # histogram
    websocket_rooms_active                        # gauge

Logging:
    - Log connection open/close with user_id, tenant_id, duration
    - Log room subscribe/unsubscribe
    - Log errors (auth failures, rate limits, protocol violations)
    - Do NOT log message content (privacy)

Tracing:
    - Create a span for each significant operation (connect, subscribe, broadcast)
    - Propagate correlation_id from HTTP headers through WebSocket messages
```

## Example: Real-Time Notifications

```
// When an API action creates a notification:
notification_service.create(notification)

// Publish to the WebSocket layer:
ws_broadcaster.send_to_user(notification.user_id, {
    type: "notification",
    payload: {
        id: notification.id,
        title: notification.title,
        body: notification.body,
        action_url: notification.action_url,
        created_at: notification.created_at,
    }
})
```

## Example: Live Dashboard Updates

```
// Dashboard room per tenant
room_id = "dashboard:{tenant_id}"

// When metrics update (e.g., from a cron job or event):
ws_broadcaster.broadcast_to_room(room_id, {
    type: "dashboard.update",
    payload: {
        metric: "active_users",
        value: 1234,
        timestamp: now(),
    }
})
```

## Critical Rules

- ALWAYS authenticate on upgrade — never allow anonymous WebSocket connections
- ALWAYS enforce message size limits — prevent memory exhaustion from large payloads
- ALWAYS implement heartbeat ping/pong — detect and clean up dead connections
- ALWAYS implement rate limiting per connection — prevent abuse
- ALWAYS clean up on disconnect — remove from connection manager, rooms, user map
- Room authorization MUST be checked on subscribe — don't rely on client honesty
- Use protocol-level ping/pong frames when available (not application messages)
- Close connections with appropriate codes (4001 for auth, 4029 for rate limit)
- Never log message content — only metadata (type, room, size)
- Multi-instance deployments MUST use a pub/sub backbone for cross-instance broadcasting
- Client reconnection MUST use exponential backoff with jitter
- Provide a state reconciliation mechanism for clients that reconnect after a gap
