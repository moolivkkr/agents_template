#!/usr/bin/env python3
"""make-policy.py — write the sdlc-guard policy (and the pinned agent kubeconfig) from a kubeconfig.

Human-run, once per cluster (the guard denies agents writing either output). Typical use after the
cluster bootstrap has created the sdlc-agent ServiceAccount kubeconfig:

  python3 .claude/guard/make-policy.py \
      --kubeconfig agent-kubeconfig.yaml \
      --pin ~/.kube/sdlc-lab.json \
      --namespaces '*-dev,*-qa' \
      --lima-instance sdlc-agent --lab-host 10.10.10.2 --lab-host 10.10.10.3 \
      --out ~/.config/sdlc-guard/policy.json

What it pins, per context: the API server URL and the SHA-256 of the cluster CA, so a prod cluster
renamed to the same context (or tunnelled to the same address) fails the guard's identity check.
The input kubeconfig may be JSON or YAML (YAML is converted with `kubectl config view --raw
--flatten -o json`); CA data must be inline. It refuses kubeconfigs that authenticate with a client
certificate (k3s's admin kubeconfig does) unless --allow-admin is given: agents get the ServiceAccount
token, never cluster-admin.
"""
import argparse, base64, hashlib, json, os, re, subprocess, sys
from typing import NoReturn

PROD_RE = re.compile(r"(^|[^a-z])(prod|production|prd|live)([^a-z]|$)", re.I)
DEFAULT_LOCAL = ["localhost", "127.0.0.1", "::1", "[::1]", "0.0.0.0", "host.lima.internal", "10.0.2.2"]
DEFAULT_SHELL_ALLOW = [
    "k3s ctr images ls", "k3s ctr -n k8s.io images ls", "k3s ctr images import",
    "journalctl -u k3s", "journalctl -u k3s-agent", "systemctl status k3s", "systemctl status k3s-agent",
    "cat /etc/rancher/k3s/registries.yaml", "uptime", "df -h", "free -m"]
# never read or copied by agents (any command naming them is denied); the admin kubeconfig is the key one
DEFAULT_SECRET = ["~/.kube/sdlc-lab-admin.yaml", "~/.kube/config", "~/.ssh", "~/.aws", "~/.config/gcloud",
                  "~/.azure", "~/.docker/config.json", "~/.lima/sdlc-server/copied-from-guest"]
DEFAULT_PROTECTED = [
    "~/.claude/settings.json", "~/.claude/settings.local.json", "~/.claude/hooks",
    "/Library/Application Support/ClaudeCode", "~/.config/sdlc-guard", "~/.kube", "~/.lima/_config"]


def die(msg) -> NoReturn:
    sys.stderr.write(f"make-policy: {msg}\n")
    sys.exit(1)


def load_kubeconfig(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (ValueError, UnicodeDecodeError):
        pass
    except OSError as e:
        die(f"cannot read {path}: {e}")
    try:
        out = subprocess.run(["kubectl", "config", "view", "--raw", "--flatten", "-o", "json",
                              "--kubeconfig", path], capture_output=True, text=True, check=True).stdout
    except FileNotFoundError:
        die("the kubeconfig is not JSON and kubectl is not on PATH to convert it")
    except subprocess.CalledProcessError as e:
        die(f"kubectl could not read {path}: {e.stderr.strip()}")
    return json.loads(out)


def by_name(items, name):
    return next((x for x in items or [] if x.get("name") == name), None)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kubeconfig", required=True, help="agent kubeconfig (ServiceAccount token), JSON or YAML")
    ap.add_argument("--pin", required=True, help="where the JSON copy agents use lives, e.g. ~/.kube/sdlc-lab.json")
    ap.add_argument("--namespaces", default="*-dev,*-qa", help="comma-separated names/globs agents may write")
    ap.add_argument("--context", action="append", help="context(s) to allow (default: every non-prod context)")
    ap.add_argument("--lima-instance", action="append", default=[], help="Lima instance(s) agents may start/stop/shell")
    ap.add_argument("--lab-host", action="append", default=[], help="extra hosts treated as local (cluster node IPs)")
    ap.add_argument("--allow-admin", action="store_true", help="accept a client-certificate (admin) kubeconfig")
    ap.add_argument("--out", help="write the policy here (default: stdout)")
    ap.add_argument("--write-pin", action="store_true", help="also write the JSON kubeconfig to --pin (mode 600)")
    a = ap.parse_args()

    cfg = load_kubeconfig(a.kubeconfig)
    names = a.context or [c["name"] for c in cfg.get("contexts", [])]
    if not names:
        die("no contexts in the kubeconfig")
    patterns = [p.strip() for p in a.namespaces.split(",") if p.strip()]
    for p in patterns:
        if PROD_RE.search(p) or p in ("*", "default") or p.startswith("kube-"):
            die(f"namespace pattern '{p}' would expose system or prod namespaces")

    contexts = {}
    for name in names:
        if PROD_RE.search(name):
            die(f"context '{name}' looks like prod; agents must never hold it")
        ctx = by_name(cfg.get("contexts"), name)
        if not ctx:
            die(f"context '{name}' not found")
        cl = by_name(cfg.get("clusters"), ctx["context"].get("cluster"))
        us = by_name(cfg.get("users"), ctx["context"].get("user"))
        if not cl or not us:
            die(f"context '{name}' references a missing cluster or user")
        ca = cl["cluster"].get("certificate-authority-data")
        if not ca:
            die(f"cluster for '{name}' has no inline certificate-authority-data (use --flatten)")
        if cl["cluster"].get("insecure-skip-tls-verify"):
            die(f"cluster for '{name}' skips TLS verification; the CA pin would be meaningless")
        user = us.get("user", {})
        if (user.get("client-certificate-data") or user.get("client-certificate")) and not a.allow_admin:
            die(f"user for '{name}' authenticates with a client certificate (an admin kubeconfig?); "
                "give agents the sdlc-agent ServiceAccount token kubeconfig, or pass --allow-admin")
        if user.get("exec") or user.get("auth-provider"):
            die(f"user for '{name}' uses an exec/auth-provider plugin; the agent kubeconfig must be a static token")
        cred = user.get("token") or user.get("client-certificate-data") or ""
        contexts[name] = {
            "server": cl["cluster"]["server"],
            "ca_sha256": hashlib.sha256(base64.b64decode(ca)).hexdigest(),
            # which CREDENTIAL, not just which cluster: an admin credential copied into the pinned file fails
            "user_sha256": hashlib.sha256(cred.encode()).hexdigest(),
            "mutate_namespaces": patterns,
        }

    pin = os.path.expanduser(a.pin)
    if a.write_pin:
        os.makedirs(os.path.dirname(pin), exist_ok=True)
        fd = os.open(pin, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(cfg, f, indent=1)

    policy = {
        "kube": {"kubeconfig": pin, "contexts": contexts},
        "lima": {"instances": a.lima_instance or ["sdlc"], "shell_allow": DEFAULT_SHELL_ALLOW},
        "local_hosts": DEFAULT_LOCAL + [h for h in a.lab_host if h not in DEFAULT_LOCAL],
        "protected_paths": DEFAULT_PROTECTED,
        "secret_paths": DEFAULT_SECRET,
    }
    text = json.dumps(policy, indent=1) + "\n"
    if a.out:
        out = os.path.expanduser(a.out)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w") as f:
            f.write(text)
        sys.stderr.write(f"make-policy: wrote {out} ({', '.join(contexts)}; namespaces {', '.join(patterns)})\n")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
