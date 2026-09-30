package snippet;

import io.micrometer.registry.otlp.OtlpMeterRegistry;
import io.opentelemetry.instrumentation.annotations.WithSpan;
import net.logstash.logback.encoder.LogstashEncoder;

// Compiles only if the snippet's dependencies resolve onto the compile classpath.
class Probe {
    OtlpMeterRegistry registry;
    LogstashEncoder encoder;

    @WithSpan
    void traced() {}
}
