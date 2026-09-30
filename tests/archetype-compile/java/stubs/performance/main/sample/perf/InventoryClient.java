package sample.perf;

import java.util.List;
import java.util.UUID;

// Harness stub: an application type the archetype samples use but no archetype defines.
public interface InventoryClient {
    StockLevels checkStock(List<UUID> itemIds);
}
