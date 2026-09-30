package sample.perf;

import java.util.Optional;
import java.util.UUID;

// Harness stub: an application type the archetype samples use but no archetype defines.
public interface ProductRepository {
    Optional<Product> findByTenantIdAndId(UUID tenantId, UUID id);
    Product save(Product product);
    void deleteByTenantIdAndId(UUID tenantId, UUID id);
}
