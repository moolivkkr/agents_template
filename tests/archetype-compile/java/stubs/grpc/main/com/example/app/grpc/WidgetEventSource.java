package com.example.app.grpc;

import java.util.UUID;
import java.util.function.Consumer;

// Harness stub: an application type the archetype samples use but no archetype defines.
// The event feed grpc-pattern-java.md's watchWidgets excerpt subscribes to.
public interface WidgetEventSource {
    Subscription subscribe(UUID tenantId, Consumer<Object> listener);

    interface Subscription {
        void cancel();
    }
}
