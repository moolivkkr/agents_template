package com.example.app.security;

import java.util.List;
import java.util.UUID;

// Harness stub: an application type the archetype samples use but no archetype defines.
public interface ApiKey {
    List<String> getRoles();
    UUID getUserId();
    UUID getTenantId();
    String getLabel();
}
