package com.company.app;

import java.util.UUID;

// Harness stub: an application type the samples use but no sample defines.
public interface OrderQueryService {
    OrderPage listOrders(UUID tenantId, String cursor, int limit);
}
