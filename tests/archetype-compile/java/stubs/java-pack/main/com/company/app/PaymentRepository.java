package com.company.app;

import java.util.List;
import java.util.UUID;

// Harness stub: an application type the samples use but no sample defines.
public interface PaymentRepository {
    Payment save(Payment payment);
    List<Payment> findByTenantId(UUID tenantId);
}
