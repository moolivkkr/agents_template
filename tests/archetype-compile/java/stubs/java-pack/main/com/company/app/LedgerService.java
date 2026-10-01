package com.company.app;

import java.util.UUID;

// Harness stub: an application type the samples use but no sample defines.
public interface LedgerService {
    void recordEntry(UUID tenantId, Payment payment);
}
