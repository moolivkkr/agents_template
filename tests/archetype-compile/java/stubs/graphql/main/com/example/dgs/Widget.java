package com.example.dgs;

import java.util.UUID;

// Harness stub: an application type the samples use but no sample defines.
public record Widget(UUID id, String name, UUID createdById) {
    public UUID getCreatedById() { return createdById; }
}
