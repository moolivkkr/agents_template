// Harness project for a dependencies snippet that uses the doc's version catalog (gradle/libs.versions.toml).
plugins {
    java
@PLUGINS@
}

@SNIPPET@

repositories { mavenCentral() }
