package com.example.quarkus;

import java.util.List;
import java.util.UUID;

// Harness stub: an application type the samples use but no sample defines.
public interface WidgetService {
    default Widget create(UUID tenantId, CreateWidgetRequest request) { throw new UnsupportedOperationException(); }
    default Widget get(UUID tenantId, UUID id) { throw new UnsupportedOperationException(); }
    default List<Widget> list(UUID tenantId, String cursor, int limit, String sortBy) { throw new UnsupportedOperationException(); }
    default Widget update(UUID tenantId, UUID id, UpdateWidgetRequest request) { throw new UnsupportedOperationException(); }
    default void delete(UUID tenantId, UUID id) { throw new UnsupportedOperationException(); }
}
