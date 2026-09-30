package com.example.app.security;

// Harness stub: an application type the archetype samples use but no archetype defines.
public interface JwtTokenProvider {
    UserPrincipal validateAndGetPrincipal(String token);
}
