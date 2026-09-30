package sample.perf;

// Harness stub: an application type the archetype samples use but no archetype defines.
public interface CustomerClient {
    CustomerProfile getProfile(String userId);
    CustomerProfile getProfile(String tenantId, String userId);
}
