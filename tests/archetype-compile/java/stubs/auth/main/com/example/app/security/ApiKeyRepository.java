package com.example.app.security;

import java.util.Optional;

// Harness stub: an application type the archetype samples use but no archetype defines.
public interface ApiKeyRepository {
    Optional<ApiKey> findByKeyHash(String keyHash);
}
