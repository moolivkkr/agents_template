package sample.perf;

// Harness stub: an application type the archetype samples use but no archetype defines.
public interface ShippingClient {
    ShippingEstimate estimate(String address);
    ShippingEstimate estimate(String tenantId, String address);
}
