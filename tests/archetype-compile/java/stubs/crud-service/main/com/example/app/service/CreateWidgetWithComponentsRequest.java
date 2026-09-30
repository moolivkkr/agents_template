package com.example.app.service;

import java.util.List;

// Harness stub: an application type the archetype samples use but no archetype defines.
public record CreateWidgetWithComponentsRequest(String name, String description, List<Component> components) {
    public record Component(String name) {}
}
