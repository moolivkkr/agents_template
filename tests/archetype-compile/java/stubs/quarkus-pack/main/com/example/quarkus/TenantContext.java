package com.example.quarkus;

import jakarta.ws.rs.core.SecurityContext;

import java.util.UUID;

// Harness stub: an application type the samples use but no sample defines.
public final class TenantContext {
    public static UUID getTenantId(SecurityContext ctx) {
        throw new UnsupportedOperationException();
    }
}
