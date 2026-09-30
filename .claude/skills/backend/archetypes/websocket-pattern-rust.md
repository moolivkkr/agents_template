---
skill: websocket-pattern-rust
description: Rust WebSocket archetype — axum WebSocket, tokio-tungstenite, connection manager, rooms, broadcasting, graceful shutdown
version: "1.0"
tags:
  - rust
  - websocket
  - axum
  - tokio-tungstenite
  - real-time
  - archetype
  - backend
---

# WebSocket Pattern — Rust

> Rust samples compile-checked 2026-09-30 (tests/archetype-compile/rust/run.sh): rustc 1.98.1, axum 0.8.9 (ws), tokio 1.53.1, reqwest 0.13.5; the tests below (cross-tenant room refusals, the 401 envelope over a live server) ran and pass.

> **Canonical reference**: This is the Rust counterpart to `websocket-pattern.md` (language-neutral). Read that first for concepts and contracts.

Rust WebSocket servers use `axum`'s built-in WebSocket support (backed by `tokio-tungstenite`) for the upgrade handler, plus `tokio::sync::broadcast` or `mpsc` channels for message distribution.

## Types

```rust
// src/ws/types.rs

use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct WsMessage {
    #[serde(rename = "type")]
    pub msg_type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub payload: Option<serde_json::Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub room: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    #[serde(rename = "ref")]
    pub reference: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub timestamp: Option<String>,
    /// Error frames only (`"type": "error"`): a stable UPPER_SNAKE code and a user-safe message
    /// (websocket-pattern.md)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub code: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub message: Option<String>,
}

#[derive(Debug, Clone)]
pub struct ConnectedUser {
    pub conn_id: String,
    pub user_id: Uuid,
    pub tenant_id: Uuid,
    pub roles: Vec<String>,
}
```

## Connection Manager

```rust
// src/ws/manager.rs

use std::collections::{HashMap, HashSet};
use std::sync::Arc;

use tokio::sync::{mpsc, RwLock};
use tracing::{info, warn};

use super::types::{ConnectedUser, WsMessage};

/// Sender half given to each connection's write task.
type ConnSender = mpsc::UnboundedSender<WsMessage>;

pub struct ConnectionManager {
    connections: RwLock<HashMap<String, (ConnectedUser, ConnSender)>>,
    rooms: RwLock<HashMap<String, HashSet<String>>>,       // room -> conn_ids
    users: RwLock<HashMap<String, HashSet<String>>>,       // user_id -> conn_ids
}

impl ConnectionManager {
    pub fn new() -> Arc<Self> {
        Arc::new(Self {
            connections: RwLock::new(HashMap::new()),
            rooms: RwLock::new(HashMap::new()),
            users: RwLock::new(HashMap::new()),
        })
    }

    pub async fn register(&self, user: ConnectedUser, tx: ConnSender) {
        let conn_id = user.conn_id.clone();
        let user_id = user.user_id.to_string();

        self.connections
            .write()
            .await
            .insert(conn_id.clone(), (user.clone(), tx));

        self.users
            .write()
            .await
            .entry(user_id)
            .or_default()
            .insert(conn_id.clone());

        info!(conn_id = %conn_id, user_id = %user.user_id, "ws.connected");
    }

    pub async fn unregister(&self, conn_id: &str) {
        let user = {
            let mut conns = self.connections.write().await;
            conns.remove(conn_id).map(|(u, _)| u)
        };

        if let Some(user) = user {
            // Remove from user map
            let user_id = user.user_id.to_string();
            let mut users = self.users.write().await;
            if let Some(set) = users.get_mut(&user_id) {
                set.remove(conn_id);
                if set.is_empty() {
                    users.remove(&user_id);
                }
            }

            // Remove from all rooms
            let mut rooms = self.rooms.write().await;
            let room_keys: Vec<String> = rooms.keys().cloned().collect();
            for room in room_keys {
                if let Some(set) = rooms.get_mut(&room) {
                    set.remove(conn_id);
                    if set.is_empty() {
                        rooms.remove(&room);
                    }
                }
            }

            info!(conn_id = %conn_id, user_id = %user.user_id, "ws.disconnected");
        }
    }

    pub async fn subscribe(&self, conn_id: &str, room: &str) {
        self.rooms
            .write()
            .await
            .entry(room.to_string())
            .or_default()
            .insert(conn_id.to_string());

        info!(conn_id = %conn_id, room = %room, "ws.subscribed");
    }

    pub async fn unsubscribe(&self, conn_id: &str, room: &str) {
        let mut rooms = self.rooms.write().await;
        if let Some(set) = rooms.get_mut(room) {
            set.remove(conn_id);
            if set.is_empty() {
                rooms.remove(room);
            }
        }
        info!(conn_id = %conn_id, room = %room, "ws.unsubscribed");
    }

    pub async fn broadcast_to_room(&self, room: &str, msg: WsMessage, except: Option<&str>) {
        let room_conns = {
            let rooms = self.rooms.read().await;
            rooms.get(room).cloned().unwrap_or_default()
        };

        let conns = self.connections.read().await;
        for conn_id in &room_conns {
            if except.map_or(false, |e| e == conn_id) {
                continue;
            }
            if let Some((_, tx)) = conns.get(conn_id.as_str()) {
                if tx.send(msg.clone()).is_err() {
                    warn!(conn_id = %conn_id, "ws.send_failed");
                }
            }
        }
    }

    pub async fn send_to_conn(&self, conn_id: &str, msg: WsMessage) {
        if let Some((_, tx)) = self.connections.read().await.get(conn_id) {
            let _ = tx.send(msg);
        }
    }

    pub async fn send_to_user(&self, user_id: &str, msg: WsMessage) {
        let user_conns = {
            let users = self.users.read().await;
            users.get(user_id).cloned().unwrap_or_default()
        };

        let conns = self.connections.read().await;
        for conn_id in &user_conns {
            if let Some((_, tx)) = conns.get(conn_id.as_str()) {
                let _ = tx.send(msg.clone());
            }
        }
    }

    pub async fn active_connections(&self) -> usize {
        self.connections.read().await.len()
    }
}
```

## Axum WebSocket Handler

```rust
// src/ws/handler.rs

use std::sync::Arc;

use axum::{
    extract::{
        ws::{Message, WebSocket, WebSocketUpgrade},
        Query, State,
    },
    response::IntoResponse,
};
use futures_util::{SinkExt, StreamExt};
use serde::Deserialize;
use tokio::sync::mpsc;
use tracing::{error, info, warn};
use uuid::Uuid;

use super::manager::ConnectionManager;
use super::types::{ConnectedUser, WsMessage};
use crate::auth::redeem_ws_ticket;
use crate::error::AppError; // error-handling-rust.md

const MAX_MESSAGE_SIZE: usize = 65536; // 64KB

/// `?ticket=` is a single-use, ~30s ticket from `POST /api/v1/ws-tickets` (websocket-pattern.md,
/// Option 1). Never a bearer token: query strings end up in proxy and access logs.
#[derive(Deserialize)]
pub struct WsQuery {
    ticket: String,
}

pub async fn ws_upgrade(
    ws: WebSocketUpgrade,
    Query(query): Query<WsQuery>,
    State(manager): State<Arc<ConnectionManager>>,
) -> impl IntoResponse {
    // Authenticate before upgrade: atomically redeem (GET+DELETE) the ticket
    let claims = match redeem_ws_ticket(&query.ticket).await {
        Ok(c) => c,
        Err(e) => {
            warn!(error = %e, "ws.auth_failed");
            // Still HTTP (the upgrade hasn't happened): the one error envelope, WWW-Authenticate: Bearer
            return AppError::Unauthenticated.into_response();
        }
    };

    let user = ConnectedUser {
        conn_id: Uuid::new_v4().to_string(),
        user_id: claims.user_id,
        tenant_id: claims.tenant_id,
        roles: claims.roles,
    };

    ws.max_message_size(MAX_MESSAGE_SIZE)
        .on_upgrade(move |socket| handle_socket(socket, user, manager))
}

async fn handle_socket(
    socket: WebSocket,
    user: ConnectedUser,
    manager: Arc<ConnectionManager>,
) {
    let conn_id = user.conn_id.clone();
    let tenant_id = user.tenant_id; // from the redeemed ticket: authorizes every room this socket uses
    let (mut ws_tx, mut ws_rx) = socket.split();

    // Channel for sending messages to this connection
    let (tx, mut rx) = mpsc::unbounded_channel::<WsMessage>();

    // Register connection
    manager.register(user, tx).await;

    // Write task: forward messages from channel to WebSocket
    let write_task = tokio::spawn(async move {
        while let Some(msg) = rx.recv().await {
            let json = match serde_json::to_string(&msg) {
                Ok(j) => j,
                Err(e) => {
                    error!(error = %e, "ws.serialize_error");
                    continue;
                }
            };
            if ws_tx.send(Message::Text(json.into())).await.is_err() {
                break;
            }
        }
    });

    // Read task: process incoming messages
    let mgr = manager.clone();
    let cid = conn_id.clone();
    let read_task = tokio::spawn(async move {
        while let Some(Ok(msg)) = ws_rx.next().await {
            match msg {
                Message::Text(text) => {
                    let text_ref: &str = &text;
                    match serde_json::from_str::<WsMessage>(text_ref) {
                        Ok(ws_msg) => {
                            handle_message(&cid, tenant_id, ws_msg, &mgr).await;
                        }
                        Err(e) => {
                            warn!(conn_id = %cid, error = %e, "ws.invalid_message");
                        }
                    }
                }
                Message::Close(_) => break,
                _ => {} // Ignore binary, ping, pong (handled by axum)
            }
        }
    });

    // Wait for either task to finish
    tokio::select! {
        _ = write_task => {},
        _ = read_task => {},
    }

    // Cleanup
    manager.unregister(&conn_id).await;
}

/// Rooms belong to a tenant and are named `<topic>:<tenant_id>` (websocket-pattern.md's
/// `dashboard:{tenant_id}`). A connection may join or post only to its own tenant's rooms; the tenant
/// is the one from the redeemed ticket, never one the message names.
fn room_in_tenant(room: &str, tenant_id: Uuid) -> bool {
    room.rsplit_once(':')
        .and_then(|(_, tenant)| Uuid::parse_str(tenant).ok())
        .is_some_and(|tenant| tenant == tenant_id)
}

async fn handle_message(conn_id: &str, tenant_id: Uuid, msg: WsMessage, manager: &Arc<ConnectionManager>) {
    match msg.msg_type.as_str() {
        "subscribe" => {
            if let Some(payload) = &msg.payload {
                if let Some(room) = payload.get("room").and_then(|r| r.as_str()) {
                    if !room_in_tenant(room, tenant_id) {
                        warn!(conn_id = %conn_id, room = %room, "ws.room_forbidden");
                        send_error(conn_id, "FORBIDDEN", "You can't join this room.", msg.reference.as_deref(), manager).await;
                        return;
                    }
                    manager.subscribe(conn_id, room).await;
                    send_ack(conn_id, msg.reference.as_deref(), manager).await;
                }
            }
        }
        "unsubscribe" => {
            if let Some(payload) = &msg.payload {
                if let Some(room) = payload.get("room").and_then(|r| r.as_str()) {
                    manager.unsubscribe(conn_id, room).await;
                    send_ack(conn_id, msg.reference.as_deref(), manager).await;
                }
            }
        }
        "message" => {
            if let Some(payload) = &msg.payload {
                if let Some(room) = payload.get("room").and_then(|r| r.as_str()) {
                    if !room_in_tenant(room, tenant_id) {
                        warn!(conn_id = %conn_id, room = %room, "ws.room_forbidden");
                        send_error(conn_id, "FORBIDDEN", "You can't post to this room.", msg.reference.as_deref(), manager).await;
                        return;
                    }
                    let broadcast = WsMessage {
                        msg_type: "message".to_string(),
                        payload: payload.get("data").cloned(),
                        room: Some(room.to_string()),
                        timestamp: Some(chrono::Utc::now().to_rfc3339()),
                        ..Default::default()
                    };
                    manager
                        .broadcast_to_room(room, broadcast, Some(conn_id))
                        .await;
                    send_ack(conn_id, msg.reference.as_deref(), manager).await;
                }
            }
        }
        _ => {
            warn!(conn_id = %conn_id, msg_type = %msg.msg_type, "ws.unknown_type");
        }
    }
}

async fn send_ack(conn_id: &str, reference: Option<&str>, manager: &Arc<ConnectionManager>) {
    if let Some(r) = reference {
        let ack = WsMessage {
            msg_type: "ack".to_string(),
            reference: Some(r.to_string()),
            ..Default::default()
        };
        // Send via manager (it owns the connection map and the senders)
        manager.send_to_conn(conn_id, ack).await;
    }
}

/// `{"type": "error", "code", "message", "ref"}` (websocket-pattern.md): code is stable UPPER_SNAKE,
/// message is user-safe.
async fn send_error(conn_id: &str, code: &str, message: &str, reference: Option<&str>, manager: &Arc<ConnectionManager>) {
    let frame = WsMessage {
        msg_type: "error".to_string(),
        code: Some(code.to_string()),
        message: Some(message.to_string()),
        reference: reference.map(str::to_string),
        ..Default::default()
    };
    manager.send_to_conn(conn_id, frame).await;
}
```

## Router Setup

```rust
// src/main.rs

use axum::{middleware, routing::get, Router};

use crate::error::request_id_middleware; // error-handling-rust.md

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();

    let manager = ConnectionManager::new();

    let app = Router::new()
        .route("/ws", get(ws_upgrade))
        // outermost: X-Request-Id on every response, and the same id in the 401 envelope
        .layer(middleware::from_fn(request_id_middleware))
        .with_state(manager);

    let listener = tokio::net::TcpListener::bind("0.0.0.0:3000").await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
```

## Tests

```rust
// src/ws/handler.rs (bottom of the file)

#[cfg(test)]
mod tests {
    use super::*;

    async fn connect(manager: &Arc<ConnectionManager>, tenant_id: Uuid) -> (String, mpsc::UnboundedReceiver<WsMessage>) {
        let (tx, rx) = mpsc::unbounded_channel();
        let user = ConnectedUser { conn_id: Uuid::new_v4().to_string(), user_id: Uuid::new_v4(), tenant_id, roles: vec![] };
        let conn_id = user.conn_id.clone();
        manager.register(user, tx).await;
        (conn_id, rx)
    }

    fn frame(msg_type: &str, payload: serde_json::Value) -> WsMessage {
        WsMessage { msg_type: msg_type.into(), payload: Some(payload), reference: Some("r1".into()), ..Default::default() }
    }

    #[tokio::test]
    async fn subscribing_to_another_tenants_room_is_refused() {
        let manager = ConnectionManager::new();
        let (tenant_a, tenant_b) = (Uuid::new_v4(), Uuid::new_v4());
        let (conn_a, mut rx_a) = connect(&manager, tenant_a).await;

        // Tenant A asks for tenant B's room: an error frame, and no membership
        let room_b = format!("dashboard:{tenant_b}");
        handle_message(&conn_a, tenant_a, frame("subscribe", serde_json::json!({ "room": room_b })), &manager).await;
        let refused = rx_a.try_recv().expect("an error frame");
        assert_eq!(refused.msg_type, "error");
        assert_eq!(refused.code.as_deref(), Some("FORBIDDEN"));
        assert_eq!(refused.reference.as_deref(), Some("r1"));

        manager.broadcast_to_room(&room_b, WsMessage { msg_type: "message".into(), ..Default::default() }, None).await;
        assert!(rx_a.try_recv().is_err(), "tenant A must not receive tenant B's room traffic");

        // Its own tenant's room is allowed
        let room_a = format!("dashboard:{tenant_a}");
        handle_message(&conn_a, tenant_a, frame("subscribe", serde_json::json!({ "room": room_a })), &manager).await;
        assert_eq!(rx_a.try_recv().expect("an ack").msg_type, "ack");
    }

    #[tokio::test]
    async fn posting_to_another_tenants_room_is_refused() {
        let manager = ConnectionManager::new();
        let (tenant_a, tenant_b) = (Uuid::new_v4(), Uuid::new_v4());
        let room_b = format!("dashboard:{tenant_b}");
        let (conn_b, mut rx_b) = connect(&manager, tenant_b).await;
        handle_message(&conn_b, tenant_b, frame("subscribe", serde_json::json!({ "room": room_b })), &manager).await;
        assert_eq!(rx_b.try_recv().expect("an ack").msg_type, "ack");

        let (conn_a, mut rx_a) = connect(&manager, tenant_a).await;
        let post = frame("message", serde_json::json!({ "room": room_b, "data": { "text": "hi" } }));
        handle_message(&conn_a, tenant_a, post, &manager).await;

        assert_eq!(rx_a.try_recv().expect("an error frame").code.as_deref(), Some("FORBIDDEN"));
        assert!(rx_b.try_recv().is_err(), "tenant B's room must not receive tenant A's post");
    }

    #[tokio::test]
    async fn an_invalid_ticket_is_a_401_error_envelope() {
        // A real server: the upgrade request is answered before any upgrade happens
        let app = axum::Router::new()
            .route("/ws", axum::routing::get(ws_upgrade))
            .layer(axum::middleware::from_fn(crate::error::request_id_middleware))
            .with_state(ConnectionManager::new());
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let addr = listener.local_addr().unwrap();
        tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });

        let resp = reqwest::Client::new()
            .get(format!("http://{addr}/ws?ticket=not-a-ticket"))
            .header("connection", "upgrade")
            .header("upgrade", "websocket")
            .header("sec-websocket-version", "13")
            .header("sec-websocket-key", "dGhlIHNhbXBsZSBub25jZQ==")
            .send()
            .await
            .unwrap();

        assert_eq!(resp.status(), 401);
        assert_eq!(resp.headers()["www-authenticate"], "Bearer");
        let header_id = resp.headers()["x-request-id"].to_str().unwrap().to_owned();
        let body: serde_json::Value = resp.json().await.unwrap();
        assert!(body.get("data").is_none());
        assert_eq!(body["error"]["code"], "UNAUTHENTICATED");
        assert_eq!(body["error"]["request_id"], header_id.as_str());
    }
}
```

## Critical Rules

- Use `WebSocket::split()` to get separate sink and stream — one task for reading, one for writing
- Use `mpsc::unbounded_channel` per connection for the write path — the write task receives from the channel
- Use `RwLock` (from `tokio::sync`) for the connection manager — allows concurrent reads during broadcasts
- Authenticate BEFORE calling `ws.on_upgrade()` — a failed ticket is a 401 in the error envelope (`AppError::Unauthenticated`), before the upgrade happens
- Set `max_message_size()` on the upgrade — prevents memory exhaustion
- Use `tokio::select!` to wait for either read or write task to finish — then clean up both
- Always call `manager.unregister()` after the connection tasks finish — prevents leaks
- `WsMessage` must be `Clone` — it gets sent to multiple connections during broadcast
- Room authorization is checked in `handle_message` before subscribing AND before posting: a room belongs to the tenant in its name (`<topic>:<tenant_id>`), which must be the connection's tenant from the ticket; anything else gets an error frame with code `FORBIDDEN`
- For multi-instance: use Redis pub/sub via the `redis` crate to bridge instances
