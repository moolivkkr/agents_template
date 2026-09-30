package sample.perf;

import java.util.Optional;
import java.util.UUID;

// Harness stub: an application type the archetype samples use but no archetype defines.
public interface OrderLookup {
    Optional<Order> findById(UUID id);
}
