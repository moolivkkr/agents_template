package com.example.app.controller;

import com.example.app.security.UserPrincipal;

// Harness stub: an application type the archetype samples use but no archetype defines.
public interface RoomAuthorizationService {
    boolean canAccess(UserPrincipal user, String roomId);
}
