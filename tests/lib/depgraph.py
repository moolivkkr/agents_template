#!/usr/bin/env python3
"""depgraph.py — static dependency graph of the framework's agents, commands and skills.

Builds the graph from:
  * agent frontmatter: dependencies.upstream / downstream / runs_after, subagents, skill_packs
  * command bodies: every `subagent_type: X` / backticked agent name / skill path referenced
  * skill bodies:   every `~/.claude/skills/...md` path referenced

and reports the reference classes that break communication between them:

  DANGLING_AGENT    a dependency / spawn names an agent with no core/, templates/ or rule_board/ file
  DANGLING_SKILL    a skill_packs entry or body path names a skill file that does not exist
  ASYMMETRIC        A lists B downstream but B does not list A upstream (or vice versa)
  ORPHAN_AGENT      an agent no command, orchestrator or other agent ever invokes
  ORPHAN_SKILL      a skill file no agent, template, command or skill references
  NO_SKILLS         an agent with no skill_packs at all

Usage: python3 tests/lib/depgraph.py [--json] [--strict CLASS,CLASS]
Exit code is non-zero only when a class listed in --strict has findings.
"""
import fnmatch
import json
import os
import re
import sys

import yaml

# DEPGRAPH_ROOT points the analysis at another tree (the regression fixtures in dependency-graph.test.sh).
ROOT = os.path.abspath(os.environ.get("DEPGRAPH_ROOT") or os.path.join(os.path.dirname(__file__), "..", ".."))
C = os.path.join(ROOT, ".claude")
CORE = os.path.join(C, "agents", "core")
TMPL = os.path.join(C, "agents", "templates")
RULE = os.path.join(C, "agents", "rule_board")
CMDS = os.path.join(C, "commands")
SKILLS = os.path.join(C, "skills")

# Names used in dependency lists that are not agents: the parent session, humans, commands, tools.
NON_AGENT = {"parent", "user", "human", "orchestrator", "none", "all", "any", "test_runner_cli"}


def frontmatter(path):
    text = open(path, encoding="utf-8").read()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}, text
    raw = m.group(1)
    # Templates carry {{VARS}} that are not valid YAML inside flow sequences — quote-neutralise them.
    raw = re.sub(r"\{\{([A-Z0-9_+\-]+)\}\}", r"TMPL_\1", raw)
    try:
        return yaml.safe_load(raw) or {}, text
    except yaml.YAMLError:
        return {"__yaml_error__": True}, text


def as_list(v):
    if v is None:
        return []
    if isinstance(v, str):
        return [s.strip() for s in re.split(r"[,\s]+", v) if s.strip()]
    if isinstance(v, list):
        out = []
        for x in v:
            if isinstance(x, str):
                out.append(x.strip())
            elif isinstance(x, dict):
                out.extend(str(k) for k in x)
        return out
    return []


def norm_agent(n):
    n = re.sub(r"_TMPL_[A-Z_]+$", "", n)  # ui_test_agent_{{PROJECT_NAME}} -> ui_test_agent
    n = n.split("(")[0].strip().strip("`\"'")
    return n


# ---------------------------------------------------------------- inventory
agents = {}  # name -> {path, kind, fm, text}
for d, kind, ext in ((CORE, "core", ".md"), (TMPL, "template", ".tmpl"), (RULE, "rule_board", ".md")):
    for dp, _, fs in os.walk(d):
        for f in fs:
            if not f.endswith(ext) or f.isupper() or f.startswith(("README", "EDR_")) or f.upper() == f:
                continue
            p = os.path.join(dp, f)
            fm, text = frontmatter(p)
            name = f[: -len(ext)]
            agents[name] = {"path": os.path.relpath(p, ROOT), "kind": kind, "fm": fm, "text": text}

commands = {}
for f in sorted(os.listdir(CMDS)):
    if f.endswith(".md"):
        p = os.path.join(CMDS, f)
        commands[f[:-3]] = {"path": os.path.relpath(p, ROOT), "text": open(p, encoding="utf-8").read()}

skills = {}  # relative path under skills/ -> text
for dp, _, fs in os.walk(SKILLS):
    for f in fs:
        if f.endswith(".md"):
            p = os.path.join(dp, f)
            skills[os.path.relpath(p, SKILLS)] = open(p, encoding="utf-8").read()

SKILL_REF = re.compile(r"(?:~/\.claude/|\.claude/)skills/([A-Za-z0-9_./{}\-]+?\.md)")
AGENT_NAMES = set(agents)


def skill_refs(text):
    return {m.group(1) for m in SKILL_REF.finditer(text)}


def skill_exists(rel):
    if "{{" in rel or "TMPL_" in rel:
        return None  # resolved at runtime from agent_registry.json — cannot check statically
    return rel in skills


def agent_mentions(text):
    """Agent names a command/skill/agent body actually invokes or names in code/backticks."""
    found = set()
    for m in re.finditer(r"subagent_type[\"']?\s*[:=]\s*[\"']?([A-Za-z0-9_]+)", text):
        found.add(m.group(1))
    for m in re.finditer(r"`([a-z][A-Za-z0-9_]+)`", text):
        found.add(m.group(1))
    for m in re.finditer(r"\"([a-z][A-Za-z0-9_]+)\"", text):
        found.add(m.group(1))
    # Bare mentions in prose/tables/rosters: "spawn code_reviewer_I", "| test_runner |", "Agent(test_runner".
    for m in re.finditer(r"(?<![A-Za-z0-9_/.-])([a-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+)(?![A-Za-z0-9_.])", text):
        found.add(m.group(1))
    return {norm_agent(x) for x in found} & AGENT_NAMES


# ---------------------------------------------------------------- findings
# Wave each roster agent runs in under /develop-orchestrator (the canonical executor). A hard
# `upstream` edge between two of these must point to a STRICTLY earlier wave — same-wave agents run
# in parallel, so a same-wave "hard dependency" is a lie the orchestrator never honours.
WAVE = {
    "backend_audit_agent": 1, "ui_audit_agent": 1,
    # Wave 2A is sequenced (develop-orchestrator 2A.1–2A.5), so its steps get sub-wave numbers.
    "database_agent": 2.1, "migration_agent": 2.2, "backend_developer": 2.3, "api_developer": 2.4,
    "ui_developer": 2.5, "mobile_developer": 2.5,
    "solution_selector": 2.5,
    "unit_test_agent": 3, "integration_test_agent": 3, "ui_test_agent": 3, "mobile_test_agent": 3,
    "e2e_orchestrator": 3.2, "mobile_e2e_orchestrator": 3.2, "test_runner": 3.4,
    "code_reviewer_I": 4, "code_reviewer_II": 4, "security_reviewer": 4, "tenant_isolation_verifier": 4,
    "dependency_scanner": 4, "code_quality_verifier": 4, "accessibility_auditor": 4,
    "mobile_platform_auditor": 4, "ui_standards_auditor": 4, "migration_safety_reviewer": 4, "breaking_change_reviewer": 4,
    "spec_impl_reconciler": 4, "spec_test_reconciler": 4, "acceptance_test_agent": 4,
}

findings = {k: [] for k in ("REPORT_NAME", "IO_UNPRODUCED", "WAVE_ORDER", "DANGLING_AGENT", "DANGLING_SKILL", "ASYMMETRIC", "ORPHAN_AGENT", "ORPHAN_SKILL", "NO_SKILLS", "YAML_ERROR")}
edges = []  # (src, relation, dst)
referenced_skills = set()
invoked_agents = set()

for name, a in agents.items():
    fm = a["fm"]
    if fm.get("__yaml_error__"):
        findings["YAML_ERROR"].append(f"{a['path']}: frontmatter is not valid YAML")
        continue
    deps = fm.get("dependencies") or {}
    if not isinstance(deps, dict):
        deps = {}
    for rel in ("upstream", "downstream", "runs_after"):
        for dst in as_list(deps.get(rel)):
            dst = norm_agent(dst)
            if not dst or dst.lower() in NON_AGENT or dst.startswith("/"):
                continue
            edges.append((name, rel, dst))
            if dst not in AGENT_NAMES:
                findings["DANGLING_AGENT"].append(f"{a['path']}: dependencies.{rel} -> '{dst}' (no agent file)")
    for dst in as_list(fm.get("subagents")):
        dst = norm_agent(dst)
        edges.append((name, "spawns", dst))
        invoked_agents.add(dst)
        if dst not in AGENT_NAMES:
            findings["DANGLING_AGENT"].append(f"{a['path']}: subagents -> '{dst}' (no agent file)")
    packs = [str(p) for p in (fm.get("skill_packs") or [])]
    if not packs and a["kind"] != "rule_board":
        findings["NO_SKILLS"].append(a["path"])
    for p in packs:
        m = SKILL_REF.search(p.replace("TMPL_", "{{"))
        if not m:
            continue
        rel = m.group(1)
        referenced_skills.add(rel)
        if skill_exists(rel) is False:
            findings["DANGLING_SKILL"].append(f"{a['path']}: skill_packs -> skills/{rel}")
    for rel in skill_refs(a["text"]):
        referenced_skills.add(rel)
        if skill_exists(rel) is False:
            findings["DANGLING_SKILL"].append(f"{a['path']}: body -> skills/{rel}")
    body = re.sub(r"\A---\n.*?\n---\n", "", a["text"], flags=re.S)  # frontmatter deps are not invocations
    for other in agent_mentions(body) - {name}:
        invoked_agents.add(other)

for cname, c in commands.items():
    for ag in agent_mentions(c["text"]):
        invoked_agents.add(ag)
        edges.append((f"/{cname}", "invokes", ag))
    for rel in skill_refs(c["text"]):
        referenced_skills.add(rel)
        if skill_exists(rel) is False:
            findings["DANGLING_SKILL"].append(f"{c['path']}: -> skills/{rel}")

for sname, text in skills.items():
    # Sibling references inside the skills tree use the bare filename: `memory-as-tools.md`.
    for m in re.finditer(r"`([a-z0-9][a-z0-9\-]*\.md)`", text):
        sib = os.path.join(os.path.dirname(sname), m.group(1)) if os.path.dirname(sname) else m.group(1)
        if sib in skills and sib != sname:
            referenced_skills.add(sib)
    for rel in skill_refs(text):
        if rel != sname:
            referenced_skills.add(rel)
        if skill_exists(rel) is False:
            findings["DANGLING_SKILL"].append(f".claude/skills/{sname}: -> skills/{rel}")
    for ag in agent_mentions(text):
        invoked_agents.add(ag)

# Symmetry: A.downstream has B  <=>  B lists A in upstream or runs_after (downstream is DERIVED —
# .claude/agents/_sync-deps.py rewrites it; this catches a hand edit that skipped the sync).
up = {(s, d) for s, r, d in edges if r == "upstream"}
soft = {(s, d) for s, r, d in edges if r == "runs_after"}
down = {(s, d) for s, r, d in edges if r == "downstream"}
for s, d in sorted(down):
    if d in AGENT_NAMES and (d, s) not in up and (d, s) not in soft:
        findings["ASYMMETRIC"].append(f"{s} lists {d} downstream, but {d} lists {s} in neither upstream nor runs_after")
for s, d in sorted(up | soft):
    if d in AGENT_NAMES and (d, s) not in down:
        findings["ASYMMETRIC"].append(f"{s} depends on {d}, but {d} does not list {s} downstream")

for s_, d in sorted(up):
    if s_ in WAVE and d in WAVE and WAVE[d] >= WAVE[s_]:
        findings["WAVE_ORDER"].append(f"{s_} (wave {WAVE[s_]}) has hard upstream {d} (wave {WAVE[d]}) — not earlier; use runs_after or fix the orchestrator")

for name, a in sorted(agents.items()):
    if name not in invoked_agents and a["kind"] != "rule_board":
        findings["ORPHAN_AGENT"].append(f"{a['path']}: never invoked by a command, skill or other agent")

# Skills pulled in by name patterns at runtime (languages/frameworks/databases picked from the stack).
RUNTIME_DIRS = ("languages/", "frameworks/", "databases/", "backend/archetypes/", "ui/archetypes/")
FACTORY = agents.get("agent_factory", {}).get("text", "")
for rel in sorted(skills):
    stem = os.path.basename(rel)[:-3]
    # Tool packs (testing/playwright.md, testing/pytest.md) are chosen by agent_factory from the stack
    # block via {{E2E_TOOL}} / {{TEST_FRAMEWORK}}; they count as referenced when the factory names them.
    if rel.startswith("testing/") and re.search(rf"\b{re.escape(stem)}\b", FACTORY):
        continue
    if rel in referenced_skills or rel.startswith(RUNTIME_DIRS) or rel.endswith(("README.md", "INDEX.md")):
        continue
    findings["ORPHAN_SKILL"].append(f".claude/skills/{rel}")

# IO contract: an input an agent READS from agent-produced areas must be something some agent (or a
# command) declares it WRITES. Catches path drift like research/ vs reference/ between producer and consumer.
def _paths(node):
    out = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "path" and isinstance(v, str):
                out.append(v)
            elif k == "primary" and isinstance(v, str):
                out.append(v)
            else:
                out.extend(_paths(v))
    elif isinstance(node, list):
        for x in node:
            out.extend(_paths(x))
    return out


def _canon(pth):
    pth = re.sub(r"TMPL_[A-Z0-9_+\-]+|\{\{[^}]+\}\}|\$\{[^}]+\}|<[^>]+>", "*", pth.strip().strip("`\"'"))
    return re.sub(r"\*+", "*", pth)


def _seg_match(a, b):
    """Do two canonical paths name the same file? Segment-aware: the same number of '/' segments, and
    each pair of segments matches as a glob one way or the other. A '*' never crosses '/'. (fnmatch's
    '*' does, so 'agent_state/phases/*/manifest.json' used to "produce" every per-agent
    'agent_state/phases/*/<agent>/manifest.json' input — board review 2026-09-30, ARCH-08.)"""
    sa, sb = a.split("/"), b.split("/")
    if len(sa) != len(sb):
        return False
    return all(x == y or fnmatch.fnmatchcase(x, y) or fnmatch.fnmatchcase(y, x) for x, y in zip(sa, sb))


PRODUCED_AREAS = ("agent_state/phases/", "docs/product-workflows/", "agent_state/e2e/", "agent_state/mobile/")
produced = set()
for a in agents.values():
    produced.update(_canon(x) for x in _paths(a["fm"].get("output") or {}))
# Commands produce some files too (PARENT-written reports, e.g. collective_feedback.md). Normalise their
# ${VAR}/{{VAR}} paths the same way so a command-written file satisfies a reader.
cmd_paths = set()
for c in commands.values():
    for m in re.finditer(r"((?:agent_state|docs)/[A-Za-z0-9_./{}$*<>\-]+\.(?:md|json|jsonl|yaml))", c["text"]):
        cmd_paths.add(_canon(m.group(1).replace("${OUTPUT}", "docs/product-workflows")))
for name, a in sorted(agents.items()):
    for pth in _paths(a["fm"].get("input") or {}):
        c = _canon(pth)
        if not c.startswith(PRODUCED_AREAS):
            continue
        if c.endswith("/") or c.endswith("*"):
            continue  # a directory/glob input — any producer inside it satisfies it
        hit = any(_seg_match(c, pr) for pr in produced) or any(_seg_match(c, pr) for pr in cmd_paths)
        if not hit:
            findings["IO_UNPRODUCED"].append(f"{a['path']}: reads {pth} — no agent output or command produces it")

# Orchestrator ↔ agent report names: every "Agent: <name> → reports/<file>" line in the canonical
# executor must name a file that agent declares in its output (primary/artifacts/reports). A mismatch
# means the agent writes one path and the Wave verification looks for another → false BLOCK or a
# silently-missing report.
ORCH_TEXT = commands.get("develop-orchestrator", {}).get("text", "")
for m in re.finditer(r"(?:Agent: |[├└]─ )([a-zA-Z_I]+)\s*(?:→|->)\s*reports/([A-Za-z0-9_.\-]+\.md)", ORCH_TEXT):
    ag, rep = m.group(1), m.group(2)
    if ag not in agents:
        continue
    outs = json.dumps(agents[ag]["fm"].get("output") or {})  # bare-string artifacts count too
    if f"reports/{rep}" not in outs:
        findings["REPORT_NAME"].append(f"develop-orchestrator expects {ag} → reports/{rep}, but {agents[ag]['path']} declares output: {outs or '(none)'}")

# ---------------------------------------------------------------- output
if "--json" in sys.argv:
    print(json.dumps({"findings": findings, "edges": edges}, indent=1))
else:
    print(f"agents={len(agents)} commands={len(commands)} skills={len(skills)} edges={len(edges)}")
    for k, v in findings.items():
        print(f"\n## {k} ({len(v)})")
        for line in sorted(set(v)):
            print("  " + line)

strict = []
if "--strict" in sys.argv:
    strict = sys.argv[sys.argv.index("--strict") + 1].split(",")
sys.exit(1 if any(findings.get(k) for k in strict) else 0)
