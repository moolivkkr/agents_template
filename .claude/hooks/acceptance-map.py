#!/usr/bin/env python3
"""acceptance-map.py — every requirement in docs/BRD.md → its TC-ACC rows → the tests that ran, and whether
the requirement changed after those tests were written.

  acceptance-map.py [--phase N | --all] [--results SIDECAR ...] [--out agent_state/accept/acceptance_map.json]
                    [--merge-into SIDECAR]
  acceptance-map.py --record [--phase N | --all] --results SIDECAR ... [--ack FR-012 "why the tests still hold"]

Scope:
  --phase N   the FRs in the Scope of every PHASE_PLAN.md numbered <= N: everything delivered so far plus this
              phase. A new phase re-proves every earlier FR, not only its own.
  --all       every FR in the BRD except Won't. /accept uses this.
  (neither)   the FRs of every planned phase; FRs no phase has picked up are listed as UNPLANNED (not blocking).

Per FR, the worst of:
  CHANGED   its BRD text (requirement, priority, acceptance criteria) differs from the text its tests were
            recorded against, so the tests verify the old requirement
  NEW       no TC-ACC row names the FR
  PARTIAL   the BRD has more SHALL clauses than its TC-ACC rows cover
  FAILING   a TC-ACC test for it failed (--results)
  UNTESTED  rows exist, but no test named with the ID ran and passed (without --results: no non-skipped test)
  COVERED   none of the above
Retire (requirements that went away):
  retire row   a TC-ACC row whose every FR left the BRD or became Won't: delete the row and its tests
  retire test  test code named with a TC-ACC ID that no spec row defines any more: delete the test
ONLY THE WORKING PHASE REMOVES, and only what it owns: rows in its own spec, test IDs from its own block
(NUMBER = P*10000 + ...), or rows/tests whose FR its PHASE_PLAN scope names. Every other retire candidate goes
to "retire_needs_decision": left in place, reported, never blocking. The working phase is --working-phase,
else --phase; with neither (bare /recon, /accept --all) nothing is removable.
--diff-base SHA (the commit the working phase started from) also flags every TC-ACC row or test removed since
then that the working phase doesn't own ("removed_outside_phase", blocking: restore it).

The JSON's "delta" lists what the current BRD calls for: add (NEW/PARTIAL), update (CHANGED), retire rows,
retire tests (the working phase's), retire_needs_decision (everyone else's).
An FR belongs to the phases whose PHASE_PLAN scopes it and the phases whose specs hold its TC-ACC rows.

Blocking = an in-scope Must/Should FR that is not COVERED, plus the working phase's own retire items, plus
removals outside the working phase. Exit 0 = none, 1 = some, 2 = usage/input error.
The FR's text is its row in a requirements table (Source/Phase/Status columns ignored), plus any heading or
line that starts with its ID, e.g. "FR-012: WHEN ... SHALL ...". Traceability, out-of-scope, open-question
and changelog sections are not part of any FR's text.

--merge-into SIDECAR adds one UNTESTED case per blocking FR (priority from MoSCoW) to an acceptance sidecar
(sdlc.test-results/v1) and sets its verdict to FAIL, so verify-gate.sh blocks on it like any failing HIGH case.

--record, after a green run, writes agent_state/accept/fr-baseline.json: for each COVERED FR, a hash of its BRD
text and of its TC-ACC rows. A CHANGED FR is re-recorded only when its TC-ACC rows changed too (the spec followed
the requirement) or with --ack FR "<why the tests still hold, 15+ chars>", which is kept in the baseline.
"""
import argparse, datetime, hashlib, importlib.util, json, os, re, subprocess, sys

sys.dont_write_bytecode = True          # importing tc-inventory.py must not leave __pycache__ in .claude/hooks
HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("tc_inventory", os.path.join(HERE, "tc-inventory.py"))
assert _spec and _spec.loader, "acceptance-map.py needs tc-inventory.py beside it"
tci = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tci)

FR_RE = re.compile(r"(?<![A-Za-z0-9-])FR-\d+(?:-?[a-z])?(?![A-Za-z0-9])")
SHALL_K_RE = r"(?<![A-Za-z0-9-]){fr}\s+SHALL\s+(\d+)"
SKIP_SECTION_RE = re.compile(r"traceab|out[- ]of[- ]scope|open question|change ?log|amendment|revision|history", re.I)
DROP_COL_RE = re.compile(r"source|phase|status|trace|owner|spec|test|design|link|^id$", re.I)
PRIORITY_COL_RE = re.compile(r"priority|moscow", re.I)
MOSCOW = {"must": "HIGH", "should": "MEDIUM", "could": "LOW", "wont": None, "won't": None}
BLOCKING_STATUSES = ("CHANGED", "NEW", "PARTIAL", "FAILING", "UNTESTED")


def norm_text(s):
    return re.sub(r"\s+", " ", re.sub(r"[*_`]+", "", s)).strip()


def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def moscow_of(text):
    t = text.strip().lower().replace("’", "'")
    for k in ("must", "should", "could", "won't", "wont"):
        if t.startswith(k):
            return k.replace("'", "")
    m = re.search(r"(?:priority|moscow)\s*[:=]\s*\**\s*(must|should|could|won'?t)", text, re.I) \
        or re.search(r"\((MUST|SHOULD|COULD|WON'?T)\)", text)
    return m.group(1).lower().replace("'", "") if m else None


# ─── BRD ──────────────────────────────────────────────────────────────────────────────────────────
def parse_brd(path):
    """{fr: {"blocks": [text], "moscow": str|None, "as_built": bool}} from the BRD's definition lines."""
    lines = open(path, encoding="utf-8", errors="replace").read().split("\n")
    frs, skip_level, i = {}, None, 0
    trows = tci.table_rows(lines)       # tc-inventory.py's table parser: header = the row above a |---| line

    def entry(fr):
        return frs.setdefault(fr, {"blocks": [], "moscow": None, "as_built": False})

    while i < len(lines):
        s = lines[i].strip()
        h = re.match(r"(#+)\s+(.*)", s)
        if h:
            level = len(h.group(1))
            if skip_level is not None and level <= skip_level:
                skip_level = None
            if skip_level is None and SKIP_SECTION_RE.search(h.group(2)):
                skip_level = level
        if skip_level is not None:
            i += 1
            continue
        if h:
            ids = FR_RE.findall(h.group(2))
            if ids and h.group(2).lstrip("*_` ").startswith(ids[0]):          # "### FR-012 — Title"
                level, block, j = len(h.group(1)), [s], i + 1
                while j < len(lines):
                    hh = re.match(r"(#+)\s", lines[j].strip())
                    if hh and len(hh.group(1)) <= level:
                        break
                    block.append(lines[j])
                    j += 1
                e = entry(ids[0])
                text = "\n".join(block)
                e["blocks"].append(norm_text(text))
                e["moscow"] = e["moscow"] or moscow_of(text)
                e["as_built"] = e["as_built"] or "as-built" in text.lower()
                i = j
                continue
            i += 1
            continue
        if s.startswith("|"):
            if re.fullmatch(r"[\s|:-]+", s):
                i += 1
                continue
            row = trows[i]
            cells = row["raw"]
            first = cells[0].strip("*_` ")
            if FR_RE.fullmatch(first):
                e = entry(first)
                cols = row["header"] or [""] * len(cells)
                kept = [c for j, c in enumerate(cells[1:], 1) if not DROP_COL_RE.search(cols[j] if j < len(cols) else "")]
                e["blocks"].append(norm_text(" | ".join(kept)))
                pj = next((j for j, c in enumerate(cols) if PRIORITY_COL_RE.search(c)), None)
                if pj is not None and pj < len(cells):
                    e["moscow"] = e["moscow"] or moscow_of(cells[pj])
                e["moscow"] = e["moscow"] or moscow_of(s)
                e["as_built"] = e["as_built"] or "as-built" in s.lower()
            i += 1
            continue
        lead = re.sub(r"^([-*+]\s+|\d+\.\s+)?[*_`]*", "", s)
        ids = FR_RE.findall(lead[:20])
        if ids and lead.startswith(ids[0]) and re.match(re.escape(ids[0]) + r"[*_`]*\s*([:—–.-]|\s)", lead):
            block, j = [s], i + 1                                              # "FR-012: WHEN ... SHALL ..."
            while j < len(lines):
                nxt = lines[j].strip()
                nlead = re.sub(r"^([-*+]\s+|\d+\.\s+)?[*_`]*", "", nxt)
                if not nxt or nxt.startswith("#") or nxt.startswith("|") or FR_RE.match(nlead):
                    break
                block.append(nxt)
                j += 1
            e = entry(ids[0])
            text = "\n".join(block)
            e["blocks"].append(norm_text(text))
            e["moscow"] = e["moscow"] or moscow_of(text)
            e["as_built"] = e["as_built"] or "as-built" in text.lower()
            i = j
            continue
        i += 1
    for e in frs.values():
        e["text"] = "\n".join(e["blocks"])
        e["hash"] = sha(e["text"])
        e["shall"] = len(re.findall(r"\bSHALL\b", e["text"], re.I))
    return frs


# ─── phase plans and specs ────────────────────────────────────────────────────────────────────────
def phase_dirs(root):
    base = os.path.join(root, "docs", "design", "phases")
    if not os.path.isdir(base):
        return []
    return sorted((int(d), os.path.join(base, d)) for d in os.listdir(base) if d.isdigit())


def plan_scope(path):
    """FR IDs in the PHASE_PLAN's Scope section, minus lines that defer or exclude them."""
    lines = open(path, encoding="utf-8", errors="replace").read().split("\n")
    start = level = None
    for i, l in enumerate(lines):
        m = re.match(r"(#+)\s+(.*)", l.strip())
        if m and re.search(r"\bscope\b", m.group(2), re.I) and not SKIP_SECTION_RE.search(m.group(2)):
            start, level = i, len(m.group(1))
            break
    body = lines if start is None else lines[start + 1:]
    out, sub_skip = set(), False
    for l in body:
        m = re.match(r"(#+)\s+(.*)", l.strip())
        if m:
            if level is not None and len(m.group(1)) <= level:
                break
            sub_skip = bool(re.search(r"out[- ]of[- ]scope|not in scope|defer", m.group(2), re.I))
            continue
        if sub_skip or re.search(r"defer|out[- ]of[- ]scope|not in scope|moved to phase", l, re.I):
            continue
        out |= set(FR_RE.findall(l))
    return out


def acceptance_rows(root):
    """[{id, priority, where, text, frs, shall_k}] for every TC-ACC / tier-acceptance row in every phase."""
    rows = []
    for n, d in phase_dirs(root):
        for tid, meta in tci.spec_rows(d).items():
            if not (tid.startswith("TC-ACC-") or meta["tier"] == "acceptance"):
                continue
            path, _, ln = meta["where"].rpartition(":")
            try:
                text = open(path, encoding="utf-8", errors="replace").read().split("\n")[int(ln) - 1]
            except (OSError, ValueError, IndexError):
                text = ""
            frs = sorted(set(FR_RE.findall(text)))
            rows.append({"id": tid, "phase": n, "priority": meta["priority"], "where": f"{os.path.relpath(path, root)}:{ln}",
                         "text": norm_text(text), "frs": frs,
                         "shall_k": {fr: sorted({int(k) for k in re.findall(SHALL_K_RE.format(fr=re.escape(fr)), text)}) for fr in frs}})
    return rows


def row_verdicts(root, results):
    cases = tci.scan_tests(root)[0]
    named, any_named = {}, {}
    for c in cases:
        for i in c["ids"]:
            any_named.setdefault(i, []).append((f"{c['file']}:{c['line']}", c["name"]))   # skipped ones too: still test code
            if not c["skipped"]:
                named.setdefault(i, []).append(f"{c['file']}:{c['line']}")
    res = {}
    for p in results:
        try:
            sc = json.load(open(p))
        except (OSError, ValueError) as e:
            sys.exit(f"acceptance-map: cannot read results {p}: {e}")
        for c in sc.get("cases", []):
            for i in c.get("ids", []):
                res.setdefault(i, []).append(str(c.get("verdict", "")).upper())

    def verdict(tid):
        if results:
            vs = res.get(tid, [])
            return "FAIL" if any(v in ("FAIL", "FLAKY") for v in vs) else ("PASS" if "PASS" in vs else "UNTESTED")
        return "PASS" if named.get(tid) else "UNTESTED"
    return verdict, named, {k: [w for w, _ in v] for k, v in any_named.items()}, \
        {k: {fr for _, n in v for fr in FR_RE.findall(n)} for k, v in any_named.items()}


def id_phase(tid):
    """The phase an ID was allocated to (NUMBER = P*10000 + k*100 + i); None for legacy numbering."""
    m = re.search(r"(\d+)$", tid)
    n = int(m.group(1)) if m else 0
    return n // 10000 if n >= 10000 else None


def removed_since(root, base):
    """{TC-ACC id: {"phases", "frs", "where"}} for IDs on spec or test lines removed since `base`."""
    def git(*a):
        return subprocess.run(["git", "-C", root, *a], capture_output=True, text=True).stdout
    files = [f for f in git("diff", "--name-only", "--no-renames", base, "--").split("\n") if f and
             ((f.startswith("docs/design/phases/") and f.endswith(".md")) or tci.is_test_file(f))]
    out, path, header = {}, None, False
    if not files:
        return out
    for line in git("diff", "-U0", "--no-color", "--no-renames", base, "--", *files).split("\n"):
        if line.startswith("diff --git"):
            header, path = True, None
        elif header and line.startswith("--- a/"):
            path = line[6:]
        elif header and line.startswith("+++ b/") and path is None:
            path = line[6:]
        elif line.startswith("@@"):
            header = False
        elif not header and line.startswith("-") and path:
            for tid in (i for i in tci.ids_in(line) if i.startswith("TC-ACC-")):
                e = out.setdefault(tid, {"phases": set(), "frs": set(), "where": []})
                m = re.match(r"docs/design/phases/(\d+)/", path)
                if m:
                    e["phases"].add(int(m.group(1)))
                e["frs"] |= set(FR_RE.findall(line))
                if path not in e["where"]:
                    e["where"].append(path)
    return out


# ─── the map ──────────────────────────────────────────────────────────────────────────────────────
def build(root, brd_path, scope_phase, scope_all, results, baseline, working_phase=None, diff_base=None):
    frs = parse_brd(brd_path)
    plans = {n: plan_scope(os.path.join(d, "PHASE_PLAN.md")) for n, d in phase_dirs(root)
             if os.path.isfile(os.path.join(d, "PHASE_PLAN.md"))}
    rows = acceptance_rows(root)
    wont = {fr for fr, e in frs.items() if e["moscow"] == "wont"}
    active = set(frs) - wont
    # An FR belongs to the phases whose plan scopes it AND the phases whose specs hold its TC-ACC rows
    # (rows added later by /recon or /accept amend a delivered phase without re-planning it).
    owner = {}
    for n, ids in sorted(plans.items()):
        for fr in ids:
            owner.setdefault(fr, []).append(n)
    for r in rows:
        for fr in r["frs"]:
            if fr in active and r["phase"] not in owner.setdefault(fr, []):
                owner[fr].append(r["phase"])
    for fr in owner:
        owner[fr].sort()
    upto = (lambda n: n <= scope_phase) if scope_phase is not None else (lambda n: True)
    if scope_all:
        scope, label = set(frs), "all"
    elif scope_phase is not None:
        scope, label = {fr for fr, ns in owner.items() if any(upto(n) for n in ns)}, f"phase<={scope_phase}"
    else:
        scope, label = set(owner), "planned"
    verdict, named, any_named, test_frs = row_verdicts(root, results)
    by_fr = {}
    for r in rows:
        r["verdict"] = verdict(r["id"])
        r["tests"] = named.get(r["id"], [])[:3]
        for fr in r["frs"]:
            by_fr.setdefault(fr, []).append(r)

    out_frs, unplanned = [], []
    for fr in sorted(frs, key=lambda x: (int(re.sub(r"\D", "", x.split("-")[1]) or 0), x)):
        e = frs[fr]
        moscow = e["moscow"]
        if moscow == "wont":
            continue
        priority = MOSCOW.get(moscow or "should") or "MEDIUM"
        if fr not in scope:
            if not scope_all and scope_phase is None:
                unplanned.append({"fr": fr, "priority": priority, "as_built": e["as_built"]})
            continue
        rs = by_fr.get(fr, [])
        issues = []
        base = (baseline.get("frs") or {}).get(fr)
        if base and base.get("brd_hash") != e["hash"]:
            issues.append(("CHANGED", "BRD text changed since its acceptance tests were recorded "
                                      f"({base.get('recorded', '?')[:10]}) — update its TC-ACC rows and tests"))
        if not rs:
            where = "" if owner.get(fr) else " (in no phase)"
            issues.append(("NEW", "no TC-ACC row names it" + where))
        else:
            ks = sorted({k for r in rs for k in r["shall_k"].get(fr, [])})
            if ks:
                gap = [k for k in range(1, e["shall"] + 1) if k not in ks]
                if gap:
                    issues.append(("PARTIAL", f"SHALL {', '.join(map(str, gap))} of {e['shall']} have no TC-ACC row"))
            elif len(rs) < e["shall"]:
                issues.append(("PARTIAL", f"{len(rs)} TC-ACC row(s) for {e['shall']} SHALL clause(s)"))
            bad = [r["id"] for r in rs if r["verdict"] == "FAIL"]
            if bad:
                issues.append(("FAILING", "failed: " + ", ".join(bad)))
            unt = [r["id"] for r in rs if r["verdict"] == "UNTESTED"]
            if unt:
                issues.append(("UNTESTED", "no passing test named: " + ", ".join(unt[:8])))
        status = next((s for s in BLOCKING_STATUSES if any(k == s for k, _ in issues)), "COVERED")
        out_frs.append({
            "fr": fr, "moscow": moscow or "unknown (treated as Should)", "priority": priority,
            "as_built": e["as_built"], "phases": owner.get(fr, []), "shall": e["shall"], "brd_hash": e["hash"],
            "rows_hash": sha("\n".join(f"{r['id']} {r['text']}" for r in sorted(rs, key=lambda r: r["id"]))),
            "rows": [{k: r[k] for k in ("id", "phase", "priority", "verdict", "where", "tests")} for r in rs],
            "status": status, "issues": [f"{k}: {v}" for k, v in issues],
            "blocking": status != "COVERED" and priority in ("HIGH", "MEDIUM"),
        })
    # Retire: rows whose every FR left the BRD or became Won't, and test code named with a TC-ACC ID that
    # no spec row defines any more. Only the WORKING phase may remove anything, and only what it owns (rows
    # in its own spec, test IDs from its own block) or what its PHASE_PLAN names. Everything else is left
    # in place and listed for a decision; it never blocks the working phase.
    impacted = plans.get(working_phase, set()) if working_phase is not None else set()

    def may_remove(owner, frs_):
        return working_phase is not None and (owner == working_phase or bool(set(frs_) & impacted))

    retire_rows, retire_tests, needs_decision = [], [], []
    for r in rows:
        if r["frs"] and not any(f in active for f in r["frs"]):
            why = "; ".join(f"{f} {'is Won’t' if f in wont else 'is no longer in the BRD'}" for f in r["frs"])
            item = {"id": r["id"], "phase": r["phase"], "where": r["where"], "frs": r["frs"],
                    "tests": any_named.get(r["id"], [])[:5], "reason": why}
            if may_remove(r["phase"], r["frs"]):
                retire_rows.append(item)
            else:
                needs_decision.append(dict(item, kind="row", owner=r["phase"]))
    row_ids = {r["id"] for r in rows}
    for tid, where in sorted(any_named.items()):
        if tid.startswith("TC-ACC-") and tid not in row_ids:
            owner, frs_ = id_phase(tid), sorted(test_frs.get(tid, set()))
            item = {"id": tid, "tests": where[:5], "frs": frs_, "reason": "no spec row defines this TC-ACC ID"}
            if may_remove(owner, frs_):
                retire_tests.append(item)
            else:
                needs_decision.append(dict(item, kind="test", owner=owner, where=", ".join(where[:2])))
    # Guard: a TC-ACC row or test removed since the working phase started, that the phase doesn't own.
    removed_outside = []
    if diff_base and working_phase is not None:
        now_ids = row_ids | set(any_named)
        for tid, info in sorted(removed_since(root, diff_base).items()):
            if tid in now_ids:
                continue                                   # edited or moved, not removed
            owners = info["phases"] or ({id_phase(tid)} - {None})
            if working_phase in owners or info["frs"] & impacted:
                continue
            removed_outside.append({"id": tid, "owner": sorted(owners) or "unknown", "frs": sorted(info["frs"]),
                                    "where": info["where"],
                                    "reason": f"removed since {diff_base[:12]} but owned by phase {sorted(owners) or 'unknown'}, "
                                              f"not the working phase {working_phase}: restore it"})
    unlinked = [{"id": r["id"], "where": r["where"]} for r in rows if not r["frs"]]
    delta = {
        "add": [{"fr": f["fr"], "status": f["status"], "phases": f["phases"], "as_built": f["as_built"], "detail": "; ".join(f["issues"])}
                for f in out_frs if f["status"] in ("NEW", "PARTIAL")],
        "update": [{"fr": f["fr"], "phases": f["phases"], "rows": [r["id"] for r in f["rows"]], "detail": "; ".join(f["issues"]),
                    # the rows were rewritten since the baseline: the spec followed the requirement (tests may not have yet)
                    "rows_amended": ((baseline.get("frs") or {}).get(f["fr"]) or {}).get("rows_hash") != f["rows_hash"]}
                   for f in out_frs if f["status"] == "CHANGED"],
        "retire_rows": retire_rows, "retire_tests": retire_tests,        # the working phase removes these
        "retire_needs_decision": needs_decision,                          # nobody removes these automatically
    }
    counts = {}
    for f in out_frs:
        counts[f["status"]] = counts.get(f["status"], 0) + 1
    sha_, dirty = tci.code_state(root)
    blocking = sum(f["blocking"] for f in out_frs) + len(retire_rows) + len(retire_tests) + len(removed_outside)
    return {
        "schema": "sdlc.acceptance-map/v1", "scope": label, "brd": os.path.relpath(brd_path, root),
        "mode": "results" if results else "source", "code_sha": sha_, "dirty": dirty, "working_phase": working_phase,
        "summary": {"frs": len(out_frs), "by_status": counts, "blocking": blocking,
                    "add": len(delta["add"]), "update": len(delta["update"]),
                    "retire_rows": len(retire_rows), "retire_tests": len(retire_tests),
                    "retire_needs_decision": len(needs_decision), "removed_outside_phase": len(removed_outside),
                    "unlinked_rows": len(unlinked), "unplanned": len(unplanned)},
        "frs": out_frs, "delta": delta, "removed_outside_phase": removed_outside, "unlinked_rows": unlinked, "unplanned": unplanned,
        "ts": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def write_md(m, path):
    L = [f"# Acceptance map — requirements → acceptance tests ({m['scope']})", "",
         f"Generated {m['ts']} from `{m['brd']}` · code {str(m['code_sha'])[:12]} · mode {m['mode']} · "
         f"blocking {m['summary']['blocking']} · {json.dumps(m['summary']['by_status'])}", "",
         "| FR | MoSCoW | Phase(s) | SHALLs | TC-ACC (verdict) | Status | Detail |",
         "|----|--------|----------|--------|------------------|--------|--------|"]
    for f in m["frs"]:
        tcs = ", ".join(f"{r['id']} ({r['verdict']})" for r in f["rows"][:6]) + (" …" if len(f["rows"]) > 6 else "")
        mark = "⛔ " if f["blocking"] else ""
        L.append(f"| {f['fr']}{' (as-built)' if f['as_built'] else ''} | {f['moscow']} | {','.join(map(str, f['phases'])) or '—'} | "
                 f"{f['shall']} | {tcs or '—'} | {mark}{f['status']} | {'; '.join(f['issues']) or ''} |")
    d = m["delta"]
    if any(d.values()):
        L += ["", "## Acceptance changes the requirements call for", "",
              "| Action | What | Where | Why |", "|--------|------|-------|-----|"]
        L += [f"| add rows + tests | {a['fr']}{' (as-built)' if a['as_built'] else ''} | phase {','.join(map(str, a['phases'])) or '— (the phase amending it)'} | {a['detail']} |" for a in d["add"]]
        L += [f"| update rows + tests | {u['fr']} ({', '.join(u['rows'])}) | phase {','.join(map(str, u['phases']))} | {u['detail']} |" for u in d["update"]]
        L += [f"| retire row + its tests | {r['id']} | {r['where']}{' · tests ' + ', '.join(r['tests']) if r['tests'] else ''} | {r['reason']} |" for r in d["retire_rows"]]
        L += [f"| delete test | {t['id']} | {', '.join(t['tests'])} | {t['reason']} |" for t in d["retire_tests"]]
        if d["retire_needs_decision"]:
            L += ["", f"## Needs a decision — not removed (working phase: {m['working_phase'] if m['working_phase'] is not None else 'none'})", "",
                  "Rows/tests for requirements that went away, owned by a phase other than the working one. They stay",
                  "until their owning phase's work (or a human) removes them. They don't block the working phase.", ""]
            L += [f"- {x['kind']} {x['id']} (phase {x['owner'] if x['owner'] is not None else 'unknown'}) at {x['where']}: {x['reason']}"
                  for x in d["retire_needs_decision"]]
    if m["removed_outside_phase"]:
        L += ["", "## ⛔ Removed outside the working phase — restore", ""] + \
             [f"- {x['id']} (owner {x['owner']}) from {', '.join(x['where'])}: {x['reason']}" for x in m["removed_outside_phase"]]
    if m["unplanned"]:
        L += ["", "## In the BRD, in no phase yet", ""] + [f"- {u['fr']} ({u['priority']}{', as-built' if u['as_built'] else ''})" for u in m["unplanned"]]
    if m["unlinked_rows"]:
        L += ["", "## TC-ACC rows that name no FR (can't be traced)", ""] + [f"- {o['id']} at {o['where']}" for o in m["unlinked_rows"]]
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    open(path, "w").write("\n".join(L) + "\n")


def merge_into(m, path):
    try:
        sc = json.load(open(path))
    except (OSError, ValueError) as e:
        sys.exit(f"acceptance-map: cannot read sidecar {path}: {e}")
    sc["cases"] = [c for c in sc.get("cases", []) if c.get("source") != "acceptance-map"]
    added = 0
    for f in m["frs"]:
        if f["blocking"]:
            sc["cases"].append({"name": f"{f['fr']} {f['status']} — {'; '.join(f['issues'])[:200]}", "ids": [],
                                "priority": f["priority"], "verdict": "UNTESTED", "source": "acceptance-map"})
            added += 1
    for r in m["delta"]["retire_rows"]:
        sc["cases"].append({"name": f"{r['id']} RETIRE — {r['reason']}: delete the row ({r['where']}) and its tests", "ids": [],
                            "priority": "HIGH", "verdict": "UNTESTED", "source": "acceptance-map"})
        added += 1
    for t in m["delta"]["retire_tests"]:
        sc["cases"].append({"name": f"{t['id']} RETIRE — {t['reason']}: delete the test at {', '.join(t['tests'][:2])}", "ids": [],
                            "priority": "HIGH", "verdict": "UNTESTED", "source": "acceptance-map"})
        added += 1
    for x in m["removed_outside_phase"]:
        sc["cases"].append({"name": f"{x['id']} REMOVED OUTSIDE PHASE — {x['reason']}", "ids": [],
                            "priority": "HIGH", "verdict": "UNTESTED", "source": "acceptance-map"})
        added += 1
    if added:
        sc["verdict"] = "FAIL"
    sc["acceptance_map"] = {"scope": m["scope"], "blocking": [f["fr"] for f in m["frs"] if f["blocking"]],
                            "retire": [r["id"] for r in m["delta"]["retire_rows"] + m["delta"]["retire_tests"]],
                            "retire_needs_decision": [x["id"] for x in m["delta"]["retire_needs_decision"]],
                            "removed_outside_phase": [x["id"] for x in m["removed_outside_phase"]]}
    json.dump(sc, open(path, "w"), indent=1)
    return added


def record(m, baseline, acks, path):
    frs = baseline.setdefault("frs", {})
    baseline["schema"] = "sdlc.acceptance-baseline/v1"
    done, held = [], []
    now = m["ts"]
    for f in m["frs"]:
        other = [i for i in f["issues"] if not i.startswith("CHANGED")]
        if other:
            continue                                  # not green for this FR — nothing to record
        prev = frs.get(f["fr"])
        entry = {"brd_hash": f["brd_hash"], "rows_hash": f["rows_hash"], "tcs": [r["id"] for r in f["rows"]],
                 "recorded": now, "code_sha": m["code_sha"]}
        if f["status"] == "CHANGED":
            if prev and prev.get("rows_hash") != f["rows_hash"]:
                entry["reason"] = "TC-ACC rows updated with the requirement"
            elif f["fr"] in acks:
                entry["ack"] = {"reason": acks[f["fr"]], "date": now[:10]}
            else:
                held.append(f["fr"])
                continue
        frs[f["fr"]] = entry
        done.append(f["fr"])
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    json.dump(baseline, open(path, "w"), indent=1, sort_keys=True)
    return done, held


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--phase", type=int)
    g.add_argument("--all", action="store_true")
    ap.add_argument("--root", default=".")
    ap.add_argument("--brd", default="docs/BRD.md")
    ap.add_argument("--results", nargs="*", default=[])
    ap.add_argument("--baseline", default="agent_state/accept/fr-baseline.json")
    ap.add_argument("--out", default="agent_state/accept/acceptance_map.json")
    ap.add_argument("--merge-into")
    ap.add_argument("--working-phase", type=int, help="the phase allowed to remove rows/tests (default: --phase)")
    ap.add_argument("--diff-base", help="commit the working phase started from: flag TC-ACC rows/tests it removed but doesn't own")
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--ack", nargs=2, action="append", default=[], metavar=("FR", "REASON"))
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    rel = lambda p: p if os.path.isabs(p) else os.path.join(root, p)
    brd = rel(a.brd)
    if not os.path.isfile(brd):
        print(f"acceptance-map: no BRD at {a.brd}", file=sys.stderr)
        return 2
    acks = {}
    for fr, reason in a.ack:
        if len(reason.strip()) < 15:
            print(f"acceptance-map: --ack {fr} needs a reason of 15+ characters saying why the tests still hold", file=sys.stderr)
            return 2
        acks[fr] = reason.strip()
    if a.record and not a.results:
        print("acceptance-map: --record needs --results (only a run that passed can be recorded)", file=sys.stderr)
        return 2
    try:
        baseline = json.load(open(rel(a.baseline)))
    except (OSError, ValueError):
        baseline = {}
    working = a.working_phase if a.working_phase is not None else a.phase
    m = build(root, brd, a.phase, a.all, [rel(p) for p in a.results], baseline, working, a.diff_base)
    out = rel(a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(m, open(out, "w"), indent=1)
    write_md(m, re.sub(r"\.json$", "", out) + ".md")
    s = m["summary"]
    print(f"acceptance-map ({m['scope']}, {m['mode']}): {s['frs']} FRs {json.dumps(s['by_status'])}; blocking {s['blocking']}; "
          f"to add {s['add']}, update {s['update']}, retire rows {s['retire_rows']}, retire tests {s['retire_tests']}, "
          f"needs decision {s['retire_needs_decision']}, removed outside phase {s['removed_outside_phase']}; "
          f"unlinked rows {s['unlinked_rows']}, unplanned {s['unplanned']}")
    for f in m["frs"]:
        if f["status"] != "COVERED":
            print(f"  {'⛔' if f['blocking'] else '·'} {f['fr']} [{f['priority']}] {'; '.join(f['issues'])}")
    for r in m["delta"]["retire_rows"]:
        print(f"  ⛔ {r['id']} RETIRE row ({r['where']}): {r['reason']}")
    for t in m["delta"]["retire_tests"]:
        print(f"  ⛔ {t['id']} RETIRE test ({', '.join(t['tests'][:2])}): {t['reason']}")
    for x in m["delta"]["retire_needs_decision"]:
        print(f"  · {x['id']} {x['kind']} of phase {x['owner'] if x['owner'] is not None else '?'} — needs a decision, not removed: {x['reason']}")
    for x in m["removed_outside_phase"]:
        print(f"  ⛔ {x['id']} REMOVED OUTSIDE PHASE {m['working_phase']}: {x['reason']}")
    if a.merge_into:
        n = merge_into(m, rel(a.merge_into))
        print(f"  merged {n} blocking gap(s) into {a.merge_into}")
    if a.record:
        done, held = record(m, baseline, acks, rel(a.baseline))
        print(f"  recorded {len(done)} FR baseline(s) in {a.baseline}")
        for fr in held:
            print(f"  ⛔ {fr} still CHANGED: update its TC-ACC rows (spec_writer acceptance-amend mode) and tests, "
                  f"or --ack {fr} \"<why the existing tests still hold>\"")
        return 1 if held else 0
    return 1 if s["blocking"] else 0


if __name__ == "__main__":
    sys.exit(main())
