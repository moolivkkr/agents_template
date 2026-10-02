#!/usr/bin/env python3
"""sdlc-graph.py — the project's artifact + traceability graph, and the deterministic TC gate.

Built by scripts, never by an LLM, from files the pipeline already writes: docs/BRD.md, PHASE_PLAN.md and
every spec / wireframe / contract under docs/design/phases/N/, docs/design/stitch.json, migrations, source and
test code, agent_state/phases/N/{roster.json,execution.jsonl,reports/*}, reconciliation reports,
docs/DECISIONS.md and docs/PROJECT_FACTS.md. Stored in agent_state/graph/graph.sqlite with a deterministic
JSONL export (graph.jsonl). Python 3.9+ standard library only.

Usage: sdlc-graph.py [--root DIR] [--graph-dir DIR] [--json] [--max-tokens N] [--limit N] [--full]
                     [--no-refresh] <command> ...

  build [--incremental]                  full rebuild (default) or re-index only changed files (per-file
                                         sha256, candidates from git diff + status + stat changes)
  stats                                  node / edge counts by kind
  tc --phase N [--tier T] [--status S] [--priority HIGH,MEDIUM] [--results F ...] [--source]
     [--diff-base SHA] [--out F] [--spec-only]
                                         the phase's TC inventory: ID, priority, tier, spec file:line,
                                         section, covering tests, result. S = todo|done|missing|failing|all.
                                         --out F writes the whole inventory (tc-inventory.py's JSON shape plus
                                         the graph checks; exit 1 unless PASS); --spec-only --out F writes
                                         {id: priority} incl. range-defined IDs (the results converters' input)
  context --agent ROLE --phase N         an agent's work list: its TC rows (todo/done), the ONLY spec
                                         sections to read (file:start-end), endpoints, tables, screens,
                                         code targets with spans. Use instead of reading specs/ whole.
                                         Test roles get their tier's rows; developers, verifiers, auditors and
                                         spec_impl_reconciler get a role profile (PROFILE_ROLES): the spec
                                         sections their job needs + every skipped span, and role inventories
  diff-context [--base SHA] [--phase N]  changed symbols (spans) since SHA (default: the phase's base_sha),
                                         and the endpoints, tables, TCs, FRs and spec sections they touch
  impact <file|symbol>                   reverse closure: callers/importers → endpoints → screens →
                                         tests → TC IDs → FRs
  consumers <symbol|"METHOD /path"|table:NAME> [--changed-since SHA]
                                         who uses it (callers, importers, frontend callers, screen bindings,
                                         readers/writers); with --changed-since, every changed definition's
                                         consumers OUTSIDE the change (breaking-change candidates)
  trace <FR-id|TC-id>                    FR → phases → spec sections → TC rows → tests → results → endpoints
  orphans [--phase N]                    declared endpoints with no handler, handlers with no contract,
                                         FRs with no spec/TC, screens with no route/baseline, tests naming
                                         TC IDs no spec defines, TC IDs mentioned in a phase but never listed
  unlocked --phase N                     E2E workflows unlocked by phases <= N (PHASE_PLAN §E2E Workflows
                                         Unlocked) + the phase's TC-E2E rows: the e2e scope (fixes C3)
  gate --phase N [--summary] [--tc-only] [--results F ...] [--diff-base SHA] [--out F]
                                         the deterministic TC gate (a superset of tc-inventory.py, see
                                         below) + roster/execution/evidence summary. Exit 0 = PASS, 1 = FAIL.
  repomap [--focus PATH,...]             deterministic personalized PageRank over import/call edges

Output is capped (--max-tokens, default 2000 ≈ 8 KB; --limit rows per list); --full lifts the caps.
Every query first refreshes the graph incrementally (seconds) unless --no-refresh.

TC GATE. `gate` computes the same inventory tc-inventory.py does — it imports tc-inventory.py's test-name
parsers and test-weakening check, so a test counts the same way in both — and is stricter in four ways:
  1. A range written as a DEFINITION is expanded into required IDs: a table row whose ID cell is a range
     ("| TC-VAL-001 – TC-VAL-004 | … | MEDIUM | unit |") or a line that starts with a range and carries a
     priority ("TC-VAL-001 – TC-VAL-004 — validation cases (MEDIUM, unit)"). tc-inventory.py drops the middle
     IDs. Allocation/reference ranges ("range owned by this spec", headings) are listed, not expanded.
  2. A table cell shaped like an ID but malformed ("TC-SEC-REG-001", "tc-api-001") is a finding: such a row
     silently drops out of tc-inventory.py's inventory.
  3. It always runs in results mode (every sdlc.test-results/v1 sidecar in agent_state/phases/N/reports/, or
     --results) and BLOCKs when there are none: coverage nobody ran is not coverage.
  4. It always runs the test-weakening check (base: --diff-base, else agent_state/phases/N/base_sha) and
     BLOCKs when there is no base to diff against.
Cross-phase duplicate detection also covers expanded range IDs. Everything else is tc-inventory.py's rule.

Code layer = rung 1 (regex per stack: Go, TS/JS, Python, Java/Kotlin, Rust; routes for gin/echo/chi/
net-http/express/Nest/Next/FastAPI/Flask/Django/Spring/axum/actix). Symbols are qualified by receiver/class
where the regex can see it; calls resolve by NAME (confidence "name"), so same-named methods can conflate.
Rung 2 plugs in through CODE_EXTRACTORS (go list + gopls, the TypeScript compiler API, Python ast,
tree-sitter): same node/edge schema, higher confidence.
"""
import argparse, datetime, fcntl, hashlib, importlib.util, json, os, re, sqlite3, subprocess, sys, time

sys.dont_write_bytecode = True          # importing tc-inventory.py must not leave __pycache__ in .claude/hooks
HERE = os.path.dirname(os.path.abspath(__file__))
_tci_path = os.path.join(HERE, "tc-inventory.py")
if not os.path.exists(_tci_path):
    sys.exit("sdlc-graph: tc-inventory.py must sit beside sdlc-graph.py (copy both from ~/.claude/hooks/startup/)")
_spec = importlib.util.spec_from_file_location("tc_inventory", _tci_path)
tci = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tci)

SCHEMA_VERSION = "1"
# A graph built by different extractor code is rebuilt in full, so an upgrade never leaves stale rows behind.
EXTRACTOR_SIG = hashlib.sha256(open(os.path.abspath(__file__), "rb").read() + open(_tci_path, "rb").read()).hexdigest()[:16]
SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes(id TEXT NOT NULL, kind TEXT NOT NULL, name TEXT, phase INTEGER, file TEXT NOT NULL,
                                 line INTEGER, end_line INTEGER, attrs TEXT);
CREATE TABLE IF NOT EXISTS edges(src TEXT NOT NULL, rel TEXT NOT NULL, dst TEXT NOT NULL, file TEXT NOT NULL,
                                 line INTEGER, attrs TEXT);
CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, kind TEXT, sha TEXT, size INTEGER, mtime INTEGER);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE INDEX IF NOT EXISTS n_id ON nodes(id);
CREATE INDEX IF NOT EXISTS n_kind ON nodes(kind, phase);
CREATE INDEX IF NOT EXISTS n_file ON nodes(file);
CREATE INDEX IF NOT EXISTS n_name ON nodes(name);
CREATE INDEX IF NOT EXISTS e_src ON edges(src, rel);
CREATE INDEX IF NOT EXISTS e_dst ON edges(dst, rel);
CREATE INDEX IF NOT EXISTS e_file ON edges(file);
"""

# ─── shared patterns ─────────────────────────────────────────────────────────────────────────────
TC_ID_RE = re.compile(r"(?<![A-Za-z0-9])TC-([A-Z0-9]+)-(\d+)(?![0-9])")                 # spec side: hyphen form
TC_CELL_RE = re.compile(r"TC-[A-Z0-9]+-\d+")                                             # what tc-inventory reads
MALFORMED_CELL_RE = re.compile(r"(?i)TC[-_][A-Z0-9][A-Z0-9_-]*")                         # ID-shaped but not valid
SPEC_RANGE_RE = re.compile(r"\bTC-([A-Z0-9]+)-(\d+)\**\s*(?:to|through|thru|–|—|\.\.|-)\s*\**TC-\1-(\d+)\b")
RANGE_CELL_RE = re.compile(r"TC-([A-Z0-9]+)-(\d+)\s*(?:to|through|thru|–|—|\.\.|-)\s*TC-\1-(\d+)")
ALLOCATION_RE = re.compile(r"\b(owned|own|allocat\w*|reserved|belong\w*|listed|block|range)\b", re.I)
PRIO_WORD_RE = re.compile(r"\b(HIGH|MEDIUM|LOW)\b")
TIER_WORD_RE = re.compile(r"\b(unit|integration|component|e2e|acceptance|performance|mobile|device|system|manual)\b", re.I)
REQ_RE = re.compile(r"(?<![A-Za-z0-9-])((?:FR|NFR|OBJ)(?:-[A-Z]+)*-\d+[a-z]?)(?![A-Za-z0-9])")
EP_RE = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+`?(/[A-Za-z0-9_{}:./\-$<>\[\]*]*)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
INVENTORY_SEC_RE = re.compile(r"test (case|coverage)|inventory|\btc\b", re.I)
DEFERRED_SEC_RE = re.compile(r"deferred|out[- ]of[- ]scope|future phase", re.I)
SKIP_BRD_SEC_RE = re.compile(r"traceab|out[- ]of[- ]scope|open question|change ?log|amendment|revision|history", re.I)
MOSCOW = {"must": "HIGH", "should": "MEDIUM", "could": "LOW", "wont": None}
MOBILE_RE = re.compile(r"(?i)(?<![a-z])(mobile|rn|react[ -]native|expo|ios|android)(?![a-z])")
CONTRACT_RE = re.compile(r"(data|api)-contracts?\.md$")
SIG_RES = {   # a section's own lines → what it talks about (role profiles: schema, ownership, accessibility)
    "sql": re.compile(r"(?i)\bCREATE\s+(?:UNIQUE\s+)?(?:TABLE|INDEX)\b|\bALTER\s+TABLE\b|\b(?:primary|foreign)\s+key\b|\bNOT\s+NULL\b|\bcolumns?\b|\bmigrations?\b"),
    "owner": re.compile(r"(?i)created_by|owner_id|\bowner(?:ship)?\b|assignee|\btheir own\b|only the (?:author|owner|creator)|\btenant"),
    "a11y": re.compile(r"(?i)aria-|\bwcag\b|contrast|\bfocus|keyboard|screen ?reader|\balt=|accessib|\ba11y\b|tab order"),
}

# The walk prunes exactly what tc-inventory.py's test walk prunes (so both see the same test files), except
# docs/ and agent_state/, which hold the artifacts; .maestro is always walked.
WALK_PRUNE = (set(tci.SKIP_DIRS) | {".git"}) - {"docs", "agent_state", ".maestro"}
CODE_EXT = {".go": "go", ".ts": "ts", ".tsx": "ts", ".js": "js", ".jsx": "js", ".mjs": "js", ".cjs": "js",
            ".py": "py", ".java": "java", ".kt": "kt", ".rs": "rs"}
MAX_FILE_BYTES = 2_000_000
TIER_SIDECAR_EXCLUDE = {"tc-inventory"}

ROLE_TIERS = {
    "unit_test_agent": ["unit"], "integration_test_agent": ["integration"],
    "ui_test_agent": ["component", "e2e"], "e2e_orchestrator": ["e2e"],
    "mobile_test_agent": ["mobile", "device"], "mobile_e2e_orchestrator": ["device"],
    "acceptance_test_agent": ["acceptance"], "performance_agent": ["performance"],
    "system_test_agent": ["system"], "manual_test_agent": ["manual"],
}
DEV_ROLES = {"backend_developer", "api_developer", "ui_developer", "mobile_developer", "database_agent",
             "migration_agent", "backend_audit_agent", "ui_audit_agent"}


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def norm_path(p):
    """/tasks/:id/complete == /tasks/{id}/complete == /tasks/${id}/complete == /tasks/<int:id>/complete"""
    p = p.split("?")[0].split("#")[0]
    p = re.sub(r"^\$\{[^}]*\}", "", p)                      # `${API_BASE}/tasks`
    p = re.sub(r"\$\{[^}]+\}|\{[^}]*\}|:[A-Za-z_]\w*|<[^>]+>|\[[^\]]+\]", "{}", p)
    p = re.sub(r"/+", "/", p)
    return (p.rstrip("/") or "/") if p.startswith("/") else "/" + p.rstrip("/")


def ep_id(method, path):
    return f"ep:{method.upper()} {norm_path(path)}"


def jdump(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"))


def read_text(path):
    try:
        if os.path.getsize(path) > MAX_FILE_BYTES:
            return ""
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def git(root, *args):
    try:
        p = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True)
        return p.stdout if p.returncode == 0 else None
    except (OSError, FileNotFoundError):
        return None


def strip_md(s):
    return s.strip().strip("`*_ ")


# ═══════════════════════════════════════════════════════════════════════════════════════════════
# Extraction: every extractor is a pure function of ONE file's content → (nodes, edges). Cross-file
# resolution (endpoint ↔ handler, test ↔ TC, import ↔ file) happens at query time, so an incremental
# re-index of a changed file gives exactly the graph a full rebuild gives.
# ═══════════════════════════════════════════════════════════════════════════════════════════════
class Out:
    def __init__(self, rel):
        self.rel, self.nodes, self.edges, self._seen = rel, [], [], set()

    def node(self, id, kind, name=None, phase=None, line=None, end_line=None, **attrs):
        a = {k: v for k, v in attrs.items() if v not in (None, "", [], {})}
        key = (id, kind, line)
        if key in self._seen:
            return
        self._seen.add(key)
        self.nodes.append((id, kind, name if name is not None else id, phase, self.rel, line, end_line, jdump(a)))

    def edge(self, src, rel, dst, line=None, **attrs):
        a = {k: v for k, v in attrs.items() if v not in (None, "", [], {})}
        key = (src, rel, dst, line)
        if key in self._seen:
            return
        self._seen.add(key)
        self.edges.append((src, rel, dst, self.rel, line, jdump(a)))


def classify(rel):
    """(kind, phase) for a repo-relative posix path, or (None, None) when the graph ignores it."""
    parts = rel.split("/")
    m = re.match(r"docs/design/phases/(\d+)/", rel)
    if m and rel.endswith(".md"):
        return "phasedoc", int(m.group(1))
    if rel == "docs/BRD.md":
        return "brd", None
    if rel in ("docs/DECISIONS.md", "docs/PROJECT_FACTS.md"):
        return "ledger", None
    if rel == "docs/design/stitch.json":
        return "stitch", None
    m = re.match(r"agent_state/phases/(\d+)/(.*)$", rel)
    if m:
        ph, sub = int(m.group(1)), m.group(2)
        if sub == "roster.json":
            return "roster", ph
        if sub == "execution.jsonl":
            return "exec", ph
        if sub in ("base_sha", "wave4_sha"):
            return "phase_sha", ph
        if sub == "manifest.json":
            return "manifest", ph
        if re.fullmatch(r"reports/[^/]+\.json", sub):
            return "report_json", ph
        if re.fullmatch(r"reports/[^/]+\.md", sub):
            return "report_md", ph
        return None, None
    m = re.match(r"agent_state/reconciliation/phase-(\d+)/([^/]+)$", rel)
    if m:
        ph = int(m.group(1))
        if rel.endswith(".json"):
            return "report_json", ph
        if rel.endswith(".md"):
            return "report_md", ph
        return None, None
    if parts[0] in ("docs", "agent_state", ".claude"):
        return None, None
    if is_test_path(rel) and not rel.endswith(".rs"):
        return "test", None
    if rel.endswith(".sql"):
        return "migration", None
    if rel.endswith(".prisma"):
        return "prisma", None
    if os.path.splitext(rel)[1] in CODE_EXT:
        return "code", None
    return None, None


def is_test_path(rel):
    """Exactly tc-inventory.py's notion of a test file, including the directories its walk prunes."""
    parts = rel.split("/")
    if any(p in tci.SKIP_DIRS and p != ".maestro" for p in parts[:-1]):
        return False
    return tci.is_test_file(rel.replace("/", os.sep))


# ─── markdown: BRD ───────────────────────────────────────────────────────────────────────────────
def moscow_of(text):
    t = text.strip().lower().replace("’", "'").replace("won't", "wont")
    for k in ("must", "should", "could", "wont"):
        if t.startswith(k):
            return k
    m = re.search(r"(?:priority|moscow)\s*[:=]\s*\**\s*(must|should|could|won'?t)", text, re.I) \
        or re.search(r"\((MUST|SHOULD|COULD|WON'?T)\)", text)
    return m.group(1).lower().replace("'", "") if m else None


def ex_brd(o, text):
    header, skip_level = None, None
    for i, line in enumerate(text.split("\n"), 1):
        s = line.strip()
        h = HEADING_RE.match(s)
        if h:
            level = len(h.group(1))
            if skip_level is not None and level <= skip_level:
                skip_level = None
            if skip_level is None and SKIP_BRD_SEC_RE.search(h.group(2)):
                skip_level = level
            header = None
        if skip_level is not None:
            continue
        if h:
            title = strip_md(h.group(2))
            m = REQ_RE.match(title)
            if m:
                o.node(f"req:{m.group(1)}", "req", m.group(1), line=i, text=title[:200],
                       category=m.group(1).rsplit("-", 1)[0], moscow=moscow_of(title))
            continue
        if s.startswith("|"):
            if re.fullmatch(r"[\s|:-]+", s):
                continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            first = strip_md(cells[0]) if cells else ""
            m = REQ_RE.fullmatch(first)
            if not m:
                header = [c.lower() for c in cells]
                continue
            pj = next((j for j, c in enumerate(header or []) if re.search(r"priority|moscow", c)), None)
            mo = moscow_of(cells[pj]) if pj is not None and pj < len(cells) else moscow_of(s)
            o.node(f"req:{first}", "req", first, line=i, text=" | ".join(cells[1:])[:200],
                   category=first.rsplit("-", 1)[0], moscow=mo)
            continue
        m = re.match(r"^[-*+]?\s*\**((?:FR|NFR|OBJ)(?:-[A-Z]+)*-\d+[a-z]?)\**\s*[:—–-]", s)
        if m:
            o.node(f"req:{m.group(1)}", "req", m.group(1), line=i, text=s[:200],
                   category=m.group(1).rsplit("-", 1)[0], moscow=moscow_of(s))


def ex_ledger(o, text):
    found = []
    for i, line in enumerate(text.split("\n"), 1):
        m = re.match(r"^###\s+((?:D|F)-\d+)\s*[—–-]\s*(.*)", line)
        if m:
            found.append([m.group(1), i, m.group(2)[:160], None])
            continue
        m = re.match(r"^-\s*status:\s*(\S+)", line)
        if m and found and found[-1][3] is None:
            found[-1][3] = m.group(1)
    for (did, i, title, status) in found:
        o.node(did, "decision" if did.startswith("D") else "fact", did, line=i, title=title, status=status)


# ─── markdown: phase docs (specs, wireframes, contracts, PHASE_PLAN, phase_context) ─────────────
def sections_of(lines):
    """[(start, end, level, title)] for every heading; end = line before the next heading of <= level."""
    heads = []
    in_code = False
    for i, l in enumerate(lines, 1):
        if l.strip().startswith("```"):
            in_code = not in_code
        if in_code:
            continue
        h = HEADING_RE.match(l.strip()) if l.startswith("#") else None
        if h:
            heads.append((i, len(h.group(1)), strip_md(h.group(2))))
    out = []
    for k, (i, lv, t) in enumerate(heads):
        end = len(lines)
        for j, lv2, _ in heads[k + 1:]:
            if lv2 <= lv:
                end = j - 1
                break
        out.append((i, end, lv, t))
    return out


def ex_phasedoc(o, text, phase):
    rel = o.rel
    lines = text.split("\n")
    base = os.path.basename(rel)
    is_screen = bool(re.search(r"\.(wireframe|ui-spec)\.md$", base))
    is_contract = bool(re.search(r"(data|api)-contracts?\.md$", base))
    dkind = "screen_spec" if is_screen else ("spec" if "/specs/" in rel else "phasedoc")
    doc = f"doc:{rel}"
    secs = sections_of(lines)
    title1 = next((t for (s, e, lv, t) in secs), "")
    platform = ("mobile" if MOBILE_RE.search(base) or MOBILE_RE.search(title1) else "web") if is_screen else None
    o.node(doc, dkind, base, phase=phase, line=1, end_line=len(lines), tokens=len(text) // 4, platform=platform)

    innermost = [None] * (len(lines) + 2)       # line → innermost section (s, e, lv, t)
    deferred = [False] * (len(lines) + 2)
    for sec in secs:                             # headings are in line order: later (deeper) ones overwrite
        s0, e0, lv0, t0 = sec
        for k in range(s0, e0 + 1):
            innermost[k] = sec
            if DEFERRED_SEC_RE.search(t0):
                deferred[k] = True
    # content signals per section, from its OWN lines (children carry their own): what role profiles key on
    sigs = {}
    for i, l in enumerate(lines, 1):
        b = innermost[i]
        if b is None:
            continue
        for name, rx in SIG_RES.items():
            if rx.search(l):
                sigs.setdefault(b[0], set()).add(name)
    for (s, e, lv, t) in secs:
        o.node(f"sec:{rel}#L{s}", "section", t[:120], phase=phase, line=s, end_line=e, level=lv,
               tokens=sum(len(x) + 1 for x in lines[s - 1:e]) // 4, sig=sorted(sigs.get(s, ())))

    def sec_id(i):
        b = innermost[i]
        return f"sec:{rel}#L{b[0]}" if b else doc

    def sec_title(i):
        b = innermost[i]
        return b[3] if b else ""

    def in_deferred(i):
        return deferred[i]

    screen = None
    if is_screen:
        screen = "screen:" + re.sub(r"\.(wireframe|ui-spec)\.md$", "", base)
        m = re.search(r"(?im)^\s*[-*]?\s*\**route\**\s*[:|]\s*`?(/[^\s`|*]*)", text) or re.search(r"route:\s*`?(/[^\s`]*)", text)
        o.node(screen, "screen", screen[7:], phase=phase, line=1, route=m.group(1) if m else None)
        o.edge(screen, "specified_by", doc, line=1)
    if base == "PHASE_PLAN.md":
        title = next((t for (s, e, lv, t) in secs if lv == 1), f"phase {phase}")
        o.node(f"phase:{phase}", "phase", title[:120], phase=phase, line=1)

    header, last_header, in_code = None, None, False
    plan_sec, wf_blocks = None, []
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith("```"):
            in_code = not in_code
        sid = sec_id(i)
        # PHASE_PLAN: scope + e2e workflows
        if base == "PHASE_PLAN.md":
            h = HEADING_RE.match(s) if s.startswith("#") else None
            if h:
                t = h.group(2).lower()
                plan_sec = ("workflows" if re.search(r"e2e workflows?|workflows? unlocked", t) else
                            "scope" if re.search(r"scope|requirements", t) and not DEFERRED_SEC_RE.search(t) else
                            "other")
            elif plan_sec == "scope":
                for r in set(REQ_RE.findall(s)):
                    o.edge(f"req:{r}", "assigned_to", f"phase:{phase}", line=i)
            elif plan_sec == "workflows":
                if re.match(r"^\s{0,1}[-*+]\s+\S", line) or (s.startswith("|") and not re.fullmatch(r"[\s|:-]+", s)):
                    wf_blocks.append([i, [s]])          # a top-level bullet (or table row) starts an entry
                elif wf_blocks and s and not s.startswith("|"):
                    wf_blocks[-1][1].append(s)
        # requirement mentions, per section
        for r in set(REQ_RE.findall(s)):
            o.edge(sid, "mentions_req", f"req:{r}", line=i)
            if dkind in ("spec", "screen_spec"):
                o.edge(doc, "covers", f"req:{r}", line=i)
        # endpoints
        if is_contract or s.startswith("#") or s.startswith("//"):
            m = re.match(r"^(?:#+|//)\s*`?(GET|POST|PUT|PATCH|DELETE)\s+`?(/\S*?)`?\s*(?:$|[—–(|])", s)
            if m:
                e = ep_id(m.group(1), m.group(2))
                o.node(e, "endpoint", e[3:], phase=phase, line=i, declared_in=rel)
                o.edge(doc, "declares", e, line=i)
        for m in EP_RE.finditer(s):
            o.edge(sid, "mentions_ep", ep_id(m.group(1), m.group(2)), line=i)
        # contract types
        if is_contract or in_code:
            t = re.match(r"^\s*(?:export\s+)?(?:interface|type)\s+([A-Z]\w*)", line)
            if t:
                o.node(f"type:{t.group(1)}", "type", t.group(1), phase=phase, line=i, declared_in=rel)
        # TC mentions outside inventory rows (EARS tables, prose), range endpoints excluded
        bare = SPEC_RANGE_RE.sub(" ", s)
        mention_ids = {f"TC-{a}-{n}" for a, n in TC_ID_RE.findall(bare)}
        # spec ranges (any line): definition-shaped ones are expanded below / in the table branch
        if not s.startswith("|"):
            stripped = re.sub(r"^[-*+]\s*", "", s).lstrip("*_` ")
            line_def = (stripped.startswith("TC-") and SPEC_RANGE_RE.match(stripped) is not None
                        and PRIO_WORD_RE.search(s) and not ALLOCATION_RE.search(s) and not s.startswith("#")
                        and not in_deferred(i))
            for k, m in enumerate(SPEC_RANGE_RE.finditer(s)):
                is_def = line_def and k == 0
                expand_range(o, m, phase, i, sid, sec_title(i), s, bool(is_def),
                             PRIO_WORD_RE.search(s).group(1) if PRIO_WORD_RE.search(s) else None,
                             TIER_WORD_RE.search(s).group(1).lower() if TIER_WORD_RE.search(s) else "",
                             None if is_def else ("heading" if s.startswith("#") else
                                                  "deferred section" if in_deferred(i) else
                                                  "allocation/reference wording" if ALLOCATION_RE.search(s) else
                                                  "no priority on the line" if not PRIO_WORD_RE.search(s) else
                                                  "range is not the line's subject" if k == 0 or not line_def else
                                                  "only the line's first range is a definition"))
        # tables — the TC inventory, mirroring tc-inventory.py's spec_rows() exactly
        if not s.startswith("|"):
            header = None
            for tid in mention_ids:
                o.edge(sid, "mentions_tc", f"tcid:{tid}", line=i, deferred=in_deferred(i) or None)
            continue
        if re.fullmatch(r"[\s|:-]+", s):
            continue
        cells = [c.strip().strip("`*_ ") for c in s.strip("|").split("|")]
        idc = next((c for c in cells if re.fullmatch(r"TC-[A-Z0-9]+-\d+", c)), None)
        if screen:
            b = re.match(r"^\|\s*`?([\w.]+)`?\s*\|\s*`?(GET|POST|PUT|PATCH|DELETE)\s+(\S+?)`?\s*\|\s*([^|]*)\|\s*(ARRAY|OBJECT)?", s)
            if b:
                o.edge(screen, "binds", ep_id(b.group(2), b.group(3)), line=i, component=b.group(1),
                       field=b.group(4).strip(), shape=b.group(5))
        if idc is None:
            rc = next((c for c in cells if RANGE_CELL_RE.fullmatch(c)), None)
            if rc:
                hdr = header or last_header or []
                col = lambda name: next((j for j, h in enumerate(hdr) if name in h), None)
                pj, tj = col("priority"), col("tier")
                pr = (cells[pj].upper() if pj is not None and pj < len(cells) else "") or "MEDIUM"
                tier = cells[tj].lower() if tj is not None and tj < len(cells) else ""
                expand_range(o, RANGE_CELL_RE.fullmatch(rc), phase, i, sid, sec_title(i), s, True,
                             pr if pr in ("HIGH", "MEDIUM", "LOW") else "MEDIUM", tier, None)
            else:
                for c in cells:
                    if MALFORMED_CELL_RE.fullmatch(c) and not re.fullmatch(r"TC-[A-Z0-9]+-\d+", c) \
                            and not RANGE_CELL_RE.fullmatch(c) and re.search(r"\d", c):
                        o.node(f"tcbad:{phase}/{c}", "tc_malformed", c, phase=phase, line=i, section=sec_title(i),
                               text=s[:160])
            if header is not None:
                last_header = header
            header = [c.lower() for c in cells]
            for tid in mention_ids:
                o.edge(sid, "mentions_tc", f"tcid:{tid}", line=i, deferred=in_deferred(i) or None)
            continue
        col = lambda name: next((j for j, h in enumerate(header or []) if name in h), None)
        pj, tj = col("priority"), col("tier")
        pr = (cells[pj].upper() if pj is not None and pj < len(cells) else "") or "MEDIUM"
        pr = pr if pr in ("HIGH", "MEDIUM", "LOW") else "MEDIUM"
        tier = cells[tj].lower() if tj is not None and tj < len(cells) else ""
        desc = next((c for c in cells if c != idc and len(c) > 12), "")
        reqs = sorted(set(REQ_RE.findall(s)))
        o.node(f"tc:{phase}/{idc}", "tc", idc, phase=phase, line=i, priority=pr, tier=tier,
               inventory=pj is not None, desc=desc[:140], section=sec_title(i), sec=sid,
               category=idc.split("-")[1], reqs=reqs, deferred=in_deferred(i) or None)
        o.edge(doc, "defines_tc", f"tc:{phase}/{idc}", line=i)
        for r in reqs:
            o.edge(f"tc:{phase}/{idc}", "verifies_req", f"req:{r}", line=i)
        for m in EP_RE.finditer(s):
            o.edge(f"tc:{phase}/{idc}", "exercises_ep", ep_id(m.group(1), m.group(2)), line=i)
        for tid in mention_ids - {idc}:
            o.edge(sid, "mentions_tc", f"tcid:{tid}", line=i)
    if wf_blocks:
        emit_workflows(o, phase, wf_blocks)


def emit_workflows(o, phase, blocks):
    """PHASE_PLAN §E2E Workflows Unlocked entries: project_planner's `- name: "slug"` + description/triggers
    form, `- **"Title"** — text`, `- slug: text`, or a table row. FRs and TC IDs come from the whole entry."""
    seen = set()
    for (line, parts) in blocks:
        text = " ".join(parts)
        first = parts[0]
        if first.startswith("|"):
            cells = [strip_md(c) for c in first.strip("|").split("|")]
            if not cells or cells[0].lower() in ("id", "name", "workflow", "slug", ""):
                continue
            name, desc = cells[0], " ".join(cells[1:])
        else:
            body = re.sub(r"^[-*+]\s+", "", first)
            m = re.search(r"\bname:\s*[\"']?([^\"'\n]+?)[\"']?\s*$", body) or re.search(r"\bname:\s*[\"']([^\"']+)[\"']", body)
            d = re.search(r"\bdescription:\s*\"([^\"]+)\"", text) or re.search(r"\bdescription:\s*(.+?)(?:\s+\w+:|$)", text)
            if m:
                name, desc = m.group(1).strip(), d.group(1) if d else text
            else:
                m = re.match(r"^\**[\"“]?([^\"”*]+?)[\"”]?\**\s*(?:[:—–]|\s-\s)\s*(.*)$", body)
                name, desc = (m.group(1), " ".join([m.group(2)] + parts[1:])) if m else (body[:60], text)
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60]
        if not slug or slug in seen or slug in ("none", "n-a"):
            continue
        seen.add(slug)
        wid = f"wf:{phase}/{slug}"
        o.node(wid, "workflow", slug, phase=phase, line=line, text=desc.strip()[:240])
        o.edge(wid, "unlocked_in", f"phase:{phase}", line=line)
        for r in sorted(set(REQ_RE.findall(text))):
            o.edge(wid, "exercises", f"req:{r}", line=line)
        for a, n in sorted(set(TC_ID_RE.findall(text))):
            o.edge(wid, "has_tc", f"tcid:TC-{a}-{n}", line=line)


def expand_range(o, m, phase, line, sid, section, text, is_def, prio, tier, reason):
    cat, a, b = m.group(1), int(m.group(2)), int(m.group(3))
    width = len(m.group(2))
    rid = f"TC-{cat}-{m.group(2)} – TC-{cat}-{m.group(3)}"
    size = b - a + 1
    if is_def and (size < 1 or size > 500):
        is_def, reason = False, f"range of {size} IDs is not expanded (1–500)"
    o.node(f"tcrange:{phase}/{rid}", "spec_range", rid, phase=phase, line=line, expanded=is_def,
           reason=reason, text=text[:160], section=section)
    if not is_def:
        return
    for n in range(a, b + 1):
        tid = f"TC-{cat}-{n:0{width}d}"
        o.node(f"tc:{phase}/{tid}", "tc", tid, phase=phase, line=line, priority=prio or "MEDIUM", tier=tier,
               inventory=True, from_range=True, desc=text[:140], section=section, sec=sid, category=cat,
               reqs=sorted(set(REQ_RE.findall(text))))
        o.edge(f"doc:{o.rel}", "defines_tc", f"tc:{phase}/{tid}", line=line)


def ex_stitch(o, text):
    try:
        st = json.loads(text)
    except ValueError:
        return
    screens = st.get("screens") if isinstance(st.get("screens"), dict) else {}
    for key, v in sorted(screens.items()):
        if isinstance(v, dict):
            o.node(f"page:{key}", "page", key, line=1, route=v.get("route"), app=v.get("app"),
                   device=v.get("deviceType"), status=v.get("status"))
            if v.get("route"):
                o.edge(f"page:{key}", "baselines", f"route:{norm_path(v['route'])}", line=1)
    pages = st.get("pages") if isinstance(st.get("pages"), dict) else {}     # pre-v2 layout
    for key, v in sorted(pages.items()):
        route = key.split(":", 1)[-1].split("|")[0]
        o.node(f"page:{key}", "page", key, line=1, route=route, status=(v or {}).get("status"))
        o.edge(f"page:{key}", "baselines", f"route:{norm_path(route)}", line=1)


def ex_sql(o, text):
    for i, l in enumerate(text.split("\n"), 1):
        for m in re.finditer(r"\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"]?(?:\w+\.)?([A-Za-z_]\w*)", l, re.I):
            t = m.group(1).lower()
            o.node(f"table:{t}", "table", t, line=i)
            o.edge(f"file:{o.rel}", "creates", f"table:{t}", line=i)
        for m in re.finditer(r"\bALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:ONLY\s+)?[`\"]?(?:\w+\.)?([A-Za-z_]\w*)", l, re.I):
            o.edge(f"file:{o.rel}", "alters", f"table:{m.group(1).lower()}", line=i)


def ex_prisma(o, text):
    cur = None
    for i, l in enumerate(text.split("\n"), 1):
        m = re.match(r"^model\s+(\w+)\s*\{", l)
        if m:
            cur = (m.group(1), i)
        m2 = re.search(r'@@map\("([^"]+)"\)', l)
        if cur and (m2 or l.strip() == "}"):
            t = (m2.group(1) if m2 else cur[0]).lower()
            o.node(f"table:{t}", "table", t, line=cur[1], model=cur[0])
            o.edge(f"file:{o.rel}", "creates", f"table:{t}", line=cur[1])
            cur = None


# ─── agent_state ─────────────────────────────────────────────────────────────────────────────────
COUNT_LINE_RE = re.compile(r"BLOCKING:\s*(\d+)\s+WARNING:\s*(\d+)\s+INFO:\s*(\d+)")


def ex_agent_state(o, text, kind, phase):
    rel = o.rel
    if kind == "roster":
        try:
            r = json.loads(text)
        except ValueError:
            o.node(f"roster:{phase}", "roster", f"roster {phase}", phase=phase, line=1, invalid=True)
            return
        req = [a for a in (r.get("required") or []) if isinstance(a, str)]
        o.node(f"roster:{phase}", "roster", f"roster {phase}", phase=phase, line=1, required=req)
        for a in req:
            o.edge(f"roster:{phase}", "requires", f"agent:{a}", line=1)
    elif kind == "exec":
        for i, l in enumerate(text.split("\n"), 1):
            if not l.strip():
                continue
            try:
                e = json.loads(l)
            except ValueError:
                o.node(f"exec:{phase}:{i}", "exec", "invalid line", phase=phase, line=i, invalid=True)
                continue
            if not isinstance(e, dict):
                continue
            rep = e.get("report")
            o.node(f"exec:{phase}:{i}", "exec", str(e.get("agent")), phase=phase, line=i, agent=e.get("agent"),
                   status=e.get("status"), report=rep if isinstance(rep, str) and rep != "null" else None,
                   ts=e.get("ts"))
            if isinstance(rep, str) and rep not in ("null", ""):
                o.edge(f"agent:{e.get('agent')}", "produced", f"report:{rep}", line=i, status=e.get("status"))
    elif kind == "phase_sha":
        o.node(f"{os.path.basename(rel)}:{phase}", "phase_sha", os.path.basename(rel), phase=phase, line=1,
               sha=text.strip()[:64])
    elif kind == "manifest":
        try:
            m = json.loads(text)
        except ValueError:
            return
        g = m.get("gate") if isinstance(m.get("gate"), dict) else {}
        o.node(f"manifest:{phase}", "manifest", f"manifest {phase}", phase=phase, line=1,
               gate_passed=g.get("passed"), e2e_workflows_unlocked=m.get("e2e_workflows_unlocked"))
    elif kind == "report_json":
        try:
            j = json.loads(text)
        except ValueError:
            o.node(f"report:{rel}", "report", os.path.basename(rel), phase=phase, line=1, invalid=True)
            return
        if not isinstance(j, dict):
            return
        if j.get("schema") == "sdlc.test-results/v1":
            o.node(f"sidecar:{rel}", "sidecar", os.path.basename(rel), phase=phase, line=1, tier=j.get("tier"),
                   verdict=j.get("verdict"), total=j.get("total"), passed=j.get("passed"), failed=j.get("failed"),
                   flaky=j.get("flaky"), code_sha=j.get("code_sha"), dirty=j.get("dirty"))
            for k, c in enumerate(j.get("cases") or []):
                if not isinstance(c, dict):
                    continue
                for tid in c.get("ids") or []:
                    o.edge(f"sidecar:{rel}", "result", f"tcid:{tid}", line=k + 1, verdict=c.get("verdict"),
                           test=str(c.get("name", ""))[:160])
        else:
            o.node(f"report:{rel}", "report", os.path.basename(rel), phase=phase, line=1,
                   verdict=j.get("verdict"), blocking=j.get("blocking"), total=j.get("total"))
    elif kind == "report_md":
        cl = None
        for i, l in enumerate(text.split("\n"), 1):
            m = COUNT_LINE_RE.search(l)
            if m:
                cl = (i, int(m.group(1)), int(m.group(2)), int(m.group(3)))
        o.node(f"report:{rel}", "report", os.path.basename(rel), phase=phase, line=1,
               blocking=cl[1] if cl else None, warning=cl[2] if cl else None, info=cl[3] if cl else None,
               count_line=cl[0] if cl else None, lines=text.count("\n"))


# ─── code (rung 1: regex) ────────────────────────────────────────────────────────────────────────
KEYWORDS = set("""if for while switch return func function catch match case new typeof sizeof make len append cap
delete panic recover print println range select go defer import from class def lambda await async yield assert
super this self not and or in is elif else try except finally with raise int str float bool list dict set tuple
string error nil None True False null undefined var let const fn impl pub use mod struct enum trait type where
loop break continue static void public private protected""".split())


def brace_end(lines, start):
    """Line (1-based) where the brace block opened at/after `start` closes; strings/comments approximated."""
    depth, opened = 0, False
    for j in range(start - 1, min(len(lines), start + 4000)):
        l = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`[^`]*`', '""', lines[j])
        l = l.split("//")[0]
        for ch in l:
            if ch == "{":
                depth += 1
                opened = True
            elif ch == "}":
                depth -= 1
                if opened and depth <= 0:
                    return j + 1
        if not opened and j > start + 3:
            return start                  # declaration without a body (interface method, prototype)
    return len(lines)


def indent_end(lines, start):
    ind = len(lines[start - 1]) - len(lines[start - 1].lstrip())
    end = start
    for j in range(start, len(lines)):
        l = lines[j]
        if not l.strip() or l.lstrip().startswith("#"):
            continue
        if len(l) - len(l.lstrip()) <= ind and not l.lstrip().startswith((")", "]", "}")):
            break
        end = j + 1
    return end


def defs_go(lines):
    out = []
    for i, l in enumerate(lines, 1):
        m = re.match(r"^func\s+(?:\(\s*\w*\s*\*?\s*(\w+)(?:\[[^\]]*\])?\s*\)\s*)?(\w+)", l)
        if m:
            out.append((i, f"{m.group(1)}.{m.group(2)}" if m.group(1) else m.group(2), m.group(2),
                        "method" if m.group(1) else "func", brace_end(lines, i)))
            continue
        m = re.match(r"^type\s+(\w+)\s+(struct|interface)\b", l)
        if m:
            out.append((i, m.group(1), m.group(1), m.group(2), brace_end(lines, i)))
    return out


def defs_ts(lines):
    out, cls = [], None
    for i, l in enumerate(lines, 1):
        if cls and i > cls[1]:
            cls = None
        m = re.match(r"^(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+(\w+)", l)
        if m:
            end = brace_end(lines, i)
            cls = (m.group(1), end)
            out.append((i, m.group(1), m.group(1), "class", end))
            continue
        m = (re.match(r"^(?:export\s+)?(?:default\s+)?(?:async\s+)?function\*?\s+(\w+)", l) or
             re.match(r"^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*(?::[^=]{0,80})?=\s*(?:async\s+)?(?:function\b|\(|\w+\s*=>|React\.memo|memo\(|forwardRef)", l))
        if m:
            out.append((i, m.group(1), m.group(1), "func", brace_end(lines, i)))
            continue
        m = re.match(r"^(?:export\s+)?(?:declare\s+)?(?:interface|type|enum)\s+(\w+)", l)
        if m:
            out.append((i, m.group(1), m.group(1), "type", brace_end(lines, i) if "{" in l else i))
            continue
        if cls:
            m = re.match(r"^\s{2,8}(?:(?:public|private|protected|static|async|readonly|override|get|set)\s+)*(\w+)\s*(?:<[^>]*>)?\s*\([^)]*\)?\s*(?::\s*[^{=;]+)?\{?\s*$", l)
            if m and m.group(1) not in KEYWORDS and m.group(1) != "constructor":
                out.append((i, f"{cls[0]}.{m.group(1)}", m.group(1), "method", brace_end(lines, i)))
    return out


def defs_py(lines):
    out, stack = [], []
    for i, l in enumerate(lines, 1):
        m = re.match(r"^(\s*)(?:async\s+)?(def|class)\s+(\w+)", l)
        if not m:
            continue
        ind = len(m.group(1))
        while stack and stack[-1][0] >= ind:
            stack.pop()
        qual = ".".join([s[1] for s in stack] + [m.group(3)])
        kind = "class" if m.group(2) == "class" else ("method" if stack else "func")
        out.append((i, qual, m.group(3), kind, indent_end(lines, i)))
        stack.append((ind, m.group(3)))
    return out


def defs_jvm(lines):
    out, cls = [], None
    for i, l in enumerate(lines, 1):
        m = re.match(r"^\s*(?:@\w+(?:\([^)]*\))?\s*)*(?:(?:public|private|protected|internal|abstract|final|open|data|sealed|static)\s+)*(?:class|interface|enum|object|record)\s+(\w+)", l)
        if m:
            cls = m.group(1)
            out.append((i, cls, cls, "class", brace_end(lines, i)))
            continue
        m = (re.match(r"^\s+(?:(?:public|private|protected|internal|override|suspend|open|static|final|synchronized|abstract)\s+)*fun\s+(?:<[^>]*>\s*)?(?:\w+\.)?(\w+)\s*\(", l) or
             re.match(r"^\s+(?:(?:public|private|protected|static|final|synchronized|abstract|default)\s+)+[\w<>\[\],.? ]+?\s+(\w+)\s*\(", l))
        if m and m.group(1) not in KEYWORDS:
            out.append((i, f"{cls}.{m.group(1)}" if cls else m.group(1), m.group(1), "method", brace_end(lines, i)))
    return out


def defs_rs(lines):
    out, impl = [], None
    for i, l in enumerate(lines, 1):
        if impl and i > impl[1]:
            impl = None
        m = re.match(r"^\s*impl(?:<[^>]*>)?\s+(?:[\w:<>]+\s+for\s+)?(\w+)", l)
        if m:
            impl = (m.group(1), brace_end(lines, i))
            continue
        m = re.match(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(?:unsafe\s+)?fn\s+(\w+)", l)
        if m:
            q = f"{impl[0]}.{m.group(1)}" if impl and l.startswith((" ", "\t")) else m.group(1)
            out.append((i, q, m.group(1), "method" if "." in q else "func", brace_end(lines, i)))
            continue
        m = re.match(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:struct|enum|trait)\s+(\w+)", l)
        if m:
            out.append((i, m.group(1), m.group(1), "type", brace_end(lines, i) if "{" in l else i))
    return out


DEFS = {"go": defs_go, "ts": defs_ts, "js": defs_ts, "py": defs_py, "java": defs_jvm, "kt": defs_jvm, "rs": defs_rs}
ROUTER_RECV = re.compile(r"^(app|router|r|e|g|s|srv|server|mux|api|v\d|routes?|\w*[Rr]outer|\w*[Gg]roup|grp|engine|fiber|f)$")
CLIENT_RECV = re.compile(r"^(axios|http|client|apiClient|request|\$http|instance|ky|fetcher|\w*[Cc]lient|\w*Api|api)$")


def routes_of(lang, rel, text, lines):
    """[(method, path, handler_name, line)] — rung-1 regex route extraction per framework."""
    out = []
    if lang == "go":
        prefix = {}
        for m in (re.finditer(r"(?m)^\s*(\w+)\s*:?=\s*(\w+)\.Group\(\s*\"([^\"]*)\"", text) if ".Group(" in text else ()):
            prefix[m.group(1)] = prefix.get(m.group(2), "") + m.group(3)
        for m in re.finditer(r"(\w+)\.(GET|POST|PUT|PATCH|DELETE|Get|Post|Put|Patch|Delete)\(\s*\"([^\"]+)\"\s*,\s*(?:[\w.]+\s*,\s*)*?&?([\w.]+?)(?:\(\))?\s*\)", text):
            out.append((m.group(2).upper(), prefix.get(m.group(1), "") + m.group(3), m.group(4).split(".")[-1], tci.line_of(text, m.start())))
        for m in re.finditer(r"HandleFunc\(\s*\"(?:(GET|POST|PUT|PATCH|DELETE)\s+)?([^\"]+)\"\s*,\s*([\w.]+)\)(?:\s*\.Methods\(\s*\"(\w+)\")?", text):
            out.append(((m.group(1) or m.group(4) or "GET").upper(), m.group(2), m.group(3).split(".")[-1], tci.line_of(text, m.start())))
    elif lang in ("ts", "js"):
        for m in re.finditer(r"\b(\w+)\.(get|post|put|patch|delete)\(\s*['\"`]([^'\"`]+)['\"`]\s*,\s*((?:[^()]|\([^()]*\))*?)\)", text):
            recv, args = m.group(1), m.group(4)
            if not ROUTER_RECV.match(recv) or CLIENT_RECV.match(recv) and recv != "api":
                continue
            if recv == "api" and not re.search(r"\b(req|res|ctx|request|reply)\b|=>|function|Handler|handler|controller", args):
                continue
            h = re.findall(r"([A-Za-z_][\w.]*)", args.split("=>")[0])
            out.append((m.group(2).upper(), m.group(3), h[-1].split(".")[-1] if h else "<inline>", tci.line_of(text, m.start())))
        ctl = re.search(r"@Controller\(\s*['\"]([^'\"]*)['\"]", text)
        if ctl or "@Controller(" in text:
            pre = "/" + ctl.group(1).strip("/") if ctl and ctl.group(1) else ""
            for m in re.finditer(r"@(Get|Post|Put|Patch|Delete)\(\s*(?:['\"]([^'\"]*)['\"])?\s*\)\s*(?:@\w+\([^)]*\)\s*)*(?:async\s+)?(\w+)\s*\(", text):
                out.append((m.group(1).upper(), pre + ("/" + m.group(2).strip("/") if m.group(2) else ""), m.group(3), tci.line_of(text, m.start())))
        nm = re.search(r"(?:^|/)app/(.*)/route\.[jt]sx?$", rel) or re.search(r"(?:^|/)pages/(api/.*?)(?:/index)?\.[jt]sx?$", rel)
        if nm:
            path = "/" + re.sub(r"\([^)]*\)/?", "", nm.group(1))
            for m in re.finditer(r"export\s+(?:async\s+)?(?:function|const)\s+(GET|POST|PUT|PATCH|DELETE)\b", text):
                out.append((m.group(1), path, m.group(1), tci.line_of(text, m.start())))
    elif lang == "py":
        pre = {m.group(1): m.group(2) for m in re.finditer(r"(?m)^\s*(\w+)\s*=\s*APIRouter\([^)]*prefix\s*=\s*['\"]([^'\"]+)['\"]", text)} \
            if "APIRouter" in text else {}
        if "@" in text:                          # line-based: decorator, then the next def within 12 lines
            for i, l in enumerate(lines):
                s_ = l.strip()
                if not s_.startswith("@"):
                    continue
                m = re.match(r"@(\w+)\.(get|post|put|patch|delete)\(\s*['\"]([^'\"]*)['\"]", s_)
                f = re.match(r"@(\w+)\.route\(\s*['\"]([^'\"]+)['\"](.*)", s_)
                if not (m or f):
                    continue
                fn = next((dm.group(1) for dm in (re.match(r"\s*(?:async\s+)?def\s+(\w+)", x) for x in lines[i + 1:i + 13]) if dm), None)
                if not fn:
                    continue
                if m:
                    out.append((m.group(2).upper(), pre.get(m.group(1), "") + m.group(3), fn, i + 1))
                else:
                    for me in re.findall(r"['\"](GET|POST|PUT|PATCH|DELETE)['\"]", f.group(3).upper()) or ["GET"]:
                        out.append((me, f.group(2), fn, i + 1))
        if "path(" in text and ("urlpatterns" in text or "django" in text):
            for m in re.finditer(r"\b(?:re_)?path\(\s*r?['\"]\^?([^'\"]*)['\"]\s*,\s*([\w.]+)", text):
                out.append(("ANY", "/" + m.group(1).lstrip("^").rstrip("$"), m.group(2).split(".")[-1], tci.line_of(text, m.start())))
    elif lang in ("java", "kt"):
        cm = re.search(r"@RequestMapping\(\s*(?:value\s*=\s*|path\s*=\s*)?\"([^\"]*)\"", text)
        pre = cm.group(1) if cm and cm.start() < (text.find("class ") if "class " in text else 0) + 400 else ""
        for m in re.finditer(r"@(Get|Post|Put|Patch|Delete)Mapping(?:\(\s*(?:value\s*=\s*|path\s*=\s*)?\"?([^\")]*)\"?[^)]*\))?\s*(?:@\w+(?:\([^)]*\))?\s*)*(?:public\s+|fun\s+|suspend\s+fun\s+)?[\w<>\[\],.? ]*?(\w+)\s*\(", text):
            out.append((m.group(1).upper(), pre + (m.group(2) or ""), m.group(3), tci.line_of(text, m.start())))
    elif lang == "rs":
        for m in re.finditer(r"\.route\(\s*\"([^\"]+)\"\s*,\s*([^;]*?)\)\s*(?=\.|;|\n)", text):
            for mm in re.finditer(r"\b(get|post|put|patch|delete)\(\s*([\w:]+)\s*\)", m.group(2)):
                out.append((mm.group(1).upper(), m.group(1), mm.group(2).split("::")[-1], tci.line_of(text, m.start())))
        for m in re.finditer(r"#\[(get|post|put|patch|delete)\(\s*\"([^\"]+)\"[^\]]*\]\s*(?:pub\s+)?(?:async\s+)?fn\s+(\w+)", text):
            out.append((m.group(1).upper(), m.group(2), m.group(3), tci.line_of(text, m.start())))
    return out


def client_calls(lang, text):
    out = []
    if lang not in ("ts", "js"):
        return out
    for m in re.finditer(r"\bfetch\(\s*[`'\"]([^`'\"]+)[`'\"](?:\s*,\s*\{[^}]*?method:\s*['\"](\w+)['\"])?", text):
        out.append(((m.group(2) or "GET").upper(), m.group(1), tci.line_of(text, m.start())))
    for m in re.finditer(r"\b([\w$]+)\.(get|post|put|patch|delete)\(\s*[`'\"]([^`'\"]+)[`'\"]", text):
        if CLIENT_RECV.match(m.group(1)) and m.group(3).startswith(("/", "${")):
            out.append((m.group(2).upper(), m.group(3), tci.line_of(text, m.start())))
    return [(me, p, ln) for me, p, ln in out if p.startswith("/") or p.startswith("${")]


def imports_of(lang, text):
    if lang == "go":
        blocks = [a or b for a, b in re.findall(r'(?m)^import\s*(?:\(([^)]*)\)|("[^"]+"))', text)]
        return sorted({m.group(1) for m in re.finditer(r'"([^"]+)"', " ".join(blocks))})
    if lang in ("ts", "js"):
        return sorted(set(re.findall(r"""(?:from\s+|import\s*\(\s*|require\(\s*|^import\s+)['"]([^'"]+)['"]""", text, re.M)))
    if lang == "py":
        out = set()
        for m in re.finditer(r"^\s*from\s+(\.*[\w.]*)\s+import\s+([\w, ()*]+)", text, re.M):
            out.add(m.group(1))
        for m in re.finditer(r"^\s*import\s+([\w.]+)", text, re.M):
            out.add(m.group(1))
        return sorted(out)
    if lang in ("java", "kt"):
        return sorted(set(re.findall(r"^import\s+([\w.]+)", text, re.M)))
    if lang == "rs":
        return sorted(set(re.findall(r"^\s*use\s+((?:crate|super|self)::[\w:]+)", text, re.M)))
    return []


def ex_code(o, text, is_test):
    rel = o.rel
    lang = CODE_EXT.get(os.path.splitext(rel)[1])
    lines = text.split("\n")
    fid = f"file:{rel}"
    o.node(fid, "file", rel, line=1, end_line=len(lines), lang=lang, test=is_test or None, tokens=len(text) // 4)
    for imp in imports_of(lang, text):
        o.edge(fid, "imports", f"imp:{lang}:{imp}", line=None)
    defs = DEFS.get(lang, lambda _l: [])(lines)
    for (i, qual, simple, kind, end) in defs:
        end = max(end, i)
        body = "\n".join(lines[i - 1:end])
        sid = f"sym:{rel}#{qual}"
        o.node(sid, "symbol", qual, line=i, end_line=end, simple=simple, symkind=kind,
               hash=hashlib.sha1(body.encode()).hexdigest()[:12], test=is_test or None)
        o.edge(fid, "defines", sid, line=i)
        if kind == "class" or kind in ("struct", "interface", "type"):
            continue
        callees = set()
        for c in re.findall(r"(?<![\w$])([A-Za-z_]\w*)\s*\(", body):
            if c not in KEYWORDS and c != simple and len(c) > 2:
                callees.add(c)
        for c in sorted(callees)[:200]:
            o.edge(sid, "calls", f"name:{c}", line=i, confidence="name")
        for mm in re.finditer(r"\b(FROM|JOIN|INTO|UPDATE|DELETE\s+FROM)\s+[`\"]?(?:\w+\.)?([a-z_][a-z0-9_]*)", body, re.I):
            word = mm.group(2).lower()
            if word in ("select", "set", "where", "the", "a", "values", "only", "lateral"):
                continue
            rel_ = "writes" if mm.group(1).upper() in ("INTO", "UPDATE") or mm.group(1).upper().startswith("DELETE") else "reads"
            o.edge(sid, rel_, f"table:{word}", line=i + body[:mm.start()].count("\n"))
    m = re.search(r"__tablename__\s*=\s*['\"](\w+)['\"]", text) or re.search(r"func\s*\([^)]*\)\s*TableName\(\)\s*string\s*\{\s*return\s*\"(\w+)\"", text)
    if m:
        o.edge(fid, "maps_table", f"table:{m.group(1).lower()}", line=tci.line_of(text, m.start()))

    def enclosing(line):
        best = None
        for (i, qual, simple, kind, end) in defs:
            if i <= line <= end and (best is None or i >= best[0]):
                best = (i, qual)
        return f"sym:{rel}#{best[1]}" if best else fid

    for (meth, path, handler, ln) in routes_of(lang, rel, text, lines):
        e = ep_id(meth, path)
        o.edge(fid, "route", e, line=ln, handler=handler, confidence="regex")
    for (meth, path, ln) in client_calls(lang, text):
        o.edge(enclosing(ln), "calls_endpoint", ep_id(meth, path), line=ln, confidence="regex")
    for m in re.finditer(r"<Route\s+[^>]*?path=[\"'{`]+([^\"'}`]+)[\"'}`]+[^>]*?(?:element=\{\s*<(\w+)|component=\{(\w+))", text):
        o.edge(f"route:{norm_path(m.group(1))}", "renders", f"component:{m.group(2) or m.group(3)}", line=tci.line_of(text, m.start()))
    for m in re.finditer(r"\bpath:\s*['\"`]([^'\"`]+)['\"`]\s*,\s*(?:element:\s*<(\w+)|component:\s*(\w+))", text):
        o.edge(f"route:{norm_path(m.group(1))}", "renders", f"component:{m.group(2) or m.group(3)}", line=tci.line_of(text, m.start()))


def ex_tests(o, text, rel):
    """Test cases exactly as tc-inventory.py's scan_tests() sees them."""
    fn = os.path.basename(rel)
    if fn.endswith(".go"):
        found = tci.cases_go(text)
    elif re.search(r"\.[cm]?[jt]sx?$", fn):
        found = tci.cases_js(text)
    elif fn.endswith(".py"):
        found = tci.cases_py(text)
    elif fn.endswith(".rs"):
        if "#[test]" not in text and "#[tokio::test" not in text:
            return False
        found = tci.cases_rs(text)
    elif re.search(r"\.(java|kt)$", fn):
        found = tci.cases_jvm(text)
    else:
        found = tci.cases_maestro(rel, text)
    for k, (name, ln, skipped) in enumerate(found):
        ids = sorted(tci.ids_in(name))
        tid = f"test:{rel}::{name}"
        o.node(tid, "test", name[:200], line=ln, skipped=bool(skipped), ids=ids, ord=k)
        for i in ids:
            o.edge(tid, "verifies", f"tcid:{i}", line=ln, skipped=bool(skipped) or None)
    for m in tci.TC_RE.finditer(text):
        o.node(f"tcmention:{tci.norm(m)}", "tc_mention", tci.norm(m), line=tci.line_of(text, m.start()))
    for m in tci.RANGE_RE.finditer(text):
        o.node(f"testrange:{rel}:{tci.line_of(text, m.start())}", "test_range", m.group(0),
               line=tci.line_of(text, m.start()))
    return True


# Rung-2 hook: map a language to a callable(o, text, is_test) that emits the same node/edge schema with
# confidence "compiler"/"ast". Leave None to use the regex rung. (go list -json + gopls, the TypeScript
# compiler API via node, Python ast, tree-sitter.) An extractor that raises falls back to the regex rung.
CODE_EXTRACTORS = {"go": None, "ts": None, "js": None, "py": None, "java": None, "kt": None, "rs": None}


def extract(rel, kind, phase, text):
    o = Out(rel)
    if kind == "phasedoc":
        ex_phasedoc(o, text, phase)
    elif kind == "brd":
        ex_brd(o, text)
    elif kind == "ledger":
        ex_ledger(o, text)
    elif kind == "stitch":
        ex_stitch(o, text)
    elif kind in ("roster", "exec", "phase_sha", "manifest", "report_json", "report_md"):
        ex_agent_state(o, text, kind, phase)
    elif kind == "migration":
        ex_sql(o, text)
    elif kind == "prisma":
        ex_prisma(o, text)
    elif kind in ("code", "test"):
        is_test = kind == "test"
        if is_test:
            ex_tests(o, text, rel)
        elif rel.endswith(".rs") and is_test_path(rel):
            is_test = ex_tests(o, text, rel)          # tc-inventory.py: a .rs file is a test file iff it has #[test]
        if os.path.splitext(rel)[1] in CODE_EXT:
            rung2 = CODE_EXTRACTORS.get(CODE_EXT[os.path.splitext(rel)[1]])
            done = False
            if rung2:
                try:
                    rung2(o, text, is_test)
                    done = True
                except Exception:          # rung 2 is best effort; regex rung is the floor
                    done = False
            if not done:
                ex_code(o, text, is_test)
    return o


# ═══════════════════════════════════════════════════════════════════════════════════════════════
# The graph store
# ═══════════════════════════════════════════════════════════════════════════════════════════════
class Graph:
    def __init__(self, root, graph_dir=None):
        self.root = os.path.abspath(root)
        self.dir = os.path.abspath(graph_dir or os.environ.get("SDLC_GRAPH_DIR") or
                                   os.path.join(self.root, "agent_state", "graph"))
        os.makedirs(self.dir, exist_ok=True)
        gi = os.path.join(self.dir, ".gitignore")
        if not os.path.exists(gi):
            with open(gi, "w") as f:
                f.write("# rebuildable: python3 .claude/hooks/sdlc-graph.py build\ngraph.sqlite*\ngraph.jsonl\n.lock\n")
        self.path = os.path.join(self.dir, "graph.sqlite")
        self.db = sqlite3.connect(self.path, timeout=60)
        self.db.executescript(SCHEMA)
        if self.meta("schema_version") not in (None, SCHEMA_VERSION):
            self.wipe()
        self.stats = {}
        self.cache = {}

    # ── meta / lock ──
    def meta(self, k):
        r = self.db.execute("SELECT value FROM meta WHERE key=?", (k,)).fetchone()
        return r[0] if r else None

    def set_meta(self, k, v):
        self.db.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (k, v))

    def wipe(self):
        for t in ("nodes", "edges", "files", "meta"):
            self.db.execute(f"DELETE FROM {t}")

    def q(self, sql, *a):
        return self.db.execute(sql, a).fetchall()

    # ── discovery ──
    def walk(self):
        out = {}
        for base, dirs, files in os.walk(self.root):
            relbase = os.path.relpath(base, self.root)
            relbase = "" if relbase == "." else relbase.replace(os.sep, "/")
            keep = []
            for d in sorted(dirs):
                if d in WALK_PRUNE:
                    continue
                if relbase == "agent_state" and d not in ("phases", "reconciliation"):
                    continue                     # only phase evidence; not junit dumps, sessions, the graph itself
                if os.path.abspath(os.path.join(base, d)) == self.dir:
                    continue
                keep.append(d)
            dirs[:] = keep
            for fn in files:
                rel = f"{relbase}/{fn}" if relbase else fn
                kind, phase = classify(rel)
                if kind:
                    out[rel] = (kind, phase)
        return out

    # ── indexing ──
    def forget(self, rel):
        self.db.execute("DELETE FROM nodes WHERE file=?", (rel,))
        self.db.execute("DELETE FROM edges WHERE file=?", (rel,))
        self.db.execute("DELETE FROM files WHERE path=?", (rel,))

    def index(self, rel, kind, phase, raw=None):
        p = os.path.join(self.root, rel)
        try:
            st = os.stat(p)
            raw = raw if raw is not None else open(p, "rb").read()
        except OSError:
            self.forget(rel)
            return
        text = raw.decode("utf-8", errors="replace") if len(raw) <= MAX_FILE_BYTES else ""
        o = extract(rel, kind, phase, text)
        self.db.execute("DELETE FROM nodes WHERE file=?", (rel,))
        self.db.execute("DELETE FROM edges WHERE file=?", (rel,))
        self.db.executemany("INSERT INTO nodes VALUES(?,?,?,?,?,?,?,?)", o.nodes)
        self.db.executemany("INSERT INTO edges VALUES(?,?,?,?,?,?)", o.edges)
        self.db.execute("INSERT OR REPLACE INTO files VALUES(?,?,?,?,?)",
                        (rel, kind, hashlib.sha256(raw).hexdigest(), st.st_size, int(st.st_mtime_ns)))

    def build(self, incremental=False):
        t0 = time.time()
        lockf = open(os.path.join(self.dir, ".lock"), "w")
        fcntl.flock(lockf, fcntl.LOCK_EX)
        try:
            cur = self.walk()
            known = {r[0]: r[1:] for r in self.q("SELECT path, kind, sha, size, mtime FROM files")}
            head = (git(self.root, "rev-parse", "HEAD") or "").strip() or None
            mode = ("incremental" if incremental and known and self.meta("built_at")
                    and self.meta("extractor") == EXTRACTOR_SIG else "full")
            changed = removed = 0
            if mode == "full":
                self.wipe()
                for rel in sorted(cur):
                    self.index(rel, *cur[rel])
                changed = len(cur)
            else:
                gitset = set()
                last = self.meta("head")
                if last and head and last != head:
                    gitset |= set((git(self.root, "diff", "--name-only", last, head) or "").splitlines())
                for l in (git(self.root, "status", "--porcelain", "--untracked-files=all") or "").splitlines():
                    gitset.add(l[3:].split(" -> ")[-1].strip('"'))
                for rel in sorted(cur):
                    kind, phase = cur[rel]
                    k = known.get(rel)
                    p = os.path.join(self.root, rel)
                    try:
                        st = os.stat(p)
                    except OSError:
                        continue
                    if k and k[0] == kind and rel not in gitset and k[2] == st.st_size and k[3] == int(st.st_mtime_ns):
                        continue
                    raw = open(p, "rb").read()
                    if k and k[0] == kind and k[1] == hashlib.sha256(raw).hexdigest():
                        self.db.execute("UPDATE files SET size=?, mtime=? WHERE path=?", (st.st_size, int(st.st_mtime_ns), rel))
                        continue
                    self.index(rel, kind, phase, raw)
                    changed += 1
                for rel in sorted(set(known) - set(cur)):
                    self.forget(rel)
                    removed += 1
            self.set_meta("schema_version", SCHEMA_VERSION)
            self.set_meta("extractor", EXTRACTOR_SIG)
            self.set_meta("head", head or "")
            self.set_meta("built_at", now_iso())
            self.set_meta("root", self.root)
            if mode == "full":
                self.set_meta("full_built_at", now_iso())
                self.set_meta("full_head", head or "")
            self.db.commit()
            if changed or removed or not os.path.exists(os.path.join(self.dir, "graph.jsonl")):
                self.export()
            self.stats = {"mode": mode, "files": len(cur), "reindexed": changed, "removed": removed,
                          "seconds": round(time.time() - t0, 2), "head": head}
            return self.stats
        finally:
            fcntl.flock(lockf, fcntl.LOCK_UN)
            lockf.close()

    def export(self):
        tmp = os.path.join(self.dir, "graph.jsonl.tmp")
        with open(tmp, "w") as f:
            for r in self.db.execute("SELECT id, kind, name, phase, file, line, end_line, attrs FROM nodes "
                                     "ORDER BY id, file, line, kind, attrs"):
                d = {"t": "node", "id": r[0], "kind": r[1], "name": r[2], "phase": r[3], "file": r[4],
                     "line": r[5], "end_line": r[6]}
                d.update(json.loads(r[7] or "{}"))
                f.write(json.dumps(d, sort_keys=True) + "\n")
            for r in self.db.execute("SELECT src, rel, dst, file, line, attrs FROM edges "
                                     "ORDER BY src, rel, dst, file, line, attrs"):
                d = {"t": "edge", "src": r[0], "rel": r[1], "dst": r[2], "file": r[3], "line": r[4]}
                d.update(json.loads(r[5] or "{}"))
                f.write(json.dumps(d, sort_keys=True) + "\n")
        os.replace(tmp, os.path.join(self.dir, "graph.jsonl"))

    # ── node helpers ──
    def nodes(self, where, *a):
        out = []
        for r in self.q(f"SELECT id, kind, name, phase, file, line, end_line, attrs FROM nodes WHERE {where}", *a):
            d = {"id": r[0], "kind": r[1], "name": r[2], "phase": r[3], "file": r[4], "line": r[5], "end_line": r[6]}
            d.update(json.loads(r[7] or "{}"))
            out.append(d)
        return out

    def edges(self, where, *a):
        out = []
        for r in self.q(f"SELECT src, rel, dst, file, line, attrs FROM edges WHERE {where}", *a):
            d = {"src": r[0], "rel": r[1], "dst": r[2], "file": r[3], "line": r[4]}
            d.update(json.loads(r[5] or "{}"))
            out.append(d)
        return out

    def phases(self):
        return sorted({r[0] for r in self.q("SELECT DISTINCT phase FROM nodes WHERE phase IS NOT NULL")})


# ═══════════════════════════════════════════════════════════════════════════════════════════════
# TC inventory + gate
# ═══════════════════════════════════════════════════════════════════════════════════════════════
def spec_inventory(g, phase):
    """{id: row} for a phase with tc-inventory.py's precedence (an inventory row beats a passing mention; the
    first row wins; two inventory rows = duplicate) + expanded definition ranges (only where no row exists)."""
    rows = g.nodes("kind='tc' AND phase=? ORDER BY file, line", phase)
    spec, dup = {}, {}
    for r in [r for r in rows if not r.get("from_range")]:
        r["where"] = f"{r['file']}:{r['line']}"
        prev = spec.get(r["name"])
        if prev is None or (r.get("inventory") and not prev.get("inventory")):
            spec[r["name"]] = r
        elif r.get("inventory") and prev.get("inventory"):
            dup.setdefault(r["name"], [prev["where"]]).append(r["where"])
    expanded = []
    for r in [r for r in rows if r.get("from_range")]:
        r["where"] = f"{r['file']}:{r['line']}"
        if r["name"] not in spec:
            spec[r["name"]] = r
            expanded.append(r["name"])
    return spec, dup, sorted(set(expanded))


def discover_results(g, phase):
    out = []
    for d in (f"agent_state/phases/{phase}/reports",):
        p = os.path.join(g.root, d)
        if not os.path.isdir(p):
            continue
        for fn in sorted(os.listdir(p)):
            if not fn.endswith(".json"):
                continue
            try:
                j = json.load(open(os.path.join(p, fn)))
            except (OSError, ValueError):
                continue
            if isinstance(j, dict) and j.get("schema") == "sdlc.test-results/v1" and j.get("tier") not in TIER_SIDECAR_EXCLUDE:
                out.append(os.path.join(p, fn))
    return out


def tc_inventory(g, phase, results=None, diff_base=None, gate_mode=False):
    """The same computation as tc-inventory.py main(), over the graph, plus the graph-only checks."""
    phase = int(phase)
    spec, dup_in_phase, expanded = spec_inventory(g, phase)
    others = {}
    for p in g.phases():
        if p == phase:
            continue
        ids = {r[0] for r in g.q("SELECT DISTINCT name FROM nodes WHERE kind='tc' AND phase=?", p)}
        for k in set(spec) & ids:
            others.setdefault(k, []).append(str(p))
    dups = {k: sorted(v, key=lambda x: int(x)) for k, v in others.items()}
    named = {}
    for t in g.nodes("kind='test' ORDER BY file, line"):
        for i in t.get("ids") or []:
            named.setdefault(i, []).append(t)
    anywhere = {r[0] for r in g.q("SELECT DISTINCT name FROM nodes WHERE kind='tc_mention'")}
    ranges = [f"{r['file']}:{r['line']}: {r['name']}" for r in g.nodes("kind='test_range' ORDER BY file, line")]
    res_by_id, results_used, results_err = {}, [], []
    if results is not None:
        for p in results:
            try:
                sc = json.load(open(p))
            except (OSError, ValueError) as e:
                results_err.append(f"{p}: {e}")
                continue
            results_used.append(os.path.relpath(p, g.root) if os.path.isabs(p) else p)
            for c in sc.get("cases", []) or []:
                for i in c.get("ids", []) or []:
                    res_by_id.setdefault(i, []).append(c.get("verdict", ""))
    results_mode = results is not None and bool(results)
    cases, missing, failing, skipped_only, comment_only = [], [], [], [], []
    for tid, meta in sorted(spec.items()):
        blocking = meta["priority"] in ("HIGH", "MEDIUM")
        live = [c for c in named.get(tid, []) if not c.get("skipped")]
        if results_mode:
            vs = res_by_id.get(tid, [])
            if any(v in ("FAIL", "FLAKY") for v in vs):
                v = "FAIL"
                failing.append(tid)
            elif "PASS" in vs:
                v = "PASS"
            else:
                v = "UNTESTED"
        else:
            v = "PASS" if live else "UNTESTED"
        if v == "UNTESTED":
            if named.get(tid):
                skipped_only.append(tid)
            elif tid in anywhere:
                comment_only.append(tid)
            if blocking:
                missing.append(tid)
        cases.append({"name": tid, "ids": [tid], "priority": meta["priority"], "tier": meta.get("tier", ""),
                      "verdict": v, "tests": [f"{c['file']}:{c['line']}" for c in live][:5],
                      "spec": meta["where"], "section": meta.get("section", ""),
                      **({"from_range": True} if meta.get("from_range") else {})})
    weak, unack, changes, invalid = [], [], [], []
    base_err = None
    if gate_mode and not diff_base:
        bp = os.path.join(g.root, "agent_state", "phases", str(phase), "base_sha")
        diff_base = open(bp).read().strip() if os.path.exists(bp) else None
        if not diff_base:
            base_err = f"no base commit: agent_state/phases/{phase}/base_sha is missing or empty (Wave 0c writes it) — the test-weakening check can't run"
    if diff_base:
        weak, unack, changes, invalid = tci.weakening(g.root, diff_base, phase)
    malformed = [f"{r['file']}:{r['line']}: {r['name']}" for r in g.nodes("kind='tc_malformed' AND phase=? ORDER BY file, line", phase)]
    spec_ranges = [{"where": f"{r['file']}:{r['line']}", "range": r["name"], "expanded": bool(r.get("expanded")),
                    **({"reason": r["reason"]} if r.get("reason") else {})}
                   for r in g.nodes("kind='spec_range' AND phase=? ORDER BY file, line", phase)]
    blocking_ids = [k for k, m in spec.items() if m["priority"] in ("HIGH", "MEDIUM")]
    gate_blockers = []
    if gate_mode and not results_mode:
        gate_blockers.append(f"no runner results: no sdlc.test-results/v1 sidecar in agent_state/phases/{phase}/reports/ "
                             "(an ID counts only when a test named with it RAN and PASSED)")
    if results_err:
        gate_blockers += [f"unreadable results sidecar {e}" for e in results_err]
    if base_err:
        gate_blockers.append(base_err)
    failed = (len(set(missing) | set(failing)) + len(dups) + len(dup_in_phase) + len(ranges) + len(unack)
              + len(malformed) + len(gate_blockers))
    sha, dirty = tci.code_state(g.root)
    verdict = "PASS" if spec and failed == 0 else ("BLOCKED" if not spec else "FAIL")
    return {
        "schema": "sdlc.test-results/v1", "tier": "tc-inventory", "source": "sdlc-graph", "verdict": verdict,
        "phase": phase, "total": len(blocking_ids), "passed": len(blocking_ids) - len(set(missing) | set(failing)),
        "failed": failed, "skipped": len(skipped_only), "flaky": 0, "code_sha": sha, "dirty": dirty,
        "mode": "results" if results_mode else "source", "results": results_used,
        "missing": missing, "failing": failing, "skipped_only": skipped_only, "comment_only": comment_only,
        "duplicate_ids": dups, "duplicate_in_phase": dup_in_phase, "range_annotations": ranges,
        "weakening": weak, "weakening_unacknowledged": unack, "test_changes": changes, "test_change_invalid": invalid,
        "graph": {"range_expanded_ids": expanded, "spec_ranges": spec_ranges, "malformed_ids": malformed,
                  "gate_blockers": gate_blockers, "diff_base": diff_base, "graph_head": g.meta("head")},
        "cases": cases, "ts": now_iso(),
    }


def blocking_lines(inv):
    """One `BLOCKING: …` line per reason (verify-gate.sh reads these)."""
    out = []
    by = {c["name"]: c for c in inv["cases"]}
    if inv["verdict"] == "BLOCKED":
        out.append(f"no TC inventory rows under docs/design/phases/{inv['phase']}/ (a phase with no TC IDs can't pass)")
    for t in inv["missing"]:
        c = by.get(t, {})
        why = "only skipped tests" if t in inv["skipped_only"] else "only a comment" if t in inv["comment_only"] else \
              "no test named with it" + (" ran and passed" if inv["mode"] == "results" else "")
        out.append(f"{t} ({c.get('priority')}, {c.get('tier') or 'no tier'}) uncovered: {why} — {c.get('spec')}"
                   + (" [defined by a range]" if c.get("from_range") else ""))
    for t in inv["failing"]:
        out.append(f"{t} failing: a test named with it FAILED/FLAKY in {', '.join(inv['results']) or 'the results'}")
    for t, ps in sorted(inv["duplicate_ids"].items()):
        out.append(f"{t} is also defined by phase(s) {', '.join(ps)} — IDs are project-unique")
    for t, ws in sorted(inv["duplicate_in_phase"].items()):
        out.append(f"{t} has {len(ws)} inventory rows in this phase: {', '.join(ws)}")
    for r in inv["range_annotations"]:
        out.append(f"range annotation in a test covers nothing: {r}")
    for w in inv["weakening_unacknowledged"]:
        out.append(f"test weakening {w['kind']} at {w['file']}:{w['line']} — needs {w.get('needs', 'an acknowledgement')}")
    for m in inv["graph"]["malformed_ids"]:
        out.append(f"malformed TC ID in an inventory table (row is invisible to the inventory): {m}")
    out += inv["graph"]["gate_blockers"]
    return out


def roster_summary(g, phase):
    r = g.nodes("kind='roster' AND phase=?", phase)
    required = r[0].get("required", []) if r else []
    lines = sorted(g.nodes("kind='exec' AND phase=?", phase), key=lambda d: d["line"])
    last, completed, failed_after = {}, set(), {}
    for e in lines:
        a, st = e.get("agent"), e.get("status")
        if not a:
            continue
        last[a] = e
        if st == "completed":
            completed.add(a)
            failed_after.pop(a, None)
        elif st == "failed":
            failed_after[a] = e["line"]
    reports = {}
    for e in lines:
        if e.get("status") == "completed" and e.get("report"):
            reports[e["agent"]] = e["report"]
    rep_state = []
    for a, rp in sorted(reports.items()):
        exists = os.path.isfile(os.path.join(g.root, rp))
        side = os.path.splitext(rp)[0] + ".json"
        sc = g.nodes("id=?", f"sidecar:{side}")
        md = g.nodes("id=?", f"report:{rp}")
        st = {"agent": a, "report": rp, "exists": exists}
        if sc:
            st.update({k: sc[0].get(k) for k in ("verdict", "total", "failed", "flaky", "code_sha", "dirty")})
        elif md and md[0].get("blocking") is not None:
            st["blocking"] = md[0]["blocking"]
        rep_state.append(st)
    return {"roster_present": bool(r), "required": required, "missing": [a for a in required if a not in completed],
            "dangling_failed": sorted(failed_after), "reports": rep_state}


def evidence_summary(g, phase):
    sha, dirty = tci.code_state(g.root)
    out = []
    for s in g.nodes("kind='sidecar' AND phase=? ORDER BY file", phase):
        if s.get("tier") in TIER_SIDECAR_EXCLUDE and "reconciliation" not in s["file"]:
            continue
        bad_cases = len([1 for e in g.edges("src=? AND rel='result'", s["id"]) if e.get("verdict") in ("FAIL", "FLAKY")])
        out.append({"file": s["file"], "tier": s.get("tier"), "verdict": s.get("verdict"), "total": s.get("total"),
                    "failed": s.get("failed"), "flaky": s.get("flaky"), "failing_case_ids": bad_cases,
                    "stale": bool(sha and s.get("code_sha") and s.get("code_sha") != sha)})
    recon = []
    for r in g.nodes("kind='report' AND phase=? ORDER BY file", phase):
        if "/reconciliation/" in r["file"] and r["file"].endswith(".md"):
            recon.append({"file": r["file"], "blocking": r.get("blocking")})
    return {"code_sha": sha, "dirty": dirty, "sidecars": out, "reconcilers": recon}


# ═══════════════════════════════════════════════════════════════════════════════════════════════
# Queries
# ═══════════════════════════════════════════════════════════════════════════════════════════════
def tests_for(g, tid):
    return g.nodes("kind='test' AND id IN (SELECT src FROM edges WHERE rel='verifies' AND dst=?) ORDER BY file, line", f"tcid:{tid}")


def results_for(g, tid, phase=None):
    rows = g.edges("rel='result' AND dst=?" + (" AND src IN (SELECT id FROM nodes WHERE kind='sidecar' AND phase=?)" if phase else ""),
                   *([f"tcid:{tid}"] + ([phase] if phase else [])))
    vs = [r.get("verdict") for r in rows]
    return "FAIL" if any(v in ("FAIL", "FLAKY") for v in vs) else "PASS" if "PASS" in vs else ("UNTESTED" if rows else None)


def cmd_tc(g, a):
    phase = int(a.phase)
    if a.spec_only:                 # {id: priority} for the results converters — range-defined IDs included
        spec, _, expanded = spec_inventory(g, phase)
        dest = a.out or os.path.join(g.dir, f"tc-priorities-phase-{phase}.json")
        os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
        with open(dest, "w") as f:
            json.dump({k: v["priority"] for k, v in sorted(spec.items())}, f, indent=1)
        return {"_line": f"phase {phase}: {len(spec)} spec TC IDs ({len(expanded)} from definition ranges) -> {dest}"}
    results = None if a.source else (a.results if a.results else discover_results(g, phase))
    inv = tc_inventory(g, phase, results=results or None, diff_base=a.diff_base or None)
    if a.out:                       # the whole inventory, tc-inventory.py's JSON shape + the graph's extra checks
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w") as f:
            json.dump(inv, f, indent=1)
        return {"_line": f"sdlc-graph tc phase {phase}: {inv['verdict']} {inv['passed']}/{inv['total']} HIGH+MEDIUM "
                         f"({inv['mode']} mode, {len(inv['results'])} sidecar(s)); missing {len(inv['missing'])}, failing "
                         f"{len(inv['failing'])}, range-expanded IDs {len(inv['graph']['range_expanded_ids'])}, malformed "
                         f"{len(inv['graph']['malformed_ids'])}; detail {a.out}", "_rc": 0 if inv["verdict"] == "PASS" else 1}
    tiers = [t.strip().lower() for t in (a.tier or "").split(",") if t.strip()]
    prios = [p.strip().upper() for p in (a.priority or "").split(",") if p.strip()]
    rows = []
    for c in inv["cases"]:
        if tiers and c["tier"] not in tiers:
            continue
        if prios and c["priority"] not in prios:
            continue
        done = c["verdict"] == "PASS"
        st = a.status or "all"
        if st == "todo" and done or st == "done" and not done:
            continue
        if st == "missing" and c["name"] not in inv["missing"] or st == "failing" and c["name"] not in inv["failing"]:
            continue
        rows.append(c)
    ids = {c["name"] for c in rows}
    return {"phase": phase, "mode": inv["mode"], "verdict": inv["verdict"], "covered": f"{inv['passed']}/{inv['total']} HIGH+MEDIUM",
            "filter": {"tier": tiers or None, "priority": prios or None, "status": a.status or "all"},
            "counts": {k: len([x for x in inv[k] if x in ids]) for k in ("missing", "failing", "comment_only", "skipped_only")},
            "rows": [{"tc": c["name"], "priority": c["priority"], "tier": c["tier"], "verdict": c["verdict"], "spec": c["spec"],
                      "tests": c["tests"][:3],
                      **({"note": "comment only"} if c["name"] in inv["comment_only"] else
                         {"note": "skipped only"} if c["name"] in inv["skipped_only"] else {}),
                      **({"from_range": True} if c.get("from_range") else {})} for c in rows],
            "problems": {"duplicate_ids": {k: v for k, v in inv["duplicate_ids"].items() if k in ids},
                         "duplicate_in_phase": {k: v for k, v in inv["duplicate_in_phase"].items() if k in ids},
                         "malformed_ids": inv["graph"]["malformed_ids"] if not (tiers or prios) else len(inv["graph"]["malformed_ids"]),
                         "range_expanded_ids": len(inv["graph"]["range_expanded_ids"])}}


def section_rows(g, sids):
    out = []
    key = lambda x: (x.split("#L")[0], int(x.rsplit("#L", 1)[1]) if "#L" in x else 0)
    for sid in sorted(set(sids), key=key):
        n = g.nodes("id=?", sid)
        if n:
            n = n[0]
            out.append({"where": f"{n['file']}:{n['line']}-{n['end_line']}", "title": n["name"], "tokens": n.get("tokens")})
        elif sid.startswith("doc:"):
            d = g.nodes("id=?", sid)
            out.append({"where": sid[4:], "title": "(whole file)", "tokens": d[0].get("tokens") if d else None})
    return out


def handlers_for(g, ep):
    """[(symbol id or file, file, line, confidence)] for an endpoint id. Exact path first, then suffix match."""
    out = []
    rows = g.edges("rel='route' AND dst=?", ep)
    if not rows:
        meth, path = ep[3:].split(" ", 1)
        for e in g.edges("rel='route' AND (dst LIKE ? OR dst LIKE ?)", f"ep:{meth} %{path}", f"ep:ANY %{path}"):
            out_path = e["dst"].split(" ", 1)[1]
            if path.endswith(out_path) or out_path.endswith(path):
                rows.append(dict(e, confidence="suffix"))
    for e in rows:
        h = e.get("handler")
        syms = [s for s in g.nodes("kind='symbol' AND id LIKE ?", f"%#%{h}") if s.get("simple") == h and not s.get("test")]
        same = [s for s in syms if s["file"] == e["file"]]
        dirs = imported_dirs(g, e["file"]) if not same else set()
        imported = [s for s in syms if os.path.dirname(s["file"]) in dirs or os.path.splitext(s["file"])[0] in dirs]
        pick, conf = (same, "") if same else (imported, "+import") if imported else (syms, "+name")
        if pick:
            for s in pick[:3]:
                out.append({"handler": s["id"], "span": f"{s['file']}:{s['line']}-{s['end_line']}", "route_at": f"{e['file']}:{e['line']}",
                            "confidence": e.get("confidence", "regex") + conf})
        else:
            out.append({"handler": h, "span": None, "route_at": f"{e['file']}:{e['line']}", "confidence": e.get("confidence", "regex")})
    return out


def imported_dirs(g, file):
    """Repo dirs / module stems that `file` imports (Go module packages, relative TS/JS, Python dotted)."""
    out = set()
    lang = CODE_EXT.get(os.path.splitext(file)[1])
    mod = None
    if lang == "go":
        m = re.search(r"^module\s+(\S+)", read_text(os.path.join(g.root, "go.mod")), re.M)
        mod = m.group(1) if m else None
    for e in g.edges("src=? AND rel='imports'", f"file:{file}"):
        spec_ = e["dst"].split(":", 2)[2]
        if lang == "go" and mod and spec_.startswith(mod + "/"):
            out.add(spec_[len(mod) + 1:])
        elif lang in ("ts", "js") and spec_.startswith("."):
            out.add(os.path.normpath(os.path.join(os.path.dirname(file), spec_)).replace(os.sep, "/"))
        elif lang == "py":
            out.add(spec_.lstrip(".").replace(".", "/"))
    return out


def phase_endpoints(g, phase):
    return sorted({r[0] for r in g.q("SELECT DISTINCT id FROM nodes WHERE kind='endpoint' AND phase=?", phase)})


# ─── role profiles: which spec sections a non-test role reads ─────────────────────────────────────
# A spec is split into READING UNITS: its preamble (title + intro) and each section at the first heading level
# that repeats (## in a "# Title / ## …" spec). A unit's category comes from its title; content signals
# (SIG_RES) and endpoint mentions refine it. A profile keeps whole units, keeps only the child sections that
# carry a signal ("refine"), or skips the unit — and every skipped unit is listed with its span, so the agent
# can open it when its work touches it. Nothing is hidden; the list is the floor, not the ceiling.
UNIT_CATS = [
    ("test", re.compile(r"test (case|coverage|plan|matrix|scenario)|tests? required|\binventory\b|\btc[- ]?(ids?|rows?)\b|verification matrix")),
    ("trace", re.compile(r"traceab|requirements? map")),
    ("perf", re.compile(r"performance|latency|throughput|\bslos?\b|capacity")),
    ("ui", re.compile(r"\bdom\b|\bcss\b|component tree|layout|wireframe|\bscreens?\b|\b(4|four) states\b|^(the )?states\b|"
                      r"interaction|bindings?|accessib|a11y|responsive|visual|design tokens?|archetype|offline|error boundary|"
                      r"\bpages?\b|\bux\b")),
    ("data", re.compile(r"data model|schema|database|\btables?\b|migrations?|entit|\bindex(es)?\b|persistence|storage|backfill|\bddl\b|\berd\b|columns?")),
    ("api", re.compile(r"contracts?|\bapis?\b|endpoints?|routes?|requests?|responses?|envelope|\bwire\b|grpc|graphql|\bevents?\b|"
                       r"webhooks?|interfaces?|payloads?|error codes?")),
    ("edge", re.compile(r"edge cases?|failure modes?|error (cases|handling)|abuse")),
    ("flow", re.compile(r"flows?\b|behaviou?r|algorithms?|pseudocode|state machine|lifecycle|sequence|processing")),
]
CROSS_CUT_RE = re.compile(r"(?i)envelope|error|convention|common|shared|auth|pagination|canonical|overview|general")
BACKEND_ROLES = {"backend_developer", "api_developer", "backend_audit_agent"}
DB_ROLES = {"database_agent", "migration_agent"}
UI_ROLES = {"ui_developer": "web", "mobile_developer": "mobile", "ui_audit_agent": None}
PROFILE_ROLES = BACKEND_ROLES | DB_ROLES | set(UI_ROLES) | {
    "code_quality_verifier", "tenant_isolation_verifier", "migration_safety_reviewer", "accessibility_auditor",
    "ui_standards_auditor", "spec_impl_reconciler"}
PROFILE_DESC = {
    "backend": "backend/API developer: every component-spec and contract section except test inventories, BRD "
               "traceability and UI-only sections; screen specs belong to the UI roles",
    "db": "schema roles: data-model sections, sections with schema content (CREATE/ALTER, columns, keys), "
          "acceptance criteria and edge cases",
    "ui": "UI developer: your platform's screen specs (minus test inventories), the contract sections for the endpoints "
          "your screens bind, acceptance criteria",
    "code_quality_verifier": "stub check needs the declared endpoints and their handlers only — no spec prose",
    "tenant_isolation_verifier": "data-model sections + sections that define ownership/tenancy (created_by, owner, "
                                 "'their own', tenant)",
    "migration_safety_reviewer": "data-model / schema sections the migrations must satisfy",
    "accessibility_auditor": "web screen specs' accessibility, states, tokens and interaction sections",
    "ui_standards_auditor": "every screen spec section except test inventories (bindings come from the graph)",
    "spec_impl_reconciler": "every spec section except test inventories (spec_test_reconciler's): read each on demand "
                            "while you verify it, using the inventory below",
}


def unit_cat(title):
    t = title.lower()
    for cat, rx in UNIT_CATS:
        if rx.search(t):
            return cat
    return "general"


def doc_lines(g, rel):
    c = g.cache.setdefault("doclines", {})
    if rel not in c:
        c[rel] = read_text(os.path.join(g.root, rel)).split("\n")
    return c[rel]


def span_tokens(g, rel, s, e):
    return sum(len(x) + 1 for x in doc_lines(g, rel)[s - 1:e]) // 4


def doc_units(g, d):
    """[unit] for one spec file: {start, end, title, cat, tokens, sig, eps, children:[same, no children]}."""
    f = d["file"]
    secs = g.nodes("kind='section' AND file=? ORDER BY line", f)
    end = d.get("end_line") or len(doc_lines(g, f))
    eps = [(e["line"], e["dst"]) for e in g.edges("rel='mentions_ep' AND file=?", f)]

    def mk(s, e, title, cat):
        inside = [x for x in secs if s <= x["line"] <= e]
        return {"start": s, "end": e, "title": title, "cat": cat, "tokens": span_tokens(g, f, s, e),
                "sig": set().union(*[set(x.get("sig") or ()) for x in inside]) if inside else set(),
                "eps": {dst for (ln, dst) in eps if ln is not None and s <= ln <= e}}
    counts = {}
    for x in secs:
        counts[x["level"]] = counts.get(x["level"], 0) + 1
    lv = min((k for k, c in counts.items() if c > 1), default=None)
    tops = [x for x in secs if x["level"] == lv] if lv is not None else []
    units = []
    first = tops[0]["line"] if tops else end + 1
    if first > 1:
        units.append(dict(mk(1, first - 1, "(preamble) " + (secs[0]["name"] if secs and secs[0]["line"] < first else ""), "preamble"),
                          children=[]))
    for x in tops:
        u = mk(x["line"], x["end_line"], x["name"], unit_cat(x["name"]))
        kids = [k for k in secs if k["level"] == lv + 1 and x["line"] < k["line"] <= x["end_line"]]
        u["children"] = [mk(k["line"], k["end_line"], k["name"], unit_cat(k["name"])) for k in kids]
        u["intro_end"] = (kids[0]["line"] - 1) if kids else x["end_line"]
        units.append(u)
    return units


def refine(g, f, u, pred):
    """The unit's own intro + the child sections pred keeps; the whole unit when it has no children and pred(u)."""
    if not u.get("children"):
        return [(u["start"], u["end"], u["title"])] if pred(u) else []
    kids = [c for c in u["children"] if pred(c)]
    if not kids:
        return []
    return [(u["start"], u["intro_end"], u["title"] + " (intro)")] + [(c["start"], c["end"], c["title"]) for c in kids]


def profile_choice(role, kind, u, bound, want, g, f):
    """[(start, end, title)] to read from unit u, or a skip reason (str)."""
    cat, sig = u["cat"], u["sig"]
    whole = [(u["start"], u["end"], u["title"])]
    if cat == "test":
        return "test inventory (Wave 3 test agents' work list)"
    if role in BACKEND_ROLES:
        if kind == "screen":
            return "screen spec (UI roles)"
        if kind == "spec" and cat in ("trace", "ui"):
            return "BRD traceability" if cat == "trace" else "UI-only section"
        return whole
    if role in DB_ROLES:
        if kind == "screen":
            return "screen spec (UI roles)"
        if cat in ("data", "preamble") or (kind == "spec" and cat in ("general", "edge")):
            return whole
        got = refine(g, f, u, lambda x: "sql" in x["sig"] or x["cat"] == "data")
        return got or "no schema content"
    if role in UI_ROLES:
        if kind == "screen":
            return whole if want is None or u["platform"] == want else f"{u['platform']} screen (the other UI role)"
        if cat == "preamble" or (kind == "spec" and cat == "general"):
            return whole
        if kind == "contract" and (not bound or CROSS_CUT_RE.search(u["title"])):
            return whole
        if kind == "contract" or cat == "api":
            got = refine(g, f, u, lambda x: bool(x["eps"] & bound))
            return got or "no endpoint your screens bind"
        return "backend-only section"
    if role == "code_quality_verifier":
        return "not needed for the quality checks"
    if role == "tenant_isolation_verifier":
        if kind == "screen":
            return "screen spec"
        if cat == "data":
            return whole
        got = refine(g, f, u, lambda x: "owner" in x["sig"])
        return got or "no ownership/tenancy content"
    if role == "migration_safety_reviewer":
        if kind == "screen":
            return "screen spec"
        if cat == "data":
            return whole
        got = refine(g, f, u, lambda x: "sql" in x["sig"] or x["cat"] == "data")
        return got or "no schema content"
    if role == "accessibility_auditor":
        if kind != "screen" or u["platform"] == "mobile":
            return "not a web screen spec" if kind != "screen" else "mobile screen (mobile_platform_auditor)"
        if cat == "preamble" or "a11y" in sig or re.search(r"(?i)accessib|a11y|states?\b|tokens?|css|interaction|focus|keyboard", u["title"]):
            return whole
        return "no accessibility-relevant content"
    if role == "ui_standards_auditor":
        return whole if kind == "screen" else "bindings come from the graph (screens below)"
    if role == "spec_impl_reconciler":
        return whole
    return whole


def profile_sections(g, phase, role):
    """(read rows, skipped rows, read tokens, whole-dir tokens) for a profile role."""
    docs = g.nodes("kind IN ('spec','screen_spec') AND phase=? ORDER BY file", phase)
    want = UI_ROLES.get(role)
    if role in UI_ROLES and want and not any(d.get("platform") == want for d in docs if d["kind"] == "screen_spec"):
        want = None                                   # no screen is marked for this platform: can't tell, read them all
    bound = set()
    if role in UI_ROLES:
        for s in g.nodes("kind='screen' AND phase=?", phase):
            d = next((x for x in docs if x["file"] == s["file"]), None)
            if want is None or (d and d.get("platform") == want):
                bound |= {e["dst"] for e in g.edges("src=? AND rel='binds'", s["id"])}
        for d in docs:
            if d["kind"] == "screen_spec" and (want is None or d.get("platform") == want):
                bound |= {e["dst"] for e in g.edges("rel='mentions_ep' AND file=?", d["file"])}
    read, skipped, read_tok, whole_tok = [], [], 0, 0
    for d in docs:
        f, base = d["file"], os.path.basename(d["file"])
        kind = "screen" if d["kind"] == "screen_spec" else "contract" if CONTRACT_RE.search(base) else "spec"
        whole_tok += d.get("tokens") or 0
        spans, skips = [], []
        units = doc_units(g, d)
        for u in units:
            u["platform"] = d.get("platform")
            ch = profile_choice(role, kind, u, bound, want, g, f)
            if isinstance(ch, str):
                skips.append((u, ch))
            else:
                spans += ch
                if len(ch) > 1:            # refined: the unit's other children are skipped
                    kept = {(s_, e_) for (s_, e_, _) in ch}
                    skips += [(c, "not in your scope") for c in u.get("children", []) if (c["start"], c["end"]) not in kept]
        if spans and not any(s_ == 1 for (s_, _, _) in spans):
            pre = [u for u in units if u["cat"] == "preamble"]
            if pre:
                spans.insert(0, (1, pre[0]["end"], pre[0]["title"]))
                skips = [(u, r) for (u, r) in skips if u["cat"] != "preamble"]
        spans.sort()
        merged = []
        for (s_, e_, t_) in spans:
            if merged and s_ <= merged[-1][1] + 2:
                merged[-1][1] = max(merged[-1][1], e_)
                merged[-1][2].append(t_)
            else:
                merged.append([s_, e_, [t_]])
        if merged:
            tok = sum(span_tokens(g, f, s_, e_) for (s_, e_, _) in merged)
            read_tok += tok
            titles = [re.sub(r"\s+", " ", t)[:34] for m in merged for t in m[2] if not t.startswith("(preamble)")]
            read.append(f"{f}: " + ", ".join(f"{s_}-{e_}" for (s_, e_, _) in merged) + f" (~{tok:,} tok)"
                        + (" — " + "; ".join(titles[:6]) + (f"; +{len(titles) - 6}" if len(titles) > 6 else "") if titles else ""))
        if skips:
            stok = sum(u["tokens"] for (u, _) in skips)
            if not merged:
                skipped.append(f"{f} (whole file, ~{d.get('tokens') or stok:,} tok): {skips[0][1]}")
            else:
                why = {}
                for (u, r) in skips:
                    why.setdefault(r, []).append(f"{u['start']}-{u['end']}")
                skipped.append(f"{f}: ~{stok:,} tok — " + "; ".join(f"{r} {', '.join(v[:4])}{' …' if len(v) > 4 else ''}" for r, v in why.items()))
    return read, skipped, read_tok, whole_tok


def context_profile(g, phase, role):
    read, skipped, read_tok, whole_tok = profile_sections(g, phase, role)
    key = ("backend" if role in BACKEND_ROLES else "db" if role in DB_ROLES else "ui" if role in UI_ROLES else role)
    results = discover_results(g, phase)
    inv = tc_inventory(g, phase, results=results or None)
    tiers = {}
    for c in inv["cases"]:
        tiers[c["tier"] or "?"] = tiers.get(c["tier"] or "?", 0) + 1
    out = {"agent": role, "phase": phase, "profile": PROFILE_DESC[key]}
    rf = [p for p in (os.path.join("docs", "design", "phases", str(phase), "phase_context.md"),
                      os.path.join("docs", "design", "phases", str(phase), "threat_model.md"))
          if os.path.exists(os.path.join(g.root, p))]
    out["read_first"] = rf
    out["spec_sections_to_read (file: line spans)"] = read
    out["spec_sections_tokens"] = read_tok
    out["whole_specs_dir_tokens"] = whole_tok
    out["skipped (open on demand: file: start-end)"] = skipped
    spec_tc = {r["name"]: r for r in g.nodes("kind='tc' AND phase=?", phase)}
    eps = phase_endpoints(g, phase)
    if role in BACKEND_ROLES or role in DB_ROLES:
        out["tc_rows_by_tier (tests are Wave 3's; `tc --phase N` lists them)"] = tiers
    if role in BACKEND_ROLES or role in UI_ROLES:
        out["security_rows (TC-SEC: implement the mitigation)"] = [
            f"{c['name']} {c['priority']} {c['spec']} {(spec_tc.get(c['name']) or {}).get('desc', '')[:90]}"
            for c in inv["cases"] if c["name"].startswith("TC-SEC-")]
    if role in BACKEND_ROLES:
        out["endpoints"] = [{"endpoint": e[3:], "handlers": [h["span"] or h["handler"] for h in handlers_for(g, e)[:2]]} for e in eps]
    if role in DB_ROLES:
        out["tables (existing)"] = sorted({r[0][6:] for r in g.q("SELECT DISTINCT id FROM nodes WHERE kind='table'")})
    if role in UI_ROLES:
        want = UI_ROLES[role]
        docs = {d["file"]: d for d in g.nodes("kind='screen_spec' AND phase=?", phase)}
        if want and not any(d.get("platform") == want for d in docs.values()):
            want = None
        scr = [s for s in g.nodes("kind='screen' AND phase=? ORDER BY name", phase)
               if want is None or (docs.get(s["file"]) or {}).get("platform") == want]
        out["screens"] = [{"screen": s["name"], "route": s.get("route"), "spec": s["file"],
                           "binds": [e["dst"][3:] for e in g.edges("src=? AND rel='binds'", s["id"])]} for s in scr]
        bound = sorted({e["dst"] for s in scr for e in g.edges("src=? AND rel='binds'", s["id"])})
        out["bound_endpoints (declared in a contract?)"] = [
            f"{e[3:]} → " + (", ".join(f"{x['file']}:{x['line']}" for x in g.edges("rel='declares' AND dst=?", e)[:2]) or "NOT DECLARED")
            for e in bound]
    if role == "code_quality_verifier":
        rows = [{"endpoint": e[3:], "handlers": [h["span"] or h["handler"] for h in handlers_for(g, e)[:2]]} for e in eps]
        out["endpoints (Check 2: verify each handler is substantive)"] = rows
        out["endpoints_without_handler"] = [r["endpoint"] for r in rows if not r["handlers"]]
    if role == "tenant_isolation_verifier":
        files, _ = changed_since(g, default_base(g, phase))
        id_routes = []
        for e in g.edges("rel='route'"):
            if "{}" in e["dst"] and (files is None or e["file"] in files):
                hs = handlers_for(g, e["dst"])
                id_routes.append(f"{e['dst'][3:]} @{e['file']}:{e['line']} handler "
                                 + (", ".join(h["span"] or h["handler"] for h in hs[:2] if h["route_at"] == f"{e['file']}:{e['line']}") or e.get("handler") or "?"))
        out["id_routes (changed this phase; Step 1 seed — grep for what regex routes miss)"] = sorted(set(id_routes))
    if role == "migration_safety_reviewer":
        files, _ = changed_since(g, default_base(g, phase))
        migs = sorted(f for f in (files or {}) if g.q("SELECT 1 FROM files WHERE path=? AND kind IN ('migration','prisma')", f))
        out["migrations_changed (UP/DOWN to review)"] = [
            {"file": f, "creates": sorted({e["dst"][6:] for e in g.edges("file=? AND rel='creates'", f)}),
             "alters": sorted({e["dst"][6:] for e in g.edges("file=? AND rel='alters'", f)})} for f in migs]
    if role == "accessibility_auditor":
        out["a11y_rows (results: e2e_results.json)"] = [
            f"{c['name']} {c['priority']} {c['tier'] or '?'} {c['spec']} {c['verdict']}" for c in inv["cases"]
            if c["name"].startswith("TC-A11Y-") or SIG_RES["a11y"].search((spec_tc.get(c["name"]) or {}).get("desc", ""))]
        out["screens (web)"] = [{"screen": s["name"], "route": s.get("route"), "spec": s["file"]}
                                for s in g.nodes("kind='screen' AND phase=? ORDER BY name", phase)
                                if (g.nodes("id=?", f"doc:{s['file']}") or [{}])[0].get("platform") != "mobile"]
    if role == "ui_standards_auditor":
        pages = g.nodes("kind='page'")
        base = {norm_path(p["route"]): p["name"] for p in pages if p.get("route")}
        out["screens (all phases)"] = [
            f"{s['name']} p{s['phase']} {s.get('route') or 'no route'} stitch={base.get(norm_path(s['route'])) if s.get('route') else None} "
            f"binds={','.join(sorted({(x.get('shape') or 'OBJECT')[0] + ':' + x['dst'][3:] for x in g.edges('src=? AND rel=?', s['id'], 'binds')}))}"
            for s in g.nodes("kind='screen' ORDER BY phase, name")]
    if role == "spec_impl_reconciler":
        rows = [(e[3:], handlers_for(g, e)) for e in eps]
        out["endpoints declared → handler (Level 1)"] = [f"{e} → {(hs[0]['span'] or hs[0]['handler']) if hs else 'MISSING'}" for e, hs in rows]
        files, _ = changed_since(g, default_base(g, phase))
        declared_all = {r[0] for r in g.q("SELECT DISTINCT id FROM nodes WHERE kind='endpoint'")}
        out["routes changed this phase with no contract (impl → spec)"] = sorted({
            f"{e['dst'][3:]} @{e['file']}:{e['line']}" for e in g.edges("rel='route'")
            if (files is None or e["file"] in files) and e["dst"] not in declared_all})
        types = g.nodes("kind='type' AND phase=? ORDER BY name", phase)
        tdefs = {}
        for t in types:
            hit = [s for s in g.nodes("kind='symbol' AND name=?", t["name"]) if not s.get("test")]
            tdefs[t["name"]] = f"{hit[0]['file']}:{hit[0]['line']}" if hit else "NOT FOUND (by name)"
        out["contract types → code"] = [f"{k} ({next(t['file'] for t in types if t['name'] == k)}) → {v}" for k, v in sorted(tdefs.items())]
        in_scope = sorted({e["src"][4:] for e in g.edges("rel='assigned_to' AND dst=?", f"phase:{phase}")})
        mentioned = {e["dst"][4:] for e in g.edges("rel='mentions_req' AND file LIKE ?", f"docs/design/phases/{phase}/specs/%")}
        out["FRs in scope with no spec section"] = [r for r in in_scope if r not in mentioned]
    out["note"] = ("Read the listed spans (file: start-end) instead of the whole specs/ directory; open a skipped span when "
                   "your work touches it. Lists ending '… +N more' were capped: re-run with --full. Code links are rung-1 "
                   "regex (by name): confirm before you act on one.")
    return out


PROTECTED_KEYS = ("spec_sections_to_read (file: line spans)", "read_first")


def cmd_context(g, a):
    phase, role = int(a.phase), a.agent
    if role in PROFILE_ROLES:
        return context_profile(g, phase, role)
    tiers = ROLE_TIERS.get(role)
    results = discover_results(g, phase)
    inv = tc_inventory(g, phase, results=results or None)
    rows = [c for c in inv["cases"] if (tiers is None or c["tier"] in tiers or (c["tier"] == "" and role in ROLE_TIERS))]
    todo = [c for c in rows if c["verdict"] != "PASS"]
    done = [c["name"] for c in rows if c["verdict"] == "PASS"]
    todo.sort(key=lambda c: ({"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(c["priority"], 3), c["name"]))
    # the spec sections to read: each todo row's inventory section + every section that mentions the ID
    sids = set()
    spec_tc = {r["name"]: r for r in g.nodes("kind='tc' AND phase=?", phase)}
    for c in (todo if tiers else rows):
        r = spec_tc.get(c["name"])
        if r and r.get("sec"):
            sids.add(r["sec"])
        for e in g.edges("rel='mentions_tc' AND dst=? AND file LIKE ?", f"tcid:{c['name']}", f"docs/design/phases/{phase}/specs/%"):
            sids.add(e["src"])
    eps = phase_endpoints(g, phase)
    if tiers is not None and not set(tiers) & {"integration", "e2e", "acceptance", "performance", "system", "component"}:
        eps_rel = []
    else:
        eps_rel = eps
    # contract sections for endpoints the todo rows exercise (tiers that call the API)
    for c in (todo if eps_rel else []):
        for e in g.edges("src=? AND rel='exercises_ep'", f"tc:{phase}/{c['name']}"):
            for d in g.edges("rel='declares' AND dst=?", e["dst"]):
                n = g.nodes("kind='section' AND file=? AND line<=? AND end_line>=? ORDER BY line DESC", d["file"], d["line"], d["line"])
                if n:
                    sids.add(n[0]["id"])
    endpoints = []
    for e in eps_rel:
        endpoints.append({"endpoint": e[3:], "handlers": handlers_for(g, e)[:2]})
    ctx = os.path.join("docs", "design", "phases", str(phase), "phase_context.md")
    out = {"agent": role, "phase": phase, "tiers": tiers or "all (developer/auditor: whole phase)", "results_mode": inv["mode"],
           "read_first": [ctx] if os.path.exists(os.path.join(g.root, ctx)) else [],
           "todo (id priority tier spec-row [status])": [
               f"{c['name']} {c['priority']} {c['tier'] or '?'} {c['spec']}" + (" FAILING" if c["verdict"] == "FAIL" else "")
               + (" [defined by a range]" if c.get("from_range") else "") for c in todo],
           "done": done, "spec_sections_to_read": section_rows(g, sids), "endpoints": endpoints}
    out["spec_sections_tokens"] = sum(x.get("tokens") or 0 for x in out["spec_sections_to_read"])
    out["whole_specs_dir_tokens"] = sum(d.get("tokens") or 0 for d in g.nodes("kind IN ('spec','screen_spec') AND phase=?", phase))
    if role in DEV_ROLES or tiers is None:
        out["tables"] = sorted({r[0][6:] for r in g.q("SELECT DISTINCT id FROM nodes WHERE kind='table'")})
        out["specs"] = [{"file": d["file"], "tokens": d.get("tokens")} for d in g.nodes("kind IN ('spec','screen_spec') AND phase=? ORDER BY file", phase)]
    if role in ("ui_test_agent", "ui_developer", "mobile_developer", "mobile_test_agent", "ui_audit_agent"):
        out["screens"] = [{"screen": s["name"], "route": s.get("route"), "spec": s["file"],
                           "binds": [e["dst"][3:] for e in g.edges("src=? AND rel='binds'", s["id"])]}
                          for s in g.nodes("kind='screen' AND phase=? ORDER BY name", phase)]
    out["note"] = ("Read ONLY the listed sections (file:start-end); open more of a spec only when a row needs it. "
                   "TC IDs go in test NAMES. 'status' is from the latest runner sidecar when one exists, else from source.")
    return out


def changed_since(g, base):
    """{file: [(start, end)]} of changed line ranges in the NEW file since base (committed + working tree)."""
    diff = git(g.root, "diff", "--unified=0", "--no-color", base, "--", ".", ":(exclude)agent_state", ":(exclude)docs/design/stitch")
    if diff is None:
        return None, []
    files, cur, deleted, prev = {}, None, [], None
    for l in diff.splitlines():
        if l.startswith("+++ "):
            cur = l[6:] if l.startswith("+++ b/") else None
            if cur:
                files.setdefault(cur, [])
        elif l.startswith("--- a/"):
            prev = l[6:]
        if l.startswith("+++ /dev/null") and prev:
            deleted.append(prev)
        m = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", l)
        if m and cur:
            s, n = int(m.group(1)), int(m.group(2)) if m.group(2) is not None else 1
            files[cur].append((s, s + max(n, 1) - 1))
    for l in (git(g.root, "ls-files", "--others", "--exclude-standard") or "").splitlines():
        if not l.startswith("agent_state/"):
            files.setdefault(l, []).append((1, 10 ** 9))
    return files, deleted


def changed_symbols(g, files):
    out = []
    for f, ranges in sorted(files.items()):
        for s in g.nodes("kind='symbol' AND file=? ORDER BY line", f):
            if any(a <= (s["end_line"] or s["line"]) and b >= s["line"] for a, b in ranges):
                out.append(s)
    return out


def default_base(g, phase):
    if phase is not None:
        for fn in ("base_sha",):
            p = os.path.join(g.root, "agent_state", "phases", str(phase), fn)
            if os.path.exists(p) and open(p).read().strip():
                return open(p).read().strip()
    return "HEAD~1"


def callers_of(g, sym):
    simple = sym.get("simple") or sym["name"].split(".")[-1]
    c = g.cache.setdefault("callers", {})
    if simple not in c:
        c[simple] = g.nodes("kind='symbol' AND id IN (SELECT src FROM edges WHERE rel='calls' AND dst=?) ORDER BY file, line", f"name:{simple}")
    return [x for x in c[simple] if x["id"] != sym["id"]]


def importers_of(g, file):
    """Files whose import strings resolve to `file`'s package/module (Go package dir, relative TS/JS, Python dotted)."""
    c = g.cache.setdefault("importers", {})
    if file not in c:
        c[file] = _importers_of(g, file)
    return c[file]


def _rel_imports(g, lang):
    """[(importing file, resolved target stem)] for relative TS/JS imports — computed once per query."""
    key = f"relimp:{lang}"
    if key not in g.cache:
        out = []
        for e in g.edges("rel='imports' AND dst LIKE ?", f"imp:{lang}:.%"):
            spec_ = e["dst"].split(":", 2)[2]
            out.append((e["file"], os.path.normpath(os.path.join(os.path.dirname(e["file"]), spec_)).replace(os.sep, "/")))
        g.cache[key] = out
    return g.cache[key]


def _importers_of(g, file):
    lang = CODE_EXT.get(os.path.splitext(file)[1])
    d = os.path.dirname(file)
    keys = set()
    if lang == "go":
        gm = read_text(os.path.join(g.root, "go.mod"))
        m = re.search(r"^module\s+(\S+)", gm, re.M)
        if m:
            keys.add(f"imp:go:{m.group(1)}/{d}" if d else f"imp:go:{m.group(1)}")
    elif lang == "py":
        mod = os.path.splitext(file)[0].replace("/", ".")
        keys.add(f"imp:py:{mod}")
        for pre in ("src.", "app."):
            if mod.startswith(pre):
                keys.add(f"imp:py:{mod[len(pre):]}")
    out = set()
    if keys:
        for e in g.edges("rel='imports' AND dst IN (%s)" % ",".join("?" * len(keys)), *sorted(keys)):
            if e["file"] != file:
                out.add(e["file"])
    if lang in ("ts", "js"):
        stem = os.path.splitext(file)[0]
        for src, tgt in _rel_imports(g, lang):
            if tgt in (stem, stem.rsplit("/index", 1)[0]) and src != file:
                out.add(src)
    if lang == "go":   # same-package files see each other without imports
        for f in g.q("SELECT path FROM files WHERE path LIKE ? AND kind IN ('code','test')", (d + "/%") if d else "%"):
            if os.path.dirname(f[0]) == d and f[0] != file and f[0].endswith(".go"):
                out.add(f[0])
    return sorted(out)


def endpoints_of_symbol(g, sym):
    """Routes whose handler name is this symbol's: in its own file, or in a route file that defines no
    symbol of that name (then the handler must live elsewhere — name-resolved, rung 1)."""
    if "routes" not in g.cache:
        by_handler = {}
        for e in g.edges("rel='route'"):
            by_handler.setdefault(e.get("handler"), []).append((e["file"], e["dst"]))
        g.cache["routes"] = by_handler
        fs = set()
        for f, attrs in g.q("SELECT file, attrs FROM nodes WHERE kind='symbol'"):
            fs.add((f, json.loads(attrs or "{}").get("simple")))
        g.cache["file_simple"] = fs
    simple = sym.get("simple") or sym["name"].split(".")[-1]
    out = set()
    for f, ep in g.cache["routes"].get(simple, ()):
        if f == sym["file"] or (f, simple) not in g.cache["file_simple"]:
            out.add(ep)
    return sorted(out)


def tc_of_tests(g, test_files):
    out = set()
    for f in test_files:
        for t in g.nodes("kind='test' AND file=?", f):
            out |= set(t.get("ids") or [])
    return sorted(out)


def enclosing_secs(g, file, line):
    return [n["id"] for n in g.nodes("kind='section' AND file=? AND line<=? AND end_line>=?", file, line, line)]


def reqs_of_tc_row(g, r):
    """Row-level FR refs win; else every FR its section or an enclosing section (e.g. the spec title) names."""
    if r.get("reqs"):
        return set(r["reqs"]), "row"
    out = set()
    for sid in enclosing_secs(g, r["file"], r["line"]):
        out |= {e["dst"][4:] for e in g.edges("src=? AND rel='mentions_req'", sid) if e["line"] == int(sid.rsplit("#L", 1)[1]) or sid == r.get("sec")}
    return out, "section"


def reqs_of_tcs(g, tcs):
    out = set()
    for t in tcs:
        for r in g.nodes("kind='tc' AND name=?", t):
            out |= reqs_of_tc_row(g, r)[0]
    return sorted(out)


def resolve_target(g, target):
    """file path | sym id | Qual.name | name → (kind, [nodes])."""
    t = target.strip()
    if t.startswith("sym:"):
        return "symbol", g.nodes("id=?", t)
    if os.path.exists(os.path.join(g.root, t)) or g.q("SELECT 1 FROM files WHERE path=?", t):
        return "file", [{"id": f"file:{t}", "file": t, "name": t}]
    if "#" in t:
        return "symbol", g.nodes("id=?", f"sym:{t}")
    syms = g.nodes("kind='symbol' AND name=? ORDER BY file", t) or \
        [s for s in g.nodes("kind='symbol' AND id LIKE ? ORDER BY file", f"%#%{t.split('.')[-1]}") if s.get("simple") == t.split(".")[-1]]
    return "symbol", syms


def impact_of(g, syms, files, depth=3):
    seen, frontier = {s["id"]: s for s in syms}, list(syms)
    for _ in range(depth):
        nxt = []
        for s in frontier:
            for c in callers_of(g, s):
                if c["id"] not in seen:
                    seen[c["id"]] = c
                    nxt.append(c)
        frontier = nxt
    importer_files = set()
    for f in files:
        importer_files |= set(importers_of(g, f))
    eps = sorted({e for s in seen.values() for e in endpoints_of_symbol(g, s)})
    screens = sorted({e["src"] for ep in eps for e in g.edges("rel='binds' AND dst=?", ep)})
    fe = sorted({e["src"] for ep in eps for e in g.edges("rel='calls_endpoint' AND dst=?", ep)})
    test_files = sorted({s["file"] for s in seen.values() if s.get("test")} |
                        {f for f in importer_files if g.q("SELECT 1 FROM files WHERE path=? AND kind='test'", f)} |
                        {f for f in files if g.q("SELECT 1 FROM files WHERE path=? AND kind='test'", f)})
    tcs = tc_of_tests(g, test_files)
    tables = sorted({e["dst"][6:] for s in seen.values() for e in g.edges("src=? AND rel IN ('reads','writes')", s["id"])})
    return {"changed": sorted(s["id"] for s in syms), "affected_symbols": sorted(set(seen) - {s["id"] for s in syms}),
            "importer_files": sorted(importer_files), "endpoints": [e[3:] for e in eps], "tables": tables,
            "screens_binding": screens, "frontend_callers": fe, "tests_to_run": test_files, "tc_ids": tcs,
            "requirements": reqs_of_tcs(g, tcs), "confidence": "regex rung: calls resolve by name"}


def cmd_impact(g, a):
    kind, ns = resolve_target(g, a.target)
    if not ns:
        return {"target": a.target, "error": "not found (give a repo path, sym:<file>#<Qual.name>, or a symbol name)"}
    if kind == "file":
        syms = g.nodes("kind='symbol' AND file=? ORDER BY line", ns[0]["file"])
        return {"target": a.target, **impact_of(g, syms, [ns[0]["file"]])}
    return {"target": a.target, **impact_of(g, ns, sorted({s["file"] for s in ns}))}


def consumers_one(g, target):
    t = target.strip()
    m = re.match(r"^(GET|POST|PUT|PATCH|DELETE)\s+(/\S*)$", t, re.I)
    if m:
        e = ep_id(m.group(1), m.group(2))
        return {"endpoint": e[3:], "declared_in": [f"{d['file']}:{d['line']}" for d in g.edges("rel='declares' AND dst=?", e)],
                "handlers": handlers_for(g, e),
                "frontend_callers": [f"{x['src']} @{x['file']}:{x['line']}" for x in g.edges("rel='calls_endpoint' AND dst=?", e)],
                "screen_bindings": [{"screen": x["src"], "component": x.get("component"), "field": x.get("field"), "shape": x.get("shape"),
                                     "at": f"{x['file']}:{x['line']}"} for x in g.edges("rel='binds' AND dst=?", e)],
                "tc_rows": sorted({f"{x['src'].split('/', 1)[1]} (phase {x['src'][3:].split('/')[0]})" for x in g.edges("rel='exercises_ep' AND dst=?", e)})}
    if t.startswith("table:"):
        tb = f"table:{t[6:].lower()}"
        return {"table": tb[6:], "created_by": [f"{x['file']}:{x['line']}" for x in g.edges("rel IN ('creates','maps_table') AND dst=?", tb)],
                "altered_by": [f"{x['file']}:{x['line']}" for x in g.edges("rel='alters' AND dst=?", tb)],
                "readers": sorted({x["src"] for x in g.edges("rel='reads' AND dst=?", tb)}),
                "writers": sorted({x["src"] for x in g.edges("rel='writes' AND dst=?", tb)})}
    kind, ns = resolve_target(g, t)
    if not ns:
        return {"target": t, "error": "not found"}
    out = []
    for s in ns[:5]:
        if kind == "file":
            out.append({"file": s["file"], "importers": importers_of(g, s["file"])})
            continue
        eps = endpoints_of_symbol(g, s)
        out.append({"symbol": s["id"], "span": f"{s['file']}:{s['line']}-{s['end_line']}",
                    "callers": [f"{c['id']} ({c['file']}:{c['line']})" for c in callers_of(g, s)],
                    "importers_of_file": importers_of(g, s["file"]),
                    "endpoints": [e[3:] for e in eps],
                    "frontend_callers": sorted({x["src"] for e in eps for x in g.edges("rel='calls_endpoint' AND dst=?", e)}),
                    "screen_bindings": sorted({x["src"] for e in eps for x in g.edges("rel='binds' AND dst=?", e)}),
                    "confidence": "name" if len(ns) > 1 else "regex"})
    return {"target": t, "matches": len(ns), "consumers": out}


def phase_introduced(g, file):
    """Earliest phase-N-complete tag that already contains the file (None = not in any gated phase)."""
    if "tagfiles" not in g.cache:
        tf = {}
        for t in (git(g.root, "tag", "--list", "phase-*-complete") or "").split():
            m = re.match(r"phase-(\d+)-complete$", t)
            if m:
                tf[int(m.group(1))] = set((git(g.root, "ls-tree", "-r", "--name-only", t) or "").splitlines())
        g.cache["tagfiles"] = tf
    hits = [n for n, files in g.cache["tagfiles"].items() if file in files]
    return min(hits) if hits else None


def git_show_many(root, rev, files):
    """{file: text or None} for `rev:file` of many files in one `git cat-file --batch` process."""
    out = {}
    if not files:
        return out
    try:
        p = subprocess.Popen(["git", "-C", root, "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        data, _ = p.communicate("".join(f"{rev}:{f}\n" for f in files).encode())
    except OSError:
        return {f: None for f in files}
    pos = 0
    for f in files:
        nl = data.find(b"\n", pos)
        head = data[pos:nl].decode(errors="replace").split()
        pos = nl + 1
        if len(head) == 3 and head[1] == "blob":
            size = int(head[2])
            out[f] = data[pos:pos + size].decode("utf-8", errors="replace")
            pos += size + 1
        else:
            out[f] = None
    return out


def cmd_consumers(g, a):
    if not a.changed_since:
        if not a.target:
            return {"error": "give a target or --changed-since SHA"}
        return consumers_one(g, a.target)
    files, deleted = changed_since(g, a.changed_since)
    if files is None:
        return {"error": f"git diff against {a.changed_since} failed"}
    syms = changed_symbols(g, {f: r for f, r in files.items() if not g.q("SELECT 1 FROM files WHERE path=? AND kind='test'", f)})
    changed_files = set(files)
    old_defs = {}
    for f, old in git_show_many(g.root, a.changed_since, sorted({s["file"] for s in syms})).items():
        lang = CODE_EXT.get(os.path.splitext(f)[1])
        old_defs[f] = {d_[1] for d_ in DEFS.get(lang, lambda _l: [])(old.split("\n"))} if old is not None else set()
    rows = []
    for s in syms:
        if re.fullmatch(r"__\w+__", s.get("simple") or ""):
            continue                                  # dunders resolve by name to every class: noise at rung 1
        ext = [c for c in callers_of(g, s) if c["file"] not in changed_files]
        imps = [f for f in importers_of(g, s["file"]) if f not in changed_files]
        eps = endpoints_of_symbol(g, s)
        fe = sorted({x["src"] for e in eps for x in g.edges("rel='calls_endpoint' AND dst=?", e)})
        scr = sorted({x["src"] for e in eps for x in g.edges("rel='binds' AND dst=?", e)})
        if not (ext or eps or fe or scr):
            continue
        rows.append({"changed": s["id"], "span": f"{s['file']}:{s['line']}-{s['end_line']}",
                     "existed_at_base": s["name"] in old_defs.get(s["file"], set()),
                     "file_in_gated_phase": phase_introduced(g, s["file"]), "endpoints": [e[3:] for e in eps],
                     "external_callers": [f"{c['id']} ({c['file']}:{c['line']})" for c in ext][:15],
                     "importer_files_outside_change": imps[:15], "frontend_callers": fe, "screen_bindings": scr})
    contracts = []
    for f in sorted(files):
        if re.search(r"docs/design/phases/\d+/.*(contracts?|\.wireframe|\.ui-spec)", f):
            contracts.append(f)
    tables = sorted({e["dst"][6:] for f in files for e in g.edges("file=? AND rel IN ('creates','alters')", f)})
    rows.sort(key=lambda r: (not r["existed_at_base"], -(len(r["external_callers"]) + len(r["endpoints"]) + len(r["frontend_callers"]))))
    return {"since": a.changed_since, "changed_files": len(files), "deleted_files": deleted, "changed_symbols": len(syms),
            "with_consumers": rows, "migrations_touch_tables": [consumers_one(g, f"table:{t}") for t in tables][:10],
            "note": "callers resolve by NAME (rung 1): confirm each with the language server before calling it breaking."}


def cmd_diff_context(g, a):
    phase = int(a.phase) if a.phase is not None else None
    base = a.base or default_base(g, phase)
    files, deleted = changed_since(g, base)
    if files is None:
        return {"error": f"git diff against {base} failed (give --base SHA)"}
    syms = changed_symbols(g, files)
    sym_rows = []
    for s in syms:
        eps = endpoints_of_symbol(g, s)
        tables = sorted({e["dst"][6:] for e in g.edges("src=? AND rel IN ('reads','writes')", s["id"])})
        sym_rows.append({"symbol": s["name"], "span": f"{s['file']}:{s['line']}-{s['end_line']}",
                         **({"test": True} if s.get("test") else {}), "endpoints": [e[3:] for e in eps], "tables": tables})
    # spec sections governing the change: sections that mention a touched endpoint
    eps = sorted({e for r in sym_rows for e in r["endpoints"]})
    sids = set()
    for e in eps:
        for x in g.edges("rel IN ('mentions_ep') AND dst=?", f"ep:{e}"):
            if phase is None or x["file"].startswith(f"docs/design/phases/{phase}/"):
                sids.add(x["src"])
        for x in g.edges("rel='declares' AND dst=?", f"ep:{e}"):
            n = g.nodes("kind='section' AND file=? AND line<=? AND end_line>=? ORDER BY line DESC", x["file"], x["line"], x["line"])
            if n:
                sids.add(n[0]["id"])
    test_files = sorted(f for f in files if g.q("SELECT 1 FROM files WHERE path=? AND kind='test'", f))
    tcs = tc_of_tests(g, test_files)
    other = sorted(f for f in files if not g.q("SELECT 1 FROM files WHERE path=? AND kind IN ('code','test')", f))
    return {"base": base, "head": g.meta("head"), "changed_code_files": sorted(f for f in files if f not in other),
            "other_changed_files": other, "deleted_files": deleted, "changed_symbols": sym_rows,
            "endpoints_touched": eps, "tc_ids_in_changed_tests": tcs, "requirements": reqs_of_tcs(g, tcs),
            "spec_sections_to_read": section_rows(g, sids),
            "note": "Review the changed spans (read each file:start-end), then the listed spec sections. "
                    "`consumers --changed-since <base>` lists who depends on each changed symbol."}


def cmd_trace(g, a):
    t = a.id.strip()
    if t.startswith("TC-"):
        rows = g.nodes("kind='tc' AND name=? ORDER BY phase, file, line", t)
        tests = tests_for(g, t)
        return {"tc": t, "defined_in": [{"phase": r["phase"], "spec": f"{r['file']}:{r['line']}", "priority": r.get("priority"),
                                         "tier": r.get("tier"), "section": r.get("section"), **({"from_range": True} if r.get("from_range") else {})} for r in rows],
                "tests": [{"test": x["name"], "at": f"{x['file']}:{x['line']}", "skipped": x.get("skipped")} for x in tests],
                "results": [{"sidecar": e["src"][8:], "verdict": e.get("verdict")} for e in g.edges("rel='result' AND dst=?", f"tcid:{t}")],
                "requirements": reqs_of_tcs(g, [t]),
                "mentioned_in": sorted({f"{e['file']}:{e['line']}" for e in g.edges("rel='mentions_tc' AND dst=?", f"tcid:{t}")})[:10]}
    rid = f"req:{t}"
    req = g.nodes("id=?", rid)
    phases = sorted({e["dst"][6:] for e in g.edges("src=? AND rel='assigned_to'", rid)}, key=lambda x: int(x) if x.isdigit() else 0)
    secs = sorted({e["src"] for e in g.edges("rel='mentions_req' AND dst=?", rid) if e["src"].startswith("sec:")})
    tcs = {}
    files_mentioning = {e["file"] for e in g.edges("rel='mentions_req' AND dst=?", rid)}
    for r in g.nodes("kind='tc' ORDER BY phase, name"):
        if t in (r.get("reqs") or []) or (not r.get("reqs") and r["file"] in files_mentioning and t in reqs_of_tc_row(g, r)[0]):
            tcs.setdefault(r["name"], r)
    tc_rows = []
    for name, r in sorted(tcs.items()):
        tests = tests_for(g, name)
        tc_rows.append({"tc": name, "phase": r["phase"], "priority": r.get("priority"), "tier": r.get("tier"),
                        "link": reqs_of_tc_row(g, r)[1], "tests": len([x for x in tests if not x.get("skipped")]),
                        "result": results_for(g, name)})
    eps = set()
    for sn in g.nodes("kind='section' AND id IN (%s)" % ",".join("?" * len(secs)), *secs) if secs else []:
        eps |= {e["dst"] for e in g.edges("rel='mentions_ep' AND file=? AND line>=? AND line<=?", sn["file"], sn["line"], sn["end_line"])}
    eps = sorted(eps)
    return {"req": t, "text": req[0].get("text") if req else None, "moscow": req[0].get("moscow") if req else None,
            "defined_at": f"{req[0]['file']}:{req[0]['line']}" if req else None, "phases": phases,
            "workflows": [e["src"] for e in g.edges("rel='exercises' AND dst=?", rid)],
            "spec_sections": section_rows(g, secs), "tc": tc_rows,
            "endpoints": [{"endpoint": e[3:], "handlers": [h.get("handler") for h in handlers_for(g, e)]} for e in eps]}


def cmd_orphans(g, a):
    phase = int(a.phase) if a.phase is not None else None
    ph = " AND phase=?" if phase is not None else ""
    pa = [phase] if phase is not None else []
    declared = sorted({r[0] for r in g.q("SELECT DISTINCT id FROM nodes WHERE kind='endpoint'" + ph, *pa)})
    no_handler = [e[3:] for e in declared if not handlers_for(g, e)]
    routes = sorted({(e["dst"], e["file"], e["line"]) for e in g.edges("rel='route'")})
    all_declared = {r[0] for r in g.q("SELECT DISTINCT id FROM nodes WHERE kind='endpoint'")}
    def declared_match(ep):
        if ep in all_declared:
            return True
        meth, path = ep[3:].split(" ", 1)
        return any(d[3:].split(" ", 1)[0] in (meth, "ANY") and (path.endswith(d[3:].split(" ", 1)[1]) or d[3:].split(" ", 1)[1].endswith(path))
                   for d in all_declared) if meth != "ANY" else any(d.endswith(path) for d in all_declared)
    no_contract = [f"{e[3:]} @{f}:{l}" for e, f, l in routes if not declared_match(e)] if all_declared else []
    reqs = g.nodes("kind='req' ORDER BY name")
    req_ids = sorted({r["name"] for r in reqs})
    covered = {e["dst"][4:] for e in g.edges("rel IN ('covers','mentions_req')") if e["file"].startswith("docs/design/phases/")}
    tc_reqs = {x for r in g.nodes("kind='tc'") for x in (r.get("reqs") or [])}
    assigned = {e["src"][4:] for e in g.edges("rel='assigned_to'")}
    fr_no_spec = [r for r in req_ids if r not in covered and r.startswith("FR")]
    in_phase = {e["src"][4:] for e in g.edges("rel='assigned_to' AND dst=?", f"phase:{phase}")} if phase is not None else assigned
    fr_no_tc = [r for r in sorted(in_phase) if r.startswith("FR") and r not in tc_reqs]
    defined = {r[0] for r in g.q("SELECT DISTINCT name FROM nodes WHERE kind='tc'")}
    unknown = sorted({(i, t["file"]) for t in g.nodes("kind='test'") for i in (t.get("ids") or []) if i not in defined})
    # IDs a phase's specs mention (EARS, prose) that no phase inventories: a test case with no row/priority
    unlisted = []
    for e in g.edges("rel='mentions_tc'" + (" AND file LIKE ?" if phase is not None else ""), *([f"docs/design/phases/{phase}/%"] if phase is not None else [])):
        tid = e["dst"][5:]
        if tid not in defined and not e.get("deferred"):
            unlisted.append(f"{tid} @{e['file']}:{e['line']}")
    screens = g.nodes("kind='screen'" + ph, *pa)
    pages = g.nodes("kind='page'")
    baselined = {norm_path(p["route"]) for p in pages if p.get("route")}
    routes_ui = {e["src"][6:] for e in g.edges("rel='renders'")}
    scr_no_baseline = [f"{s['name']} ({s.get('route')})" for s in screens if pages and s.get("route") and norm_path(s["route"]) not in baselined]
    scr_no_route = [f"{s['name']} ({s.get('route') or 'no route in spec'})" for s in screens
                    if routes_ui and (not s.get("route") or norm_path(s["route"]) not in routes_ui)]
    return {"phase": phase, "endpoints_without_handler": no_handler, "handlers_without_contract": no_contract,
            "frs_without_spec": fr_no_spec, "frs_in_scope_without_tc": fr_no_tc,
            "tests_naming_undefined_tc": [f"{i} @{f}" for i, f in unknown],
            "tc_mentioned_never_listed": sorted(set(unlisted)),
            "screens_without_stitch_baseline": scr_no_baseline, "screens_without_code_route": scr_no_route,
            "note": "rung-1 regex extraction: confirm a code-side orphan by reading the file before acting."}


def cmd_unlocked(g, a):
    phase = int(a.phase)
    wfs = g.nodes("kind='workflow' AND phase<=? ORDER BY phase, line", phase)
    e2e = [r for r in g.nodes("kind='tc' AND phase=? ORDER BY name", phase) if r.get("tier") == "e2e" or r.get("category") == "E2E"]
    specs = sorted({t["file"] for t in g.nodes("kind='test'") if re.search(r"(^|/)(e2e|playwright|cypress|\.maestro)(/|$)|\.e2e\.|\.spec\.[jt]sx?$", t["file"])
                    and not t["file"].startswith("tests/acceptance/")})
    return {"phase": phase,
            "this_phase": [{"id": w["name"], "text": w.get("text"), "at": f"{w['file']}:{w['line']}",
                            "frs": [e["dst"][4:] for e in g.edges("src=? AND rel='exercises'", w["id"])]} for w in wfs if w["phase"] == phase],
            "regression": [{"id": w["name"], "phase": w["phase"], "text": w.get("text")} for w in wfs if w["phase"] != phase],
            "e2e_tc_rows": [{"tc": r["name"], "priority": r.get("priority"), "spec": f"{r['file']}:{r['line']}", "desc": r.get("desc", "")[:80]} for r in e2e],
            "committed_e2e_spec_files": specs,
            "manifest_field": [w["name"] for w in wfs if w["phase"] == phase],
            "note": "Scope = this_phase workflows + e2e_tc_rows; regression = earlier phases' workflows and committed e2e specs. Never invent scenarios."}


def cmd_gate(g, a):
    phase = int(a.phase)
    results = a.results if a.results else discover_results(g, phase)
    inv = tc_inventory(g, phase, results=results, diff_base=a.diff_base, gate_mode=True)
    out = {"phase": phase, "tc": inv}
    blk = ["TC: " + b for b in blocking_lines(inv)]
    if not a.tc_only:
        rs = roster_summary(g, phase)
        ev = evidence_summary(g, phase)
        out.update({"roster": rs, "evidence": ev})
        if not rs["roster_present"]:
            blk.append(f"ROSTER: agent_state/phases/{phase}/roster.json missing")
        blk += [f"ROSTER: {x} never completed" for x in rs["missing"]]
        blk += [f"ROSTER: {x} failed with no later completion" for x in rs["dangling_failed"]]
        for s in ev["sidecars"]:
            if s["verdict"] != "PASS" or (s.get("failed") or 0) > 0 or (s.get("flaky") or 0) > 0:
                blk.append(f"EVIDENCE: {s['file']} verdict {s['verdict']} failed={s.get('failed')} flaky={s.get('flaky')}")
            if s["stale"]:
                blk.append(f"EVIDENCE: {s['file']} is STALE (code_sha is not the current code commit)")
        for r in ev["reconcilers"]:
            if r["blocking"] is None:
                blk.append(f"RECONCILE: {r['file']} has no 'BLOCKING:N WARNING:N INFO:N' line")
            elif r["blocking"] > 0:
                blk.append(f"RECONCILE: {r['file']} BLOCKING:{r['blocking']}")
    out["blocking"] = blk
    out["verdict"] = "PASS" if not blk else "FAIL"
    dest = a.out or os.path.join(g.dir, f"tc-gate-phase-{phase}.json")
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    with open(dest, "w") as f:
        json.dump(inv if a.tc_only else out, f, indent=1)
    summ = {"phase": phase, "verdict": out["verdict"], "tc": {"verdict": inv["verdict"], "covered": f"{inv['passed']}/{inv['total']}",
            "mode": inv["mode"], "missing": len(inv["missing"]), "failing": len(inv["failing"]),
            "range_expanded": len(inv["graph"]["range_expanded_ids"])}, "blocking": blk, "detail": dest}
    with open(os.path.join(g.dir, f"summary-phase-{phase}.json"), "w") as f:
        json.dump(summ, f, indent=1)
    out["detail"] = os.path.relpath(dest, g.root) if dest.startswith(g.root) else dest
    return out


def cmd_repomap(g, a):
    files = sorted(r[0] for r in g.q("SELECT path FROM files WHERE kind='code'"))
    fset = set(files)
    adj = {f: set() for f in files}
    simple_def = {}
    for s in g.nodes("kind='symbol'"):
        simple_def.setdefault(s.get("simple") or s["name"], set()).add(s["file"])
    for e in g.edges("rel='calls'"):
        src_f = e["file"]
        if src_f not in adj:
            continue
        for b in simple_def.get(e["dst"][5:], ()):
            if b != src_f and b in adj and len(simple_def[e["dst"][5:]]) <= 3:
                adj[src_f].add(b)
    for f in files:
        for imp in importers_of(g, f):
            if imp in fset and imp != f:
                adj[imp].add(f)
    focus = {x.strip() for x in (a.focus or "").split(",") if x.strip()}
    pers = {f: (50.0 if f in focus or any(f.startswith(x.rstrip("/") + "/") for x in focus) else 1.0) for f in files}
    tot = sum(pers.values()) or 1.0
    pers = {f: v / tot for f, v in pers.items()}
    pr = dict(pers)
    for _ in range(40):
        nxt = {f: 0.15 * pers[f] for f in files}
        dangling = sum(pr[f] for f in files if not adj[f])
        for f in files:
            outs = adj[f]
            for o_ in outs:
                nxt[o_] += 0.85 * pr[f] / len(outs)
        for f in files:
            nxt[f] += 0.85 * dangling * pers[f]
        pr = nxt
    ranked = sorted(pr.items(), key=lambda x: (-x[1], x[0]))
    rows = []
    for f, s in ranked:
        syms = [x["name"] for x in g.nodes("kind='symbol' AND file=? ORDER BY line", f)]
        eps = [e["dst"][3:] for e in g.edges("rel='route' AND file=?", f)]
        rows.append({"file": f, "rank": round(s * 1000, 3), "symbols": syms[:6] + ([f"+{len(syms) - 6}"] if len(syms) > 6 else []),
                     **({"routes": eps[:4]} if eps else {})})
    return {"files": len(files), "focus": sorted(focus), "ranked": rows}


def cmd_stats(g, a):
    return {"root": g.root, "graph": g.path, "head": g.meta("head"), "built_at": g.meta("built_at"),
            "files": dict(g.q("SELECT kind, count(*) FROM files GROUP BY kind ORDER BY kind")),
            "nodes": dict(g.q("SELECT kind, count(*) FROM nodes GROUP BY kind ORDER BY kind")),
            "edges": dict(g.q("SELECT rel, count(*) FROM edges GROUP BY rel ORDER BY rel")),
            "phases": g.phases()}


# ═══════════════════════════════════════════════════════════════════════════════════════════════
# Budgeted output
# ═══════════════════════════════════════════════════════════════════════════════════════════════
def cap_lists(obj, limit, top=True):
    """--limit rows per list; a role's reading list (PROTECTED_KEYS) is never cut by --limit."""
    if isinstance(obj, dict):
        return {k: (v if top and k in PROTECTED_KEYS else cap_lists(v, limit, False)) for k, v in obj.items()}
    if isinstance(obj, list):
        if limit and len(obj) > limit:
            return [cap_lists(x, limit, False) for x in obj[:limit]] + [f"… +{len(obj) - limit} more (raise --limit)"]
        return [cap_lists(x, limit, False) for x in obj]
    return obj


def fit(obj, max_chars, fmt):
    """Halve the longest list until the rendering fits; deterministic, keeps the head of each list. Lists under a
    top-level PROTECTED_KEYS key (a role's reading list) are cut only when nothing else is left to cut."""
    s = fmt(obj)
    guard = 0
    protect = True
    while len(s) > max_chars and guard < 200:
        guard += 1
        best, best_len, best_path = None, 0, None

        def walk(o, path):
            nonlocal best, best_len, best_path
            if protect and len(path) == 1 and path[0] in PROTECTED_KEYS:
                return
            if isinstance(o, list) and len(o) > 1:
                ln = len(json.dumps(o))
                if ln > best_len:
                    best, best_len, best_path = o, ln, path
            if isinstance(o, dict):
                for k, v in o.items():
                    walk(v, path + [k])
            elif isinstance(o, list):
                for i, v in enumerate(o):
                    walk(v, path + [i])
        walk(obj, [])
        if best is None and protect:
            protect = False
            continue
        if best is None:
            break
        real = [x for x in best if not (isinstance(x, str) and x.startswith("… +"))]
        extra = sum(int(re.match(r"… \+(\d+)", x).group(1)) for x in best if isinstance(x, str) and re.match(r"… \+(\d+)", x))
        keep = max(1, min(len(real) - 1, int(len(real) * 0.8)))
        cut = len(real) - keep + extra
        best[:] = real[:keep] + [f"… +{cut} more (output capped at --max-tokens; narrow the query or raise it)"]
        s = fmt(obj)
    if len(s) > max_chars:
        s = s[:max_chars] + "\n… (truncated)"
    return s


def render(obj, ind=0):
    """Compact, line-oriented rendering: scalars and short values inline, one compact JSON per list item."""
    pad = "  " * ind
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            js = json.dumps(v, separators=(",", ":"), ensure_ascii=False)
            if not isinstance(v, (dict, list)) or len(js) <= 110 or not v or \
                    (isinstance(v, list) and all(isinstance(x, (str, int, float)) and len(str(x)) <= 40 for x in v)):
                out.append(f"{pad}{k}: {js}")
            else:
                out.append(f"{pad}{k}:")
                out.append(render(v, ind + 1))
    elif isinstance(obj, list):
        for v in obj:
            out.append(f"{pad}- " + (v if isinstance(v, str) else json.dumps(v, separators=(",", ":"), ensure_ascii=False)))
    else:
        out.append(pad + json.dumps(obj, ensure_ascii=False))
    return "\n".join(out)


def emit(obj, a):
    if not a.full:
        obj = cap_lists(obj, a.limit)
    fmt = (lambda o: json.dumps(o, separators=(",", ":"), ensure_ascii=False)) if a.json else render
    if a.full:
        print(fmt(obj))
    else:
        print(fit(obj, a.max_tokens * 4, fmt))


def main(argv=None):
    def common(p, top):
        d = (lambda v: v) if top else (lambda v: argparse.SUPPRESS)      # options work before OR after the command
        p.add_argument("--root", default=d(os.environ.get("CLAUDE_PROJECT_DIR") or "."))
        p.add_argument("--graph-dir", default=d(None), help="where graph.sqlite/graph.jsonl live (default <root>/agent_state/graph)")
        p.add_argument("--json", action="store_true", default=d(False), help="compact JSON instead of the line format")
        p.add_argument("--max-tokens", type=int, default=d(None), help="output budget in tokens (~4 chars each; default 2000, context 5000)")
        p.add_argument("--limit", type=int, default=d(60), help="max rows per list (default 60)")
        p.add_argument("--full", action="store_true", default=d(False), help="no caps")
        p.add_argument("--no-refresh", action="store_true", default=d(False), help="skip the incremental refresh before a query")

    ap = argparse.ArgumentParser(prog="sdlc-graph.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    common(ap, True)
    sp = ap.add_subparsers(dest="cmd", required=True)

    def sub(name):
        p = sp.add_parser(name)
        common(p, False)
        return p
    b = sub("build"); b.add_argument("--incremental", action="store_true")
    sub("stats")
    t = sub("tc"); t.add_argument("--phase", required=True); t.add_argument("--tier"); t.add_argument("--priority")
    t.add_argument("--status", choices=["todo", "done", "missing", "failing", "all"]); t.add_argument("--results", nargs="*")
    t.add_argument("--source", action="store_true", help="source mode: ignore runner sidecars (a non-skipped test NAMED with the ID)")
    t.add_argument("--diff-base", help="also run the test-weakening check since SHA")
    t.add_argument("--spec-only", action="store_true", help="write {id: priority} (incl. range-defined IDs) to --out")
    t.add_argument("--out", help="write the full inventory JSON (tc-inventory.py's shape) here; exit 1 unless PASS")
    c = sub("context"); c.add_argument("--agent", required=True); c.add_argument("--phase", required=True)
    d = sub("diff-context"); d.add_argument("--base"); d.add_argument("--phase")
    i = sub("impact"); i.add_argument("target")
    cs = sub("consumers"); cs.add_argument("target", nargs="?"); cs.add_argument("--changed-since")
    tr = sub("trace"); tr.add_argument("id")
    o = sub("orphans"); o.add_argument("--phase")
    u = sub("unlocked"); u.add_argument("--phase", required=True)
    gt = sub("gate"); gt.add_argument("--phase", required=True); gt.add_argument("--summary", action="store_true")
    gt.add_argument("--tc-only", action="store_true"); gt.add_argument("--results", nargs="*"); gt.add_argument("--diff-base")
    gt.add_argument("--out")
    r = sub("repomap"); r.add_argument("--focus")
    a = ap.parse_args(argv)
    if a.max_tokens is None:
        a.max_tokens = {"context": 5000, "diff-context": 4000}.get(a.cmd, 2000)
    if not os.path.isdir(a.root):
        print(f"sdlc-graph: no such root {a.root}", file=sys.stderr)
        return 3
    try:
        g = Graph(a.root, a.graph_dir)
        if a.cmd == "build":
            st = g.build(incremental=a.incremental)
            print(json.dumps({**st, "graph": g.path, "nodes": g.q("SELECT count(*) FROM nodes")[0][0],
                              "edges": g.q("SELECT count(*) FROM edges")[0][0]}))
            return 0
        if a.cmd == "gate":
            g.build(incremental=False)          # the gate always reads a full rebuild
        elif not a.no_refresh:
            g.build(incremental=True)
    except (sqlite3.Error, OSError) as e:
        print(f"sdlc-graph: GRAPH UNAVAILABLE ({e}) — fall back to the pre-graph procedure and say so", file=sys.stderr)
        return 4
    fn = {"stats": cmd_stats, "tc": cmd_tc, "context": cmd_context, "diff-context": cmd_diff_context, "impact": cmd_impact,
          "consumers": cmd_consumers, "trace": cmd_trace, "orphans": cmd_orphans, "unlocked": cmd_unlocked,
          "gate": cmd_gate, "repomap": cmd_repomap}[a.cmd]
    if a.cmd == "tc" and a.diff_base is not None and not a.diff_base.strip():
        print("sdlc-graph: --diff-base is empty (agent_state/phases/N/base_sha missing?) — the weakening check needs "
              "the commit the phase started from; leave the flag out only for a source-mode inventory", file=sys.stderr)
        return 2
    res = fn(g, a)
    if isinstance(res, dict) and "_line" in res:
        print(res["_line"])
        return res.get("_rc", 0)
    if a.cmd == "gate":
        if a.summary or a.tc_only:
            tc = res["tc"]
            print(f"sdlc-graph gate phase {res['phase']}: {res['verdict']} — TC {tc['verdict']} {tc['passed']}/{tc['total']} "
                  f"HIGH+MEDIUM ({tc['mode']} mode, {len(tc['results'])} sidecar(s)); missing {len(tc['missing'])}, "
                  f"failing {len(tc['failing'])}, range-expanded IDs {len(tc['graph']['range_expanded_ids'])}; detail {res['detail']}")
            budget = a.max_tokens * 4
            used = 0
            for k, line in enumerate(res["blocking"]):
                s = "BLOCKING: " + line
                if not a.full and used + len(s) > budget:
                    print(f"BLOCKING: … +{len(res['blocking']) - k} more (see {res['detail']})")
                    break
                print(s)
                used += len(s)
            if not a.tc_only and "roster" in res:
                rs = res["roster"]
                print(f"roster: {len(rs['required']) - len(rs['missing'])}/{len(rs['required'])} required agents completed; "
                      f"evidence sidecars: {len(res['evidence']['sidecars'])}, stale "
                      f"{sum(1 for s in res['evidence']['sidecars'] if s['stale'])} (verify-gate.sh is authoritative for roster/evidence)")
        else:
            view = {k: v for k, v in res.items() if k != "tc"}
            view["tc"] = {k: res["tc"][k] for k in ("verdict", "passed", "total", "mode", "missing", "failing",
                                                   "duplicate_ids", "duplicate_in_phase", "graph")}
            emit(view, a)
        return 0 if res["verdict"] == "PASS" else 1
    emit(res, a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
