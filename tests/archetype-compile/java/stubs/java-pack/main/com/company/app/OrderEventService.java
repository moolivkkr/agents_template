package com.company.app;

import reactor.core.publisher.Flux;

import java.util.UUID;

// Harness stub: an application type the samples use but no sample defines.
public interface OrderEventService {
    Flux<OrderEvent> subscribe(UUID tenantId);
}
