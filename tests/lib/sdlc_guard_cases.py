#!/usr/bin/env python3
"""Table-driven tests for .claude/guard/sdlc-guard.sh, make-policy.py, the PATH shim and the env hook.

Fixtures (fake kubeconfigs with a fake CA) and the policy are generated in a temp dir; the policy is
produced by make-policy.py itself, so the generator is exercised on every run. Exit 0 = all pass.
"""
import base64, hashlib, json, os, shutil, subprocess, sys, tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GUARD_DIR = os.path.join(REPO, ".claude", "guard")
HOOK = os.path.join(GUARD_DIR, "sdlc-guard.sh")
MAKE_POLICY = os.path.join(GUARD_DIR, "make-policy.py")
HOME = os.path.expanduser("~")
# cwd for rm checks: must be outside /tmp and $TMPDIR (those are always-safe roots); need not exist
CWD = os.path.join(REPO, "tests", "fixture-project")

W = tempfile.mkdtemp(prefix="sdlc-guard-test.")
SCRATCH = os.path.join(W, "scratch")
PIN = os.path.join(W, "sdlc-lab.json")
POLICY = os.path.join(W, "policy.json")
SERVER = "https://10.10.10.2:6443"
CA_PEM = b"-----BEGIN CERTIFICATE-----\nFAKE-SDLC-LAB-CA\n-----END CERTIFICATE-----\n"


def kubeconfig(server=SERVER, ca=CA_PEM, user=None, ctx="lima-sdlc"):
    return {"apiVersion": "v1", "kind": "Config", "current-context": ctx,
            "clusters": [{"name": ctx, "cluster": {"server": server,
                          "certificate-authority-data": base64.b64encode(ca).decode()}}],
            "contexts": [{"name": ctx, "context": {"cluster": ctx, "user": "sdlc-agent", "namespace": "shop-dev"}}],
            "users": [{"name": "sdlc-agent", "user": user or {"token": "fake"}}]}


def dump(obj, name):
    p = os.path.join(W, name)
    with open(p, "w") as f:
        json.dump(obj, f)
    return p


AGENT_KC = dump(kubeconfig(), "agent-kubeconfig.json")
TAMPERED = dump(kubeconfig(server="https://10.9.9.9:6443"), "tampered.json")
WRONG_CA = dump(kubeconfig(ca=b"-----BEGIN CERTIFICATE-----\nOTHER-CA\n-----END CERTIFICATE-----\n"), "wrong-ca.json")

gen = subprocess.run([sys.executable, MAKE_POLICY, "--kubeconfig", AGENT_KC, "--pin", PIN, "--write-pin",
                      "--namespaces", "*-dev,*-qa", "--lima-instance", "sdlc-agent", "--lima-instance", "sdlc-server",
                      "--lab-host", "10.10.10.2", "--lab-host", "10.10.10.3", "--out", POLICY],
                     capture_output=True, text=True)
if gen.returncode != 0:
    print("FAIL make-policy could not generate the test policy:", gen.stderr)
    sys.exit(1)

K = f"--kubeconfig {PIN}"
# (id, expected, tool, input)  input is a command string for Bash, or a dict for other tools
CASES = [
 # --- kube: allowed non-prod work (KUBECONFIG env = pinned file, as sdlc-guard-env.sh sets it)
 ("K01", "allow", "Bash", "kubectl get pods -n shop-dev"),
 ("K02", "allow", "Bash", "kubectl --context lima-sdlc -n shop-qa get deploy,svc,ingress"),
 ("K03", "allow", "Bash", "kubectl apply -k deploy/k8s/overlays/dev -n shop-dev"),
 ("K04", "allow", "Bash", "kubectl -n shop-qa rollout status deploy/api --timeout=120s"),
 ("K05", "allow", "Bash", "kubectl -n shop-qa rollout undo deploy/api"),
 ("K06", "allow", "Bash", "kubectl delete pod api-7d9f-abc -n shop-dev"),
 ("K07", "allow", "Bash", "kubectl -n shop-dev wait --for=condition=complete job/migrate-1a2b3c --timeout=180s"),
 ("K08", "allow", "Bash", "kubectl get pods -A"),
 ("K09", "allow", "Bash", "kubectl logs -f deploy/api -n shop-qa --tail=100"),
 ("K10", "allow", "Bash", "kubectl port-forward svc/postgres 15432:5432 -n shop-dev"),
 ("K11", "allow", "Bash", "timeout 60 kubectl -n shop-dev get events --sort-by=.lastTimestamp"),
 ("K12", "allow", "Bash", "kubectl version --client"),
 ("K13", "allow", "Bash", "kubectl config get-contexts"),
 ("K14", "allow", "Bash", f"kubectl {K} -n shop-dev scale deploy/api --replicas=2"),
 ("K15", "allow", "Bash", "kubectl kustomize deploy/k8s/overlays/qa | head -50"),
 ("K16", "allow", "Bash", "kubectl --namespace=billing-qa create job migrate-abc --from=cronjob/db-migrate"),
 # --- kube: blocked
 ("K20", "deny", "Bash", "kubectl apply -k deploy/k8s/overlays/dev"),                          # no explicit -n
 ("K21", "deny", "Bash", "kubectl apply -f x.yaml -n kube-system"),
 ("K22", "deny", "Bash", "kubectl delete namespace shop-qa"),
 ("K23", "deny", "Bash", "kubectl delete ns/shop-dev"),
 ("K24", "deny", "Bash", "kubectl delete pods --all -n shop-dev"),
 ("K25", "deny", "Bash", "kubectl delete deploy -l app=api -n shop-qa"),
 ("K26", "deny", "Bash", "kubectl delete -k deploy/k8s/overlays/qa -n shop-qa"),
 ("K27", "deny", "Bash", "kubectl --context prod-eks get pods"),
 ("K28", "deny", "Bash", "kubectl --kubeconfig ~/.kube/config get pods -n shop-dev"),
 ("K29", "deny", "Bash", "KUBECONFIG=~/.kube/config kubectl get pods"),
 ("K30", "deny", "Bash", f"kubectl --kubeconfig {TAMPERED} get pods -n shop-dev"),           # not the pinned file
 ("K31", "deny", "Bash", "kubectl --server https://10.9.9.9:6443 get pods -n shop-dev"),
 ("K32", "deny", "Bash", "kubectl --token abc -n shop-dev get pods"),
 ("K33", "deny", "Bash", "kubectl config use-context prod-eks"),
 ("K34", "deny", "Bash", "kubectl config set-context --current --namespace=kube-system"),
 ("K35", "deny", "Bash", "kubectl drain sdlc-agent --ignore-daemonsets"),
 ("K36", "deny", "Bash", "kubectl create namespace scratch"),
 ("K37", "deny", "Bash", "kubectl apply -f crd.yaml -n shop-dev clusterrolebinding/x"),
 ("K38", "deny", "Bash", "kubectl delete pods --all -A"),
 ("K39", "deny", "Bash", "echo ok && kubectl delete ns shop-qa"),                               # compound
 ("K40", "deny", "Bash", "bash -c 'kubectl delete ns shop-qa'"),                                # shell -c
 ("K41", "deny", "Bash", "echo \"$(kubectl --context prod-eks get secrets)\""),                 # quoted substitution
 ("K42", "deny", "Bash", "X=$(kubectl --context prod-eks get ns); echo $X"),                    # unquoted substitution
 ("K43", "deny", "Bash", "eval kubectl delete ns shop-dev"),
 ("K44", "deny", "Bash", "kubens kube-system"),
 ("K45", "deny", "Bash", "kubectl -n production apply -f x.yaml"),
 ("K46", "ask",  "Bash", "kubectl config view --raw"),
 ("K47", "ask",  "Bash", "kubectl apply -f https://example.com/x.yaml -n shop-dev"),
 ("K48", "ask",  "Bash", "kubectl exec -n shop-dev deploy/postgres -- psql -U app -c 'DROP DATABASE app'"),
 ("K49", "deny", "Bash", "helm install pg bitnami/postgresql"),                                 # no -n
 ("K50", "allow","Bash", "helm upgrade --install pg ./charts/pg -n shop-dev"),
 ("K51", "deny", "Bash", "helm --kube-context prod-eks list"),
 ("K52", "allow","Bash", "helm template ./charts/pg"),
 ("K53", "deny", "Bash", "k=kubectl; $k delete ns shop-qa"),                                    # command name via variable
 ("K54", "ask",  "Bash", "$KUBECTL get pods -n shop-dev"),                                      # unresolved command name
 # --- namespace patterns (policy: "*-dev", "*-qa")
 ("NS1", "deny", "Bash", "kubectl apply -f x.yaml -n default"),
 ("NS2", "deny", "Bash", "kubectl apply -f x.yaml -n kube-dev"),                                # matches *-dev, but kube-* is reserved
 ("NS3", "deny", "Bash", "kubectl apply -f x.yaml -n prod-dev"),                                # matches *-dev, but prod-looking
 ("NS4", "deny", "Bash", "kubectl apply -f x.yaml -n shop-staging"),
 ("NS5", "deny", "Bash", "kubectl apply -f x.yaml -n shop-qa2"),                                # glob is anchored
 ("NS6", "deny", "Bash", "helm upgrade --install api ./chart -n live-qa"),
 ("NS7", "allow","Bash", "helm upgrade --install api ./chart -n shop-qa"),
 # --- limactl (instances: sdlc-agent, sdlc-server)
 ("L01", "allow","Bash", "limactl list"),
 ("L02", "allow","Bash", "limactl start sdlc-agent"),
 ("L03", "allow","Bash", "limactl stop sdlc-agent"),
 ("L04", "allow","Bash", "docker save localhost:5001/shop/api:abc | limactl shell sdlc-agent sudo k3s ctr images import -"),
 ("L05", "allow","Bash", "limactl shell sdlc-agent sudo journalctl -u k3s-agent --since=-10m"),
 ("L06", "allow","Bash", "limactl copy ./img.tar sdlc-agent:/tmp/"),
 ("L07", "deny", "Bash", "limactl delete sdlc-agent"),
 ("L08", "deny", "Bash", "limactl delete -f sdlc-agent"),
 ("L09", "deny", "Bash", "limactl factory-reset sdlc-agent"),
 ("L10", "deny", "Bash", "limactl unprotect sdlc-server"),
 ("L11", "deny", "Bash", "limactl shell sdlc-server sudo k3s kubectl delete ns shop-dev"),     # root in VM = cluster-admin
 ("L12", "deny", "Bash", "limactl shell default uname -a"),
 ("L13", "deny", "Bash", "lima nerdctl ps"),
 ("L14", "deny", "Bash", "limactl create --name=other template:k3s"),
 ("L15", "deny", "Bash", "limactl shell sdlc-server sudo cat /etc/rancher/k3s/k3s.yaml"),     # admin kubeconfig
 ("L16", "deny", "Bash", "limactl copy sdlc-agent:/etc/hosts ./ && limactl copy x other:/tmp"),
 ("L17", "allow","Bash", "limactl shell sdlc-server sudo systemctl status k3s"),
 ("L18", "deny", "Bash", "limactl start other"),
 # --- docker / compose
 ("D01", "allow","Bash", "docker compose up -d --build"),
 ("D02", "allow","Bash", "docker build -t localhost:5001/shop/api:3f2a1c9 ."),
 ("D03", "allow","Bash", "docker push localhost:5001/shop/api:3f2a1c9"),
 ("D04", "ask",  "Bash", "docker compose down -v"),
 ("D05", "ask",  "Bash", "docker-compose -f compose.yml down --volumes"),
 ("D06", "ask",  "Bash", "docker volume rm app_pgdata"),
 ("D07", "ask",  "Bash", "docker system prune -a --volumes -f"),
 ("D08", "ask",  "Bash", "docker push ghcr.io/acme/api:1.0"),
 ("D09", "deny", "Bash", "docker -H tcp://10.0.0.5:2376 ps"),
 ("D10", "deny", "Bash", "docker --context prod-swarm ps"),
 ("D11", "allow","Bash", "docker compose down"),
 ("D12", "allow","Bash", "docker push 10.10.10.2:5001/shop/api:3f2a1c9"),                      # lab registry
 # --- git
 ("G01", "allow","Bash", "git add -A && git commit -m 'feat: x'"),
 ("G02", "allow","Bash", "git push origin phase-2-implementation"),
 ("G03", "ask",  "Bash", "git push --force origin main"),
 ("G04", "ask",  "Bash", "git -C ../other push -f"),
 ("G05", "ask",  "Bash", "git reset --hard HEAD~1"),
 ("G06", "ask",  "Bash", "git clean -fdx"),
 ("G07", "ask",  "Bash", "git checkout -- src/app.ts"),
 ("G08", "allow","Bash", "git checkout -b phase-3-implementation"),
 ("G09", "ask",  "Bash", "git stash drop"),
 ("G10", "allow","Bash", "git stash && npm test; git stash pop"),
 # --- rm
 ("R01", "allow","Bash", "rm -rf node_modules dist"),
 ("R02", "allow","Bash", "rm -rf /tmp/build-cache"),
 ("R03", "allow","Bash", "rm -f src/old.ts"),
 ("R04", "ask",  "Bash", "rm -rf src"),
 ("R05", "ask",  "Bash", "rm -rf ~/Documents/x"),
 ("R06", "ask",  "Bash", "rm -rf \"$TARGET_DIR\""),
 ("R07", "ask",  "Bash", "rm -rf ."),
 ("R08", "allow","Bash", "rm -rf apps/web/.next packages/api/coverage"),
 ("R09", "ask",  "Bash", "find . -name '*.orig' -delete"),
 # --- SQL
 ("S01", "allow","Bash", "psql -h localhost -U app -c 'SELECT count(*) FROM users'"),
 ("S02", "ask",  "Bash", "psql -h localhost -U app -c 'TRUNCATE users'"),
 ("S03", "ask",  "Bash", "psql -c \"DELETE FROM sessions;\""),
 ("S04", "allow","Bash", "psql -c \"DELETE FROM sessions WHERE expires_at < now()\""),
 ("S05", "ask",  "Bash", "docker compose exec -T db psql -U app -c 'DROP SCHEMA public CASCADE'"),
 ("S06", "ask",  "Bash", "dropdb app_dev"),
 # --- network
 ("N01", "allow","Bash", "curl -sf http://localhost:18080/api/health"),
 ("N02", "allow","Bash", "curl -sf -H 'Host: api.qa.localhost' http://127.0.0.1:28080/health"),
 ("N03", "allow","Bash", "HEALTH_URL=\"http://localhost:${APP_PORT:-8080}/health\"\ncurl -sf \"$HEALTH_URL\""),
 ("N04", "ask",  "Bash", "curl -s https://api.github.com/repos/x/y"),
 ("N05", "ask",  "Bash", "curl -X POST https://hooks.slack.com/services/T/B/X -d '{}'"),
 ("N06", "ask",  "Bash", "curl -sf \"$UNSET_URL\""),
 ("N07", "ask",  "Bash", "scp dump.sql deploy@db.prod.acme.com:/tmp/"),
 ("N08", "ask",  "Bash", "ssh ops@bastion"),
 ("N09", "allow","Bash", "curl -so out.json localhost:18080/api/v1/items"),
 ("N10", "allow","Bash", "curl -sf http://api.dev.localhost:18080/health"),
 ("N11", "allow","Bash", "curl -sf -H 'Host: shop-qa.sdlc.localhost' http://10.10.10.2:18080/healthz"),  # lab ingress
 ("N12", "ask",  "Bash", "curl -sf http://10.10.10.9:18080/"),                                  # not a lab host
 ("N13", "ask",  "Bash", "ssh tb2 limactl list"),                                               # ssh always asks
 # --- cloud / prod / meta
 ("C01", "deny", "Bash", "aws s3 ls"),
 ("C02", "allow","Bash", "aws --endpoint-url http://localhost:4566 route53 list-hosted-zones"),
 ("C03", "deny", "Bash", "gcloud container clusters get-credentials prod"),
 ("C04", "ask",  "Bash", "terraform apply -auto-approve"),
 ("C05", "deny", "Bash", "sudo launchctl list"),
 ("C06", "deny", "Bash", "claude -p 'go' --dangerously-skip-permissions"),
 ("C07", "ask",  "Bash", "npm publish"),
 ("C08", "ask",  "Bash", "chmod -R 777 storage"),
 ("C09", "allow","Bash", "npm ci && npm test"),
 ("C10", "allow","Bash", "go test ./... && go build ./cmd/..."),
 # --- tamper protection
 ("T01", "deny", "Bash", "jq '.hooks={}' ~/.claude/settings.json > ~/.claude/settings.json.new && mv ~/.claude/settings.json.new ~/.claude/settings.json"),
 ("T02", "deny", "Bash", "echo '{}' > ~/.claude/settings.json"),
 ("T03", "allow","Bash", "cat ~/.claude/settings.json | jq '.permissions.deny | length'"),
 ("T04", "deny", "Bash", "cp /tmp/kc.yaml ~/.kube/sdlc-lab.json"),
 ("T05", "deny", "Write", {"file_path": HOME + "/.claude/settings.json", "content": "{}"}),
 ("T06", "deny", "Edit", {"file_path": CWD + "/.claude/settings.json", "old_string": "{", "new_string": "{\"disableAllHooks\": true,"}),
 ("T07", "allow","Write", {"file_path": CWD + "/deploy/k8s/base/api.yaml", "content": "kind: Deployment"}),
 ("T08", "deny", "Bash", "sed -i '' 's/dev/prod/' ~/.config/sdlc-guard/policy.json"),
 ("T09", "deny", "Bash", "ln -sf /tmp/x ~/.claude/hooks/sdlc-guard.sh"),
 # --- secret paths (read or copy)
 ("SE1", "deny", "Bash", "cat ~/.kube/sdlc-lab-admin.yaml"),
 ("SE2", "deny", "Bash", "kubectl --kubeconfig ~/.kube/sdlc-lab-admin.yaml get pods -n shop-dev"),
 ("SE3", "deny", "Bash", "KUBECONFIG=$HOME/.kube/sdlc-lab-admin.yaml kubectl get ns"),
 ("SE4", "deny", "Bash", "cp ~/.ssh/id_ed25519 /tmp/k"),
 ("SE5", "deny", "Bash", "python3 -c 'print(1)' --config=~/.aws/credentials"),
 ("SE6", "deny", "Read", {"file_path": HOME + "/.kube/sdlc-lab-admin.yaml"}),
 ("SE7", "deny", "Grep", {"pattern": "token", "path": HOME + "/.ssh"}),
 ("SE8", "allow","Bash", "ls ~/.kube"),
 ("SE9", "allow","Read", {"file_path": CWD + "/deploy/k8s/app.env"}),
 # --- Skill tool
 ("SK1", "deny", "Skill", {"skill": "startup:deploy", "args": "--target=prod"}),
 ("SK2", "deny", "Skill", {"skill": "deploy", "args": "--target=staging --phase=3"}),
 ("SK3", "allow","Skill", {"skill": "startup:deploy", "args": "--target=qa"}),
 ("SK4", "deny", "Skill", {"skill": "startup:rollback", "args": "--target=prod --confirm"}),
]


def run(tool, ti, env):
    p = subprocess.run(["/bin/bash", HOOK], input=json.dumps({"tool_name": tool, "tool_input": ti, "cwd": CWD,
                       "scratchpad_dir": SCRATCH}), capture_output=True, text=True, env=env)
    if p.returncode == 2:
        return "deny", p.stderr.strip()
    if p.returncode == 0 and p.stdout.strip():
        out = json.loads(p.stdout)["hookSpecificOutput"]
        return out["permissionDecision"], out.get("permissionDecisionReason", "")
    if p.returncode == 0:
        return "allow", ""
    return f"error rc={p.returncode}", p.stderr.strip()


fails = 0
total = 0


def check(cid, want, got, label, why=""):
    global fails, total
    total += 1
    ok = got == want
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'} {cid:4} want={want!s:5} got={got!s:5} {label.replace(chr(10), ' ⏎ ')[:90]}" + ("" if ok else f"\n      reason: {why}"))


def main():
    env = dict(os.environ, SDLC_GUARD_POLICY=POLICY, KUBECONFIG=PIN)
    # before anything below copies over the pinned file
    check("MP3", True, oct(os.stat(PIN).st_mode & 0o777) == "0o600", "make-policy writes the pinned kubeconfig mode 600")
    for cid, want, tool, inp in CASES:
        ti = {"command": inp, "description": cid} if isinstance(inp, str) else inp
        got, why = run(tool, ti, env)
        check(cid, want, got, inp if isinstance(inp, str) else json.dumps(inp), why)

    # identity pinning: same pinned path, content swapped (wrong CA / server moved under the same context name)
    for cid, src, label in [("P01", WRONG_CA, "wrong CA at pinned path"), ("P02", TAMPERED, "server swapped, same context name")]:
        shutil.copy(src, PIN)
        got, why = run("Bash", {"command": "kubectl get pods -n shop-dev"}, env)
        check(cid, "deny", got, f"[{label}] kubectl get pods -n shop-dev", why)
    # credential swapped: same cluster (server + CA) but not the agent's token, e.g. admin creds copied in
    dump(kubeconfig(user={"token": "admin-token"}), "swapped.json"); shutil.copy(os.path.join(W, "swapped.json"), PIN)
    got, why = run("Bash", {"command": "kubectl get pods -n shop-dev"}, env)
    check("P05", "deny", got, "[credential swapped in pinned file] kubectl get pods -n shop-dev", why)
    shutil.copy(AGENT_KC, PIN)

    # missing policy: cluster commands fail closed, ordinary commands unaffected
    env3 = dict(env, SDLC_GUARD_POLICY=os.path.join(W, "nonexistent.json"))
    for cid, want, cmd in [("P03", "deny", "kubectl get pods -n shop-dev"), ("P04", "allow", "npm test")]:
        got, why = run("Bash", {"command": cmd}, env3)
        check(cid, want, got, f"[no policy file] {cmd}", why)

    # generated policy content
    pol = json.load(open(POLICY))
    ctx = pol["kube"]["contexts"].get("lima-sdlc", {})
    check("MP1", True, ctx.get("ca_sha256") == hashlib.sha256(CA_PEM).hexdigest() and ctx.get("server") == SERVER
          and ctx.get("user_sha256") == hashlib.sha256(b"fake").hexdigest(), "make-policy pins server + CA + credential sha256")
    check("MP2", True, "10.10.10.2" in pol["local_hosts"] and pol["lima"]["instances"] == ["sdlc-agent", "sdlc-server"],
          "make-policy adds lab hosts and Lima instances")

    # generator refusals
    admin = dump(kubeconfig(user={"client-certificate-data": "eA==", "client-key-data": "eA=="}), "admin.json")
    prodctx = dump(kubeconfig(ctx="prod-eks"), "prodctx.json")
    for cid, args, label in [
        ("MP4", ["--kubeconfig", admin], "refuses a client-certificate (admin) kubeconfig"),
        ("MP5", ["--kubeconfig", prodctx], "refuses a prod-looking context"),
        ("MP6", ["--kubeconfig", AGENT_KC, "--namespaces", "*"], "refuses namespace pattern '*'"),
        ("MP7", ["--kubeconfig", AGENT_KC, "--namespaces", "*-dev,shop-prod"], "refuses a prod namespace pattern"),
    ]:
        p = subprocess.run([sys.executable, MAKE_POLICY, "--pin", os.path.join(W, "x.json")] + args,
                           capture_output=True, text=True)
        check(cid, "refused", "refused" if p.returncode != 0 else "accepted", label, p.stderr.strip())

    # PATH shim: re-checks at exec time and execs the real binary found after itself on PATH
    realdir = os.path.join(W, "realbin"); os.makedirs(realdir)
    with open(os.path.join(realdir, "kubectl"), "w") as f:
        f.write("#!/bin/sh\necho REAL-KUBECTL \"$@\"\n")
    os.chmod(os.path.join(realdir, "kubectl"), 0o755)
    shims = os.path.join(GUARD_DIR, "shims")
    senv = dict(env, SDLC_GUARD_HOOK=HOOK, PATH=f"{shims}:{realdir}:/usr/bin:/bin")
    p = subprocess.run([os.path.join(shims, "kubectl"), "delete", "ns", "shop-qa"], capture_output=True, text=True, env=senv)
    check("SH1", 126, p.returncode, "shim blocks `kubectl delete ns shop-qa` from a subprocess (exit 126)", p.stderr)
    p = subprocess.run([os.path.join(shims, "kubectl"), "get", "pods", "-n", "shop-dev"], capture_output=True, text=True, env=senv)
    check("SH2", "REAL-KUBECTL get pods -n shop-dev", p.stdout.strip(), "shim passes an allowed call to the real kubectl", p.stderr)

    # SessionStart env hook: shims first on PATH + KUBECONFIG pinned from the policy
    envfile = os.path.join(W, "claude-env")
    open(envfile, "w").close()
    subprocess.run(["/bin/bash", os.path.join(GUARD_DIR, "sdlc-guard-env.sh")],
                   env=dict(env, CLAUDE_ENV_FILE=envfile, SDLC_GUARD_SHIMS=shims), check=False)
    body = open(envfile).read()
    check("EN1", True, f'export PATH="{shims}:$PATH"' in body and f'export KUBECONFIG="{PIN}"' in body,
          "env hook exports shim PATH and pinned KUBECONFIG", body)

    # apply-user-settings.py against a SYNTHETIC home (never the real ~/.claude/settings.json)
    fh = os.path.join(W, "home"); os.makedirs(os.path.join(fh, ".claude", "hooks")); os.makedirs(os.path.join(fh, ".config", "sdlc-guard"))
    for f in ("sdlc-guard.sh", "sdlc-guard-env.sh"): open(os.path.join(fh, ".claude", "hooks", f), "w").close()
    shutil.copy(POLICY, os.path.join(fh, ".config", "sdlc-guard", "policy.json"))
    sp = os.path.join(fh, ".claude", "settings.json")
    json.dump({"model": "opus", "permissions": {"allow": ["Read", "Bash", "Bash(git push*)"], "deny": ["Bash(git push* --force*)"]}}, open(sp, "w"))
    aenv = dict(os.environ, HOME=fh); aenv.pop("SDLC_GUARD_POLICY", None)
    AUS = os.path.join(GUARD_DIR, "apply-user-settings.py")
    for _ in range(2):  # second run must be a no-op apart from the backup
        p = subprocess.run([sys.executable, AUS, "--github", "someone"], capture_output=True, text=True, env=aenv)
    s = json.load(open(sp)); pm = s["permissions"]
    check("AS1", True, p.returncode == 0 and "Bash" not in pm["allow"] and "Bash(git push*)" in pm["allow"]
          and "Bash(git push* --force*)" in pm["deny"] and s["model"] == "opus", "apply-user-settings: drops bare Bash, keeps existing keys/rules", p.stderr)
    check("AS2", True, pm["defaultMode"] == "auto" and "Bash(sudo *)" in pm["deny"] and "Bash(git reset --hard*)" in pm["ask"]
          and "https://10.10.10.2:6443" in json.dumps(s["autoMode"]), "apply-user-settings: mode, deny/ask lists, autoMode from policy")
    check("AS3", 1, sum("sdlc-guard.sh" in json.dumps(e) for e in s["hooks"]["PreToolUse"]), "apply-user-settings: guard hook added once (idempotent)")
    check("AS4", True, len(pm["allow"]) == len(set(pm["allow"])) and any(f.startswith("settings.json.bak-") for f in os.listdir(os.path.join(fh, ".claude"))),
          "apply-user-settings: no duplicate rules, backup written")

    shutil.rmtree(W, ignore_errors=True)
    print(f"\n{total - fails}/{total} passed")
    sys.exit(1 if fails else 0)


main()
