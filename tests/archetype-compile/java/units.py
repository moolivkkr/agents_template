"""How every Java block in .claude/skills/backend/archetypes/*.md is compiled (read by harness.py).

Block ids are "<file>.md#<n>", n = 1-based index among that file's ```java blocks. Other fenced
languages use "<file>.md#<lang><n>" (e.g. "grpc-pattern.md#protobuf2", "dockerfile-java.md#kotlin1").

Layout specs (default for a block not listed in BLOCKS: File()):
  File        the block is one or more complete top-level types; each type becomes its own .java file.
              A block without a `package` line needs File(package=...), and the imports it assumes.
  Members     fields/methods (an excerpt of a class) wrapped in a harness class. `inject` declares the
              collaborators the excerpt uses without declaring (a repository field, a logger).
  Statements  statements wrapped in a harness method (`method` is its signature, parameters = the
              excerpt's free variables).
  Into        a class-body excerpt inserted into another block's class (nested test classes).
  Split       a block mixing those; each part starts at the first line matching its regex.
  Skip        not compiled, with the reason. Only for blocks with no code to compile.

Rules the specs follow: the harness may add imports and declarations to an EXCERPT (a block with no
`package` line) — but never to a block presented as a complete file, whose missing imports/fields are doc
bugs to fix in the markdown. Stubs (stubs/<dir>/{main,test}/...) define APPLICATION types the samples use
but no archetype defines (OrderRepository, PaymentClient, ...). No stub defines a library type.
"""
from dataclasses import dataclass, field

A = ".claude/skills/backend/archetypes"


@dataclass
class File:
    package: str = None
    imports: tuple = ()
    test: bool = False
    only: tuple = ()          # keep only these top-level types (when the rest collides in a unit)
    transforms: tuple = ()    # "elide": `{ ... }` → `{ }`; "stub_bodies": comment-only method bodies → throw


@dataclass
class Members:
    cls: str
    package: str
    imports: tuple = ()
    test: bool = False
    inject: tuple = ()
    extends: str = None
    implements: str = None
    annotations: tuple = ()
    abstract: bool = False
    interface: bool = False
    transforms: tuple = ()


@dataclass
class Statements(Members):
    method: str = "void run() throws Exception"


@dataclass
class Into:
    host: str
    imports: tuple = ()
    transforms: tuple = ()
    test: bool = False


@dataclass
class Split:
    parts: list
    transforms: tuple = ()


@dataclass
class Unit:
    name: str
    own: list                 # blocks this unit is responsible for (each block is owned exactly once)
    deps: list = field(default_factory=list)   # blocks from other files compiled alongside (id or (id, spec))
    stubs: tuple = ()
    pom_extra: str = ""
    protos: tuple = ()        # (block id, path under src/main/protobuf)


@dataclass
class MavenSnippet:
    name: str
    pom: str                  # @SNIPPET@ is replaced by the block
    probe_java: str = ""
    goal: str = "test-compile"   # "package" runs as its own Maven invocation after the reactor
    verify: str = ""          # run.sh check after the build (see run.sh)
    tool: str = "maven"


@dataclass
class GradleSnippet:  # the snippet is merged into gradle/<template>/<build_file> (@PLUGINS@, @SNIPPET@)
    name: str
    template: str             # directory under gradle/
    build_file: str
    tasks: tuple
    protos: tuple = ()        # (block id, path under src/main/proto)
    verify: str = ""
    tool: str = "gradle"


def ids(md, *nums):
    return [f"{md}#{n}" for n in nums]


def rng(md, lo, hi):
    return ids(md, *range(lo, hi + 1))


SKIP = {}
BLOCKS = {}

# Expected ```java block count per file — a mismatch means the doc changed: re-map it here.
JAVA_BLOCKS = {
    "auth-middleware-java.md": 10,
    "crud-handler-java.md": 9,
    "crud-handler-test-java.md": 11,
    "crud-repository-java.md": 10,
    "crud-repository-test-java.md": 13,
    "crud-service-java.md": 8,
    "crud-service-test-java.md": 10,
    "error-handling-java.md": 6,
    "grpc-pattern-java.md": 7,
    "migration-pattern-java.md": 3,
    "observability-java.md": 17,
    "performance-java.md": 26,
    "websocket-pattern-java.md": 7,
    "worker-pattern-java.md": 8,
}

# ── shared building blocks of the Widget CRUD chain ───────────────────────────────────────────────
EH = "error-handling-java.md"
REPO = "crud-repository-java.md"
HANDLER = "crud-handler-java.md"
SERVICE = "crud-service-java.md"
AUTH = "auth-middleware-java.md"

EXCEPTIONS = ids(EH, 1, 2)                 # FieldError, DomainException + its subclasses
ERROR_WRITER = ids(EH, 3, 4)               # GlobalExceptionHandler, SecurityErrorDelegate
ENTITY = ids(REPO, 1, 2)                   # AuditableEntity, Widget, WidgetStatus
REPOSITORY = ids(REPO, 3, 4)               # WidgetRepository, WidgetSpecs
DTO = ids(HANDLER, 2)                      # Create/UpdateWidgetRequest, WidgetResponse
ENVELOPE = ids(HANDLER, 3, 4)              # ApiResponse/ResponseMeta/Pagination, CursorCodec
CONTROLLER = ids(HANDLER, 5, 6)            # WidgetController, RequestIdFilter
SANITIZER = ids(HANDLER, 8)
SERVICE_API = ids(SERVICE, 1)
SERVICE_IMPL = ids(SERVICE, 2, 4)          # WidgetServiceImpl, AuditService

S = "static "

# ── error-handling-java.md ──
BLOCKS[f"{EH}#2"] = File(package="com.example.app.exception",
                         imports=("org.springframework.http.HttpStatus", "java.util.List"))
SKIP[f"{EH}#5"] = "comment-only: the wrapping rules as prose (every line is a // comment)"
BLOCKS[f"{EH}#6"] = File(package="com.example.app.controller", test=True, imports=(
    "com.example.app.exception.ConflictException", "com.example.app.exception.ResourceNotFoundException",
    "com.example.app.service.WidgetService", "com.example.app.config.SecurityConfig",
    "com.example.app.security.SecurityErrorDelegate", "com.example.app.security.UserPrincipal",
    "org.junit.jupiter.api.Test", "org.springframework.beans.factory.annotation.Autowired",
    "org.springframework.context.annotation.Import", "org.springframework.test.context.TestPropertySource",
    "org.springframework.security.core.authority.SimpleGrantedAuthority", "java.util.List",
    S + "org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.user",
    "org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest",
    "org.springframework.http.MediaType",
    "org.springframework.test.context.bean.override.mockito.MockitoBean",
    "org.springframework.test.web.servlet.MockMvc", "java.util.UUID",
    S + "org.hamcrest.Matchers.containsString", S + "org.hamcrest.Matchers.not",
    S + "org.mockito.ArgumentMatchers.any", S + "org.mockito.BDDMockito.given",
    S + "org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*",
    S + "org.springframework.test.web.servlet.result.MockMvcResultMatchers.*"))

# ── crud-repository-java.md ──
_ENT = ("com.example.app.model.entity.Widget", "com.example.app.model.entity.WidgetStatus")
BLOCKS[f"{REPO}#5"] = Members(
    cls="WidgetSearchExample", package="com.example.app.service", implements="WidgetSearch",
    imports=_ENT + ("com.example.app.repository.WidgetRepository", "com.example.app.repository.WidgetSpecs",
                    "org.springframework.data.domain.ScrollPosition", "org.springframework.data.domain.Sort",
                    "org.springframework.data.domain.Window", "org.slf4j.MDC", "java.time.Instant", "java.util.UUID"),
    inject=("private static final org.slf4j.Logger log = org.slf4j.LoggerFactory.getLogger(WidgetSearchExample.class);",
            "private WidgetRepository repository;"))
BLOCKS[f"{REPO}#6"] = Statements(
    cls="ScrollExample", package="com.example.app.service",
    method="void run(WidgetRepository repository, Sort.Direction direction, String sortBy, String cursor, "
           "UUID tenantId, WidgetStatus status, int limit)",
    imports=_ENT + ("com.example.app.common.CursorCodec", "com.example.app.repository.WidgetRepository",
                    "com.example.app.repository.WidgetSpecs", "org.springframework.data.domain.Sort",
                    "org.springframework.data.domain.Window", "java.util.UUID"))
BLOCKS[f"{REPO}#7"] = File(package="sample.repo.b7", transforms=("elide",), imports=(
    "org.hibernate.annotations.SQLDelete", "org.hibernate.annotations.SQLRestriction",
    "com.example.app.model.entity.AuditableEntity"))
BLOCKS[f"{REPO}#8"] = Members(cls="VersionField", package="sample.repo.b8", imports=("jakarta.persistence.Version",))
BLOCKS[f"{REPO}#9"] = Split([
    (None, Members(cls="TenantScopedQueries", package="com.example.app.repository", interface=True,
                   imports=("com.example.app.model.entity.Widget", "org.springframework.data.domain.ScrollPosition",
                            "org.springframework.data.domain.Window", "java.util.Optional", "java.util.UUID"))),
    (r"^// Option 2", File(package="sample.repo.b9", transforms=("elide",), imports=(
        "jakarta.persistence.Entity", "org.hibernate.annotations.Filter", "org.hibernate.annotations.FilterDef",
        "org.hibernate.annotations.ParamDef", "com.example.app.model.entity.AuditableEntity", "java.util.UUID"))),
    (r"^// Enable the filter", File(package="sample.repo.b9", imports=(
        "jakarta.persistence.EntityManager", "org.hibernate.Session",
        "org.springframework.stereotype.Component", "java.util.UUID"))),
])
BLOCKS[f"{REPO}#10"] = Split([
    (None, File(package="com.example.app.repository",
                imports=("com.example.app.model.entity.WidgetStatus", "java.time.Instant", "java.util.UUID"))),
    (r"^// In repository", Members(
        cls="WidgetSummaryQueries", package="com.example.app.repository", interface=True,
        extends="org.springframework.data.jpa.repository.JpaRepository<Widget, UUID>",
        imports=("com.example.app.model.entity.Widget", "com.example.app.model.dto.WidgetStats",
                 "org.springframework.data.domain.ScrollPosition", "org.springframework.data.domain.Window",
                 "org.springframework.data.jpa.repository.Query", "org.springframework.data.repository.query.Param",
                 "java.util.List", "java.util.UUID"))),
    (r"^public record WidgetStats", File(package="com.example.app.model.dto",
                                         imports=("com.example.app.model.entity.WidgetStatus", "java.time.Instant"))),
])

# ── crud-handler-test / crud-service-test / crud-repository-test: nested test classes go into the host ──
for n in range(2, 12):
    BLOCKS[f"crud-handler-test-java.md#{n}"] = Into("crud-handler-test-java.md#1")
BLOCKS["crud-handler-test-java.md#1"] = File(test=True)
BLOCKS["crud-service-test-java.md#1"] = File(test=True)
BLOCKS["crud-service-test-java.md#2"] = File(test=True)
for n in range(3, 11):
    BLOCKS[f"crud-service-test-java.md#{n}"] = Into("crud-service-test-java.md#2")
BLOCKS["crud-repository-test-java.md#1"] = File(test=True)
BLOCKS["crud-repository-test-java.md#2"] = File(test=True)
for n in range(3, 14):
    BLOCKS[f"crud-repository-test-java.md#{n}"] = Into("crud-repository-test-java.md#2")

# ── crud-service-java.md ──
_SVC = ("com.example.app.common.Sanitizer", "com.example.app.repository.WidgetRepository", "org.slf4j.MDC",
        "org.springframework.transaction.annotation.Transactional", "java.time.Instant", "java.util.UUID") + _ENT
BLOCKS[f"{SERVICE}#3"] = Members(
    cls="WidgetComponentsExample", package="com.example.app.service", imports=_SVC,
    inject=("private static final org.slf4j.Logger log = org.slf4j.LoggerFactory.getLogger(WidgetComponentsExample.class);",
            "private WidgetRepository repository;", "private WidgetComponentRepository componentRepository;",
            "private AuditService auditService;"))
SKIP[f"{SERVICE}#6"] = "comment-only: the exception-to-status table as // comments"
BLOCKS[f"{SERVICE}#7"] = Members(
    cls="WidgetValidationExample", package="com.example.app.service",
    imports=("com.example.app.exception.BusinessRuleException", "com.example.app.model.dto.CreateWidgetRequest",
             "com.example.app.repository.WidgetRepository", "java.util.UUID"),
    inject=("private WidgetRepository repository;",))
BLOCKS[f"{SERVICE}#8"] = Split([
    (None, File()),
    (r"^// In service:", Members(
        cls="WidgetEventPublishingExample", package="com.example.app.service",
        imports=("com.example.app.event.WidgetEvent", "com.example.app.model.dto.CreateWidgetRequest",
                 "com.example.app.model.entity.Widget", "org.springframework.context.ApplicationEventPublisher",
                 "org.springframework.transaction.annotation.Transactional"),
        inject=("private ApplicationEventPublisher applicationEventPublisher;",
                "private Widget widget; // built by the part the excerpt elides (// ... create widget ...)"))),
])

# ── auth-middleware-java.md ──
BLOCKS[f"{AUTH}#4"] = File(transforms=("stub_bodies",))   # @PreAuthorize placement sketch: bodies are `// ...`
BLOCKS[f"{AUTH}#10"] = Members(
    cls="CorsSecurityConfigExample", package="com.example.app.config",
    imports=("org.springframework.context.annotation.Bean",
             "org.springframework.security.config.annotation.web.builders.HttpSecurity",
             "org.springframework.security.config.http.SessionCreationPolicy",
             "org.springframework.security.web.SecurityFilterChain",
             "org.springframework.web.cors.CorsConfigurationSource"))

# ── observability-java.md ──
OBS = "observability-java.md"
BLOCKS[f"{OBS}#4"] = Split([
    (None, File(package="sample.obs.b4", imports=(
        "java.util.concurrent.CompletableFuture", "java.util.concurrent.Executor", "java.util.function.Supplier"))),
    (r"^// Usage", Members(
        cls="EnrichmentExample", package="sample.obs.b4",
        imports=("com.example.app.service.*", "io.opentelemetry.instrumentation.annotations.WithSpan",
                 "java.util.concurrent.CompletableFuture", "java.util.concurrent.Executor"),
        inject=("private CustomerClient customerClient;", "private ShippingClient shippingClient;",
                "private Executor taskExecutor;"))),
])
BLOCKS[f"{OBS}#9"] = Members(
    cls="PaymentTimingExample", package="sample.obs.b9",
    imports=("com.example.app.service.PaymentGateway", "com.example.app.service.PaymentRequest",
             "io.micrometer.core.instrument.MeterRegistry"),
    inject=("private MeterRegistry meterRegistry;", "private PaymentGateway paymentGateway;"))
BLOCKS[f"{OBS}#11"] = Statements(
    cls="ResponseSizeExample", package="sample.obs.b11",
    method="void record(MeterRegistry meterRegistry, String routeTemplate, byte[] responseBody)",
    imports=("io.micrometer.core.instrument.MeterRegistry",))

# ── performance-java.md ──
PERF = "performance-java.md"
_P = "sample.perf.*"
BLOCKS[f"{PERF}#2"] = Members(cls="WebClientConfig", package="sample.perf.b2",
                              imports=("java.time.Duration", "org.springframework.context.annotation.Bean"))
BLOCKS[f"{PERF}#4"] = Split([
    (None, Members(cls="SumBad", package="sample.perf.b4", imports=("java.util.List", _P))),
    (r"^// GOOD", Members(cls="SumGood", package="sample.perf.b4", imports=("java.util.List", _P))),
])
BLOCKS[f"{PERF}#5"] = Split([
    (None, Members(cls="ReportBad", package="sample.perf.b5", imports=("java.util.List", _P))),
    (r"^// GOOD", Members(cls="ReportGood", package="sample.perf.b5", imports=("java.util.List", _P))),
])
BLOCKS[f"{PERF}#6"] = File(package="sample.perf.b6", imports=("java.time.Duration", _P))
BLOCKS[f"{PERF}#7"] = File(package="sample.perf.b7")
BLOCKS[f"{PERF}#8"] = Members(
    cls="OrderImporter", package="sample.perf.b8",
    imports=("jakarta.persistence.EntityManager", "org.springframework.transaction.annotation.Transactional",
             "java.util.List", _P),
    inject=("private EntityManager entityManager;",))
BLOCKS[f"{PERF}#9"] = Members(cls="OrderIdMapping", package="sample.perf.b9", imports=("jakarta.persistence.*",))
BLOCKS[f"{PERF}#10"] = File(package="sample.perf.b10", imports=(
    "org.springframework.data.jpa.repository.EntityGraph", "org.springframework.data.jpa.repository.JpaRepository",
    "java.util.List", "java.util.Optional", "java.util.UUID", _P))
BLOCKS[f"{PERF}#11"] = File(package="sample.perf.b11", imports=("jakarta.persistence.*", "java.util.List", _P))
_B12 = ("org.springframework.data.domain.*", "org.springframework.data.jpa.repository.JpaRepository",
        "org.springframework.data.jpa.repository.Query", "org.springframework.data.repository.query.Param",
        "com.example.app.dto.OrderListItem", "java.math.BigDecimal", "java.time.Instant", "java.util.List",
        "java.util.UUID", _P)
BLOCKS[f"{PERF}#12"] = File(package="sample.perf.b12", imports=_B12)
BLOCKS[f"{PERF}#14"] = Members(
    cls="ReadReplicaExample", package="sample.perf.b12",
    imports=_B12 + ("org.springframework.stereotype.Service",
                    "org.springframework.transaction.annotation.Transactional"),
    inject=("private OrderRepository orderRepository;",))
BLOCKS[f"{PERF}#15"] = File(package="sample.perf.b15", imports=(
    "jakarta.persistence.*", "org.hibernate.annotations.Cache", "org.hibernate.annotations.CacheConcurrencyStrategy",
    "java.math.BigDecimal", "java.util.UUID"))
BLOCKS[f"{PERF}#16"] = File(package="sample.perf.b16", imports=(
    "jakarta.persistence.EntityManager", "jakarta.persistence.PersistenceContext", "org.hibernate.Session",
    "org.hibernate.SessionFactory", "org.hibernate.stat.Statistics", "org.slf4j.Logger", "org.slf4j.LoggerFactory",
    "org.springframework.context.annotation.Profile", "org.springframework.scheduling.annotation.Scheduled",
    "org.springframework.stereotype.Component"))
_CLIENTS = ("private OrderLookup orderRepository;", "private CustomerClient customerClient;",
            "private ShippingClient shippingClient;", "private InventoryClient inventoryClient;")
BLOCKS[f"{PERF}#17"] = Members(
    cls="VirtualThreadsExample", package="sample.perf.b17",
    imports=("org.springframework.web.bind.annotation.*", "java.util.UUID", _P), inject=_CLIENTS)
BLOCKS[f"{PERF}#18"] = Members(
    cls="StructuredConcurrencyExample", package="sample.perf.b18", imports=("java.util.UUID", _P), inject=_CLIENTS)
BLOCKS[f"{PERF}#19"] = Members(
    cls="EnrichmentExample", package="sample.perf.b19",
    imports=("org.springframework.stereotype.Service", "java.util.concurrent.CompletableFuture",
             "java.util.concurrent.Executor", "java.util.concurrent.TimeUnit", _P),
    inject=_CLIENTS + ("private static final org.slf4j.Logger log = "
                       "org.slf4j.LoggerFactory.getLogger(EnrichmentExample.class);",))
BLOCKS[f"{PERF}#21"] = Statements(
    cls="ExecutorsExample", package="sample.perf.b21",
    imports=("java.util.concurrent.ExecutorService", "java.util.concurrent.Executors"))
_PRODUCTS = ("private ProductRepository productRepository;",
             "private static final org.slf4j.Logger log = org.slf4j.LoggerFactory.getLogger(Object.class);")
BLOCKS[f"{PERF}#23"] = Members(
    cls="ProductCacheExample", package="sample.perf.b23",
    imports=("com.example.app.exception.ResourceNotFoundException", "org.springframework.cache.annotation.*",
             "org.springframework.stereotype.Service", "java.util.UUID", _P),
    inject=_PRODUCTS)
BLOCKS[f"{PERF}#24"] = Members(
    cls="ProductCacheSyncExample", package="sample.perf.b24",
    imports=("org.springframework.cache.annotation.Cacheable", "java.util.UUID", _P), inject=_PRODUCTS)
BLOCKS[f"{PERF}#26"] = File(package="sample.perf.b26", imports=(
    "com.github.benmanes.caffeine.cache.Cache", "com.github.benmanes.caffeine.cache.Caffeine",
    "org.springframework.data.redis.core.RedisTemplate", "org.springframework.stereotype.Service",
    "java.time.Duration", "java.util.function.Function"))

# ── grpc-pattern-java.md ──
GRPC = "grpc-pattern-java.md"
_G = ("com.example.yourapp.v1.*", "io.grpc.stub.StreamObserver", "java.util.UUID",
      "org.slf4j.Logger", "org.slf4j.LoggerFactory")
BLOCKS[f"{GRPC}#2"] = Members(
    cls="WatchWidgetsExample", package="com.example.app.grpc", extends="WidgetServiceGrpc.WidgetServiceImplBase",
    imports=_G + ("io.grpc.Context", "com.google.common.util.concurrent.MoreExecutors"),
    inject=("private static final Logger log = LoggerFactory.getLogger(WatchWidgetsExample.class);",
            "private WidgetEventSource widgetService;",
            "private WidgetEvent toEventProto(Object event) { return WidgetEvent.getDefaultInstance(); }"))
# client streaming: a method of WidgetGrpcService (it uses that class's create(...) helper and logger)
BLOCKS[f"{GRPC}#3"] = Into(f"{GRPC}#1", imports=(
    "com.example.app.exception.DomainException", "java.util.ArrayList", "java.util.List"))

GRPC_POM = """  <build>
    <plugins>
      <plugin>
        <groupId>io.github.ascopes</groupId>
        <artifactId>protobuf-maven-plugin</artifactId>
        <configuration>
          <protoc kind="binary-maven"><version>${protobuf-java.version}</version></protoc>
          <plugins>
            <plugin kind="binary-maven">
              <groupId>io.grpc</groupId>
              <artifactId>protoc-gen-grpc-java</artifactId>
              <version>${grpc-java.version}</version>
            </plugin>
          </plugins>
        </configuration>
        <executions><execution><goals><goal>generate</goal></goals></execution></executions>
      </plugin>
    </plugins>
  </build>"""
PROTOS = (("grpc-pattern.md#protobuf1", "yourapp/v1/widget_service.proto"),
          ("grpc-pattern.md#protobuf2", "yourapp/v1/widget.proto"),
          ("grpc-pattern.md#protobuf3", "yourapp/v1/common.proto"))

PREVIEW_POM = """  <build>
    <plugins>
      <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-compiler-plugin</artifactId>
        <configuration>
          <compilerArgs combine.children="append"><arg>--enable-preview</arg></compilerArgs>
        </configuration>
      </plugin>
    </plugins>
  </build>"""

# ── units ──────────────────────────────────────────────────────────────────────────────────────────
UNITS = [
    Unit("error-handling-java", own=ids(EH, 1, 2, 3, 4, 6),
         deps=ENTITY + DTO + ENVELOPE + CONTROLLER + SERVICE_API + ids(AUTH, 1, 2, 3)),
    Unit("crud-repository-java", own=rng(REPO, 1, 10), deps=EXCEPTIONS + ENVELOPE, stubs=("crud-repository",)),
    Unit("crud-handler-java-entity", own=ids(HANDLER, 1),
         deps=[(f"{REPO}#2", File(only=("WidgetStatus",)))]),
    Unit("crud-handler-java", own=rng(HANDLER, 2, 9), deps=EXCEPTIONS + ENTITY + SERVICE_API),
    Unit("crud-service-java", own=ids(SERVICE, 1, 2, 3, 4, 5, 7, 8),
         deps=EXCEPTIONS + ENTITY + REPOSITORY + DTO + SANITIZER, stubs=("crud-service",)),
    Unit("crud-handler-test-java", own=rng("crud-handler-test-java.md", 1, 11),
         deps=EXCEPTIONS + ERROR_WRITER + ENTITY + DTO + ENVELOPE + CONTROLLER + SERVICE_API + ids(AUTH, 1, 2, 3),
         stubs=()),
    Unit("crud-service-test-java", own=rng("crud-service-test-java.md", 1, 10),
         deps=EXCEPTIONS + ENTITY + REPOSITORY + DTO + SANITIZER + SERVICE_API + SERVICE_IMPL, stubs=("crud-service",)),
    Unit("crud-repository-test-java", own=rng("crud-repository-test-java.md", 1, 13), deps=ENTITY + REPOSITORY),
    Unit("auth-middleware-java", own=rng(AUTH, 1, 10),
         deps=EXCEPTIONS + ERROR_WRITER + ENTITY + REPOSITORY + DTO, stubs=("auth",)),
    Unit("observability-java", own=ids(OBS, 1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13, 15, 16, 17),
         stubs=("observability",)),
    Unit("observability-java-timed", own=ids(OBS, 7), stubs=("observability",)),
    Unit("observability-java-mdc", own=ids(OBS, 14), stubs=("observability",)),
    Unit("performance-java", own=[b for b in rng(PERF, 1, 26) if b != f"{PERF}#18"], deps=EXCEPTIONS,
         stubs=("performance",)),
    Unit("performance-java-preview", own=ids(PERF, 18), stubs=("performance",), pom_extra=PREVIEW_POM),
    Unit("websocket-pattern-java", own=rng("websocket-pattern-java.md", 1, 7), deps=ids(AUTH, 3),
         stubs=("websocket",)),
    Unit("worker-pattern-java", own=rng("worker-pattern-java.md", 1, 8), stubs=("worker",)),
    Unit("grpc-pattern-java", own=rng(GRPC, 1, 7), deps=EXCEPTIONS + ENTITY + DTO + ENVELOPE + SERVICE_API,
         stubs=("grpc",), pom_extra=GRPC_POM, protos=PROTOS),
    Unit("migration-pattern-java", own=rng("migration-pattern-java.md", 1, 3),
         deps=["crud-repository-test-java.md#1"]),
]
BLOCKS["migration-pattern-java.md#3"] = File(test=True)

# ── JVM build/config blocks ────────────────────────────────────────────────────────────────────────
BOOT_POM = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>4.1.1</version>
    <relativePath/>
  </parent>
  <groupId>archetype.compile</groupId>
  <artifactId>@NAME@</artifactId>
  <version>0</version>
  <name>@NAME@</name>
  <properties><java.version>25</java.version></properties>
@BODY@
</project>
"""


def boot_pom(name, body):
    return BOOT_POM.replace("@NAME@", name).replace("@BODY@", body)


BUILD_SNIPPETS = {
    f"{OBS}#xml1": MavenSnippet(
        name="observability-maven-deps",
        pom=boot_pom("observability-maven-deps", "@SNIPPET@"),
        probe_java="package snippet;\n"
                   "import io.opentelemetry.instrumentation.annotations.WithSpan;\n"
                   "import io.micrometer.registry.otlp.OtlpMeterRegistry;\n"
                   "import net.logstash.logback.encoder.LogstashEncoder;\n"
                   "class Probe { @WithSpan void traced() {} OtlpMeterRegistry r; LogstashEncoder e; }\n",
        verify="otel-api-version"),
    "dockerfile-java.md#xml1": MavenSnippet(
        name="dockerfile-maven-layers", goal="package",
        pom=boot_pom("dockerfile-maven-layers", "  <build>\n    <plugins>\n@SNIPPET@\n    </plugins>\n  </build>"),
        probe_java="package snippet;\n\npublic class Probe { public static void main(String[] a) {} }\n",
        verify="layers-idx"),
    f"{OBS}#kotlin1": GradleSnippet(
        name="observability-gradle-deps", template="deps-kts", build_file="build.gradle.kts",
        tasks=("compileJava",), verify="otel-api-version"),
    "dockerfile-java.md#kotlin1": GradleSnippet(
        name="dockerfile-gradle-layers", template="bootjar-kts", build_file="build.gradle.kts",
        tasks=("bootJar",), verify="layers-idx"),
    "dockerfile-java.md#kotlin2": GradleSnippet(
        name="dockerfile-gradle-native", template="native-kts", build_file="build.gradle.kts",
        tasks=("nativeCompile", "--dry-run")),
    f"{GRPC}#groovy1": GradleSnippet(
        name="grpc-gradle-codegen", template="grpc-groovy", build_file="build.gradle",
        tasks=("compileJava",), protos=PROTOS),
}
SKIP[f"{OBS}#xml2"] = ("logback-spring.xml is runtime logging config, not a build file; its <springProfile> tags "
                       "need Spring Boot's LoggingSystem, so this harness does not load it. (Loaded once on 2026-09-30: "
                       "logback 1.5.38 + logstash-logback-encoder 9.0 took the production profile without warnings "
                       "and <decorator> redacted a structured `password` field.)")
SKIP[f"{PERF}#xml1"] = ("caffeine-cache.xml is runtime JCache config, not a build file. NOT verified, and likely "
                        "wrong: Caffeine's JCache provider is configured with Typesafe Config (application.conf), "
                        "not jsr107 XML")
SKIP[f"{PERF}#scala1"] = ("Gatling simulation (Scala), outside this Java harness. Not compiled. Reviewed by eye only: it "
                          "sends the tenant as an X-Tenant-ID header (the tenant comes from the verified token) and "
                          "reads $.id where the envelope puts it at $.data.id")
