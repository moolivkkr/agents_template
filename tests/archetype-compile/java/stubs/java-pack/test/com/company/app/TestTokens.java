package com.company.app;

import java.util.UUID;

// Harness stub: an application type the samples use but no sample defines.
public final class TestTokens {
    public static String forTenant(UUID tenantId) {
        return "test-token-for-" + tenantId;
    }
}
