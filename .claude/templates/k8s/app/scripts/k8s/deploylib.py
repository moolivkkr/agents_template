#!/usr/bin/env python3
"""deploylib.py — structured state for scripts/k8s/*.sh (digest pinning, deploy history, evidence).

  set-images  <kustomization.yaml> name=repo@sha256:... ...   rewrite the managed images block
  get-images  <kustomization.yaml>                             print pinned name=repo@digest lines
  pick        <history.jsonl> [--differs name=ref ...]         print the newest HEALTHY entry (JSON);
                                                               with --differs, the newest HEALTHY one
                                                               whose images differ (= rollback target)
  keep        <history.jsonl> [--n N]                          print the image refs of the newest N HEALTHY
                                                               deploys (registry-prune.sh keeps these)
  stuck       [--digests sha256:...]  < kubectl get pods -o json
                                                               print "pod/container: reason: message" for
                                                               containers stuck in a state that never
                                                               resolves (only pods running the given digests)
  record      --root R --env E --ns NS --sha S --url U --verdict V --steps JSON --smoke JSON
              [--phase N] [--images name=ref ...]              append history, write the status marker
                                                               and (with --phase) the gate sidecar
Evidence is written by code, never by an agent's prose:
  agent_state/deploy/<env>/history.jsonl         one line per deploy (promotion and rollback read it)
  agent_state/deploy/last-deploy-status.json     marker /accept and /status read (status HEALTHY|DEGRADED|FAILED)
  agent_state/phases/<N>/reports/deploy_<env>.{json,md} + an execution.jsonl line (agent deploy_<env>):
                                                 the sdlc.test-results/v1 evidence verify-gate.sh reads
"""
import argparse, datetime, json, os, re, sys

BLOCK = re.compile(r"(# BEGIN images[^\n]*\n)(.*?)(# END images)", re.S)


def pairs(items):
    out = {}
    for it in items or []:
        name, ref = it.split("=", 1)
        if "@sha256:" not in ref:
            sys.exit(f"deploylib: {it} is not digest-pinned (repo@sha256:...)")
        out[name] = ref
    return out


def set_images(path, items):
    imgs = pairs(items)
    s = open(path).read()
    lines = "".join(f"- {{name: {n}, newName: {r.split('@')[0]}, digest: {r.split('@')[1]}}}\n"
                    for n, r in sorted(imgs.items()))
    new, n = BLOCK.subn(lambda m: m.group(1) + "images:\n" + lines + m.group(3), s)
    if n != 1:
        sys.exit(f"deploylib: {path}: '# BEGIN images' / '# END images' markers not found")
    open(path, "w").write(new)


def get_images(path):
    m = BLOCK.search(open(path).read())
    if not m:
        sys.exit(f"deploylib: {path}: images markers not found")
    for name, repo, digest in re.findall(r"name:\s*([\w.-]+),\s*newName:\s*([^,}\s]+),\s*digest:\s*(sha256:[0-9a-f]+)", m.group(2)):
        print(f"{name}={repo}@{digest}")


def pick(path, differs):
    try:
        entries = [json.loads(l) for l in open(path) if l.strip()]
    except FileNotFoundError:
        entries = []
    current = pairs(differs) if differs else None
    for e in reversed(entries):
        if e.get("verdict") != "HEALTHY":
            continue
        if current is not None and e.get("images") == current:
            continue
        print(json.dumps(e))
        return
    sys.exit(1)


def keep(path, n):
    try:
        entries = [json.loads(l) for l in open(path) if l.strip()]
    except FileNotFoundError:
        return
    for e in [e for e in entries if e.get("verdict") == "HEALTHY"][-n:]:
        for ref in e.get("images", {}).values():
            print(ref)


STUCK = {"CreateContainerConfigError", "CreateContainerError", "ErrImagePull", "ImagePullBackOff",
         "InvalidImageName", "CrashLoopBackOff", "ErrImageNeverPull"}


def stuck(digests):
    pods = json.load(sys.stdin).get("items", [])
    for pod in pods:
        images = {c["name"]: c.get("image", "") for c in pod["spec"].get("containers", [])}
        for cs in pod.get("status", {}).get("containerStatuses", []) or []:
            w = (cs.get("state") or {}).get("waiting") or {}
            if w.get("reason") in STUCK and (not digests or any(d in images.get(cs["name"], "") for d in digests)):
                print(f"{pod['metadata']['name']}/{cs['name']}: {w['reason']}: {w.get('message', '')[:300]}")
                return


def record(a):
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    steps, smoke = json.loads(a.steps), json.loads(a.smoke)
    dirty = str(a.dirty).lower() == "true"
    entry = {"ts": now, "env": a.env, "namespace": a.ns, "git_sha": a.sha, "code_sha": a.code_sha, "dirty": dirty,
             "url": a.url, "images": pairs(a.images), "mode": a.mode, "steps": steps, "smoke": smoke,
             "verdict": a.verdict}
    state = os.path.join(a.root, "agent_state", "deploy")
    os.makedirs(os.path.join(state, a.env), exist_ok=True)
    with open(os.path.join(state, a.env, "history.jsonl"), "a") as f:
        f.write(json.dumps(entry) + "\n")
    failing = [k for k, v in steps.items() if v != "ok"] + [x["path"] for x in smoke.get("failures", [])]
    with open(os.path.join(state, "last-deploy-status.json"), "w") as f:
        json.dump({"target": a.env, "status": a.verdict, "ts": now, "namespace": a.ns, "git_sha": a.sha,
                   "code_sha": a.code_sha, "url": a.url, "digests": entry["images"], "failing": ", ".join(failing)},
                  f, indent=1)
    if a.phase:
        # Gate evidence (sdlc.test-results/v1) + an execution.jsonl line, so verify-gate.sh actually reads it:
        # agent "deploy_<env>", report reports/deploy_<env>.md, sidecar reports/deploy_<env>.json.
        pdir = os.path.join(a.root, "agent_state", "phases", str(a.phase))
        rep = os.path.join(pdir, "reports")
        os.makedirs(rep, exist_ok=True)
        cases = [{"name": f"step:{k}", "verdict": "PASS" if v == "ok" else "FAIL", "priority": "HIGH"} for k, v in steps.items()]
        cases += [{"name": f"smoke:{x['path']}", "verdict": "FAIL", "priority": "HIGH", "detail": x.get("got", "")}
                  for x in smoke.get("failures", [])]
        total = len(steps) + smoke.get("total", 0)
        failed = sum(1 for v in steps.values() if v != "ok") + smoke.get("failed", 0)
        with open(os.path.join(rep, f"deploy_{a.env}.json"), "w") as f:
            json.dump({"schema": "sdlc.test-results/v1", "tier": "deploy", "verdict": "PASS" if a.verdict == "HEALTHY" else "FAIL",
                       "deploy_status": a.verdict, "total": total, "passed": total - failed, "failed": failed,
                       "skipped": 0, "flaky": 0, "code_sha": a.code_sha, "dirty": dirty, "env": a.env,
                       "base_url": a.url, "namespace": a.ns, "digests": entry["images"], "mode": a.mode,
                       "cases": cases, "ts": now}, f, indent=1)
        with open(os.path.join(rep, f"deploy_{a.env}.md"), "w") as f:
            f.write(f"# deploy_{a.env} — {a.verdict}\n\n- namespace: {a.ns}\n- url: {a.url}\n- mode: {a.mode}\n"
                    f"- code_sha: {a.code_sha}\n- images: {json.dumps(entry['images'])}\n- failing: {', '.join(failing) or 'none'}\n")
        with open(os.path.join(pdir, "execution.jsonl"), "a") as f:
            f.write(json.dumps({"agent": f"deploy_{a.env}", "phase": int(a.phase) if str(a.phase).isdigit() else a.phase,
                                "status": "completed" if a.verdict == "HEALTHY" else "failed",
                                "report": f"agent_state/phases/{a.phase}/reports/deploy_{a.env}.md", "ts": now}) + "\n")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("set-images"); p.add_argument("path"); p.add_argument("images", nargs="*")
    p = sub.add_parser("get-images"); p.add_argument("path")
    p = sub.add_parser("pick"); p.add_argument("history"); p.add_argument("--differs", nargs="*")
    p = sub.add_parser("keep"); p.add_argument("history"); p.add_argument("--n", type=int, default=5)
    p = sub.add_parser("stuck"); p.add_argument("--digests", nargs="*")
    p = sub.add_parser("record")
    for k in ("root", "env", "ns", "sha", "url", "verdict", "steps", "smoke"):
        p.add_argument("--" + k, required=True)
    p.add_argument("--mode", default="deploy"); p.add_argument("--phase"); p.add_argument("--images", nargs="*")
    p.add_argument("--code-sha", default=""); p.add_argument("--dirty", default="false")
    a = ap.parse_args()
    if a.cmd == "set-images": set_images(a.path, a.images)
    elif a.cmd == "get-images": get_images(a.path)
    elif a.cmd == "pick": pick(a.history, a.differs)
    elif a.cmd == "keep": keep(a.history, a.n)
    elif a.cmd == "stuck": stuck(a.digests)
    else: record(a)


if __name__ == "__main__":
    main()
