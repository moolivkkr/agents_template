package com.example.quarkus;

import java.util.List;
import java.util.Map;

// Harness stub: an application type the samples use but no sample defines.
public class ValidationException extends AppException {
    private final List<?> details;
    public ValidationException(String field, String code, String message) {
        this.details = List.of(Map.of("field", field, "code", code, "message", message));
    }
    @Override public int getStatus() { return 400; }
    @Override public String getCode() { return "VALIDATION_FAILED"; }
    @Override public String getUserMessage() { return "Some fields are invalid."; }
    @Override public List<?> getDetails() { return details; }
}
