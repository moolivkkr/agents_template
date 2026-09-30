package com.example.app.worker;

import java.time.Duration;

// Harness stub: an application type the archetype samples use but no archetype defines.
public interface IdempotencyStore {
    boolean isProcessed(String jobId);
    void markProcessed(String jobId, Duration ttl);
}
