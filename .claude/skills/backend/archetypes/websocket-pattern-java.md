---
skill: websocket-pattern-java
description: Java/Spring Boot WebSocket archetype — Spring WebSocket, STOMP, SimpMessagingTemplate, session management, auth
version: "1.0"
tags:
  - java
  - spring-boot
  - websocket
  - stomp
  - real-time
  - archetype
  - backend
---

# WebSocket Pattern — Java (Spring Boot)

> Java samples compile-checked 2026-09-30: JDK 25.0.4.1, Spring Boot 4.1.1, Maven 3.9.16 (`tests/archetype-compile/java/run.sh`). The ticket and room flow was also run end to end (random-port server with auth-middleware-java.md's SecurityConfig, Redis 7, STOMP and raw clients): no, unknown or reused ticket → 401 envelope; another tenant's room on SUBSCRIBE or SEND → ERROR `FORBIDDEN` and nothing delivered; own tenant delivered.

> **Canonical reference**: This is the Java counterpart to `websocket-pattern.md` (language-neutral). Read that first for concepts and contracts.

Spring Boot provides two WebSocket approaches: raw WebSocket handlers and STOMP over WebSocket. STOMP is recommended for most applications as it provides built-in pub/sub, message routing, and Spring Security integration.

Both authenticate the upgrade with a single-use ticket and confine each socket to its own tenant's rooms.

## How a client connects

1. `POST /api/v1/ws-tickets` with its normal credential (`Authorization: Bearer`): the server stores a
   single-use ticket (user, tenant, roles) for 30 s and returns `{"data": {"ticket", "expires_in"}}`.
2. `ws://…/ws?ticket=<ticket>`: the handshake redeems it (Redis `GETDEL`: used once, then gone) before the
   upgrade. Unknown, expired or reused → 401 in the error envelope, no socket. A bearer token never goes in
   the URL (URLs land in access logs); a consumed ticket in a log is useless.
3. STOMP `SUBSCRIBE`/`SEND` to a room: deny by default. A room is `tenant:<tenantId>` or
   `tenant:<tenantId>:<topic>`, and only the tenant on the ticket may use it — the client never chooses its
   tenant.

`SecurityConfig` (auth-middleware-java.md) permits `/ws` itself: the ticket is its authentication.

## Single-Use Connection Tickets

```java
package com.example.app.ws;

import java.util.List;
import java.util.UUID;

/** What a ticket stands for, copied from the verified token when it was issued. */
public record WsTicket(UUID userId, UUID tenantId, List<String> roles) {}
```

```java
package com.example.app.ws;

import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;
import tools.jackson.databind.ObjectMapper;

import java.security.SecureRandom;
import java.time.Duration;
import java.util.Base64;

/** Tickets in Redis, so the POST and the upgrade can reach different replicas. */
@Component
public class WsTicketStore {

    public static final Duration TTL = Duration.ofSeconds(30);
    private static final SecureRandom RANDOM = new SecureRandom();

    private final StringRedisTemplate redis;
    private final ObjectMapper json;

    public WsTicketStore(StringRedisTemplate redis, ObjectMapper json) {
        this.redis = redis;
        this.json = json;
    }

    public String issue(WsTicket claims) {
        var bytes = new byte[32];
        RANDOM.nextBytes(bytes);
        var ticket = Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
        redis.opsForValue().set(key(ticket), json.writeValueAsString(claims), TTL);
        return ticket;
    }

    /** The ticket's claims, deleted in the same step (GETDEL, Redis 6.2+); null when unknown, expired or used. */
    public WsTicket redeem(String ticket) {
        var raw = redis.opsForValue().getAndDelete(key(ticket));
        return raw == null ? null : json.readValue(raw, WsTicket.class);
    }

    private static String key(String ticket) {
        return "ws-ticket:" + ticket;
    }
}
```

```java
package com.example.app.ws;

import com.example.app.common.ApiResponse;
import com.example.app.security.UserPrincipal;
import org.slf4j.MDC;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/** POST /api/v1/ws-tickets — authenticated like any API call (JWT); the ticket carries that identity. */
@RestController
public class WsTicketController {

    private final WsTicketStore tickets;

    public WsTicketController(WsTicketStore tickets) {
        this.tickets = tickets;
    }

    @PostMapping("/api/v1/ws-tickets")
    @ResponseStatus(HttpStatus.CREATED)
    public ApiResponse<Map<String, Object>> issue(@AuthenticationPrincipal UserPrincipal user) {
        var roles = user.getAuthorities().stream().map(GrantedAuthority::getAuthority).toList();
        var ticket = tickets.issue(new WsTicket(user.getUserId(), user.getTenantId(), roles));
        return ApiResponse.of(Map.of("ticket", ticket, "expires_in", WsTicketStore.TTL.toSeconds()),
            MDC.get("request_id"));
    }
}
```

## Handshake: Redeem the Ticket Before the Upgrade

```java
package com.example.app.ws;

import java.security.Principal;
import java.util.List;
import java.util.UUID;

/** The socket's user. getName() is the user id, so convertAndSendToUser(userId.toString(), …) reaches it. */
public record WsUser(UUID userId, UUID tenantId, List<String> roles) implements Principal {
    @Override
    public String getName() {
        return userId.toString();
    }
}
```

```java
package com.example.app.ws;

import com.example.app.exception.ApiError;
import com.example.app.exception.ErrorBody;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.server.ServerHttpRequest;
import org.springframework.http.server.ServerHttpResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.WebSocketHandler;
import org.springframework.web.socket.server.HandshakeInterceptor;
import org.springframework.web.socket.server.support.DefaultHandshakeHandler;
import org.springframework.web.util.UriComponentsBuilder;
import tools.jackson.databind.ObjectMapper;

import java.security.Principal;
import java.util.List;
import java.util.Map;

/**
 * Redeems ?ticket= before the upgrade. No valid ticket → 401 in the error envelope and no socket; nothing is
 * read from a socket that has not authenticated.
 */
@Component
public class WsTicketHandshakeInterceptor implements HandshakeInterceptor {

    static final String USER = "ws.user";
    private static final Logger log = LoggerFactory.getLogger(WsTicketHandshakeInterceptor.class);

    private final WsTicketStore tickets;
    private final ObjectMapper json;

    public WsTicketHandshakeInterceptor(WsTicketStore tickets, ObjectMapper json) {
        this.tickets = tickets;
        this.json = json;
    }

    @Override
    public boolean beforeHandshake(ServerHttpRequest request, ServerHttpResponse response,
                                   WebSocketHandler handler, Map<String, Object> attributes) throws Exception {
        var ticket = UriComponentsBuilder.fromUri(request.getURI()).build().getQueryParams().getFirst("ticket");
        var claims = ticket == null || ticket.isBlank() ? null : tickets.redeem(ticket);
        if (claims == null) {
            log.warn("ws.auth_failed"); // never log the ticket
            response.setStatusCode(HttpStatus.UNAUTHORIZED);
            response.getHeaders().setContentType(MediaType.APPLICATION_JSON);
            response.getBody().write(json.writeValueAsBytes(new ErrorBody(new ApiError(
                "UNAUTHENTICATED", "Sign in to continue.", List.of(), MDC.get("request_id"), false))));
            return false;
        }
        attributes.put(USER, new WsUser(claims.userId(), claims.tenantId(), claims.roles()));
        return true;
    }

    @Override
    public void afterHandshake(ServerHttpRequest request, ServerHttpResponse response,
                               WebSocketHandler handler, Exception exception) {
    }

    /** Makes the redeemed ticket's user the socket's Principal. */
    public static class TicketUserHandshakeHandler extends DefaultHandshakeHandler {
        @Override
        protected Principal determineUser(ServerHttpRequest request, WebSocketHandler handler,
                                          Map<String, Object> attributes) {
            return (WsUser) attributes.get(USER);
        }
    }
}
```

## Rooms: Deny by Default, Own Tenant Only

```java
package com.example.app.ws;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.messaging.Message;
import org.springframework.messaging.MessageChannel;
import org.springframework.messaging.simp.stomp.StompCommand;
import org.springframework.messaging.simp.stomp.StompHeaderAccessor;
import org.springframework.messaging.support.ChannelInterceptor;
import org.springframework.messaging.support.MessageHeaderAccessor;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.stereotype.Component;

/**
 * Checks every SUBSCRIBE and SEND — including SUBSCRIBEs to broker destinations (/topic/…), which no
 * @MessageMapping or @SubscribeMapping ever sees. Deny by default.
 */
@Component
public class TenantRoomInterceptor implements ChannelInterceptor {

    private static final Logger log = LoggerFactory.getLogger(TenantRoomInterceptor.class);

    @Override
    public Message<?> preSend(Message<?> message, MessageChannel channel) {
        var accessor = MessageHeaderAccessor.getAccessor(message, StompHeaderAccessor.class);
        if (accessor == null) {
            return message;
        }
        var command = accessor.getCommand();
        if (StompCommand.SUBSCRIBE.equals(command) || StompCommand.SEND.equals(command)) {
            var destination = accessor.getDestination();
            if (!(accessor.getUser() instanceof WsUser user) || !mayUse(user, command, destination)) {
                log.warn("ws.forbidden, command={}, destination={}", command, destination);
                throw new AccessDeniedException("FORBIDDEN"); // → STOMP ERROR frame; the message goes nowhere
            }
        }
        return message;
    }

    /**
     * SUBSCRIBE: /topic/tenant:<own>[:topic], and the user's own queues (/user/queue/…, which Spring resolves to
     * this user's sessions). SEND: /app/rooms/tenant:<own>[:topic] only — never straight to /topic/…, which skips
     * the controller and lets a client forge server messages. Nothing else.
     */
    static boolean mayUse(WsUser user, StompCommand command, String destination) {
        if (destination == null) {
            return false;
        }
        if (StompCommand.SUBSCRIBE.equals(command)) {
            return destination.startsWith("/user/queue/") || ownRoom(user, destination, "/topic/");
        }
        return ownRoom(user, destination, "/app/rooms/");
    }

    private static boolean ownRoom(WsUser user, String destination, String prefix) {
        if (!destination.startsWith(prefix)) {
            return false;
        }
        var parts = destination.substring(prefix.length()).split(":", 3); // tenant:<id>[:<topic>]
        return parts.length >= 2 && parts[0].equals("tenant") && parts[1].equals(user.tenantId().toString());
    }
}
```

## WebSocket Configuration with STOMP

```java
package com.example.app.config;

import com.example.app.ws.TenantRoomInterceptor;
import com.example.app.ws.WsTicketHandshakeInterceptor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.messaging.Message;
import org.springframework.messaging.simp.config.ChannelRegistration;
import org.springframework.messaging.simp.config.MessageBrokerRegistry;
import org.springframework.messaging.simp.stomp.StompHeaderAccessor;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.web.socket.config.annotation.*;
import org.springframework.web.socket.messaging.StompSubProtocolErrorHandler;

import java.util.List;

@Configuration
@EnableWebSocketMessageBroker
public class WebSocketConfig implements WebSocketMessageBrokerConfigurer {

    private final WsTicketHandshakeInterceptor tickets;
    private final TenantRoomInterceptor rooms;
    private final List<String> allowedOrigins;

    public WebSocketConfig(WsTicketHandshakeInterceptor tickets, TenantRoomInterceptor rooms,
                           @Value("${app.ws.allowed-origins}") List<String> allowedOrigins) {
        this.tickets = tickets;
        this.rooms = rooms;
        this.allowedOrigins = allowedOrigins;
    }

    @Override
    public void configureMessageBroker(MessageBrokerRegistry config) {
        config.enableSimpleBroker("/topic", "/queue");     // server → client (rooms, user queues)
        config.setApplicationDestinationPrefixes("/app");  // client → server (@MessageMapping)
        config.setUserDestinationPrefix("/user");
    }

    @Override
    public void registerStompEndpoints(StompEndpointRegistry registry) {
        registry.addEndpoint("/ws")
            .setAllowedOrigins(allowedOrigins.toArray(String[]::new)) // an allowlist, never "*"
            .addInterceptors(tickets)                                 // ?ticket= redeemed before the upgrade
            .setHandshakeHandler(new WsTicketHandshakeInterceptor.TicketUserHandshakeHandler());
        // No .withSockJS(): its fallback transports repeat the URL (and its ticket) across many requests
        registry.setErrorHandler(new StompErrors());
    }

    @Override
    public void configureClientInboundChannel(ChannelRegistration registration) {
        registration.interceptors(rooms); // every SUBSCRIBE and SEND, deny by default
    }

    @Override
    public void configureWebSocketTransport(WebSocketTransportRegistration registration) {
        registration.setMessageSizeLimit(64 * 1024);
    }

    /**
     * A refused SUBSCRIBE/SEND → STOMP ERROR frame with message "FORBIDDEN" (then the server closes the socket).
     * Without this the frame carries the exception text, which names internal channels.
     */
    static class StompErrors extends StompSubProtocolErrorHandler {
        @Override
        protected Message<byte[]> handleInternal(StompHeaderAccessor error, byte[] payload, Throwable cause,
                                                 StompHeaderAccessor clientHeaders) {
            error.setMessage(isAccessDenied(cause) ? "FORBIDDEN" : "BAD_REQUEST");
            return super.handleInternal(error, payload, cause, clientHeaders);
        }

        private static boolean isAccessDenied(Throwable t) {
            for (; t != null; t = t.getCause()) {
                if (t instanceof AccessDeniedException) {
                    return true;
                }
            }
            return false;
        }
    }
}
```

## Message Controller (STOMP)

```java
package com.example.app.controller;

import com.example.app.ws.WsUser;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.messaging.handler.annotation.*;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Controller;

import java.security.Principal;
import java.time.Instant;
import java.util.Map;

@Controller
public class WebSocketController {

    private static final Logger log = LoggerFactory.getLogger(WebSocketController.class);
    private final SimpMessagingTemplate messagingTemplate;

    public WebSocketController(SimpMessagingTemplate messagingTemplate) {
        this.messagingTemplate = messagingTemplate;
    }

    /**
     * SEND /app/rooms/tenant:<id>[:topic] → every subscriber of /topic/tenant:<id>[:topic]. TenantRoomInterceptor
     * has already refused a room of another tenant, so this only adds server metadata.
     */
    @MessageMapping("/rooms/{room}")
    public void handleRoomMessage(@DestinationVariable String room, @Payload Map<String, Object> payload,
                                  Principal principal) {
        var user = (WsUser) principal;
        log.debug("ws.message, userId={}, room={}", user.userId(), room);

        // Object, not var (Map): a Map argument also matches convertAndSend(payload, headers) — ambiguous on Spring Framework 7
        Object message = Map.of(
            "type", "message",
            "payload", payload,
            "from", user.userId().toString(),
            "room", room,
            "timestamp", Instant.now().toString()
        );
        messagingTemplate.convertAndSend("/topic/" + room, message);
    }
}
```

## Broadcasting from Service Layer

```java
package com.example.app.service;

import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

@Service
public class NotificationBroadcaster {

    private final SimpMessagingTemplate messagingTemplate;

    public NotificationBroadcaster(SimpMessagingTemplate messagingTemplate) {
        this.messagingTemplate = messagingTemplate;
    }

    /** Broadcast to one tenant's room: /topic/tenant:<tenantId>:<topic>. There is no cross-tenant broadcast. */
    public void broadcastToTenant(UUID tenantId, String topic, Object payload) {
        var room = "tenant:" + tenantId + ":" + topic;
        // Object, not var (Map): a Map argument also matches convertAndSend(payload, headers) — ambiguous on Spring Framework 7
        Object message = Map.of(
            "type", "update",
            "payload", payload,
            "room", room,
            "timestamp", Instant.now().toString()
        );
        messagingTemplate.convertAndSend("/topic/" + room, message);
    }

    /** Send to a specific user (all their sessions): /user/queue/notifications on the client. */
    public void sendToUser(UUID userId, Object payload) {
        var message = Map.of(
            "type", "notification",
            "payload", payload,
            "timestamp", Instant.now().toString()
        );
        messagingTemplate.convertAndSendToUser(userId.toString(), "/queue/notifications", message);
    }
}
```

## Session Event Listener

```java
package com.example.app.ws;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.event.EventListener;
import org.springframework.messaging.simp.stomp.StompHeaderAccessor;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.messaging.SessionConnectedEvent;
import org.springframework.web.socket.messaging.SessionDisconnectEvent;

import java.util.concurrent.atomic.AtomicInteger;

@Component
public class WebSocketEventListener {

    private static final Logger log = LoggerFactory.getLogger(WebSocketEventListener.class);
    private final AtomicInteger activeConnections = new AtomicInteger(0);

    @EventListener
    public void handleConnect(SessionConnectedEvent event) {
        StompHeaderAccessor accessor = StompHeaderAccessor.wrap(event.getMessage());
        String sessionId = accessor.getSessionId();
        int count = activeConnections.incrementAndGet();

        log.info("ws.connected, sessionId={}, activeConnections={}", sessionId, count);
    }

    @EventListener
    public void handleDisconnect(SessionDisconnectEvent event) {
        StompHeaderAccessor accessor = StompHeaderAccessor.wrap(event.getMessage());
        String sessionId = accessor.getSessionId();
        int count = activeConnections.decrementAndGet();

        log.info("ws.disconnected, sessionId={}, activeConnections={}", sessionId, count);
    }

    public int getActiveConnections() {
        return activeConnections.get();
    }
}
```

## Raw WebSocket Handler (Non-STOMP)

Same ticket handshake; one tenant's broadcast reaches only that tenant's sockets.

```java
package com.example.app.ws;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.socket.*;
import org.springframework.web.socket.handler.ConcurrentWebSocketSessionDecorator;
import org.springframework.web.socket.handler.TextWebSocketHandler;
import tools.jackson.databind.ObjectMapper;
import tools.jackson.databind.json.JsonMapper;

import java.io.IOException;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Use this when STOMP is overkill — e.g., simple notification streaming. Register it with the ticket handshake
 * (in a WebSocketConfigurer) and permit its path in SecurityConfig, as for /ws:
 *   registry.addHandler(handler, "/ws/raw").setAllowedOrigins(origins)
 *       .addInterceptors(ticketInterceptor)
 *       .setHandshakeHandler(new WsTicketHandshakeInterceptor.TicketUserHandshakeHandler());
 */
public class RawWebSocketHandler extends TextWebSocketHandler {

    private static final Logger log = LoggerFactory.getLogger(RawWebSocketHandler.class);
    // tenant → its sockets (decorated: sendMessage is not thread-safe on a raw session)
    private final Map<UUID, Set<WebSocketSession>> sessionsByTenant = new ConcurrentHashMap<>();
    private final ObjectMapper objectMapper = JsonMapper.shared(); // Jackson 3 (Spring Boot 4)

    @Override
    public void afterConnectionEstablished(WebSocketSession session) throws IOException {
        if (!(session.getPrincipal() instanceof WsUser user)) { // only reachable through the ticket handshake
            session.close(new CloseStatus(4001, "Unauthorized"));
            return;
        }
        sessionsByTenant.computeIfAbsent(user.tenantId(), t -> ConcurrentHashMap.newKeySet())
            .add(new ConcurrentWebSocketSessionDecorator(session, 10_000, 512 * 1024));
        log.info("ws.connected, sessionId={}, tenantId={}", session.getId(), user.tenantId());
    }

    @Override
    protected void handleTextMessage(WebSocketSession session, TextMessage message) throws Exception {
        if (message.getPayloadLength() > 65536) {
            session.close(new CloseStatus(1009, "Message too large"));
            return;
        }

        var payload = objectMapper.readValue(message.getPayload(), Map.class);
        String type = (String) payload.get("type");

        log.debug("ws.message, sessionId={}, type={}", session.getId(), type);
        // Handle message based on type...
    }

    @Override
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) {
        remove(session);
        log.info("ws.disconnected, sessionId={}, code={}", session.getId(), status.getCode());
    }

    @Override
    public void handleTransportError(WebSocketSession session, Throwable exception) {
        log.error("ws.error, sessionId={}", session.getId(), exception);
        remove(session);
    }

    /** One tenant's sockets only. */
    public void broadcast(UUID tenantId, Object message) throws IOException {
        TextMessage textMessage = new TextMessage(objectMapper.writeValueAsString(message));
        for (WebSocketSession session : sessionsByTenant.getOrDefault(tenantId, Set.of())) {
            if (session.isOpen()) {
                session.sendMessage(textMessage);
            }
        }
    }

    private void remove(WebSocketSession session) {
        sessionsByTenant.values().forEach(set -> set.removeIf(s -> s.getId().equals(session.getId())));
    }
}
```

## Critical Rules

- Use STOMP over WebSocket for most applications — it provides routing, pub/sub, and security integration out of the box
- Authenticate the upgrade with a single-use ticket (`POST /api/v1/ws-tickets` → `?ticket=`, redeemed with Redis `GETDEL`) — never a bearer token in the URL; no valid ticket → 401 envelope, no socket
- The socket's tenant comes from the ticket, never from the client: a room is `tenant:<tenantId>[:<topic>]`, and `TenantRoomInterceptor` refuses every other SUBSCRIBE or SEND (deny by default) — `@MessageMapping`/`@SubscribeMapping` never see subscriptions to `/topic/…`, so the check belongs on the inbound channel
- `setAllowedOrigins` with an allowlist — never `"*"`; no SockJS fallback (it repeats the ticketed URL)
- Use `SimpMessagingTemplate` for server-initiated broadcasts — one tenant's room, never all sockets
- Use `convertAndSendToUser` for user-targeted messages — the socket's `Principal` name is the user id
- Listen for `SessionDisconnectEvent` to clean up resources — do not rely on client close
- For multi-instance scaling: replace the simple broker with a full broker (RabbitMQ STOMP plugin); tickets are already in Redis
- Raw `TextWebSocketHandler` is appropriate only for simple streaming — prefer STOMP otherwise
- Set message size limits via `WebSocketTransportRegistration.setMessageSizeLimit()`
- ConcurrentHashMap for session storage — WebSocket events come from different threads
