package com.example.app.service;

import com.example.app.model.entity.Widget;
import org.springframework.data.domain.ScrollPosition;
import org.springframework.data.domain.Sort;
import org.springframework.data.domain.Window;

import java.util.UUID;

// Harness stub: an application type the archetype samples use but no archetype defines.
// The service interface whose search(...) the crud-repository-java.md excerpt overrides.
public interface WidgetSearch {
    Window<Widget> search(UUID tenantId, WidgetSearchExample.WidgetSearchCriteria criteria,
                          ScrollPosition position, Sort sort, int limit);
}
