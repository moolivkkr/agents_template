// Harness project for a complete build.gradle.kts snippet: its plugins block is the snippet's own, its body follows.
plugins {
@PLUGINS@
}

@SNIPPET@

repositories { mavenCentral() }
