#!/usr/bin/env python3
"""tc-inventory.py — TC-* coverage that means "a test ran and passed", not "the string appears".

  tc-inventory.py --phase N [--root .] [--results sidecar.json ...] [--diff-base SHA]
                  [--out agent_state/phases/N/reports/tc_inventory.json]
  tc-inventory.py --phase N --spec-only --out priorities.json     # {"TC-X-1": "HIGH", ...}

Spec side: the TC inventory TABLES in docs/design/phases/N/**/*.md (rows whose ID cell is a TC ID;
Priority/Tier columns when present, priority defaults to MEDIUM = blocking). Range lines such as
"TC-E-106 to TC-E-110" are groupings, not IDs. An ID defined by more than one phase is an error: IDs are
project-unique (spec_writer allocates them).

Test side, a TC ID counts only when it is in the NAME of a test case (test title, subtest name,
parametrize id, table-driven `name:` field, Maestro flow name/file) that is not skipped. Comment-only IDs,
TODOs, skipped tests and range annotations do not count. With --results (sidecars from
junit-to-sidecar.py / test_runner), the covering test must also have PASSED in that run.

--diff-base SHA: flags test weakening since the phase started — removed assertion lines, new skip / only
markers, deleted test files. Each needs an entry in agent_state/phases/N/test-changes.json
([{"file": ..., "kind": "removed_assertion|added_skip|added_only|deleted_test_file", "reason": ...}]).

Writes an sdlc.test-results/v1 sidecar (tier "tc-inventory"); exit 0 = PASS, 1 = FAIL.
"""
import argparse, datetime, json, os, re, subprocess, sys

TC = r"TC[-_]([A-Z0-9]+)[-_](\d+)"
TC_RE = re.compile(r"(?<![A-Za-z0-9])" + TC + r"(?![0-9])")   # TC_X_1 inside TestFoo_TC_X_1 too
RANGE_RE = re.compile(r"\bTC-[A-Z0-9]+-\d+\s*(?:to|through|thru|–|—|\.\.|-)\s*TC-[A-Z0-9]+-\d+\b")
SKIP_DIRS = {".git", "node_modules", "vendor", "dist", "build", ".next", "coverage", "Pods", "agent_state",
             "docs", ".claude", "__pycache__", "target", ".venv", "venv", ".gradle", "DerivedData", ".expo"}
CODE_EXCLUDES = ["agent_state", "docs", ".claude", "deploy/k8s/overlays"]


def norm(m):
    return f"TC-{m.group(1)}-{m.group(2)}"


def ids_in(text):
    return {norm(m) for m in TC_RE.finditer(text or "")}


# ─── spec inventory ───────────────────────────────────────────────────────────────────────────────
def spec_rows(phase_dir):
    """{id: {"priority", "tier", "where"}} from markdown tables under a phase's design dir."""
    out = {}
    for base, _dirs, files in os.walk(phase_dir):
        for fn in sorted(files):
            if not fn.endswith(".md"):
                continue
            path = os.path.join(base, fn)
            lines = open(path, encoding="utf-8", errors="replace").read().split("\n")
            header = None
            for i, line in enumerate(lines):
                s = line.strip()
                if not s.startswith("|"):
                    header = None                       # a table ended
                    continue
                if re.fullmatch(r"[\s|:-]+", s):          # separator row
                    continue
                cells = [c.strip().strip("`*_ ") for c in s.strip("|").split("|")]
                idc = next((c for c in cells if re.fullmatch(r"TC-[A-Z0-9]+-\d+", c)), None)
                if idc is None:
                    header = [c.lower() for c in cells]  # a header (or any non-ID row) names the columns
                    continue
                col = lambda name: next((j for j, h in enumerate(header or []) if name in h), None)
                pj, tj = col("priority"), col("tier")
                pr = (cells[pj].upper() if pj is not None and pj < len(cells) else "") or "MEDIUM"
                pr = pr if pr in ("HIGH", "MEDIUM", "LOW") else "MEDIUM"
                tier = cells[tj].lower() if tj is not None and tj < len(cells) else ""
                out.setdefault(idc, {"priority": pr, "tier": tier, "where": f"{path}:{i + 1}"})
    return out


# ─── test cases ───────────────────────────────────────────────────────────────────────────────────
def is_test_file(path):
    fn = os.path.basename(path)
    if re.search(r"_test\.go$", fn) or re.search(r"\.(test|spec)\.[cm]?[jt]sx?$", fn):
        return True
    if re.fullmatch(r"test_.*\.py|.*_test\.py", fn):
        return True
    if re.search(r"(Test|Tests|IT)\.(java|kt)$", fn):
        return True
    if fn.endswith(".rs"):
        return True                                     # filtered by #[test] content below
    if re.search(r"\.ya?ml$", fn) and ".maestro" in path.split(os.sep):
        return True
    if "__tests__" in path.split(os.sep) and re.search(r"\.[cm]?[jt]sx?$", fn):
        return True
    return False


def matching_paren(text, i):
    """text[i] == '(' → index of the matching ')' (strings/comments approximated)."""
    depth, q = 0, None
    while i < len(text):
        ch = text[i]
        if q:
            if ch == "\\":
                i += 2
                continue
            if ch == q:
                q = None
        elif ch in "'\"`":
            q = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return len(text)


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def cases_go(text):
    out = []
    funcs = [m for m in re.finditer(r"^func\s+(Test\w+|Example\w+|Benchmark\w+|Fuzz\w+)\s*\(", text, re.M)]
    for k, m in enumerate(funcs):
        end = funcs[k + 1].start() if k + 1 < len(funcs) else len(text)
        body = text[m.start():end]
        code = "\n".join(l for l in body.split("\n") if not l.strip().startswith("//"))
        skipped = bool(re.search(r"\bt\.Skip(Now|f)?\(", code))
        out.append((m.group(1), line_of(text, m.start()), skipped))
        for s in re.finditer(r"\bt\.Run\(\s*\"((?:\\.|[^\"])*)\"", code):
            out.append((f"{m.group(1)}/{s.group(1)}", line_of(text, m.start()), skipped))
        for s in re.finditer(r"\bname:\s*\"((?:\\.|[^\"])*)\"", code):
            out.append((f"{m.group(1)}/{s.group(1)}", line_of(text, m.start()), skipped))
    return out


JS_CASE = re.compile(r"\b(x?(?:it|test|describe))((?:\.(?:skip|only|todo|fixme|concurrent|serial|each\([^)]*\)))*)\s*\(\s*(['\"`])((?:\\.|(?!\3).)*)\3", re.S)


def cases_js(text):
    out, skip_ranges = [], []
    for m in JS_CASE.finditer(text):
        kw, mods, title = m.group(1), m.group(2) or "", m.group(4)
        skipped = kw.startswith("x") or bool(re.search(r"\.(skip|todo|fixme)\b", mods))
        paren = text.find("(", m.start() + len(kw) + len(mods))
        if skipped and kw.endswith("describe"):
            skip_ranges.append((paren, matching_paren(text, paren)))
        if not kw.endswith("describe"):
            out.append([title, m.start(), skipped])
    res = []
    for title, pos, skipped in out:
        if any(a <= pos <= b for a, b in skip_ranges):
            skipped = True
        res.append((title, line_of(text, pos), skipped))
    return res


def cases_py(text):
    out = []
    lines = text.split("\n")
    for i, l in enumerate(lines):
        m = re.match(r"\s*(?:async\s+)?def\s+(test\w*)\s*\(", l)
        if not m:
            continue
        deco = []                                         # decorator lines (incl. multi-line) above the def
        j = i - 1
        while j >= 0 and len(deco) < 30:
            s = lines[j].strip()
            if not s or re.match(r"(async\s+)?(def|class)\s", s):
                break
            deco.append(lines[j])
            j -= 1
        d = "\n".join(reversed(deco))
        body = "\n".join(lines[i + 1:i + 6])
        skipped = bool(re.search(r"@(pytest\.mark\.(skip|xfail)|unittest\.skip)", d) or re.search(r"\bpytest\.skip\(", body))
        out.append((m.group(1), i + 1, skipped))
        for p in re.finditer(r"\bid\s*=\s*['\"]([^'\"]+)['\"]", d):
            out.append((f"{m.group(1)}[{p.group(1)}]", i + 1, skipped))
        ids = re.search(r"\bids\s*=\s*\[([^\]]*)\]", d, re.S)
        if ids:
            for s in re.finditer(r"['\"]([^'\"]+)['\"]", ids.group(1)):
                out.append((f"{m.group(1)}[{s.group(1)}]", i + 1, skipped))
    return out


def cases_rs(text):
    out = []
    for m in re.finditer(r"#\[(?:tokio::)?test[^\]]*\]((?:\s*#\[[^\]]*\])*)\s*(?:async\s+)?fn\s+(\w+)", text):
        out.append((m.group(2), line_of(text, m.start()), "#[ignore" in m.group(1)))
    return out


def cases_jvm(text):
    out = []
    for m in re.finditer(r"@Test\b((?:\s*@[\w.]+(?:\([^)]*\))?)*)\s*(?:public\s+|internal\s+)?(?:void|fun)\s+`?([^`(\s]+)`?", text):
        ann = m.group(1)
        dn = re.search(r"@DisplayName\(\s*\"([^\"]*)\"", ann)
        name = (dn.group(1) + " ") if dn else ""
        out.append((name + m.group(2), line_of(text, m.start()), "@Disabled" in ann or "@Ignore" in ann))
    return out


def cases_maestro(path, text):
    head = text.split("---")[0]
    nm = re.search(r"^\s*name:\s*['\"]?([^'\"\n]+)", head, re.M)
    first_comment = next((l for l in text.split("\n") if l.strip().startswith("#")), "")
    name = " ".join(x for x in [os.path.splitext(os.path.basename(path))[0], nm.group(1) if nm else "", first_comment] if x)
    return [(name, 1, False)]


def scan_tests(root):
    cases, comment_ids, ranges = [], {}, []
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS or d == ".maestro"]
        for fn in files:
            path = os.path.join(base, fn)
            if not is_test_file(path):
                continue
            try:
                text = open(path, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            rel = os.path.relpath(path, root)
            if fn.endswith(".go"):
                found = cases_go(text)
            elif re.search(r"\.[cm]?[jt]sx?$", fn):
                found = cases_js(text)
            elif fn.endswith(".py"):
                found = cases_py(text)
            elif fn.endswith(".rs"):
                if "#[test]" not in text and "#[tokio::test" not in text:
                    continue
                found = cases_rs(text)
            elif re.search(r"\.(java|kt)$", fn):
                found = cases_jvm(text)
            else:
                found = cases_maestro(path, text)
            for name, ln, skipped in found:
                cases.append({"file": rel, "line": ln, "name": name, "skipped": skipped, "ids": sorted(ids_in(name))})
            for m in TC_RE.finditer(text):
                comment_ids.setdefault(norm(m), f"{rel}:{line_of(text, m.start())}")
            for m in RANGE_RE.finditer(text):
                ranges.append(f"{rel}:{line_of(text, m.start())}: {m.group(0)}")
    return cases, comment_ids, ranges


# ─── test weakening since a base commit ───────────────────────────────────────────────────────────
ASSERT_RE = re.compile(r"\b(assert\w*|expect\s*\(|require\.\w+\(|t\.(Error|Errorf|Fatal|Fatalf|Fail|FailNow)\b|"
                       r"\.to(Be|Equal|Have|Match|Contain|Throw|StrictEqual)\w*\(|Assert\.\w+\(|assertThat\(|should\.)")
SKIP_ADD_RE = re.compile(r"\b(it|test|describe)\.(skip|todo|fixme)\b|\bx(it|test|describe)\s*\(|\bt\.Skip(Now|f)?\(|"
                         r"@pytest\.mark\.(skip|xfail)|@unittest\.skip|#\[ignore\]|@Disabled|@Ignore")
ONLY_ADD_RE = re.compile(r"\b(it|test|describe)\.only\b|\bfit\s*\(|\bfdescribe\s*\(")


def weakening(root, base):
    spec = ["--", "."] + [f":(exclude){p}" for p in CODE_EXCLUDES]
    try:
        names = subprocess.run(["git", "-C", root, "diff", "--name-status", base] + spec, capture_output=True, text=True, check=True).stdout
        diff = subprocess.run(["git", "-C", root, "diff", "--unified=0", base] + spec, capture_output=True, text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        return [{"file": "-", "kind": "diff_unavailable", "detail": str(e)}]
    found = []
    for l in names.splitlines():
        parts = l.split("\t")
        if parts[0].startswith("D") and len(parts) > 1 and is_test_file(parts[1]):
            found.append({"file": parts[1], "kind": "deleted_test_file", "detail": ""})
    cur = None
    for l in diff.splitlines():
        if l.startswith("+++ "):
            cur = l[6:] if l.startswith("+++ b/") else None
            continue
        if l.startswith("--- ") or cur is None or not is_test_file(cur):
            continue
        if l.startswith("-") and ASSERT_RE.search(l):
            found.append({"file": cur, "kind": "removed_assertion", "detail": l[1:].strip()[:160]})
        elif l.startswith("+") and SKIP_ADD_RE.search(l):
            found.append({"file": cur, "kind": "added_skip", "detail": l[1:].strip()[:160]})
        elif l.startswith("+") and ONLY_ADD_RE.search(l):
            found.append({"file": cur, "kind": "added_only", "detail": l[1:].strip()[:160]})
    return found


def code_state(root):
    spec = ["--", "."] + [f":(exclude){p}" for p in CODE_EXCLUDES]
    try:
        sha = subprocess.run(["git", "-C", root, "log", "-1", "--format=%H"] + spec, capture_output=True, text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "-C", root, "status", "--porcelain"] + spec, capture_output=True, text=True, check=True).stdout.strip())
        return sha or None, dirty
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None, True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phase", required=True)
    ap.add_argument("--root", default=".")
    ap.add_argument("--results", nargs="*", default=[], help="test-results sidecars; covering tests must have PASSED")
    ap.add_argument("--diff-base", help="commit the phase started from; flags test weakening since then")
    ap.add_argument("--spec-only", action="store_true", help="just write {id: priority} for the phase")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    design = os.path.join(root, "docs", "design", "phases")
    phase_dir = os.path.join(design, str(a.phase))
    spec = spec_rows(phase_dir) if os.path.isdir(phase_dir) else {}
    if a.spec_only:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        json.dump({k: v["priority"] for k, v in spec.items()}, open(a.out, "w"), indent=1)
        print(f"phase {a.phase}: {len(spec)} spec TC IDs")
        return

    # IDs another phase also defines — ambiguous coverage (a phase-1 test "covering" a phase-3 ID)
    dups = {}
    if os.path.isdir(design):
        for other in os.listdir(design):
            if other == str(a.phase) or not os.path.isdir(os.path.join(design, other)):
                continue
            for k in set(spec) & set(spec_rows(os.path.join(design, other))):
                dups.setdefault(k, []).append(other)

    cases, anywhere, ranges = scan_tests(root)
    named = {}
    for c in cases:
        for i in c["ids"]:
            named.setdefault(i, []).append(c)

    res_by_id = {}
    for p in a.results:
        try:
            sc = json.load(open(p))
        except (OSError, ValueError) as e:
            sys.exit(f"tc-inventory: cannot read results {p}: {e}")
        for c in sc.get("cases", []):
            for i in c.get("ids", []):
                res_by_id.setdefault(i, []).append(c.get("verdict", ""))

    out_cases, missing, failing, skipped_only, comment_only = [], [], [], [], []
    for tid, meta in sorted(spec.items()):
        blocking = meta["priority"] in ("HIGH", "MEDIUM")
        live = [c for c in named.get(tid, []) if not c["skipped"]]
        if a.results:
            vs = res_by_id.get(tid, [])
            if any(v in ("FAIL", "FLAKY") for v in vs):
                v = "FAIL"; failing.append(tid)
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
        where = [f"{c['file']}:{c['line']}" for c in live][:5]
        out_cases.append({"name": tid, "ids": [tid], "priority": meta["priority"], "tier": meta["tier"],
                          "verdict": v, "tests": where})

    weak = weakening(root, a.diff_base) if a.diff_base else []
    ack_path = os.path.join(root, "agent_state", "phases", str(a.phase), "test-changes.json")
    acks = json.load(open(ack_path)) if os.path.exists(ack_path) else []
    unack = [w for w in weak if not any(x.get("file") == w["file"] and x.get("kind") == w["kind"] and x.get("reason") for x in acks)]

    blocking_ids = [k for k, m in spec.items() if m["priority"] in ("HIGH", "MEDIUM")]
    failed = len(set(missing) | set(failing)) + len(dups) + len(ranges) + len(unack)
    sha, dirty = code_state(root)
    verdict = "PASS" if spec and failed == 0 else ("BLOCKED" if not spec else "FAIL")
    out = {
        "schema": "sdlc.test-results/v1", "tier": "tc-inventory", "verdict": verdict,
        "total": len(blocking_ids), "passed": len(blocking_ids) - len(set(missing) | set(failing)),
        "failed": failed, "skipped": len(skipped_only), "flaky": 0,
        "code_sha": sha, "dirty": dirty, "mode": "results" if a.results else "source",
        "missing": missing, "failing": failing, "skipped_only": skipped_only, "comment_only": comment_only,
        "duplicate_ids": dups, "range_annotations": ranges, "weakening": weak, "weakening_unacknowledged": unack,
        "cases": out_cases,
        "ts": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(out, open(a.out, "w"), indent=1)
    print(f"tc-inventory phase {a.phase} ({out['mode']}): {verdict} — {out['passed']}/{out['total']} HIGH+MEDIUM covered; "
          f"missing {len(missing)}, failing {len(failing)}, skipped-only {len(skipped_only)}, comment-only {len(comment_only)}, "
          f"duplicate ids {len(dups)}, range annotations {len(ranges)}, unacknowledged test weakening {len(unack)}")
    if not spec:
        print(f"  no TC inventory tables found under docs/design/phases/{a.phase}/")
    sys.exit(0 if verdict == "PASS" else 1)


if __name__ == "__main__":
    main()
