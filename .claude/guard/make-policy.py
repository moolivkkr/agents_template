#!/usr/bin/env python3
"""make-policy.py — write the sdlc-guard policy (and the pinned agent kubeconfig) from a kubeconfig.

Human-run, once per cluster (the guard denies agents writing either output). Typical use after the
cluster bootstrap has created the sdlc-agent ServiceAccount kubeconfig:

  python3 .claude/guard/make-policy.py \
      --kubeconfig agent-kubeconfig.yaml \
      --pin ~/.kube/sdlc-lab.json \
      --namespaces '*-dev,*-qa' \
      --lima-instance sdlc-agent --lab-host 10.10.10.20 --lab-host 10.10.10.30 \
      --out ~/.config/sdlc-guard/policy.json

What it pins, per context: the API server URL and the SHA-256 of the cluster CA, so a prod cluster
renamed to the same context (or tunnelled to the same address) fails the guard's identity check.
The input kubeconfig may be JSON or YAML (YAML is converted with `kubectl config view --raw
--flatten -o json`); CA data must be inline. It refuses kubeconfigs that authenticate with a client
certificate (k3s's admin kubeconfig does) unless --allow-admin is given: agents get the ServiceAccount
token, never cluster-admin.

AWS for your projects (docs/PERMISSIONS_GUIDE.md "AWS for your projects"): agents may use the real AWS
CLI, every service and region, inside the listed project directories. Add or change one without
touching the kube/lab settings:

  python3 ~/.claude/hooks/sdlc-guard-make-policy.py --update --out ~/.config/sdlc-guard/policy.json \
      --aws-project ~/development/rera [--aws-profile NAME]... [--aws-region ap-south-1]... \
      [--aws-ask-services iam,organizations,account,sso-admin,identitystore,eks | none]
      [--aws-anywhere on|off] [--aws-confirm-destructive on|off]

--aws-anywhere on allows the real CLI from any directory (global settings apply). Destructive calls
(delete-*, terminate-*, deregister-*, s3 rm/rb, s3 sync --delete) and writes to ask_services always prompt
unless --aws-confirm-destructive off (globally, or per --aws-project for unattended project scripts).

--update edits the aws section of the existing --out file and keeps everything else. A full run (with
--kubeconfig/--pin, as cluster-up.sh does) also keeps an existing aws section from --out, so rebuilding
the cluster never drops the AWS projects.
"""
import argparse, base64, hashlib, json, os, re, subprocess, sys
from typing import NoReturn

PROD_RE = re.compile(r"(^|[^a-z])(prod|production|prd|live)([^a-z]|$)", re.I)
DEFAULT_LOCAL = ["localhost", "127.0.0.1", "::1", "[::1]", "0.0.0.0", "host.lima.internal", "10.0.2.2"]
DEFAULT_SHELL_ALLOW = [
    "k3s ctr images ls", "k3s ctr -n k8s.io images ls", "k3s ctr images import",
    "journalctl -u k3s", "journalctl -u k3s-agent", "systemctl status k3s", "systemctl status k3s-agent",
    "cat /etc/rancher/k3s/registries.yaml", "uptime", "df -h", "free -m"]
# never read or copied by agents (any command naming them, literally or by glob, is denied); the admin
# kubeconfig is the key one. Registry/forge tokens and the keychain files were added after the
# 2026-09-30 board review (SEC-03); the guard also unions its own baseline, so older policies are covered.
DEFAULT_SECRET = ["~/.kube/sdlc-lab-admin.yaml", "~/.kube/config", "~/.ssh", "~/.aws", "~/.config/gcloud",
                  "~/.azure", "~/.docker/config.json", "~/.lima/sdlc-server/copied-from-guest",
                  "~/.config/gh", "~/.netrc", "~/.npmrc", "~/.pypirc", "~/.git-credentials", "~/.gnupg",
                  "~/Library/Keychains"]
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


# aws.ask_services default: account-wide identity, permission and org changes prompt, and so does EKS
# (the framework's staging/prod clusters; their deploys are human/CI only). `--aws-ask-services none`
# empties it. Kept in step with DEFAULT_AWS_ASK_SERVICES in sdlc-guard.sh.
DEFAULT_AWS_ASK_SERVICES = ["iam", "organizations", "account", "sso-admin", "identitystore", "eks"]
REGION_RE = re.compile(r"^(\*|[a-z]{2}(-gov|-iso[a-z]*)?-[a-z]+-\d+|[a-z0-9*?-]+)$")


def csv_or_none(v):
    if v is None:
        return None
    return [] if v.strip().lower() in ("none", "") else [x.strip() for x in v.split(",") if x.strip()]


def apply_aws(policy, a):
    """Merge the --aws-* flags into policy["aws"]; returns True if anything was asked to change."""
    asked = any([a.aws_project, a.aws_remove_project, a.aws_ask_services is not None, a.aws_ask_actions is not None,
                 a.aws_allow_credential_actions is not None, a.aws_prod_names is not None,
                 a.aws_anywhere is not None, a.aws_confirm_destructive is not None])
    if (a.aws_profile or a.aws_account or a.aws_region) and not a.aws_project:
        die("--aws-profile/--aws-account/--aws-region apply to the --aws-project(s) named in the same run")
    if not asked:
        return False
    aws = policy.setdefault("aws", {})
    aws.setdefault("projects", [])
    aws.setdefault("ask_services", list(DEFAULT_AWS_ASK_SERVICES))
    aws.setdefault("ask_actions", [])
    aws.setdefault("allow_credential_actions", [])
    aws.setdefault("ask_prod_names", True)

    def norm(pth):
        full = os.path.realpath(os.path.expanduser(pth))
        if full in ("/", os.path.realpath(os.path.expanduser("~"))):
            die(f"aws project path '{pth}' would cover every project; name the project directory")
        return full

    for rm in a.aws_remove_project:
        full = norm(rm)
        aws["projects"] = [p for p in aws["projects"] if norm(p["path"]) != full]
    for prof in a.aws_profile:
        if PROD_RE.search(prof):
            die(f"profile '{prof}' looks like prod; agents must never hold it")
    for acct in a.aws_account:
        if not re.match(r"^\d{12}$", acct):
            die(f"account '{acct}' is not a 12-digit AWS account id")
    for r in a.aws_region:
        if not REGION_RE.match(r):
            die(f"region '{r}' is not a region name or glob")
    for pth in a.aws_project:
        full = norm(pth)
        if not os.path.isdir(full):
            sys.stderr.write(f"make-policy: note: {pth} does not exist yet\n")
        shown = "~/" + os.path.relpath(full, os.path.realpath(os.path.expanduser("~"))) \
            if full.startswith(os.path.realpath(os.path.expanduser("~")) + "/") else full
        entry = {"path": shown, "profiles": list(a.aws_profile), "accounts": list(a.aws_account),
                 "regions": "*" if not a.aws_region or "*" in a.aws_region else list(a.aws_region)}
        aws["projects"] = [p for p in aws["projects"] if norm(p["path"]) != full] + [entry]
    for key, val in (("ask_services", csv_or_none(a.aws_ask_services)), ("ask_actions", csv_or_none(a.aws_ask_actions)),
                     ("allow_credential_actions", csv_or_none(a.aws_allow_credential_actions))):
        if val is not None:
            aws[key] = val
    for act in aws["ask_actions"] + aws["allow_credential_actions"]:
        if ":" not in act:
            die(f"'{act}' is not service:operation (e.g. ec2:delete-vpc, sts:assume-role)")
    never = {"configure:export-credentials", "eks:get-token", "eks:update-kubeconfig"}
    if never & set(aws["allow_credential_actions"]):
        die(f"{', '.join(sorted(never & set(aws['allow_credential_actions'])))} can't be allowed (always denied)")
    if a.aws_prod_names is not None:
        aws["ask_prod_names"] = a.aws_prod_names == "ask"
    if a.aws_anywhere is not None:
        aws["anywhere"] = a.aws_anywhere == "on"
    if a.aws_confirm_destructive is not None:
        on = a.aws_confirm_destructive == "on"
        if a.aws_project:                         # per project (e.g. rera's scripts terminate instances)
            for pth in a.aws_project:
                full = norm(pth)
                for p in aws["projects"]:
                    if norm(p["path"]) == full: p["confirm_destructive"] = on
        else:
            aws["confirm_destructive"] = on
    return True


def write_policy(policy, a, summary):
    text = json.dumps(policy, indent=1) + "\n"
    if a.out:
        out = os.path.expanduser(a.out)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        tmp = out + ".tmp"
        with open(tmp, "w") as f:
            f.write(text)
        os.replace(tmp, out)
        sys.stderr.write(f"make-policy: wrote {out} ({summary})\n")
        if "aws" in policy:
            sys.stdout.write("aws section:\n" + json.dumps(policy["aws"], indent=1) + "\n")
    else:
        sys.stdout.write(text)
        if "aws" in policy:
            sys.stderr.write("make-policy: aws section: " + json.dumps(policy["aws"]) + "\n")


def by_name(items, name):
    return next((x for x in items or [] if x.get("name") == name), None)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kubeconfig", help="agent kubeconfig (ServiceAccount token), JSON or YAML (full run)")
    ap.add_argument("--pin", help="where the JSON copy agents use lives, e.g. ~/.kube/sdlc-lab.json (full run)")
    ap.add_argument("--update", action="store_true",
                    help="edit only the aws section of the existing --out policy; kube/lima/hosts are kept as they are")
    ap.add_argument("--aws-project", action="append", default=[], metavar="DIR",
                    help="project directory where agents may use the real AWS CLI (all services, all regions)")
    ap.add_argument("--aws-profile", action="append", default=[], metavar="NAME",
                    help="pin the --aws-project(s) of this run to these AWS profiles (default: any)")
    ap.add_argument("--aws-account", action="append", default=[], metavar="ID",
                    help="pin to accounts; checked offline from sso_account_id/role_arn in ~/.aws/config only")
    ap.add_argument("--aws-region", action="append", default=[], metavar="REGION",
                    help="limit the --aws-project(s) of this run to these regions/globs (default: all, '*')")
    ap.add_argument("--aws-remove-project", action="append", default=[], metavar="DIR", help="drop a project from aws.projects")
    ap.add_argument("--aws-ask-services", metavar="LIST|none",
                    help="services that prompt (default iam,organizations,account,sso-admin,identitystore,eks); 'none' allows all")
    ap.add_argument("--aws-ask-actions", metavar="LIST|none", help="service:operation globs that prompt, e.g. ec2:delete-vpc,s3:rb")
    ap.add_argument("--aws-allow-credential-actions", metavar="LIST|none",
                    help="credential-printing calls to allow, e.g. sts:assume-role (default none)")
    ap.add_argument("--aws-prod-names", choices=["ask", "off"], help="prompt when an aws argument looks like prod (default ask)")
    ap.add_argument("--aws-anywhere", choices=["on", "off"],
                    help="on: the real AWS CLI from any directory with the global aws settings, not only inside --aws-project dirs")
    ap.add_argument("--aws-confirm-destructive", choices=["on", "off"],
                    help="prompt on delete-*/terminate-*/s3 rm|rb (default on); with --aws-project it sets that project only")
    ap.add_argument("--namespaces", default="*-dev,*-qa", help="comma-separated names/globs agents may write")
    ap.add_argument("--context", action="append", help="context(s) to allow (default: every non-prod context)")
    ap.add_argument("--lima-instance", action="append", default=[], help="Lima instance(s) agents may start/stop/shell")
    ap.add_argument("--lab-host", action="append", default=[], help="extra hosts treated as local (cluster node IPs)")
    ap.add_argument("--allow-admin", action="store_true", help="accept a client-certificate (admin) kubeconfig")
    ap.add_argument("--out", help="write the policy here (default: stdout)")
    ap.add_argument("--write-pin", action="store_true", help="also write the JSON kubeconfig to --pin (mode 600)")
    a = ap.parse_args()

    existing = None
    if a.out and os.path.exists(os.path.expanduser(a.out)):
        try:
            with open(os.path.expanduser(a.out)) as f:
                existing = json.load(f)
        except (OSError, ValueError) as e:
            if a.update:
                die(f"cannot read the existing policy {a.out}: {e}")
    if a.update:
        if not a.out:
            die("--update needs --out <existing policy.json>")
        if existing is None:
            die(f"--update: {a.out} does not exist; run the full make-policy first (cluster-up.sh does)")
        if not apply_aws(existing, a):
            die("--update with no --aws-* flags changes nothing")
        write_policy(existing, a, "aws section updated; kube/lima/hosts unchanged")
        return
    if not a.kubeconfig or not a.pin:
        die("--kubeconfig and --pin are required (or use --update --out <policy> to change only the aws section)")

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
    if existing and isinstance(existing.get("aws"), dict):
        policy["aws"] = existing["aws"]          # regenerating the cluster pins never drops the AWS projects
    apply_aws(policy, a)
    write_policy(policy, a, f"{', '.join(contexts)}; namespaces {', '.join(patterns)}")


if __name__ == "__main__":
    main()
