#!/usr/bin/env bash
# eks-templates.test.sh — offline checks for the Amazon EKS layer (.claude/templates/k8s/eks + the shared
# app scripts): no AWS account, no cluster, no credentials. Run: bash tests/eks-templates.test.sh
#   1 scripts       parse under macOS bash 3.2, executable
#   2 instantiate   --eks copies the layer, fills __APP__, never overwrites, gitignores Terraform state
#   3 overlays      staging/prod render (kustomize), pass kubeconform -strict (CRDs against vendored schemas,
#                   tests/fixtures/eks-crd-schemas), deploylib db-access and eks-policy; every $(VAR)
#                   reference is defined earlier; the security properties are asserted on the render
#   4 eks-policy    refuses tags, Secrets, LoadBalancer Services, missing PDB/zone spread, HPA+replicas,
#                   foreign registries, an in-cluster Postgres and leftover placeholders
#   5 cluster       eks-cluster.yaml renders and validates (IngressClassParams limited to the namespace)
#   6 deploy-eks    with fake kubectl/crane: prod is refused without a typed confirmation or a matching
#                   CI confirmation, before anything is applied; prod needs the staging-healthy tag;
#                   the lab kubeconfig and placeholder eks.env are refused
#   7 terraform     fmt -check, init -backend=false + validate per root, tflint (when installed), and the
#                   security properties (no static keys, write-only secrets, encrypted private RDS, ...)
#   8 workflow      actionlint (when installed); OIDC only, no stored AWS keys, prod by hand in its environment
# Terraform providers/modules and kubeconform's core schemas are downloaded on first run (cached after).
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPT="$REPO/.claude/templates/k8s/app"; EKST="$REPO/.claude/templates/k8s/eks"
SCHEMAS="$REPO/tests/fixtures/eks-crd-schemas"
export PATH="$PATH:/opt/homebrew/bin:$HOME/go/bin:/Applications/Docker.app/Contents/Resources/bin"
PASS=0; FAIL=0; SKIP=0
ok()   { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad()  { echo "  ✗ FAIL: $1"; FAIL=$((FAIL+1)); }
skip() { echo "  - skip: $1"; SKIP=$((SKIP+1)); }
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
# a tool that really runs (the sdlc-guard PATH shims answer `command -v` even when the real binary is absent)
have() { "$@" >/dev/null 2>&1; }

echo "== 1 scripts"
for f in "$EKST"/scripts/k8s/*.sh; do
  /bin/bash -n "$f" 2>/dev/null && [ -x "$f" ] && ok "$(basename "$f") parses under bash 3.2, executable" || bad "$(basename "$f") does not parse or is not executable"
done

echo "== 2 instantiate --eks"
P="$W/proj"
bash "$APPT/instantiate.sh" "$P" demo --eks >/dev/null && ok "instantiate.sh demo --eks" || bad "instantiate.sh --eks failed"
for f in deploy/k8s/components/eks/kustomization.yaml deploy/k8s/overlays/staging/eks.env deploy/k8s/overlays/prod/kustomization.yaml \
         deploy/k8s/eks-cluster.yaml scripts/k8s/deploy-eks.sh scripts/k8s/promote-eks.sh infra/terraform/modules/platform/main.tf \
         infra/terraform/envs/prod/backend.tf .github/workflows/deploy-eks.yml deploy/k8s/overlays/dev/kustomization.yaml; do
  [ -f "$P/$f" ] || bad "missing $f"
done
grep -rq "__APP__" "$P" && bad "unreplaced __APP__ placeholders: $(grep -rl __APP__ "$P" | head -3)" || ok "every __APP__ replaced (lab + EKS layers)"
again="$(bash "$APPT/instantiate.sh" "$P" demo --eks)"
echo "$again" | grep -q kept && ! echo "$again" | grep -q created && ok "a second run keeps every file" || bad "instantiate --eks overwrote files"
grep -qxF '*.tfstate' "$P/.gitignore" && grep -qxF '.terraform/' "$P/.gitignore" && ok ".gitignore covers Terraform state and .terraform/" || bad ".gitignore lacks Terraform entries"
(cd "$W" && mkdir dot && cd dot && bash "$APPT/instantiate.sh" . demo >/dev/null) && [ -f "$W/dot/deploy/k8s/app.env" ] \
  && ok "instantiate.sh . <app> writes into the caller's directory" || bad "instantiate.sh . <app> did not write into cwd"

echo "== 3 overlays"
DL="$P/scripts/k8s/deploylib.py"
REG="000000000000.dkr.ecr.us-east-1.amazonaws.com"; D1="sha256:$(printf 'a%.0s' $(seq 1 64))"
KZ_BUILD=""; if have kustomize version; then KZ_BUILD="kustomize build"; elif have kubectl version --client; then KZ_BUILD="kubectl kustomize"; fi
KC="$(command -v kubeconform || true)"
to_json() { python3 -c 'import json,sys,yaml; print(json.dumps({"kind":"List","items":[d for d in yaml.safe_load_all(open(sys.argv[1])) if d]}))' "$1"; }
python3 -c 'import yaml' 2>/dev/null || { echo "PyYAML is required"; exit 1; }
if [ -z "$KZ_BUILD" ]; then skip "neither kustomize nor kubectl installed (overlay checks)"; else
  for e in staging prod; do
    python3 "$DL" set-images "$P/deploy/k8s/overlays/$e/kustomization.yaml" "api=$REG/demo/api@$D1"
    if $KZ_BUILD "$P/deploy/k8s/overlays/$e" > "$W/$e.yaml" 2>"$W/$e.err"; then ok "overlay $e renders"; else bad "overlay $e: $(head -3 "$W/$e.err")"; continue; fi
    to_json "$W/$e.yaml" > "$W/$e.json"
    if [ -n "$KC" ]; then
      "$KC" -strict -summary -schema-location default -schema-location "$SCHEMAS/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json" "$W/$e.yaml" >"$W/$e.kc" 2>&1 \
        && ok "kubeconform -strict overlay $e (ExternalSecret/SecretStore against vendored CRD schemas): $(tail -1 "$W/$e.kc")" || bad "kubeconform $e: $(grep -v '^Summary' "$W/$e.kc" | head -3)"
    else skip "kubeconform not installed"; fi
    python3 "$DL" db-access < "$W/$e.json" 2>"$W/$e.acc" && ok "$e: db-access (who reads which database role) passes" || bad "$e db-access: $(cat "$W/$e.acc")"
    python3 "$DL" eks-policy --registry "$REG" --allow-placeholders < "$W/$e.json" 2>"$W/$e.pol" && ok "$e: eks-policy passes" || bad "$e eks-policy: $(cat "$W/$e.pol")"
    python3 "$DL" eks-policy --registry "$REG" < "$W/$e.json" 2>/dev/null && bad "$e: eks-policy accepted placeholder coordinates" || ok "$e: eks-policy refuses the template's placeholder coordinates"
    python3 - "$W/$e.json" "$e" > "$W/$e.checks" 2>&1 <<'PY' || echo "FAIL|checks crashed: $(tail -1 "$W/$e.checks")" >> "$W/$e.checks"
import json, re, sys
objs, env = json.load(open(sys.argv[1]))["items"], sys.argv[2]
by = {f"{o['kind']}/{o['metadata']['name']}": o for o in objs}
cm = lambda prefix: next(o for k, o in by.items() if k.startswith("ConfigMap/" + prefix))
def spec(o): return o["spec"]["jobTemplate"]["spec"]["template"]["spec"] if o["kind"] == "CronJob" else o["spec"]["template"]["spec"]
def check(cond, msg): print(("PASS" if cond else "FAIL") + "|" + msg)
check(all(o["metadata"].get("namespace") == f"demo-{env}" for o in objs), f"every object in namespace demo-{env}")
check(not any(o["kind"] == "Secret" for o in objs), "no Secret in the render (credentials come from AWS Secrets Manager)")
check("StatefulSet/postgres" not in by and "Service/postgres" not in by, "no in-cluster Postgres")
imgs = [c["image"] for o in objs if o["kind"] in ("Deployment", "CronJob") for c in spec(o).get("initContainers", []) + spec(o)["containers"]]
check(all(re.search(r"@sha256:[0-9a-f]{64}$", i) for i in imgs), f"all {len(imgs)} container images digest-pinned")
# $(VAR) in an env value expands only variables defined EARLIER in the list or by envFrom (kubelet rule)
probs = []
for o in objs:
    if o["kind"] not in ("Deployment", "CronJob"): continue
    s = spec(o)
    for c in s.get("initContainers", []) + s["containers"]:
        defined = set()
        for ef in c.get("envFrom", []):
            ref = ef.get("configMapRef", {}).get("name")
            data = next((x.get("data", {}) for x in objs if x["kind"] == "ConfigMap" and x["metadata"]["name"] == ref), {})
            defined |= set(data)
        for e in c.get("env", []):
            for v in re.findall(r"\$\(([A-Za-z_][A-Za-z0-9_]*)\)", e.get("value", "")):
                if v not in defined: probs.append(f"{o['metadata']['name']}/{c['name']}: {e['name']} uses $({v}) before it is defined")
            defined.add(e["name"])
check(not probs, "every $(VAR) reference is defined earlier in its container" + (": " + "; ".join(probs) if probs else ""))
api = spec(by["Deployment/api"])["containers"][0]
url = next(e["value"] for e in api["env"] if e["name"] == "DATABASE_URL")
check("$(DB_HOST)" in url and "sslmode=$(DB_SSLMODE)" in url and cm("app-config")["data"]["DB_SSLMODE"] == "require", "the API connects to DB_HOST with sslmode=require")
check(sorted(e["valueFrom"]["secretKeyRef"]["key"] for e in api["env"] if "valueFrom" in e) == ["DB_APP_PASSWORD", "DB_APP_USER"], "the API reads only the RLS-bound app role (DB_APP_*)")
eks = cm("eks-config")["data"]
check(cm("app-config")["data"]["DB_HOST"] == eks["DB_HOST"], "app-config DB_HOST comes from eks.env")
ing = by["Ingress/web"]
check(ing["spec"]["ingressClassName"] == "demo-alb" and ing["spec"]["rules"][0]["host"] == eks["APP_HOST"]
      and ing["metadata"]["annotations"]["alb.ingress.kubernetes.io/ssl-redirect"] == "443", "Ingress: Auto Mode ALB class, host from eks.env, HTTP->HTTPS redirect")
es = by["ExternalSecret/db-credentials"]["spec"]
keys = {d["secretKey"]: d["remoteRef"]["key"] for d in es["data"]}
check(es["target"]["name"] == "db-credentials" and keys["DB_SUPERUSER_PASSWORD"] == eks["DB_MASTER_SECRET_ARN"]
      and keys["DB_MIGRATOR_PASSWORD"] == eks["DB_MIGRATOR_SECRET"] and keys["DB_APP_USER"] == eks["DB_APP_SECRET"]
      and len(keys) == 6, "ExternalSecret db-credentials: the three role pairs, secret ids from eks.env")
check("auth" not in by["SecretStore/aws-secrets-manager"]["spec"]["provider"]["aws"], "SecretStore uses the controller's Pod Identity credentials (no static keys, no auth block)")
dep = by["Deployment/api"]["spec"]
check("replicas" not in dep and by["HorizontalPodAutoscaler/api"]["spec"]["minReplicas"] == (3 if env == "prod" else 2), f"HPA owns replicas (min {3 if env == 'prod' else 2}); the Deployment sets none")
check(by["PodDisruptionBudget/api"]["spec"]["maxUnavailable"] == 1, "PodDisruptionBudget maxUnavailable 1")
tsc = spec(by["Deployment/api"]).get("topologySpreadConstraints", [])
check(any(t["topologyKey"] == "topology.kubernetes.io/zone" and t["whenUnsatisfiable"] == "DoNotSchedule" for t in tsc), "API spread across AZs (hard)")
check(api["resources"]["requests"]["cpu"] and api["resources"]["limits"]["memory"], "API has requests and a memory limit")
check(by["NetworkPolicy/env-isolation"]["spec"]["ingress"][1]["from"][0]["ipBlock"]["cidr"] == eks["VPC_CIDR"], "NetworkPolicy admits the ALB from the VPC CIDR in eks.env")
roles = spec(by["CronJob/db-roles"])["containers"][0]
envs = {e["name"]: e.get("value") for e in roles["env"]}
check(envs["PGHOST"] == "$(DB_HOST)" and cm("app-config")["data"]["PGSSLMODE"] == "require", "db-roles connects to RDS over TLS as the master user (DB_SUPERUSER_*)")
check(not any(o["kind"] == "Service" and o["spec"].get("type") in ("LoadBalancer", "NodePort") for o in objs), "no LoadBalancer/NodePort Service")
# Pod Security "restricted" (enforced on the namespace by eks-cluster.yaml): non-root, RuntimeDefault seccomp,
# no privilege escalation, every capability dropped — for every container, init containers included
bad = []
for o in objs:
    if o["kind"] not in ("Deployment", "CronJob"): continue
    s = spec(o); psc = s.get("securityContext", {})
    if not psc.get("runAsNonRoot") or psc.get("seccompProfile", {}).get("type") != "RuntimeDefault": bad.append(o["metadata"]["name"] + " pod")
    for c in s.get("initContainers", []) + s["containers"]:
        sc = c.get("securityContext", {})
        if sc.get("allowPrivilegeEscalation") is not False or "ALL" not in sc.get("capabilities", {}).get("drop", []): bad.append(f"{o['metadata']['name']}/{c['name']}")
check(not bad, "every pod and container meets Pod Security 'restricted'" + (": " + ", ".join(bad) if bad else ""))
PY
    while IFS='|' read -r v m; do [ "$v" = PASS ] && ok "$e: $m" || bad "$e: ${m:-$v}"; done < "$W/$e.checks"
  done
  # lab overlays still render and pass db-access with the shared scripts (the EKS layer changes no base file)
  for e in dev qa; do
    python3 "$DL" db-secrets "$P/deploy/k8s/overlays/$e/secrets.env" 2>/dev/null
    $KZ_BUILD "$P/deploy/k8s/overlays/$e" > "$W/$e.yaml" 2>/dev/null && to_json "$W/$e.yaml" | python3 "$DL" db-access 2>/dev/null \
      && grep -q 'kind: StatefulSet' "$W/$e.yaml" && ok "lab overlay $e unchanged: renders with its in-cluster Postgres, db-access passes" || bad "lab overlay $e broke"
  done
fi

echo "== 4 eks-policy refuses"
if [ -s "$W/prod.json" ]; then
  python3 - "$DL" "$W/prod.json" "$REG" <<'PY' && ok "eks-policy refuses: tag image, foreign registry, a Secret, LoadBalancer/NodePort Service, no PDB, no zone spread, replicas under an HPA, in-cluster postgres, privileged, hostPath, no ingressClassName, missing ExternalSecret" || bad "eks-policy let a forbidden render through"
import copy, json, subprocess, sys
dl, objs, reg = sys.argv[1], json.load(open(sys.argv[2]))["items"], sys.argv[3]
def run(items):
    return subprocess.run([sys.executable, dl, "eks-policy", "--registry", reg, "--allow-placeholders"],
                          input=json.dumps({"kind": "List", "items": items}), text=True, capture_output=True).returncode
def mut(kind, name, f):
    out = copy.deepcopy(objs)
    for o in out:
        if o["kind"] == kind and o["metadata"]["name"] == name: f(o)
    return out
c = lambda o: o["spec"]["template"]["spec"]["containers"][0]
D = "sha256:" + "a" * 64
cases = {
  "tag": mut("Deployment", "api", lambda o: c(o).update(image=f"{reg}/demo/api:latest")),
  "foreign registry": mut("Deployment", "api", lambda o: c(o).update(image=f"docker.io/library/nginx@{D}")),
  "secret": objs + [{"kind": "Secret", "metadata": {"name": "db-credentials"}, "data": {}}],
  "loadbalancer": mut("Service", "api", lambda o: o["spec"].update(type="LoadBalancer")),
  "nodeport": mut("Service", "api", lambda o: o["spec"].update(type="NodePort")),
  "no pdb": [o for o in objs if o["kind"] != "PodDisruptionBudget"],
  "no zone spread": mut("Deployment", "api", lambda o: o["spec"]["template"]["spec"].pop("topologySpreadConstraints")),
  "replicas+hpa": mut("Deployment", "api", lambda o: o["spec"].update(replicas=2)),
  "postgres": objs + [{"kind": "StatefulSet", "metadata": {"name": "postgres"}, "spec": {"template": {"spec": {"securityContext": {"runAsNonRoot": True}, "containers": [{"name": "p", "image": f"{reg}/x@{D}"}]}}}}],
  "privileged": mut("Deployment", "api", lambda o: c(o).setdefault("securityContext", {}).update(privileged=True)),
  "hostPath": mut("Deployment", "api", lambda o: o["spec"]["template"]["spec"].setdefault("volumes", []).append({"name": "h", "hostPath": {"path": "/"}})),
  "no class": mut("Ingress", "web", lambda o: o["spec"].pop("ingressClassName")),
  "no externalsecret": [o for o in objs if o["kind"] != "ExternalSecret"],
}
assert run(objs) == 0, "the clean prod render was refused"
let_through = [k for k, items in cases.items() if run(items) == 0]
assert not let_through, let_through
PY
else skip "no rendered prod overlay"; fi

echo "== 5 cluster bootstrap manifest"
python3 - "$P/deploy/k8s/eks-cluster.yaml" > "$W/cluster.yaml" <<'PY' || bad "eks-cluster.yaml does not render with string.Template (what eks-bootstrap.sh uses)"
import string, sys
print(string.Template(open(sys.argv[1]).read()).substitute(ENV="prod", ACM_CERTIFICATE_ARN="arn:aws:acm:us-east-1:123456789012:certificate/abc"))
PY
python3 - "$W/cluster.yaml" <<'PY' && ok "eks-cluster.yaml: restricted Pod Security on demo-prod; IngressClass eks.amazonaws.com/alb; params limited to demo-prod with the ACM certificate; deployers get ExternalSecrets in the namespace only" || bad "eks-cluster.yaml content"
import sys, yaml
d = {f"{o['kind']}/{o['metadata']['name']}": o for o in yaml.safe_load_all(open(sys.argv[1])) if o}
ns, icp, ic, role = d["Namespace/demo-prod"], d["IngressClassParams/demo-alb"], d["IngressClass/demo-alb"], d["Role/demo-deployer-extras"]
assert ns["metadata"]["labels"]["pod-security.kubernetes.io/enforce"] == "restricted"
assert ic["spec"]["controller"] == "eks.amazonaws.com/alb" and ic["spec"]["parameters"]["name"] == "demo-alb"
assert icp["spec"]["namespaceSelector"]["matchLabels"] == {"kubernetes.io/metadata.name": "demo-prod"}
assert icp["spec"]["certificateARNs"] == ["arn:aws:acm:us-east-1:123456789012:certificate/abc"] and icp["spec"]["scheme"] == "internet-facing"
assert role["metadata"]["namespace"] == "demo-prod" and role["rules"][0]["apiGroups"] == ["external-secrets.io"]
assert d["RoleBinding/demo-deployer-extras"]["subjects"][0]["name"] == "demo-deployers"
PY
if [ -n "$KC" ] && [ -s "$W/cluster.yaml" ]; then
  "$KC" -strict -summary -schema-location default -schema-location "$SCHEMAS/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json" "$W/cluster.yaml" >"$W/cl.kc" 2>&1 \
    && grep -q 'Valid: 5, Invalid: 0, Errors: 0, Skipped: 0' "$W/cl.kc" && ok "kubeconform -strict eks-cluster.yaml (IngressClassParams against the vendored eks.amazonaws.com/v1 schema)" || bad "kubeconform cluster: $(head -3 "$W/cl.kc")"
fi

echo "== 6 deploy-eks.sh safety (fake kubectl/crane, nothing real is touched)"
S="$W/sandbox"; mkdir -p "$S/bin" "$S/kube"
cp -R "$P/." "$S/proj"
SP="$S/proj"; ARN="arn:aws:eks:us-east-1:123456789012:cluster/demo-prod"; R2="123456789012.dkr.ecr.us-east-1.amazonaws.com"
for e in staging prod; do
  cat > "$SP/deploy/k8s/overlays/$e/eks.env" <<EOF
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012
EKS_CLUSTER_NAME=demo-$e
EKS_CLUSTER_ARN=arn:aws:eks:us-east-1:123456789012:cluster/demo-$e
ECR_REGISTRY=$R2
APP_HOST=$e.demo.test
ACM_CERTIFICATE_ARN=arn:aws:acm:us-east-1:123456789012:certificate/abc
DB_HOST=demo-$e.abc.us-east-1.rds.amazonaws.com
DB_MASTER_SECRET_ARN=arn:aws:secretsmanager:us-east-1:123456789012:secret:rds!db-abc
DB_MIGRATOR_SECRET=demo/$e/db-migrator
DB_APP_SECRET=demo/$e/db-app
VPC_CIDR=10.0.0.0/16
EOF
  python3 "$SP/scripts/k8s/deploylib.py" set-images "$SP/deploy/k8s/overlays/$e/kustomization.yaml" "api=$R2/demo/api@$D1"
  printf '{"from_env": "qa", "git_sha": "abc123def456", "images": {}}\n' > "$SP/deploy/k8s/overlays/$e/promoted-from.json"
done
cat > "$S/bin/kubectl" <<EOF
#!/bin/sh
echo "kubectl \$*" >> "$S/calls"
case "\$*" in
  "config current-context") echo "$ARN" ;;
  "get --raw /readyz") echo ok ;;
  *"get serviceaccount default"*) echo sa ;;
  kustomize*) echo "fake: stop here" >&2; exit 1 ;;
  *) exit 0 ;;
esac
EOF
cat > "$S/bin/crane" <<EOF
#!/bin/sh
echo "crane \$*" >> "$S/calls"
case "\$*" in
  "digest $R2/demo/api@$D1") echo "$D1" ;;
  "digest $R2/demo/api:staging-healthy-abc123def456") [ -f "$S/healthy" ] && echo "$D1" || exit 1 ;;
  *) exit 1 ;;
esac
EOF
chmod +x "$S/bin/kubectl" "$S/bin/crane"; : > "$S/kube/config"
dep() { (cd "$SP" && env -u SDLC_PROD_CONFIRM -u GITHUB_ACTIONS PATH="$S/bin:$PATH" EKS_KUBECONFIG="$S/kube/config" "$@" </dev/null 2>&1); }
: > "$S/calls"; out="$(dep scripts/k8s/deploy.sh prod)"; rc=$?
[ $rc -ne 0 ] && grep -q 'has no staging-healthy-abc123def456 tag' <<<"$out" && ! grep -q 'apply' "$S/calls" \
  && ok "prod refused when the digest was never HEALTHY in staging (no staging-healthy tag); nothing applied" || bad "prod without staging-healthy: rc=$rc $out"
touch "$S/healthy"
: > "$S/calls"; out="$(dep scripts/k8s/deploy.sh prod)"; rc=$?
[ $rc -ne 0 ] && grep -q 'prod needs a typed confirmation' <<<"$out" && ! grep -qE 'kustomize|apply|create' "$S/calls" \
  && ok "prod without a terminal or CI confirmation is refused before anything is rendered or applied" || bad "prod unconfirmed: rc=$rc $out"
: > "$S/calls"; out="$(cd "$SP" && PATH="$S/bin:$PATH" EKS_KUBECONFIG="$S/kube/config" GITHUB_ACTIONS=true SDLC_PROD_CONFIRM=demo-prod@wrong scripts/k8s/deploy.sh prod </dev/null 2>&1)"; rc=$?
[ $rc -ne 0 ] && grep -q 'does not match demo-prod@abc123def456' <<<"$out" && ! grep -qE 'kustomize|apply' "$S/calls" \
  && ok "CI confirmation for another release is refused" || bad "wrong CI confirmation: rc=$rc $out"
: > "$S/calls"; out="$(cd "$SP" && PATH="$S/bin:$PATH" EKS_KUBECONFIG="$S/kube/config" GITHUB_ACTIONS=true SDLC_PROD_CONFIRM=demo-prod@abc123def456 scripts/k8s/deploy.sh prod </dev/null 2>&1)"; rc=$?
grep -q 'prod confirmed by the approved GitHub Environment run' <<<"$out" && grep -q '^kubectl kustomize' "$S/calls" && ! grep -q 'kubectl apply' "$S/calls" \
  && ok "the matching CI confirmation passes; the (fake) render failure stops the deploy before apply (verdict FAILED)" || bad "matching CI confirmation: rc=$rc $out"
out="$(cd "$SP" && PATH="$S/bin:$PATH" EKS_KUBECONFIG="$HOME/.kube/sdlc-lab.json" scripts/k8s/deploy.sh staging </dev/null 2>&1)"; rc=$?
[ $rc -ne 0 ] && grep -qE 'is the lab kubeconfig|current context' <<<"$out" && ok "staging refuses the lab kubeconfig" || bad "lab kubeconfig accepted: $out"
out="$(cd "$SP" && PATH="$S/bin:$PATH" scripts/k8s/deploy.sh staging </dev/null 2>&1)"; rc=$?
[ $rc -ne 0 ] && grep -q 'set EKS_KUBECONFIG' <<<"$out" && ok "staging refuses to run without an explicit EKS_KUBECONFIG (never the lab default)" || bad "no EKS_KUBECONFIG: $out"
out="$(cd "$P" && PATH="$S/bin:$PATH" EKS_KUBECONFIG="$S/kube/config" scripts/k8s/deploy.sh staging </dev/null 2>&1)"; rc=$?
[ $rc -ne 0 ] && grep -q 'placeholder values' <<<"$out" && ok "an eks.env with placeholders is refused" || bad "placeholder eks.env accepted: $out"
DE="$P/scripts/k8s/deploy-eks.sh"
c="$(grep -n '^confirm_prod$' "$DE" | cut -d: -f1)"; a="$(grep -n 'kubectl apply -n' "$DE" | head -1 | cut -d: -f1)"
[ -n "$c" ] && [ -n "$a" ] && [ "$c" -lt "$a" ] && ! grep -qE 'docker build|crane push' "$DE" \
  && ok "deploy-eks.sh confirms prod before any apply and never builds or pushes an image" || bad "deploy-eks.sh: confirmation order / build"

echo "== 7 terraform"
TF=""; for t in terraform tofu; do have "$t" version && { TF="$t"; break; }; done
TFD="$P/infra/terraform"
if [ -z "$TF" ]; then skip "neither terraform nor tofu installed"; else
  "$TF" fmt -check -recursive "$TFD" >/dev/null 2>&1 && ok "$TF fmt -check (all roots and modules)" || bad "$TF fmt: $("$TF" fmt -check -recursive "$TFD" 2>&1 | head -3)"
  export TF_PLUGIN_CACHE_DIR="${TF_PLUGIN_CACHE_DIR:-$HOME/.cache/sdlc-eks-tf-plugins}"; mkdir -p "$TF_PLUGIN_CACHE_DIR"
  for d in state staging prod; do
    if (cd "$TFD/envs/$d" && "$TF" init -backend=false -input=false -no-color >"$W/init-$d.log" 2>&1); then
      (cd "$TFD/envs/$d" && "$TF" validate -no-color >"$W/val-$d.log" 2>&1) && ok "$TF init -backend=false + validate envs/$d" || bad "validate envs/$d: $(grep -A3 Error "$W/val-$d.log" | head -4)"
    else skip "init envs/$d failed (no network for providers/modules?): $(grep -m1 -i error "$W/init-$d.log")"; fi
  done
  if have tflint --version; then
    printf 'plugin "terraform" {\n  enabled = true\n  preset  = "recommended"\n}\n' > "$W/tflint.hcl"
    tl=ok; for d in modules/platform modules/github-oidc envs/state envs/staging envs/prod; do
      tflint --chdir="$TFD/$d" --config="$W/tflint.hcl" --call-module-type=local >"$W/tflint.log" 2>&1 || { tl=fail; bad "tflint $d: $(head -5 "$W/tflint.log")"; }
    done
    [ "$tl" = ok ] && ok "tflint (recommended preset) clean on every module and root"
  else skip "tflint not installed"; fi
fi
python3 - "$TFD" <<'PY' > "$W/tf.checks" 2>&1 || echo "FAIL|terraform checks crashed: $(tail -1 "$W/tf.checks")" >> "$W/tf.checks"
import glob, os, re, sys
d = sys.argv[1]
src = {p: open(p).read() for p in glob.glob(f"{d}/**/*.tf", recursive=True) if "/.terraform/" not in p}
allt = "\n".join(src.values())
code = re.sub(r"#[^\n]*", "", allt)
plat = open(f"{d}/modules/platform/main.tf").read(); oidc = open(f"{d}/modules/github-oidc/main.tf").read()
def check(cond, msg): print(("PASS" if cond else "FAIL") + "|" + msg)
check(not re.search(r'resource\s+"aws_iam_(user|access_key)"|access_key\s*=|secret_key\s*=', code), "no IAM users, access keys or static credentials anywhere")
check("manage_master_user_password = true" in plat and not re.search(r"^\s*password\s*=", plat, re.M), "RDS master password is RDS-managed in Secrets Manager (never in Terraform)")
check("secret_string_wo " in plat and not re.search(r"secret_string\s*=", plat) and 'ephemeral "random_password"' in plat, "role passwords: ephemeral random_password -> write-only secret_string_wo (never in state)")
check(all(s in plat for s in ("storage_encrypted     = true", "publicly_accessible    = false", '"rds.force_ssl"')), "RDS encrypted, private, TLS forced")
check('image_tag_mutability = "IMMUTABLE"' in plat and "scan_on_push = true" in plat, "ECR: immutable tags, scan on push")
check('authentication_mode                      = "API"' in plat and "enable_cluster_creator_admin_permissions = false" in plat, "EKS: access entries only, no implicit creator admin")
check(re.search(r'access_scope\s*=\s*\{\s*type\s*=\s*"namespace",\s*namespaces\s*=\s*\[local\.namespace\]', plat) is not None, "the CI deployer is admin in its namespace only")
check('"pods.eks.amazonaws.com"' in plat and "aws_eks_pod_identity_association" in plat and "enable_irsa" not in plat, "pod AWS access through EKS Pod Identity")
check("compute_config" in plat and "enabled    = true" in plat, "EKS Auto Mode compute")
check('"StringEquals"' in oidc and "StringLike" not in oidc and ":environment:${var.github_environment}" in oidc and "sts.amazonaws.com" in oidc,
      "GitHub OIDC trust: exact repo + environment subject, audience sts.amazonaws.com, no wildcards")
check("thumbprint_list" not in re.sub(r"#[^\n]*", "", oidc), "no OIDC thumbprint pinned (IAM validates GitHub's CA)")
for e in ("staging", "prod"):
    b = open(f"{d}/envs/{e}/backend.tf").read()
    check('backend "s3"' in b and "use_lockfile = true" in b and "encrypt      = true" in b and f'key          = "{e}/terraform.tfstate"' in b and "dynamodb_table" not in b,
          f"envs/{e}: S3 remote state, own key, encrypted, S3-native locking (no DynamoDB)")
check(re.search(r'required_version\s*=\s*">= 1\.11"', allt) is not None, "Terraform >= 1.11 (write-only arguments, use_lockfile)")
PY
while IFS='|' read -r v m; do [ "$v" = PASS ] && ok "terraform: $m" || bad "terraform: ${m:-$v}"; done < "$W/tf.checks"

echo "== 8 workflow"
WF="$P/.github/workflows/deploy-eks.yml"
if have actionlint -version; then actionlint "$WF" >"$W/al.log" 2>&1 && ok "actionlint deploy-eks.yml" || bad "actionlint: $(head -3 "$W/al.log")"; else skip "actionlint not installed"; fi
python3 - "$WF" <<'PY' && ok "workflow: id-token write only in the deploy job, configure-aws-credentials role-to-assume (no stored AWS keys), job in the target's GitHub Environment, prod only by workflow_dispatch, pinned checksum-verified tools" || bad "workflow security properties"
import sys, yaml
src = open(sys.argv[1]).read(); w = yaml.safe_load(src)
on = w.get("on", w.get(True))
job = w["jobs"]["deploy"]
assert w["permissions"] == {"contents": "read"} and job["permissions"]["id-token"] == "write"
assert "secrets." not in src and "aws-access-key-id" not in src and "aws-secret-access-key" not in src
steps = {s.get("uses", "").split("@")[0]: s for s in job["steps"]}
assert "role-to-assume" in steps["aws-actions/configure-aws-credentials"]["with"]
assert "environment" in job and "inputs.env" in job["environment"]
assert on["push"]["paths"] == ["deploy/k8s/overlays/staging/**"]   # prod never deploys on push
assert "sha256sum -c" in src and "KUBECTL_VERSION" in src
PY

echo "────────────────────────────────────────────"
echo "eks-templates.test.sh: $PASS passed, $FAIL failed, $SKIP skipped"
[ "$FAIL" -eq 0 ]
