#!/usr/bin/env bash
# run.sh — compile every Java sample in .claude/skills: the archetypes (backend/archetypes/*.md) and every other
# skill pack's ```java blocks (languages/java.md, frameworks/{spring-boot,quarkus,graphql}.md, testing/*.md), and
# check the JVM build snippets they depend on.
#
#   bash tests/archetype-compile/java/run.sh              # everything (Maven units + Gradle snippets)
#   bash tests/archetype-compile/java/run.sh --inventory  # only: is every ```java block compiled or skipped? (no JDK)
#   bash tests/archetype-compile/java/run.sh --keep       # keep the generated project (path printed at the end)
#
# What it does, from the markdown as it is NOW (so an edited sample is re-verified):
#   1. harness.py inventory — fails if a file's ```java block count differs from units.py, or any block is
#      neither compiled by a unit nor skipped with a reason, or a Kotlin/Groovy/XML build block is unchecked.
#   2. harness.py layout — one Maven module per unit (parent-pom.xml: Spring Boot 4.1.1 and the libraries the
#      samples import; the Quarkus pack has its own POM on the Quarkus 3.40.1 BOM), plus modules/projects for the
#      Maven and Gradle build snippets.
#   3. mvn test-compile over the reactor (--fail-at-end): main code compiles, tests type-check. Nothing runs,
#      so no database or Docker is needed. Compiler errors are mapped back to <file>.md:<line>.
#   4. Build snippets: `mvn package` for snippets that configure packaging (layers.idx is checked), `mvn verify`
#      for the JaCoCo coverage gate (a probe test runs under the agent on JDK 25), Gradle
#      tasks for the Gradle snippets (compile, bootJar + layers.idx, native task graph, protobuf codegen),
#      and an OpenTelemetry API version check (Spring Boot's BOM must not downgrade what the OTel starter needs).
#
# Needs: JDK 25 (exactly — the structured-concurrency sample is a JDK 25 preview API), Maven 3.9+, Gradle 9+,
# python3, network access to Maven Central / the Gradle plugin portal on the first run.
# Exit 0 = every unit and snippet passed.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEEP=0
for a in "$@"; do
  case "$a" in
    --inventory) exec python3 "$HERE/harness.py" inventory ;;
    --keep) KEEP=1 ;;
    *) echo "usage: run.sh [--inventory] [--keep]"; exit 2 ;;
  esac
done

# ── toolchain ──
pick_jdk() {
  local c
  for c in "${JAVA_HOME:-}" "$(/usr/libexec/java_home -v 25 2>/dev/null)" \
           /opt/homebrew/opt/openjdk@25 /usr/local/opt/openjdk@25 /usr/lib/jvm/java-25-openjdk*; do
    [ -n "$c" ] && [ -x "$c/bin/javac" ] || continue
    if "$c/bin/javac" -version 2>&1 | grep -qE '^javac 25(\.|$)'; then echo "$c"; return 0; fi
  done
  return 1
}
if ! JDK="$(pick_jdk)"; then
  echo "FAIL toolchain: JDK 25 not found (set JAVA_HOME, or: brew install openjdk@25)"; exit 2
fi
export JAVA_HOME="$JDK" PATH="$JDK/bin:$PATH"
command -v mvn >/dev/null || { echo "FAIL toolchain: mvn not found (brew install maven)"; exit 2; }
command -v gradle >/dev/null || { echo "FAIL toolchain: gradle not found (brew install gradle)"; exit 2; }
echo "toolchain: $(javac -version 2>&1) | $(mvn -v 2>/dev/null | head -1) | $(gradle -v 2>/dev/null | grep -E '^Gradle')"

WORK="$(mktemp -d "${TMPDIR:-/tmp}/archetype-java.XXXXXX")"
cleanup() { [ "$KEEP" = 1 ] && echo "kept: $WORK" || rm -rf "$WORK"; }
trap cleanup EXIT

python3 "$HERE/harness.py" layout "$WORK" || exit 2

# ── 3. Java units: one reactor build ──
echo "maven: test-compile (log: $WORK/maven.log)"
( cd "$WORK" && mvn -B -T 1C --fail-at-end test-compile ) > "$WORK/maven.log" 2>&1
python3 "$HERE/harness.py" report "$WORK" "$WORK/maven.log"
RC=$?

# ── 4. build snippets ──
FAILS=0
snippet_result() {  # name status detail
  if [ "$2" = PASS ]; then printf 'PASS  %-34s %s\n' "$1" "$3"; else printf 'FAIL  %-34s %s\n' "$1" "$3"; FAILS=$((FAILS + 1)); fi
}

check_layers_idx() { python3 "$HERE/harness.py" check-layers "$1"; }

otel_maven_check() {  # module dir → FAIL if dependency management downgrades the OTel API the starter needs
  ( cd "$1" && mvn -B -q dependency:tree -Dverbose -Dincludes=io.opentelemetry:opentelemetry-api \
      -DoutputFile="$1/otel-tree.txt" ) >/dev/null 2>&1
  python3 "$HERE/harness.py" check-otel maven "$1/otel-tree.txt"
}

python3 - "$WORK/snippets.json" <<'PY' > "$WORK/snippets.tsv"
import json, sys
for s in json.load(open(sys.argv[1])):
    print("\t".join([s["name"], s["dir"], s["goal"], s["verify"] or "-"]))
PY
while IFS=$'\t' read -r name dir goal verify; do
  detail="resolves"
  if grep -qE "^\[INFO\] $name \.+ ?(FAILURE|SKIPPED)" "$WORK/maven.log"; then
    snippet_result "$name" FAIL "does not build (see the Maven errors above)"; continue
  fi
  if [ "$goal" = package ]; then
    if ! ( cd "$dir" && mvn -B package -DskipTests ) > "$dir/package.log" 2>&1; then
      snippet_result "$name" FAIL "mvn package failed ($dir/package.log)"; continue
    fi
    if grep -q "is unknown for plugin" "$dir/package.log"; then
      snippet_result "$name" FAIL "$(grep -m1 'is unknown for plugin' "$dir/package.log")"; continue
    fi
    detail="packages"
  elif [ "$goal" = verify ]; then   # runs the probe's tests too (e.g. a coverage gate)
    if ! ( cd "$dir" && mvn -B verify ) > "$dir/verify.log" 2>&1; then
      snippet_result "$name" FAIL "mvn verify failed: $(grep -m1 -E '\[(ERROR|WARNING)\].*(Rule violated|Unsupported|coverage|BUILD)' "$dir/verify.log" | cut -c1-200) ($dir/verify.log)"; continue
    fi
    detail="mvn verify ok"
  fi
  case "$verify" in
    layers-idx) if ! detail="$(check_layers_idx "$(ls "$dir"/target/*.jar | head -1)")"; then snippet_result "$name" FAIL "$detail"; continue; fi ;;
    otel-api-version) if ! detail="$(otel_maven_check "$dir")"; then snippet_result "$name" FAIL "$detail"; continue; fi ;;
  esac
  snippet_result "$name" PASS "$detail"
done < "$WORK/snippets.tsv"

python3 - "$WORK/gradle.json" <<'PY' > "$WORK/gradle.tsv"
import json, sys
for g in json.load(open(sys.argv[1])):
    print("\t".join([g["name"], g["dir"], " ".join(g["tasks"]), g["verify"] or "-"]))
PY
while IFS=$'\t' read -r name dir tasks verify; do
  # shellcheck disable=SC2086
  if ! ( cd "$dir" && gradle --no-daemon --console=plain -q $tasks ) > "$dir/gradle.log" 2>&1; then
    snippet_result "$name" FAIL "gradle $tasks failed: $(grep -m1 -E 'error|What went wrong|Exception' -A2 "$dir/gradle.log" | tr '\n' ' ' | cut -c1-220)"
    continue
  fi
  detail="gradle $tasks ok"
  case "$verify" in
    layers-idx) if ! detail="$(check_layers_idx "$(ls "$dir"/build/libs/*.jar | grep -v plain | head -1)")"; then snippet_result "$name" FAIL "$detail"; continue; fi ;;
    otel-api-version)
      ( cd "$dir" && gradle --no-daemon --console=plain -q dependencyInsight --dependency io.opentelemetry:opentelemetry-api \
          --configuration runtimeClasspath ) > "$dir/otel-insight.txt" 2>&1
      if ! extra="$(python3 "$HERE/harness.py" check-otel gradle "$dir/otel-insight.txt")"; then
        snippet_result "$name" FAIL "$extra"; continue
      fi
      detail="$detail; $extra" ;;
  esac
  snippet_result "$name" PASS "$detail"
done < "$WORK/gradle.tsv"

INV="$(python3 "$HERE/harness.py" inventory | tail -1)"
echo "────────────────────────────────────────────"
echo "$INV"
if [ "$RC" -eq 0 ] && [ "$FAILS" -eq 0 ]; then echo "ALL JAVA SAMPLES COMPILE (archetypes + skill packs)"; exit 0; fi
echo "FAILURES: Java units $([ "$RC" -eq 0 ] && echo ok || echo failed), build snippets failed: $FAILS"
exit 1
