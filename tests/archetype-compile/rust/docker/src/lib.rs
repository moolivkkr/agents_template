//! HARNESS-ONLY minimal service for docker-check.py: just enough of a real Rust service that the
//! Dockerfile archetypes have something representative to build — axum, sqlx with rustls, a
//! compile-time-checked query (needs .sqlx/ and SQLX_OFFLINE), embedded migrations (need migrations/)
//! — and the runtime contract the images are checked against: /healthz (liveness, no dependencies),
//! /readyz (the database), /api/version (GIT_SHA). Stops on SIGTERM (it runs as PID 1).
use axum::{
    extract::{Path, State},
    http::StatusCode,
    routing::get,
    Json, Router,
};
use serde_json::{json, Value};
use sqlx::{postgres::PgPoolOptions, PgPool};

/// Embedded at compile time, so the build needs migrations/ in the context.
pub static MIGRATOR: sqlx::migrate::Migrator = sqlx::migrate!("./migrations");

#[derive(Clone)]
struct AppState {
    db: Option<PgPool>,
    binary: &'static str,
}

pub async fn serve(binary: &'static str) -> Result<(), Box<dyn std::error::Error>> {
    let db = match std::env::var("DATABASE_URL") {
        Ok(url) => Some(PgPoolOptions::new().connect_lazy(&url)?),
        Err(_) => None,
    };
    let app = Router::new()
        .route("/healthz", get(|| async { Json(json!({ "status": "ok" })) }))
        .route("/readyz", get(readyz))
        .route("/api/version", get(version))
        .route("/api/v1/widgets/{id}/deleted-at", get(deleted_at))
        .with_state(AppState { db, binary });
    let listener = tokio::net::TcpListener::bind("0.0.0.0:8080").await?;
    axum::serve(listener, app).with_graceful_shutdown(shutdown()).await?;
    Ok(())
}

async fn readyz(State(state): State<AppState>) -> (StatusCode, Json<Value>) {
    let ok = match &state.db {
        Some(db) => sqlx::query("SELECT 1").execute(db).await.is_ok(),
        None => false,
    };
    let status = if ok { StatusCode::OK } else { StatusCode::SERVICE_UNAVAILABLE };
    (status, Json(json!({ "status": if ok { "ok" } else { "unavailable" } })))
}

async fn version(State(state): State<AppState>) -> Json<Value> {
    Json(json!({ "git_sha": std::env::var("GIT_SHA").unwrap_or_default(), "binary": state.binary }))
}

async fn deleted_at(State(state): State<AppState>, Path(id): Path<uuid::Uuid>) -> Result<Json<Value>, StatusCode> {
    let db = state.db.as_ref().ok_or(StatusCode::SERVICE_UNAVAILABLE)?;
    let row = sqlx::query!("SELECT deleted_at FROM widgets WHERE id = $1", id)
        .fetch_optional(db)
        .await
        .map_err(|_| StatusCode::SERVICE_UNAVAILABLE)?
        .ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(json!({ "deleted_at": row.deleted_at })))
}

async fn shutdown() {
    let mut sigterm = tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
        .expect("register SIGTERM handler");
    tokio::select! {
        _ = tokio::signal::ctrl_c() => {}
        _ = sigterm.recv() => {}
    }
}
