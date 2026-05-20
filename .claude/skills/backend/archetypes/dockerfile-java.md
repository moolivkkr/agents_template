---
skill: dockerfile-java
description: Java/Spring Boot optimized Docker archetype — multi-stage build, layered JAR, JVM tuning, non-root user, actuator health check, GraalVM native-image variant
version: "1.0"
tags:
  - java
  - spring-boot
  - docker
  - dockerfile
  - archetype
  - backend
  - devops
---

# Dockerfile Archetype (Java / Spring Boot)

Complete, production-ready Docker build template for Spring Boot applications. Every generated Dockerfile MUST follow this pattern.

## Multi-Stage Dockerfile (Gradle)

```dockerfile
# ============================================================================
# Stage 1: Build — compile and package the application
# ============================================================================
FROM eclipse-temurin:21-jdk-alpine AS build

WORKDIR /app

# Copy Gradle wrapper and build files first (layer caching)
COPY gradlew gradlew
COPY gradle/ gradle/
COPY build.gradle.kts settings.gradle.kts ./

# Download dependencies (cached unless build files change)
RUN chmod +x gradlew && ./gradlew dependencies --no-daemon

# Copy source code
COPY src/ src/

# Build the application — skip tests (tests run in CI, not in Docker build)
RUN ./gradlew bootJar --no-daemon -x test

# ============================================================================
# Stage 2: Extract — Spring Boot layered JAR extraction for optimal caching
# ============================================================================
FROM eclipse-temurin:21-jdk-alpine AS extract

WORKDIR /app

COPY --from=build /app/build/libs/*.jar app.jar

# Extract Spring Boot layered JAR into separate directories
# Layers (from least to most frequently changing):
#   dependencies/         — third-party JARs (rarely change)
#   spring-boot-loader/   — Spring Boot loader (rarely changes)
#   snapshot-dependencies/ — SNAPSHOT JARs (change occasionally)
#   application/          — your code (changes every build)
RUN java -Djarmode=layertools -jar app.jar extract

# ============================================================================
# Stage 3: Runtime — minimal JRE image with layered application
# ============================================================================
FROM eclipse-temurin:21-jre-alpine AS runtime

# Security: create non-root user
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /app

# Copy layers in order of change frequency (most stable first)
# Docker caches each COPY as a layer — stable layers are reused across builds
COPY --from=extract /app/dependencies/ ./
COPY --from=extract /app/spring-boot-loader/ ./
COPY --from=extract /app/snapshot-dependencies/ ./
COPY --from=extract /app/application/ ./

# JVM configuration for containers
ENV JAVA_OPTS="\
    -XX:MaxRAMPercentage=75.0 \
    -XX:+UseG1GC \
    -XX:+UseContainerSupport \
    -XX:+ExitOnOutOfMemoryError \
    -Djava.security.egd=file:/dev/./urandom \
    -Dspring.profiles.active=prod"

# Application port
EXPOSE 8080

# Health check using Spring Boot Actuator
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/actuator/health || exit 1

# Run as non-root user
USER appuser

# Use exec form for proper signal handling (graceful shutdown)
ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS org.springframework.boot.loader.launch.JarLauncher"]
```

## Multi-Stage Dockerfile (Maven)

```dockerfile
# ============================================================================
# Stage 1: Build — compile with Maven
# ============================================================================
FROM eclipse-temurin:21-jdk-alpine AS build

WORKDIR /app

# Copy Maven wrapper and POM first (layer caching)
COPY mvnw mvnw
COPY .mvn/ .mvn/
COPY pom.xml ./

# Download dependencies (cached unless POM changes)
RUN chmod +x mvnw && ./mvnw dependency:go-offline -B

# Copy source code
COPY src/ src/

# Build — skip tests
RUN ./mvnw package -B -DskipTests

# ============================================================================
# Stage 2: Extract — layered JAR extraction
# ============================================================================
FROM eclipse-temurin:21-jdk-alpine AS extract

WORKDIR /app
COPY --from=build /app/target/*.jar app.jar
RUN java -Djarmode=layertools -jar app.jar extract

# ============================================================================
# Stage 3: Runtime
# ============================================================================
FROM eclipse-temurin:21-jre-alpine AS runtime

RUN addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /app

COPY --from=extract /app/dependencies/ ./
COPY --from=extract /app/spring-boot-loader/ ./
COPY --from=extract /app/snapshot-dependencies/ ./
COPY --from=extract /app/application/ ./

ENV JAVA_OPTS="\
    -XX:MaxRAMPercentage=75.0 \
    -XX:+UseG1GC \
    -XX:+UseContainerSupport \
    -XX:+ExitOnOutOfMemoryError \
    -Djava.security.egd=file:/dev/./urandom \
    -Dspring.profiles.active=prod"

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/actuator/health || exit 1

USER appuser

ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS org.springframework.boot.loader.launch.JarLauncher"]
```

## .dockerignore

```
# Build artifacts
build/
target/
*.jar
!gradle-wrapper.jar

# IDE files
.idea/
*.iml
.vscode/
*.swp

# Git
.git/
.gitignore

# CI/CD
.github/
.gitlab-ci.yml
Jenkinsfile

# Documentation
*.md
docs/
LICENSE

# Docker
Dockerfile*
docker-compose*.yml
.dockerignore

# OS files
.DS_Store
Thumbs.db

# Test artifacts
src/test/
*.test.ts
```

## JVM Memory Tuning

```dockerfile
# Container-aware JVM settings explanation:
#
# -XX:MaxRAMPercentage=75.0
#   Use 75% of container memory limit for JVM heap.
#   Leaves 25% for JVM metaspace, thread stacks, NIO buffers, and OS.
#   For 512MB container: ~384MB heap.
#   For 1GB container: ~768MB heap.
#
# -XX:+UseG1GC
#   G1 garbage collector — best default for most workloads.
#   Low-latency, good throughput, handles large heaps well.
#
# -XX:+UseContainerSupport
#   JVM detects container memory/CPU limits (default since JDK 10+).
#   Without this, JVM sees host machine resources instead of container limits.
#
# -XX:+ExitOnOutOfMemoryError
#   Kill the JVM on OOM instead of limping along.
#   Container orchestrator (K8s) will restart the pod.
#
# -Djava.security.egd=file:/dev/./urandom
#   Use non-blocking entropy source for faster startup.
#   Default /dev/random can block on low-entropy systems (containers).

# For memory-constrained environments (256MB containers):
ENV JAVA_OPTS="\
    -XX:MaxRAMPercentage=60.0 \
    -XX:+UseSerialGC \
    -XX:+UseContainerSupport \
    -XX:+ExitOnOutOfMemoryError \
    -Xss256k"

# For high-throughput services (2GB+ containers):
ENV JAVA_OPTS="\
    -XX:MaxRAMPercentage=75.0 \
    -XX:+UseZGC \
    -XX:+UseContainerSupport \
    -XX:+ExitOnOutOfMemoryError \
    -XX:+ZGenerational"
```

## Spring Boot Layered JAR Configuration

```kotlin
// build.gradle.kts — enable layered JARs (default in Spring Boot 3.x)
tasks.named<org.springframework.boot.gradle.tasks.bundling.BootJar>("bootJar") {
    layered {
        application {
            intoLayer("spring-boot-loader") {
                include("org/springframework/boot/loader/**")
            }
            intoLayer("application")
        }
        dependencies {
            intoLayer("snapshot-dependencies") {
                include("*:*:*SNAPSHOT")
            }
            intoLayer("dependencies")
        }
    }
}
```

```xml
<!-- pom.xml — enable layered JARs -->
<plugin>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-maven-plugin</artifactId>
    <configuration>
        <layers>
            <enabled>true</enabled>
        </layers>
    </configuration>
</plugin>
```

## Docker Compose Snippet

```yaml
# docker-compose.yml
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
      target: runtime        # Use specific stage
    ports:
      - "8080:8080"
    environment:
      SPRING_PROFILES_ACTIVE: local
      SPRING_DATASOURCE_URL: jdbc:postgresql://db:5432/appdb
      SPRING_DATASOURCE_USERNAME: app
      SPRING_DATASOURCE_PASSWORD: ${DB_PASSWORD}
      SPRING_REDIS_HOST: redis
      JAVA_OPTS: >-
        -XX:MaxRAMPercentage=75.0
        -XX:+UseG1GC
        -XX:+UseContainerSupport
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    deploy:
      resources:
        limits:
          memory: 512M        # JVM will use 75% = ~384MB heap
    healthcheck:
      test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:8080/actuator/health"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 60s
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: appdb
      POSTGRES_USER: app
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d appdb"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: ["redis-server", "--maxmemory", "128mb", "--maxmemory-policy", "allkeys-lru"]

volumes:
  pgdata:
```

## GraalVM Native Image Variant (Optional)

```dockerfile
# ============================================================================
# GraalVM Native Image — ultra-fast startup, lower memory
# Trade-off: longer build time, no JIT optimization at runtime
# ============================================================================

# Stage 1: Build native image
FROM ghcr.io/graalvm/native-image-community:21 AS native-build

WORKDIR /app

COPY gradlew gradlew
COPY gradle/ gradle/
COPY build.gradle.kts settings.gradle.kts ./

RUN chmod +x gradlew && ./gradlew dependencies --no-daemon

COPY src/ src/

# Build native image — requires Spring Boot AOT processing
RUN ./gradlew nativeCompile --no-daemon

# Stage 2: Minimal runtime (no JVM needed)
FROM alpine:3.19 AS native-runtime

RUN addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /app

# Copy the single native executable
COPY --from=native-build /app/build/native/nativeCompile/app ./app

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/actuator/health || exit 1

USER appuser

ENTRYPOINT ["./app"]

# Native image benefits:
# - Startup: ~50ms (vs ~2-5s for JVM)
# - Memory: ~50-100MB (vs ~256-512MB for JVM)
# - Image size: ~80MB (vs ~200-300MB with JRE)
#
# Native image trade-offs:
# - Build time: 5-15 minutes (vs 30-60s for JAR)
# - No JIT optimization — throughput may be lower for long-running workloads
# - Reflection/proxy must be configured via GraalVM hints
# - Spring Boot 3.x has excellent native support via spring-aot
```

## build.gradle.kts — Native Support

```kotlin
plugins {
    id("org.graalvm.buildtools.native") version "0.10.4"
}

graalvmNative {
    binaries {
        named("main") {
            buildArgs.add("--enable-url-protocols=http,https")
            buildArgs.add("-H:+ReportExceptionStackTraces")
        }
    }
}
```

## Actuator Health Configuration

```yaml
# application.yml — health check for Docker HEALTHCHECK and K8s probes
management:
  endpoints:
    web:
      exposure:
        include: health, info, prometheus
  endpoint:
    health:
      show-details: when-authorized
      probes:
        enabled: true              # enables /actuator/health/liveness and /readiness
  health:
    db:
      enabled: true
    redis:
      enabled: true
    diskSpace:
      enabled: true
```

## Critical Rules

- Multi-stage builds MANDATORY — build stage with JDK, runtime stage with JRE only.
- Layered JAR extraction MANDATORY — `java -Djarmode=layertools -jar app.jar extract` for optimal Docker layer caching.
- Copy layers in order of change frequency: dependencies -> spring-boot-loader -> snapshot-dependencies -> application.
- Non-root user MANDATORY — `adduser -S appuser` and `USER appuser` before ENTRYPOINT.
- `HEALTHCHECK` MANDATORY — use Spring Boot Actuator `/actuator/health` endpoint.
- `-XX:MaxRAMPercentage=75.0` instead of fixed `-Xmx` — automatically adapts to container memory limits.
- `-XX:+UseContainerSupport` — JVM respects container cgroup limits (default since JDK 10+ but explicit is safer).
- `-XX:+ExitOnOutOfMemoryError` — crash instead of limping, let orchestrator restart.
- Use `ENTRYPOINT` exec form with `sh -c` for `$JAVA_OPTS` expansion — never use shell form directly.
- `.dockerignore` MANDATORY — exclude build artifacts, tests, IDE files, Git history.
- `--no-daemon` for Gradle in Docker — daemon is wasteful in ephemeral build containers.
- `-DskipTests` in Docker build — tests run in CI, not during image build.
- `start-period` in HEALTHCHECK should be >= application startup time (60s for Spring Boot).
- Docker Compose `deploy.resources.limits.memory` should match JVM expectations.
- Never hardcode secrets in Dockerfile — use environment variables or mounted secrets.
- GraalVM native image is OPTIONAL — only use when startup time or memory is critical (serverless, CLI tools).
