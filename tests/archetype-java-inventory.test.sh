#!/usr/bin/env bash
# archetype-java-inventory.test.sh — every ```java block in .claude/skills (the backend/archetypes/*.md and every
# other skill pack: languages/java.md, frameworks/*.md, testing/*.md, ...) is compiled by a unit of
# tests/archetype-compile/java or skipped there with a reason, and every Kotlin/Groovy/XML/Scala/HOCON block of the
# *-java.md archetypes and the Java packs (languages/java.md, frameworks/spring-boot.md, frameworks/quarkus.md,
# testing/junit-mockito.md) is checked or skipped. A new or removed Java sample fails here until it is mapped in
# tests/archetype-compile/java/units.py.
# This is the inventory only (no JDK needed). The compile itself: bash tests/archetype-compile/java/run.sh
# (needs JDK 25, Maven, Gradle and network on the first run).
# Run: bash tests/archetype-java-inventory.test.sh   (exit 0 = pass; bash 3.2 compatible; no network)
set -uo pipefail
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$TEST_DIR/archetype-compile/java/harness.py" inventory
