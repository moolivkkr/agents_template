#!/bin/bash
# sdlc-guard.sh — Claude Code PreToolUse guard for unattended non-prod development and deployment.
#
# Installed by `./install.sh --guard` to ~/.claude/hooks/sdlc-guard.sh and registered in USER (or
# managed) settings with matcher "Bash|Monitor|Skill|Write|Edit|MultiEdit|NotebookEdit|Read|Grep|Glob". User-level on
# purpose: a repo's settings (or disableAllHooks there) cannot switch it off. See docs/PERMISSIONS_GUIDE.md.
# Contract (code.claude.com/docs/en/hooks#pretooluse-decision-control):
#   - no output + exit 0  -> no opinion; normal permission flow (deny/ask rules, mode, classifier) continues
#   - JSON permissionDecision "ask" + exit 0 -> forces a prompt (in `-p --permission-prompts none` it is denied)
#   - JSON permissionDecision "deny" + reason on stderr + exit 2 -> blocked; Claude sees the reason
# The guard never returns "allow": it only narrows, so deny/ask rules and auto mode still apply.
#
# Policy file: $SDLC_GUARD_POLICY or ~/.config/sdlc-guard/policy.json, written once by the human with
# .claude/guard/make-policy.py (pins the agent kubeconfig, its server + CA hash, and the namespace
# patterns agents may write, e.g. "*-dev", "*-qa").
# Fail-closed: if python3 is missing or the engine crashes, kube/lima/cloud commands are denied.

INPUT="$(cat)"
PY="$(command -v python3 || echo /usr/bin/python3)"

if [ ! -x "$PY" ]; then
  if printf '%s' "$INPUT" | grep -Eq '(kubectl|helm|limactl|kubecolor|aws |gcloud|az |terraform|crane|-eks\.sh|eks-bootstrap|--target=(prod|staging))'; then
    echo "sdlc-guard: python3 unavailable; refusing cluster/cloud command (fail-closed)" >&2; exit 2
  fi
  exit 0
fi

# NB: not "$(cat <<'PYEOF' ...)" -- macOS bash 3.2 mis-parses quotes/parens inside a heredoc in $(...)
IFS= read -r -d '' PYCODE <<'PYEOF' || true
import json, os, re, shlex, sys, hashlib, base64, fnmatch

POLICY_PATH = os.environ.get("SDLC_GUARD_POLICY", os.path.expanduser("~/.config/sdlc-guard/policy.json"))
HOME = os.path.expanduser("~")

def load_policy():
    try:
        with open(POLICY_PATH) as f:
            return json.load(f)
    except Exception:
        return None

POLICY = load_policy()
PROD_RE = re.compile((POLICY or {}).get("prod_regex", r"(^|[^a-z])(prod|production|prd|live)([^a-z]|$)"), re.I)
LOCAL_HOSTS = set((POLICY or {}).get("local_hosts", ["localhost", "127.0.0.1", "::1", "[::1]", "0.0.0.0", "host.lima.internal", "10.0.2.2"]))
ARTIFACT_DIRS = set((POLICY or {}).get("artifact_dirs", [
    "node_modules", "dist", "build", "out", ".next", ".nuxt", ".svelte-kit", "coverage", "target",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".turbo", ".cache", ".gradle",
    "DerivedData", ".expo", "tmp", ".tmp", "test-results", "playwright-report", "bin", "obj"]))
PROTECTED_WRITE = [os.path.realpath(os.path.expanduser(p)) for p in (POLICY or {}).get("protected_paths", [
    "~/.claude/settings.json", "~/.claude/settings.local.json", "~/.claude/hooks",
    "/Library/Application Support/ClaudeCode", "~/.config/sdlc-guard", "~/.kube", "~/.lima/_config"])]
# Credentials agents never read or copy. The policy's list is UNIONED with this baseline, so a policy
# written by an older make-policy.py still covers the credential files added later (board review SEC-03).
BASELINE_SECRETS = ["~/.kube/sdlc-lab-admin.yaml", "~/.kube/config", "~/.ssh", "~/.aws", "~/.config/gcloud",
    "~/.azure", "~/.docker/config.json", "~/.config/gh", "~/.netrc", "~/.npmrc", "~/.pypirc",
    "~/.git-credentials", "~/.gnupg", "~/Library/Keychains"]
_SECRET_SRC = list(dict.fromkeys(list((POLICY or {}).get("secret_paths", [])) + BASELINE_SECRETS))
SECRET_PATHS = list(dict.fromkeys(os.path.realpath(os.path.expanduser(p)) for p in _SECRET_SRC))
# glob matching can't realpath a pattern, so also keep the un-resolved spelling of every root
SECRET_ROOTS_RAW = list(dict.fromkeys(SECRET_PATHS + [os.path.normpath(os.path.expanduser(p)) for p in _SECRET_SRC]))
# Tier-0/0.5 ledgers injected into every session with override priority (SEC-04): agents never edit an
# existing one directly. Facts go through .claude/hooks/remember.sh (the /remember command).
LEDGERS = ("docs/PROJECT_FACTS.md", "docs/DECISIONS.md")
CWD = os.getcwd()
LIMA = (POLICY or {}).get("lima", {})
LIMA_INSTANCES = LIMA.get("instances") or [LIMA.get("instance", "sdlc")]
# never writable, whatever the patterns say: system namespaces and anything prod-looking
RESERVED_NS = {"default", "kube-system", "kube-public", "kube-node-lease"}

class Deny(Exception): pass
class Ask(Exception): pass
class Confirm(Ask): pass

def deny(msg): raise Deny(msg)
# Two kinds of "ask" (owner decisions 2026-10-06 and 2026-10-07):
#   ask()     soft: unusual but not destructive (network egress, unparseable command, ...). By default it
#             is logged to ASK_LOG and falls through to the normal permission flow; SDLC_GUARD_ASK=prompt
#             makes it prompt again.
#   confirm() destructive or irreversible (deletes, force pushes, volume/DB drops, IAM changes, real-infra
#             apply/destroy). Always prompts, and the exec-time shims block it in scripts.
def ask(msg): raise Ask(msg)
def confirm(msg): raise Confirm(msg)

# ---------------------------------------------------------------- tokenising
SEP_CHARS = set(";&|()\n")
def tokenize(s):
    lx = shlex.shlex(s, posix=True, punctuation_chars=";&|()<>\n")
    lx.whitespace = " \t\r"
    lx.whitespace_split = True
    try:
        return list(lx)
    except ValueError:
        ask("command could not be parsed (unbalanced quotes)")

def segments(s, env):
    """Split into simple commands. Returns items in order: ("seg", argv, stdout_redirected) for a
    command and ("sep", token) for each separator (;, &&, ||, |, &, (, ), newline), so callers can
    follow `cd` and pipes between commands."""
    toks = tokenize(s)
    cur, out, redir = [], [], False
    i = 0
    while i < len(toks):
        t = toks[i]
        if t and all(c in SEP_CHARS for c in t):
            if cur: out.append(("seg", cur, redir))
            out.append(("sep", t))
            cur, redir = [], False
        elif t and all(c in "<>&" for c in t):
            # redirection operator: the next token is its target (or an fd number)
            tgt = toks[i + 1] if i + 1 < len(toks) else ""
            if ">" in t and tgt and not tgt.isdigit() and tgt != "-":
                check_write_target(expand(tgt, env))
            if ">" in t and not (cur and cur[-1] == "2"):
                redir = True                       # stdout goes to a file (or another fd), not down a pipe
            i += 1
        else:
            cur.append(t)
        i += 1
    if cur: out.append(("seg", cur, redir))
    return out

VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::?-([^}]*))?\}|\$([A-Za-z_][A-Za-z0-9_]*)")
def expand(tok, env):
    def rep(m):
        name = m.group(1) or m.group(3)
        if name in env: return env[name]
        if m.group(2) is not None: return m.group(2)
        if name == "HOME": return HOME
        return m.group(0)
    return VAR_RE.sub(rep, tok.replace("~/", HOME + "/", 1) if tok.startswith("~/") else tok)

def nested_bodies(tok):
    bodies = []
    i = tok.find("$(")
    while i != -1:
        depth, j = 1, i + 2
        while j < len(tok) and depth:
            if tok[j] == "(": depth += 1
            elif tok[j] == ")": depth -= 1
            j += 1
        bodies.append(tok[i + 2:j - 1])
        i = tok.find("$(", j)
    bodies += re.findall(r"`([^`]*)`", tok)
    return bodies

# Heredoc bodies are DATA (file contents, python source, notes), not shell commands — except when a
# shell reads them (`bash <<EOF`), and except for $(...) / backticks in an UNQUOTED heredoc, which run.
# A body an interpreter reads (`python3 - <<EOF`) is a program: it is scanned for network I/O.
HEREDOC_RE = re.compile(r"(?<!<)<<(?!<)(-?)[ \t]*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2")
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
INTERP_BODIES = []
def split_heredocs(cmd):
    """Return (cmd without heredoc bodies, bodies a shell executes, unquoted bodies to scan for $(...))."""
    lines, out, shell_bodies, subst_bodies, i = cmd.split("\n"), [], [], [], 0
    while i < len(lines):
        line = lines[i]; out.append(line); i += 1
        for m in HEREDOC_RE.finditer(line):
            dash, quote, delim = m.group(1), m.group(2), m.group(3)
            body = []
            while i < len(lines):
                l = lines[i]; i += 1
                if (l.lstrip("\t") if dash else l).rstrip() == delim: break
                body.append(l)
            text = "\n".join(body)
            words = re.split(r"\|\||&&|[|;&(]", line[:m.start()])[-1].split()
            words = [w for w in words if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", w)]
            consumer = os.path.basename(words[0]) if words else ""
            if consumer in SHELLS and not any(w == "-c" for w in words):
                shell_bodies.append(text)
            else:
                if interpreter_name(consumer):
                    INTERP_BODIES.append((consumer, text))
                if not quote:
                    subst_bodies.append(text)
    return "\n".join(out), shell_bodies, subst_bodies

WRAPPERS = {"timeout", "time", "nice", "nohup", "stdbuf", "command", "builtin", "noglob", "exec", "caffeinate"}
def strip_wrappers(argv, env):
    changed = True
    while argv and changed:
        changed = False
        a0 = os.path.basename(argv[0])
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", argv[0]):
            k, v = argv[0].split("=", 1)
            env[k] = expand(v, env); argv = argv[1:]; changed = True
        elif a0 == "env":
            argv = argv[1:]
            while argv and (argv[0].startswith("-") or "=" in argv[0]):
                if "=" in argv[0] and not argv[0].startswith("-"):
                    k, v = argv[0].split("=", 1); env[k] = expand(v, env)
                argv = argv[1:]
            changed = True
        elif a0 in ("export", "declare", "typeset", "local", "readonly") and all(
                re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", a) or a.startswith("-") for a in argv[1:]):
            # `export KUBECONFIG=...; kubectl ...` — the assignment applies to later segments
            for a in argv[1:]:
                if "=" in a and not a.startswith("-"):
                    k, v = a.split("=", 1); env[k] = expand(v, env)
            argv = []
        elif a0 in ("sudo", "doas", "su"):
            deny("sudo/su is never run by agents (user rule: system-wide changes need the human)")
        elif a0 in WRAPPERS:
            argv = argv[1:]
            if a0 == "timeout":
                while argv and argv[0].startswith("-"): argv = argv[1:]
                if argv and re.match(r"^\d+[smhd]?$", argv[0]): argv = argv[1:]
            if a0 == "nice" and argv[:1] == ["-n"]: argv = argv[2:]
            changed = True
        elif a0 == "xargs":
            argv = argv[1:]
            while argv and argv[0].startswith("-"):
                flag = argv[0]; argv = argv[1:]
                if flag in ("-n", "-I", "-P", "-L", "-s", "-d", "-E") and argv: argv = argv[1:]
            changed = True
    return argv

# ---------------------------------------------------------------- write protection
def under(path, root):
    return path == root or path.startswith(root.rstrip("/") + "/")

def check_write_target(path):
    if not path or path.startswith("/dev/"): return
    p = os.path.realpath(os.path.join(CWD, os.path.expanduser(path)))
    for root in PROTECTED_WRITE:
        if under(p, root):
            deny(f"write to protected path {path} (guard/settings/kubeconfig are human-owned)")
    check_ledger(p, path)

def check_ledger(p, shown):
    """Existing Tier-0/0.5 ledgers are not edited directly (creating one from the template is fine)."""
    for led in LEDGERS:
        if (p.endswith("/" + led) or p == led) and os.path.exists(p):
            how = ("record facts with .claude/hooks/remember.sh (the /remember command)" if led.endswith("FACTS.md")
                   else "return the proposed D-NNN entry in your final message; the ledger is written by its "
                        "writer script or the human, never edited in place by an agent")
            deny(f"{shown} is a ground-truth ledger injected into every session; agents never edit it directly — {how}")

GLOB_CHARS = "*?["
def brace_expand(s, limit=64):
    """Bash-style {a,b} expansion (enough to see through `~/.{ssh,aws}/…`). Past the cap, the brace
    groups are also tried as `*`, so padding a group with many alternatives can't hide `ssh`."""
    m = re.search(r"\{([^{}]*,[^{}]*)\}", s)
    if not m: return [s]
    out = []
    for alt in m.group(1).split(","):
        out += brace_expand(s[:m.start()] + alt + s[m.end():], limit)
        if len(out) >= limit:
            return out[:limit] + [re.sub(r"\{[^{}]*\}", "*", s)]
    return out

def glob_hits_root(pattern, root):
    """True if a shell glob could match `root` or anything beneath it (segment-wise; a `*` never crosses
    `/`, and like the shell a pattern segment only matches a leading '.' if it spells it)."""
    ps = [s for s in os.path.normpath(pattern).split("/") if s]
    rs = [s for s in root.split("/") if s]
    if len(ps) < len(rs):
        return any(s == "**" for s in ps) and all(fnmatch.fnmatchcase(r, s) or s == "**" for s, r in zip(ps, rs))
    for s, r in zip(ps, rs):
        if s == "**": return True
        if r.startswith(".") and not s.startswith("."): return False
        if not fnmatch.fnmatchcase(r, s): return False
    return True

def secret_hit(v, cwd):
    """Return the secret root a (possibly globbed / brace-expanded) path argument reaches, else None."""
    for cand in brace_expand(v):
        p = os.path.join(cwd, os.path.expanduser(cand))
        if any(c in cand for c in GLOB_CHARS):
            for root in SECRET_ROOTS_RAW:
                if glob_hits_root(os.path.normpath(p), root): return root
            continue
        rp = os.path.realpath(p)
        for root in SECRET_PATHS:
            if under(rp, root): return root
    return None

def check_secret_args(argv, env, cwd):
    """Any command naming a secret path (admin kubeconfig, ~/.ssh, cloud creds, gh/npm/pypi/netrc
    tokens, the keychain files) is denied — read or write, spelled literally or as a glob."""
    for t in argv[1:]:
        for part in [t.split("=", 1)[1]] if t.startswith("-") and "=" in t else [t]:
            v = expand(part, env)
            if "/" not in v and not v.startswith("~"):
                continue
            if secret_hit(v, cwd):
                deny(f"{part} is a secret path (admin kubeconfig / ssh / cloud or registry credentials); agents never read or copy it")

DEST_WRITERS = {"cp", "mv", "ln", "install", "rsync", "ditto"}          # last positional is written
ALL_WRITERS = {"rm", "rmdir", "unlink", "shred", "touch", "mkdir", "chmod", "chown", "chflags", "truncate", "tee"}
def check_protected_args(a0, argv, env):
    pos = [expand(t, env) for t in argv[1:] if not t.startswith("-")]
    if a0 in ("sed", "perl") and any(t.startswith("-i") or t == "-pi" for t in argv[1:]):
        targets = pos[1:]
    elif a0 in DEST_WRITERS:
        targets = pos[-1:]
    elif a0 in ALL_WRITERS:
        targets = pos
    elif a0 == "dd":
        targets = [t[3:] for t in pos if t.startswith("of=")]
    else:
        return
    for t in targets:
        check_write_target(t)

# ---------------------------------------------------------------- kube identity
KUBE_VALUE_FLAGS = {"-n", "--namespace", "--context", "--kubeconfig", "--cluster", "--user", "-s", "--server",
    "--token", "--as", "--as-group", "--as-uid", "--certificate-authority", "--client-certificate", "--client-key",
    "--request-timeout", "-v", "--v", "--cache-dir", "--tls-server-name", "-f", "--filename", "-k", "--kustomize",
    "-l", "--selector", "-o", "--output", "-c", "--container", "--field-selector", "--timeout", "--for", "--type",
    "-p", "--patch", "--image", "--replicas", "--from-literal", "--from-file", "--dry-run", "--grace-period",
    "--kube-context", "--kube-apiserver", "--kube-token", "--kube-as-user", "--kube-as-group", "--kube-ca-file",
    "--values", "--set", "--set-string", "--version", "--revision", "--wait-for", "--sort-by", "--since", "--tail",
    "--field-manager", "--template", "-L", "--label-columns"}
IDENTITY_FLAGS = {"--cluster", "--user", "-s", "--server", "--token", "--as", "--as-group", "--as-uid",
    "--certificate-authority", "--client-certificate", "--client-key", "--insecure-skip-tls-verify",
    "--kube-apiserver", "--kube-token", "--kube-as-user", "--kube-as-group", "--kube-ca-file", "--kube-insecure-skip-tls-verify"}

def parse_flags(args):
    flags, pos, i = {}, [], 0
    while i < len(args):
        a = args[i]
        if a == "--":
            pos += args[i + 1:]; break
        if a.startswith("--") and "=" in a:
            k, v = a.split("=", 1); flags.setdefault(k, []).append(v)
        elif a.startswith("-") and len(a) > 1 and not re.match(r"^-\d", a):
            if a in KUBE_VALUE_FLAGS and i + 1 < len(args):
                flags.setdefault(a, []).append(args[i + 1]); i += 1
            elif re.match(r"^-n\S+", a):
                flags.setdefault("-n", []).append(a[2:])
            else:
                flags.setdefault(a, []).append(True)
        else:
            pos.append(a)
        i += 1
    return flags, pos

def fget(flags, *names):
    for n in names:
        if n in flags: return flags[n][-1]
    return None

def ca_sha(ca_b64):
    try: return hashlib.sha256(base64.b64decode(ca_b64)).hexdigest()
    except Exception: return None

def kube_identity(flags, env, tool):
    """Return (context_name, cfg). Deny unless the effective identity is the pinned non-prod cluster."""
    if POLICY is None or "kube" not in POLICY:
        deny("sdlc-guard policy missing: cluster commands are blocked until the human bootstrap writes it")
    kp = POLICY["kube"]
    for f in IDENTITY_FLAGS:
        if f in flags: deny(f"{tool}: identity override flag {f} is not allowed; use the pinned sdlc kubeconfig")
    kc = fget(flags, "--kubeconfig") or env.get("KUBECONFIG") or os.environ.get("KUBECONFIG") or os.path.join(HOME, ".kube/config")
    kc = expand(kc, env)
    if ":" in kc: deny(f"{tool}: multi-file KUBECONFIG ({kc}) is not allowed")
    pinned = os.path.realpath(os.path.expanduser(kp["kubeconfig"]))
    if os.path.realpath(os.path.expanduser(kc)) != pinned:
        deny(f"{tool}: kubeconfig {kc} is not the pinned sdlc kubeconfig ({kp['kubeconfig']}); prod and other clusters are unreachable by design")
    try:
        with open(pinned) as f: cfg = json.load(f)
    except Exception as e:
        deny(f"{tool}: pinned kubeconfig unreadable or not JSON ({e})")
    ctx = fget(flags, "--context", "--kube-context") or cfg.get("current-context")
    if not ctx or PROD_RE.search(ctx): deny(f"{tool}: context '{ctx}' is not allowed")
    allowed = kp.get("contexts", {})
    if ctx not in allowed: deny(f"{tool}: context '{ctx}' is not in the allowlist {sorted(allowed)}")
    c = next((x for x in cfg.get("contexts", []) if x.get("name") == ctx), None)
    if not c: deny(f"{tool}: context '{ctx}' not found in pinned kubeconfig")
    cl = next((x for x in cfg.get("clusters", []) if x.get("name") == c["context"].get("cluster")), None)
    if not cl: deny(f"{tool}: cluster for context '{ctx}' missing")
    want = allowed[ctx]
    server = cl["cluster"].get("server", "")
    if server != want["server"]: deny(f"{tool}: context '{ctx}' points at {server}, expected {want['server']}")
    if want.get("ca_sha256") and ca_sha(cl["cluster"].get("certificate-authority-data", "")) != want["ca_sha256"]:
        deny(f"{tool}: cluster CA does not match the pinned Lima cluster CA (identity check failed)")
    if want.get("user_sha256"):
        us = next((x for x in cfg.get("users", []) if x.get("name") == c["context"].get("user")), {}).get("user", {})
        cred = us.get("token") or us.get("client-certificate-data") or ""
        if hashlib.sha256(cred.encode()).hexdigest() != want["user_sha256"]:
            deny(f"{tool}: the pinned kubeconfig's credential changed (not the agent ServiceAccount token); re-run make-policy if this was intended")
    return ctx, want, c["context"].get("namespace")

def ns_writable(ns, want):
    """Namespaces agents may mutate: exact names or globs from the policy (e.g. "*-dev", "*-qa")."""
    if not ns or ns in RESERVED_NS or ns.startswith("kube-") or PROD_RE.search(ns):
        return False
    return any(fnmatch.fnmatchcase(ns, p) for p in want.get("mutate_namespaces", []))

def ns_hint(want):
    return "|".join(want.get("mutate_namespaces", [])) or "<none configured>"

KUBE_READ = {"get", "describe", "logs", "top", "explain", "api-resources", "api-versions", "version", "cluster-info",
             "diff", "kustomize", "wait", "events", "completion", "plugin", "options", "help", "auth"}
CLUSTER_SCOPED = re.compile(r"^(ns|namespaces?|nodes?|no|clusterroles?|clusterrolebindings?|crds?|customresourcedefinitions?|pv|persistentvolumes?|storageclass(es)?|sc|mutatingwebhookconfigurations?|validatingwebhookconfigurations?|apiservices?|priorityclass(es)?|pc|csidrivers?|runtimeclass(es)?)([./].*)?$", re.I)

EPHEMERAL_KINDS = re.compile(r"^(po|pods?|jobs?(\.batch)?)$", re.I)
KUBE_LOCAL_ONLY = {"completion", "kustomize", "plugin", "options", "help"}
def check_kubectl(argv, env):
    tool = os.path.basename(argv[0])
    flags, pos = parse_flags(argv[1:])
    verb = pos[0] if pos else "help"
    sub = pos[1] if len(pos) > 1 else ""
    if verb in KUBE_LOCAL_ONLY or (verb == "version" and "--client" in flags):
        return
    if verb == "config":
        if sub in ("view", "get-contexts", "current-context", "get-clusters", "get-users", ""):
            if "--raw" in flags or "--flatten" in flags:
                confirm("kubectl config view --raw prints live credentials")
            return
        deny(f"kubectl config {sub} mutates kubeconfig identity; only the human bootstrap may do that")
    ctx, want, ctx_ns = kube_identity(flags, env, tool)
    read = verb in KUBE_READ or (verb == "rollout" and sub in ("status", "history"))
    if read:
        return
    ns = fget(flags, "-n", "--namespace")
    if "-A" in flags or "--all-namespaces" in flags:
        deny(f"kubectl {verb} across all namespaces is not allowed")
    if verb in ("drain", "cordon", "uncordon", "taint", "certificate", "proxy"):
        deny(f"kubectl {verb} is node/cluster-level; not allowed for agents")
    targets = pos[1:]
    if any(CLUSTER_SCOPED.match(t) for t in targets):
        deny(f"kubectl {verb} on a cluster-scoped kind ({' '.join(targets)}); namespaces are created by the human bootstrap and reset with scripts/k8s/env-reset.sh")
    if verb == "delete" and any(f in flags for f in ("--all", "-l", "--selector", "-k", "--kustomize")):
        deny("bulk delete (--all / selector / -k) at the prompt is blocked; use scripts/k8s/env-reset.sh <env>")
    if not ns:
        deny(f"mutating kubectl {verb} must name the namespace explicitly (-n {ns_hint(want)})")
    if not ns_writable(ns, want):
        deny(f"namespace '{ns}' is not writable by agents (allowed: {ns_hint(want)}; never system or prod namespaces)")
    for f in flags.get("-f", []) + flags.get("--filename", []):
        if re.match(r"^https?://", str(f)): ask("applying a manifest fetched from the network")
    if verb == "delete":
        # pods and jobs are recreated by their controllers / re-run by the deploy scripts (system_test_agent
        # kills pods unattended); deleting anything else (deployments, services, PVCs, secrets, ...) is
        # destructive and needs the owner (decision 2026-10-07)
        if not targets:
            kinds = [""]                                         # delete -f/-k: the manifest decides; ask
        elif "/" in targets[0]:
            kinds = [t.split("/", 1)[0] for t in targets]        # delete pod/a job/b
        else:
            kinds = targets[0].split(",")                        # delete pod,job a b
        if not all(EPHEMERAL_KINDS.match(k) for k in kinds):
            confirm(f"kubectl delete {' '.join(targets)} -n {ns}: deleting anything but a pod or job needs the owner")

HELM_READ = {"list", "ls", "status", "get", "history", "hist", "show", "inspect", "template", "lint", "search",
             "repo", "version", "env", "dependency", "dep", "help", "completion", "verify", "pull", "fetch", "plugin"}
def check_helm(argv, env):
    flags, pos = parse_flags(argv[1:])
    verb = pos[0] if pos else "help"
    cluster_read = ("status", "get", "history", "hist", "list", "ls")
    if verb in HELM_READ and verb not in cluster_read:
        return
    ctx, want, _ = kube_identity(flags, env, "helm")
    if verb in cluster_read:
        return
    ns = fget(flags, "-n", "--namespace")
    if not ns_writable(ns, want):
        deny(f"helm {verb} must target a writable namespace explicitly (-n {ns_hint(want)})")
    if verb in ("uninstall", "delete", "del", "un"):
        confirm(f"helm {verb} removes a release and its resources from {ns}; needs the owner")

LIMA_ALLOW_SUB = {"list", "ls", "info", "validate", "help", "--version", "-v", "version", "watch", "completion"}
def check_limactl(argv, env):
    insts = LIMA_INSTANCES
    names = "', '".join(insts)
    a0 = os.path.basename(argv[0])
    if a0 == "lima":
        deny("`lima` targets the 'default' instance; use `limactl shell %s ...`" % insts[0])
    flags, pos = parse_flags(argv[1:])
    if not pos:
        return
    sub = pos[0]
    if sub in LIMA_ALLOW_SUB or (sub in ("template", "snapshot") and pos[1:2] == ["list"]):
        return
    if sub in ("delete", "rm", "remove", "factory-reset", "unprotect", "prune") or (sub == "snapshot" and pos[1:2] in (["delete"], ["apply"])):
        deny(f"limactl {sub} destroys VM state; human-only")
    if sub in ("create",) or (sub == "start" and (len(pos) < 2 or pos[1] not in insts)):
        deny(f"limactl {sub} creating/starting anything but '{names}' is bootstrap-only (the human creates the cluster VMs)")
    if sub in ("start", "stop", "restart", "protect"):
        if len(pos) >= 2 and pos[1] in insts: return
        deny(f"limactl {sub} only on '{names}'")
    if sub in ("copy", "cp"):
        remote = [p for p in pos[1:] if re.match(r"^[A-Za-z0-9_.-]+:", p)]
        if remote and all(p.split(":", 1)[0] in insts for p in remote): return
        deny(f"limactl copy only to/from '{names}'")
    if sub == "shell":
        # limactl shell [flags] INSTANCE [--] CMD...
        rest = argv[argv.index("shell") + 1:]
        while rest and rest[0].startswith("-"):
            f = rest[0]; rest = rest[1:]
            if f in ("--workdir", "--shell") and rest: rest = rest[1:]
        if not rest or rest[0] not in insts: deny(f"limactl shell only into '{names}'")
        inner = rest[1:]
        if inner[:1] == ["--"]: inner = inner[1:]
        if inner[:1] == ["sudo"]: inner = inner[1:]
        line = " ".join(inner)
        allow = LIMA.get("shell_allow", [])
        if any(line == a or line.startswith(a + " ") for a in allow): return
        deny(f"limactl shell {rest[0]} '{line}' is not in the allowlist (root in the VM = cluster-admin)")
    ask(f"limactl {sub} is not a routine agent action")

# ---------------------------------------------------------------- other tools
def check_docker(argv, env):
    a0 = os.path.basename(argv[0])
    args = argv[1:]
    host = env.get("DOCKER_HOST") or os.environ.get("DOCKER_HOST")
    if host and not host.startswith("unix://"): deny(f"DOCKER_HOST={host} points at a remote daemon")
    i = 0
    while i < len(args) and args[i].startswith("-"):
        f = args[i]
        if f in ("-H", "--host", "--context", "-c"):
            v = args[i + 1] if i + 1 < len(args) else ""
            if f in ("-H", "--host") and not v.startswith("unix://"): deny(f"docker {f} {v}: remote daemon")
            if f in ("--context", "-c") and v not in ("default", "desktop-linux"): deny(f"docker --context {v}: non-local daemon")
            i += 2; continue
        if f.startswith(("--host=", "--context=")):
            v = f.split("=", 1)[1]
            if v not in ("default", "desktop-linux") and not v.startswith("unix://"): deny(f"docker {f}: non-local daemon")
        if f in ("--config", "-l", "--log-level"): i += 1
        i += 1
    rest = args[i:]
    if a0 == "docker-compose": rest = ["compose"] + rest
    words = [r for r in rest if not r.startswith("-")]
    if rest[:1] == ["compose"] and "down" in rest and ("-v" in rest or "--volumes" in rest):
        confirm("docker compose down -v deletes volumes (user rule: ask first)")
    if words[:2] in (["volume", "rm"], ["volume", "prune"], ["volume", "remove"]):
        confirm("docker volume deletion (user rule: ask first)")
    if words[:2] == ["system", "prune"] and "--volumes" in rest:
        confirm("docker system prune --volumes (user rule: ask first)")
    if words[:1] in (["login"], ["logout"]) or words[:2] in (["context", "use"], ["context", "create"], ["context", "rm"], ["context", "update"]):
        ask(f"docker {' '.join(words[:2])} changes where images/credentials go")
    if words[:1] == ["push"]:
        ref = words[1] if len(words) > 1 else ""
        reg = ref.split("/")[0] if "/" in ref else "docker.io"
        if reg.split(":")[0] not in LOCAL_HOSTS: ask(f"docker push to {reg} leaves this machine")

# Where a push really goes can be redirected by config: remote URLs and URL rewrites.
GIT_URL_CONFIG = re.compile(r"^(remote\..+\.(url|pushurl)|url\..+\.(insteadof|pushinsteadof))(=|$)", re.I)
PUSH_VALUE_FLAGS = {"-o", "--push-option", "--receive-pack", "--exec", "--repo"}
def push_destination(rest):
    """The <repository> a `git push` names (None = the configured default)."""
    i = 0
    while i < len(rest):
        r = rest[i]
        if r.startswith("--repo="): return r.split("=", 1)[1]
        if r == "--repo" and i + 1 < len(rest): return rest[i + 1]
        if r in PUSH_VALUE_FLAGS: i += 2; continue
        if r == "--": return rest[i + 1] if i + 1 < len(rest) else None
        if r.startswith("-"): i += 1; continue
        return r
    return None

def check_git(argv, env):
    args = argv[1:]
    while args and args[0] in ("-C", "-c", "--git-dir", "--work-tree", "--namespace"):
        if args[0] == "-c" and len(args) > 1 and GIT_URL_CONFIG.match(args[1]):
            ask(f"git -c {args[1]} redirects where git talks to (user rule: non-local network needs approval)")
        args = args[2:]
    while args and args[0].startswith(("--git-dir=", "--work-tree=", "--no-pager", "-P", "--bare")): args = args[1:]
    if not args: return
    sub, rest = args[0], args[1:]
    if sub == "remote" and rest[:1] and rest[0] in ("add", "set-url", "rename"):
        ask(f"git remote {rest[0]} changes where pushes go (exfiltration path; user rule: ask first)")
    if sub == "config" and any(GIT_URL_CONFIG.match(r) for r in rest if not r.startswith("-")) and not any(
            r in ("--get", "--get-all", "--get-regexp", "-l", "--list") for r in rest):
        ask("git config of a remote URL or URL rewrite changes where pushes go (user rule: ask first)")
    if sub == "push":
        dest = push_destination(rest)
        if dest is not None and dest != "origin":
            ask(f"git push to '{dest}', not origin (a new or URL remote is an exfiltration path; user rule: ask first)")
        if any(r in ("--force", "-f", "--force-with-lease", "--force-if-includes", "--mirror", "--delete", "-d", "--prune") or r.startswith(("--force-with-lease=", "+", ":")) for r in rest):
            confirm("git push rewriting/deleting remote refs (user rule: ask first)")
    elif sub == "reset" and "--hard" in rest: confirm("git reset --hard discards work (user rule)")
    elif sub == "clean" and ("--force" in rest or any(r.startswith("-") and not r.startswith("--") and "f" in r for r in rest)):
        confirm("git clean -f deletes untracked files (user rule)")
    elif sub == "checkout" and ("--" in rest or "." in rest or "-f" in rest or "--force" in rest): confirm("git checkout over working-tree changes (user rule)")
    elif sub == "restore" and "--staged" not in rest: confirm("git restore discards working-tree changes (user rule)")
    elif sub == "stash" and rest[:1] in (["drop"], ["clear"]): confirm("git stash drop/clear (user rule)")
    elif sub == "branch" and ("-D" in rest or ("-d" in rest and "--force" in rest)): confirm("git branch -D")
    elif sub in ("filter-branch", "filter-repo") or (sub == "update-ref" and "-d" in rest) or (sub == "reflog" and rest[:1] == ["expire"]):
        confirm(f"git {sub} rewrites history")

def check_rm(argv, env, cwd, scratch):
    flags = [a for a in argv[1:] if a.startswith("-") and a != "-"]
    recursive = any(("r" in f.lstrip("-") or "R" in f) for f in flags if not f.startswith("--")) or "--recursive" in flags
    if not recursive: return
    targets = [expand(a, env) for a in argv[1:] if not a.startswith("-")]
    if not targets: return
    safe_roots = [os.path.realpath(p) for p in ["/tmp", "/private/tmp", "/var/folders", os.environ.get("TMPDIR", "/tmp")] + ([scratch] if scratch else [])]
    for t in targets:
        if "$" in t or "*" in t or "?" in t or "`" in t:
            confirm(f"rm -r with an unresolved/glob target '{t}' (user rule: ask before rm -rf outside /tmp and build artifacts)")
        p = os.path.realpath(os.path.join(cwd, os.path.expanduser(t)))
        if any(under(p, r) for r in safe_roots): continue
        inside_repo = under(p, os.path.realpath(cwd))
        comps = set(os.path.relpath(p, os.path.realpath(cwd)).split(os.sep)) if inside_repo else set()
        if inside_repo and p != os.path.realpath(cwd) and comps & ARTIFACT_DIRS: continue
        confirm(f"rm -r {t} is outside /tmp and build artifacts (user rule: ask first)")

SQL_CLIENTS = {"psql", "mysql", "mariadb", "sqlite3", "mongosh", "mongo", "redis-cli", "cockroach", "clickhouse-client", "dropdb"}
SQL_DESTRUCTIVE = re.compile(r"\bDROP\s+(DATABASE|SCHEMA|TABLE|OWNED|ROLE|USER)\b|\bTRUNCATE\b|\bFLUSH(ALL|DB)\b|dropDatabase\(|\bDELETE\s+FROM\s+[\w.\"]+\s*(;|$|\"|')", re.I)
def check_sql(argv):
    names = {os.path.basename(a) for a in argv}
    if names & SQL_CLIENTS:
        if "dropdb" in names: confirm("dropdb (user rule: ask before DROP DATABASE)")
        text = " ".join(argv)
        if SQL_DESTRUCTIVE.search(text): confirm("destructive SQL (DROP/TRUNCATE/DELETE without WHERE) — user rule: ask first")

NET_TOOLS = {"curl", "wget", "http", "https", "xh", "httpie", "nc", "ncat", "telnet", "ssh", "scp", "sftp", "ftp", "rsync"}
HTTP_VALUE_FLAGS = {"-o", "--output", "-H", "--header", "-d", "--data", "--data-raw", "--data-binary", "--data-urlencode",
    "-X", "--request", "-u", "--user", "-A", "--user-agent", "-e", "--referer", "-b", "--cookie", "-c", "--cookie-jar",
    "-w", "--write-out", "-T", "--upload-file", "-F", "--form", "-m", "--max-time", "--connect-timeout", "--retry",
    "--retry-delay", "--resolve", "--connect-to", "-O", "--output-document", "--header=", "-x", "--proxy", "--cacert", "--cert", "--key"}
def url_hosts(argv, env, a0):
    hosts, skip = [], False
    for a in argv[1:]:
        if skip: skip = False; continue
        if a0 in ("curl", "wget", "http", "https", "xh", "httpie") and (a in HTTP_VALUE_FLAGS or
                (a.startswith("-") and not a.startswith("--") and len(a) > 2 and a[-1] in "oHdXuAebcwTFmxO")):
            skip = True; continue
        a = expand(a, env)
        if a in ("-x", "--proxy"): continue
        m = re.match(r"^[a-z][a-z0-9+.-]*://(\[[^\]]+\]|[^/:?#]+)", a, re.I)
        if m: hosts.append(m.group(1)); continue
        if a.startswith("-"): continue
        if a0 in ("scp", "sftp", "rsync"):
            m = re.match(r"^(?:[\w.-]+@)?([\w.-]+):", a)
            if m: hosts.append(m.group(1))
        elif a0 in ("curl", "wget", "http", "https", "xh", "httpie", "nc", "ncat", "telnet"):
            m = re.match(r"^(\[[^\]]+\]|[\w.-]+)(:\d+)?(/|$)", a)
            if m and ("." in m.group(1) or m.group(1) in LOCAL_HOSTS or m.group(2) or m.group(3)): hosts.append(m.group(1))
    return hosts
SSH_VALUE_FLAGS = set("BbcDEeFIiJLlmOoPpQRSWw")
def ssh_remote_command(argv):
    """The command an `ssh [opts] host cmd...` runs remotely ('' for an interactive login)."""
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--": i += 1; break
        if a.startswith("-") and len(a) > 1:
            if a[-1] in SSH_VALUE_FLAGS and len(a) == 2: i += 1     # -i key, -p 22, -o X=Y …
            i += 1; continue
        break
    return " ".join(argv[i + 1:])
# Remote commands are opaque to the guard; the destructive ones are spotted by name.
REMOTE_DESTRUCTIVE = re.compile(
    r"\brm\s+(-[a-zA-Z]*[rR]|--recursive)|\b(mkfs|wipefs|shred|fdisk|parted)\b|\bdd\s+[^|;&]*\bof=|"
    r"\b(shutdown|reboot|halt|poweroff)\b|\bkubectl\s+[^|;&]*\bdelete\b|\bhelm\s+(uninstall|delete)\b|"
    r"\bdocker\s+(volume\s+(rm|prune)|system\s+prune)|\bcompose\s+[^|;&]*down\s+[^|;&]*(-v\b|--volumes)|"
    r"\bDROP\s+(DATABASE|SCHEMA|TABLE)\b|\bTRUNCATE\b|\bdropdb\b|\blimactl\s+(delete|rm|factory-reset)\b|"
    r"\bgit\s+(reset\s+--hard|clean\s+-[a-z]*f|push\s+[^|;&]*(--force|-f\b))", re.I)

def check_network(argv, env):
    a0 = os.path.basename(argv[0])
    if a0 not in NET_TOOLS: return
    if a0 in ("ssh",):
        remote = ssh_remote_command(argv)
        m = REMOTE_DESTRUCTIVE.search(remote)
        if m:
            confirm(f"ssh runs a destructive command on the remote host ('{m.group(0).strip()}'); needs the owner")
        ask("ssh leaves this machine unless proven otherwise (user rule)")
    hosts = url_hosts(argv, env, a0)
    if not hosts and a0 in ("curl", "wget", "http", "https", "xh", "httpie") and any("$" in expand(a, env) for a in argv[1:] if not a.startswith("-")):
        ask(f"{a0} target is an unresolved variable (user rule: non-localhost network needs approval)")
    for h in hosts:
        h2 = h.strip("[]").lower()
        if "$" in h2: ask(f"{a0} to an unresolved host '{h}' (user rule: non-localhost network needs approval)")
        if h2 in LOCAL_HOSTS or h2.endswith(".localhost") or h2.startswith("127."): continue
        ask(f"{a0} to {h} leaves this machine (user rule: ask first; use WebFetch for docs)")

# Interpreter one-liners (`node -e`, `python3 -c`, …) and interpreter-fed heredocs are programs the
# CLI-name checks above can't see into. Code that talks to the network is asked about (SEC-03).
INTERP_CODE_FLAGS = {  # interpreter -> (long flags taking code, short-flag letters that take code)
    "node": ({"--eval", "--print"}, "ep"), "nodejs": ({"--eval", "--print"}, "ep"), "bun": ({"--eval", "--print"}, "ep"),
    "python": (set(), "c"), "ruby": (set(), "e"), "perl": (set(), "eE"), "php": (set(), "r"),
}
def interpreter_name(a0):
    a0 = os.path.basename(a0)
    if re.match(r"^python[0-9.]*$", a0): return "python"
    if a0 in INTERP_CODE_FLAGS or a0 == "deno": return a0
    return None
URL_LIT_RE = re.compile(r"\b(?:https?|wss?|ftp)://(\[[^\]]+\]|[^/:?#\s'\"`)\\]+)", re.I)
NET_CODE_RE = re.compile(r"\bhttps?\b|\bsocket|stream_socket|\bfetch\b|\brequests\b|\burllib|\bhttpx\b|aiohttp"
    r"|\bnet::|net/http|\bcurl\b|\baxios\b|\bdgram\b|websocket|xmlhttprequest|\bnet\.(?:connect|createConnection|Socket)\b"
    r"|require\(\s*['\"](?:node:)?(?:net|tls|dgram)['\"]|\bLWP\b|open-uri|fsockopen|\bsmtplib\b|\bftplib\b|\bparamiko\b", re.I)
def is_local_host(h):
    h = h.strip("[]").lower()
    return h in LOCAL_HOSTS or h.endswith(".localhost") or h.startswith("127.")
def network_in_code(code):
    """Why this code does network I/O (a remote URL literal or a network API), or None."""
    remote = [h for h in URL_LIT_RE.findall(code) if not is_local_host(h)]
    if remote: return f"a URL to {remote[0]}"
    m = NET_CODE_RE.search(URL_LIT_RE.sub(" ", code))
    return f"'{m.group(0)}'" if m else None
def check_interpreter(argv):
    kind = interpreter_name(argv[0])
    if not kind: return
    if kind == "deno":
        code_given = argv[1:2] == ["eval"]
    else:
        longs, letters = INTERP_CODE_FLAGS[kind]
        code_given = any(a in longs or a.split("=", 1)[0] in longs or
                         (re.match(r"^-[A-Za-z]+$", a) and a[-1] in letters) for a in argv[1:])
    if not code_given: return
    why = network_in_code(" ".join(argv[1:]))
    if why:
        ask(f"{os.path.basename(argv[0])} one-liner does network I/O ({why}); network egress from inline code "
            "needs approval (use curl for localhost checks)")

KEYCHAIN_READ = {"find-generic-password", "find-internet-password", "dump-keychain", "export"}
def check_keychain(argv):
    if os.path.basename(argv[0]) == "security" and argv[1:2] and argv[1] in KEYCHAIN_READ:
        deny(f"security {argv[1]} reads the macOS Keychain (stored passwords, tokens, keys); agents never read it")

CLOUD_DENY = {"gcloud", "az", "doctl", "flyctl", "fly", "heroku", "vercel", "netlify", "railway", "eksctl", "kops", "oci", "ibmcloud",
              # AWS credential brokers: they mint real-account sessions for whatever runs under them
              "aws-vault", "saml2aws", "aws-sso-util", "aws-iam-authenticator"}
# terraform/tofu subcommands that never touch a backend or provider credentials (`init` only with
# -backend=false). Everything else reads real state or infrastructure: plan, refresh, output, show,
# state, console, import, test (which can create resources), workspace, login, init with a backend, ...
TF_OFFLINE = {"fmt", "validate", "version", "help", "providers", "graph", "get", "metadata"}
def check_cloud(argv, env):
    a0 = os.path.basename(argv[0])
    if a0 in CLOUD_DENY and not (argv[1:2] in (["--version"], ["version"], ["help"], ["--help"])):
        deny(f"{a0} reaches real cloud accounts; prod is unreachable by policy")
    if a0 in ("terraform", "tofu", "pulumi", "cdk", "terragrunt"):
        words = [a for a in argv[1:] if not a.startswith("-")]
        if words[:1] and words[0] in ("apply", "destroy", "import", "up", "deploy", "taint") or words[:2] == ["state", "rm"]:
            confirm(f"{a0} {words[0]} changes real infrastructure")
        if a0 in ("terraform", "tofu") and words:
            if words[0] == "init":
                if not any(a in ("-backend=false", "--backend=false") for a in argv[1:]):
                    ask(f"{a0} init without -backend=false opens the remote state backend with real cloud credentials (offline checks: init -backend=false, validate, fmt)")
            elif words[0] not in TF_OFFLINE:
                ask(f"{a0} {words[0]} reads or changes real state/infrastructure with cloud credentials (agents run fmt, validate, init -backend=false)")
    if a0 in ("npm", "pnpm", "yarn") and argv[1:2] == ["publish"] or a0 in ("twine",) or (a0 == "cargo" and argv[1:2] == ["publish"]):
        confirm("publishing a package leaves this machine (irreversible)")
    if a0 == "claude" and any(a in ("--dangerously-skip-permissions", "--allow-dangerously-skip-permissions") for a in argv):
        deny("agents may not launch unguarded Claude sessions")

def check_crane(argv, env):
    """crane against a registry that isn't on this machine: pushing, copying or tagging there is a release
    step (ECR promotion is promote-eks.sh / deploy-eks.sh, run by a human or CI), and even a read is
    non-local network. localhost:5001 (the lab registry, via its forward) stays allowed."""
    if os.path.basename(argv[0]) != "crane": return
    for a in argv[1:]:
        a = expand(a, env)
        if a.startswith(("-", "/", ".", "~")) or "/" not in a: continue
        host = a.split("/")[0]
        if not ("." in host or ":" in host or host == "localhost"): continue   # linux/amd64, repo/name
        h = host.rsplit(":", 1)[0].strip("[]").lower() if not host.startswith("[") else host.split("]")[0].strip("[").lower()
        if h in LOCAL_HOSTS or h.endswith(".localhost") or h.startswith("127."): continue
        ask(f"crane against {host} leaves this machine (a remote registry push/copy/tag is a release step for a human or CI)")

# Release scripts for the EKS environments (staging, prod): human or CI only, like /deploy --target=staging|prod.
# Their kubectl/aws/crane calls would be refused one by one anyway (EKS is not the pinned kubeconfig, aws
# is not LocalStack); this says why up front.
EKS_SCRIPTS = re.compile(r"(^|/)(deploy-eks|promote-eks|eks-bootstrap|eks-outputs)\.sh$")
ENV_SCRIPTS = {"deploy.sh", "seed.sh", "env-reset.sh", "smoke.sh"}
def check_release_scripts(argv):
    a = argv
    if os.path.basename(a[0]) in ("bash", "sh", "zsh", "dash") and len(a) > 1 and not a[1].startswith("-"):
        a = a[1:]
    if EKS_SCRIPTS.search(a[0]):
        deny(f"{os.path.basename(a[0])} acts on the EKS staging/prod environments: a human (or the CI deploy workflow) runs it, never an agent")
    if os.path.basename(a[0]) in ENV_SCRIPTS and any(PROD_RE.search(x) or x == "staging" for x in a[1:]):
        deny(f"{os.path.basename(a[0])} {' '.join(a[1:])}: staging/prod deploys are human-only (agents deploy dev and qa)")

def check_kind_k3d(argv):
    a0 = os.path.basename(argv[0]); words = [a for a in argv[1:] if not a.startswith("-")]
    if a0 == "kind" and (words[:1] == ["delete"] or words[:2] == ["export", "kubeconfig"]): confirm(f"kind {' '.join(words[:2])}")
    if a0 == "k3d" and (words[:2] in (["cluster", "delete"], ["cluster", "stop"]) or words[:2] == ["kubeconfig", "merge"]): confirm(f"k3d {' '.join(words[:2])}")

def check_chmod(argv):
    if os.path.basename(argv[0]) == "chmod" and any(a in ("777", "a+rwx", "ugo+rwx", "0777") for a in argv[1:]):
        confirm("chmod 777 (user rule: ask first)")

# ---------------------------------------------------------------- shell state: cwd (cd) and exported vars
class ShellState:
    """What a command line does to its own environment, followed segment by segment: the directory
    later commands run in (`cd`/`pushd`) and the variables it exports or unsets. `cands` is every
    directory a segment could be running in (None = unknown); anything decided by cwd needs ALL of
    them to qualify, so a `cd` that may have failed, ran in a subshell or a pipeline only widens it."""
    def __init__(self, cwd):
        self.cands = frozenset([os.path.realpath(cwd)])
        self.stack, self.pending = [], None
        self.exported, self.unset = {}, set()
    def copy(self):
        c = ShellState.__new__(ShellState)
        c.cands, c.stack, c.pending = self.cands, list(self.stack), None
        c.exported, c.unset = dict(self.exported), set(self.unset)
        return c
    def on_sep(self, tok):
        # shlex glues adjacent operators into one token (");", "&&(" …): apply them one at a time
        for sep in re.findall(r"&&|\|\||\|&|;;|[;&|()\n]", tok):
            self._on_sep(sep)
    def _on_sep(self, sep):
        if sep == "(":
            self.stack.append(self.cands); self.pending = None
        elif sep == ")":
            outer = self.stack.pop() if self.stack else self.cands
            self.cands = outer | self.cands; self.pending = None   # a subshell's cd may or may not have run
        elif self.pending is not None:
            # `cd X && cmd`: cmd runs in X. After ; || | & or a newline, the cd may have failed (or ran
            # in a pipeline subshell), so both the old and the new directory remain possible.
            self.cands = self.pending if sep == "&&" else (self.cands | self.pending)
            self.pending = None
    def var(self, name, prefix=None):
        if prefix and name in prefix: return prefix[name]
        if name in self.exported: return self.exported[name]
        if name in self.unset: return None
        return os.environ.get(name)
    def after_segment(self, seg, argv, env):
        a0 = os.path.basename(argv[0]) if argv else ""
        if seg[:1] in (["export"],) or (seg[:1] in (["declare"], ["typeset"]) and "-x" in seg):
            for a in seg[1:]:
                if "=" in a and not a.startswith("-"):
                    k, v = a.split("=", 1); self.exported[k] = expand(v, env); self.unset.discard(k)
        if a0 == "unset":
            for a in argv[1:]:
                if not a.startswith("-"): self.unset.add(a); self.exported.pop(a, None)
        if a0 in ("cd", "pushd", "popd"):
            args = [expand(a, env) for a in argv[1:] if a not in ("-L", "-P", "-e", "-@", "--")]
            if a0 == "popd" or (args and (args[0] == "-" or any(c in args[0] for c in "$`*?["))):
                new = frozenset([None])
            else:
                tgt = args[0] if args else HOME
                if not tgt.startswith(("/", "~", ".")) and os.environ.get("CDPATH"):
                    new = frozenset([None])                                  # CDPATH could send it anywhere
                else:
                    tgt = os.path.expanduser(tgt)
                    new = frozenset(None if c is None else os.path.realpath(os.path.join(c, tgt)) for c in self.cands)
            self.pending = new

def leading_assignments(seg, env):
    """VAR=value words that apply to this command only (`AWS_PROFILE=x aws …`, `env AWS_PROFILE=x aws …`)."""
    out = {}
    for t in seg:
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t):
            k, v = t.split("=", 1); out[k] = expand(v, env)
        elif os.path.basename(t) in WRAPPERS or t == "env" or t.startswith("-") or re.match(r"^\d+[smhd]?$", t):
            continue
        else:
            break
    return out

# ---------------------------------------------------------------- aws
# Default: aws is denied unless it targets LocalStack. A project listed under "aws.projects" in the
# policy gets the real AWS CLI, every service and region, when the command runs inside that project
# (hook cwd + any cd in the command). Credential-printing calls stay denied everywhere; services in
# ask_services and actions in ask_actions prompt. See docs/PERMISSIONS_GUIDE.md "AWS for your projects".
AWS = (POLICY or {}).get("aws") or {}
DEFAULT_AWS_ASK_SERVICES = ["iam", "organizations", "account", "sso-admin", "identitystore", "eks"]
AWS_VALUE_OPTS = {"--profile", "--region", "--endpoint-url", "--output", "--query", "--cli-read-timeout",
                  "--cli-connect-timeout", "--color", "--ca-bundle", "--cli-binary-format"}
AWS_BOOL_OPTS = {"--no-verify-ssl", "--no-paginate", "--no-sign-request", "--no-cli-pager", "--cli-auto-prompt",
                 "--no-cli-auto-prompt", "--version", "--debug"}
# calls whose output IS a credential (keys, session tokens, registry/db passwords): denied in every
# project unless the policy lists them in allow_credential_actions
AWS_CRED_ACTIONS = {"sts:get-session-token", "sts:assume-role", "sts:assume-role-with-saml",
    "sts:assume-role-with-web-identity", "sts:get-federation-token", "sts:assume-root", "sso:get-role-credentials",
    "ecr:get-authorization-token", "ecr-public:get-authorization-token", "ecr:get-login", "codeartifact:get-authorization-token",
    "rds:generate-db-auth-token", "redshift:get-cluster-credentials", "redshift:get-cluster-credentials-with-iam",
    "cognito-identity:get-credentials-for-identity", "ecr:get-login-password", "ecr-public:get-login-password"}
# never, whatever the policy says: the CLI's own credential dumps, and EKS kube credentials (the agent
# kubeconfig is pinned to the lab; staging/prod EKS is human/CI only)
AWS_NEVER = {"configure:export-credentials", "eks:get-token", "eks:update-kubeconfig"}
AWS_SECRET_KEY_RE = re.compile(r"(^|\.)(aws_secret_access_key|aws_session_token|aws_security_token|credential_process|[a-z_]*secret[a-z_]*|[a-z_]*token[a-z_]*)$", re.I)
# variables that replace the profile's credentials or config, so a profile pin could not hold
AWS_CRED_ENV = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_SECURITY_TOKEN",
                "AWS_CONFIG_FILE", "AWS_SHARED_CREDENTIALS_FILE", "AWS_WEB_IDENTITY_TOKEN_FILE", "AWS_ROLE_ARN",
                "AWS_CONTAINER_CREDENTIALS_FULL_URI", "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI")
LOGIN_STDIN = {("docker", "login"), ("podman", "login"), ("nerdctl", "login"), ("finch", "login"), ("oras", "login"),
               ("skopeo", "login"), ("crane", "auth"), ("helm", "registry")}

AWS_READ_OP = re.compile(r"^(describe|list|get|wait|help|batch-get|lookup|search|simulate|generate-credential-report)(-|$)")
AWS_DESTRUCTIVE_OP = re.compile(r"^(delete|terminate|remove|deregister|purge|destroy|release|schedule-key-deletion)(-|$)")
def aws_destructive(svc, op, pos):
    if AWS_DESTRUCTIVE_OP.match(op): return True
    if svc == "s3" and op in ("rm", "rb"): return True
    if svc == "s3" and op == "sync" and "--delete" in pos: return True
    return False

def aws_parse(argv, env):
    """-> (global options, [service, operation, args...]) or ask when the service can't be told apart."""
    # `aws $AWSOPTS ec2 …` with AWSOPTS="--profile p --region r": an unquoted variable word-splits
    flat = [argv[0]]
    for a in argv[1:]:
        e = expand(a, env)
        try:
            flat += shlex.split(e) if ("$" in a and e != a and " " in e) else [a]
        except ValueError:
            flat.append(a)
    argv = flat
    opts, pos, i = {}, [], 1
    while i < len(argv):
        a = expand(argv[i], env)
        if a.startswith("--"):
            k, eq, v = a.partition("=")
            if k in AWS_VALUE_OPTS:
                if not eq:
                    v = expand(argv[i + 1], env) if i + 1 < len(argv) else ""; i += 1
                opts[k] = v
            elif k in AWS_BOOL_OPTS:
                opts[k] = True
            elif len(pos) < 2 and not (pos[:1] == ["configure"] or pos[:1] == ["help"]):
                ask(f"aws: cannot tell the service/operation apart from option {k} (put global options after the operation)")
            elif eq:
                pos.append(v)                    # --user-data=file://… : the value is an argument like any other
        else:
            pos.append(a)
        i += 1
    return opts, pos

def aws_project(st):
    """The policy project every directory this command may run in lies inside, else None."""
    if not st.cands or None in st.cands: return None
    for pr in AWS.get("projects", []) or []:
        root = os.path.realpath(os.path.expanduser(str(pr.get("path", ""))))
        if root in ("/", os.path.realpath(HOME)) or not pr.get("path"): continue
        if all(under(c, root) for c in st.cands): return pr
    return None

def aws_setting(pr, key, default):
    if key in pr: return pr[key]
    if key in AWS: return AWS[key]
    return default

def aws_config_section(profile, cfg_path):
    import configparser
    cp = configparser.RawConfigParser(strict=False)
    try: cp.read(cfg_path)
    except Exception: return {}
    name = "default" if profile == "default" else f"profile {profile}"
    if cp.has_section(name): return dict(cp.items(name))
    if profile == "default" and cp.has_section("profile default"): return dict(cp.items("profile default"))
    return {}

def aws_account_of(profile, cfg_path):
    """The account a profile acts in, from the CLI config file only (never credentials, never a network
    call): sso_account_id, or the account in role_arn. None when it isn't written down there."""
    sec = aws_config_section(profile, cfg_path)
    if sec.get("sso_account_id"): return sec["sso_account_id"].strip()
    m = re.match(r"^arn:aws[a-z-]*:iam::(\d{12}):", sec.get("role_arn", "").strip())
    return m.group(1) if m else None

def piped_to_login(nxt):
    """True when the next pipeline stage is a registry login reading the password from stdin."""
    if not nxt: return False
    argv = [a for a in nxt if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", a)]
    while argv and os.path.basename(argv[0]) in WRAPPERS: argv = argv[1:]
    if len(argv) < 2: return False
    words = [a for a in argv[1:] if not a.startswith("-")]
    tool = os.path.basename(argv[0])
    sub = (tool, words[0]) if words else (tool, "")
    if sub not in LOGIN_STDIN: return False
    if tool in ("crane", "helm") and words[1:2] != ["login"]: return False
    return "--password-stdin" in argv

def check_aws(argv, env, st, prefix, redirected, pipe_next):
    opts, pos = aws_parse(argv, env)
    if not pos or pos[0] == "help" or (len(pos) <= 3 and pos[-1] == "help"):
        return                                                           # local help/version output
    svc, op = pos[0], (pos[1] if len(pos) > 1 else "")
    action = f"{svc}:{op}"
    if opts.get("--debug"):
        deny("aws --debug logs signed request headers (session token included); run without --debug")
    if action in AWS_NEVER:
        why = ("prints the CLI's credentials" if svc == "configure" else
               "creates EKS kube credentials; the agent kubeconfig is pinned to the lab and EKS staging/prod is human/CI only")
        deny(f"aws {svc} {op} {why}; agents never run it")
    if svc == "configure" and op == "get" and len(pos) > 2 and AWS_SECRET_KEY_RE.search(pos[2]):
        deny(f"aws configure get {pos[2]} prints a credential; agents never read AWS secrets")
    ep = opts.get("--endpoint-url")
    if ep and re.match(r"^https?://(localhost|127\.0\.0\.1|localstack)(:\d+)?(/|$)", ep):
        return                                                           # LocalStack: allowed everywhere
    pr = aws_project(st)
    if pr is None and AWS.get("anywhere"):
        pr = {}                                   # aws.anywhere: the real CLI from any directory, global settings
    if pr is None:
        hint = (" (aws.projects in the guard policy lists the projects where the real CLI is allowed; this command "
                "is not running inside one; aws.anywhere allows it everywhere)" if AWS.get("projects") else "")
        deny("aws without --endpoint-url http://localhost:* (LocalStack) is blocked; prod is unreachable by policy" + hint)
    where = f"project {pr.get('path')}" if pr.get("path") else "any directory (aws.anywhere)"
    if any(c in svc + op for c in "$`*?["):
        ask(f"aws {svc} {op}: the service/operation is an unresolved variable or glob, so the guard can't check it")
    # -- identity: profile pin, then (optional) account pin, then region list
    profiles = [str(p) for p in pr.get("profiles", []) or []]
    accounts = [str(a) for a in pr.get("accounts", []) or []]
    if profiles or accounts:
        for k in AWS_CRED_ENV:
            # config-file locations count only when the command sets them; the session's own are the owner's
            v = st.var(k, prefix) if k not in ("AWS_CONFIG_FILE", "AWS_SHARED_CREDENTIALS_FILE") else \
                (prefix.get(k) or st.exported.get(k))
            if v:
                deny(f"aws in {where}: {k} is set, which overrides the profile's credentials or config; the policy pins "
                     f"{'profiles ' + ', '.join(profiles) if profiles else 'accounts'}, so unset it and use --profile")
    if opts.get("--profile"):
        eff = {opts["--profile"]}
    else:
        eff = {v for v in (st.var("AWS_PROFILE", prefix), st.var("AWS_DEFAULT_PROFILE", prefix)) if v} or {"default"}
    if profiles:
        bad = sorted(p for p in eff if p not in profiles)
        if bad:
            deny(f"aws in {where} uses profile '{bad[0]}'; the policy allows only {', '.join(profiles)} (pass --profile)")
    if accounts:
        cfg = os.path.expanduser(os.environ.get("AWS_CONFIG_FILE") or "~/.aws/config")
        for p in sorted(eff):
            acct = aws_account_of(p, cfg)
            if acct is None:
                deny(f"aws in {where}: the account of profile '{p}' is not in the AWS config file (no sso_account_id or "
                     "role_arn), so the account pin can't be checked offline; pin profiles instead of accounts")
            if acct not in accounts:
                deny(f"aws in {where}: profile '{p}' acts in account {acct}; the policy allows only {', '.join(accounts)}")
    regions = aws_setting(pr, "regions", "*")
    if isinstance(regions, str) and regions != "*": regions = [regions]
    if regions not in ("*", ["*"], None):
        reg = opts.get("--region") or st.var("AWS_REGION", prefix) or st.var("AWS_DEFAULT_REGION", prefix)
        if not reg:
            cfg = os.path.expanduser(os.environ.get("AWS_CONFIG_FILE") or "~/.aws/config")
            reg = aws_config_section(sorted(eff)[0], cfg).get("region") if len(eff) == 1 else None
        if not reg:
            deny(f"aws in {where}: no region given and the policy limits regions to {', '.join(regions)} (pass --region)")
        if not any(fnmatch.fnmatchcase(reg, r) for r in regions):
            deny(f"aws in {where}: region {reg} is outside the policy's regions ({', '.join(regions)})")
    # -- files: file:// inputs that are secrets, s3 downloads onto protected paths
    for a in pos[2:] + [v for k, v in opts.items() if isinstance(v, str)]:
        m = re.match(r"^fileb?://(.+)$", a)
        if m and secret_hit(m.group(1), CWD):
            deny(f"{a} is a secret path; agents never read or upload it")
    if svc == "s3" and op in ("cp", "mv", "sync"):
        locs = [a for a in pos[2:] if not a.startswith("s3://") and not a.startswith("-")]
        if locs and len(pos) >= 4 and not pos[-1].startswith("s3://"):
            check_write_target(pos[-1])
    # -- credentials printed to stdout
    allow_cred = set(aws_setting(pr, "allow_credential_actions", []) or [])
    if action in AWS_CRED_ACTIONS and action not in allow_cred:
        if op == "get-login-password" and not redirected and piped_to_login(pipe_next):
            pass                                  # `aws ecr get-login-password | docker login --password-stdin …`
        elif op == "get-login-password" and SHIM_STDOUT_PIPE and pipe_next is None and not redirected:
            pass                                  # exec-time shim inside a script: stdout is a pipe (consumer unseen)
        elif op == "get-login-password":
            deny(f"aws {svc} {op} prints a registry password; allowed only piped straight into "
                 "`docker login --password-stdin` (or crane/helm/oras/podman login --password-stdin)")
        else:
            deny(f"aws {svc} {op} prints temporary credentials to the transcript; agents don't run it "
                 f"(the owner can list '{action}' in aws.allow_credential_actions)")
    # -- prompts: prod-looking names, the ask list, CLI config changes
    if aws_setting(pr, "ask_prod_names", True):
        for v in sorted(eff) + pos[2:]:
            if v and PROD_RE.search(v):
                confirm(f"aws {svc} {op} names '{v}', which looks like a production resource (policy: aws.ask_prod_names)")
    ask_services = aws_setting(pr, "ask_services", DEFAULT_AWS_ASK_SERVICES) or []
    if any(fnmatch.fnmatchcase(svc, s) for s in ask_services) and not AWS_READ_OP.match(op):
        confirm(f"aws {svc} {op}: {svc} is in the policy's ask_services (account-wide identity/permission changes); "
                "reads pass, changes need the owner; the owner can empty aws.ask_services to allow them")
    if aws_setting(pr, "confirm_destructive", True) and aws_destructive(svc, op, [expand(a, env) for a in argv]):
        confirm(f"aws {svc} {op} deletes or terminates resources; needs the owner "
                "(aws.confirm_destructive: false in the policy lets a project's scripts do it unattended)")
    for pat in aws_setting(pr, "ask_actions", []) or []:
        if fnmatch.fnmatchcase(action, pat):
            confirm(f"aws {svc} {op} matches '{pat}' in the policy's ask_actions")
    if svc == "configure" and op not in ("list", "list-profiles", "get"):
        confirm(f"aws configure {op or ''} changes which credentials/profiles the CLI uses (human step)".replace("  ", " "))
    if svc == "sso" and op in ("login", "logout"):
        ask(f"aws sso {op} is an interactive sign-in (human step)")

# ---------------------------------------------------------------- driver
KUBE_TOOLS = {"kubectl", "kubecolor", "oc", "stern"}
def check_command(cmd, cwd, scratch, depth=0, env=None, st=None):
    if depth > 4: ask("command nesting too deep to analyse")
    env = dict(env or {})
    st = st.copy() if st else ShellState(cwd)
    seen = len(INTERP_BODIES)
    cmd, shell_bodies, subst_bodies = split_heredocs(cmd)
    for consumer, body in INTERP_BODIES[seen:]:
        why = network_in_code(body)
        if why:
            ask(f"{consumer} script from a heredoc does network I/O ({why}); network egress from inline code needs approval")
    for b in shell_bodies:
        check_command(b, cwd, scratch, depth + 1, env, st)
    for b in subst_bodies:
        for body in nested_bodies(b):
            check_command(body, cwd, scratch, depth + 1, env, st)
    items = segments(cmd, env)
    for idx, item in enumerate(items):
        if item[0] == "sep":
            st.on_sep(item[1]); continue
        seg, redirected = item[1], item[2]
        for tok in seg:
            for body in nested_bodies(tok):
                check_command(body, cwd, scratch, depth + 1, env, st)
        prefix = leading_assignments(seg, env)
        argv = strip_wrappers(list(seg), env)   # consumes VAR=value prefixes / standalone assignments into env
        if not argv:
            st.after_segment(seg, argv, env); continue
        argv[0] = expand(argv[0], env)
        if "$" in argv[0]: ask(f"command name is an unresolved variable ({argv[0]})")
        a0 = os.path.basename(argv[0])
        if a0 in ("bash", "sh", "zsh", "dash") and "-c" in argv:
            i = argv.index("-c")
            if i + 1 < len(argv): check_command(argv[i + 1], cwd, scratch, depth + 1, env, st)
            continue
        if a0 == "eval":
            check_command(" ".join(argv[1:]), cwd, scratch, depth + 1, env, st); continue
        check_protected_args(a0, argv, env)
        check_secret_args(argv, env, cwd)
        check_keychain(argv)
        check_interpreter(argv)
        if a0 in KUBE_TOOLS: check_kubectl(argv, env)
        elif a0 == "helm": check_helm(argv, env)
        elif a0 in ("kubectx", "kubens", "k9s"): deny(f"{a0} changes/uses ambient kube context; use kubectl with the pinned KUBECONFIG and an explicit -n")
        elif a0 in ("limactl", "lima"): check_limactl(argv, env)
        elif a0 in ("docker", "docker-compose"): check_docker(argv, env)
        elif a0 == "git": check_git(argv, env)
        elif a0 == "rm": check_rm(argv, env, cwd, scratch)
        elif a0 == "find" and ("-delete" in argv or ("-exec" in argv and "rm" in argv)): confirm("find -delete/-exec rm (user rule: ask before bulk deletion)")
        aws_argv = argv if a0 == "aws" else (["aws"] + argv[3:] if interpreter_name(a0) == "python" and argv[1:3] == ["-m", "awscli"] else None)
        if aws_argv:
            nxt = None
            if idx + 2 < len(items) and items[idx + 1] == ("sep", "|") or idx + 2 < len(items) and items[idx + 1] == ("sep", "|&"):
                nxt = items[idx + 2][1] if items[idx + 2][0] == "seg" else None
            check_aws(aws_argv, env, st, prefix, redirected, nxt)
        check_sql(argv)
        check_network(argv, env)
        check_cloud(argv, env)
        check_crane(argv, env)
        check_release_scripts(argv)
        check_kind_k3d(argv)
        check_chmod(argv)
        st.after_segment(seg, argv, env)

def check_skill(ti):
    name = str(ti.get("skill", "")); args = str(ti.get("args", ""))
    if re.search(r"(^|:)(deploy|rollback)$", name) and re.search(r"--target[= ](prod|production|staging)", args):
        deny(f"/{name} {args}: staging/prod deploys are human-only")

def check_write(tool, ti):
    fp = ti.get("file_path", "") or ti.get("notebook_path", "")
    check_write_target(fp)
    body = str(ti.get("content", "")) + str(ti.get("new_string", ""))
    if fp.endswith((".claude/settings.json", ".claude/settings.local.json")) and "disableAllHooks" in body:
        deny("disableAllHooks would switch off the guard")

def check_read(ti, tool=""):
    for k in ("file_path", "path", "notebook_path"):
        v = ti.get(k)
        if not v: continue
        if secret_hit(expand(str(v), {}), CWD):
            deny(f"{v} is a secret path (admin kubeconfig / ssh / cloud or registry credentials); agents never read it")
    pat = str(ti.get("pattern", "") or "")
    if tool == "Glob" and pat.startswith(("/", "~", "$HOME")) and secret_hit(expand(pat, {}), CWD):   # absolute Glob pattern
        deny(f"glob {pat} reaches a secret path; agents never read it")

ASK_PASSTHROUGH = os.environ.get("SDLC_GUARD_ASK", "passthrough") != "prompt"
ASK_LOG = os.environ.get("SDLC_GUARD_ASK_LOG", os.path.expanduser("~/.claude/sdlc-guard-asks.log"))
def log_ask(tool, ti, reason):
    try:
        import datetime
        what = ti.get("command") or ti.get("file_path") or ti.get("skill") or ""
        with open(ASK_LOG, "a") as f:
            f.write(json.dumps({"ts": datetime.datetime.now().isoformat(timespec="seconds"), "tool": tool,
                                "reason": reason, "input": str(what)[:2000], "cwd": CWD}) + "\n")
    except Exception:
        pass

SHIM_STDOUT_PIPE = False
def main():
    global CWD, SHIM_STDOUT_PIPE
    data = json.load(sys.stdin)
    SHIM_STDOUT_PIPE = data.get("stdout_is_pipe") is True
    tool = data.get("tool_name", ""); ti = data.get("tool_input", {}) or {}
    cwd = data.get("cwd") or os.getcwd(); scratch = data.get("scratchpad_dir")
    CWD = cwd
    try:
        if tool in ("Bash", "Monitor"): check_command(ti.get("command", ""), cwd, scratch)
        elif tool == "Skill": check_skill(ti)
        elif tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"): check_write(tool, ti); check_read(ti)
        elif tool in ("Read", "Grep", "Glob"): check_read(ti, tool)
    except Deny as e:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                          "permissionDecisionReason": "sdlc-guard: " + str(e)}}))
        sys.stderr.write("sdlc-guard: " + str(e) + "\n"); sys.exit(2)
    except Ask as e:
        if ASK_PASSTHROUGH and not isinstance(e, Confirm):
            log_ask(tool, ti, str(e))
            sys.exit(0)                     # no opinion: the normal permission flow decides
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask",
                          "permissionDecisionReason": "sdlc-guard: " + str(e)}}))
        sys.exit(0)
    sys.exit(0)

main()
PYEOF
ERRF="$(mktemp -t sdlc-guard.XXXXXX)"
OUT="$(printf '%s' "$INPUT" | "$PY" -c "$PYCODE" 2>"$ERRF")"
RC=$?
ERR="$(cat "$ERRF" 2>/dev/null)"; rm -f "$ERRF"
if [ $RC -eq 0 ] || [ $RC -eq 2 ]; then
  [ -n "$OUT" ] && printf '%s\n' "$OUT"
  [ $RC -eq 2 ] && printf '%s\n' "$ERR" >&2
  exit $RC
fi
# Engine crashed: fail closed for sensitive tools, otherwise let the normal permission flow decide.
if printf '%s' "$INPUT" | grep -Eq '(kubectl|helm|limactl|kubecolor|aws |gcloud|terraform|crane|-eks\.sh|eks-bootstrap|--target=(prod|staging))'; then
  echo "sdlc-guard: engine error (rc=$RC) on a cluster/cloud command; failing closed. ${ERR}" >&2; exit 2
fi
exit 0
