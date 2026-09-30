package sample.perf;

import java.util.List;
import java.util.UUID;

// Harness stub: an application type the archetype samples use but no archetype defines.
public class Order {
    public static Order fromImport(String tenantId, OrderImport imp) { return new Order(); }
    public static Order create(String tenantId, CreateOrderRequest request) { return new Order(); }
    public UUID getId() { return null; }
    public String getUserId() { return null; }
    public String getAddress() { return null; }
    public List<UUID> getItemIds() { return List.of(); }
}
