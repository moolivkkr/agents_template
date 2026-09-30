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
  if printf '%s' "$INPUT" | grep -Eq '(kubectl|helm|limactl|kubecolor|aws |gcloud|az |terraform|--target=(prod|staging))'; then
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

def deny(msg): raise Deny(msg)
def ask(msg): raise Ask(msg)

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
    """Split into simple commands; also yield nested $(..)/backtick/-c bodies."""
    toks = tokenize(s)
    cur, out = [], []
    i = 0
    while i < len(toks):
        t = toks[i]
        if t and all(c in SEP_CHARS for c in t):
            if cur: out.append(cur)
            cur = []
        elif t and all(c in "<>&" for c in t):
            # redirection operator: the next token is its target (or an fd number)
            tgt = toks[i + 1] if i + 1 < len(toks) else ""
            if ">" in t and tgt and not tgt.isdigit() and tgt != "-":
                check_write_target(expand(tgt, env))
            i += 1
        else:
            cur.append(t)
        i += 1
    if cur: out.append(cur)
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
    """Bash-style {a,b} expansion (enough to see through `~/.{ssh,aws}/…`); capped."""
    m = re.search(r"\{([^{}]*,[^{}]*)\}", s)
    if not m: return [s]
    out = []
    for alt in m.group(1).split(","):
        out += brace_expand(s[:m.start()] + alt + s[m.end():], limit)
        if len(out) >= limit: break
    return out[:limit]

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
                ask("kubectl config view --raw prints live credentials")
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
        ask("docker compose down -v deletes volumes (user rule: ask first)")
    if words[:2] in (["volume", "rm"], ["volume", "prune"], ["volume", "remove"]):
        ask("docker volume deletion (user rule: ask first)")
    if words[:2] == ["system", "prune"] and "--volumes" in rest:
        ask("docker system prune --volumes (user rule: ask first)")
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
            ask("git push rewriting/deleting remote refs (user rule: ask first)")
    elif sub == "reset" and "--hard" in rest: ask("git reset --hard discards work (user rule)")
    elif sub == "clean" and ("--force" in rest or any(r.startswith("-") and not r.startswith("--") and "f" in r for r in rest)):
        ask("git clean -f deletes untracked files (user rule)")
    elif sub == "checkout" and ("--" in rest or "." in rest or "-f" in rest or "--force" in rest): ask("git checkout over working-tree changes (user rule)")
    elif sub == "restore" and "--staged" not in rest: ask("git restore discards working-tree changes (user rule)")
    elif sub == "stash" and rest[:1] in (["drop"], ["clear"]): ask("git stash drop/clear (user rule)")
    elif sub == "branch" and ("-D" in rest or ("-d" in rest and "--force" in rest)): ask("git branch -D")
    elif sub in ("filter-branch", "filter-repo") or (sub == "update-ref" and "-d" in rest) or (sub == "reflog" and rest[:1] == ["expire"]):
        ask(f"git {sub} rewrites history")

def check_rm(argv, env, cwd, scratch):
    flags = [a for a in argv[1:] if a.startswith("-") and a != "-"]
    recursive = any(("r" in f.lstrip("-") or "R" in f) for f in flags if not f.startswith("--")) or "--recursive" in flags
    if not recursive: return
    targets = [expand(a, env) for a in argv[1:] if not a.startswith("-")]
    if not targets: return
    safe_roots = [os.path.realpath(p) for p in ["/tmp", "/private/tmp", "/var/folders", os.environ.get("TMPDIR", "/tmp")] + ([scratch] if scratch else [])]
    for t in targets:
        if "$" in t or "*" in t or "?" in t or "`" in t:
            ask(f"rm -r with an unresolved/glob target '{t}' (user rule: ask before rm -rf outside /tmp and build artifacts)")
        p = os.path.realpath(os.path.join(cwd, os.path.expanduser(t)))
        if any(under(p, r) for r in safe_roots): continue
        inside_repo = under(p, os.path.realpath(cwd))
        comps = set(os.path.relpath(p, os.path.realpath(cwd)).split(os.sep)) if inside_repo else set()
        if inside_repo and p != os.path.realpath(cwd) and comps & ARTIFACT_DIRS: continue
        ask(f"rm -r {t} is outside /tmp and build artifacts (user rule: ask first)")

SQL_CLIENTS = {"psql", "mysql", "mariadb", "sqlite3", "mongosh", "mongo", "redis-cli", "cockroach", "clickhouse-client", "dropdb"}
SQL_DESTRUCTIVE = re.compile(r"\bDROP\s+(DATABASE|SCHEMA|TABLE|OWNED|ROLE|USER)\b|\bTRUNCATE\b|\bFLUSH(ALL|DB)\b|dropDatabase\(|\bDELETE\s+FROM\s+[\w.\"]+\s*(;|$|\"|')", re.I)
def check_sql(argv):
    names = {os.path.basename(a) for a in argv}
    if names & SQL_CLIENTS:
        if "dropdb" in names: ask("dropdb (user rule: ask before DROP DATABASE)")
        text = " ".join(argv)
        if SQL_DESTRUCTIVE.search(text): ask("destructive SQL (DROP/TRUNCATE/DELETE without WHERE) — user rule: ask first")

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
def check_network(argv, env):
    a0 = os.path.basename(argv[0])
    if a0 not in NET_TOOLS: return
    if a0 in ("ssh",):
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

CLOUD_DENY = {"gcloud", "az", "doctl", "flyctl", "fly", "heroku", "vercel", "netlify", "railway", "eksctl", "kops", "oci", "ibmcloud"}
def check_cloud(argv, env):
    a0 = os.path.basename(argv[0])
    if a0 in CLOUD_DENY and not (argv[1:2] in (["--version"], ["version"], ["help"], ["--help"])):
        deny(f"{a0} reaches real cloud accounts; prod is unreachable by policy")
    if a0 == "aws":
        ep = None
        for i, a in enumerate(argv):
            if a.startswith("--endpoint-url="): ep = a.split("=", 1)[1]
            elif a == "--endpoint-url" and i + 1 < len(argv): ep = argv[i + 1]
        if ep and re.match(r"^https?://(localhost|127\.0\.0\.1|localstack)(:\d+)?", ep): return
        if argv[1:2] in (["--version"], ["help"]): return
        deny("aws without --endpoint-url http://localhost:* (LocalStack) is blocked; prod is unreachable by policy")
    if a0 in ("terraform", "tofu", "pulumi", "cdk", "terragrunt"):
        words = [a for a in argv[1:] if not a.startswith("-")]
        if words[:1] and words[0] in ("apply", "destroy", "import", "up", "deploy", "taint") or words[:2] == ["state", "rm"]:
            ask(f"{a0} {words[0]} changes real infrastructure")
    if a0 in ("npm", "pnpm", "yarn") and argv[1:2] == ["publish"] or a0 in ("twine",) or (a0 == "cargo" and argv[1:2] == ["publish"]):
        ask("publishing a package leaves this machine")
    if a0 == "claude" and any(a in ("--dangerously-skip-permissions", "--allow-dangerously-skip-permissions") for a in argv):
        deny("agents may not launch unguarded Claude sessions")

def check_kind_k3d(argv):
    a0 = os.path.basename(argv[0]); words = [a for a in argv[1:] if not a.startswith("-")]
    if a0 == "kind" and (words[:1] == ["delete"] or words[:2] == ["export", "kubeconfig"]): ask(f"kind {' '.join(words[:2])}")
    if a0 == "k3d" and (words[:2] in (["cluster", "delete"], ["cluster", "stop"]) or words[:2] == ["kubeconfig", "merge"]): ask(f"k3d {' '.join(words[:2])}")

def check_chmod(argv):
    if os.path.basename(argv[0]) == "chmod" and any(a in ("777", "a+rwx", "ugo+rwx", "0777") for a in argv[1:]):
        ask("chmod 777 (user rule: ask first)")

# ---------------------------------------------------------------- driver
KUBE_TOOLS = {"kubectl", "kubecolor", "oc", "stern"}
def check_command(cmd, cwd, scratch, depth=0, env=None):
    if depth > 4: ask("command nesting too deep to analyse")
    env = dict(env or {})
    seen = len(INTERP_BODIES)
    cmd, shell_bodies, subst_bodies = split_heredocs(cmd)
    for consumer, body in INTERP_BODIES[seen:]:
        why = network_in_code(body)
        if why:
            ask(f"{consumer} script from a heredoc does network I/O ({why}); network egress from inline code needs approval")
    for b in shell_bodies:
        check_command(b, cwd, scratch, depth + 1, env)
    for b in subst_bodies:
        for body in nested_bodies(b):
            check_command(body, cwd, scratch, depth + 1, env)
    for seg in segments(cmd, env):
        for tok in seg:
            for body in nested_bodies(tok):
                check_command(body, cwd, scratch, depth + 1, env)
        argv = strip_wrappers(list(seg), env)   # consumes VAR=value prefixes / standalone assignments into env
        if not argv: continue
        argv[0] = expand(argv[0], env)
        if "$" in argv[0]: ask(f"command name is an unresolved variable ({argv[0]})")
        a0 = os.path.basename(argv[0])
        if a0 in ("bash", "sh", "zsh", "dash") and "-c" in argv:
            i = argv.index("-c")
            if i + 1 < len(argv): check_command(argv[i + 1], cwd, scratch, depth + 1, env)
            continue
        if a0 == "eval":
            check_command(" ".join(argv[1:]), cwd, scratch, depth + 1, env); continue
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
        elif a0 == "find" and ("-delete" in argv or ("-exec" in argv and "rm" in argv)): ask("find -delete/-exec rm (user rule: ask before bulk deletion)")
        check_sql(argv)
        check_network(argv, env)
        check_cloud(argv, env)
        check_kind_k3d(argv)
        check_chmod(argv)

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

def main():
    global CWD
    data = json.load(sys.stdin)
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
if printf '%s' "$INPUT" | grep -Eq '(kubectl|helm|limactl|kubecolor|aws |gcloud|terraform|--target=(prod|staging))'; then
  echo "sdlc-guard: engine error (rc=$RC) on a cluster/cloud command; failing closed. ${ERR}" >&2; exit 2
fi
exit 0
