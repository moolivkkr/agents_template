package com.example.quarkus;

import java.util.List;

// Harness stub: an application type the samples use but no sample defines.
public abstract class AppException extends RuntimeException {
    public abstract int getStatus();
    public abstract String getCode();
    public abstract String getUserMessage();
    public List<?> getDetails() { return List.of(); }
}
