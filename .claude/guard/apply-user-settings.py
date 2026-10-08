#!/usr/bin/env python3
"""apply-user-settings.py — merge the sdlc permission model into ~/.claude/settings.json.

HUMAN-RUN (Claude Code's auto mode rightly refuses to let an agent rewrite its own permissions):

  python3 .claude/guard/apply-user-settings.py --github <your-github-owner> --dry-run   # show the result
  python3 .claude/guard/apply-user-settings.py --github <your-github-owner>             # backup + write

What it changes (everything else in the file is kept):
  permissions.allow   adds a bare "Bash" allow (owner decision 2026-10-07: scripts, find/grep/awk/sed and the
                      rest run without prompts; the sdlc-guard hook and the ask/deny rules below still stop
                      destructive and prod/credential commands). --narrow keeps the old narrow list instead
                      (git, kubectl/helm/crane/trivy, scripts/k8s/*, local docker, localhost curl, builds)
                      and drops the bare "Bash"
  permissions.ask     the ~/.claude/CLAUDE.md "ask first" list, so it holds even if hooks are disabled
  permissions.deny    sudo, context switching, namespace deletion, VM deletion, cloud CLIs, reading
                      the admin kubeconfig / ~/.ssh / ~/.aws, editing ~/.kube, the guard policy, hooks
  permissions.defaultMode = "auto"
  autoMode            environment / allow / hard_deny describing the lab cluster (filled from the
                      guard policy: API server, context, lab hosts, and the aws.projects directories)
  hooks               PreToolUse -> sdlc-guard.sh; SessionStart -> sdlc-guard-env.sh
It does NOT set disableBypassPermissionsMode (that lives in the optional managed settings).
Revert: the backup path is printed; `cp <backup> ~/.claude/settings.json`.
"""
import argparse, json, os, shutil, sys, time

H = os.path.expanduser("~")
SETTINGS = os.path.join(H, ".claude", "settings.json")
POLICY = os.environ.get("SDLC_GUARD_POLICY", os.path.join(H, ".config", "sdlc-guard", "policy.json"))

ALLOW = [
    "Bash(git status*)", "Bash(git diff*)", "Bash(git log*)", "Bash(git show*)", "Bash(git add *)", "Bash(git commit *)",
    "Bash(git switch *)", "Bash(git checkout -b *)", "Bash(git branch)", "Bash(git branch -a*)", "Bash(git fetch*)",
    "Bash(git stash)", "Bash(git stash pop)", "Bash(git stash list)", "Bash(git rev-parse *)", "Bash(git tag *)",
    "Bash(kubectl *)", "Bash(helm *)", "Bash(kubeconform *)", "Bash(crane *)", "Bash(trivy *)",
    "Bash(limactl list*)", "Bash(limactl start sdlc-agent)", "Bash(limactl stop sdlc-agent)", "Bash(limactl shell sdlc-agent *)",
    "Bash(scripts/k8s/*)", "Bash(./scripts/k8s/*)", "Bash(bash scripts/k8s/*)",
    "Bash(docker build *)", "Bash(docker compose *)", "Bash(docker ps*)", "Bash(docker logs *)", "Bash(docker images*)",
    "Bash(docker inspect *)", "Bash(docker save *)", "Bash(docker push localhost:5001/*)",
    "Bash(curl -s* http://localhost:*)", "Bash(curl -s* http://127.0.0.1:*)", "Bash(curl -s* http://*.localhost:*)",
    "Bash(npm ci*)", "Bash(npm install*)", "Bash(npm test*)", "Bash(npm run *)", "Bash(npx playwright *)",
    "Bash(pnpm install*)", "Bash(pnpm test*)", "Bash(pnpm run *)", "Bash(yarn install*)", "Bash(yarn test*)",
    "Bash(pip install *)", "Bash(pip3 install *)", "Bash(uv sync*)", "Bash(uv pip install *)", "Bash(uv run pytest*)",
    "Bash(go mod *)", "Bash(go get *)", "Bash(go build *)", "Bash(go test *)", "Bash(go vet *)",
    "Bash(cargo build*)", "Bash(cargo test*)", "Bash(cargo fetch*)", "Bash(brew install *)",
    "Bash(pytest*)", "Bash(jq *)",
]
ASK = [
    "Bash(git reset --hard*)", "Bash(git clean -f*)", "Bash(git checkout -- *)", "Bash(git restore *)",
    "Bash(git stash drop*)", "Bash(git stash clear*)", "Bash(git branch -D *)",
    "Bash(docker compose down -v*)", "Bash(docker compose * down -v*)", "Bash(docker compose down --volumes*)",
    "Bash(docker volume rm *)", "Bash(docker volume prune*)", "Bash(docker system prune*)",
    "Bash(dropdb *)", "Bash(chmod 777 *)", "Bash(chmod -R 777 *)",
    "Bash(terraform apply*)", "Bash(terraform destroy*)", "Bash(npm publish*)",
    "Bash(helm uninstall *)", "Bash(helm delete *)",
]
# prompted under --narrow only; in the default broad mode the guard checks the remote command instead
NARROW_ASK = ["Bash(ssh *)", "Bash(scp *)"]
DENY = [
    "Bash(sudo *)", "Bash(kubectx*)", "Bash(kubens*)",
    "Bash(kubectl config use-context *)", "Bash(kubectl config set-context *)", "Bash(kubectl config set-cluster *)",
    "Bash(kubectl config set-credentials *)", "Bash(kubectl delete namespace *)", "Bash(kubectl delete ns *)",
    "Bash(limactl delete *)", "Bash(limactl factory-reset *)", "Bash(limactl unprotect *)",
    "Bash(gcloud *)", "Bash(az *)", "Bash(eksctl *)", "Bash(doctl *)", "Bash(aws-vault *)", "Bash(saml2aws *)",
    "Read(~/.kube/sdlc-lab-admin.yaml)", "Read(~/.kube/config)", "Read(~/.ssh/**)", "Read(~/.aws/**)",
    "Edit(~/.kube/**)", "Edit(~/.config/sdlc-guard/**)", "Edit(~/.claude/hooks/**)",
]


def auto_mode(github, server, context, lab_hosts, aws_projects=(), aws_anywhere=False):
    hosts = ", ".join(lab_hosts) or "none"
    am = {
        "environment": [
            "$defaults",
            "Organization: solo developer building products with the startup-agents SDLC framework; agents run unattended for hours.",
            f"Host containment: ordinary macOS developer machine. Non-prod infrastructure the agent operates: Docker Desktop (compose stacks) and a disposable k3s lab cluster in Lima VMs (sdlc-agent on this Mac; the server VM may be on another Mac reachable over a private link). API {server}, kube context '{context}', kubeconfig ~/.kube/sdlc-lab.json, identity ServiceAccount sdlc-system/sdlc-agent with admin only in namespaces named <app>-dev and <app>-qa.",
            "Protected deployment namespaces / environments: every staging or production environment in any cloud or cluster, and any kube context, namespace, host, database or bucket whose name contains prod, production, prd or live. The <app>-dev and <app>-qa namespaces of the lab cluster are NOT protected; they are rebuilt from git.",
            "Sensitive remote targets: production and staging hosts, clusters and databases. Local compose containers, the Lima VMs sdlc-agent/sdlc-server and pods in <app>-dev/<app>-qa are the agent's own development environments.",
            "Protected IaC scopes: cloud IAM, cloud networking, DNS, TLS certificates, cluster RBAC, namespaces and ResourceQuotas (changed only by the human bootstrap scripts cluster-up.sh / app-namespaces.sh). Namespaced Deployments, StatefulSets, Services, Ingresses, ConfigMaps, Secrets, PVCs and Jobs applied by a project's scripts/k8s/*.sh to <app>-dev/<app>-qa are ordinary application deploys.",
            f"Trusted internal domains: localhost, 127.0.0.1, *.localhost, host.lima.internal, 10.0.2.2 (Android emulator alias for this Mac), and the lab cluster hosts {hosts}.",
            "Key internal services: lab image registry at localhost:5001; app ingress at http://<app>-<env>.localhost:18080; LocalStack at localhost:4566 when a project uses it.",
            f"Source control: github.com/{github} and the repos under it.",
        ],
        "allow": [
            "$defaults",
            "Local non-prod deploys: building images, pushing them to localhost:5001, and running a project's scripts/k8s/deploy.sh, seed.sh, smoke.sh and env-reset.sh (which apply kustomize overlays, run migration/seed Jobs, and wipe and re-seed <app>-dev/<app>-qa) is allowed.",
            "Package downloads for builds and tests (npm, pnpm, yarn, pip, uv, go modules, cargo, Homebrew formulae for dev tools) are allowed.",
            "Disposable environments: deleting, restarting, scaling or resetting workloads, jobs, PVCs and databases in <app>-dev/<app>-qa of the lab cluster and in local compose stacks via the project's reset scripts is allowed.",
            "Scripts and code search: running any project or scratch script (bash/sh/zsh, ./x.sh, python, node, make targets) and read/search tools (find, grep, rg, awk, sed without -i on protected files, xargs, jq, yq) is allowed.",
            "Kubernetes management in <app>-dev/<app>-qa of the lab cluster: kubectl/helm create, apply, patch, set image, scale, rollout restart/undo/pause/resume, exec, port-forward, and deleting pods or jobs is allowed. Deleting other resources and helm uninstall need the owner (the guard prompts).",
        ],
        "soft_deny": ["$defaults"],
        "hard_deny": [
            "$defaults",
            "Never deploy to, run migrations against, read from, exec into, or port-forward to any staging or production environment, or any kube context, cluster, namespace, host, database or bucket whose name contains prod, production, prd or live. A human does these outside Claude.",
            "Never read, copy, print or modify credentials: the admin kubeconfig ~/.kube/sdlc-lab-admin.yaml, ~/.ssh, cloud credentials, ~/.claude/settings*.json, ~/.claude/hooks/, managed settings, or ~/.config/sdlc-guard/.",
        ],
    }
    if aws_projects:
        # mirrors the guard policy's aws.projects (docs/PERMISSIONS_GUIDE.md "AWS for your projects")
        where = ", ".join(aws_projects)
        am["environment"].append(
            f"Owner's AWS projects: {where}. Inside these directories the owner has approved the real AWS CLI in any region: "
            "EC2 instances, security groups and their ingress rules, tags, S3 objects and buckets, autoscaling and the "
            "like are the project's own disposable inference infrastructure, launched and terminated routinely to iterate "
            "and test. IAM, Organizations, account and identity-center changes, and EKS, still need the owner.")
        am["allow"].append(
            f"AWS in the owner's projects ({where}): running the project's infra scripts and aws CLI commands that create, "
            "describe, tag, modify or delete EC2 instances, security groups, S3 objects/buckets and other resources, in any "
            "region, is allowed (the sdlc-guard hook enforces the project scope, profile pins and credential rules).")
    if aws_anywhere:
        am["environment"].append(
            "AWS (owner decision 2026-10-07): agents manage the owner's AWS services from any directory as the owner "
            "instructs: create, describe, update, tag, deploy and scale resources in any service and region. Deleting, "
            "terminating or purging resources, IAM/Organizations/identity changes and EKS changes need the owner (the "
            "sdlc-guard hook prompts for them); credential-printing calls are always denied.")
        am["allow"].append(
            "AWS anywhere: aws CLI commands that create, describe, update, tag, deploy or scale resources in any service "
            "and region are allowed (the sdlc-guard hook prompts for destructive and IAM calls and denies credential dumps).")
    return am


def add(lst, items):
    for i in items:
        if i not in lst:
            lst.append(i)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--github", required=True, help="GitHub owner your repos live under (for autoMode)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--narrow", action="store_true", help="old behaviour: narrow Bash allow list, no bare \"Bash\"")
    a = ap.parse_args()

    try:
        pol = json.load(open(POLICY))
        ctx, spec = next(iter(pol["kube"]["contexts"].items()))
        server = spec["server"]
        lab = [h for h in pol.get("local_hosts", []) if h[:1].isdigit() and not h.startswith(("127.", "0.", "10.0.2.2"))]
        aws_projects = [str(p.get("path")) for p in (pol.get("aws") or {}).get("projects", []) if p.get("path")]
        aws_anywhere = bool((pol.get("aws") or {}).get("anywhere"))
    except Exception as e:
        sys.exit(f"read the guard policy first ({POLICY}): {e} — run cluster-up.sh / make-policy.py")
    for f in ("sdlc-guard.sh", "sdlc-guard-env.sh"):
        if not os.path.exists(os.path.join(H, ".claude", "hooks", f)):
            sys.exit(f"~/.claude/hooks/{f} missing — run ./install.sh --guard first")

    s = json.load(open(SETTINGS)) if os.path.exists(SETTINGS) else {}
    perm = s.setdefault("permissions", {})
    if a.narrow:
        perm["allow"] = [x for x in perm.get("allow", []) if x != "Bash"]
        add(perm["allow"], ALLOW)
        add(perm.setdefault("ask", []), ASK + NARROW_ASK)
    else:
        add(perm.setdefault("allow", []), ["Bash"] + ALLOW)
        perm["ask"] = [x for x in perm.get("ask", []) if x not in NARROW_ASK]
        add(perm["ask"], ASK)
    add(perm.setdefault("deny", []), DENY)
    perm["defaultMode"] = "auto"
    s["autoMode"] = auto_mode(a.github, server, ctx, lab, aws_projects, aws_anywhere)
    hooks = s.setdefault("hooks", {})
    pre = hooks.setdefault("PreToolUse", [])
    if not any("sdlc-guard.sh" in json.dumps(e) for e in pre):
        pre.append({"matcher": "Bash|Monitor|Skill|Write|Edit|MultiEdit|NotebookEdit|Read|Grep|Glob",
                    "hooks": [{"type": "command", "command": f"{H}/.claude/hooks/sdlc-guard.sh", "timeout": 10}]})
    ss = hooks.setdefault("SessionStart", [])
    if not any("sdlc-guard-env.sh" in json.dumps(e) for e in ss):
        ss.append({"hooks": [{"type": "command", "command": f"{H}/.claude/hooks/sdlc-guard-env.sh"}]})

    text = json.dumps(s, indent=2) + "\n"
    if a.dry_run:
        sys.stdout.write(text)
        return
    if os.path.exists(SETTINGS):
        bak = f"{SETTINGS}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
        shutil.copy2(SETTINGS, bak)
        print(f"backup: {bak}")
    tmp = SETTINGS + ".tmp"
    with open(tmp, "w") as f:
        f.write(text)
    os.replace(tmp, SETTINGS)
    print(f"wrote {SETTINGS}: allow {len(perm['allow'])}, ask {len(perm['ask'])}, deny {len(perm['deny'])}, "
          f"defaultMode auto, hooks {', '.join(hooks)}")
    print("verify: claude doctor; claude auto-mode config; then start a NEW session (hooks load at startup)")


if __name__ == "__main__":
    main()
