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

> **Canonical reference**: This is the Rust counterpart to `websocket-pattern.md` (language-neutral). Read that first for concepts and contracts.

Rust WebSocket servers use `axum`'s built-in WebSocket support (backed by `tokio-tungstenite`) for the upgrade handler, plus `tokio::sync::broadcast` or `mpsc` channels for message distribution.

## Types

```rust
// src/ws/types.rs

use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
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
use crate::auth::validate_jwt;

const MAX_MESSAGE_SIZE: usize = 65536; // 64KB

#[derive(Deserialize)]
pub struct WsQuery {
    token: String,
}

pub async fn ws_upgrade(
    ws: WebSocketUpgrade,
    Query(query): Query<WsQuery>,
    State(manager): State<Arc<ConnectionManager>>,
) -> impl IntoResponse {
    // Authenticate before upgrade
    let claims = match validate_jwt(&query.token) {
        Ok(c) => c,
        Err(e) => {
            warn!(error = %e, "ws.auth_failed");
            return axum::http::StatusCode::UNAUTHORIZED.into_response();
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
                            handle_message(&cid, ws_msg, &mgr).await;
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

async fn handle_message(conn_id: &str, msg: WsMessage, manager: &Arc<ConnectionManager>) {
    match msg.msg_type.as_str() {
        "subscribe" => {
            if let Some(payload) = &msg.payload {
                if let Some(room) = payload.get("room").and_then(|r| r.as_str()) {
                    // TODO: authorization check
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
                    let broadcast = WsMessage {
                        msg_type: "message".to_string(),
                        payload: payload.get("data").cloned(),
                        room: Some(room.to_string()),
                        reference: None,
                        timestamp: Some(chrono::Utc::now().to_rfc3339()),
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
            payload: None,
            room: None,
            reference: Some(r.to_string()),
            timestamp: None,
        };
        // Send via manager (it has the sender)
        let conns = manager.connections.read().await;
        if let Some((_, tx)) = conns.get(conn_id) {
            let _ = tx.send(ack);
        }
    }
}
```

## Router Setup

```rust
// src/main.rs

use axum::{routing::get, Router};
use std::sync::Arc;

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();

    let manager = ConnectionManager::new();

    let app = Router::new()
        .route("/ws", get(ws_upgrade))
        .with_state(manager);

    let listener = tokio::net::TcpListener::bind("0.0.0.0:3000").await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
```

## Critical Rules

- Use `WebSocket::split()` to get separate sink and stream — one task for reading, one for writing
- Use `mpsc::unbounded_channel` per connection for the write path — the write task receives from the channel
- Use `RwLock` (from `tokio::sync`) for the connection manager — allows concurrent reads during broadcasts
- Authenticate BEFORE calling `ws.on_upgrade()` — return 401 before the upgrade happens
- Set `max_message_size()` on the upgrade — prevents memory exhaustion
- Use `tokio::select!` to wait for either read or write task to finish — then clean up both
- Always call `manager.unregister()` after the connection tasks finish — prevents leaks
- `WsMessage` must be `Clone` — it gets sent to multiple connections during broadcast
- Room authorization must be checked in `handle_message` before subscribing
- For multi-instance: use Redis pub/sub via the `redis` crate to bridge instances
