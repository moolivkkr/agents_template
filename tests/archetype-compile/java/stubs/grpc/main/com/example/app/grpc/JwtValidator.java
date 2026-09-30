package com.example.app.grpc;

import java.util.UUID;

// Harness stub: an application type the archetype samples use but no archetype defines.
public interface JwtValidator {
    Claims validate(String token);

    interface Claims {
        UUID getTenantId();
        UUID getUserId();
    }
}
