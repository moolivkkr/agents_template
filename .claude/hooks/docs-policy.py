#!/usr/bin/env python3
"""docs-policy.py — which OPTIONAL documents the pipeline maintains. Lean by default.

  docs-policy.py is-on KEY            exit 0 = generate it, 1 = skip it, 2 = unknown key
  docs-policy.py show [--json]        every key: on/off, why, producer, output, and how stale what's on disk is
  docs-policy.py set KEY on|off       per-project override (agent_state/config/docs-policy.json)
  docs-policy.py profile lean|full    switch profile (overrides are kept; `--reset` clears them)

The pipeline only NEEDS the documents a gate or an agent reads: PROJECT_FACTS, DECISIONS, BRD,
IMPLEMENTATION_GUIDELINES, PHASE_PLAN + phase_context, the phase specs (TRDs with the TC inventory),
data-contracts and, for UI phases, the wireframes. Everything else is narrative that nobody re-reads
after it's written, so it drifts from the code. Those are the keys below. Off means "don't produce or
maintain it in the pipeline"; `/docs <key>` still generates a fresh, sha-stamped snapshot on demand.

Resolution order: env SDLC_DOCS (a profile name, for one run) > the project file's overrides > the project
file's profile > "lean". A missing or unreadable project file means lean.
"""
import json, os, subprocess, sys

POLICY_FILE = os.path.join("agent_state", "config", "docs-policy.json")
PROFILES = ("lean", "full")

# key: (on in lean, producer, output, why it is optional)
KEYS = {
    "architecture_diagrams": (False, "architecture_orchestrator (c4/sequence/deployment/eagle agents)", "docs/architecture/",
                              "narrative diagrams; no gate or agent reads them back"),
    "adr_files": (False, "adr_agent", "docs/adr/",
                  "off = decisions still go to docs/DECISIONS.md (the ledger every agent reads), just no ADR file"),
    "developer_docs": (False, "documentation_agent (/develop Step 6b)", "docs/api/ docs/developer-guide.md",
                       "hand-maintained prose that trails the code; OpenAPI/data-contracts stay in the specs"),
    "phase_sketches": (False, "/plan Step 4d", "docs/design/phases/*/SKETCH.md",
                       "guesses about future phases; /plan rewrites the phase when it gets there"),
    "traceability_matrix_file": (False, "brd_writer", "docs/traceability-matrix.md",
                                 "TBD columns nobody fills; the live trace is the acceptance map (agent_state/accept/acceptance_map.md)"),
    "user_stories": (False, "product_manager", "docs/user-stories/",
                     "acceptance criteria live on the FR in docs/BRD.md (EARS), which is what the tests are written from"),
    "phase_summary": (True, "/develop post-gate step 4a", "agent_state/phases/*/PHASE_SUMMARY.md",
                      "rebuilt from the phase's reports at each gate, so it can't drift"),
    "worklog": (True, "/worklog (post-gate step 4b)", "docs/WORKLOG.md",
                "rebuilt from manifests, decisions and logs at each gate, so it can't drift"),
    "release_notes": (True, "/accept Step 6", "docs/RELEASE_NOTES.md",
                      "generated from manifests at acceptance time"),
}

REQUIRED = [
    ("docs/PROJECT_FACTS.md", "Tier 0 facts, read first by every agent"),
    ("docs/DECISIONS.md", "Tier 0.5 decision ledger"),
    ("docs/BRD.md", "FR/NFR/OBJ IDs + EARS acceptance criteria — the source of the acceptance tests"),
    ("docs/IMPLEMENTATION_GUIDELINES.md", "stack + the Commands and versions table the gate runs"),
    ("docs/design/phases/*/PHASE_PLAN.md + phase_context.md", "phase scope; context for every agent"),
    ("docs/design/phases/*/specs/*.md", "TRDs + TC inventory the gate reads (incl. TC-ACC)"),
    ("docs/design/phases/*/specs/data-contracts.md", "typed response shapes"),
    ("docs/design/phases/*/specs/*.wireframe.*", "UI phases only: the design-gate contract"),
    ("tests/acceptance/", "committed acceptance specs, one test per TC-ACC"),
]


def load(root):
    try:
        with open(os.path.join(root, POLICY_FILE)) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def resolve(root, key):
    """(on, source) for one key."""
    data = load(root)
    env = os.environ.get("SDLC_DOCS", "").strip().lower()
    if env in PROFILES:
        return (True if env == "full" else KEYS[key][0]), f"env SDLC_DOCS={env}"
    ov = data.get("overrides") or {}
    if key in ov and isinstance(ov[key], bool):
        return ov[key], f"override in {POLICY_FILE}"
    prof = str(data.get("profile", "lean")).lower()
    if prof not in PROFILES:
        prof = "lean"
    return (True if prof == "full" else KEYS[key][0]), f"profile {prof}"


def save(root, data):
    path = os.path.join(root, POLICY_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")


def git(root, *args):
    try:
        return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def staleness(root, output):
    """'-' when nothing is on disk; else how many code commits landed after the doc was last touched."""
    paths = [p for p in output.split() if "*" not in p]
    globbed = [p for p in output.split() if "*" in p]
    present = [p for p in paths if os.path.exists(os.path.join(root, p))]
    if globbed:
        import glob
        present += [os.path.relpath(g, root) for p in globbed for g in glob.glob(os.path.join(root, p))]
    if not present:
        return "-"
    last = git(root, "log", "-1", "--format=%H", "--", *present)
    if not last:
        return "on disk, not committed"
    n = git(root, "rev-list", "--count", f"{last}..HEAD", "--", ".",
            ":(exclude)docs", ":(exclude)agent_state", ":(exclude).claude")
    return f"{n or '?'} code commit(s) since last update"


def main(argv):
    root = os.environ.get("DOCS_POLICY_ROOT", ".")
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "is-on":
        if len(rest) != 1 or rest[0] not in KEYS:
            print(f"docs-policy: unknown key {rest[:1]} — known: {', '.join(KEYS)}", file=sys.stderr)
            return 2
        on, src = resolve(root, rest[0])
        print(f"{rest[0]}: {'on' if on else 'off'} ({src})")
        return 0 if on else 1
    if cmd == "set":
        if len(rest) != 2 or rest[0] not in KEYS or rest[1] not in ("on", "off"):
            print("usage: docs-policy.py set KEY on|off", file=sys.stderr)
            return 2
        data = load(root)
        data.setdefault("profile", "lean")
        data.setdefault("overrides", {})[rest[0]] = rest[1] == "on"
        save(root, data)
        print(f"{rest[0]}: {rest[1]} (override written to {POLICY_FILE})")
        return 0
    if cmd == "profile":
        if not rest or rest[0] not in PROFILES:
            print(f"usage: docs-policy.py profile {'|'.join(PROFILES)} [--reset]", file=sys.stderr)
            return 2
        data = load(root)
        data["profile"] = rest[0]
        if "--reset" in rest:
            data["overrides"] = {}
        save(root, data)
        kept = data.get("overrides") or {}
        print(f"profile: {rest[0]}" + (f" (overrides kept: {', '.join(kept)})" if kept else ""))
        return 0
    if cmd == "show":
        rows = []
        for k, spec in KEYS.items():
            producer, output, why = spec[1:]
            on, src = resolve(root, k)
            rows.append({"key": k, "on": on, "source": src, "producer": producer, "output": output,
                         "why": why, "on_disk": staleness(root, output)})
        if "--json" in rest:
            print(json.dumps({"optional": rows, "required": [{"path": p, "why": w} for p, w in REQUIRED]}, indent=2))
            return 0
        print("Optional documents (off = not produced or maintained by the pipeline; `/docs <key>` makes a snapshot):")
        for r in rows:
            print(f"  {'ON ' if r['on'] else 'off'}  {r['key']:<25} {r['output']:<40} [{r['source']}]")
            print(f"       {r['why']}; on disk: {r['on_disk']}")
        print("Always maintained (gates and agents read these):")
        for p, w in REQUIRED:
            print(f"  req  {p:<55} {w}")
        return 0
    print(f"docs-policy: unknown command {cmd!r} (is-on | show | set | profile)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
