#!/usr/bin/env python3
"""board-review.py - the deterministic half of /board-review.

The 2026-09-30 board review couldn't be re-run: its checklists, prompts and formats weren't saved
(docs/DEBATE_AND_BOARD_REVIEW_2026-09-30.md, B1-B6). The checklists now live in
skills/review/board-review/; this script does everything that shouldn't be left to a model:

  targets <group|glob>      resolve a target group (or an agent-file glob) to agent files and the
                            context files the hats should read          -> JSON on stdout
  validate <file>...        check sdlc.board-findings/v1 or sdlc.board-verification/v1 files; every
                            citation must name a file that exists and a line inside it   (exit 2 on problems)
  select --dir RUN          build each verifier's input: all CRITICAL/HIGH plus a deterministic sample of
                            MEDIUM/LOW, severity REMOVED, order shuffled (blind verification, B4)
  merge --dir RUN           join hat findings and verdicts -> RUN/merged.json + RUN/scorecard.md. A score is
                            the agent's worst finding after verification (CRITICAL 1 .. none 5): verified
                            findings count at the verifier's severity, MEDIUM/LOW findings that weren't
                            sampled at the hat's (marked * in the scorecard); refuted ones don't count
                            (exit 2 if a CRITICAL/HIGH finding has no verdict)
  compare BEFORE AFTER      score movement between two merged.json files

Run directory layout (docs/board-review-<date>-<group>/):
  hats/<hat>.json, hats/<hat>.md               one per hat
  verify/plan.json                             which hats each verifier covers (written by select)
  verify/input-<V>.json, verify/<V>.json/.md   per verifier
  merged.json, scorecard.md                    written by merge
"""
import argparse
import glob
import hashlib
import json
import os
import random
import re
import sys

HATS = {"architect": "ARCH", "senior_dev": "DEV", "tester": "TEST", "sre": "SRE", "devops": "OPS",
        "security": "SEC", "ai_engineer": "AI"}
DEFAULT_HATS = list(HATS)
SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
SCORE = {"CRITICAL": 1, "HIGH": 2, "MEDIUM": 3, "LOW": 4}
VERDICTS = {"confirmed", "narrowed", "refuted", "unverifiable"}
FINDINGS_SCHEMA = "sdlc.board-findings/v1"
VERIFY_SCHEMA = "sdlc.board-verification/v1"
TYPE_RE = re.compile(r"^[abc](\+[abc])*$")

# Target groups. "agents" are agent names; "context" are files every hat reads alongside them.
GROUPS = {
    "coding-testing": {
        "agents": ["api_developer", "backend_developer", "database_agent", "migration_agent", "ui_developer",
                   "mobile_developer", "unit_test_agent", "integration_test_agent", "ui_test_agent",
                   "mobile_test_agent", "code_optimizer", "ui_code_optimizer", "solution_selector", "test_runner",
                   "e2e_orchestrator", "mobile_e2e_orchestrator", "acceptance_test_agent", "system_test_agent",
                   "manual_test_agent", "performance_agent", "spec_test_reconciler", "accessibility_auditor"],
        "context": [".claude/commands/develop-orchestrator.md", ".claude/hooks/verify-gate.sh",
                    ".claude/hooks/tc-inventory.py", ".claude/skills/testing/test-results-sidecar.md"],
    },
    "debate": {
        "agents": ["debate_moderator", "debate_researcher", "debate_advocate", "debate_arbitrator"],
        "context": [".claude/skills/core/debate-protocol.md", ".claude/hooks/debate-status.py",
                    ".claude/skills/core/develop-steps/step-0-orient.md", ".claude/commands/develop-orchestrator.md",
                    ".claude/skills/core/model-routing.md"],
    },
    "requirements": {
        "agents": ["brd_agent", "brd_analyzer", "brd_interviewer", "brd_writer", "product_manager",
                   "requirements_brd_reconciler", "impl_guidelines_agent"],
        "context": [".claude/commands/init.md", ".claude/hooks/acceptance-map.py"],
    },
    "reconcile": {
        "agents": ["brd_spec_reconciler", "spec_impl_reconciler", "spec_test_reconciler", "pipeline_completeness_agent",
                   "plan_goal_verifier", "spec_verifier", "acceptance_test_agent"],
        "context": [".claude/commands/recon.md", ".claude/commands/reconcile.md", ".claude/commands/converge.md",
                    ".claude/commands/accept.md", ".claude/hooks/acceptance-map.py", ".claude/hooks/tc-inventory.py"],
    },
    "planning": {
        "agents": ["project_planner", "spec_writer", "ux_designer", "wireframe_generator", "threat_model_agent",
                   "phase_assumptions_analyzer", "decision_researcher", "adr_agent"],
        "context": [".claude/commands/plan.md", ".claude/commands/discuss.md"],
    },
    "review": {
        "agents": ["code_reviewer_I", "code_reviewer_II", "security_reviewer", "code_quality_verifier",
                   "tenant_isolation_verifier", "dependency_scanner", "breaking_change_reviewer",
                   "migration_safety_reviewer", "design_quality_reviewer", "ui_standards_auditor",
                   "mobile_platform_auditor"],
        "context": [".claude/commands/develop-orchestrator.md", ".claude/hooks/verify-gate.sh"],
    },
    "ops": {
        "agents": ["deployment_agent", "ci_cd_agent", "observability_agent", "reliability_agent", "performance_agent"],
        "context": [".claude/commands/deploy.md", ".claude/commands/rollback.md"],
    },
}


def agent_file(root, name):
    home = os.path.expanduser("~/.claude/agents")
    for p in (f"{root}/.claude/agents/core/{name}.md", f"{root}/.claude/agents/generated/{name}.md",
              f"{root}/.claude/agents/{name}.md", f"{root}/.claude/agents/templates/{name}.tmpl",
              f"{home}/{name}.md", f"{home}/templates/{name}.tmpl"):
        if os.path.isfile(p):
            return os.path.relpath(p, root) if p.startswith(root) else p
    return None


def all_agents(root):
    names = set()
    for pat in (".claude/agents/core/*.md", ".claude/agents/generated/*.md", ".claude/agents/templates/*.tmpl"):
        for p in glob.glob(os.path.join(root, pat)):
            names.add(os.path.basename(p).rsplit(".", 1)[0])
    return sorted(names)


def resolve_targets(root, spec):
    if spec == "all":
        agents, context = all_agents(root), [".claude/commands/develop-orchestrator.md", ".claude/hooks/verify-gate.sh"]
    elif spec in GROUPS:
        agents, context = GROUPS[spec]["agents"], GROUPS[spec]["context"]
    else:  # a glob of agent files, or a comma list of names
        if any(c in spec for c in "*/?"):
            agents = sorted({os.path.basename(p).rsplit(".", 1)[0] for p in glob.glob(os.path.join(root, spec))})
        else:
            agents = [a.strip() for a in spec.split(",") if a.strip()]
        context = [".claude/commands/develop-orchestrator.md"]
    files, missing = {}, []
    for a in agents:
        f = agent_file(root, a)
        if f:
            files[a] = f
        else:
            missing.append(a)
    ctx = [c for c in context if os.path.isfile(os.path.join(root, c))]
    return {"group": spec, "agents": files, "missing": missing, "context": ctx,
            "context_missing": [c for c in context if c not in ctx]}


def load(path):
    with open(path) as fh:
        return json.load(fh)


def line_count(root, rel, cache={}):
    p = rel if os.path.isabs(rel) else os.path.join(root, rel)
    if p not in cache:
        if os.path.isfile(p):
            with open(p, errors="replace") as fh:
                cache[p] = sum(1 for _ in fh)
        else:
            cache[p] = None
    return cache[p]


def validate_findings(doc, root):
    probs = []
    hat = doc.get("hat")
    if hat not in HATS:
        return [f"hat '{hat}' is not one of {sorted(HATS)}"]
    prefix = HATS[hat]
    targets = set(doc.get("targets") or [])
    covered = {c.get("agent") for c in doc.get("coverage") or [] if isinstance(c, dict)}
    for t in sorted(targets - covered):
        probs.append(f"target '{t}' has no coverage entry (it would get no score)")
    seen = set()
    for i, f in enumerate(doc.get("findings") or []):
        fid = f.get("id") or f"#{i}"
        if not re.match(rf"^{prefix}-\d+$", fid):
            probs.append(f"{fid}: id must be {prefix}-<n>")
        if fid in seen:
            probs.append(f"{fid}: duplicate id")
        seen.add(fid)
        if f.get("severity") not in SEVERITIES:
            probs.append(f"{fid}: severity must be one of {SEVERITIES}")
        if not TYPE_RE.match(str(f.get("type") or "")):
            probs.append(f"{fid}: type must be a, b, c or a combination like a+c")
        if not f.get("agents"):
            probs.append(f"{fid}: names no agent")
        for k in ("evidence", "problem", "fix"):
            if not str(f.get(k) or "").strip():
                probs.append(f"{fid}: no {k}")
        rel, line = f.get("file"), f.get("line")
        if not rel:
            probs.append(f"{fid}: no file cited")
            continue
        n = line_count(root, rel)
        if n is None:
            probs.append(f"{fid}: cited file does not exist: {rel}")
        elif not isinstance(line, int) or line < 1 or line > n:
            probs.append(f"{fid}: cited line {line} is outside {rel} (1-{n})")
    return probs


def validate_verification(doc, expected_ids=None):
    probs = []
    ids = set()
    for v in doc.get("verdicts") or []:
        vid = v.get("id")
        ids.add(vid)
        if v.get("verdict") not in VERDICTS:
            probs.append(f"{vid}: verdict must be one of {sorted(VERDICTS)}")
        if v.get("verdict") in ("confirmed", "narrowed") and v.get("severity") not in SEVERITIES:
            probs.append(f"{vid}: a {v.get('verdict')} finding needs the verifier's own severity")
        if not str(v.get("reproduction") or "").strip():
            probs.append(f"{vid}: no reproduction (what was opened or run)")
        if not str(v.get("note") or "").strip():
            probs.append(f"{vid}: no note (say why: it's the only explanation of a severity the merge changes)")
    if expected_ids is not None:
        for m in sorted(set(expected_ids) - ids):
            probs.append(f"{m}: in the verifier's input but has no verdict")
    return probs


def validate_file(path, root):
    try:
        doc = load(path)
    except (OSError, ValueError) as e:
        return [f"not readable JSON: {e}"]
    if doc.get("schema") == FINDINGS_SCHEMA:
        return validate_findings(doc, root)
    if doc.get("schema") == VERIFY_SCHEMA:
        inp = os.path.join(os.path.dirname(path), f"input-{doc.get('verifier')}.json")
        expected = [f["id"] for f in load(inp)["findings"]] if os.path.isfile(inp) else None
        return validate_verification(doc, expected)
    return [f"schema is neither {FINDINGS_SCHEMA} nor {VERIFY_SCHEMA}"]


def hat_files(run):
    return sorted(glob.glob(os.path.join(run, "hats", "*.json")))


def verifier_plan(hats, per_verifier=2):
    # Pair hats so related lenses share a verifier (the 2026-09-30 pairing), two hats each.
    order = [h for h in ["security", "architect", "tester", "senior_dev", "sre", "devops", "ai_engineer"] if h in hats]
    order += [h for h in hats if h not in order]
    return {f"V{i // per_verifier + 1}": order[i:i + per_verifier] for i in range(0, len(order), per_verifier)}


def select(run, sample=0.25, min_sample=3):
    docs = {load(p)["hat"]: load(p) for p in hat_files(run)}
    plan = verifier_plan(sorted(docs))
    os.makedirs(os.path.join(run, "verify"), exist_ok=True)
    out = {}
    for v, hats in plan.items():
        picked = []
        for h in hats:
            fs = docs[h].get("findings") or []
            serious = [f for f in fs if f.get("severity") in ("CRITICAL", "HIGH")]
            rest = sorted((f for f in fs if f.get("severity") not in ("CRITICAL", "HIGH")), key=lambda f: f["id"])
            rng = random.Random(int(hashlib.sha256((os.path.basename(run.rstrip("/")) + h).encode()).hexdigest(), 16))
            k = min(len(rest), max(min_sample, int(round(len(rest) * sample))))
            picked += serious + rng.sample(rest, k)
        blind = [{k: f[k] for k in ("id", "type", "agents", "file", "line", "evidence", "problem", "fix") if k in f}
                 for f in picked]
        mine = {f["id"] for f in picked}
        # every other finding, briefly and without severity, so duplicates across verifiers can be marked
        others = [{"id": f["id"], "hat": h, "agents": f.get("agents"), "file": f.get("file"), "line": f.get("line"),
                   "problem": str(f.get("problem") or "")[:200]}
                  for h, d in sorted(docs.items()) for f in d.get("findings") or [] if f["id"] not in mine]
        random.Random(int(hashlib.sha256((os.path.basename(run.rstrip("/")) + v).encode()).hexdigest(), 16)).shuffle(blind)
        doc = {"schema": "sdlc.board-verify-input/v1", "verifier": v, "hats": hats, "findings": blind, "others": others,
               "note": "severity removed on purpose: rate each finding yourself from the evidence. 'others' are the "
                       "remaining findings (not yours to verify): use their ids in duplicate_of when one of yours is the same problem"}
        with open(os.path.join(run, "verify", f"input-{v}.json"), "w") as fh:
            json.dump(doc, fh, indent=2)
        out[v] = {"hats": hats, "count": len(blind)}
    with open(os.path.join(run, "verify", "plan.json"), "w") as fh:
        json.dump(out, fh, indent=2)
    return out


def merge(run):
    docs = [load(p) for p in hat_files(run)]
    verifs = [load(p) for p in sorted(glob.glob(os.path.join(run, "verify", "V*.json")))]
    verdict = {}
    stats = {}
    for vd in verifs:
        s = stats.setdefault(vd.get("verifier"), {"model": vd.get("model"), "confirmed": 0, "narrowed": 0, "refuted": 0,
                                                   "unverifiable": 0, "severity_up": 0, "severity_down": 0, "total": 0})
        for v in vd.get("verdicts") or []:
            verdict[v["id"]] = dict(v, verifier=vd.get("verifier"))
            s["total"] += 1
            s[v.get("verdict")] = s.get(v.get("verdict"), 0) + 1
    errors, final, refuted, changes = [], {}, [], []
    targets, coverage = set(), {}
    for d in docs:
        hat = d["hat"]
        targets |= set(d.get("targets") or [])
        coverage[hat] = {c.get("agent") for c in d.get("coverage") or [] if isinstance(c, dict)}
        for f in d.get("findings") or []:
            v = verdict.get(f["id"])
            item = dict(f, hat=hat, hat_severity=f.get("severity"), verified=False)
            if v is None:
                if f.get("severity") in ("CRITICAL", "HIGH"):
                    errors.append(f"{f['id']} ({f.get('severity')}) has no verifier verdict")
                final[f["id"]] = item
                continue
            item.update(verdict=v["verdict"], verifier=v.get("verifier"), reproduction=v.get("reproduction"),
                        verifier_note=v.get("note"), duplicate_of=v.get("duplicate_of"))
            if v["verdict"] == "refuted":
                refuted.append(item)
                continue
            if v["verdict"] in ("confirmed", "narrowed"):
                item["verified"] = True
                item["severity"] = v["severity"]
                if v["severity"] != f.get("severity"):
                    up = SEVERITIES.index(v["severity"]) < SEVERITIES.index(f.get("severity"))
                    changes.append({"id": f["id"], "hat": f.get("severity"), "verifier": v["severity"],
                                    "direction": "up" if up else "down", "note": v.get("note")})
                    st = stats[v.get("verifier")]
                    st["severity_up" if up else "severity_down"] += 1
            final[f["id"]] = item
    # fold duplicates into their target, following chains (A dup of B, B dup of C -> both into C). Roots are
    # computed on the original graph before anything is deleted; a cycle (two verifiers marking each other's
    # finding) is left unfolded rather than guessed.
    dup = {k: f["duplicate_of"] for k, f in final.items() if f.get("duplicate_of") in final and f.get("duplicate_of") != k}

    def root(fid):
        seen = set()
        while fid in dup and fid not in seen:
            seen.add(fid)
            fid = dup[fid]
        return fid
    roots = {fid: root(fid) for fid in dup}
    for fid, tgt_id in sorted(roots.items()):
        if tgt_id == fid or roots.get(tgt_id, tgt_id) != tgt_id or fid not in final or tgt_id not in final:
            continue
        src, tgt = final[fid], final[tgt_id]
        tgt["agents"] = sorted(set(tgt.get("agents") or []) | set(src.get("agents") or []))
        tgt.setdefault("duplicates", []).append(fid)
        if SEVERITIES.index(src["severity"]) < SEVERITIES.index(tgt["severity"]):
            tgt["severity"] = src["severity"]
        tgt["verified"] = bool(tgt.get("verified") or src.get("verified"))
        del final[fid]
    hats = sorted(coverage)
    scores, basis = {}, {}
    for a in sorted(targets):
        scores[a], basis[a] = {}, {}
        for h in hats:
            if a not in coverage[h]:
                scores[a][h] = basis[a][h] = None
                continue
            fs = [f for f in final.values() if f["hat"] == h and a in (f.get("agents") or [])]
            scores[a][h] = min((SCORE[f["severity"]] for f in fs), default=5)
            worst = [f for f in fs if SCORE[f["severity"]] == scores[a][h]]
            basis[a][h] = "none" if not fs else ("verified" if any(f.get("verified") for f in worst) else "unverified")
    avgs = {a: (round(sum(v for v in s.values() if v) / len([v for v in s.values() if v]), 2)
                if any(s.values()) else None) for a, s in scores.items()}
    warnings = []
    for v, s in stats.items():
        if s["total"] >= 10 and s["refuted"] == 0 and s["narrowed"] == 0 and s["severity_up"] + s["severity_down"] == 0:
            warnings.append(f"verifier {v} changed nothing across {s['total']} findings: check it tried to refute")
    counts = {sv: sum(1 for f in final.values() if f["severity"] == sv) for sv in SEVERITIES}
    out = {"schema": "sdlc.board-merged/v1", "run": os.path.basename(os.path.abspath(run)), "hats": hats,
           "targets": sorted(targets), "counts": counts, "findings": sorted(final.values(), key=lambda f: (SEVERITIES.index(f["severity"]), f["id"])),
           "refuted": refuted, "severity_changes": changes, "scores": scores, "score_basis": basis, "averages": avgs,
           "verifier_stats": stats, "warnings": warnings, "errors": errors}
    with open(os.path.join(run, "merged.json"), "w") as fh:
        json.dump(out, fh, indent=2)
    with open(os.path.join(run, "scorecard.md"), "w") as fh:
        fh.write(render_scorecard(out))
    return out


def render_scorecard(m):
    short = {"architect": "Arch", "senior_dev": "Dev", "tester": "Test", "sre": "SRE", "devops": "Ops",
             "security": "Sec", "ai_engineer": "AI"}
    L = [f"# Scorecard: {m['run']}", "",
         "Generated by `board-review.py merge`. Score = the agent's worst finding under that hat after verification "
         "(CRITICAL 1, HIGH 2, MEDIUM 3, LOW 4, none 5): verified findings at the verifier's severity, refuted ones dropped. "
         "`*` = that worst finding is a MEDIUM/LOW the verifiers didn't sample, so it's at the hat's severity. "
         "`-` = the hat didn't cover the agent.", "",
         f"Findings after verification: " + ", ".join(f"{k} {v}" for k, v in m["counts"].items())
         + f"; refuted {len(m['refuted'])}; severity changed {len(m['severity_changes'])}.", ""]
    L.append("| Agent | " + " | ".join(short.get(h) or h for h in m["hats"]) + " | Avg |")
    L.append("|---|" + "---|" * (len(m["hats"]) + 1))
    for a in sorted(m["scores"], key=lambda a: (m["averages"][a] is None, m["averages"][a] or 0, a)):
        b = m.get("score_basis", {}).get(a, {})
        cells = ["-" if m["scores"][a][h] is None else str(m["scores"][a][h]) + ("*" if b.get(h) == "unverified" else "")
                 for h in m["hats"]]
        L.append(f"| {a} | " + " | ".join(cells) + f" | {m['averages'][a] if m['averages'][a] is not None else '-'} |")
    L += ["", "## Verifiers", "", "| Verifier | Model | Total | Confirmed | Narrowed | Refuted | Unverifiable | Severity up | Severity down |",
          "|---|---|---|---|---|---|---|---|---|"]
    for v, s in sorted(m["verifier_stats"].items()):
        L.append(f"| {v} | {s.get('model')} | {s['total']} | {s['confirmed']} | {s['narrowed']} | {s['refuted']} | {s['unverifiable']} | {s['severity_up']} | {s['severity_down']} |")
    for w in m["warnings"]:
        L.append(f"\n> Warning: {w}")
    for e in m["errors"]:
        L.append(f"\n> Error: {e}")
    if m["severity_changes"]:
        L += ["", "## Severity changed by verification", "", "| Finding | Hat | Verifier | Why |", "|---|---|---|---|"]
        for c in m["severity_changes"]:
            L.append(f"| {c['id']} | {c['hat']} | {c['verifier']} | {(c.get('note') or '').replace('|', '/')} |")
    if m["refuted"]:
        L += ["", "## Refuted", "", "| Finding | Hat severity | Why |", "|---|---|---|"]
        for f in m["refuted"]:
            L.append(f"| {f['id']} | {f['hat_severity']} | {(f.get('verifier_note') or '').replace('|', '/')} |")
    return "\n".join(L) + "\n"


def compare(before, after):
    b, a = load(before), load(after)
    rows = []
    for agent in sorted(set(b["averages"]) | set(a["averages"])):
        x, y = b["averages"].get(agent), a["averages"].get(agent)
        d = round(y - x, 2) if x is not None and y is not None else None
        rows.append((agent, x, y, d))
    L = [f"Score movement: {b['run']} -> {a['run']}", "", "| Agent | Before | After | Change |", "|---|---|---|---|"]
    for agent, x, y, d in sorted(rows, key=lambda r: (r[3] is None, r[3] if r[3] is not None else 0)):
        L.append(f"| {agent} | {x if x is not None else '-'} | {y if y is not None else '-'} | {('+' if d and d > 0 else '') + str(d) if d is not None else '-'} |")
    L += ["", "Findings by severity: " + ", ".join(f"{s} {b['counts'].get(s, 0)} -> {a['counts'].get(s, 0)}" for s in SEVERITIES)]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description="deterministic half of /board-review")
    ap.add_argument("--root", default=os.environ.get("CLAUDE_PROJECT_DIR") or ".")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("targets"); t.add_argument("spec")
    v = sub.add_parser("validate"); v.add_argument("files", nargs="+")
    s = sub.add_parser("select"); s.add_argument("--dir", required=True); s.add_argument("--sample", type=float, default=0.25)
    m = sub.add_parser("merge"); m.add_argument("--dir", required=True)
    c = sub.add_parser("compare"); c.add_argument("before"); c.add_argument("after")
    a = ap.parse_args(argv)
    root = os.path.abspath(a.root)
    if a.cmd == "targets":
        r = resolve_targets(root, a.spec)
        print(json.dumps(r, indent=2))
        return 2 if not r["agents"] or r["missing"] else 0
    if a.cmd == "validate":
        bad = 0
        for f in a.files:
            probs = validate_file(f, root)
            print(f"{'OK  ' if not probs else 'FAIL'} {f}" + (f" ({len(probs)} problem(s))" if probs else ""))
            for p in probs:
                print(f"     - {p}")
            bad += bool(probs)
        return 2 if bad else 0
    if a.cmd == "select":
        print(json.dumps(select(a.dir, a.sample), indent=2))
        return 0
    if a.cmd == "merge":
        out = merge(a.dir)
        print(f"merged {sum(out['counts'].values())} finding(s) ({', '.join(f'{k} {v}' for k, v in out['counts'].items())}); "
              f"refuted {len(out['refuted'])}; wrote {a.dir}/merged.json and {a.dir}/scorecard.md")
        for w in out["warnings"]:
            print(f"WARNING: {w}")
        for e in out["errors"]:
            print(f"ERROR: {e}")
        return 2 if out["errors"] else 0
    if a.cmd == "compare":
        print(compare(a.before, a.after))
        return 0
    return 3


if __name__ == "__main__":
    sys.exit(main())
