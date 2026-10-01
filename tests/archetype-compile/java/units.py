"""How every Java block in .claude/skills is compiled (read by harness.py): the backend archetypes, then the other
skill packs (section "skill packs outside backend/archetypes" at the end).

Block ids are "<file>.md#<n>", n = 1-based index among that file's ```java blocks; an archetype is named by its file
name, any other pack by its path under .claude/skills ("languages/java.md#3"). Other fenced languages use
"<file>.md#<lang><n>" (e.g. "grpc-pattern.md#protobuf2", "dockerfile-java.md#kotlin1").

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
    pom: str = ""             # a whole module POM instead of the Spring Boot parent's (@NAME@ = the unit name)


@dataclass
class MavenSnippet:
    name: str
    pom: str                  # @SNIPPET@ is replaced by the block
    probe_java: str = ""
    probe_test: str = ""      # src/test/java/snippet/ProbeTest.java, for snippets that act on tests (coverage)
    goal: str = "test-compile"   # "package" / "verify" run as their own Maven invocation after the reactor
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
    files: tuple = ()         # (block id, path in the project): other doc blocks the build reads


def ids(md, *nums):
    return [f"{md}#{n}" for n in nums]


def rng(md, lo, hi):
    return ids(md, *range(lo, hi + 1))


SKIP = {}
BLOCKS = {}

# Expected ```java block count per file — a mismatch means the doc changed: re-map it here.
JAVA_BLOCKS = {
    "auth-middleware-java.md": 9,
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
    "websocket-pattern-java.md": 11,
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
BLOCKS[f"{AUTH}#9"] = Members(
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
         deps=ENTITY + DTO + ENVELOPE + CONTROLLER + SERVICE_API + ids(AUTH, 1, 2, 3, 8), stubs=("auth",)),
    Unit("crud-repository-java", own=rng(REPO, 1, 10), deps=EXCEPTIONS + ENVELOPE, stubs=("crud-repository",)),
    Unit("crud-handler-java-entity", own=ids(HANDLER, 1),
         deps=[(f"{REPO}#2", File(only=("WidgetStatus",)))]),
    Unit("crud-handler-java", own=rng(HANDLER, 2, 9), deps=EXCEPTIONS + ENTITY + SERVICE_API),
    Unit("crud-service-java", own=ids(SERVICE, 1, 2, 3, 4, 5, 7, 8),
         deps=EXCEPTIONS + ENTITY + REPOSITORY + DTO + SANITIZER, stubs=("crud-service",)),
    Unit("crud-handler-test-java", own=rng("crud-handler-test-java.md", 1, 11),
         deps=EXCEPTIONS + ERROR_WRITER + ENTITY + DTO + ENVELOPE + CONTROLLER + SERVICE_API + ids(AUTH, 1, 2, 3, 8),
         stubs=("auth",)),
    Unit("crud-service-test-java", own=rng("crud-service-test-java.md", 1, 10),
         deps=EXCEPTIONS + ENTITY + REPOSITORY + DTO + SANITIZER + SERVICE_API + SERVICE_IMPL, stubs=("crud-service",)),
    Unit("crud-repository-test-java", own=rng("crud-repository-test-java.md", 1, 13), deps=ENTITY + REPOSITORY),
    Unit("auth-middleware-java", own=rng(AUTH, 1, 9),
         deps=EXCEPTIONS + ERROR_WRITER + ENTITY + REPOSITORY + DTO, stubs=("auth",)),
    Unit("observability-java", own=ids(OBS, 1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13, 15, 16, 17),
         stubs=("observability",)),
    Unit("observability-java-timed", own=ids(OBS, 7), stubs=("observability",)),
    Unit("observability-java-mdc", own=ids(OBS, 14), stubs=("observability",)),
    Unit("performance-java", own=[b for b in rng(PERF, 1, 26) if b != f"{PERF}#18"], deps=EXCEPTIONS,
         stubs=("performance",)),
    Unit("performance-java-preview", own=ids(PERF, 18), stubs=("performance",), pom_extra=PREVIEW_POM),
    Unit("websocket-pattern-java", own=rng("websocket-pattern-java.md", 1, 11),
         deps=EXCEPTIONS + ENVELOPE + ids(AUTH, 3) + [(f"{EH}#3", File(only=("ErrorBody", "ApiError")))]),
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
SKIP[f"{PERF}#hocon1"] = ("Caffeine JCache config (Typesafe Config), runtime config rather than a build file; "
                          "not loaded here. (Loaded once on 2026-09-30: Hibernate 7.4.5 + Caffeine 3.2.4 jcache built the "
                          "products region with maximum size 1000 and expire-after-write 15m from it.)")
SKIP[f"{PERF}#scala1"] = ("Gatling simulation (Scala), outside this Java harness. Not compiled. Reviewed by eye only: it "
                          "sends the tenant as an X-Tenant-ID header (the tenant comes from the verified token) and "
                          "reads $.id where the envelope puts it at $.data.id")


# ═════════════════════════════ skill packs outside backend/archetypes ═════════════════════════════
# Block ids are "<path under .claude/skills>#<n>". Their ```java blocks are excerpts (no package line), so the
# specs give each a package and the imports it assumes; each pack's undefined application types are stubs.

# Java packs whose Kotlin/Groovy/XML blocks are build files too (checked or skipped like the *-java.md ones)
JVM_PACKS = {"languages/java.md", "frameworks/spring-boot.md", "frameworks/quarkus.md", "testing/junit-mockito.md"}

JAVA_BLOCKS.update({
    "languages/java.md": 22,
    "frameworks/spring-boot.md": 5,
    "frameworks/quarkus.md": 8,
    "testing/junit-mockito.md": 6,
    "testing/property-based.md": 1,
    "testing/contract-testing.md": 1,
    "testing/external-service-mocks.md": 1,
    "frameworks/graphql.md": 1,
})


def dep(group, artifact, version=None, scope=None):
    v = f"<version>{version}</version>" if version else ""
    sc = f"<scope>{scope}</scope>" if scope else ""
    return f"    <dependency><groupId>{group}</groupId><artifactId>{artifact}</artifactId>{v}{sc}</dependency>"


def deps_pom(*lines):
    return "  <dependencies>\n" + "\n".join(lines) + "\n  </dependencies>"


REST_TEST_CLIENT = dep("org.springframework.boot", "spring-boot-resttestclient", scope="test")
JJWT_RUNTIME = (dep("io.jsonwebtoken", "jjwt-impl", "${jjwt.version}", "test"),
                dep("io.jsonwebtoken", "jjwt-jackson", "${jjwt.version}", "test"))

# ── languages/java.md ── (package com.company.app, the pack's own project layout)
JM = "languages/java.md"
JP = "com.company.app"
_SPRING_MVC = ("org.springframework.web.bind.annotation.*", "org.springframework.http.HttpStatus")
_TX = ("org.springframework.stereotype.Service", "org.springframework.transaction.annotation.Transactional")
_U = ("java.util.List", "java.util.Optional", "java.util.UUID")
_JUNIT = ("org.junit.jupiter.api.Test", S + "org.assertj.core.api.Assertions.assertThat",
          S + "org.assertj.core.api.Assertions.assertThatThrownBy")
BLOCKS[f"{JM}#1"] = Split([   # the good and the bad UserService, side by side
    (None, File(package=f"{JP}.di.good", imports=("org.springframework.stereotype.Service", f"{JP}.UserRepository"))),
    (r"^// Bad", File(package=f"{JP}.di.bad", imports=(
        "org.springframework.stereotype.Service", "org.springframework.beans.factory.annotation.Autowired",
        f"{JP}.UserRepository"))),
])
BLOCKS[f"{JM}#2"] = File(package=JP, imports=("jakarta.validation.constraints.NotBlank",
                                              "jakarta.validation.constraints.Size"))
BLOCKS[f"{JM}#3"] = File(package=JP, imports=_TX + _SPRING_MVC + _U + (
    "org.springframework.stereotype.Repository", "org.springframework.cache.CacheManager",
    "org.springframework.data.jpa.repository.JpaRepository", "jakarta.validation.Valid"))
BLOCKS[f"{JM}#4"] = File(package=JP, imports=(
    "org.springframework.boot.context.properties.ConfigurationProperties", "java.time.Duration"))
BLOCKS[f"{JM}#5"] = File(package=JP, imports=_TX + _U)
BLOCKS[f"{JM}#6"] = File(package=f"{JP}.tenancy", imports=(   # its Order is the filter demo; the rest use the stub
    "jakarta.persistence.Column", "jakarta.persistence.Entity", "jakarta.persistence.EntityManager",
    "jakarta.persistence.Id", "jakarta.persistence.Table", "jakarta.persistence.Version",
    "org.hibernate.Session", "org.hibernate.annotations.Filter", "org.hibernate.annotations.FilterDef",
    "org.hibernate.annotations.ParamDef", "org.hibernate.annotations.SQLRestriction",
    "org.springframework.stereotype.Component", f"{JP}.TenantContext", "java.time.Instant", "java.util.UUID"))
BLOCKS[f"{JM}#7"] = File(package=JP, imports=_U + (
    "jakarta.servlet.FilterChain", "jakarta.servlet.ServletException", "jakarta.servlet.http.HttpServletRequest",
    "jakarta.servlet.http.HttpServletResponse", "org.springframework.web.filter.OncePerRequestFilter",
    "org.springframework.security.core.context.SecurityContextHolder",
    "org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken",
    "org.springframework.security.oauth2.jwt.Jwt", "org.slf4j.MDC", "java.io.IOException"))
BLOCKS[f"{JM}#8"] = File(package=JP, imports=_U + (
    "org.springframework.context.annotation.Bean", "org.springframework.context.annotation.Configuration",
    "org.springframework.security.config.annotation.web.builders.HttpSecurity",
    "org.springframework.security.config.annotation.web.configuration.EnableWebSecurity",
    "org.springframework.security.web.SecurityFilterChain", "org.springframework.security.web.AuthenticationEntryPoint",
    "org.springframework.security.web.access.AccessDeniedHandler",
    "org.springframework.security.oauth2.server.resource.web.authentication.BearerTokenAuthenticationFilter",
    "org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationConverter",
    "org.springframework.security.oauth2.jwt.Jwt", "org.springframework.security.core.GrantedAuthority",
    "org.springframework.security.core.authority.SimpleGrantedAuthority", "java.util.Collection"))
BLOCKS[f"{JM}#9"] = Split([
    (None, File(package=JP, imports=(
        "com.fasterxml.jackson.annotation.JsonInclude", "com.fasterxml.jackson.annotation.JsonProperty",
        "jakarta.servlet.http.HttpServletResponse", "org.springframework.http.HttpHeaders",
        "org.springframework.http.MediaType", "tools.jackson.databind.json.JsonMapper", "java.io.IOException",
        "java.util.List"))),
    (r"^// List endpoint", Members(cls="OrderListEndpoint", package=JP, imports=(
        "org.springframework.web.bind.annotation.GetMapping", "org.springframework.web.bind.annotation.RequestParam",
        "java.util.List"), inject=("private OrderQueryService orderService;",))),
])
BLOCKS[f"{JM}#10"] = File(package=JP, imports=(
    "org.slf4j.Logger", "org.slf4j.LoggerFactory", "org.springframework.http.HttpHeaders",
    "org.springframework.http.HttpStatusCode", "org.springframework.http.ResponseEntity",
    "org.springframework.web.bind.MethodArgumentNotValidException",
    "org.springframework.web.bind.annotation.ExceptionHandler",
    "org.springframework.web.bind.annotation.RestControllerAdvice",
    "org.springframework.web.context.request.WebRequest",
    "org.springframework.web.servlet.mvc.method.annotation.ResponseEntityExceptionHandler",
    "org.springframework.validation.FieldError", "jakarta.validation.ConstraintViolation",
    "java.util.Collection", "java.util.List", "java.util.Map"))
BLOCKS[f"{JM}#11"] = File(package=JP, imports=("java.util.List",))
_DATA = (f"{JP}.Order", f"{JP}.OrderStatus", "java.time.Instant", "java.util.UUID")
BLOCKS[f"{JM}#12"] = File(package=f"{JP}.data", imports=_DATA + (
    "org.springframework.data.jpa.repository.JpaRepository", "org.springframework.data.jpa.repository.JpaSpecificationExecutor",
    "org.springframework.data.jpa.repository.Query", "org.springframework.data.jpa.repository.Modifying",
    "org.springframework.data.repository.query.Param", "org.springframework.data.domain.Limit",
    "java.util.List", "java.util.Optional", "java.util.Set"))
BLOCKS[f"{JM}#13"] = Split([
    (None, File(package=f"{JP}.data", imports=_DATA + ("org.springframework.data.jpa.domain.Specification",))),
    (r"^// Usage", Statements(cls="SpecificationUsage", package=f"{JP}.data", imports=_DATA + (
        "org.springframework.data.jpa.domain.Specification", "org.springframework.data.domain.ScrollPosition",
        "org.springframework.data.domain.Sort", "org.springframework.data.domain.Window",
        S + f"{JP}.data.OrderSpecifications.*", S + f"{JP}.OrderStatus.PENDING"),
        method="void run(OrderRepository orderRepo, UUID tenantId, Instant startDate, Instant endDate, "
               "ScrollPosition position)")),
])
_REPO_OF_ORDER = "org.springframework.data.repository.Repository<Order, UUID>"
BLOCKS[f"{JM}#14"] = Split([
    (None, File(package=f"{JP}.data", imports=_DATA + ("java.math.BigDecimal",))),
    (r"^// Repository returns projection", Members(
        cls="OrderSummaryRepository", package=f"{JP}.data", interface=True, extends=_REPO_OF_ORDER,
        imports=_DATA + ("org.springframework.data.domain.ScrollPosition", "org.springframework.data.domain.Window"))),
    # the JPQL constructor expression names com.company.app.dto.OrderStats — so that is its package here
    (r"^// Record-based projection", File(package=f"{JP}.dto", imports=(f"{JP}.OrderStatus", "java.math.BigDecimal"))),
    (r"^@Query", Members(cls="OrderStatsRepository", package=f"{JP}.data", interface=True, extends=_REPO_OF_ORDER,
                         imports=_DATA + (f"{JP}.dto.OrderStats", "org.springframework.data.jpa.repository.Query",
                                          "org.springframework.data.repository.query.Param", "java.util.List"))),
])
BLOCKS[f"{JM}#15"] = File(package=JP, test=True, imports=_JUNIT + _U + (
    "org.junit.jupiter.api.extension.ExtendWith", "org.mockito.InjectMocks", "org.mockito.Mock",
    "org.mockito.junit.jupiter.MockitoExtension", "java.math.BigDecimal",
    S + "org.mockito.ArgumentMatchers.any", S + "org.mockito.Mockito.verify", S + "org.mockito.Mockito.when"))
BLOCKS[f"{JM}#16"] = Members(cls="OrderParameterizedTest", package=JP, test=True, imports=(
    "org.junit.jupiter.params.ParameterizedTest", "org.junit.jupiter.params.provider.Arguments",
    "org.junit.jupiter.params.provider.CsvSource", "org.junit.jupiter.params.provider.MethodSource",
    "java.util.stream.Stream", S + "org.junit.jupiter.api.Assertions.assertEquals", S + f"{JP}.OrderStatus.*"))
BLOCKS[f"{JM}#17"] = File(package=JP, test=True, imports=_JUNIT + _U + (
    "org.springframework.beans.factory.annotation.Autowired",
    "org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest",
    "org.springframework.boot.jdbc.test.autoconfigure.AutoConfigureTestDatabase",
    "org.springframework.boot.jdbc.test.autoconfigure.AutoConfigureTestDatabase.Replace",
    "org.springframework.boot.jpa.test.autoconfigure.TestEntityManager",
    "org.springframework.boot.test.context.SpringBootTest",
    "org.springframework.boot.resttestclient.TestRestTemplate",
    "org.springframework.boot.resttestclient.autoconfigure.AutoConfigureTestRestTemplate",
    "org.springframework.http.HttpEntity", "org.springframework.http.HttpHeaders",
    "org.springframework.http.HttpMethod", "org.springframework.http.HttpStatus",
    "java.math.BigDecimal", "java.time.Instant"))
BLOCKS[f"{JM}#18"] = File(package=JP, test=True, imports=(
    "org.junit.jupiter.api.Test", "org.springframework.beans.factory.annotation.Autowired",
    "org.springframework.boot.test.context.SpringBootTest",
    "org.springframework.boot.testcontainers.service.connection.ServiceConnection",
    "org.testcontainers.junit.jupiter.Container", "org.testcontainers.junit.jupiter.Testcontainers",
    "org.testcontainers.postgresql.PostgreSQLContainer"))
BLOCKS[f"{JM}#19"] = Statements(cls="AssertJExamples", package=JP, test=True, imports=_JUNIT + _U,
                                method="void run(Order order, List<Order> orders, PaymentService service, "
                                       "PaymentRequest invalidRequest, UUID TENANT_ID)")
BLOCKS[f"{JM}#20"] = File(package=f"{JP}.cache", imports=_TX + (
    "org.springframework.cache.annotation.Cacheable", "org.springframework.cache.annotation.CacheEvict",
    "org.springframework.cache.annotation.EnableCaching", "org.springframework.context.annotation.Bean",
    "org.springframework.context.annotation.Configuration",
    "org.springframework.data.redis.cache.RedisCacheConfiguration",
    "org.springframework.data.redis.serializer.GenericJacksonJsonRedisSerializer",
    "org.springframework.data.redis.serializer.RedisSerializationContext.SerializationPair",
    "tools.jackson.databind.jsontype.BasicPolymorphicTypeValidator",
    f"{JP}.NotFoundException", f"{JP}.UpdateUserRequest", f"{JP}.UserMapper", f"{JP}.UserRepository",
    f"{JP}.UserResponse", "java.time.Duration", "java.util.ArrayList", "java.util.HashMap", "java.util.HashSet",
    "java.util.UUID"))
BLOCKS[f"{JM}#21"] = Members(cls="VirtualThreadConfig", package=JP,
                             annotations=("@org.springframework.context.annotation.Configuration",), imports=(
    "org.springframework.context.annotation.Bean", "org.springframework.boot.tomcat.TomcatProtocolHandlerCustomizer",
    "java.util.concurrent.Executors"))
BLOCKS[f"{JM}#22"] = File(package=JP, imports=(
    "org.springframework.web.bind.annotation.GetMapping", "org.springframework.web.bind.annotation.RestController",
    "org.springframework.http.MediaType", "org.springframework.security.core.annotation.AuthenticationPrincipal",
    "org.springframework.security.oauth2.jwt.Jwt", "reactor.core.publisher.Flux", "java.util.UUID"))

# ── frameworks/spring-boot.md ── (its own package; the exception, envelope and security types are the archetypes')
SB = "frameworks/spring-boot.md"
SBP = "com.example.app.springboot"
BLOCKS[f"{SB}#1"] = File(package=SBP, imports=("org.springframework.stereotype.Service",
                                               "org.springframework.cache.CacheManager"))
BLOCKS[f"{SB}#2"] = File(package=SBP, transforms=("elide", "stub_bodies"), imports=(
    "com.example.app.exception.*", "org.springframework.http.ResponseEntity",
    "org.springframework.web.bind.MethodArgumentNotValidException",
    "org.springframework.web.bind.annotation.ExceptionHandler",
    "org.springframework.web.bind.annotation.RestControllerAdvice"))
BLOCKS[f"{SB}#3"] = Split([
    (None, File(package=SBP, imports=("jakarta.validation.constraints.NotBlank", "jakarta.validation.constraints.NotNull",
                                      "jakarta.validation.constraints.Size"))),
    (r"^// In controller", Members(cls="ValidationExample", package=SBP, transforms=("elide", "stub_bodies"), imports=(
        "com.example.app.common.ApiResponse", "jakarta.validation.Valid", "org.springframework.http.ResponseEntity",
        "org.springframework.web.bind.annotation.PostMapping", "org.springframework.web.bind.annotation.RequestBody"))),
])
BLOCKS[f"{SB}#4"] = File(package=SBP, imports=(
    "com.example.app.security.JwtAuthenticationFilter", "com.example.app.security.SecurityErrorDelegate",
    "org.springframework.context.annotation.Bean", "org.springframework.context.annotation.Configuration",
    "org.springframework.security.config.annotation.web.builders.HttpSecurity",
    "org.springframework.security.config.annotation.web.configuration.EnableWebSecurity",
    "org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer",
    "org.springframework.security.config.http.SessionCreationPolicy",
    "org.springframework.security.web.SecurityFilterChain",
    "org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter"))
BLOCKS[f"{SB}#5"] = File(package=SBP, test=True, imports=(
    "org.junit.jupiter.api.extension.ExtendWith", "org.mockito.InjectMocks", "org.mockito.Mock",
    "org.mockito.junit.jupiter.MockitoExtension", "org.springframework.beans.factory.annotation.Autowired",
    "org.springframework.boot.test.context.SpringBootTest",
    "org.springframework.boot.testcontainers.service.connection.ServiceConnection",
    "org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest",
    "org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest",
    "org.springframework.boot.jpa.test.autoconfigure.TestEntityManager",
    "org.springframework.test.context.bean.override.mockito.MockitoBean",
    "org.springframework.test.web.servlet.MockMvc", "org.testcontainers.junit.jupiter.Container",
    "org.testcontainers.junit.jupiter.Testcontainers", "org.testcontainers.postgresql.PostgreSQLContainer"))

# ── testing/junit-mockito.md ── (tests of the Widget archetypes, in their packages)
JU = "testing/junit-mockito.md"
_W = ("com.example.app.model.entity.Widget", "com.example.app.model.entity.WidgetStatus",
      "com.example.app.model.dto.CreateWidgetRequest", "com.example.app.model.dto.UpdateWidgetRequest",
      "com.example.app.model.dto.WidgetResponse", "com.example.app.exception.ConflictException",
      "com.example.app.exception.ResourceNotFoundException", "java.time.Instant", "java.util.List",
      "java.util.Optional", "java.util.UUID")
BLOCKS[f"{JU}#1"] = File(package="com.example.app.service", test=True, imports=_W + (
    "com.example.app.repository.WidgetRepository",))
BLOCKS[f"{JU}#2"] = File(package="com.example.app.model.dto", test=True, imports=_W + (
    "jakarta.validation.Validation", "jakarta.validation.Validator", "org.junit.jupiter.api.DisplayName",
    "java.util.stream.Stream", S + "org.assertj.core.api.Assertions.assertThat"))
BLOCKS[f"{JU}#3"] = File(package="com.example.app.controller", test=True, imports=_W + (
    "com.example.app.service.WidgetService", "org.junit.jupiter.api.Test",
    "org.springframework.beans.factory.annotation.Autowired", "org.springframework.http.MediaType",
    "org.springframework.security.core.authority.SimpleGrantedAuthority",
    S + "org.mockito.ArgumentMatchers.any", S + "org.mockito.ArgumentMatchers.eq",
    S + "org.mockito.BDDMockito.given", S + "org.mockito.BDDMockito.then"))
BLOCKS[f"{JU}#4"] = File(package="com.example.app.repository", test=True, imports=_W + (
    "org.junit.jupiter.api.BeforeEach", "org.junit.jupiter.api.Test",
    "org.springframework.beans.factory.annotation.Autowired", "org.springframework.data.domain.ScrollPosition",
    S + "org.assertj.core.api.Assertions.assertThat"))
BLOCKS[f"{JU}#5"] = File(package="com.example.app", test=True, imports=_W + (
    "com.example.app.common.ApiResponse", "com.example.app.exception.ErrorBody", "org.junit.jupiter.api.Test",
    "org.springframework.beans.factory.annotation.Autowired", "org.springframework.http.HttpEntity",
    "org.springframework.http.HttpHeaders", "org.springframework.http.HttpMethod",
    "org.springframework.http.HttpStatus", "java.nio.charset.StandardCharsets", "java.util.Date",
    S + "org.assertj.core.api.Assertions.assertThat"))
BLOCKS[f"{JU}#6"] = Statements(cls="AssertJPatterns", package="com.example.app", test=True, imports=_W + (
    "com.example.app.service.WidgetService", "org.assertj.core.api.SoftAssertions",
    S + "org.assertj.core.api.Assertions.assertThat", S + "org.assertj.core.api.Assertions.assertThatThrownBy"),
    method="void run(Widget widget, List<Widget> widgets, WidgetService service, UUID id, UUID tenantId, "
           "Widget result)")

# ── frameworks/quarkus.md ── (its own POM: the Quarkus platform BOM, not Spring Boot)
QM = "frameworks/quarkus.md"
QP = "com.example.quarkus"
_CDI = ("jakarta.enterprise.context.ApplicationScoped", "jakarta.inject.Inject")
BLOCKS[f"{QM}#1"] = Split([   # constructor injection, then the field-injection alternative (same class name)
    (None, File(package=QP, imports=_CDI + ("io.quarkus.cache.CacheManager",))),
    (r"^// Alternative: field injection", File(package=f"{QP}.fieldinjection", imports=_CDI + (
        "io.quarkus.cache.CacheManager", f"{QP}.WidgetRepository", f"{QP}.WidgetService"))),
])
BLOCKS[f"{QM}#2"] = File(package=QP, imports=_CDI + (
    "jakarta.ws.rs.Consumes", "jakarta.ws.rs.DELETE", "jakarta.ws.rs.DefaultValue", "jakarta.ws.rs.GET",
    "jakarta.ws.rs.POST", "jakarta.ws.rs.PUT", "jakarta.ws.rs.Path", "jakarta.ws.rs.PathParam",
    "jakarta.ws.rs.Produces", "jakarta.ws.rs.QueryParam", "jakarta.ws.rs.core.Context",
    "jakarta.ws.rs.core.MediaType", "jakarta.ws.rs.core.Response", "jakarta.ws.rs.core.SecurityContext",
    "jakarta.validation.Valid", "java.util.Set", "java.util.UUID", S + f"{QP}.Envelopes.newMeta"))
BLOCKS[f"{QM}#3"] = File(package=QP, imports=_CDI + (
    "jakarta.persistence.Column", "jakarta.persistence.Entity", "jakarta.persistence.GeneratedValue",
    "jakarta.persistence.Id", "jakarta.persistence.Table",
    "io.quarkus.hibernate.orm.panache.PanacheEntityBase", "io.quarkus.hibernate.orm.panache.PanacheRepositoryBase",
    "org.hibernate.reactive.mutiny.Mutiny", "io.smallrye.mutiny.Uni",
    "java.time.Instant", "java.util.List", "java.util.Optional", "java.util.UUID"))
BLOCKS[f"{QM}#4"] = File(package=QP, imports=("io.quarkus.runtime.annotations.RegisterForReflection",
                                              "java.time.Instant", "java.util.UUID"))
BLOCKS[f"{QM}#5"] = File(package=QP, imports=("io.smallrye.config.ConfigMapping", "io.smallrye.config.WithDefault",
                                              "java.time.Duration", "java.util.Optional"))
BLOCKS[f"{QM}#6"] = File(package=QP, test=True, imports=(
    "io.quarkus.test.InjectMock", "io.quarkus.test.junit.QuarkusTest", "io.quarkus.test.junit.QuarkusTestProfile",
    "io.quarkus.test.junit.TestProfile", "io.quarkus.test.security.TestSecurity",
    "io.quarkus.test.security.jwt.Claim", "io.quarkus.test.security.jwt.JwtSecurity",
    "io.restassured.http.ContentType", "jakarta.inject.Inject", "org.junit.jupiter.api.Test",
    "java.util.Map", "java.util.UUID", S + "io.restassured.RestAssured.given", S + "org.hamcrest.Matchers.equalTo",
    S + "org.junit.jupiter.api.Assertions.assertEquals", S + "org.mockito.ArgumentMatchers.any",
    S + "org.mockito.Mockito.verify"))
BLOCKS[f"{QM}#7"] = File(package=QP, imports=_CDI + (
    "org.eclipse.microprofile.health.HealthCheck", "org.eclipse.microprofile.health.HealthCheckResponse",
    "org.eclipse.microprofile.health.Readiness", "io.micrometer.core.instrument.MeterRegistry",
    "javax.sql.DataSource", "java.time.Duration"))
BLOCKS[f"{QM}#8"] = File(package=QP, imports=(
    "jakarta.ws.rs.WebApplicationException", "jakarta.ws.rs.core.Response", "jakarta.ws.rs.ext.ExceptionMapper",
    "jakarta.ws.rs.ext.Provider", "io.quarkus.logging.Log", "org.jboss.logging.MDC",
    "java.util.LinkedHashMap", "java.util.List", "java.util.Map", "java.util.Objects"))

QUARKUS_VERSION = "3.40.1"
QUARKUS_POM = f"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>archetype.compile</groupId>
  <artifactId>@NAME@</artifactId>
  <version>0</version>
  <name>@NAME@</name>
  <properties>
    <maven.compiler.release>25</maven.compiler.release>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
  </properties>
  <dependencyManagement>
    <dependencies>
      <dependency>
        <groupId>io.quarkus.platform</groupId>
        <artifactId>quarkus-bom</artifactId>
        <version>{QUARKUS_VERSION}</version>
        <type>pom</type>
        <scope>import</scope>
      </dependency>
    </dependencies>
  </dependencyManagement>
  <dependencies>
{dep("io.quarkus", "quarkus-rest-jackson")}
{dep("io.quarkus", "quarkus-hibernate-validator")}
{dep("io.quarkus", "quarkus-hibernate-orm-panache")}
{dep("io.quarkus", "quarkus-hibernate-reactive")}
{dep("io.quarkus", "quarkus-cache")}
{dep("io.quarkus", "quarkus-smallrye-health")}
{dep("io.quarkus", "quarkus-micrometer")}
{dep("io.quarkus", "quarkus-smallrye-jwt")}
{dep("io.quarkus", "quarkus-junit5", scope="test")}
{dep("io.quarkus", "quarkus-junit5-mockito", scope="test")}
{dep("io.quarkus", "quarkus-test-security-jwt", scope="test")}
{dep("io.rest-assured", "rest-assured", scope="test")}
  </dependencies>
  <build>
    <plugins>
      <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-compiler-plugin</artifactId>
        <version>3.14.1</version>
        <configuration>
          <release>25</release>
          <parameters>true</parameters>
          <showWarnings>true</showWarnings>
          <compilerArgs>
            <arg>-Xlint:deprecation,removal</arg>
          </compilerArgs>
        </configuration>
      </plugin>
    </plugins>
  </build>
</project>
"""

# ── single Java blocks in shared testing / API packs ──
PB, CT, ES, GQ = ("testing/property-based.md", "testing/contract-testing.md", "testing/external-service-mocks.md",
                  "frameworks/graphql.md")
BLOCKS[f"{PB}#1"] = File(package="com.example.pbt", test=True, imports=(
    "org.junit.jupiter.api.Assertions", "java.util.ArrayList", "java.util.Collections", "java.util.List",
    S + "com.example.pbt.TestData.generateWidgets", S + "com.example.pbt.Paging.paginate"))
BLOCKS[f"{CT}#1"] = File(package="com.example.pact", test=True, imports=(
    "au.com.dius.pact.consumer.MockServer", "au.com.dius.pact.consumer.dsl.PactDslJsonBody",
    "au.com.dius.pact.consumer.dsl.PactDslWithProvider", "au.com.dius.pact.consumer.junit5.PactConsumerTestExt",
    "au.com.dius.pact.consumer.junit5.PactTestFor", "au.com.dius.pact.core.model.V4Pact",
    "au.com.dius.pact.core.model.annotations.Pact", "org.junit.jupiter.api.Test",
    "org.junit.jupiter.api.extension.ExtendWith", "java.util.Map", S + "org.junit.jupiter.api.Assertions.assertEquals"))
BLOCKS[f"{ES}#1"] = File(package="com.example.wiremock", test=True, imports=(
    "com.github.tomakehurst.wiremock.junit5.WireMockRuntimeInfo", "com.github.tomakehurst.wiremock.junit5.WireMockTest",
    "org.junit.jupiter.api.Test", S + "org.assertj.core.api.Assertions.assertThat"))
BLOCKS[f"{GQ}#1"] = File(package="com.example.dgs", imports=(
    "com.netflix.graphql.dgs.DgsComponent", "com.netflix.graphql.dgs.DgsData",
    "com.netflix.graphql.dgs.DgsDataFetchingEnvironment", "com.netflix.graphql.dgs.DgsQuery",
    "com.netflix.graphql.dgs.InputArgument", "graphql.GraphqlErrorBuilder", "graphql.execution.DataFetcherResult",
    "com.netflix.graphql.types.errors.ErrorType",
    "org.dataloader.DataLoader", "java.util.Map", "java.util.UUID", "java.util.concurrent.CompletableFuture"))

UNITS += [
    Unit("java-pack", own=rng(JM, 1, 22), stubs=("java-pack",),
         pom_extra=deps_pom(REST_TEST_CLIENT)),
    Unit("spring-boot-pack", own=rng(SB, 1, 5), stubs=("spring-boot-pack",),
         deps=EXCEPTIONS + ENVELOPE + ids(AUTH, 2, 3) + ids(EH, 4) + [(f"{EH}#3", File(only=("ErrorBody", "ApiError")))]),
    Unit("junit-mockito-pack", own=rng(JU, 1, 6),
         deps=EXCEPTIONS + ERROR_WRITER + ENTITY + REPOSITORY + DTO + ENVELOPE + CONTROLLER + SANITIZER
         + SERVICE_API + SERVICE_IMPL + ids(AUTH, 1, 2, 3, 8),
         stubs=("auth", "crud-service"), pom_extra=deps_pom(REST_TEST_CLIENT)),
    Unit("quarkus-pack", own=rng(QM, 1, 8), stubs=("quarkus-pack",), pom=QUARKUS_POM),
    Unit("property-based-pack", own=[f"{PB}#1"], stubs=("property-based",),
         pom_extra=deps_pom(dep("net.jqwik", "jqwik", "1.10.1", "test"))),
    Unit("contract-testing-pack", own=[f"{CT}#1"], stubs=("contract-testing",),
         pom_extra=deps_pom(dep("au.com.dius.pact.consumer", "junit5", "4.7.5", "test"))),
    Unit("external-service-mocks-pack", own=[f"{ES}#1"], stubs=("external-service-mocks",),
         pom_extra=deps_pom(dep("org.wiremock", "wiremock-standalone", "3.13.2", "test"))),
    Unit("graphql-pack", own=[f"{GQ}#1"], stubs=("graphql",),
         pom_extra=deps_pom(dep("com.netflix.graphql.dgs", "graphql-dgs-spring-graphql-starter", "12.1.0"))),
]

# ── JVM build blocks of the Java packs ──
BUILD_SNIPPETS[f"{JM}#kotlin1"] = GradleSnippet(
    name="java-pack-gradle-build", template="boot-build-kts", build_file="build.gradle.kts",
    tasks=("compileTestJava",))
BUILD_SNIPPETS[f"{JM}#kotlin2"] = GradleSnippet(
    name="java-pack-gradle-catalog", template="catalog-kts", build_file="build.gradle.kts",
    tasks=("compileTestJava",), files=((f"{JM}#toml1", "gradle/libs.versions.toml"),))
BUILD_SNIPPETS[f"{JU}#xml1"] = MavenSnippet(
    name="junit-jacoco-coverage", goal="verify",
    pom=boot_pom("junit-jacoco-coverage",
                 deps_pom(dep("org.springframework.boot", "spring-boot-starter-test", scope="test"))
                 + "\n  <build>\n    <plugins>\n@SNIPPET@\n    </plugins>\n  </build>"),
    probe_java="package snippet;\n\npublic class Probe {\n    public int add(int a, int b) {\n"
               "        return a + b;\n    }\n}\n",
    probe_test="package snippet;\n\nimport org.junit.jupiter.api.Test;\n\n"
               "import static org.assertj.core.api.Assertions.assertThat;\n\n"
               "class ProbeTest {\n    @Test\n    void adds() {\n"
               "        assertThat(new Probe().add(1, 2)).isEqualTo(3);\n    }\n}\n")
