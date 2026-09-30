package com.example.app.worker.stream;

import java.util.UUID;

// Harness stub: an application type the archetype samples use but no archetype defines.
public record OrderEvent(UUID orderId, UUID tenantId) {}
