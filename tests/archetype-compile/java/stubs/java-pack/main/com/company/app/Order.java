package com.company.app;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

// Harness stub: an application type the samples use but no sample defines.
// A mapped entity, so the repository samples' queries are validated when a Spring Data context starts.
@Entity
@Table(name = "orders")
public class Order {
    @Id
    private UUID id;
    @Column(name = "tenant_id", nullable = false)
    private UUID tenantId;
    @Enumerated(EnumType.STRING)
    private OrderStatus status;
    private BigDecimal total;
    @Column(name = "created_at", nullable = false)
    private Instant createdAt;
    @Column(name = "deleted_at")
    private Instant deletedAt;

    protected Order() {
    }

    public static Order create(UUID tenantId, CreateOrderRequest request) {
        var order = new Order();
        order.id = UUID.randomUUID();
        order.tenantId = tenantId;
        order.status = OrderStatus.PENDING;
        order.total = request.items().stream()
            .map(i -> i.price().multiply(BigDecimal.valueOf(i.quantity())))
            .reduce(BigDecimal.ZERO, BigDecimal::add);
        order.createdAt = Instant.now();
        return order;
    }

    public static boolean isValidTransition(OrderStatus from, OrderStatus to) {
        return switch (from) {
            case PENDING -> to == OrderStatus.CONFIRMED || to == OrderStatus.CANCELLED;
            case CONFIRMED -> to == OrderStatus.SHIPPED || to == OrderStatus.CANCELLED;
            default -> false;
        };
    }

    public UUID getId() { return id; }
    public UUID getTenantId() { return tenantId; }
    public OrderStatus getStatus() { return status; }
    public BigDecimal getTotal() { return total; }
    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
    public Instant getDeletedAt() { return deletedAt; }
    public void setDeletedAt(Instant deletedAt) { this.deletedAt = deletedAt; }
}
