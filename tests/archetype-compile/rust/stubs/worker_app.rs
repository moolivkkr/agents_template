// HARNESS STUBS — the app-specific pieces worker-pattern-rust.md's main.rs and EmailSendHandler use.
// No archetype defines them. The Queue / IdempotencyStore / JobHandler implementations here are
// empty on purpose: the doc's Worker, traits and handler are what is being compiled.
#![allow(dead_code)]
use std::collections::HashMap;
use std::sync::Arc;
use std::time::Duration;

use async_trait::async_trait;
use serde::Deserialize;

use crate::worker::job::Job;
use crate::worker::traits::{IdempotencyStore, JobHandler, Queue, WorkerError};

pub struct Settings {
    pub redis_url: String,
}

impl Settings {
    pub fn from_env() -> anyhow::Result<Self> {
        Ok(Self { redis_url: std::env::var("REDIS_URL")? })
    }
}

pub struct RedisQueue;

impl RedisQueue {
    pub async fn new(_url: &str) -> anyhow::Result<Self> {
        Ok(Self)
    }
}

#[async_trait]
impl Queue for RedisQueue {
    async fn receive(&self, _timeout: Duration) -> Result<Option<Job>, WorkerError> {
        Ok(None)
    }
    async fn ack(&self, _job: &Job) -> Result<(), WorkerError> {
        Ok(())
    }
    async fn nack(&self, _job: &Job, _retry_after: Duration) -> Result<(), WorkerError> {
        Ok(())
    }
    async fn send_to_dlq(&self, _job: &Job, _reason: &str) -> Result<(), WorkerError> {
        Ok(())
    }
    async fn health_check(&self) -> Result<(), WorkerError> {
        Ok(())
    }
}

pub struct RedisIdempotency;

impl RedisIdempotency {
    pub async fn new(_url: &str) -> anyhow::Result<Self> {
        Ok(Self)
    }
}

#[async_trait]
impl IdempotencyStore for RedisIdempotency {
    async fn is_processed(&self, _job_id: &str) -> Result<bool, WorkerError> {
        Ok(false)
    }
    async fn mark_processed(&self, _job_id: &str, _ttl: Duration) -> Result<(), WorkerError> {
        Ok(())
    }
}

#[derive(Debug, thiserror::Error)]
#[error("email service error")]
pub struct EmailError;

pub struct EmailService;

impl EmailService {
    pub fn new(_settings: &Settings) -> Self {
        Self
    }
    pub async fn render_template(&self, _template_id: &str, _vars: &HashMap<String, String>) -> Result<String, EmailError> {
        Ok(String::new())
    }
    pub async fn send(&self, _to: &str, _subject: &str, _html: &str) -> Result<(), EmailError> {
        Ok(())
    }
}

#[derive(Debug, Deserialize)]
pub struct EmailPayload {
    pub to: String,
    pub subject: String,
    pub template_id: String,
    pub variables: HashMap<String, String>,
}

pub struct ReportService;

impl ReportService {
    pub fn new(_settings: &Settings) -> Self {
        Self
    }
}

pub struct ReportGenerateHandler {
    _svc: Arc<ReportService>,
}

impl ReportGenerateHandler {
    pub fn new(svc: Arc<ReportService>) -> Self {
        Self { _svc: svc }
    }
}

#[async_trait]
impl JobHandler for ReportGenerateHandler {
    fn job_type(&self) -> &str {
        "report.generate"
    }
    async fn handle(&self, _job: &Job) -> Result<(), WorkerError> {
        Ok(())
    }
}
