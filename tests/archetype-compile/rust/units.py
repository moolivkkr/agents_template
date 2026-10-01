# ruff: noqa: E501
# flake8: noqa
"""Which archetype blocks the Rust compile harness assembles into which crate/module (see harness.py).

Rules for this file (so a PASS means the doc compiles, not the harness):
  * B(file, n) is the n-th ```rust block of .claude/skills/backend/archetypes/<file>.md, verbatim.
  * T("…") is glue the doc leaves to the reader: `mod` declarations, and `use` lines for names a
    block uses but never imports because the doc shows several files' worth of code in one place.
    Glue never re-exports or aliases a name to make a wrong doc path resolve.
  * S("x.rs") is a harness-only stub for an app-specific name that NO archetype defines (a config
    struct, a health handler, a domain type an example only mentions). Stubs never stand in for a
    crate API a sample demonstrates, and never for a type another archetype defines: where one
    archetype uses another's code (crate::error, JwtClaims, WidgetService…), the unit compiles the
    other archetype's real blocks.
  * subs=[(old, new, count)] only replaces a placeholder the doc marks as one (`/* ... */`).
  * split=regex, seg=k compiles segment k of a block cut at each matching line (a BAD/GOOD pair that
    defines the same name twice goes into two modules). Every non-empty segment must be used.
  * drop_last="}" removes a block's closing brace so the following method blocks land inside the
    same impl (the doc shows one `impl Trait for X` spread over several sections).
"""


class B:
    def __init__(self, file, idx, *, split=None, seg=None, subs=(), drop_last=None, expect=None):
        self.file, self.idx, self.split, self.seg = file, idx, split, seg
        self.subs, self.drop_last, self.expect = list(subs), drop_last, expect


class T:
    def __init__(self, text):
        self.text = text


class S:
    def __init__(self, name):
        self.name = name


class Unit:
    def __init__(self, name, what, files, *, lib=True, lib_name=None, bins=(), benches=(), migrations=False,
                 protos=False, build_rs=False, features=None, schema="default", tests=None, test_args=()):
        self.name, self.what, self.files = name, what, files
        self.package = "archetype-" + name
        # lib=False: a binary-only crate (src/main.rs is the crate root, as in the doc's layout)
        self.lib_name = (lib_name or ("archetype_" + name.replace("-", "_"))) if lib else None
        self.bins, self.benches = list(bins), list(benches)
        self.migrations, self.protos, self.build_rs = migrations, protos, build_rs
        self.features = dict(features or {})  # checked with --all-features, so cfg(feature) code compiles too
        # SCHEMAS key: the database its sqlx macros are checked against, and the migrations/ it gets
        self.schema = schema
        # run.sh --run-tests: None = the unit is compile-checked only; otherwise what its tests need
        # besides cargo: () nothing, "db" a Postgres server (--database-url), "docker" a Docker daemon
        self.tests = None if tests is None else tuple(tests)
        self.test_args = list(test_args)  # extra `cargo test` target selection, e.g. ["--lib"]


def blocks(file, *idx, **kw):
    return [B(file, i, **kw) for i in idx]


# Skill packs outside backend/archetypes whose Rust blocks are pinned here too (key: path under
# .claude/skills without .md). harness.py fails when any other .claude/skills/**/*.md has a ```rust
# block, so a new one can't go unchecked. Shared (multi-language) packs: only their Rust blocks are
# compiled; their other blocks belong to the other languages' harnesses.
EXTRA_FILES = [
    "languages/rust.md", "frameworks/axum.md", "frameworks/actix-web.md", "frameworks/graphql.md",
    "testing/rust-test.md", "testing/external-service-mocks.md", "testing/property-based.md",
]

# ─── expected block counts: a mismatch fails the run until this file is updated ──────────────────
EXPECTED = {
    "languages/rust": 26,
    "frameworks/axum": 8,
    "frameworks/actix-web": 10,
    "frameworks/graphql": 1,
    "testing/rust-test": 8,
    "testing/external-service-mocks": 1,
    "testing/property-based": 2,
    "auth-middleware-rust": 9,
    "crud-handler-rust": 8,
    "crud-handler-test-rust": 10,
    "crud-repository-rust": 13,
    "crud-repository-test-rust": 10,
    "crud-service-rust": 12,
    "crud-service-test-rust": 9,
    "error-handling-rust": 9,
    "grpc-pattern-rust": 6,
    "migration-pattern-rust": 2,
    "observability-rust": 20,
    "performance-rust": 30,
    "websocket-pattern-rust": 5,
    "worker-pattern-rust": 6,
}

# ```toml blocks of the *-rust.md files: 'deps' (dependency tables checked against Cargo.toml here),
# 'profile' ([profile.*] / [[bench]] checked by cargo), or ('skip', reason).
TOML = {
    ("auth-middleware-rust", 1): "deps",
    ("crud-handler-test-rust", 1): "deps",
    ("crud-repository-test-rust", 1): "deps",
    ("crud-service-test-rust", 1): "deps",
    ("dockerfile-rust", 1): "toolchain",  # rust-toolchain.toml: channel = the harness's pinned toolchain
    ("dockerfile-rust", 2): "profile",
    ("grpc-pattern-rust", 1): "deps",
    ("migration-pattern-rust", 1): "deps",
    ("observability-rust", 1): "deps",
    ("performance-rust", 1): "profile",
    ("performance-rust", 2): "profile",
    ("performance-rust", 3): "deps",
    ("performance-rust", 4): "deps",
    ("performance-rust", 5): "profile",
}

# The .proto files come from grpc-pattern.md (language-neutral, not edited by this harness).
# (file suffix, line to insert after, missing line, why). Empty since grpc-pattern.md's common.proto
# imports widget.proto and timestamp.proto itself (fixed upstream, 2026-09-30); the protos compile as written.
PROTO_PATCHES = []

# Databases the sqlx::query! metadata is generated against (prepare-sqlx.sh creates one per key,
# archetype_<key>): the ```sql `-- migrations/…` blocks of `migrations` (a doc key) in filename order
# (.up.sql / plain .sql only), minus `exclude` {file: reason}, plus stubs/<extra>. A unit with
# migrations=True also gets that doc's migrations/ directory (sqlx::migrate!, #[sqlx::test]).
#   default: migration-pattern-rust.md's full set (applies to a clean Postgres 17 since round 2,
#            2026-09-30, so the CRUD macros are checked against exactly what a project migrates to),
#            plus the harness-only orders tables the observability/performance excerpts query.
#   lang:    languages/rust.md's own orders/inventory migration (its repository samples).
SCHEMAS = {
    "default": {"migrations": "migration-pattern-rust", "extra": "harness_schema.sql", "exclude": {}},
    "lang": {"migrations": "languages/rust", "extra": None, "exclude": {}},
}

# docker-check.py: the Rust Dockerfiles, built for real (docker build) against docker/ — a minimal
# service with axum, sqlx (rustls, a query! macro, embedded migrations) and the runtime contract — then
# run: the image's USER is numeric, the process runs as that uid, /healthz answers 200, and the
# HEALTHCHECK (where the image has one) reports healthy.
# name: (doc, ```dockerfile block, [(old, new, count)] to compose a variant from a fragment, or None)
DOCKERFILES = {
    "debian": ("dockerfile-rust", 1, None),
    "musl-alpine": ("dockerfile-rust", 2, None),
    "scratch": ("dockerfile-rust", 3, None),
    # "Build Optimization Tips" (block 4) is a fragment: its BuildKit cache-mount RUN put into the debian
    # Dockerfile's build step, as the tip says (the binary leaves the cache-mounted target/ via cp)
    "debian-cache-mounts": ("dockerfile-rust", 1, [
        ("RUN cargo build --release --bin yourapp\n", "@FRAGMENT@\n", 1),
        ("RUN strip target/release/yourapp\n", "RUN strip /app/yourapp-bin\n", 1),
        ("COPY --from=builder /app/target/release/yourapp /app/yourapp", "COPY --from=builder /app/yourapp-bin /app/yourapp", 1),
    ]),
    "perf-chef": ("performance-rust", 1, None),
}
DOCKER_FRAGMENT = ("dockerfile-rust", 4)  # @FRAGMENT@ = its lines from the first RUN on

# Blocks (or segments) that are deliberately not compiled, with the reason. Empty: every Rust block of
# every pack is compiled (round 3, 2026-09-30).
SKIP = {}

EH = "error-handling-rust"
AUTH = "auth-middleware-rust"
HANDLER = "crud-handler-rust"
HTEST = "crud-handler-test-rust"
REPO = "crud-repository-rust"
RTEST = "crud-repository-test-rust"
SVC = "crud-service-rust"
STEST = "crud-service-test-rust"
MIG = "migration-pattern-rust"
WS = "websocket-pattern-rust"
WK = "worker-pattern-rust"
GRPC = "grpc-pattern-rust"
OBS = "observability-rust"
PERF = "performance-rust"
LANG = "languages/rust"
AXUM = "frameworks/axum"
ACTIX = "frameworks/actix-web"
RT = "testing/rust-test"
GQL = "frameworks/graphql"
MOCKS = "testing/external-service-mocks"
PROP = "testing/property-based"
ACTIX_MAIN = r"^#\[actix_web::main\]"

# The service file shows domain types, traits and WidgetService in one place; in the composed app
# those live in crate::domain / crate::traits (the layout crud-service-test-rust.md states).
SERVICE_MODULE_GLUE = T("""
use async_trait::async_trait;
use chrono::Utc;
use serde::Serialize;
use uuid::Uuid;

use crate::domain::{AuditEntry, ListFilters, ListResult};
use crate::error::AppError;
use crate::handlers::widget::{CreateWidgetInput, UpdateWidgetInput};
use crate::harness::CreateWithRelationsInput;
use crate::models::{Widget, WidgetStatus};
use crate::traits::{audit::AuditWriter, cache::Cache, repository::WidgetRepository};
""")

# crud-repository-rust.md shows the trait next to its implementation; in the composed app the
# implementation implements the service-owned trait in crate::traits::repository.
REPO_MODULE_GLUE = T("""
use async_trait::async_trait;
use uuid::Uuid;

use crate::domain::{ListFilters, ListResult};
use crate::error::AppError;
use crate::models::{Widget, WidgetStatus};
use crate::traits::repository::WidgetRepository;
""")


# observability-rust.md: the order-service types are harness stubs (crate::app) and AppError is
# error-handling-rust.md's; both come in by glob, so they never collide with a name an excerpt imports.
OBS_APP_GLUE = "#[allow(unused_imports)]\nuse crate::app::*;\n#[allow(unused_imports)]\nuse crate::error::*;\n"
OBS_LAYER_SPLIT = r"^// --- (Service|Repository) layer ---"


# performance-rust.md: a page of independent snippets. App types are harness stubs (crate::app); AppError is
# error-handling-rust.md's; all by glob so a snippet's own imports always win.
PERF_GLUE = "#[allow(unused_imports)]\nuse crate::app::*;\n#[allow(unused_imports)]\nuse crate::error::*;\n"
BAD_GOOD = r"^// (BAD|GOOD|BEST)"


def perf(idx, seg=None, split=BAD_GOOD, before="", after="", glue=PERF_GLUE, **kw):
    """One performance-rust.md block (or segment), optionally wrapped (before/after) — its own module."""
    part = B(PERF, idx, split=split, seg=seg, **kw) if seg is not None else B(PERF, idx, **kw)
    return ([T(glue)] if glue else []) + ([T(before)] if before else []) + [part] + ([T(after)] if after else [])


def repo_impl_blocks():
    """crud-repository-rust.md: `impl WidgetRepository for PgWidgetRepository` opens in "Create" and
    its other methods are shown in later sections; assemble them into that one impl."""
    return [B(REPO, 2), B(REPO, 3, drop_last="}"), B(REPO, 4), B(REPO, 5), B(REPO, 6), B(REPO, 7),
            B(REPO, 9), T("}"), B(REPO, 8), B(REPO, 10), B(REPO, 11), B(REPO, 12)]


# widget-app: the CRUD archetypes composed as one crate `yourapp` (the layout crud-service-test-rust.md
# states). testing/rust-test.md's unit reuses it with its own tests added.
WIDGET_APP_FILES = {
    "src/lib.rs": [T("""
pub mod auth;
pub mod config;
pub mod db;
pub mod domain;
pub mod error;
pub mod extractors;
pub mod handlers;
pub mod harness;
pub mod middleware;
pub mod models;
pub mod repositories;
pub mod services;
pub mod startup;
pub mod traits;
""")],
    "src/error.rs": blocks(EH, 1, 2, 3, 4, 5, 6, 7),
    "src/config.rs": [S("app_config.rs")],
    "src/harness.rs": [S("app_harness.rs")],
    "src/auth/mod.rs": [T("pub mod api_key;\npub mod claims;\npub mod middleware;\npub mod require_role;")],
    "src/auth/claims.rs": [B(AUTH, 1)],
    "src/auth/middleware.rs": [B(AUTH, 2), B(AUTH, 9)],
    "src/auth/require_role.rs": [B(AUTH, 4)],
    "src/auth/api_key.rs": [B(AUTH, 5)],
    "src/extractors/mod.rs": [T("pub mod auth_user;")],
    "src/extractors/auth_user.rs": [B(AUTH, 3)],
    "src/middleware/mod.rs": [T("pub mod cors;\npub mod rate_limit;")],
    "src/middleware/rate_limit.rs": [B(AUTH, 6)],
    "src/middleware/cors.rs": [B(AUTH, 7)],
    "src/startup.rs": [
        T("use crate::harness::{health_check, readiness_check}; // app-specific probes (no archetype defines them)"),
        B(AUTH, 8, subs=[("WidgetService::new(/* ... */)", "crate::harness::widget_service(pool.clone())", 1)]),
    ],
    "src/handlers/mod.rs": [T("pub mod admin;\npub mod widget;")],
    "src/handlers/admin.rs": [S("admin_routes.rs")],
    "src/handlers/widget.rs": blocks(HANDLER, 1, 2, 3, 4, 5, 6, 7, 8),
    "src/domain.rs": [B(SVC, 1)],
    "src/models.rs": [B(REPO, 13)],
    "src/traits/mod.rs": [T("pub mod audit;\npub mod cache;\npub mod repository;")],
    "src/traits/repository.rs": [B(STEST, 1, split=r"^// src/traits/", seg=1)],
    "src/traits/cache.rs": [B(STEST, 1, split=r"^// src/traits/", seg=2)],
    "src/traits/audit.rs": [B(STEST, 1, split=r"^// src/traits/", seg=3)],
    "src/services/mod.rs": [T("pub mod widget;")],
    "src/services/widget.rs": [SERVICE_MODULE_GLUE] + blocks(SVC, 3, 4, 5, 6, 7, 8, 9, 10, 11)
                              + blocks(STEST, 2, 3, 4, 5, 6, 7, 8, 9),
    "src/repositories/mod.rs": [T("pub mod widget;")],
    "src/repositories/widget.rs": [REPO_MODULE_GLUE] + repo_impl_blocks(),
    "src/db.rs": blocks(MIG, 1, 2),
    "tests/api/main.rs": [T("mod helpers;\nmod widget_test;")],
    "tests/api/helpers.rs": blocks(HTEST, 1, 2, 3),
    "tests/api/widget_test.rs": blocks(HTEST, 4, 5, 6, 7, 8, 9, 10),
    "tests/repository/main.rs": [B(RTEST, 1)],
    "tests/repository/widget_repo_test.rs": blocks(RTEST, 2, 3, 4, 5, 6, 7, 8, 9, 10),
}


UNITS = [
    Unit("error-handling", "error-handling-rust.md: AppError, envelope IntoResponse, request id, extractors, recovery, tests", {
        "src/lib.rs": [T("pub mod error;")],
        "src/error.rs": blocks(EH, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    }, tests=()),

    Unit("widget-app", "auth-middleware + crud-handler + crud-service + crud-repository + migration db.rs composed "
                       "as one crate `yourapp`, with the service unit tests, handler and repository integration tests",
         WIDGET_APP_FILES, lib_name="yourapp", migrations=True, tests=("db",)),

    Unit("rust-test", "testing/rust-test.md's tests inside the widget app (crate `yourapp`, minus the archetypes' own "
                      "tests/): unit, tokio, mockall, #[sqlx::test], fixtures, proptest, oneshot integration + TestApp", {
        **{k: v for k, v in WIDGET_APP_FILES.items() if not k.startswith("tests/")},
        "src/lib.rs": WIDGET_APP_FILES["src/lib.rs"] + [T("#[cfg(test)]\nmod test_fixtures;")],
        "src/test_fixtures.rs": [B(RT, 5)],
        # the unit-test module and the proptests sit next to sanitize_column / the cursor codec
        "src/repositories/widget.rs": WIDGET_APP_FILES["src/repositories/widget.rs"] + [B(RT, 1), B(RT, 6)],
        "src/repositories/mod.rs": [T("pub mod widget;\n#[cfg(test)]\nmod db_tests;")],
        "src/repositories/db_tests.rs": [T("""
use crate::error::AppError;
use crate::models::Widget;
use crate::repositories::widget::PgWidgetRepository;
use crate::traits::repository::WidgetRepository;
"""), B(RT, 4)],
        "src/services/mod.rs": [T("pub mod widget;\n#[cfg(test)]\nmod mock_examples;\n#[cfg(test)]\nmod tokio_examples;")],
        "src/services/tokio_examples.rs": [T("""
use std::sync::Arc;

use uuid::Uuid;

use crate::error::AppError;
use crate::handlers::widget::CreateWidgetInput;
use crate::services::widget::WidgetService;
use crate::traits::{audit::MockAuditWriter, cache::MockCache, repository::MockWidgetRepository};
"""), S("rust_test_setup.rs"), B(RT, 2)],
        "src/services/mock_examples.rs": [T("""
use crate::handlers::widget::CreateWidgetInput;
use crate::models::Widget;
use crate::services::widget::WidgetService;
"""), B(RT, 3)],
        "tests/api_integration.rs": [B(RT, 7)],
        "tests/common/mod.rs": [B(RT, 8)],
    }, lib_name="yourapp", migrations=True, tests=("db",)),

    Unit("crud-repository", "crud-repository-rust.md as its own module (trait next to the impl), with error.rs, Widget, ListFilters", {
        "src/lib.rs": [T("pub mod domain;\npub mod error;\npub mod models;\npub mod repositories;")],
        "src/error.rs": blocks(EH, 1, 2, 3, 4, 5, 6, 7),
        "src/domain.rs": [B(SVC, 1)],
        "src/models.rs": [B(REPO, 13)],
        "src/repositories.rs": [B(REPO, 1)] + repo_impl_blocks(),
    }, migrations=True),

    Unit("websocket", "websocket-pattern-rust.md: types, ConnectionManager, axum upgrade handler, main.rs (binary crate)", {
        "src/main.rs": [
            T("mod auth; // harness stub: the app's credential check\nmod error;\nmod ws;\n\n"
              "use ws::{handler::ws_upgrade, manager::ConnectionManager};"),
            B(WS, 4),
        ],
        "src/auth.rs": [S("ws_auth.rs")],
        "src/error.rs": blocks(EH, 1, 2, 3, 4, 5, 6, 7),
        "src/ws/mod.rs": [T("pub mod handler;\npub mod manager;\npub mod types;")],
        "src/ws/types.rs": [B(WS, 1)],
        "src/ws/manager.rs": [B(WS, 2)],
        "src/ws/handler.rs": [B(WS, 3), B(WS, 5)],
    }, lib=False, tests=()),

    Unit("worker", "worker-pattern-rust.md: job types, traits, Worker, main.rs, EmailSendHandler, health (binary crate)", {
        "src/main.rs": [
            T("mod app; // harness stubs: Settings, Redis queue/idempotency, email/report services\n"
              "mod email_handler;\n\nuse app::*;\nuse email_handler::EmailSendHandler;"),
            B(WK, 4),
        ],
        "src/app.rs": [S("worker_app.rs")],
        "src/worker/job.rs": [B(WK, 1)],
        "src/worker/traits.rs": [B(WK, 2)],
        "src/worker/mod.rs": [B(WK, 3), B(WK, 6)],
        # the example handler is shown without its file; it uses the worker's types and the app's email service
        "src/email_handler.rs": [T("""
use std::sync::Arc;

use async_trait::async_trait;

use crate::app::{EmailPayload, EmailService};
use crate::worker::job::Job;
use crate::worker::traits::{JobHandler, WorkerError};
"""), B(WK, 5)],
    }, lib=False),

    Unit("grpc", "grpc-pattern-rust.md: build.rs codegen from grpc-pattern.md's protos, server, auth layer, context, errors, main.rs (binary crate)", {
        "build.rs": [B(GRPC, 1)],
        "src/main.rs": [T("mod auth; // harness stubs for the app modules the doc says are not shown\nmod error;\nmod services;"),
                        B(GRPC, 6)],
        "src/app.rs": [S("grpc_wire.rs")],
        "src/auth.rs": [S("grpc_auth.rs")],
        "src/services.rs": [S("grpc_services.rs")],
        "src/error.rs": blocks(EH, 1, 2, 3, 4, 5, 6, 7),
        "src/grpc/mod.rs": [T("pub mod auth_layer;\npub mod context;\npub mod convert;\npub mod errors;\npub mod widget_server;")],
        "src/grpc/convert.rs": [S("grpc_convert.rs")],
        "src/grpc/widget_server.rs": [B(GRPC, 2)],
        "src/grpc/auth_layer.rs": [B(GRPC, 3)],
        "src/grpc/context.rs": [B(GRPC, 4)],
        "src/grpc/errors.rs": [B(GRPC, 5)],
    }, lib=False, protos=True, build_rs=True),

    Unit("observability", "observability-rust.md: OTel init/shutdown, instrumented layers, propagation, metrics + middleware, "
                          "Prometheus, redaction, request-id/tenant middleware, full stack; with the real error.rs and auth", {
        "src/lib.rs": [T("""
pub mod app; // harness stubs: the order-service domain the examples use
pub mod auth;
pub mod batch;
pub mod business_metrics;
pub mod config;
pub mod error;
pub mod extractors;
pub mod instrumented;
pub mod instrumented_repo;
pub mod instrumented_service;
pub mod log_format;
pub mod log_macros;
pub mod metrics;
pub mod metrics_middleware;
pub mod prometheus_export;
pub mod propagation;
pub mod redact;
pub mod request_id;
pub mod router_basic;
pub mod sensitive_bad;
pub mod sensitive_good;
pub mod span_errors;
pub mod span_fields;
pub mod stack;
pub mod telemetry;
pub mod tenant;
""")],
        "src/app.rs": [S("obs_app.rs")],
        "src/config.rs": [S("app_config.rs")],
        "src/error.rs": blocks(EH, 1, 2, 3, 4, 5, 6, 7),
        "src/auth/mod.rs": [T("pub mod claims;\npub mod middleware;")],
        "src/auth/claims.rs": [B(AUTH, 1)],
        "src/auth/middleware.rs": [B(AUTH, 2)],
        "src/extractors/mod.rs": [T("pub mod auth_user;")],
        "src/extractors/auth_user.rs": [B(AUTH, 3)],
        # Full Telemetry Setup: RedactingJson is shown later, under Sensitive Data Protection
        "src/telemetry.rs": [T("use crate::redact::RedactingJson;"), B(OBS, 1)],
        "src/bin/order_service.rs": [T("""
use std::sync::Arc;

use archetype_observability::app::AppState;
use archetype_observability::stack::build_router;
use archetype_observability::telemetry::{init_telemetry, shutdown_telemetry};
"""), B(OBS, 2)],
        # "#[tracing::instrument] on Handler / Service / Repository": one excerpt per layer
        "src/instrumented.rs": [T(OBS_APP_GLUE), B(OBS, 3, split=OBS_LAYER_SPLIT, seg=0)],
        "src/instrumented_service.rs": [T(OBS_APP_GLUE + "use uuid::Uuid;"), T("impl OrderService {"),
                                        B(OBS, 3, split=OBS_LAYER_SPLIT, seg=1), T("}")],
        "src/instrumented_repo.rs": [T(OBS_APP_GLUE), T("impl OrderRepo {"), B(OBS, 3, split=OBS_LAYER_SPLIT, seg=2), T("}")],
        "src/router_basic.rs": [T(OBS_APP_GLUE + "use crate::prometheus_export::metrics_handler;"), B(OBS, 4)],
        "src/batch.rs": [T(OBS_APP_GLUE), B(OBS, 5, split=r"^pub async fn", seg=0), T("impl OrderService {"),
                         B(OBS, 5, split=r"^pub async fn", seg=1), T("}")],
        "src/span_errors.rs": [T(OBS_APP_GLUE), B(OBS, 6, split=r"^// Errors that should", seg=0), T("impl OrderService {"),
                               B(OBS, 6, split=r"^// Errors that should", seg=1), T("}")],
        "src/propagation.rs": [T(OBS_APP_GLUE), B(OBS, 7, split=r"^#\[tracing::instrument", seg=0), T("impl HttpClient {"),
                               B(OBS, 7, split=r"^#\[tracing::instrument", seg=1), T("}")],
        "src/metrics.rs": [B(OBS, 8)],
        # the middleware and "Wire it into the router" are one file
        "src/metrics_middleware.rs": [T(OBS_APP_GLUE + "use crate::prometheus_export::metrics_handler;"), B(OBS, 9), B(OBS, 10)],
        "src/prometheus_export.rs": [T(OBS_APP_GLUE), B(OBS, 11)],
        # method excerpt of the Metrics section, which imports KeyValue
        "src/business_metrics.rs": [T(OBS_APP_GLUE + "use opentelemetry::KeyValue;"), T("impl OrderService {"), B(OBS, 12), T("}")],
        "src/log_format.rs": [B(OBS, 13)],
        "src/span_fields.rs": [T(OBS_APP_GLUE), T("impl OrderService {"), B(OBS, 14), T("}")],
        # bare macro statements: wrapped in a function whose parameters are the names they use
        "src/log_macros.rs": [T(OBS_APP_GLUE), T("pub fn structured_fields(order: &Order, cb: &CircuitBreaker, err: &AppError) {"),
                              B(OBS, 15), T("}")],
        # BAD / GOOD define create_user twice: each half goes into its own impl
        "src/sensitive_bad.rs": [T(OBS_APP_GLUE), T("impl UserService {"),
                                 B(OBS, 16, split=r"^// (BAD|GOOD)", seg=1, subs=[("{ ... }", "{ todo!() }", 1)]), T("}")],
        "src/sensitive_good.rs": [T(OBS_APP_GLUE + "pub struct UserServiceGood;\n"), T("impl UserServiceGood {"),
                                  B(OBS, 16, split=r"^// (BAD|GOOD)", seg=2, subs=[("{ ... }", "{ todo!() }", 1)]), T("}"),
                                  B(OBS, 16, split=r"^// (BAD|GOOD)", seg=3)],
        "src/redact.rs": [B(OBS, 17)],
        "src/request_id.rs": [B(OBS, 18)],
        "src/tenant.rs": [B(OBS, 19)],
        "src/stack.rs": [T(OBS_APP_GLUE + "use crate::metrics_middleware::metrics_middleware;\n"
                           "use crate::prometheus_export::metrics_handler;\nuse crate::tenant::tenant_middleware;"),
                         B(OBS, 20)],
    }),

    Unit("performance", "performance-rust.md: pools, memory, async, sqlx batch/COPY/replicas, redis cache, N+1, "
                        "criterion bench, DHAT, console, timing, dispatch, phf, itoa, SoA — each BAD/GOOD half on its own", {
        "src/lib.rs": [T("\n".join(f"pub mod {m};" for m in [
            "app", "error", "db_pool", "redis_pool", "http_client", "zero_copy_bad", "zero_copy_good", "cow",
            "clones_bad", "clones_good", "clones_arc", "small_vec", "prealloc_bad", "prealloc_good",
            "prealloc_best", "stack_heap", "runtime", "blocking_hash_bad", "blocking_hash_good", "blocking_io_bad",
            "blocking_io_good", "streams", "semaphore", "channels", "select", "prepared", "batch_insert", "replicas",
            "caching", "n_plus_one_bad", "n_plus_one_join", "n_plus_one_batch", "console", "timing",
            "dispatch_dyn", "dispatch_generic", "dispatch_enum", "inline_fn", "inline_accessor", "inline_bad",
            "phf_lookup", "format_bad", "format_itoa", "format_write", "soa"]))],
        "src/app.rs": [S("perf_app.rs")],
        "src/error.rs": blocks(EH, 1, 2, 3, 4, 5, 6, 7),
        "src/db_pool.rs": [T(PERF_GLUE), B(PERF, 1), B(PERF, 2)],
        "src/redis_pool.rs": perf(3),
        "src/http_client.rs": perf(4),
        "src/zero_copy_bad.rs": perf(5, 1),
        "src/zero_copy_good.rs": perf(5, 2),
        "src/cow.rs": perf(6),
        "src/clones_bad.rs": perf(7, 1, split=r"^// (BAD|GOOD|Arc clone)"),
        "src/clones_good.rs": perf(7, 2, split=r"^// (BAD|GOOD|Arc clone)"),
        # `let state = Arc::new(app_state);` is a statement: wrapped in a function taking app_state
        "src/clones_arc.rs": perf(7, 3, split=r"^// (BAD|GOOD|Arc clone)", glue=PERF_GLUE + "use sqlx::PgPool;")
                             + perf(7, 4, split=r"^// (BAD|GOOD|Arc clone)", glue="",
                                    before="pub fn share(app_state: AppState) {", after="}"),
        "src/small_vec.rs": perf(8),
        "src/prealloc_bad.rs": perf(9, 1),
        "src/prealloc_good.rs": perf(9, 2),
        "src/prealloc_best.rs": perf(9, 3),
        "src/stack_heap.rs": [T(PERF_GLUE), B(PERF, 10, split=r"^// (Heap|Prefer arrays)", seg=0),
                              T("pub fn heap_example() {"), B(PERF, 10, split=r"^// (Heap|Prefer arrays)", seg=1), T("}"),
                              B(PERF, 10, split=r"^// (Heap|Prefer arrays)", seg=2)],
        "src/runtime.rs": perf(11),
        "src/blocking_hash_bad.rs": perf(12, 1),
        "src/blocking_hash_good.rs": perf(12, 2),
        "src/blocking_io_bad.rs": perf(12, 3),
        "src/blocking_io_good.rs": perf(12, 4),
        "src/streams.rs": perf(13),
        "src/semaphore.rs": perf(14, glue=PERF_GLUE + "use crate::http_client::create_http_client;"),
        # module-level `let`s and spawns: wrapped in a function whose parameters are the names they use
        "src/channels.rs": [T(PERF_GLUE), B(PERF, 15, split=r"^// Bounded channel", seg=0),
                            T("pub async fn channel_sizing(events: Vec<Event>, metric_event: MetricEvent) {"),
                            B(PERF, 15, split=r"^// Bounded channel", seg=1), T("}")],
        "src/select.rs": perf(16, glue=PERF_GLUE + "use sqlx::PgPool;"),
        # a statement excerpt of a repository method
        "src/prepared.rs": perf(17, before="impl OrderRepo {\n    pub async fn recent_by_status(&self, tenant_id: &str, status: OrderStatus, "
                                           "limit: usize) -> Result<Vec<Order>, AppError> {",
                                after="        Ok(orders)\n    }\n}"),
        "src/batch_insert.rs": perf(18, glue=PERF_GLUE + "use sqlx::PgPool;"),
        "src/replicas.rs": perf(19, glue=PERF_GLUE + "use sqlx::{postgres::PgPoolOptions, PgPool};"),
        "src/caching.rs": perf(20),
        "src/n_plus_one_bad.rs": perf(21, 1, glue=PERF_GLUE + "use sqlx::PgPool;"),
        "src/n_plus_one_join.rs": perf(21, 2, glue=PERF_GLUE + "use sqlx::PgPool;"),
        "src/n_plus_one_batch.rs": perf(21, 3, glue=PERF_GLUE + "use std::collections::HashMap;\nuse sqlx::PgPool;"),
        "benches/order_benchmarks.rs": [T("use archetype_performance::app::Order;\nuse archetype_performance::cow::normalize_tenant_id;"),
                                        B(PERF, 22)],
        "src/bin/dhat_heap.rs": [B(PERF, 23)],
        "src/console.rs": perf(24),
        "src/timing.rs": perf(25),
        "src/dispatch_dyn.rs": perf(26, 1),
        "src/dispatch_generic.rs": perf(26, 2),
        "src/dispatch_enum.rs": perf(26, 3, glue="use crate::app::{Event, OrderCreatedHandler, PaymentReceivedHandler, ShipmentDispatchedHandler};"),
        "src/inline_fn.rs": perf(27, 1, split=r"^// (GOOD|BAD)"),
        "src/inline_accessor.rs": perf(27, 2, split=r"^// (GOOD|BAD)", before="impl Account {", after="}"),
        "src/inline_bad.rs": perf(27, 3, split=r"^// (GOOD|BAD)", before="impl Account {", after="}",
                                  subs=[("// ... 50 lines of logic ...", "todo!() // ... 50 lines of logic ...", 1)]),
        "src/phf_lookup.rs": perf(28),
        "src/format_bad.rs": perf(29, 1),
        "src/format_itoa.rs": perf(29, 2),
        "src/format_write.rs": perf(29, 3),
        "src/soa.rs": [T(PERF_GLUE + "use uuid::Uuid;"), B(PERF, 30, split=r"^(let orders|// GOOD)", seg=0),
                       T("pub fn aos_example() {"),
                       B(PERF, 30, split=r"^(let orders|// GOOD)", seg=1, subs=[("/* ... */", "Vec::new() /* ... */", 1)]),
                       T("}"), B(PERF, 30, split=r"^(let orders|// GOOD)", seg=2)],
    }, bins=["dhat_heap"], benches=["order_benchmarks"],
       # the doc's DHAT manifest: dhat-heap = ["dep:dhat"]; dhat is always a dependency here
       features={"dhat-heap": []}),

    Unit("lang-rust", "languages/rust.md as crate `yourapp` (its Project Structure): errors, envelope, axum handlers, "
                      "extractor, tower stack, domain types, tenant-filtered keyset queries, repository, pool, "
                      "transaction, mocks, fixtures, async patterns, two binaries, the testcontainers test "
                      "(+ harness smoke and DB tests)", {
        "src/lib.rs": [T("""
pub mod anyhow_run;
pub mod app; // harness stubs: names the snippets call but the doc never defines
pub mod axum_error; // frameworks/axum.md "Error Handling": request_id_middleware, which "Tower Middleware" layers
pub mod domain;
pub mod error;
pub mod extractors;
pub mod handlers;
pub mod join;
pub mod middleware;
pub mod perf;
pub mod pool;
pub mod repositories;
pub mod response;
pub mod select;
pub mod services;
pub mod state;
pub mod streams;
pub mod tenancy;
""")],
        "src/app.rs": [S("lang_app.rs")],
        # the pack shows several files' worth in one page: error types, the envelope, the extractor, handlers
        "src/error.rs": [T("use crate::response::current_request_id;"), B(LANG, 1), B(LANG, 3), B(LANG, 5)],
        "src/response.rs": [B(LANG, 4)],
        "src/axum_error.rs": [B(AXUM, 4)],
        "src/extractors.rs": [T("use crate::error::DomainError;"), B(LANG, 7)],
        "src/handlers.rs": [T("""
use crate::app::*;
use crate::domain::{CreateOrderRequest, OrderResponse};
use crate::error::{DomainError, FieldError};
use crate::extractors::{PaginationParams, TenantId};
use crate::response::ApiResponse;
"""), B(LANG, 6), S("lang_smoke.rs")],
        "src/anyhow_run.rs": [T("use crate::app::{load_config, serve};"), B(LANG, 2)],
        "src/middleware.rs": [T("""
use crate::app::{auth_middleware, user_routes, AppState};
use crate::axum_error::request_id_middleware;
use crate::error::DomainError;
use crate::extractors::{Claims, TenantId};
use crate::handlers::order_routes;
"""), B(LANG, 9), S("lang_mw_smoke.rs")],
        "src/tenancy.rs": [T("""
use axum::{extract::State, http::StatusCode, response::IntoResponse, Json};

use crate::app::AppState;
use crate::domain::{CreateOrderRequest, OrderResponse};
use crate::error::DomainError;
use crate::extractors::TenantId;
use crate::response::ApiResponse;
"""), B(LANG, 10)],
        # src/domain/mod.rs: the entities block, the DTOs it leaves out, and the #[cfg(test)] fixtures
        "src/domain/mod.rs": [T("use crate::error::DomainError;"), B(LANG, 11), S("lang_domain.rs"), B(LANG, 18)],
        "src/repositories/mod.rs": [T("use crate::domain::{CreateOrderRequest, Order, OrderStatus};\n"
                                      "use crate::error::{DomainError, FieldError};"),
                                    B(LANG, 12), B(LANG, 13), B(LANG, 15)],
        "src/pool.rs": [B(LANG, 14)],
        "src/services/mod.rs": [T("""
use std::sync::Arc;

use uuid::Uuid;

use crate::domain::{CreateOrderRequest, Order};
use crate::error::DomainError;
#[cfg(test)]
use crate::domain::test_helpers::{valid_request, ORDER_ID, TENANT_ID};
#[cfg(test)]
use crate::domain::OrderStatus;

mod order_tests;
"""), B(LANG, 17), S("lang_service.rs")],
        "src/services/order_tests.rs": [T("#[allow(unused_imports)]\nuse super::*;"), B(LANG, 16)],
        "src/perf.rs": [T("""
use serde::Serialize;

use crate::app::{EmailNotification, PushNotification, SmsNotification};
use crate::domain::{Order, OrderStatus};
"""), B(LANG, 20)],
        "src/state.rs": [T("use crate::app::{process_job, CachedValue, Job};\nuse crate::services::OrderService;"), B(LANG, 21)],
        "src/select.rs": [T("use crate::app::{fetch, handle_connection, Response};\nuse crate::error::DomainError;"), B(LANG, 23)],
        "src/join.rs": [T("use uuid::Uuid;\n\nuse crate::app::{ProfileService, UserProfile};\nuse crate::error::DomainError;"), B(LANG, 24)],
        "src/streams.rs": [T("use crate::app::{process_item, Item, ProcessedItem};\nuse crate::error::DomainError;"), B(LANG, 25)],
        "src/bin/tuned_runtime.rs": [T("use yourapp::app::run_server;\nuse yourapp::error::DomainError;"), B(LANG, 22)],
        "src/bin/graceful_shutdown.rs": [T("""
use std::time::Duration;

use anyhow::Context;
use tokio::net::TcpListener;
use yourapp::pool::connect_pool;
use yourapp::select::run_server;
"""), B(LANG, 26)],
        "tests/integration/main.rs": [B(LANG, 19)],
        "tests/harness_db.rs": [S("lang_db_tests.rs")],
    }, lib_name="yourapp", bins=["tuned_runtime", "graceful_shutdown"], migrations=True, schema="lang",
       tests=("db", "docker")),

    Unit("axum-pack", "frameworks/axum.md: AppError envelope, request id, rejection-mapping extractors, and its bad-path test", {
        "src/lib.rs": [T("""
pub mod app; // harness stubs: config, JWT service, the widget handlers, test helpers
pub mod auth;
pub mod error;
pub mod extractor_examples;
pub mod response;
pub mod router;
pub mod serve;
pub mod state;
""")],
        "src/app.rs": [S("axum_app.rs")],
        # ApiResponse and the REQUEST_ID task-local its success envelope reads (languages/rust.md)
        "src/response.rs": [B(LANG, 4)],
        "src/error.rs": [B(AXUM, 4), B(AXUM, 8)],
        "src/router.rs": [T("""
use crate::app::{create_widget, delete_widget, get_widget, list_widgets, recovery_middleware, update_widget, user_routes};
use crate::auth::auth_middleware;
use crate::error::{request_id_middleware, AppError};
use crate::state::AppState;
"""), B(AXUM, 1)],
        # signatures only: the `{ .. }` bodies are the doc's placeholders
        "src/extractor_examples.rs": [T("use axum::http::StatusCode;\n\nuse crate::app::{CreateInput, ListParams, UpdateInput};\n"
                                        "use crate::state::AppState;"),
                                      B(AXUM, 2, subs=[("{ .. }", "{ StatusCode::NOT_IMPLEMENTED }", 5)])],
        "src/auth.rs": [T("use crate::error::AppError;\nuse crate::state::AppState;"), B(AXUM, 3)],
        "src/state.rs": [T("use crate::app::{AppConfig, JwtService};\nuse crate::router::build_router;"), B(AXUM, 5)],
        "src/serve.rs": [B(AXUM, 6)],
        "tests/router_test.rs": [T("""
use std::sync::Arc;

use archetype_axum_pack::app::{seed_widget, test_app_state, test_token};
use archetype_axum_pack::router::build_router;
"""), B(AXUM, 7)],
        "tests/harness_smoke.rs": [S("axum_smoke.rs")],
    }, tests=()),

    Unit("actix", "frameworks/actix-web.md (+ languages/rust.md's actix handler): server setup, routes, extractors, "
                  "AuthUser, middleware fns, token-verifying auth middleware, ResponseError envelope + request id, "
                  "pools, extractor configs, its tests (+ harness smoke tests)", {
        "src/lib.rs": [T("""
pub mod app; // harness stubs: config loader, widget handlers, order service, test helpers
pub mod auth;
pub mod config;
pub mod error;
pub mod extractor_examples;
pub mod lang_orders;
pub mod middleware;
pub mod pools;
pub mod response;
pub mod routes;
pub mod state;
""")],
        "src/app.rs": [S("actix_app.rs")],
        # ApiResponse and the REQUEST_ID task-local its success envelope reads (languages/rust.md)
        "src/response.rs": [B(LANG, 4)],
        # "App & HttpServer Setup" shows the state type and main.rs together: the struct is the library's
        "src/state.rs": [T("use crate::app::AppConfig;\nuse crate::auth::middleware::JwtService;"),
                         B(ACTIX, 1, split=ACTIX_MAIN, seg=0)],
        "src/bin/server.rs": [T("""
use actix_web::{middleware, web, App, HttpServer};
use archetype_actix::app::AppConfig;
use archetype_actix::auth::middleware::JwtService;
use archetype_actix::config::{json_config, path_config, query_config};
use archetype_actix::error::request_id;
use archetype_actix::middleware::{access_log, cors};
use archetype_actix::routes::api_config;
use archetype_actix::state::AppState;
use sqlx::PgPool;
"""), B(ACTIX, 1, split=ACTIX_MAIN, seg=1)],
        "src/routes.rs": [T("""
use actix_web::web;

use crate::app::{create_widget, delete_widget, get_widget, list_widgets, update_widget};
use crate::auth::middleware::AuthMiddleware;
#[cfg(test)]
use crate::app::{seed_widget, test_app_state, test_token};
#[cfg(test)]
use crate::config::{json_config, path_config};
#[cfg(test)]
use crate::error::request_id;
"""), B(ACTIX, 2), B(ACTIX, 9)],
        # signatures only: `// ...` is the doc's placeholder for each body
        "src/extractor_examples.rs": [T("use crate::app::{CreateInput, UpdateInput};\nuse crate::state::AppState;"),
                                      B(ACTIX, 3, subs=[("    // ...", "    todo!() // ...", 5)])],
        "src/auth/mod.rs": [T("pub mod extractor;\npub mod middleware;")],
        "src/auth/extractor.rs": [T("use crate::error::AppError;"), B(ACTIX, 4)],
        "src/auth/middleware.rs": [T("use crate::auth::extractor::AuthUser;\nuse crate::error::AppError;\nuse crate::state::AppState;"),
                                   B(ACTIX, 6)],
        "src/middleware.rs": [B(ACTIX, 5)],
        "src/error.rs": [B(ACTIX, 7)],
        "src/pools.rs": [B(ACTIX, 8)],
        "src/config.rs": [T("use crate::error::{AppError, FieldError};"), B(ACTIX, 10)],
        "src/lang_orders.rs": [T("""
use crate::app::{create_order, list_orders, OrderResponse, OrderService};
use crate::auth::{extractor::AuthUser, middleware::AuthMiddleware};
use crate::error::AppError;
use crate::response::ApiResponse;
"""), B(LANG, 8)],
        "tests/harness_smoke.rs": [S("actix_smoke.rs")],
    }, bins=["server"], tests=()),

    Unit("graphql", "frameworks/graphql.md (Rust block): async-graphql resolvers with the archetypes' AppError "
                    "(+ harness smoke tests: `first` bounds, errors reach clients as code + safe message)", {
        "src/lib.rs": [T("pub mod app; // harness stubs: schema types, loader, service\npub mod error;\npub mod resolvers;")],
        "src/app.rs": [S("graphql_app.rs")],
        "src/error.rs": blocks(EH, 1, 2, 3, 4, 5, 6, 7),
        "src/resolvers.rs": [T("use crate::app::{AuthContext, QueryRoot, User, UserLoader, Widget, WidgetConnection, "
                               "WidgetFilter, WidgetService};\nuse crate::error::AppError;"),
                             B(GQL, 1), S("graphql_smoke.rs")],
    }, tests=()),

    Unit("external-service-mocks", "testing/external-service-mocks.md (Rust block): the wiremock test against a "
                                   "minimal real reqwest StripeClient", {
        "src/lib.rs": [T("pub mod stripe; // harness stub: the client under test\n#[cfg(test)]\nmod wiremock_test;")],
        "src/stripe.rs": [S("stripe_client.rs")],
        "src/wiremock_test.rs": [T("use crate::stripe::StripeClient;"), B(MOCKS, 1)],
    }, tests=()),

    Unit("property-based", "testing/property-based.md (Rust blocks): proptest and quickcheck properties", {
        "src/lib.rs": [T("pub mod app; // harness stubs: the code the properties are about\n"
                         "#[cfg(test)]\nmod proptests;\n#[cfg(test)]\nmod quickchecks;")],
        "src/app.rs": [S("property_app.rs")],
        "src/proptests.rs": [T("use crate::app::{paginate, Widget};"), B(PROP, 1)],
        "src/quickchecks.rs": [T("use crate::app::{decode, encode};"), B(PROP, 2)],
    }, tests=()),

    Unit("crud-service", "crud-service-rust.md as one module (domain types + traits + WidgetService), with error.rs, Widget and the handler DTOs", {
        "src/lib.rs": [T("pub mod dto;\npub mod error;\npub mod harness;\npub mod models;\npub mod service;")],
        "src/error.rs": blocks(EH, 1, 2, 3, 4, 5, 6, 7),
        "src/models.rs": [B(REPO, 13)],
        # the DTO block lives in the handler module, next to the envelope types that import Serialize
        "src/dto.rs": [T("use serde::Serialize;\nuse uuid::Uuid;\n\nuse crate::error::AppError;"), B(HANDLER, 8)],
        "src/harness.rs": [S("service_harness.rs")],
        "src/service.rs": [T("""
use crate::dto::{CreateWidgetInput, UpdateWidgetInput};
use crate::harness::CreateWithRelationsInput;
use crate::models::{Widget, WidgetStatus};
""")] + blocks(SVC, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12),
    }),
]
