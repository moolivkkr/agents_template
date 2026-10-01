package com.example.dgs;

import com.netflix.graphql.dgs.DgsDataFetchingEnvironment;

import java.util.UUID;

// Harness stub: an application type the samples use but no sample defines.
public final class AuthContext {
    public static UUID getTenantId(DgsDataFetchingEnvironment dfe) {
        return UUID.fromString("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"); // the verified token's tenant, in the app
    }
}
