#!/usr/bin/env bash
# skills-security.test.sh — the skill packs, security/reliability agents and /autonomous say what the
# 2026-09-30 board review fixed: one API envelope (ARCH-01/DEV-03), no tokens in web storage or WS URLs
# (SEC-08), rendering-layer XSS (SEC-09), SAST/secrets with fixed commands and no eval (SEC-13), secret
# patterns that catch a compiled-in default (SEC-10), idempotent-only retries and dependency-free
# readiness (SRE-03/05), route-template metric labels (SRE-04), no forced security findings in
# /autonomous (SEC-01), the data-not-instructions contract rule (SEC-03), offline dependency vetting
# (SEC-02), and threat-model TC-SEC rows the inventory parses (SEC-06).
# Run: bash tests/skills-security.test.sh   (exit 0 = pass; bash 3.2 compatible; no network)
set -uo pipefail
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$TEST_DIR/lib/skills_security_cases.py"
