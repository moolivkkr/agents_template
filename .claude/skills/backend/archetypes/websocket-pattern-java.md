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

> **Canonical reference**: This is the Java counterpart to `websocket-pattern.md` (language-neutral). Read that first for concepts and contracts.

Spring Boot provides two WebSocket approaches: raw WebSocket handlers and STOMP over WebSocket. STOMP is recommended for most applications as it provides built-in pub/sub, message routing, and Spring Security integration.

## WebSocket Configuration with STOMP

```java
package com.example.app.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.messaging.simp.config.MessageBrokerRegistry;
import org.springframework.web.socket.config.annotation.*;

@Configuration
@EnableWebSocketMessageBroker
public class WebSocketConfig implements WebSocketMessageBrokerConfigurer {

    @Override
    public void configureMessageBroker(MessageBrokerRegistry config) {
        // Server -> Client destinations (subscriptions)
        config.enableSimpleBroker("/topic", "/queue");

        // Client -> Server destinations (messages)
        config.setApplicationDestinationPrefixes("/app");

        // User-specific destinations
        config.setUserDestinationPrefix("/user");
    }

    @Override
    public void registerStompEndpoints(StompEndpointRegistry registry) {
        registry.addEndpoint("/ws")
            .setAllowedOriginPatterns("*")
            .withSockJS(); // Fallback for browsers without WebSocket
    }
}
```

## Authentication Interceptor

```java
package com.example.app.config;

import com.example.app.security.JwtTokenProvider;
import com.example.app.security.UserPrincipal;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.messaging.Message;
import org.springframework.messaging.MessageChannel;
import org.springframework.messaging.simp.stomp.StompCommand;
import org.springframework.messaging.simp.stomp.StompHeaderAccessor;
import org.springframework.messaging.support.ChannelInterceptor;
import org.springframework.messaging.support.MessageHeaderAccessor;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.stereotype.Component;

@Component
public class WebSocketAuthInterceptor implements ChannelInterceptor {

    private static final Logger log = LoggerFactory.getLogger(WebSocketAuthInterceptor.class);
    private final JwtTokenProvider jwtProvider;

    public WebSocketAuthInterceptor(JwtTokenProvider jwtProvider) {
        this.jwtProvider = jwtProvider;
    }

    @Override
    public Message<?> preSend(Message<?> message, MessageChannel channel) {
        StompHeaderAccessor accessor = MessageHeaderAccessor
            .getAccessor(message, StompHeaderAccessor.class);

        if (accessor == null) return message;

        if (StompCommand.CONNECT.equals(accessor.getCommand())) {
            // Extract token from STOMP CONNECT headers
            String token = accessor.getFirstNativeHeader("Authorization");
            if (token == null || !token.startsWith("Bearer ")) {
                log.warn("ws.auth_failed: missing or invalid Authorization header");
                throw new SecurityException("Unauthorized");
            }

            token = token.substring(7);
            try {
                UserPrincipal principal = jwtProvider.validateAndGetPrincipal(token);
                accessor.setUser(new UsernamePasswordAuthenticationToken(
                    principal, null, principal.getAuthorities()
                ));
                log.info("ws.authenticated, userId={}, tenantId={}",
                    principal.getUserId(), principal.getTenantId());
            } catch (Exception e) {
                log.warn("ws.auth_failed: {}", e.getMessage());
                throw new SecurityException("Invalid token");
            }
        }

        return message;
    }
}
```

```java
// Register the interceptor
package com.example.app.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.messaging.simp.config.ChannelRegistration;
import org.springframework.web.socket.config.annotation.*;

@Configuration
public class WebSocketChannelConfig implements WebSocketMessageBrokerConfigurer {

    private final WebSocketAuthInterceptor authInterceptor;

    public WebSocketChannelConfig(WebSocketAuthInterceptor authInterceptor) {
        this.authInterceptor = authInterceptor;
    }

    @Override
    public void configureClientInboundChannel(ChannelRegistration registration) {
        registration.interceptors(authInterceptor);
    }
}
```

## Message Controller (STOMP)

```java
package com.example.app.controller;

import com.example.app.security.UserPrincipal;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.messaging.handler.annotation.*;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.messaging.simp.annotation.SubscribeMapping;
import org.springframework.stereotype.Controller;

import java.security.Principal;
import java.time.Instant;
import java.util.Map;

@Controller
public class WebSocketController {

    private static final Logger log = LoggerFactory.getLogger(WebSocketController.class);
    private final SimpMessagingTemplate messagingTemplate;
    private final RoomAuthorizationService roomAuthService;

    public WebSocketController(
            SimpMessagingTemplate messagingTemplate,
            RoomAuthorizationService roomAuthService) {
        this.messagingTemplate = messagingTemplate;
        this.roomAuthService = roomAuthService;
    }

    /**
     * Handle messages sent to /app/room/{roomId}
     * Broadcasts to all subscribers of /topic/room/{roomId}
     */
    @MessageMapping("/room/{roomId}")
    public void handleRoomMessage(
            @DestinationVariable String roomId,
            @Payload Map<String, Object> payload,
            Principal principal) {

        UserPrincipal user = (UserPrincipal) ((UsernamePasswordAuthenticationToken) principal)
            .getPrincipal();

        // Authorization check
        if (!roomAuthService.canAccess(user, roomId)) {
            log.warn("ws.forbidden, userId={}, room={}", user.getUserId(), roomId);
            return;
        }

        log.debug("ws.message, userId={}, room={}", user.getUserId(), roomId);

        // Add server metadata and broadcast
        var message = Map.of(
            "type", "message",
            "payload", payload,
            "from", user.getUserId().toString(),
            "room", roomId,
            "timestamp", Instant.now().toString()
        );

        messagingTemplate.convertAndSend("/topic/room/" + roomId, message);
    }

    /**
     * Subscription handler — called when a client subscribes to /topic/room/{roomId}.
     * Return value is sent as the initial message to the subscriber.
     */
    @SubscribeMapping("/room/{roomId}")
    public Map<String, Object> onSubscribe(
            @DestinationVariable String roomId,
            Principal principal) {

        UserPrincipal user = (UserPrincipal) ((UsernamePasswordAuthenticationToken) principal)
            .getPrincipal();

        if (!roomAuthService.canAccess(user, roomId)) {
            throw new SecurityException("Not authorized for room: " + roomId);
        }

        log.info("ws.subscribed, userId={}, room={}", user.getUserId(), roomId);

        return Map.of(
            "type", "subscribed",
            "room", roomId,
            "timestamp", Instant.now().toString()
        );
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

    /** Broadcast to a room (all subscribers). */
    public void broadcastToRoom(String roomId, Object payload) {
        var message = Map.of(
            "type", "update",
            "payload", payload,
            "room", roomId,
            "timestamp", Instant.now().toString()
        );
        messagingTemplate.convertAndSend("/topic/room/" + roomId, message);
    }

    /** Send to a specific user (all their sessions). */
    public void sendToUser(UUID userId, Object payload) {
        var message = Map.of(
            "type", "notification",
            "payload", payload,
            "timestamp", Instant.now().toString()
        );
        // /user/{userId}/queue/notifications
        messagingTemplate.convertAndSendToUser(
            userId.toString(),
            "/queue/notifications",
            message
        );
    }

    /** Broadcast to all connected clients. */
    public void broadcastAll(Object payload) {
        var message = Map.of(
            "type", "broadcast",
            "payload", payload,
            "timestamp", Instant.now().toString()
        );
        messagingTemplate.convertAndSend("/topic/global", message);
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

```java
package com.example.app.ws;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.socket.*;
import org.springframework.web.socket.handler.TextWebSocketHandler;

import java.io.IOException;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Use this when STOMP is overkill — e.g., simple notification streaming.
 */
public class RawWebSocketHandler extends TextWebSocketHandler {

    private static final Logger log = LoggerFactory.getLogger(RawWebSocketHandler.class);
    private final Map<String, WebSocketSession> sessions = new ConcurrentHashMap<>();
    private final ObjectMapper objectMapper = new ObjectMapper();

    @Override
    public void afterConnectionEstablished(WebSocketSession session) {
        sessions.put(session.getId(), session);
        log.info("ws.connected, sessionId={}", session.getId());
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
        sessions.remove(session.getId());
        log.info("ws.disconnected, sessionId={}, code={}", session.getId(), status.getCode());
    }

    @Override
    public void handleTransportError(WebSocketSession session, Throwable exception) {
        log.error("ws.error, sessionId={}", session.getId(), exception);
        sessions.remove(session.getId());
    }

    public void broadcast(Object message) throws IOException {
        String json = objectMapper.writeValueAsString(message);
        TextMessage textMessage = new TextMessage(json);
        for (WebSocketSession session : sessions.values()) {
            if (session.isOpen()) {
                session.sendMessage(textMessage);
            }
        }
    }
}
```

## Critical Rules

- Use STOMP over WebSocket for most applications — it provides routing, pub/sub, and security integration out of the box
- Authenticate in the `ChannelInterceptor` on `CONNECT` — reject before any message processing
- Use `@DestinationVariable` for room-scoped handlers — validate authorization in every handler
- Use `SimpMessagingTemplate` for server-initiated broadcasts — not direct session access
- Use `convertAndSendToUser` for user-targeted messages — Spring resolves user to session(s)
- Listen for `SessionDisconnectEvent` to clean up resources — do not rely on client close
- For multi-instance scaling: replace the simple broker with a full broker (RabbitMQ STOMP plugin)
- Raw `TextWebSocketHandler` is appropriate only for simple streaming — prefer STOMP otherwise
- Set message size limits via `WebSocketTransportRegistration.setMessageSizeLimit()`
- ConcurrentHashMap for session storage — WebSocket events come from different threads
