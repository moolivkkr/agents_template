package com.company.app;

// Harness stub: an application type the samples use but no sample defines.
public final class OrderMapper {
    public static OrderResponse toResponse(Order order) {
        return new OrderResponse(order.getId(), order.getStatus());
    }
}
