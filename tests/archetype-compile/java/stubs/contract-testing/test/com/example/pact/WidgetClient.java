package com.example.pact;

// Harness stub: an application type the samples use but no sample defines.
public class WidgetClient {
    public WidgetClient(String baseUrl) {
    }

    public WidgetView getWidget(String id) {
        throw new UnsupportedOperationException();
    }

    public record WidgetView(String id, String name) {
        public String getName() { return name; }
    }
}
