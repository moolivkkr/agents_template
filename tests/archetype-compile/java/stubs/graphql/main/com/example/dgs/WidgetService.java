package com.example.dgs;

import java.util.UUID;

// Harness stub: an application type the samples use but no sample defines.
public interface WidgetService {
    Widget findById(UUID id, UUID tenantId);
    WidgetConnection list(UUID tenantId, int pageSize, String after, WidgetFilter filter);
}
