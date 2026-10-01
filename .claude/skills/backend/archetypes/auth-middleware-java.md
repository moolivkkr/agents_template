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

> Java samples compile-checked 2026-09-30: JDK 25.0.4.1, Spring Boot 4.1.1, Maven 3.9.16 (`tests/archetype-compile/java/run.sh`).

Complete, production-ready Spring Security configuration template. Every generated auth layer MUST follow this pattern.

## Security Filter Chain

```java
package com.example.app.config;

import com.example.app.security.*;
import org.springframework.beans.factory.ObjectProvider;
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
    private final SecurityErrorDelegate securityErrors; // error-handling-java.md
    // API keys (ApiKeyAuthenticationFilter below): used when the app has an ApiKeyRepository bean
    private final ObjectProvider<ApiKeyRepository> apiKeys;

    public SecurityConfig(JwtAuthenticationFilter jwtFilter, SecurityErrorDelegate securityErrors,
                          ObjectProvider<ApiKeyRepository> apiKeys) {
        this.jwtFilter = jwtFilter;
        this.securityErrors = securityErrors;
        this.apiKeys = apiKeys;
    }

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        http
            // 1. Disable CSRF — stateless JWT auth, no session cookies
            .csrf(csrf -> csrf.disable())

            // 2. Stateless sessions — no server-side session state
            .sessionManagement(session ->
                session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))

            // 3. 401/403 in the ONE error envelope: SecurityErrorDelegate hands them to GlobalExceptionHandler
            .exceptionHandling(exceptions -> exceptions
                .authenticationEntryPoint(securityErrors)       // 401 UNAUTHENTICATED + WWW-Authenticate: Bearer
                .accessDeniedHandler(securityErrors))           // 403 FORBIDDEN

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
            .addFilterBefore(jwtFilter, UsernamePasswordAuthenticationFilter.class);

        // 6. API keys (if the app stores them): read right after the JWT filter, INSIDE this chain. As a plain
        //    servlet filter it would run after Spring Security had already answered 401.
        apiKeys.ifAvailable(repo -> http.addFilterAfter(new ApiKeyAuthenticationFilter(repo), JwtAuthenticationFilter.class));

        return http.build();
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

/**
 * Validates JWT Bearer tokens and sets the Spring Security authentication context.
 * Extends OncePerRequestFilter to guarantee single execution per request.
 */
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
            MDC.put("user_id", claims.getSubject());
            MDC.put("tenant_id", claims.get("tenant_id", String.class));

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
            MDC.remove("user_id");
            MDC.remove("tenant_id");
        }
    }

    /**
     * Skip JWT filter for public endpoints to avoid unnecessary parsing.
     */
    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        // The path inside the app. Not getServletPath(): that is "" under MockMvc and only the prefix when
        // spring.mvc.servlet.path is set, so a check on it silently changes meaning.
        var path = request.getRequestURI().substring(request.getContextPath().length());
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

/**
 * Custom UserDetails implementation carrying tenant and user context.
 * Injected into controllers via @AuthenticationPrincipal.
 */
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

## 401 and 403 Responses

Spring Security rejects a request in the filter chain, before any controller runs, so
`@RestControllerAdvice` never sees it on its own. `SecurityErrorDelegate` (`error-handling-java.md`)
implements both `AuthenticationEntryPoint` (401) and `AccessDeniedHandler` (403) and hands the exception to
`GlobalExceptionHandler`, which writes the one error envelope: `{"error": {"code": "UNAUTHENTICATED"`
or `"FORBIDDEN", "message", "request_id", "retryable": false}}`, with `WWW-Authenticate: Bearer` on 401.
`SecurityConfig` above wires it. Don't write a JSON body in an entry point or access-denied handler: a
hand-built `{"error": {"code": "UNAUTHORIZED", ...}}` is a second error shape (wrong code, no `request_id`,
no `retryable`) that clients and contract tests reject.

## Role-Based Access Control (@PreAuthorize)

```java
package com.example.app.controller;

import com.example.app.model.dto.*;
import com.example.app.security.UserPrincipal;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

// Where the annotations go; method bodies are elided (the full controller is crud-handler-java.md).
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

/**
 * Custom authorization logic referenced from @PreAuthorize SpEL expressions.
 * Usage: @PreAuthorize("@widgetAuthz.isOwner(#id, authentication)")
 */
@Component("widgetAuthz")
public class WidgetAuthorizationService {

    private final WidgetRepository widgetRepository;

    public WidgetAuthorizationService(WidgetRepository widgetRepository) {
        this.widgetRepository = widgetRepository;
    }

    /**
     * Check if the authenticated user is the creator of the widget.
     */
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

import com.example.app.exception.RateLimitException;
import io.github.bucket4j.Bandwidth;
import io.github.bucket4j.Bucket;
import jakarta.servlet.*;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerExceptionResolver;

import java.io.IOException;
import java.time.Duration;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Per-tenant rate limiting using bucket4j token bucket algorithm.
 * Each tenant gets its own bucket with configurable rate and burst.
 */
@Component
public class RateLimitFilter implements Filter {

    private static final int REQUESTS_PER_SECOND = 100;
    private static final int BURST_CAPACITY = 200;

    private final Map<UUID, Bucket> tenantBuckets = new ConcurrentHashMap<>();
    private final HandlerExceptionResolver resolver;

    public RateLimitFilter(@Qualifier("handlerExceptionResolver") HandlerExceptionResolver resolver) {
        this.resolver = resolver;
    }

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
            httpResponse.setHeader("X-RateLimit-Remaining", "0");
            // A filter runs outside @RestControllerAdvice: hand the exception to it, so the 429 is the one error
            // envelope (RATE_LIMITED, retryable: true, request_id) with Retry-After (error-handling-java.md)
            resolver.resolveException(httpRequest, httpResponse, null, new RateLimitException(1));
        }
    }

    private Bucket createBucket(UUID tenantId) {
        var bandwidth = Bandwidth.builder()
            .capacity(BURST_CAPACITY)
            .refillGreedy(REQUESTS_PER_SECOND, Duration.ofSeconds(1))
            .build();
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

Use `RequestIdFilter` from `crud-handler-java.md` (package `com.example.app.common`): the app has exactly one.
A second `@Component` class named `RequestIdFilter`, even in another package, fails at startup with a
bean-name conflict (`ConflictingBeanDefinitionException`). It runs first (`HIGHEST_PRECEDENCE`), takes a
well-formed inbound `X-Request-ID` or generates one, and puts it in the MDC as `request_id`.

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
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.security.MessageDigest;
import java.util.List;

/**
 * API key authentication as an alternative to JWT.
 * Checks X-API-Key header and resolves to a tenant/user context.
 *
 * API keys are stored as SHA-256 hashes in the database — never store plaintext. The lookup is by hash,
 * so no plaintext key is ever compared.
 *
 * Not a @Component: SecurityConfig (step 6) creates it inside the SecurityFilterChain, right after the JWT
 * filter, when the app has an ApiKeyRepository. As a bean, Spring Boot would also run it as a plain servlet
 * filter — after Spring Security has already answered 401, so the key would never be read — and every
 * @WebMvcTest slice would have to build it.
 */
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
        var path = request.getRequestURI().substring(request.getContextPath().length()); // not getServletPath()
        return !path.startsWith("/api/v1/");
    }

    private String hashKey(String key) {
        try {
            var digest = MessageDigest.getInstance("SHA-256");
            var hash = digest.digest(key.getBytes(java.nio.charset.StandardCharsets.UTF_8));
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
- MDC MUST be enriched with `user_id` and `tenant_id` at the auth boundary (`request_id` comes from `RequestIdFilter`); keys are snake_case, the set the JSON log encoder includes.
- `shouldNotFilter()` MUST exclude public endpoints from JWT parsing overhead.
- Filter ordering: RequestID -> CORS -> JWT -> APIKey -> RateLimit -> Authorization.
- 401 responses MUST include `WWW-Authenticate: Bearer` header.
- 403 responses MUST use consistent JSON error format matching the application's error envelope.
- Never log JWT tokens, API keys, or credentials — log only derived identifiers (userId, tenantId).
- `@PreAuthorize` for role checks, `@Component("widgetAuthz")` beans for complex authorization logic.
- `SessionCreationPolicy.STATELESS` — no server-side sessions with JWT auth.
- Constructor injection ONLY — no `@Autowired` fields.
