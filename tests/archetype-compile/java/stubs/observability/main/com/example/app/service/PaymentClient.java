package com.example.app.service;

import java.math.BigDecimal;
import java.util.UUID;

// Harness stub: an application type the archetype samples use but no archetype defines.
public interface PaymentClient {
    void charge(String tenantId, UUID orderId, BigDecimal amount);
}
