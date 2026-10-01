package com.company.app;

// Harness stub: an application type the samples use but no sample defines.
public final class EmailValidator {
    public static boolean isValid(String email) {
        return email != null && email.contains("@");
    }
}
