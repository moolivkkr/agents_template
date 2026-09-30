#!/usr/bin/env python3
"""junit-to-sidecar.py — turn JUnit XML into the gate's test-results sidecar (sdlc.test-results/v1).

  junit-to-sidecar.py --tier unit --out agent_state/phases/3/reports/unit_results.json \
      [--command "..."] [--exit-code N] [--env qa] [--base-url URL] [--priorities spec_ids.json] \
      [--quarantine quarantine.json] [--flaky N]  junit.xml [more.xml ...]

Evidence is computed from the runner's output, never typed by an agent:
  - total/passed/failed/skipped from <testcase> elements (failure|error = failed, skipped = skipped)
  - flaky: a test name that both failed and passed within the run (runner retries, e.g. gotestsum
    --rerun-fails, Playwright retries), plus --flaky N when the runner reports it separately
  - cases[].ids: TC IDs found in the test NAME (TC-API-001, or TC_API_001 where names can't hold '-')
  - code_sha/dirty: the last commit touching code, and whether code has uncommitted changes
  - verdict: PASS only if total > 0, failed == 0, flaky == 0 and the command exited 0
See .claude/skills/testing/test-results-sidecar.md for the schema and the gate rules.
"""
import argparse, datetime, json, os, re, subprocess, sys
import xml.etree.ElementTree as ET

TC_RE = re.compile(r"(?<![A-Za-z0-9])TC[-_]([A-Z0-9]+)[-_](\d+)(?![0-9])")   # TC_X_1 inside TestFoo_TC_X_1 too
CODE_EXCLUDES = ["agent_state", "docs", ".claude", "deploy/k8s/overlays"]


def code_state(root="."):
    spec = ["--", "."] + [f":(exclude){p}" for p in CODE_EXCLUDES]
    try:
        sha = subprocess.run(["git", "-C", root, "log", "-1", "--format=%H"] + spec,
                             capture_output=True, text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "-C", root, "status", "--porcelain"] + spec,
                                    capture_output=True, text=True, check=True).stdout.strip())
        return sha or None, dirty
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None, True


def tc_ids(name):
    return sorted({f"TC-{m.group(1)}-{m.group(2)}" for m in TC_RE.finditer(name or "")})


def parse(paths):
    cases = []
    for p in paths:
        try:
            root = ET.parse(p).getroot()
        except (ET.ParseError, OSError) as e:
            sys.exit(f"junit-to-sidecar: cannot read {p}: {e}")
        for tc in root.iter("testcase"):
            name = tc.get("name", "")
            cls = tc.get("classname", "")
            full = f"{cls} {name}".strip() if cls and cls not in name else name
            if tc.find("failure") is not None or tc.find("error") is not None:
                v = "FAIL"
            elif tc.find("skipped") is not None:
                v = "SKIPPED"
            else:
                v = "PASS"
            cases.append({"name": full, "verdict": v, "ids": tc_ids(full)})
    return cases


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("junit", nargs="+")
    ap.add_argument("--tier", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--command", default="")
    ap.add_argument("--exit-code", type=int, default=None)
    ap.add_argument("--env", default="local")
    ap.add_argument("--base-url", default="")
    ap.add_argument("--flaky", type=int, default=0, help="flaky count reported separately by the runner")
    ap.add_argument("--priorities", help="JSON {\"TC-X-1\": \"HIGH\", ...} (from tc-inventory.py --spec-only)")
    ap.add_argument("--quarantine", help="JSON list [{name, issue, expires}] of tests excluded from this run")
    ap.add_argument("--root", default=".")
    a = ap.parse_args()

    raw = parse(a.junit)
    # collapse retries: a name seen more than once keeps its LAST verdict; FAIL-then-PASS = flaky
    by_name, flaky_names = {}, set()
    for c in raw:
        prev = by_name.get(c["name"])
        if prev and prev["verdict"] == "FAIL" and c["verdict"] == "PASS":
            flaky_names.add(c["name"])
        by_name[c["name"]] = c
    cases = list(by_name.values())
    prio = json.load(open(a.priorities)) if a.priorities else {}
    for c in cases:
        ps = [prio.get(i) for i in c["ids"] if prio.get(i)]
        if ps:
            c["priority"] = "HIGH" if "HIGH" in ps else ("MEDIUM" if "MEDIUM" in ps else "LOW")
        if c["name"] in flaky_names:
            c["verdict"] = "FLAKY"

    total = sum(1 for c in cases if c["verdict"] != "SKIPPED")
    failed = sum(1 for c in cases if c["verdict"] == "FAIL")
    skipped = sum(1 for c in cases if c["verdict"] == "SKIPPED")
    flaky = len(flaky_names) + a.flaky
    passed = sum(1 for c in cases if c["verdict"] == "PASS")
    sha, dirty = code_state(a.root)
    if a.exit_code not in (None, 0) and failed == 0:
        verdict = "ERROR"          # runner/compile error with no failing test recorded
    elif total == 0 or failed or flaky:
        verdict = "FAIL"
    else:
        verdict = "PASS"
    out = {
        "schema": "sdlc.test-results/v1", "tier": a.tier, "verdict": verdict,
        "total": total, "passed": passed, "failed": failed, "skipped": skipped, "flaky": flaky,
        "code_sha": sha, "dirty": dirty, "env": a.env, "base_url": a.base_url,
        "command": a.command, "exit_code": a.exit_code, "cases": cases,
        "quarantined": json.load(open(a.quarantine)) if a.quarantine else [],
        "ts": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w") as f:
        json.dump(out, f, indent=1)
    print(f"{a.tier}: {verdict} — total {total}, passed {passed}, failed {failed}, skipped {skipped}, flaky {flaky}"
          f"{'' if sha else ' (no git history: code_sha unknown)'}{' (DIRTY: commit first)' if dirty else ''}")
    sys.exit(0 if verdict == "PASS" else 1)


if __name__ == "__main__":
    main()
