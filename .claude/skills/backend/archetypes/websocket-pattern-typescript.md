---
skill: websocket-pattern-typescript
description: TypeScript WebSocket archetype — ws library, Socket.IO, connection manager, rooms, broadcasting, auth, reconnection
version: "1.0"
tags:
  - typescript
  - websocket
  - ws
  - socket-io
  - real-time
  - archetype
  - backend
---

# WebSocket Pattern — TypeScript

> **Canonical reference**: This is the TypeScript counterpart to `websocket-pattern.md` (language-neutral). Read that first for concepts and contracts.

TypeScript WebSocket servers use the `ws` library for raw WebSocket or `Socket.IO` for higher-level features (rooms, namespaces, auto-reconnect, fallback transport).

## Types

```typescript
// src/ws/types.ts

export interface WsMessage {
  type: string;
  payload?: unknown;
  room?: string;
  ref?: string;          // client message ID for ack
  timestamp?: string;
}

export interface ConnectedClient {
  id: string;
  userId: string;
  tenantId: string;
  roles: string[];
  rooms: Set<string>;
}
```

## Connection Manager (Raw `ws`)

```typescript
// src/ws/manager.ts

import { WebSocket } from 'ws';
import { Logger } from 'pino';
import type { ConnectedClient, WsMessage } from './types';

export class ConnectionManager {
  private connections = new Map<string, { client: ConnectedClient; ws: WebSocket }>();
  private rooms = new Map<string, Set<string>>();       // roomId -> Set<connId>
  private users = new Map<string, Set<string>>();       // userId -> Set<connId>

  constructor(private logger: Logger) {}

  register(client: ConnectedClient, ws: WebSocket): void {
    this.connections.set(client.id, { client, ws });

    if (!this.users.has(client.userId)) {
      this.users.set(client.userId, new Set());
    }
    this.users.get(client.userId)!.add(client.id);

    this.logger.info({ connId: client.id, userId: client.userId }, 'ws.connected');
  }

  unregister(connId: string): void {
    const entry = this.connections.get(connId);
    if (!entry) return;

    const { client } = entry;

    // Remove from user map
    const userConns = this.users.get(client.userId);
    if (userConns) {
      userConns.delete(connId);
      if (userConns.size === 0) this.users.delete(client.userId);
    }

    // Remove from all rooms
    for (const room of client.rooms) {
      const roomConns = this.rooms.get(room);
      if (roomConns) {
        roomConns.delete(connId);
        if (roomConns.size === 0) this.rooms.delete(room);
      }
    }

    this.connections.delete(connId);
    this.logger.info({ connId, userId: client.userId }, 'ws.disconnected');
  }

  subscribe(connId: string, room: string): void {
    if (!this.rooms.has(room)) {
      this.rooms.set(room, new Set());
    }
    this.rooms.get(room)!.add(connId);

    const entry = this.connections.get(connId);
    if (entry) entry.client.rooms.add(room);

    this.logger.info({ connId, room }, 'ws.subscribed');
  }

  unsubscribe(connId: string, room: string): void {
    const roomConns = this.rooms.get(room);
    if (roomConns) {
      roomConns.delete(connId);
      if (roomConns.size === 0) this.rooms.delete(room);
    }

    const entry = this.connections.get(connId);
    if (entry) entry.client.rooms.delete(room);

    this.logger.info({ connId, room }, 'ws.unsubscribed');
  }

  broadcastToRoom(room: string, message: WsMessage, exceptConnId?: string): void {
    const roomConns = this.rooms.get(room);
    if (!roomConns) return;

    const json = JSON.stringify(message);
    for (const connId of roomConns) {
      if (connId === exceptConnId) continue;
      this.safeSend(connId, json);
    }
  }

  sendToUser(userId: string, message: WsMessage): void {
    const userConns = this.users.get(userId);
    if (!userConns) return;

    const json = JSON.stringify(message);
    for (const connId of userConns) {
      this.safeSend(connId, json);
    }
  }

  private safeSend(connId: string, json: string): void {
    const entry = this.connections.get(connId);
    if (entry && entry.ws.readyState === WebSocket.OPEN) {
      entry.ws.send(json, (err) => {
        if (err) {
          this.logger.debug({ connId, error: err.message }, 'ws.send_failed');
        }
      });
    }
  }

  getClient(connId: string): ConnectedClient | undefined {
    return this.connections.get(connId)?.client;
  }

  get activeConnections(): number {
    return this.connections.size;
  }

  get activeRooms(): number {
    return this.rooms.size;
  }
}
```

## WebSocket Server with `ws` Library

```typescript
// src/ws/server.ts

import { WebSocketServer, WebSocket } from 'ws';
import { IncomingMessage } from 'http';
import { v4 as uuidv4 } from 'uuid';
import { Logger } from 'pino';
import { URL } from 'url';

import { ConnectionManager } from './manager';
import type { ConnectedClient, WsMessage } from './types';
import { validateJwt } from '../auth/jwt';

const MAX_MESSAGE_SIZE = 65536; // 64KB
const HEARTBEAT_INTERVAL = 30_000; // 30s
const HEARTBEAT_TIMEOUT = 10_000;  // 10s

export function createWebSocketServer(
  server: import('http').Server,
  manager: ConnectionManager,
  logger: Logger,
): WebSocketServer {
  const wss = new WebSocketServer({
    server,
    path: '/ws',
    maxPayload: MAX_MESSAGE_SIZE,
    verifyClient: async (info, callback) => {
      // Authenticate on upgrade
      try {
        const url = new URL(info.req.url!, `http://${info.req.headers.host}`);
        const token = url.searchParams.get('token');
        if (!token) {
          callback(false, 401, 'Unauthorized');
          return;
        }
        const claims = await validateJwt(token);
        (info.req as any).__claims = claims;
        callback(true);
      } catch (err) {
        logger.warn({ error: (err as Error).message }, 'ws.auth_failed');
        callback(false, 401, 'Unauthorized');
      }
    },
  });

  wss.on('connection', (ws: WebSocket, req: IncomingMessage) => {
    const claims = (req as any).__claims;
    const client: ConnectedClient = {
      id: uuidv4(),
      userId: claims.userId,
      tenantId: claims.tenantId,
      roles: claims.roles,
      rooms: new Set(),
    };

    manager.register(client, ws);

    // Heartbeat
    let alive = true;
    ws.on('pong', () => { alive = true; });

    const heartbeat = setInterval(() => {
      if (!alive) {
        logger.debug({ connId: client.id }, 'ws.heartbeat_timeout');
        ws.terminate();
        return;
      }
      alive = false;
      ws.ping();
    }, HEARTBEAT_INTERVAL);

    // Message handler
    ws.on('message', (data: Buffer) => {
      try {
        const msg: WsMessage = JSON.parse(data.toString());
        handleMessage(client, msg, manager, ws, logger);
      } catch (err) {
        sendError(ws, undefined, 'INVALID_JSON', 'Malformed JSON');
      }
    });

    // Cleanup
    ws.on('close', () => {
      clearInterval(heartbeat);
      manager.unregister(client.id);
    });

    ws.on('error', (err) => {
      logger.error({ connId: client.id, error: err.message }, 'ws.error');
    });
  });

  return wss;
}

function handleMessage(
  client: ConnectedClient,
  msg: WsMessage,
  manager: ConnectionManager,
  ws: WebSocket,
  logger: Logger,
): void {
  switch (msg.type) {
    case 'subscribe': {
      const room = (msg.payload as any)?.room;
      if (!room) {
        sendError(ws, msg.ref, 'INVALID_PAYLOAD', 'room is required');
        return;
      }
      if (!canJoinRoom(client, room)) {
        sendError(ws, msg.ref, 'FORBIDDEN', 'Not authorized for this room');
        return;
      }
      manager.subscribe(client.id, room);
      sendAck(ws, msg.ref);
      break;
    }

    case 'unsubscribe': {
      const room = (msg.payload as any)?.room;
      if (room) manager.unsubscribe(client.id, room);
      sendAck(ws, msg.ref);
      break;
    }

    case 'message': {
      const payload = msg.payload as any;
      const room = payload?.room;
      if (!room || !client.rooms.has(room)) {
        sendError(ws, msg.ref, 'NOT_IN_ROOM', 'Not subscribed to this room');
        return;
      }
      manager.broadcastToRoom(
        room,
        {
          type: 'message',
          payload: payload.data,
          room,
          timestamp: new Date().toISOString(),
        },
        client.id,
      );
      sendAck(ws, msg.ref);
      break;
    }

    default:
      sendError(ws, msg.ref, 'UNKNOWN_TYPE', `Unknown message type: ${msg.type}`);
  }
}

function canJoinRoom(client: ConnectedClient, room: string): boolean {
  // Implement room authorization
  return true;
}

function sendAck(ws: WebSocket, ref?: string): void {
  if (ref && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'ack', ref }));
  }
}

function sendError(ws: WebSocket, ref: string | undefined, code: string, message: string): void {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'error', code, message, ref }));
  }
}
```

## Socket.IO Alternative (Higher-Level)

```typescript
// src/ws/socket-io-server.ts

import { Server, Socket } from 'socket.io';
import { Logger } from 'pino';
import http from 'http';
import { validateJwt } from '../auth/jwt';

export function createSocketIOServer(
  httpServer: http.Server,
  logger: Logger,
): Server {
  const io = new Server(httpServer, {
    path: '/socket.io',
    cors: { origin: '*' },
    pingInterval: 30_000,
    pingTimeout: 10_000,
    maxHttpBufferSize: 65536,
    transports: ['websocket', 'polling'], // WS first, fallback to polling
  });

  // Authentication middleware
  io.use(async (socket, next) => {
    const token = socket.handshake.auth?.token || socket.handshake.query?.token;
    if (!token) {
      return next(new Error('Unauthorized'));
    }
    try {
      const claims = await validateJwt(token as string);
      socket.data.userId = claims.userId;
      socket.data.tenantId = claims.tenantId;
      socket.data.roles = claims.roles;
      next();
    } catch (err) {
      logger.warn({ error: (err as Error).message }, 'ws.auth_failed');
      next(new Error('Unauthorized'));
    }
  });

  io.on('connection', (socket: Socket) => {
    const { userId, tenantId } = socket.data;
    logger.info({ socketId: socket.id, userId }, 'ws.connected');

    // Auto-join user-specific room for targeted messages
    socket.join(`user:${userId}`);

    // Subscribe to a room
    socket.on('subscribe', (data: { room: string }, ack?: (resp: any) => void) => {
      // Authorization check
      if (!canJoinRoom(socket.data, data.room)) {
        ack?.({ error: 'FORBIDDEN' });
        return;
      }
      socket.join(data.room);
      logger.info({ socketId: socket.id, room: data.room }, 'ws.subscribed');
      ack?.({ status: 'ok' });
    });

    // Unsubscribe
    socket.on('unsubscribe', (data: { room: string }) => {
      socket.leave(data.room);
      logger.info({ socketId: socket.id, room: data.room }, 'ws.unsubscribed');
    });

    // Send message to room
    socket.on('message', (data: { room: string; payload: unknown }, ack?: (resp: any) => void) => {
      if (!socket.rooms.has(data.room)) {
        ack?.({ error: 'NOT_IN_ROOM' });
        return;
      }
      // Broadcast to room except sender
      socket.to(data.room).emit('message', {
        payload: data.payload,
        room: data.room,
        from: userId,
        timestamp: new Date().toISOString(),
      });
      ack?.({ status: 'ok' });
    });

    socket.on('disconnect', (reason) => {
      logger.info({ socketId: socket.id, userId, reason }, 'ws.disconnected');
    });
  });

  return io;
}

function canJoinRoom(data: any, room: string): boolean {
  // Implement room authorization
  return true;
}

// Broadcasting from service layer:
// io.to('room-123').emit('update', { ... });
// io.to(`user:${userId}`).emit('notification', { ... });
```

## Graceful Shutdown

```typescript
// src/ws/shutdown.ts

import { WebSocketServer } from 'ws';
import { Server as SocketIOServer } from 'socket.io';

export async function shutdownWebSocket(wss: WebSocketServer): Promise<void> {
  return new Promise((resolve) => {
    // Close all connections with "going away" code
    for (const client of wss.clients) {
      client.close(1001, 'Server shutting down');
    }
    wss.close(() => resolve());
  });
}

export async function shutdownSocketIO(io: SocketIOServer): Promise<void> {
  // Socket.IO handles disconnecting all clients
  return new Promise((resolve) => {
    io.close(() => resolve());
  });
}
```

## Critical Rules

- Use `verifyClient` callback on `WebSocketServer` for auth — reject before upgrade completes
- Use `ws.ping()` / `ws.on('pong')` for heartbeat — the `ws` library handles protocol-level frames
- Set `maxPayload` on `WebSocketServer` — prevents memory exhaustion from oversized messages
- Check `ws.readyState === WebSocket.OPEN` before sending — prevents errors on closing connections
- Use `ws.terminate()` (not `ws.close()`) for unresponsive connections — `close()` waits for handshake
- Clean up heartbeat interval in `close` handler — prevents memory leaks
- Socket.IO `socket.rooms` includes the socket's own ID as a room — account for this in room checks
- Socket.IO acknowledgements (`ack`) provide request/response semantics — use them for subscribe/message
- For multi-instance Socket.IO: use `@socket.io/redis-adapter` — bridges messages across processes
- Never store WebSocket references in long-lived closures — they become stale after disconnect
