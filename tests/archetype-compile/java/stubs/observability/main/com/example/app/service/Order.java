package com.example.app.service;

import java.math.BigDecimal;
import java.util.UUID;

// Harness stub: an application type the archetype samples use but no archetype defines.
public class Order {
    public static Order create(String tenantId, String userId, CreateOrderRequest request) { return new Order(); }
    public static Order create(String tenantId, CreateOrderRequest request) { return new Order(); }
    public static Order fromRequest(String tenantId, OrderRequest request) { return new Order(); }
    public UUID getId() { return null; }
    public BigDecimal getTotal() { return null; }
    public String getPaymentMethod() { return null; }
    public String getUserId() { return null; }
    public String getAddress() { return null; }
}
