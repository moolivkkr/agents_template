---
skill: websocket-pattern-go
description: Go WebSocket archetype — gorilla/websocket or nhooyr/websocket, goroutine per connection, hub pattern, graceful shutdown
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

> **Canonical reference**: This is the Go counterpart to `websocket-pattern.md` (language-neutral). Read that first for concepts and contracts.

Go WebSocket servers use `nhooyr.io/websocket` (modern, maintained) or `github.com/gorilla/websocket` (widely used). Each connection gets a read and write goroutine coordinated via channels.

## Connection and Hub Types

```go
package ws

import (
    "context"
    "encoding/json"
    "log/slog"
    "net/http"
    "sync"
    "time"

    "nhooyr.io/websocket"
    "nhooyr.io/websocket/wsjson"
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
}

type roomMessage struct {
    Room    string
    Message Message
    Except  string // exclude this connID (optional)
}

func NewHub(logger *slog.Logger) *Hub {
    return &Hub{
        connections: make(map[string]*Connection),
        rooms:       make(map[string]map[string]bool),
        users:       make(map[string]map[string]bool),
        register:    make(chan *Connection, 64),
        unregister:  make(chan *Connection, 64),
        broadcast:   make(chan roomMessage, 256),
        logger:      logger.With("component", "ws-hub"),
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
    // 1. Authenticate
    token := r.URL.Query().Get("token")
    if token == "" {
        http.Error(w, "missing token", http.StatusUnauthorized)
        return
    }

    claims, err := validateJWT(token)
    if err != nil {
        h.logger.Warn("ws.auth_failed", "error", err)
        http.Error(w, "invalid token", http.StatusUnauthorized)
        return
    }

    // 2. Upgrade connection
    wsConn, err := websocket.Accept(w, r, &websocket.AcceptOptions{
        OriginPatterns: []string{"*"}, // Configure for your domain
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

    // 4. Register and start goroutines
    h.register <- conn

    go h.writePump(r.Context(), conn)
    go h.readPump(r.Context(), conn)
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

        // Authorization check
        if !h.canJoinRoom(conn, payload.Room) {
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

func (h *Hub) canJoinRoom(conn *Connection, room string) bool {
    // Implement room-level authorization.
    // Example: room "tenant:{id}" requires matching tenant_id
    // Example: room "project:{id}" requires project membership check
    return true // Replace with actual authorization logic
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

// Start hub before server:
func main() {
    hub := ws.NewHub(logger)
    go hub.Run(ctx)

    r := chi.NewRouter()
    ws.RegisterWebSocketRoutes(r, hub)
}
```

## Critical Rules

- One goroutine per read pump, one per write pump — never read/write from the same goroutine
- Channel sends to `conn.send` MUST be non-blocking with `select/default` — prevent deadlocks
- Set `ReadLimit` on the WebSocket connection — prevent memory exhaustion
- Use `context.WithTimeout` for write operations — prevent blocking on slow clients
- Hub operations go through channels (`register`, `unregister`, `broadcast`) — not direct map access
- Room authorization MUST be checked on subscribe — do not trust the client
- Close the `send` channel to signal the write pump to exit — do not close the WebSocket from the hub
- Always `defer unregister` in the read pump — ensures cleanup on any exit path
