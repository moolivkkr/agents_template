#!/usr/bin/env python3
"""Write a complete, valid debate into a fixture project, for the gate tests.

  make_debate.py <root> <topic> [--phase N] [--domain D] [--impact HIGH|MEDIUM] [--verdict A]
                 [--no-promote] [--request-only] [--blocking false --default-taken A]

A complete debate is what debate-status.py --check accepts: a v1 request, a research brief per
option (and an argument per option for HIGH impact), a transcript, a v1 verdict whose request_sha,
per-criterion scores, gap and confidence agree, and a D-NNN in docs/DECISIONS.md linking to it.
The winning option scores 8 on every criterion and the others 5, so the call is clear-cut (HIGH
confidence, no second opinion needed).
"""
import argparse, importlib.util, json, os, sys

sys.dont_write_bytecode = True
HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".claude", "hooks", "debate-status.py")
_spec = importlib.util.spec_from_file_location("ds", HOOK)
assert _spec and _spec.loader
ds = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(ds)

ap = argparse.ArgumentParser()
ap.add_argument("root"); ap.add_argument("topic")
ap.add_argument("--phase", type=int, default=1); ap.add_argument("--domain", default="architecture")
ap.add_argument("--impact", default="HIGH"); ap.add_argument("--verdict", default="A")
ap.add_argument("--no-promote", action="store_true"); ap.add_argument("--request-only", action="store_true")
ap.add_argument("--blocking", default="true"); ap.add_argument("--default-taken")
ap.add_argument("--decision-id", default="D-001"); ap.add_argument("--not-applied", action="store_true")
a = ap.parse_args()

d = os.path.join(a.root, "agent_state", "debates"); os.makedirs(d, exist_ok=True)
put = lambda name, text: open(os.path.join(d, name), "w").write(text if isinstance(text, str) else json.dumps(text, indent=2))
ids = ["A", "B"]
req = {"schema": "sdlc.debate-request/v1", "type": "debate_request", "topic": a.topic, "phase": a.phase,
       "from_agent": "backend_developer", "from_step": "wave2", "decision": "pick one", "impact": a.impact,
       "domain": a.domain, "kind": "decision", "blocking": a.blocking != "false",
       "options": [{"id": i, "label": f"option {i}"} for i in ids]}
if a.default_taken:
    req["default_taken"] = a.default_taken
if not a.request_only and not a.not_applied:
    req["applied"] = a.verdict          # the parent relaunched the requester with the decision
put(f"{a.topic}.request.json", req)
if a.request_only:
    sys.exit(0)
rubric = ds.RUBRICS[a.domain]
scores = {i: {c: (8 if i == a.verdict else 5) for c in rubric} for i in ids}
for i in ids:
    put(f"{a.topic}.research-{i}.md", f"# Research: option {i}\n\n## Evidence by criterion\n| Criterion | For | Against | Source |\n"
        f"|---|---|---|---|\n| brd_alignment | meets the in-scope FRs directly | none found | https://example.org/{i}/docs |\n"
        f"| feasibility | the stack already does this | some migration work | docs/IMPLEMENTATION_GUIDELINES.md:42 |\n")
    if a.impact == "HIGH":
        put(f"{a.topic}.argument-{i}.md", f"# Argument for option {i}\n\n## Top strengths\n1. Meets the in-scope FRs ({a.topic}.research-{i}.md).\n"
            "## Why the alternatives fit worse\n- They need integrity checks in application code.\n"
            "## Weaknesses I acknowledge\n- Migration effort; mitigated by expand/contract.\n")
put(f"{a.topic}.transcript.md", "# Transcript\n" + "".join(f"- debate_researcher {i}: COMPLETE, {a.topic}.research-{i}.md\n" for i in ids))
did = a.decision_id
ver = {"schema": "sdlc.debate-verdict/v1", "topic": a.topic, "phase": a.phase, "impact": a.impact, "domain": a.domain,
       "status": "RESOLVED", "verdict": a.verdict, "verdict_label": f"option {a.verdict}", "confidence": "HIGH",
       "rubric": a.domain, "presentation_order": ["B", "A"], "scores": scores, "gap": 3.0, "decisive_factor": "brd_alignment",
       "claims_checked": [{"claim": "c", "source": "https://example.org", "result": "confirmed"}], "rationale": "r",
       "request_sha": ds.request_sha(req, a.root), "decision_id": did}
if a.domain == "security":
    ver["hardened_default"] = a.verdict
put(f"{a.topic}.verdict.json", ver)
if not a.no_promote:
    os.makedirs(os.path.join(a.root, "docs"), exist_ok=True)
    with open(os.path.join(a.root, "docs", "DECISIONS.md"), "a") as fh:
        fh.write(f"\n### {did} — {a.topic}\n- status: active\n- link: agent_state/debates/{a.topic}.verdict.json\n- decision: > option {a.verdict}\n")
