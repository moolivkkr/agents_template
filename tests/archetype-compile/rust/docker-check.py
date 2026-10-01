#!/usr/bin/env python3
# ruff: noqa: E501
# flake8: noqa
"""Build the Rust Dockerfiles of dockerfile-rust.md and performance-rust.md for real, run each image,
and check it (run via docker-check.sh; needs Docker and network access for the base images and crates).

  1. Assembles a build context under target/docker-context from the docs: the minimal service in
     docker/ (axum, sqlx with rustls, a query! macro, embedded migrations), dockerfile-rust.md's
     rust-toolchain.toml, .dockerignore and [profile.release], migration-pattern-rust.md's migrations,
     the harness .sqlx/ cache, and one Dockerfile per units.DOCKERFILES entry (verbatim, or a variant
     composed from a fragment). docker/Cargo.lock must match the manifest (--update-lock regenerates
     it from the harness Cargo.lock, so the image builds the versions the samples were checked with).
  2. Per Dockerfile: `docker build`; the image's USER is numeric; `docker run` it; the process runs as
     that uid (docker top); GET /healthz answers 200 {"status":"ok"}; /api/version reports the
     GIT_SHA build arg (where the Dockerfile declares one); the HEALTHCHECK (where present) turns
     healthy. Then the container is removed (the image is kept, so a re-run is cached).

Prints PASS/FAIL per Dockerfile; exits non-zero on any failure.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import harness  # noqa: E402
import units as cfg  # noqa: E402

CTX = os.path.join(harness.TARGET, "docker-context")
LOGS = os.path.join(harness.TARGET, "docker-logs")
GIT_SHA = "harness-check"


def sh(*cmd, **kw):
    return subprocess.run(list(cmd), capture_output=True, text=True, **kw)


def block_text(blocks, doc, lang, idx):
    try:
        return harness.block_text(blocks, doc, lang, idx)
    except ValueError as e:
        raise SystemExit(str(e))


def dockerfiles(blocks):
    out, problems = harness.docker_variants(blocks)
    if problems:
        raise SystemExit("\n".join(problems))
    return out


def assemble(blocks, update_lock):
    shutil.rmtree(CTX, ignore_errors=True)
    shutil.copytree(os.path.join(HERE, "docker"), CTX)
    toolchain = next(block_text(blocks, f, "toml", i) for (f, i), k in cfg.TOML.items() if k == "toolchain")
    open(os.path.join(CTX, "rust-toolchain.toml"), "w").write(toolchain)
    profile = block_text(blocks, "dockerfile-rust", "toml", 2)
    with open(os.path.join(CTX, "Cargo.toml"), "a") as f:
        f.write("\n# --- dockerfile-rust.md, Cargo.toml Release Profile ---\n" + profile)
    open(os.path.join(CTX, ".dockerignore"), "w").write(block_text(blocks, "dockerfile-rust", "dockerignore", 1))
    os.makedirs(os.path.join(CTX, "migrations"))
    for name, sql in harness.migrations_from_doc(blocks, cfg.SCHEMAS["default"]["migrations"]).items():
        open(os.path.join(CTX, "migrations", name), "w").write(sql)
    shutil.copytree(harness.SQLX_DIR, os.path.join(CTX, ".sqlx"))
    for name, text in dockerfiles(blocks).items():
        open(os.path.join(CTX, f"Dockerfile.{name}"), "w").write(text)
    env = harness.cargo_env()
    env["CARGO_TARGET_DIR"] = os.path.join(harness.TARGET, "docker-lock")
    if update_lock:
        shutil.copyfile(os.path.join(HERE, "Cargo.lock"), os.path.join(CTX, "Cargo.lock"))
        proc = sh("cargo", "metadata", "--format-version", "1", cwd=CTX, env=env)
        if proc.returncode != 0:
            raise SystemExit("cargo metadata (lock update) failed:\n" + proc.stderr)
        shutil.copyfile(os.path.join(CTX, "Cargo.lock"), os.path.join(HERE, "docker", "Cargo.lock"))
    proc = sh("cargo", "metadata", "--format-version", "1", "--locked", cwd=CTX, env=env)
    if proc.returncode != 0:
        raise SystemExit("docker/Cargo.lock is out of date with docker/Cargo.toml (run with --update-lock):\n" + proc.stderr[-800:])
    # fail fast on the service itself, before any docker build (sqlx offline, like the Dockerfiles)
    proc = sh("cargo", "check", "--locked", "--bins", cwd=CTX, env=env)
    if proc.returncode != 0:
        raise SystemExit("the docker/ service does not compile:\n" + proc.stderr[-3000:])
    # the image builds the versions the samples were compile-checked with
    pinned = harness.registry_packages(os.path.join(HERE, "Cargo.lock"))
    drift = sorted(p for p in harness.registry_packages(os.path.join(CTX, "Cargo.lock")) if p[0] in {n for n, _ in pinned} and p not in pinned)
    if drift:
        raise SystemExit("docker/Cargo.lock pins versions the harness Cargo.lock doesn't: " + ", ".join(f"{n} {v}" for n, v in drift[:10]))


def wait_http(url, timeout):
    deadline, last = time.time() + timeout, None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                return resp.status, resp.read().decode()
        except Exception as e:  # noqa: BLE001 - connection refused while the server starts
            last = e
            time.sleep(0.5)
    return None, str(last)


def check_image(name, path, no_cache, platform):
    tag = f"archetype-rust:{name}" + (f"-{platform.replace('/', '-')}" if platform else "")
    os.makedirs(LOGS, exist_ok=True)
    log_path = os.path.join(LOGS, f"{name}{'-' + platform.replace('/', '-') if platform else ''}.log")
    t0 = time.time()
    extra = (["--no-cache"] if no_cache else []) + (["--platform", platform] if platform else [])
    with open(log_path, "w") as log:
        proc = subprocess.run(["docker", "build", "--progress=plain", "-f", path, "-t", tag,
                               "--build-arg", f"GIT_SHA={GIT_SHA}"] + extra + [CTX],
                              stdout=log, stderr=subprocess.STDOUT)
    build_secs = time.time() - t0
    if proc.returncode != 0:
        tail = open(log_path).read().splitlines()[-25:]
        return False, [f"docker build failed ({build_secs:.0f}s), log: {log_path}"] + ["    " + l for l in tail]
    notes, ok = [f"built in {build_secs:.0f}s"], True
    info = json.loads(sh("docker", "image", "inspect", tag).stdout)[0]
    notes.append(f"platform {info.get('Os')}/{info.get('Architecture')}")
    if platform and f"{info.get('Os')}/{info.get('Architecture')}" != platform:
        ok = False
        notes.append(f"FAIL asked for {platform}")
    user = info["Config"].get("User") or ""
    size = sh("docker", "images", "--format", "{{.Size}}", tag).stdout.strip() or "?"  # unpacked, as `docker images` shows
    notes.append(f"image {size}, USER {user or '(none: root)'}")
    if not re.fullmatch(r"\d+(:\d+)?", user):
        ok = False
        notes.append("FAIL the image's USER is not numeric (a named or missing user fails Kubernetes runAsNonRoot)")
    healthcheck = (info["Config"].get("Healthcheck") or {}).get("Test")
    run = ["docker", "run", "-d", "-p", "127.0.0.1::8080"] + (["--platform", platform] if platform else [])
    if healthcheck:  # the image's own check, polled faster than its 30s interval
        run += ["--health-interval", "2s", "--health-start-period", "2s"]
    cid = sh(*run, tag).stdout.strip()
    if not cid:
        return False, notes + ["FAIL docker run did not start a container"]
    try:
        port = sh("docker", "port", cid, "8080/tcp").stdout.strip().splitlines()[0].rsplit(":", 1)[1]
        status, body = wait_http(f"http://127.0.0.1:{port}/healthz", 30)
        if status == 200 and json.loads(body or "{}").get("status") == "ok":
            notes.append(f"GET /healthz -> 200 {body.strip()}")
        else:
            ok = False
            notes.append(f"FAIL GET /healthz -> {status} {body[:200]}")
            notes.append("    container log: " + sh("docker", "logs", cid).stdout[-500:])
        # docker top runs ps in the container's pid namespace view; it insists on a PID column
        top = sh("docker", "top", cid, "-eo", "pid,uid,gid,comm").stdout.strip().splitlines()
        procs = [l.split()[1:] for l in top[1:]]
        want_uid = user.split(":")[0]
        if procs and all(p[0] == want_uid for p in procs):
            notes.append(f"process runs as uid:gid {procs[0][0]}:{procs[0][1]} ({procs[0][2]})")
        else:
            ok = False
            notes.append(f"FAIL processes run as {procs}, image USER {user}")
        if "ARG GIT_SHA" in open(path).read():
            status, body = wait_http(f"http://127.0.0.1:{port}/api/version", 5)
            if status == 200 and json.loads(body).get("git_sha") == GIT_SHA:
                notes.append(f"GIT_SHA build arg reaches the app ({GIT_SHA})")
            else:
                ok = False
                notes.append(f"FAIL /api/version -> {status} {body[:200]}")
        if healthcheck:
            deadline, health = time.time() + 60, ""
            while time.time() < deadline:
                health = sh("docker", "inspect", "-f", "{{.State.Health.Status}}", cid).stdout.strip()
                if health in ("healthy", "unhealthy"):
                    break
                time.sleep(1)
            if health == "healthy":
                notes.append("HEALTHCHECK -> healthy")
            else:
                ok = False
                notes.append(f"FAIL HEALTHCHECK -> {health or 'no status'}")
        else:
            notes.append("no HEALTHCHECK in this image: /healthz is probed from outside (as above)")
    finally:
        sh("docker", "rm", "-f", cid)
    return ok, notes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", help="build only these (units.DOCKERFILES names)")
    ap.add_argument("--update-lock", action="store_true", help="regenerate docker/Cargo.lock from the harness Cargo.lock")
    ap.add_argument("--assemble-only", action="store_true", help="write the build context and stop")
    ap.add_argument("--no-cache", action="store_true", help="docker build --no-cache: every layer from scratch")
    ap.add_argument("--platform", help="build and run for this platform (e.g. linux/amd64 on an arm64 host, emulated)")
    args = ap.parse_args()

    blocks = harness.load_blocks()
    assemble(blocks, args.update_lock)
    print(f"ok   build context: {CTX}")
    if args.assemble_only:
        return 0
    if sh("docker", "info").returncode != 0:
        print("FAIL Docker is not running")
        return 2
    results = []
    for name in cfg.DOCKERFILES:
        if args.only and name not in args.only:
            continue
        ok, notes = check_image(name, os.path.join(CTX, f"Dockerfile.{name}"), args.no_cache, args.platform)
        results.append(ok)
        doc, idx, subs = cfg.DOCKERFILES[name]
        what = f"{doc}.md dockerfile #{idx}" + (" + the cache-mount fragment" if subs else "")
        print(f"{'PASS' if ok else 'FAIL'} {name:20} ({what})")
        for n in notes:
            print("     " + n)
    print(f"\nDockerfiles: {sum(results)} PASS / {len(results) - sum(results)} FAIL")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
