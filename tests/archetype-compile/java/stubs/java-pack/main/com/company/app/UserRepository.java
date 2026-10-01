package com.company.app;

import java.util.Optional;
import java.util.UUID;

// Harness stub: an application type the samples use but no sample defines.
public interface UserRepository {
    Optional<User> findByTenantIdAndId(UUID tenantId, UUID id);
    User save(User user);
}
