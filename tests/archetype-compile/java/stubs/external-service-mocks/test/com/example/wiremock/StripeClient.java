package com.example.wiremock;

// Harness stub: an application type the samples use but no sample defines.
public class StripeClient {
    public StripeClient(String baseUrl, String apiKey) {
    }

    public PaymentIntent createPaymentIntent(long amount, String currency) {
        throw new UnsupportedOperationException();
    }

    public record PaymentIntent(String id) {
        public String getId() { return id; }
    }
}
