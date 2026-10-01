#!/usr/bin/env python3
"""debate-status.py - the one reader for agent_state/debates/.

The gate, /health, /pause, /worklog and the human checkpoint all read debates through this script
instead of globbing file names. Globbing is how pending debates went unnoticed: requests were written
as <step>-<topic>.json and the gate looked for *-request.json (docs/DEBATE_AND_BOARD_REVIEW_2026-09-30.md, D1).

Naming contract (skills/core/debate-protocol.md):
  agent_state/debates/<topic>.request.json   sdlc.debate-request/v1, written by the agent that needs the decision
  agent_state/debates/<topic>.verdict.json   sdlc.debate-verdict/v1, written by debate_arbitrator only
  agent_state/debates/<topic>.second-opinion.json  sdlc.debate-second-opinion/v1 (Fable arbitrator, close HIGH calls)
  agent_state/debates/<topic>.override.json  a user's override of a verdict
  agent_state/debates/unresolved.json        decisions auto-resolved with a default (circuit breaker, --auto)
<topic> is a slug ([a-z0-9][a-z0-9_-]*) and the join key; both files also carry it in "topic".

Files are classified by content, not name, so debates written under the older names
(<step>-<topic>.json, <topic>-verdict.json, *-request.json) are still found and matched.

Status per topic:
  pending       a request with no verdict, not auto-resolved or withdrawn
  resolved      a valid verdict
  auto_resolved recorded in unresolved.json with the default applied (always needs review)
  withdrawn     request carries status "withdrawn" and a withdrawn_reason
  overridden    a user override exists
  invalid       a request or verdict that breaks the contract (e.g. the verdict picks an option the
                request didn't offer)
A topic can also carry "review" reasons: things the human checkpoint should see (LOW confidence,
INCOMPLETE, a second opinion that disagrees, a security verdict that isn't the hardened default,
an assumption rather than a decision, a verdict not promoted to docs/DECISIONS.md).

Usage:
  debate-status.py [--root DIR] [--phase N] [--json] [--check]
    --phase N  only requests for phase N (requests without a phase field are included: an
               unattributed pending decision is still pending)
    --check    exit 2 if a blocking request is pending or invalid, a v1 verdict was never promoted
               to docs/DECISIONS.md, or a close HIGH-impact verdict has no second opinion
               (verify-gate.sh check (f))
Exit codes: 0 ok, 2 check failed, 3 usage error.
"""
import argparse
import glob
import json
import os
import re
import sys

REQ_SCHEMA = "sdlc.debate-request/v1"
VERDICT_SCHEMA = "sdlc.debate-verdict/v1"
SECOND_SCHEMA = "sdlc.debate-second-opinion/v1"
SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
CONFIDENCE = {"HIGH", "MEDIUM", "LOW"}
IMPACT = {"HIGH", "MEDIUM"}
DOMAINS = {"architecture", "security", "data_model", "feature", "testing", "operations"}


def load(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def stem_topic(path, *suffixes):
    name = os.path.basename(path)
    for s in suffixes:
        if name.endswith(s):
            return name[: -len(s)]
    return name[:-5] if name.endswith(".json") else name


def classify(path, doc):
    if not isinstance(doc, dict):
        return None
    if os.path.basename(path) == "unresolved.json" or ("decisions" in doc and "verdict" not in doc):
        return "unresolved"
    if "user_override" in doc:
        return "override"
    if doc.get("schema") == SECOND_SCHEMA or path.endswith(".second-opinion.json"):
        return "second"
    if doc.get("schema") == REQ_SCHEMA or doc.get("type") == "debate_request":
        return "request"
    if doc.get("schema") == VERDICT_SCHEMA or ("verdict" in doc and ("topic" in doc or path.endswith("verdict.json"))):
        return "verdict"
    return None


def request_problems(req):
    p = []
    v1 = req.get("schema") == REQ_SCHEMA
    opts = req.get("options") or []
    ids = [o.get("id") for o in opts if isinstance(o, dict)]
    if len(ids) < 2:
        p.append("fewer than 2 options")
    if len(set(ids)) != len(ids):
        p.append("duplicate option ids")
    if len(ids) > 4:
        p.append("more than 4 options (protocol limit)")
    if (req.get("impact") or "").upper() not in IMPACT:
        p.append("impact is not HIGH or MEDIUM")
    if v1:
        if not SLUG.match(req.get("topic") or ""):
            p.append("topic is not a slug ([a-z0-9][a-z0-9_-]*)")
        if (req.get("domain") or "") not in DOMAINS:
            p.append("domain is not one of " + "|".join(sorted(DOMAINS)))
        if not (req.get("decision") or "").strip():
            p.append("no decision statement")
    return p


def verdict_problems(ver, req):
    p = []
    v1 = ver.get("schema") == VERDICT_SCHEMA
    conf = (ver.get("confidence") or "").upper()
    if conf not in CONFIDENCE:
        p.append("confidence is not HIGH|MEDIUM|LOW")
    if not ver.get("verdict"):
        p.append("no verdict option")
    if req:
        ids = [o.get("id") for o in req.get("options") or [] if isinstance(o, dict)]
        if ver.get("verdict") and ids and ver.get("verdict") not in ids:
            p.append(f"verdict '{ver.get('verdict')}' is not one of the requested options {ids}")
    if v1:
        for k in ("topic", "verdict_label", "rationale", "decisive_factor", "status"):
            if not ver.get(k):
                p.append(f"missing {k}")
        if ver.get("status") and ver.get("status") not in ("RESOLVED", "INCOMPLETE"):
            p.append("status is not RESOLVED|INCOMPLETE")
        if ver.get("status") == "INCOMPLETE" and conf != "LOW":
            p.append("an INCOMPLETE verdict must have confidence LOW")
        domain = (ver.get("domain") or (req or {}).get("domain") or "").lower()
        if domain == "security" and not ver.get("hardened_default"):
            p.append("security verdict names no hardened_default")
        if not isinstance(ver.get("scores"), dict) or not ver.get("scores"):
            p.append("no per-option scores")
    return p


def second_opinion_required(ver, req):
    impact = (ver.get("impact") or (req or {}).get("impact") or "").upper()
    return ver.get("schema") == VERDICT_SCHEMA and impact == "HIGH" and (ver.get("confidence") or "").upper() != "HIGH"


def verdict_review(ver, req, decisions_text, rel, second=None):
    r = []
    if (ver.get("confidence") or "").upper() == "LOW":
        r.append("LOW confidence")
    if ver.get("status") == "INCOMPLETE":
        r.append("INCOMPLETE: " + (ver.get("reason") or "decided on incomplete evidence"))
    if second is not None and second.get("verdict") and second.get("verdict") != ver.get("verdict"):
        r.append(f"second opinion ({second.get('model') or '?'}) chose {second.get('verdict')}")
    elif second is None and second_opinion_required(ver, req):
        r.append("second opinion required (HIGH impact, confidence not HIGH) but missing")
    domain = (ver.get("domain") or (req or {}).get("domain") or "").lower()
    hardened = ver.get("hardened_default")
    if domain == "security" and hardened and ver.get("verdict") != hardened:
        r.append(f"security decision is not the hardened default ({hardened})")
    if ver.get("kind") == "assumption" or (req or {}).get("kind") == "assumption":
        r.append("assumption, not a decision: confirm with the product owner")
    if ver.get("none_ideal"):
        r.append("arbitrator found no option ideal")
    if ver.get("schema") != VERDICT_SCHEMA:
        r.append("legacy verdict format")
    if not promoted(ver, decisions_text, rel):
        r.append("not promoted to docs/DECISIONS.md")
    return r


def promoted(ver, decisions_text, rel):
    if decisions_text is None:
        return False
    did = ver.get("decision_id")
    if did and re.search(r"^###\s+" + re.escape(did) + r"\b", decisions_text, re.M):
        return True
    names = {rel, os.path.basename(rel)}
    return any(n and n in decisions_text for n in names)


def build(root, phase=None):
    ddir = os.path.join(root, "agent_state", "debates")
    requests, verdicts, overrides, auto, seconds = {}, {}, {}, {}, {}
    unrecognized = []
    for path in sorted(glob.glob(os.path.join(ddir, "*.json"))):
        doc = load(path)
        rel = os.path.relpath(path, root)
        if not isinstance(doc, dict):
            unrecognized.append(rel + (" (not valid JSON)" if doc is None else ""))
            continue
        kind = classify(path, doc)
        if kind == "request":
            t = doc.get("topic") or stem_topic(path, ".request.json", "-request.json")
            requests[t] = (doc, rel)
        elif kind == "verdict":
            t = doc.get("topic") or stem_topic(path, ".verdict.json", "-verdict.json")
            # the v1 file wins over a legacy duplicate for the same topic
            if t not in verdicts or doc.get("schema") == VERDICT_SCHEMA:
                verdicts[t] = (doc, rel)
        elif kind == "second":
            t = doc.get("topic") or stem_topic(path, ".second-opinion.json")
            seconds[t] = doc
        elif kind == "override":
            t = doc.get("topic") or stem_topic(path, ".override.json", "-override.json")
            overrides[t] = (doc, rel)
        elif kind == "unresolved":
            for d in doc.get("decisions") or []:
                if isinstance(d, dict) and d.get("topic") and d.get("auto_resolved_with"):
                    d = dict(d)
                    d.setdefault("phase", doc.get("phase"))
                    auto[d["topic"]] = (d, rel)
        elif not os.path.basename(path).startswith("overrides"):
            unrecognized.append(rel)

    # Legacy requests named <step>-<topic>.json with no topic field: match a verdict by suffix.
    for t in list(requests):
        if t not in verdicts:
            for vt in verdicts:
                if t.endswith("-" + vt) and vt not in requests:
                    requests[vt] = requests.pop(t)
                    break

    dec_path = os.path.join(root, "docs", "DECISIONS.md")
    decisions_text = open(dec_path).read() if os.path.isfile(dec_path) else None

    topics = []
    for t in sorted(set(requests) | set(verdicts) | set(auto)):
        req, req_rel = requests.get(t, (None, None))
        ver, ver_rel = verdicts.get(t, (None, None))
        a, _ = auto.get(t, (None, None))
        req_phase = (req or {}).get("phase", (a or {}).get("phase", (ver or {}).get("phase")))
        if phase is not None and req_phase is not None and str(req_phase) != str(phase):
            continue
        item = {
            "topic": t,
            "phase": req_phase,
            "impact": ((req or {}).get("impact") or (a or {}).get("impact") or "").upper() or None,
            "domain": (req or {}).get("domain") or (ver or {}).get("domain") or (a or {}).get("domain"),
            "blocking": (req or {}).get("blocking", True) is not False,
            "from_agent": (req or a or {}).get("from_agent"),
            "request": req_rel,
            "verdict_file": ver_rel,
            "problems": [],
            "review": [],
        }
        if req is not None:
            item["problems"] += ["request: " + x for x in request_problems(req)]
        if ver is not None:
            item["problems"] += ["verdict: " + x for x in verdict_problems(ver, req)]
            item["verdict"] = ver.get("verdict")
            item["verdict_label"] = ver.get("verdict_label")
            item["confidence"] = (ver.get("confidence") or "").upper() or None
            item["decision_id"] = ver.get("decision_id")
            item["review"] += verdict_review(ver, req, decisions_text, ver_rel, seconds.get(t))
            if t in seconds:
                item["second_opinion"] = {"model": seconds[t].get("model"), "verdict": seconds[t].get("verdict")}
        if req is not None and req.get("status") == "withdrawn":
            if len((req.get("withdrawn_reason") or "").strip()) >= 10:
                item["status"] = "withdrawn"
            else:
                item["status"] = "invalid"
                item["problems"].append("request: withdrawn without a withdrawn_reason")
        elif item["problems"]:
            item["status"] = "invalid"
        elif ver is not None:
            item["status"] = "resolved"
        elif a is not None:
            item["status"] = "auto_resolved"
            item["verdict"] = a.get("auto_resolved_with")
            item["confidence"] = (a.get("confidence") or "LOW").upper()
            item["review"].append("auto-resolved with a default: " + (a.get("reason") or "no reason recorded"))
        else:
            item["status"] = "pending"
        if t in overrides:
            o, o_rel = overrides[t]
            item["status"] = "overridden"
            item["override"] = {"file": o_rel, "user_override": o.get("user_override")}
            item["review"] = [r for r in item["review"] if r != "not promoted to docs/DECISIONS.md"]
        if req is not None and req_phase is None:
            item["review"].append("request has no phase field")
        topics.append(item)

    def blocking_reason(i):
        if not i["blocking"]:
            return None
        if i["status"] == "pending":
            return f"debate '{i['topic']}' is pending: {i['request']} has no verdict (run debate_moderator, or record it in unresolved.json under --auto)"
        if i["status"] == "invalid":
            return f"debate '{i['topic']}' breaks the debate contract: " + "; ".join(i["problems"])
        if i["status"] != "resolved" or not i.get("verdict_file"):
            return None
        ver = verdicts[i["topic"]][0]
        if ver.get("schema") != VERDICT_SCHEMA:
            return None
        if "not promoted to docs/DECISIONS.md" in i["review"]:
            return f"debate '{i['topic']}' verdict was never promoted to docs/DECISIONS.md (remember.sh decide)"
        if any(r.startswith("second opinion required") for r in i["review"]):
            return f"debate '{i['topic']}' is a close HIGH-impact call with no second opinion ({i['topic']}.second-opinion.json)"
        return None

    blocking = [b for b in (blocking_reason(i) for i in topics) if b]
    counts = {}
    for i in topics:
        counts[i["status"]] = counts.get(i["status"], 0) + 1
    return {
        "schema": "sdlc.debate-status/v1",
        "phase": phase,
        "topics": topics,
        "counts": counts,
        "blocking": blocking,
        "review": [{"topic": i["topic"], "reasons": i["review"]} for i in topics if i["review"]],
        "unrecognized": unrecognized,
    }


def render(rep):
    scope = f"phase {rep['phase']}" if rep["phase"] is not None else "all phases"
    out = [f"Debates - {scope} ({len(rep['topics'])} topic(s))"]
    for i in rep["topics"]:
        tag = {"pending": "PENDING", "resolved": "RESOLVED", "auto_resolved": "AUTO", "withdrawn": "WITHDRAWN",
               "overridden": "OVERRIDDEN", "invalid": "INVALID"}[i["status"]]
        if i["review"] and i["status"] == "resolved":
            tag = "REVIEW"
        bits = [f"  {tag:<10} {i['topic']:<28} {(i['impact'] or '-'):<6} {(i['domain'] or '-'):<12}"]
        if i.get("verdict"):
            bits.append(f"{i['verdict']} {i.get('verdict_label') or ''}".strip() + f"  {i.get('confidence') or ''}")
        if i.get("decision_id"):
            bits.append(i["decision_id"])
        if i["status"] == "pending":
            bits.append(("blocking" if i["blocking"] else "non-blocking") + f" - requested by {i['from_agent'] or '?'}")
        out.append("  ".join(bits).rstrip())
        for pr in i["problems"]:
            out.append(f"      ! {pr}")
        for rv in i["review"]:
            out.append(f"      ? {rv}")
    for u in rep["unrecognized"]:
        out.append(f"  (ignored: {u})")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--root", default=os.environ.get("CLAUDE_PROJECT_DIR") or ".")
    ap.add_argument("--phase")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    if not os.path.isdir(a.root):
        print(f"debate-status: no such directory {a.root}", file=sys.stderr)
        return 3
    rep = build(a.root, a.phase)
    if a.json:
        print(json.dumps(rep, indent=2))
    else:
        print(render(rep))
    if a.check and rep["blocking"]:
        if not a.json:
            for b in rep["blocking"]:
                print(f"BLOCKING: {b}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
