#!/usr/bin/env python3
"""debate-status.py - the one reader of agent_state/debates/, and the check the gate runs on it.

The gate, /health, /pause, /worklog, /reset-phase, /autonomous and the human checkpoint all read
debates through this script instead of globbing file names. Globbing is how pending debates went
unnoticed (docs/DEBATE_AND_BOARD_REVIEW_2026-09-30.md, D1). It also re-derives what a verdict
claims instead of trusting it: the board review of 2026-09-30 (docs/board-review-2026-09-30-debate/)
showed a verdict could pick the lower-scoring option, label a 0.2 gap HIGH and skip its second
opinion, and the check still passed.

Naming contract (skills/core/debate-protocol.md):
  agent_state/debates/<topic>.request.json         sdlc.debate-request/v1, written by the agent that needs the decision
  agent_state/debates/<topic>.verdict.json         sdlc.debate-verdict/v1, written by debate_arbitrator only
  agent_state/debates/<topic>.second-opinion.json  sdlc.debate-second-opinion/v1 (the Fable arbitrator, close HIGH calls)
  agent_state/debates/<topic>.override.json        the user's choice, written by the parent session
  agent_state/debates/<topic>.research-<id>.md, .argument-<id>.md, .transcript.md, .verdict-detailed.md
  agent_state/debates/unresolved.json              defaults applied without a debate (circuit breaker, --auto)
<topic> is a slug ([a-z0-9][a-z0-9_-]*) and the join key. Files are classified by content, so debates
written under the older names (<step>-<topic>.json, <topic>-verdict.json) are still found.

Status per topic: pending, resolved, auto_resolved, withdrawn, overridden, invalid (breaks the
contract), stale (the verdict answers an earlier version of the request). "review" lists what the
human checkpoint should see.

--check (verify-gate.sh check (f)) exits 2 when anything in scope:
  - is pending, blocking or not (a non-blocking request only lets the requester continue on a default)
  - is invalid or stale, or is a debate file that can't be read or isn't in its format
  - is a v1 verdict whose D-NNN block in docs/DECISIONS.md doesn't link to it
  - needs a second opinion (HIGH impact, confidence below HIGH) and has none, or an invalid one
  - is a security decision a human must take: INCOMPLETE, or the second opinion disagrees (until
    <topic>.override.json records the human's choice)
  - is a non-blocking request whose verdict differs from the default the requester built
Messages for security-domain topics start "security debate", so the gate can count them as
security findings (a forced gate needs one acknowledgement each).

Usage:
  debate-status.py [--root DIR] [--phase N] [--json] [--check]
  debate-status.py --request-sha <topic>     the hash the arbitrator copies into the verdict's request_sha
Exit codes: 0 ok, 2 check failed, 3 usage error.
"""
import argparse
import glob
import hashlib
import json
import os
import re
import sys

REQ_SCHEMA = "sdlc.debate-request/v1"
VERDICT_SCHEMA = "sdlc.debate-verdict/v1"
SECOND_SCHEMA = "sdlc.debate-second-opinion/v1"
SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
CONFIDENCE = ["LOW", "MEDIUM", "HIGH"]          # ordered: a verdict may claim less confidence than its gap gives, never more
IMPACT = {"HIGH", "MEDIUM"}
# One rubric per domain; weights sum to 100. Mirrors debate-protocol.md § "Rubrics by domain"
# (tests/lib/debate_cases.py fails if the two drift).
RUBRICS = {
    "architecture": {"brd_alignment": 30, "feasibility": 25, "constraint_fit": 20, "scalability": 15, "ecosystem": 10},
    "security": {"security_posture": 35, "brd_alignment": 25, "feasibility": 20, "constraint_fit": 10, "operability": 10},
    "data_model": {"brd_alignment": 25, "data_integrity": 25, "access_fit": 20, "evolution_cost": 20, "operability": 10},
    "feature": {"brd_alignment": 30, "implementation_risk": 25, "maintainability": 20, "ecosystem": 15, "performance": 10},
    "testing": {"detection_power": 35, "determinism": 25, "run_cost": 20, "constraint_fit": 20},
    "operations": {"reliability": 30, "operability": 25, "run_cost": 20, "constraint_fit": 15, "ecosystem": 10},
}
DOMAINS = set(RUBRICS)
CLAIM_RESULTS = {"confirmed", "contradicted", "unverifiable"}
NAMED = (".request.json", ".verdict.json", ".second-opinion.json", ".override.json")


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


def same_phase(a, b):
    try:
        return int(str(a)) == int(str(b))
    except ValueError:
        return str(a) == str(b)


def band(gap):
    return "HIGH" if gap > 1.0 else ("MEDIUM" if gap >= 0.3 else "LOW")


def request_sha(req):
    keys = ("topic", "phase", "decision", "options", "impact", "domain", "kind")
    canon = json.dumps({k: req.get(k) for k in keys}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()[:16]


def option_ids(req):
    return [o["id"] for o in (req or {}).get("options") or [] if isinstance(o, dict) and isinstance(o.get("id"), str)]


def option_label(req, oid):
    for o in (req or {}).get("options") or []:
        if isinstance(o, dict) and o.get("id") == oid:
            return o.get("label")
    return None


def classify(path, doc):
    name = os.path.basename(path)
    schema = doc.get("schema")
    if name == "unresolved.json" or (not schema and doc.get("type") != "debate_request"
                                     and isinstance(doc.get("decisions"), list) and "verdict" not in doc):
        return "unresolved"
    if schema == SECOND_SCHEMA:
        return "second"
    if schema == REQ_SCHEMA:
        return "request"
    if schema == VERDICT_SCHEMA:
        return "verdict"
    if name.endswith(NAMED):          # named like a debate file but not in its format
        if name.endswith(".override.json") and "user_override" in doc:
            return "override"
        if name.endswith(".request.json") and doc.get("type") == "debate_request" and not schema:
            return "request"           # v1 name, type marker, no schema: accepted, flagged below
        if name.endswith(".verdict.json") and "verdict" in doc and not schema:
            return "verdict"           # v1 name, no schema: reported as "not sdlc.debate-verdict/v1"
        return "misformatted"
    if "user_override" in doc:
        return "override"
    if doc.get("type") == "debate_request":
        return "request"               # legacy <step>-<topic>.json
    if "verdict" in doc and ("topic" in doc or name.endswith("verdict.json")):
        return "verdict"               # legacy <topic>-verdict.json
    return None


def request_problems(req, rel):
    p = []
    v1 = req.get("schema") == REQ_SCHEMA or rel.endswith(".request.json")
    ids = option_ids(req)
    if len(ids) < 2:
        p.append("fewer than 2 options")
    if len(set(ids)) != len(ids):
        p.append("duplicate option ids")
    if len(ids) > 4:
        p.append("more than 4 options (protocol limit)")
    if (req.get("impact") or "").upper() not in IMPACT:
        p.append("impact is not HIGH or MEDIUM")
    if v1:
        if req.get("schema") != REQ_SCHEMA:
            p.append(f"request is not {REQ_SCHEMA}")
        if not SLUG.match(req.get("topic") or ""):
            p.append("topic is not a slug ([a-z0-9][a-z0-9_-]*)")
        if (req.get("domain") or "") not in DOMAINS:
            p.append("domain is not one of " + "|".join(sorted(DOMAINS)))
        if not (req.get("decision") or "").strip():
            p.append("no decision statement")
        if any(not option_label(req, i) for i in ids):
            p.append("every option needs a label")
        if req.get("blocking") is False and req.get("status") != "withdrawn" and req.get("default_taken") not in ids:
            p.append("a non-blocking request must name the option the agent built as default_taken")
    return p


def score_problems(scores, ids, rubric, label):
    p = []
    if not isinstance(scores, dict):
        return [f"{label}: no per-option scores"]
    for i in ids:
        s = scores.get(i)
        if not isinstance(s, dict):
            p.append(f"{label}: option {i} has no scores")
            continue
        missing = [c for c in rubric if not (isinstance(s.get(c), (int, float)) and 1 <= s[c] <= 10)]
        if missing:
            p.append(f"{label}: option {i} has no 1-10 score for {', '.join(missing)}")
    return p


def totals(scores, ids, rubric):
    out = {}
    for i in ids:
        s = scores.get(i) or {}
        if all(isinstance(s.get(c), (int, float)) for c in rubric):
            out[i] = round(sum(s[c] * w for c, w in rubric.items()) / 100.0, 2)
    return out


def verdict_problems(ver, req, rel, root):
    """Contract problems in a verdict. Returns (problems, derived) where derived holds the recomputed
    totals, gap and confidence band (None when the verdict isn't v1 or can't be scored)."""
    p = []
    v1 = ver.get("schema") == VERDICT_SCHEMA
    must_be_v1 = (req or {}).get("schema") == REQ_SCHEMA or rel.endswith(".verdict.json")
    conf = (ver.get("confidence") or "").upper()
    ids = option_ids(req)
    if conf not in CONFIDENCE:
        p.append("confidence is not HIGH|MEDIUM|LOW")
    if not ver.get("verdict"):
        p.append("no verdict option")
    if ids and ver.get("verdict") and ver.get("verdict") not in ids:
        p.append(f"verdict '{ver.get('verdict')}' is not one of the requested options {ids}")
    if must_be_v1 and not v1:
        p.append(f"verdict is not {VERDICT_SCHEMA} (every v2 check would be skipped)")
    if not v1:
        return p, None
    if req is None:
        p.append("no request file for this verdict (write <topic>.request.json first)")
    for k in ("topic", "verdict_label", "rationale", "decisive_factor", "status"):
        if not ver.get(k):
            p.append(f"missing {k}")
    if ver.get("status") not in ("RESOLVED", "INCOMPLETE"):
        p.append("status is not RESOLVED|INCOMPLETE")
    if ver.get("status") == "INCOMPLETE" and conf != "LOW":
        p.append("an INCOMPLETE verdict must have confidence LOW")
    if req is not None:
        if req.get("phase") is not None and not same_phase(ver.get("phase"), req.get("phase")):
            p.append(f"verdict is for phase {ver.get('phase')}, the request is phase {req.get('phase')}")
        lbl = option_label(req, ver.get("verdict"))
        if lbl and ver.get("verdict_label") and ver.get("verdict_label") != lbl:
            p.append(f"verdict_label '{ver.get('verdict_label')}' is not option {ver.get('verdict')}'s label '{lbl}'")
    domain = ((req or {}).get("domain") or ver.get("domain") or "architecture").lower()
    rubric = RUBRICS.get(domain)
    if ver.get("rubric") != domain:
        p.append(f"rubric is '{ver.get('rubric')}', the request's domain is '{domain}'")
    if ids and sorted(ver.get("presentation_order") or []) != sorted(ids):
        p.append("presentation_order is not a permutation of the option ids")
    claims = [c for c in ver.get("claims_checked") or [] if isinstance(c, dict)
              and str(c.get("source") or "").strip() and c.get("result") in CLAIM_RESULTS]
    if not claims:
        p.append("claims_checked has no entry with a source and a result (re-check the decisive claim at its source)")
    if domain == "security":
        hd = ver.get("hardened_default")
        if not hd and ver.get("status") != "INCOMPLETE":
            p.append("security verdict names no hardened_default (no hardened option means status INCOMPLETE)")
        elif hd and ids and hd not in ids:
            p.append(f"hardened_default '{hd}' is not one of the options")
    derived = None
    if rubric and ids:
        sp = score_problems(ver.get("scores"), ids, rubric, "scores")
        p += sp
        if not sp:
            t = totals(ver["scores"], ids, rubric)
            ranked = sorted(t.items(), key=lambda kv: -kv[1])
            gap = round(ranked[0][1] - ranked[1][1], 2) if len(ranked) > 1 else 10.0
            derived = {"totals": t, "gap": gap, "band": band(gap)}
            for i in ids:
                claimed = (ver["scores"].get(i) or {}).get("total")
                if isinstance(claimed, (int, float)) and abs(claimed - t[i]) > 0.05:
                    p.append(f"option {i}'s total is {claimed} but its scores and the {domain} weights give {t[i]}")
            if conf in CONFIDENCE and CONFIDENCE.index(conf) > CONFIDENCE.index(derived["band"]):
                p.append(f"confidence {conf} but the scores give a gap of {gap} ({derived['band']})")
            v = ver.get("verdict")
            if v in t and t[v] < ranked[0][1] - 0.005:
                hardened_ok = domain == "security" and v == ver.get("hardened_default") and derived["band"] != "HIGH"
                tie_ok = abs(t[v] - ranked[0][1]) < 0.05 and str(ver.get("tie_break") or "").strip()
                if not (hardened_ok or tie_ok):
                    p.append(f"verdict {v} scores {t[v]}, below {ranked[0][0]} at {ranked[0][1]}, with no hardened-default or tie_break reason")
            if domain == "security" and derived["band"] != "HIGH" and ver.get("status") == "RESOLVED" \
                    and ver.get("hardened_default") and v != ver.get("hardened_default") and not str(ver.get("must_override") or "").strip():
                p.append("a security call below HIGH confidence must be the hardened default, unless must_override names the MUST requirement that rules it out")
    # the debate behind the verdict (a verdict file alone is not a debate)
    if ver.get("status") == "RESOLVED" and ids:
        topic = ver.get("topic")
        ddir = os.path.join(root, "agent_state", "debates")
        need = [f"{topic}.research-{i}.md" for i in ids] + [f"{topic}.transcript.md"]
        if ((req or {}).get("impact") or ver.get("impact") or "").upper() == "HIGH":
            need += [f"{topic}.argument-{i}.md" for i in ids]
        missing = [n for n in need if not os.path.isfile(os.path.join(ddir, n)) or os.path.getsize(os.path.join(ddir, n)) == 0]
        if missing:
            p.append("no debate behind the verdict: missing " + ", ".join(missing))
    return p, derived


def second_problems(sec, ver, req, domain):
    p = []
    ids = option_ids(req)
    if sec.get("schema") != SECOND_SCHEMA:
        p.append(f"second opinion is not {SECOND_SCHEMA}")
    if not sec.get("verdict") or (ids and sec.get("verdict") not in ids):
        p.append("second opinion names no verdict among the options")
    if not str(sec.get("model") or "").strip():
        p.append("second opinion doesn't record the model it ran on")
    po, vo = sec.get("presentation_order") or [], (ver or {}).get("presentation_order") or []
    if vo and po != list(reversed(vo)):
        p.append("second opinion didn't read the options in the reverse presentation order")
    rubric = RUBRICS.get(domain)
    if rubric and ids:
        p += score_problems(sec.get("scores"), ids, rubric, "second opinion")
    return ["second opinion: " + x if not x.startswith("second opinion") else x for x in p]


def decision_blocks(text):
    blocks = {}
    for m in re.finditer(r"^###\s+(D-\d+)\b.*?(?=^###\s|\Z)", text or "", re.M | re.S):
        blocks[m.group(1)] = m.group(0)
    return blocks


def promoted(ver, blocks, rel):
    link = re.compile(r"^- link:\s*" + re.escape(rel) + r"\s*$", re.M)
    did = ver.get("decision_id")
    if did:
        return bool(blocks.get(did) and link.search(blocks[did]))
    return any(link.search(b) for b in blocks.values())


def build(root, phase=None):
    ddir = os.path.join(root, "agent_state", "debates")
    requests, verdicts, overrides, auto, seconds = {}, {}, {}, {}, {}
    unrecognized, unreadable = [], []
    for path in sorted(glob.glob(os.path.join(ddir, "*.json"))):
        rel = os.path.relpath(path, root)
        doc = load(path)
        if not isinstance(doc, dict):
            unreadable.append(f"{rel} is not a JSON object" if doc is not None else f"{rel} is not valid JSON")
            continue
        kind = classify(path, doc)
        if kind == "request":
            t = doc.get("topic") or stem_topic(path, ".request.json", "-request.json")
            requests[t] = (doc, rel)
        elif kind == "verdict":
            t = doc.get("topic") or stem_topic(path, ".verdict.json", "-verdict.json")
            if t not in verdicts or doc.get("schema") == VERDICT_SCHEMA:
                verdicts[t] = (doc, rel)
        elif kind == "second":
            seconds[doc.get("topic") or stem_topic(path, ".second-opinion.json")] = (doc, rel)
        elif kind == "override":
            overrides[doc.get("topic") or stem_topic(path, ".override.json", "-override.json")] = (doc, rel)
        elif kind == "unresolved":
            for d in doc.get("decisions") or []:
                if isinstance(d, dict) and d.get("topic") and d.get("auto_resolved_with"):
                    d = dict(d)
                    d.setdefault("phase", doc.get("phase"))
                    auto[d["topic"]] = (d, rel)
        elif kind == "misformatted":
            unreadable.append(f"{rel} is named like a debate file but isn't in its format (schema {doc.get('schema')!r})")
        else:
            unrecognized.append(rel)

    # True legacy requests (<step>-<topic>.json: no topic field, no schema) match a verdict by suffix.
    for t in list(requests):
        doc = requests[t][0]
        if t not in verdicts and not doc.get("topic") and not doc.get("schema"):
            for vt in verdicts:
                if t.endswith("-" + vt) and vt not in requests:
                    requests[vt] = requests.pop(t)
                    break

    dec_path = os.path.join(root, "docs", "DECISIONS.md")
    blocks = decision_blocks(open(dec_path).read()) if os.path.isfile(dec_path) else {}

    topics = []
    for t in sorted(set(requests) | set(verdicts) | set(auto)):
        req, req_rel = requests.get(t, (None, None))
        ver, ver_rel = verdicts.get(t, (None, None))
        a, _ = auto.get(t, (None, None))
        sec, sec_rel = seconds.get(t, (None, None))
        req_phase = (req or {}).get("phase", (a or {}).get("phase", (ver or {}).get("phase")))
        if phase is not None and req_phase is not None and not same_phase(req_phase, phase):
            continue
        domain = ((req or {}).get("domain") or (ver or {}).get("domain") or (a or {}).get("domain") or "").lower() or None
        impact = ((req or {}).get("impact") or (ver or {}).get("impact") or (a or {}).get("impact") or "").upper() or None
        ids = option_ids(req)
        files = sorted({os.path.relpath(p, root) for p in glob.glob(os.path.join(ddir, glob.escape(t) + ".*"))}
                       | {x for x in (req_rel, ver_rel, sec_rel, (overrides.get(t) or (None, None))[1]) if x})
        item = {"topic": t, "phase": req_phase, "impact": impact, "domain": domain,
                "blocking": (req or {}).get("blocking", True) is not False, "from_agent": (req or a or {}).get("from_agent"),
                "request": req_rel, "verdict_file": ver_rel, "files": files, "problems": [], "review": [], "gate": []}
        if req is not None:
            item["problems"] += ["request: " + x for x in request_problems(req, req_rel)]
        derived = None
        stale = req is not None and ver is not None and ver.get("schema") == VERDICT_SCHEMA \
            and ver.get("request_sha") != request_sha(req)
        if ver is not None:
            # a stale verdict answers another request: its content checks would only describe that mismatch
            vp, derived = ([], None) if stale else verdict_problems(ver, req, ver_rel, root)
            item["problems"] += ["verdict: " + x for x in vp]
            item.update(verdict=ver.get("verdict"), verdict_label=ver.get("verdict_label"),
                        confidence=(ver.get("confidence") or "").upper() or None, decision_id=ver.get("decision_id"))
            if derived:
                item["derived"] = derived
        ov = overrides.get(t)
        if ov is not None:
            o = ov[0]
            if ids and o.get("user_override") not in ids:
                item["problems"].append(f"override: user_override {o.get('user_override')!r} is not one of the options")
            if not str(o.get("user_rationale") or "").strip():
                item["problems"].append("override: no user_rationale")

        # status
        if req is not None and req.get("status") == "withdrawn":
            ok = len((req.get("withdrawn_reason") or "").strip()) >= 20
            item["status"] = "withdrawn" if ok else "invalid"
            if not ok:
                item["problems"].append("request: withdrawn without a withdrawn_reason (a sentence: why it no longer applies)")
        elif item["problems"]:
            item["status"] = "invalid"
        elif ov is not None:
            item["status"] = "overridden"
            item["override"] = {"file": ov[1], "user_override": ov[0].get("user_override")}
        elif stale:
            item["status"] = "stale"
        elif ver is not None:
            item["status"] = "resolved"
        elif a is not None:
            item["status"] = "auto_resolved"
            item["verdict"], item["confidence"] = a.get("auto_resolved_with"), (a.get("confidence") or "LOW").upper()
            if ids and a.get("auto_resolved_with") not in ids:
                item["status"] = "invalid"
                item["problems"].append(f"auto-resolved with {a.get('auto_resolved_with')!r}, not one of the options")
            elif domain == "security" and a.get("hardened") is not True:
                item["status"] = "invalid"
                item["problems"].append("a security decision is auto-resolved only with the hardened option (hardened: true)")
            else:
                item["review"].append("auto-resolved with a default: " + (a.get("reason") or "no reason recorded"))
        else:
            item["status"] = "pending"

        # review reasons and gate reasons
        sec_tag = "security debate" if domain == "security" else "debate"
        if ver is not None and item["status"] in ("resolved", "overridden"):
            v1 = ver.get("schema") == VERDICT_SCHEMA
            if (item["confidence"] or "") == "LOW":
                item["review"].append("LOW confidence")
            if ver.get("status") == "INCOMPLETE":
                item["review"].append("INCOMPLETE: " + (ver.get("reason") or "decided on incomplete evidence"))
            if ver.get("kind") == "assumption" or (req or {}).get("kind") == "assumption":
                item["review"].append("assumption, not a decision: confirm with the product owner")
            if ver.get("none_ideal"):
                item["review"].append("arbitrator found no option ideal")
            if not v1:
                item["review"].append("legacy verdict format")
            hd = ver.get("hardened_default")
            if domain == "security" and hd and ver.get("verdict") != hd:
                item["review"].append(f"security decision is not the hardened default ({hd})" +
                                      (f"; must_override: {ver.get('must_override')}" if ver.get("must_override") else ""))
            needs_second = v1 and impact == "HIGH" and derived is not None and \
                (derived["band"] != "HIGH" or (item["confidence"] or "HIGH") != "HIGH")
            disagrees = False
            if sec is not None:
                sp = second_problems(sec, ver, req, domain or "architecture")
                if sp and needs_second:
                    item["gate"] += [f"{sec_tag} '{t}': " + x for x in sp]
                elif sp:
                    item["review"] += sp
                if sec.get("verdict") and sec.get("verdict") != ver.get("verdict"):
                    disagrees = True
                    item["review"].append(f"second opinion ({sec.get('model') or '?'}) chose {sec.get('verdict')}")
                if sec.get("model") and "fable" not in str(sec.get("model")).lower():
                    item["review"].append(f"second opinion ran on {sec.get('model')}, not Fable: not independent of the primary")
                item["second_opinion"] = {"model": sec.get("model"), "verdict": sec.get("verdict")}
            elif needs_second:
                item["review"].append("second opinion required (HIGH impact, confidence not HIGH) but missing")
                if item["status"] == "resolved":
                    item["gate"].append(f"{sec_tag} '{t}' is a close HIGH-impact call with no second opinion ({t}.second-opinion.json)")
            if item["status"] == "resolved":
                if v1 and not promoted(ver, blocks, ver_rel):
                    item["review"].append("not promoted to docs/DECISIONS.md")
                    item["gate"].append(f"{sec_tag} '{t}' verdict has no D-NNN in docs/DECISIONS.md linking to {ver_rel} (remember.sh decide)")
                if domain == "security" and ver.get("status") == "INCOMPLETE":
                    item["gate"].append(f"security debate '{t}' is INCOMPLETE: a person decides (record it in {t}.override.json)")
                if domain == "security" and disagrees:
                    item["gate"].append(f"security debate '{t}': the second opinion disagrees, so a person decides (record it in {t}.override.json)")
                dt = (req or {}).get("default_taken")
                if req is not None and req.get("blocking") is False and dt and dt != ver.get("verdict"):
                    item["gate"].append(f"{sec_tag} '{t}': {item['from_agent'] or 'the requester'} built option {dt}, the verdict is {ver.get('verdict')}: relaunch it with the decision, then set default_taken to {ver.get('verdict')}")
        if req is not None and req_phase is None:
            item["review"].append("request has no phase field")
        if item["status"] == "pending":
            what = "blocking" if item["blocking"] else "non-blocking (the requester continued on a default)"
            item["gate"].insert(0, f"{sec_tag} '{t}' is pending, {what}: {req_rel} has no verdict (run debate_moderator, record a default in unresolved.json, or withdraw it with a reason)")
        elif item["status"] == "invalid":
            item["gate"].insert(0, f"{sec_tag} '{t}' breaks the debate contract: " + "; ".join(item["problems"]))
        elif item["status"] == "stale":
            item["gate"].insert(0, f"{sec_tag} '{t}' verdict answers an earlier version of {req_rel} (request_sha differs): re-run the debate")
        topics.append(item)

    blocking = [g for i in topics for g in i["gate"]] + [f"debate file unreadable: {u}" for u in unreadable]
    counts = {}
    for i in topics:
        counts[i["status"]] = counts.get(i["status"], 0) + 1
    return {
        "schema": "sdlc.debate-status/v1", "phase": phase, "topics": topics, "counts": counts, "blocking": blocking,
        "review": [{"topic": i["topic"], "reasons": i["review"]} for i in topics if i["review"]],
        "unreadable": unreadable, "unrecognized": unrecognized,
    }


def render(rep):
    scope = f"phase {rep['phase']}" if rep["phase"] is not None else "all phases"
    out = [f"Debates - {scope} ({len(rep['topics'])} topic(s))"]
    for i in rep["topics"]:
        tag = i["status"].upper().replace("AUTO_RESOLVED", "AUTO")
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
    for u in rep["unreadable"]:
        out.append(f"  ! {u}")
    for u in rep["unrecognized"]:
        out.append(f"  (ignored: {u})")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--root", default=os.environ.get("CLAUDE_PROJECT_DIR") or ".")
    ap.add_argument("--phase")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--request-sha", metavar="TOPIC")
    a = ap.parse_args(argv)
    if not os.path.isdir(a.root):
        print(f"debate-status: no such directory {a.root}", file=sys.stderr)
        return 3
    if a.request_sha:
        req = load(os.path.join(a.root, "agent_state", "debates", f"{a.request_sha}.request.json"))
        if not isinstance(req, dict):
            print(f"debate-status: no readable agent_state/debates/{a.request_sha}.request.json", file=sys.stderr)
            return 3
        print(request_sha(req))
        return 0
    rep = build(a.root, a.phase)
    print(json.dumps(rep, indent=2) if a.json else render(rep))
    if a.check and rep["blocking"]:
        if not a.json:
            for b in rep["blocking"]:
                print(f"BLOCKING: {b}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
