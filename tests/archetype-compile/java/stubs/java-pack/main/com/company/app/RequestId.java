package com.company.app;

import org.slf4j.MDC;

// Harness stub: an application type the samples use but no sample defines.
public final class RequestId {
    public static String current() {
        return MDC.get("request_id");
    }
}
