// Harness project for a dependencies snippet: the snippet's plugins join this block, its body follows.
plugins {
    java
@PLUGINS@
}

@SNIPPET@

repositories { mavenCentral() }
