// Harness project: a minimal Spring Boot 4 build the snippet (GraalVM native configuration) is merged into.
plugins {
    java
    id("org.springframework.boot") version "4.1.1"
@PLUGINS@
}

repositories { mavenCentral() }

@SNIPPET@
