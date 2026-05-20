---
skill: auth-middleware-java
description: Spring Security auth archetype — SecurityFilterChain, JwtAuthenticationFilter, @PreAuthorize, RBAC, rate limiting, CORS, request ID filter, API key authentication
version: "1.0"
tags:
  - java
  - spring-boot
  - spring-security
  - jwt
  - rbac
  - middleware
  - archetype
  - backend
---

# Auth Middleware Archetype (Spring Security)

Complete, production-ready Spring Security configuration template. Every generated auth layer MUST follow this pattern.

## Security Filter Chain

```java
package com.example.app.config;

import com.example.app.security.*;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

@Configuration
@EnableWebSecurity
@EnableMethodSecurity(prePostEnabled = true) // enables @PreAuthorize, @PostAuthorize
public class SecurityConfig {

    private final JwtAuthenticationFilter jwtFilter;
    private final JwtAuthenticationEntryPoint authEntryPoint;
    private final CustomAccessDeniedHandler accessDeniedHandler;

    public SecurityConfig(
            JwtAuthenticationFilter jwtFilter,
            JwtAuthenticationEntryPoint authEntryPoint,
            CustomAccessDeniedHandler accessDeniedHandler) {
        this.jwtFilter = jwtFilter;
        this.authEntryPoint = authEntryPoint;
        this.accessDeniedHandler = accessDeniedHandler;
    }

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        return http
            // 1. Disable CSRF — stateless JWT auth, no session cookies
            .csrf(csrf -> csrf.disable())

            // 2. Stateless sessions — no server-side session state
            .sessionManagement(session ->
                session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))

            // 3. Exception handling — custom 401/403 response format
            .exceptionHandling(exceptions -> exceptions
                .authenticationEntryPoint(authEntryPoint)       // 401 handler
                .accessDeniedHandler(accessDeniedHandler))       // 403 handler

            // 4. Authorization rules
            .authorizeHttpRequests(auth -> auth
                // Public endpoints — no authentication required
                .requestMatchers("/actuator/health", "/actuator/info").permitAll()
                .requestMatchers("/api/v1/auth/login", "/api/v1/auth/register").permitAll()
                .requestMatchers("/swagger-ui/**", "/v3/api-docs/**").permitAll()

                // Admin-only endpoints
                .requestMatchers("/api/v1/admin/**").hasRole("ADMIN")

                // All other API endpoints require authentication
                .requestMatchers("/api/v1/**").authenticated()

                // Deny everything else
                .anyRequest().denyAll())

            // 5. Add JWT filter before Spring's default auth filter
            .addFilterBefore(jwtFilter, UsernamePasswordAuthenticationFilter.class)

            .build();
    }
}
```

## JWT Authentication Filter

```java
package com.example.app.security;

import io.jsonwebtoken.*;
import io.jsonwebtoken.security.Keys;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.authentication.WebAuthenticationDetailsSource;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import javax.crypto.SecretKey;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;

 * Validates JWT Bearer tokens and sets the Spring Security authentication context.
 * Extends OncePerRequestFilter to guarantee single execution per request.
@Component
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    private static final Logger log = LoggerFactory.getLogger(JwtAuthenticationFilter.class);
    private static final String AUTHORIZATION_HEADER = "Authorization";
    private static final String BEARER_PREFIX = "Bearer ";

    private final SecretKey signingKey;
    private final String expectedIssuer;
    private final String expectedAudience;

    public JwtAuthenticationFilter(
            @Value("${app.jwt.secret}") String jwtSecret,
            @Value("${app.jwt.issuer}") String issuer,
            @Value("${app.jwt.audience}") String audience) {
        this.signingKey = Keys.hmacShaKeyFor(jwtSecret.getBytes(StandardCharsets.UTF_8));
        this.expectedIssuer = issuer;
        this.expectedAudience = audience;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                     FilterChain filterChain) throws ServletException, IOException {

        var token = extractToken(request);
        if (token == null) {
            filterChain.doFilter(request, response);
            return;
        }

        try {
            var claims = validateAndParseToken(token);
            var authentication = buildAuthentication(claims, request);
            SecurityContextHolder.getContext().setAuthentication(authentication);

            // Enrich MDC for structured logging
            MDC.put("userId", claims.getSubject());
            MDC.put("tenantId", claims.get("tenant_id", String.class));

        } catch (ExpiredJwtException e) {
            log.debug("Expired JWT token");
            // Do not set authentication — Spring Security will return 401
        } catch (JwtException e) {
            log.warn("Invalid JWT token: {}", e.getMessage());
            // Do not set authentication — Spring Security will return 401
        }

        try {
            filterChain.doFilter(request, response);
        } finally {
            MDC.remove("userId");
            MDC.remove("tenantId");
        }
    }

     * Skip JWT filter for public endpoints to avoid unnecessary parsing.
    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        var path = request.getServletPath();
        return path.startsWith("/actuator/")
            || path.startsWith("/swagger-ui/")
            || path.startsWith("/v3/api-docs")
            || path.equals("/api/v1/auth/login")
            || path.equals("/api/v1/auth/register");
    }

    private String extractToken(HttpServletRequest request) {
        var header = request.getHeader(AUTHORIZATION_HEADER);
        if (header != null && header.startsWith(BEARER_PREFIX)) {
            return header.substring(BEARER_PREFIX.length());
        }
        return null;
    }

    private Claims validateAndParseToken(String token) {
        return Jwts.parser()
            .verifyWith(signingKey)
            .requireIssuer(expectedIssuer)
            .requireAudience(expectedAudience)
            .build()
            .parseSignedClaims(token)
            .getPayload();
    }

    @SuppressWarnings("unchecked")
    private UsernamePasswordAuthenticationToken buildAuthentication(Claims claims,
                                                                     HttpServletRequest request) {
        var userId = UUID.fromString(claims.getSubject());
        var tenantId = UUID.fromString(claims.get("tenant_id", String.class));
        var email = claims.get("email", String.class);

        // Extract roles from token claims
        var roles = (List<String>) claims.getOrDefault("roles", List.of());
        var authorities = roles.stream()
            .map(role -> new SimpleGrantedAuthority("ROLE_" + role.toUpperCase()))
            .collect(Collectors.toList());

        var principal = new UserPrincipal(userId, tenantId, email, authorities);

        var authToken = new UsernamePasswordAuthenticationToken(principal, null, authorities);
        authToken.setDetails(new WebAuthenticationDetailsSource().buildDetails(request));
        return authToken;
    }
}
```

## UserPrincipal

```java
package com.example.app.security;

import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.userdetails.UserDetails;

import java.util.Collection;
import java.util.UUID;

 * Custom UserDetails implementation carrying tenant and user context.
 * Injected into controllers via @AuthenticationPrincipal.
public record UserPrincipal(
    UUID userId,
    UUID tenantId,
    String email,
    Collection<? extends GrantedAuthority> authorities
) implements UserDetails {

    // Convenience accessors matching Spring Security patterns
    public UUID getUserId() { return userId; }
    public UUID getTenantId() { return tenantId; }

    @Override public String getUsername() { return email; }
    @Override public String getPassword() { return ""; }
    @Override public Collection<? extends GrantedAuthority> getAuthorities() { return authorities; }
    @Override public boolean isAccountNonExpired() { return true; }
    @Override public boolean isAccountNonLocked() { return true; }
    @Override public boolean isCredentialsNonExpired() { return true; }
    @Override public boolean isEnabled() { return true; }
}
```

## Authentication Entry Point (401 Handler)

```java
package com.example.app.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.MediaType;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.web.AuthenticationEntryPoint;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.util.Map;

 * Handles 401 Unauthorized responses with consistent JSON error format.
 * Called when an unauthenticated user tries to access a protected resource.
@Component
public class JwtAuthenticationEntryPoint implements AuthenticationEntryPoint {

    private final ObjectMapper objectMapper;

    public JwtAuthenticationEntryPoint(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    @Override
    public void commence(HttpServletRequest request, HttpServletResponse response,
                          AuthenticationException authException) throws IOException {
        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setHeader("WWW-Authenticate", "Bearer");

        var body = Map.of(
            "error", Map.of(
                "code", "UNAUTHORIZED",
                "message", "Authentication required. Provide a valid Bearer token."
            )
        );
        objectMapper.writeValue(response.getOutputStream(), body);
    }
}
```

## Access Denied Handler (403 Handler)

```java
package com.example.app.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.MediaType;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.web.access.AccessDeniedHandler;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.util.Map;

 * Handles 403 Forbidden responses with consistent JSON error format.
 * Called when an authenticated user lacks required roles/permissions.
@Component
public class CustomAccessDeniedHandler implements AccessDeniedHandler {

    private final ObjectMapper objectMapper;

    public CustomAccessDeniedHandler(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    @Override
    public void handle(HttpServletRequest request, HttpServletResponse response,
                        AccessDeniedException accessDeniedException) throws IOException {
        response.setStatus(HttpServletResponse.SC_FORBIDDEN);
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);

        var body = Map.of(
            "error", Map.of(
                "code", "FORBIDDEN",
                "message", "You do not have permission to access this resource."
            )
        );
        objectMapper.writeValue(response.getOutputStream(), body);
    }
}
```

## Role-Based Access Control (@PreAuthorize)

```java
package com.example.app.controller;

import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/widgets")
public class WidgetController {

    // Any authenticated user can read
    @GetMapping
    public ResponseEntity<?> list(@AuthenticationPrincipal UserPrincipal principal) {
        // principal.getTenantId() scopes the query
    }

    // Any authenticated user can create
    @PostMapping
    public ResponseEntity<?> create(
            @Valid @RequestBody CreateWidgetRequest request,
            @AuthenticationPrincipal UserPrincipal principal) {
        // ...
    }

    // Only ADMIN or MANAGER can delete
    @DeleteMapping("/{id}")
    @PreAuthorize("hasAnyRole('ADMIN', 'MANAGER')")
    public ResponseEntity<Void> delete(
            @PathVariable UUID id,
            @AuthenticationPrincipal UserPrincipal principal) {
        // ...
    }

    // Custom permission expression
    @PutMapping("/{id}/status")
    @PreAuthorize("hasAuthority('widget:update-status')")
    public ResponseEntity<?> updateStatus(
            @PathVariable UUID id,
            @RequestBody UpdateStatusRequest request,
            @AuthenticationPrincipal UserPrincipal principal) {
        // ...
    }

    // Owner-only access — custom SpEL expression
    @GetMapping("/{id}/audit")
    @PreAuthorize("hasRole('ADMIN') or @widgetAuthz.isOwner(#id, authentication)")
    public ResponseEntity<?> getAuditLog(
            @PathVariable UUID id,
            @AuthenticationPrincipal UserPrincipal principal) {
        // ...
    }
}
```

## Custom Authorization Bean

```java
package com.example.app.security;

import com.example.app.repository.WidgetRepository;
import org.springframework.security.core.Authentication;
import org.springframework.stereotype.Component;

import java.util.UUID;

 * Custom authorization logic referenced from @PreAuthorize SpEL expressions.
 * Usage: @PreAuthorize("@widgetAuthz.isOwner(#id, authentication)")
@Component("widgetAuthz")
public class WidgetAuthorizationService {

    private final WidgetRepository widgetRepository;

    public WidgetAuthorizationService(WidgetRepository widgetRepository) {
        this.widgetRepository = widgetRepository;
    }

     * Check if the authenticated user is the creator of the widget.
    public boolean isOwner(UUID widgetId, Authentication authentication) {
        if (authentication == null || !(authentication.getPrincipal() instanceof UserPrincipal principal)) {
            return false;
        }
        return widgetRepository.findByIdAndTenantId(widgetId, principal.getTenantId())
            .map(w -> w.getCreatedBy().equals(principal.getUserId()))
            .orElse(false);
    }
}
```

## Rate Limiting (bucket4j)

```java
package com.example.app.config;

import io.github.bucket4j.Bandwidth;
import io.github.bucket4j.Bucket;
import io.github.bucket4j.Refill;
import jakarta.servlet.*;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.time.Duration;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

 * Per-tenant rate limiting using bucket4j token bucket algorithm.
 * Each tenant gets its own bucket with configurable rate and burst.
@Component
public class RateLimitFilter implements Filter {

    private static final int REQUESTS_PER_SECOND = 100;
    private static final int BURST_CAPACITY = 200;

    private final Map<UUID, Bucket> tenantBuckets = new ConcurrentHashMap<>();

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {
        var httpRequest = (HttpServletRequest) request;
        var httpResponse = (HttpServletResponse) response;

        // Extract tenant from security context (set by JwtAuthenticationFilter)
        var auth = org.springframework.security.core.context.SecurityContextHolder
            .getContext().getAuthentication();
        if (auth == null || !(auth.getPrincipal() instanceof com.example.app.security.UserPrincipal principal)) {
            // No tenant context — skip rate limiting (auth filter will reject)
            chain.doFilter(request, response);
            return;
        }

        var bucket = tenantBuckets.computeIfAbsent(
            principal.getTenantId(), this::createBucket);

        if (bucket.tryConsume(1)) {
            httpResponse.setHeader("X-RateLimit-Remaining",
                String.valueOf(bucket.getAvailableTokens()));
            chain.doFilter(request, response);
        } else {
            httpResponse.setStatus(HttpStatus.TOO_MANY_REQUESTS.value());
            httpResponse.setContentType(MediaType.APPLICATION_JSON_VALUE);
            httpResponse.setHeader("Retry-After", "1");
            httpResponse.setHeader("X-RateLimit-Remaining", "0");
            httpResponse.getWriter().write("""
                {"error": {"code": "RATE_LIMITED", "message": "Too many requests. Retry after cooldown."}}
                """);
        }
    }

    private Bucket createBucket(UUID tenantId) {
        var bandwidth = Bandwidth.classic(
            BURST_CAPACITY,
            Refill.greedy(REQUESTS_PER_SECOND, Duration.ofSeconds(1))
        );
        return Bucket.builder().addLimit(bandwidth).build();
    }
}
```

## CORS Configuration

```java
package com.example.app.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import java.util.List;

@Configuration
public class CorsConfig {

    @Value("${app.cors.allowed-origins}")
    private List<String> allowedOrigins;

    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        var config = new CorsConfiguration();
        config.setAllowedOrigins(allowedOrigins);
        config.setAllowedMethods(List.of("GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"));
        config.setAllowedHeaders(List.of(
            "Authorization", "Content-Type", "X-Request-ID", "X-API-Key"
        ));
        config.setExposedHeaders(List.of(
            "X-Request-ID", "X-RateLimit-Remaining", "Retry-After"
        ));
        config.setAllowCredentials(true);
        config.setMaxAge(3600L); // preflight cache: 1 hour

        var source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/api/**", config);
        return source;
    }
}
```

## Request ID Filter

```java
package com.example.app.config;

import jakarta.servlet.*;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.MDC;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.util.UUID;

 * Generates or extracts a unique request ID for distributed tracing.
 * Checks X-Request-ID header first (client correlation), generates UUID if absent.
 * Sets MDC for structured logging and echos back on response header.
 * Order: HIGHEST_PRECEDENCE — must run before all other filters.
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class RequestIdFilter implements Filter {

    private static final String REQUEST_ID_HEADER = "X-Request-ID";
    private static final String MDC_KEY = "requestId";

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {
        var httpRequest = (HttpServletRequest) request;
        var httpResponse = (HttpServletResponse) response;

        var requestId = httpRequest.getHeader(REQUEST_ID_HEADER);
        if (requestId == null || requestId.isBlank()) {
            requestId = UUID.randomUUID().toString();
        }

        MDC.put(MDC_KEY, requestId);
        httpResponse.setHeader(REQUEST_ID_HEADER, requestId);

        try {
            chain.doFilter(request, response);
        } finally {
            MDC.remove(MDC_KEY);
        }
    }
}
```

## API Key Authentication Filter

```java
package com.example.app.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.security.MessageDigest;
import java.util.List;

 * API key authentication as an alternative to JWT.
 * Checks X-API-Key header and resolves to a tenant/user context.
 * API keys are stored as SHA-256 hashes in the database — never store plaintext.
 * Uses constant-time comparison to prevent timing attacks.
@Component
public class ApiKeyAuthenticationFilter extends OncePerRequestFilter {

    private static final String API_KEY_HEADER = "X-API-Key";

    private final ApiKeyRepository apiKeyRepository;

    public ApiKeyAuthenticationFilter(ApiKeyRepository apiKeyRepository) {
        this.apiKeyRepository = apiKeyRepository;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                     FilterChain filterChain) throws ServletException, IOException {
        // Only process if JWT filter did not already authenticate
        if (SecurityContextHolder.getContext().getAuthentication() != null) {
            filterChain.doFilter(request, response);
            return;
        }

        var apiKey = request.getHeader(API_KEY_HEADER);
        if (apiKey == null || apiKey.isBlank()) {
            filterChain.doFilter(request, response);
            return;
        }

        // Hash the provided key and look up in DB
        var keyHash = hashKey(apiKey);
        var identity = apiKeyRepository.findByKeyHash(keyHash);

        if (identity.isPresent()) {
            var key = identity.get();
            var authorities = key.getRoles().stream()
                .map(role -> new SimpleGrantedAuthority("ROLE_" + role.toUpperCase()))
                .toList();

            var principal = new UserPrincipal(
                key.getUserId(), key.getTenantId(), key.getLabel(), authorities);

            var authToken = new UsernamePasswordAuthenticationToken(
                principal, null, authorities);
            SecurityContextHolder.getContext().setAuthentication(authToken);
        }

        filterChain.doFilter(request, response);
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        // Only activate for paths that accept API key auth
        return !request.getServletPath().startsWith("/api/v1/");
    }

    private String hashKey(String key) {
        try {
            var digest = MessageDigest.getInstance("SHA-256");
            var hash = digest.digest(key.getBytes());
            return java.util.HexFormat.of().formatHex(hash);
        } catch (Exception e) {
            throw new RuntimeException("Failed to hash API key", e);
        }
    }
}
```

## Security Filter Chain with CORS Integration

```java
// In SecurityConfig, add CORS support:
@Bean
public SecurityFilterChain securityFilterChain(HttpSecurity http,
        CorsConfigurationSource corsConfigurationSource) throws Exception {
    return http
        .cors(cors -> cors.configurationSource(corsConfigurationSource))
        .csrf(csrf -> csrf.disable())
        .sessionManagement(session ->
            session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
        // ... rest of configuration
        .build();
}
```

## application.yml Configuration

```yaml
app:
  jwt:
    secret: ${JWT_SECRET}          # min 256-bit key for HS256
    issuer: "my-app"
    audience: "my-app-api"
    expiration-ms: 3600000         # 1 hour
  cors:
    allowed-origins:
      - "http://localhost:3000"
      - "https://app.example.com"
  rate-limit:
    requests-per-second: 100
    burst-capacity: 200
```

## Filter Ordering Summary

```
Request → RequestIdFilter (HIGHEST_PRECEDENCE)
        → CorsFilter (Spring auto-configured from CorsConfigurationSource)
        → JwtAuthenticationFilter (before UsernamePasswordAuthenticationFilter)
        → ApiKeyAuthenticationFilter (after JWT, before auth check)
        → RateLimitFilter (after auth, so tenant is known)
        → SecurityFilterChain authorization rules
        → Controller
```

## Critical Rules

- JWT validation MUST check signature, expiration, issuer, AND audience — never skip any.
- Tenant ID MUST come from the validated token, NEVER from request params or body.
- Use `@AuthenticationPrincipal UserPrincipal` in controllers — never extract auth from headers manually.
- API keys MUST be stored as SHA-256 hashes — never store or compare plaintext keys.
- Use `MessageDigest` with constant-time comparison for API key lookup (hash then DB lookup).
- Rate limiters MUST be per-tenant — shared limits allow noisy neighbor abuse.
- CORS MUST NOT use `*` with `allowCredentials: true` — browsers reject this combination.
- Request ID MUST be set on response headers for client-side correlation.
- MDC MUST be enriched with `userId`, `tenantId`, `requestId` at the auth boundary.
- `shouldNotFilter()` MUST exclude public endpoints from JWT parsing overhead.
- Filter ordering: RequestID -> CORS -> JWT -> APIKey -> RateLimit -> Authorization.
- 401 responses MUST include `WWW-Authenticate: Bearer` header.
- 403 responses MUST use consistent JSON error format matching the application's error envelope.
- Never log JWT tokens, API keys, or credentials — log only derived identifiers (userId, tenantId).
- `@PreAuthorize` for role checks, `@Component("widgetAuthz")` beans for complex authorization logic.
- `SessionCreationPolicy.STATELESS` — no server-side sessions with JWT auth.
- Constructor injection ONLY — no `@Autowired` fields.
