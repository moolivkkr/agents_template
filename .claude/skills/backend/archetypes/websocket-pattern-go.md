---
skill: websocket-pattern-go
description: Go WebSocket archetype — github.com/coder/websocket (formerly nhooyr.io/websocket) or gorilla/websocket, goroutine per connection, hub pattern, graceful shutdown
version: "1.0"
tags:
  - go
  - websocket
  - gorilla
  - real-time
  - archetype
  - backend
---

# WebSocket Pattern — Go

> Go samples compile-checked (go build + go vet) 2026-09-30 with Go 1.27.1, github.com/coder/websocket v1.8.15, chi v5.3.2; the room-authorization test was run, plus a two-client upgrade/subscribe/broadcast round trip with a cross-tenant subscribe refused (tests/archetype-compile/go/run.sh).

> **Canonical reference**: This is the Go counterpart to `websocket-pattern.md` (language-neutral). Read that first for concepts and contracts.

Go WebSocket servers use `github.com/coder/websocket` (maintained; it is the former `nhooyr.io/websocket`, which is deprecated — same API, new import path) or `github.com/gorilla/websocket` (widely used). Each connection gets a read and write goroutine coordinated via channels.

## Connection and Hub Types

```go
package ws

import (
    "context"
    "encoding/json"
    "log/slog"
    "net/http"
    "strings"
    "sync"
    "time"

    "github.com/coder/websocket"
    "github.com/coder/websocket/wsjson"
)

// Message is the wire format for all WebSocket messages.
type Message struct {
    Type      string          `json:"type"`
    Payload   json.RawMessage `json:"payload,omitempty"`
    Room      string          `json:"room,omitempty"`
    Ref       string          `json:"ref,omitempty"`
    Timestamp string          `json:"timestamp,omitempty"`
}

// Connection represents a single WebSocket client.
type Connection struct {
    ID       string
    UserID   string
    TenantID string
    Roles    []string
    conn     *websocket.Conn
    send     chan Message
    rooms    map[string]bool
    mu       sync.RWMutex
}

// Hub manages all active connections, rooms, and broadcasting.
type Hub struct {
    connections map[string]*Connection     // connID -> conn
    rooms       map[string]map[string]bool // roomID -> set of connIDs
    users       map[string]map[string]bool // userID -> set of connIDs

    register   chan *Connection
    unregister chan *Connection
    broadcast  chan roomMessage

    mu     sync.RWMutex
    logger *slog.Logger
    authz  RoomAuthorizer
}

// RoomAuthorizer decides whether a user may join a room of their own tenant — e.g. "is this user
// a member of project 42?" (a DB lookup) or "admin rooms need the admin role". The tenant check
// itself is canJoinRoom's, and never delegated.
type RoomAuthorizer interface {
    CanJoin(ctx context.Context, conn *Connection, kind, id string) (bool, error)
}

type roomMessage struct {
    Room    string
    Message Message
    Except  string // exclude this connID (optional)
}

func NewHub(logger *slog.Logger, authz RoomAuthorizer) *Hub {
    return &Hub{
        connections: make(map[string]*Connection),
        rooms:       make(map[string]map[string]bool),
        users:       make(map[string]map[string]bool),
        register:    make(chan *Connection, 64),
        unregister:  make(chan *Connection, 64),
        broadcast:   make(chan roomMessage, 256),
        logger:      logger.With("component", "ws-hub"),
        authz:       authz,
    }
}
```

## Hub Run Loop

```go
// Run processes register/unregister/broadcast events. Start in a goroutine.
func (h *Hub) Run(ctx context.Context) {
    for {
        select {
        case <-ctx.Done():
            h.closeAll()
            return

        case conn := <-h.register:
            h.mu.Lock()
            h.connections[conn.ID] = conn
            if _, ok := h.users[conn.UserID]; !ok {
                h.users[conn.UserID] = make(map[string]bool)
            }
            h.users[conn.UserID][conn.ID] = true
            h.mu.Unlock()
            h.logger.Info("ws.connected", "conn_id", conn.ID, "user_id", conn.UserID)

        case conn := <-h.unregister:
            h.mu.Lock()
            if _, ok := h.connections[conn.ID]; ok {
                delete(h.connections, conn.ID)
                close(conn.send)

                // Remove from user map
                if userConns, ok := h.users[conn.UserID]; ok {
                    delete(userConns, conn.ID)
                    if len(userConns) == 0 {
                        delete(h.users, conn.UserID)
                    }
                }

                // Remove from all rooms
                conn.mu.RLock()
                for room := range conn.rooms {
                    if roomConns, ok := h.rooms[room]; ok {
                        delete(roomConns, conn.ID)
                        if len(roomConns) == 0 {
                            delete(h.rooms, room)
                        }
                    }
                }
                conn.mu.RUnlock()
            }
            h.mu.Unlock()
            h.logger.Info("ws.disconnected", "conn_id", conn.ID, "user_id", conn.UserID)

        case msg := <-h.broadcast:
            h.mu.RLock()
            if roomConns, ok := h.rooms[msg.Room]; ok {
                for connID := range roomConns {
                    if connID == msg.Except {
                        continue
                    }
                    if conn, ok := h.connections[connID]; ok {
                        select {
                        case conn.send <- msg.Message:
                        default:
                            // Send buffer full — drop message for this connection
                            h.logger.Warn("ws.send_buffer_full", "conn_id", connID)
                        }
                    }
                }
            }
            h.mu.RUnlock()
        }
    }
}

func (h *Hub) closeAll() {
    h.mu.Lock()
    defer h.mu.Unlock()
    for _, conn := range h.connections {
        close(conn.send)
    }
}
```

## HTTP Upgrade Handler with Authentication

```go
const (
    writeWait      = 10 * time.Second
    pongWait       = 60 * time.Second
    pingPeriod     = 54 * time.Second // must be less than pongWait
    maxMessageSize = 65536            // 64KB
    sendBufferSize = 256
)

// HandleUpgrade is the HTTP handler that upgrades to WebSocket.
func (h *Hub) HandleUpgrade(w http.ResponseWriter, r *http.Request) {
    // 1. Authenticate with a single-use ticket (websocket-pattern.md §Authentication on Upgrade).
    // Never a bearer token in the URL: query strings end up in access logs and browser history.
    // The client got the ticket from an authenticated POST /api/v1/ws-tickets; redeeming it is an
    // atomic get-and-delete, so a ticket seen in a log is already useless.
    ticket := r.URL.Query().Get("ticket")
    if ticket == "" {
        http.Error(w, "missing ticket", http.StatusUnauthorized)
        return
    }

    claims, err := redeemTicket(r.Context(), ticket)
    if err != nil {
        h.logger.Warn("ws.auth_failed", "error", err)
        http.Error(w, "invalid ticket", http.StatusUnauthorized)
        return
    }

    // 2. Upgrade connection. Accept checks the Origin header against these host patterns
    // (same-origin is always allowed); never "*", which lets any site open a socket as your user.
    wsConn, err := websocket.Accept(w, r, &websocket.AcceptOptions{
        OriginPatterns: []string{"app.example.com"}, // your front-end origin(s)
    })
    if err != nil {
        h.logger.Error("ws.upgrade_failed", "error", err)
        return
    }
    wsConn.SetReadLimit(maxMessageSize)

    // 3. Create connection object
    conn := &Connection{
        ID:       generateConnID(),
        UserID:   claims.UserID,
        TenantID: claims.TenantID,
        Roles:    claims.Roles,
        conn:     wsConn,
        send:     make(chan Message, sendBufferSize),
        rooms:    make(map[string]bool),
    }

    // 4. Register, then pump until the socket closes. readPump runs on THIS goroutine: net/http
    // cancels r.Context() as soon as the handler returns (hijacked or not), so returning early would
    // cancel both pumps at once.
    h.register <- conn

    go h.writePump(r.Context(), conn)
    h.readPump(r.Context(), conn)
}
```

## Read and Write Pumps

```go
// readPump reads messages from the WebSocket and dispatches them.
func (h *Hub) readPump(ctx context.Context, conn *Connection) {
    defer func() {
        h.unregister <- conn
        conn.conn.Close(websocket.StatusNormalClosure, "")
    }()

    for {
        var msg Message
        err := wsjson.Read(ctx, conn.conn, &msg)
        if err != nil {
            if websocket.CloseStatus(err) == websocket.StatusNormalClosure {
                return
            }
            h.logger.Debug("ws.read_error", "conn_id", conn.ID, "error", err)
            return
        }

        h.handleMessage(ctx, conn, msg)
    }
}

// writePump writes messages from the send channel to the WebSocket.
func (h *Hub) writePump(ctx context.Context, conn *Connection) {
    pingTicker := time.NewTicker(pingPeriod)
    defer pingTicker.Stop()

    for {
        select {
        case msg, ok := <-conn.send:
            if !ok {
                // Hub closed the channel
                conn.conn.Close(websocket.StatusGoingAway, "server shutdown")
                return
            }
            ctx, cancel := context.WithTimeout(ctx, writeWait)
            if err := wsjson.Write(ctx, conn.conn, msg); err != nil {
                cancel()
                h.logger.Debug("ws.write_error", "conn_id", conn.ID, "error", err)
                return
            }
            cancel()

        case <-pingTicker.C:
            ctx, cancel := context.WithTimeout(ctx, writeWait)
            if err := conn.conn.Ping(ctx); err != nil {
                cancel()
                return
            }
            cancel()

        case <-ctx.Done():
            return
        }
    }
}
```

## Message Handling (Subscribe, Unsubscribe, Message)

```go
func (h *Hub) handleMessage(ctx context.Context, conn *Connection, msg Message) {
    switch msg.Type {
    case "subscribe":
        var payload struct {
            Room string `json:"room"`
        }
        if err := json.Unmarshal(msg.Payload, &payload); err != nil {
            h.sendError(conn, msg.Ref, "INVALID_PAYLOAD", "invalid subscribe payload")
            return
        }

        // Authorization check (tenant, then membership) — never trust the room name alone
        if !h.canJoinRoom(ctx, conn, payload.Room) {
            h.sendError(conn, msg.Ref, "FORBIDDEN", "not authorized for this room")
            return
        }

        h.subscribe(conn, payload.Room)
        h.sendAck(conn, msg.Ref)

    case "unsubscribe":
        var payload struct {
            Room string `json:"room"`
        }
        if err := json.Unmarshal(msg.Payload, &payload); err != nil {
            return
        }
        h.unsubscribeConn(conn, payload.Room)
        h.sendAck(conn, msg.Ref)

    case "message":
        var payload struct {
            Room string          `json:"room"`
            Data json.RawMessage `json:"data"`
        }
        if err := json.Unmarshal(msg.Payload, &payload); err != nil {
            h.sendError(conn, msg.Ref, "INVALID_PAYLOAD", "invalid message payload")
            return
        }

        // Check room membership
        conn.mu.RLock()
        inRoom := conn.rooms[payload.Room]
        conn.mu.RUnlock()
        if !inRoom {
            h.sendError(conn, msg.Ref, "NOT_IN_ROOM", "not subscribed to this room")
            return
        }

        // Broadcast to room (except sender)
        h.broadcast <- roomMessage{
            Room: payload.Room,
            Message: Message{
                Type:      "message",
                Payload:   payload.Data,
                Room:      payload.Room,
                Timestamp: time.Now().UTC().Format(time.RFC3339),
            },
            Except: conn.ID,
        }
        h.sendAck(conn, msg.Ref)

    default:
        h.sendError(conn, msg.Ref, "UNKNOWN_TYPE", "unknown message type: "+msg.Type)
    }
}

func (h *Hub) subscribe(conn *Connection, room string) {
    h.mu.Lock()
    if _, ok := h.rooms[room]; !ok {
        h.rooms[room] = make(map[string]bool)
    }
    h.rooms[room][conn.ID] = true
    h.mu.Unlock()

    conn.mu.Lock()
    conn.rooms[room] = true
    conn.mu.Unlock()

    h.logger.Info("ws.subscribed", "conn_id", conn.ID, "room", room)
}

func (h *Hub) unsubscribeConn(conn *Connection, room string) {
    h.mu.Lock()
    if roomConns, ok := h.rooms[room]; ok {
        delete(roomConns, conn.ID)
        if len(roomConns) == 0 {
            delete(h.rooms, room)
        }
    }
    h.mu.Unlock()

    conn.mu.Lock()
    delete(conn.rooms, room)
    conn.mu.Unlock()

    h.logger.Info("ws.unsubscribed", "conn_id", conn.ID, "room", room)
}
```

## Helper Methods

```go
func (h *Hub) sendAck(conn *Connection, ref string) {
    if ref == "" {
        return
    }
    select {
    case conn.send <- Message{Type: "ack", Ref: ref}:
    default:
    }
}

func (h *Hub) sendError(conn *Connection, ref, code, message string) {
    payload, _ := json.Marshal(map[string]string{"code": code, "message": message})
    select {
    case conn.send <- Message{Type: "error", Payload: payload, Ref: ref}:
    default:
    }
}

// canJoinRoom enforces room authorization on subscribe (websocket-pattern.md). Rooms are named
// "<tenant_id>:<kind>:<id>", e.g. "3f9c…:project:42". The tenant part must equal the tenant from the
// connection's verified ticket, so no room name reaches another tenant's room; the RoomAuthorizer
// then decides membership. Malformed names and authorizer errors are refused (fail closed).
func (h *Hub) canJoinRoom(ctx context.Context, conn *Connection, room string) bool {
    tenantID, rest, ok := strings.Cut(room, ":")
    if !ok || tenantID == "" || tenantID != conn.TenantID {
        return false
    }
    kind, id, ok := strings.Cut(rest, ":")
    if !ok || kind == "" || id == "" {
        return false
    }
    allowed, err := h.authz.CanJoin(ctx, conn, kind, id)
    if err != nil {
        h.logger.Warn("ws.room_authz_failed", "conn_id", conn.ID, "room", room, "error", err)
        return false
    }
    return allowed
}

// BroadcastToRoom sends a message to all connections in a room (for use from services).
func (h *Hub) BroadcastToRoom(room string, msg Message) {
    h.broadcast <- roomMessage{Room: room, Message: msg}
}

// SendToUser sends a message to all connections of a specific user.
func (h *Hub) SendToUser(userID string, msg Message) {
    h.mu.RLock()
    defer h.mu.RUnlock()

    if connIDs, ok := h.users[userID]; ok {
        for connID := range connIDs {
            if conn, ok := h.connections[connID]; ok {
                select {
                case conn.send <- msg:
                default:
                }
            }
        }
    }
}
```

## Route Registration

```go
// Mount in your chi/gin/echo router:
func RegisterWebSocketRoutes(r chi.Router, hub *Hub) {
    r.Get("/ws", hub.HandleUpgrade)
}

// Start the hub before the server (in main):
//
//     hub := ws.NewHub(logger, roomAuthz) // roomAuthz: your RoomAuthorizer (membership store)
//     go hub.Run(ctx)
//
//     r := chi.NewRouter()
//     ws.RegisterWebSocketRoutes(r, hub)
```

## Testing Room Authorization

```go
// allowKinds is a test RoomAuthorizer: members may join the listed room kinds.
type allowKinds map[string]bool

func (a allowKinds) CanJoin(_ context.Context, _ *Connection, kind, _ string) (bool, error) {
    return a[kind], nil
}

type failingAuthz struct{}

func (failingAuthz) CanJoin(context.Context, *Connection, string, string) (bool, error) {
    return false, errors.New("membership store unavailable")
}

func TestCanJoinRoom_TenantAndMembership(t *testing.T) {
    ctx := context.Background()
    conn := &Connection{ID: "c1", UserID: "u1", TenantID: "tenant-a"}
    hub := NewHub(slog.New(slog.DiscardHandler), allowKinds{"chat": true})

    for room, want := range map[string]bool{
        "tenant-a:chat:general": true,  // own tenant, a kind the user may join
        "tenant-b:chat:general": false, // another tenant's room: refused before the authorizer is asked
        "tenant-a:project:42":   false, // own tenant, the authorizer says no
        "chat:general":          false, // no tenant part
        "tenant-a":              false, // malformed
        "":                      false,
    } {
        if got := hub.canJoinRoom(ctx, conn, room); got != want {
            t.Errorf("canJoinRoom(%q) = %v, want %v", room, got, want)
        }
    }

    // An authorizer error refuses the join (fail closed).
    down := NewHub(slog.New(slog.DiscardHandler), failingAuthz{})
    if down.canJoinRoom(ctx, conn, "tenant-a:chat:general") {
        t.Error("joined a room while the authorizer was failing")
    }
}
```

## Critical Rules

- One goroutine per read pump, one per write pump — never read/write from the same goroutine
- Channel sends to `conn.send` MUST be non-blocking with `select/default` — prevent deadlocks
- Set `ReadLimit` on the WebSocket connection — prevent memory exhaustion
- Use `context.WithTimeout` for write operations — prevent blocking on slow clients
- Hub operations go through channels (`register`, `unregister`, `broadcast`) — not direct map access
- Room authorization MUST be checked on subscribe — do not trust the client: the room's tenant must be the connection's (from the verified ticket), then a RoomAuthorizer checks membership, failing closed
- Close the `send` channel to signal the write pump to exit — do not close the WebSocket from the hub
- Always `defer unregister` in the read pump — ensures cleanup on any exit path
- Run the read pump on the handler's goroutine: `r.Context()` is cancelled when the handler returns
- Authenticate the upgrade with a single-use ticket (or cookie + Origin allowlist) — never a token in the URL, never `OriginPatterns: ["*"]`
