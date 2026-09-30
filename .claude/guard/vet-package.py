#!/usr/bin/env python3
"""vet-package.py — vet a NEW dependency before a coding agent adds it (board review 2026-09-30, SEC-02).

Package installs stay pre-allowed (the owner decided build downloads need no prompt), so the defence
against hallucinated ("slopsquatted") and typosquatted names is this check, run BEFORE the name goes
into a manifest or lockfile. For each name it asks the ecosystem's public registry:

  1. exists      — the package/module is published (a hallucinated name usually isn't, or is brand new)
  2. age         — first publish is at least --min-age-days old (default 30)
  3. downloads   — at least --min-weekly-downloads last week (default 500; npm, PyPI via pypistats,
                   crates.io's 90-day count / 13). Go has no public download counts: age + name only.
  4. name        — not within a small edit distance of a popular package it isn't (typosquat), and not
                   a separator/case variant of one ("lo-dash", "python_dateutil" on npm, ...)
  5. state       — not deprecated (npm) or yanked (crates.io)
  Warnings (printed, not failing): npm install scripts (preinstall/install/postinstall, node-gyp) — install
  with lifecycle scripts disabled (`npm ci --ignore-scripts`) and run needed builds explicitly.

Usage:
  vet-package.py -e npm left-pad @scope/pkg@1.2.3
  vet-package.py -e pypi "requests>=2" python-dateutil
  vet-package.py -e go github.com/gin-gonic/gin@v1.10.0
  vet-package.py -e crates serde
Options: --min-age-days N  --min-weekly-downloads N  --json  --now YYYY-MM-DD
         --offline FIXTURE.json   (tests: a {url: response|null} map; null = 404; no network at all)
         --popular FILE.json      (extra {"npm": [...], ...} names to treat as popular)
Exit: 0 every package passed; 1 at least one failed (reasons printed); 2 usage error or a registry
could not be reached — an unverifiable package is NOT vetted.

A package that fails but is genuinely intended (a niche library, a fresh internal one) is recorded in
the agent's manifest `new_dependencies[]` with the vet output and the reason, for the human/reviewer to
approve — the agent never installs it on its own say-so.
"""
import argparse, datetime as dt, json, re, sys, urllib.error, urllib.parse, urllib.request

UA = "startup-agents-vet-package/1.0 (dependency vetting before install)"

# Popular names per ecosystem: the targets typosquats imitate. Extend with --popular.
POPULAR = {
    "npm": """react react-dom react-router react-router-dom react-native next vue nuxt svelte angular @angular/core
      lodash underscore ramda axios node-fetch got superagent request express koa fastify hapi body-parser cors
      helmet morgan cookie-parser multer jsonwebtoken bcrypt bcryptjs passport dotenv debug chalk colors
      commander yargs minimist inquirer ora execa glob rimraf mkdirp fs-extra cross-env nodemon ts-node
      typescript tslib @types/node @types/react webpack vite rollup esbuild parcel babel-loader @babel/core
      core-js eslint prettier jest vitest mocha chai sinon supertest nock msw playwright @playwright/test
      puppeteer cypress uuid nanoid moment dayjs date-fns luxon zod yup joi ajv qs semver async bluebird
      rxjs redux @reduxjs/toolkit react-redux zustand swr @tanstack/react-query formik react-hook-form
      classnames clsx prop-types styled-components tailwindcss postcss autoprefixer sass socket.io
      socket.io-client ws graphql apollo-server @apollo/client mongoose mongodb pg mysql mysql2 sqlite3
      redis ioredis knex sequelize prisma @prisma/client typeorm bull bullmq kafkajs aws-sdk
      @aws-sdk/client-s3 firebase stripe twilio nodemailer winston pino handlebars ejs pug marked
      dompurify cheerio sharp jquery bootstrap d3 chart.js three electron expo lru-cache immer
      eventemitter3 form-data crypto-js left-pad is-number""".split(),
    "pypi": """requests urllib3 httpx aiohttp numpy pandas scipy matplotlib scikit-learn tensorflow torch
      django flask fastapi starlette uvicorn gunicorn pydantic sqlalchemy alembic psycopg2 psycopg2-binary
      psycopg pymysql mysqlclient pymongo redis celery boto3 botocore pytest pytest-cov pytest-asyncio
      setuptools wheel pip six python-dateutil pyyaml jinja2 click certifi idna charset-normalizer
      cryptography pyjwt bcrypt passlib attrs typing-extensions packaging pillow beautifulsoup4 lxml
      selenium openpyxl markdown pytz tzdata marshmallow tqdm rich colorama coverage mock black flake8
      mypy ruff isort pylint tox virtualenv docker kubernetes paramiko jsonschema protobuf grpcio openai
      anthropic langchain transformers websockets python-multipart orjson ujson msgpack pyarrow polars
      networkx sympy nltk spacy opencv-python pyopenssl requests-oauthlib oauthlib simplejson toml tomli
      filelock platformdirs pluggy sentry-sdk structlog loguru python-dotenv dnspython email-validator
      arrow pendulum freezegun faker factory-boy hypothesis responses""".split(),
    "go": """github.com/gin-gonic/gin github.com/gorilla/mux github.com/go-chi/chi/v5 github.com/labstack/echo/v4
      github.com/gofiber/fiber/v2 github.com/stretchr/testify github.com/jackc/pgx/v5 github.com/lib/pq
      gorm.io/gorm github.com/go-sql-driver/mysql github.com/redis/go-redis/v9 github.com/spf13/cobra
      github.com/spf13/viper github.com/sirupsen/logrus go.uber.org/zap github.com/rs/zerolog
      github.com/golang-jwt/jwt/v5 github.com/google/uuid golang.org/x/crypto golang.org/x/sync
      golang.org/x/net google.golang.org/grpc google.golang.org/protobuf github.com/prometheus/client_golang
      go.opentelemetry.io/otel github.com/aws/aws-sdk-go-v2 github.com/pressly/goose/v3
      github.com/golang-migrate/migrate/v4 github.com/testcontainers/testcontainers-go
      github.com/kelseyhightower/envconfig github.com/joho/godotenv github.com/go-playground/validator/v10
      github.com/segmentio/kafka-go github.com/nats-io/nats.go github.com/sony/gobreaker
      github.com/cenkalti/backoff/v4 github.com/pkg/errors github.com/urfave/cli/v2
      github.com/mattn/go-sqlite3 github.com/jmoiron/sqlx go.uber.org/mock github.com/DATA-DOG/go-sqlmock
      github.com/gorilla/websocket github.com/coder/websocket""".split(),
    "crates": """serde serde_json tokio reqwest rand clap anyhow thiserror log env_logger tracing
      tracing-subscriber chrono regex lazy_static once_cell futures hyper axum actix-web sqlx diesel uuid
      base64 bytes itertools rayon crossbeam parking_lot syn quote proc-macro2 libc bitflags cfg-if time
      url http tower tower-http prost tonic rustls openssl ring sha2 hex dotenvy config toml serde_yaml
      async-trait num criterion proptest mockall tempfile walkdir glob indexmap hashbrown smallvec memchr""".split(),
}
ECOS = ("npm", "pypi", "go", "crates")
NAME_RE = {
    "npm": re.compile(r"^(@[a-z0-9][a-z0-9._~-]*/)?[a-z0-9._~-][a-z0-9._~-]*$", re.I),
    "pypi": re.compile(r"^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?$"),
    "go": re.compile(r"^[A-Za-z0-9.-]+\.[A-Za-z]{2,}(/[A-Za-z0-9._~-]+)*$"),
    "crates": re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$"),
}


class Unverifiable(Exception):
    pass


def strip_version(name, eco):
    name = name.strip()
    if eco == "npm":
        at = name.find("@", 1)
        return name[:at] if at > 0 else name
    if eco == "pypi":
        return re.split(r"[\[<>=!~;@ ]", name, 1)[0]
    if eco in ("go", "crates"):
        return name.split("@", 1)[0]
    return name


def norm(name, eco):
    if eco == "pypi":
        return re.sub(r"[-_.]+", "-", name).lower()
    return name if eco == "go" else name.lower()


def osa_distance(a, b):
    """Optimal-string-alignment edit distance (insert, delete, substitute, adjacent transposition)."""
    d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        d[i][0] = i
    for j in range(len(b) + 1):
        d[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[len(a)][len(b)]


def typosquat_of(name, eco, popular):
    """The popular package this name imitates, with the distance, or (None, 0)."""
    n = norm(name, eco)
    pop = {norm(p, eco): p for p in popular}
    if n in pop:
        return None, 0
    key = lambda s: re.sub(r"[-_.]", "", s.lower())
    for pn, p in pop.items():
        if key(pn) == key(n):
            return p, 0          # separator/case variant of a popular name
    if len(n) <= 3:
        return None, 0           # too short to judge by distance
    thr = 1 if len(n) <= 6 else 2
    best = None
    for pn, p in pop.items():
        if abs(len(pn) - len(n)) > thr:
            continue
        dist = osa_distance(n, pn)
        if dist <= thr and (best is None or dist < best[1]):
            best = (p, dist)
    return best if best else (None, 0)


def parse_time(s):
    s = s.strip().replace("Z", "+00:00")
    s = re.sub(r"\.(\d{6})\d+", r".\1", s)   # Go/crates may carry nanoseconds
    t = dt.datetime.fromisoformat(s)
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


class Registry:
    def __init__(self, offline=None):
        self.offline = offline

    def get(self, url, want_json=True):
        """(status, body) where status is 200 or 404. Raises Unverifiable on anything else."""
        if self.offline is not None:
            if url not in self.offline:
                raise Unverifiable(f"offline: no fixture for {url}")
            body = self.offline[url]
            if body is None:
                return 404, None
            if want_json and isinstance(body, str):
                body = json.loads(body)
            return 200, body
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json, text/plain"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                text = r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                return 404, None
            raise Unverifiable(f"{url} returned HTTP {e.code}")
        except (urllib.error.URLError, OSError) as e:
            raise Unverifiable(f"{url} unreachable ({e})")
        return 200, (json.loads(text) if want_json else text)


def go_escape(path):
    return "".join("!" + c.lower() if c.isupper() else c for c in path)


def semver_key(v):
    m = re.match(r"^v(\d+)\.(\d+)\.(\d+)(-.*)?", v)
    if not m:
        return (10**9, 0, 0, 1, v)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), 0 if m.group(4) else 1, v)


def lookup(eco, name, reg, warnings):
    """Registry facts: {exists, created, weekly (int|None), deprecated, yanked, install_scripts}."""
    info = {"exists": False, "created": None, "weekly": None, "deprecated": None, "yanked": False, "install_scripts": []}
    if eco == "npm":
        enc = urllib.parse.quote(name, safe="@")
        st, doc = reg.get(f"https://registry.npmjs.org/{enc}")
        if st == 404:
            return info
        info["exists"] = True
        created = (doc.get("time") or {}).get("created")
        info["created"] = parse_time(created) if created else None
        latest = (doc.get("dist-tags") or {}).get("latest")
        ver = (doc.get("versions") or {}).get(latest, {}) if latest else {}
        info["deprecated"] = ver.get("deprecated")
        scripts = ver.get("scripts") or {}
        info["install_scripts"] = [k for k in ("preinstall", "install", "postinstall") if k in scripts]
        if ver.get("gypfile") or ver.get("hasInstallScript"):
            info["install_scripts"] = info["install_scripts"] or ["native build (node-gyp)"]
        try:
            st, dl = reg.get(f"https://api.npmjs.org/downloads/point/last-week/{name}")
            info["weekly"] = int((dl or {}).get("downloads", 0)) if st == 200 else 0
        except Unverifiable as e:
            warnings.append(f"download count unavailable ({e})")
    elif eco == "pypi":
        n = norm(name, eco)
        st, doc = reg.get(f"https://pypi.org/pypi/{n}/json")
        if st == 404:
            return info
        info["exists"] = True
        times = [f.get("upload_time_iso_8601") or f.get("upload_time")
                 for files in (doc.get("releases") or {}).values() for f in files]
        times = [parse_time(t) for t in times if t]
        info["created"] = min(times) if times else None
        if not times:
            warnings.append("no release files uploaded (a name reservation, or everything was deleted)")
        try:
            st, s = reg.get(f"https://pypistats.org/api/packages/{n}/recent")
            info["weekly"] = int(((s or {}).get("data") or {}).get("last_week", 0)) if st == 200 else 0
        except Unverifiable as e:
            warnings.append(f"download count unavailable ({e})")
    elif eco == "go":
        base = f"https://proxy.golang.org/{go_escape(name)}"
        st, text = reg.get(f"{base}/@v/list", want_json=False)
        versions = [v for v in (text or "").split() if v]
        if st == 404:
            return info
        if versions:
            first = sorted(versions, key=semver_key)[0]
            st, vi = reg.get(f"{base}/@v/{first}.info")
        else:
            st, vi = reg.get(f"{base}/@latest")
        if st == 404:
            return info
        info["exists"] = True
        info["created"] = parse_time(vi["Time"]) if vi and vi.get("Time") else None
        warnings.append("Go modules have no public download counts; vetted on existence, age and name only")
    elif eco == "crates":
        st, doc = reg.get(f"https://crates.io/api/v1/crates/{name}")
        if st == 404:
            return info
        c = (doc or {}).get("crate") or {}
        info["exists"] = True
        info["created"] = parse_time(c["created_at"]) if c.get("created_at") else None
        if c.get("recent_downloads") is not None:
            info["weekly"] = int(c["recent_downloads"]) // 13       # crates.io "recent" = last 90 days
        info["yanked"] = bool(c.get("yanked"))
    return info


def vet(eco, raw, reg, args, popular):
    name = strip_version(raw, eco)
    res = {"ecosystem": eco, "package": name, "verdict": "PASS", "reasons": [], "warnings": [], "facts": {}}
    if not NAME_RE[eco].match(name):
        res["verdict"] = "FAIL"
        res["reasons"].append(f"'{name}' is not a valid {eco} package name")
        return res
    squat, dist = typosquat_of(name, eco, popular)
    if squat:
        res["reasons"].append(f"possible typosquat of popular package '{squat}'"
                              + (f" (edit distance {dist})" if dist else " (same name up to separators/case)"))
    info = lookup(eco, name, reg, res["warnings"])
    if not info["exists"]:
        res["reasons"].append(f"does not exist on the {eco} registry (a hallucinated name? never install it)")
    else:
        if info["created"]:
            age = (args.now - info["created"]).days
            res["facts"]["first_published"] = info["created"].date().isoformat()
            res["facts"]["age_days"] = age
            if age < args.min_age_days:
                res["reasons"].append(f"first published {age} day(s) ago (floor {args.min_age_days})")
        else:
            res["reasons"].append("first-publish date unknown")
        if info["weekly"] is not None:
            res["facts"]["weekly_downloads"] = info["weekly"]
            if info["weekly"] < args.min_weekly_downloads:
                res["reasons"].append(f"{info['weekly']} downloads last week (floor {args.min_weekly_downloads})")
        if info["deprecated"]:
            res["reasons"].append(f"deprecated: {str(info['deprecated'])[:120]}")
        if info["yanked"]:
            res["reasons"].append("yanked")
        if info["install_scripts"]:
            res["warnings"].append("runs install scripts (" + ", ".join(info["install_scripts"])
                                   + "): install with lifecycle scripts disabled and run needed builds explicitly")
    if res["reasons"]:
        res["verdict"] = "FAIL"
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-e", "--ecosystem", required=True, choices=ECOS)
    ap.add_argument("packages", nargs="+")
    ap.add_argument("--min-age-days", type=int, default=30)
    ap.add_argument("--min-weekly-downloads", type=int, default=500)
    ap.add_argument("--offline", help="fixture JSON {url: body|null}; no network is used")
    ap.add_argument("--popular", help="extra popular names, JSON {ecosystem: [names]}")
    ap.add_argument("--now", help="evaluate ages as of this date (YYYY-MM-DD); default today (UTC)")
    ap.add_argument("--json", action="store_true", help="print a JSON array of results")
    args = ap.parse_args()
    args.now = (dt.datetime.fromisoformat(args.now).replace(tzinfo=dt.timezone.utc) if args.now
                else dt.datetime.now(dt.timezone.utc))
    popular = list(POPULAR[args.ecosystem])
    if args.popular:
        with open(args.popular) as f:
            popular += json.load(f).get(args.ecosystem, [])
    offline = None
    if args.offline:
        with open(args.offline) as f:
            offline = json.load(f)
    reg = Registry(offline)
    results, unverifiable = [], []
    for raw in args.packages:
        try:
            results.append(vet(args.ecosystem, raw, reg, args, popular))
        except Unverifiable as e:
            unverifiable.append(raw)
            results.append({"ecosystem": args.ecosystem, "package": strip_version(raw, args.ecosystem),
                            "verdict": "UNVERIFIED", "reasons": [str(e)], "warnings": [], "facts": {}})
    if args.json:
        print(json.dumps(results, indent=1))
    else:
        for r in results:
            facts = ", ".join(f"{k}={v}" for k, v in r["facts"].items())
            print(f"vet-package: {r['ecosystem']} {r['package']} — {r['verdict']}" + (f" ({facts})" if facts else ""))
            for x in r["reasons"]:
                print(f"  - {x}")
            for w in r["warnings"]:
                print(f"  ! {w}")
    if unverifiable:
        sys.exit(2)
    sys.exit(1 if any(r["verdict"] == "FAIL" for r in results) else 0)


if __name__ == "__main__":
    main()
