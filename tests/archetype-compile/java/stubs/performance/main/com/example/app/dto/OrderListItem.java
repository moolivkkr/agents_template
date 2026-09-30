package com.example.app.dto;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

// Harness stub: an application type the archetype samples use but no archetype defines.
public record OrderListItem(UUID id, String status, BigDecimal total, Instant createdAt, int itemCount) {}
