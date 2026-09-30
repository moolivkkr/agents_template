# Permissions guide: unattended non-prod work, prod out of reach

The framework's agents build, test, deploy, reset and roll back on your own machines for hours with no
prompts. Anything that could reach production, destroy real data or change the machine stays blocked,
or waits for you. No single mechanism does this; each layer below catches what the others miss.

| Layer | Where | What it stops | What it can't stop |
|---|---|---|---|
| **Credential absence** | the machine | anything prod: there is nothing to authenticate with | a prod credential you add later to a default path |
| **RBAC + quota** | lab cluster (`cluster-up.sh`, `app-namespaces.sh`) | kubectl/helm writes outside `<app>-dev`/`<app>-qa`, including from scripts; namespace/RBAC/quota changes; kube-system secrets | misuse inside dev/qa (acceptable: disposable) |
| **sdlc-guard hook** | `~/.claude/hooks/sdlc-guard.sh` (PreToolUse) | see below: top-level commands, including `bash -c`, `eval`, `$(…)`, wrappers, `$VAR` command names | commands inside scripts (the shims cover those) |
| **PATH shims** | `~/.claude/hooks/sdlc-guard-shims/` (SessionStart) | kubectl/helm/limactl called by name from scripts, make, npx or python | a script calling a binary by absolute path |
| **allow / ask / deny rules** | `~/.claude/settings.json` | the usual spellings, even if hooks are disabled | anything spelled differently |
| **Auto mode classifier** | `~/.claude/settings.json` → `autoMode` | intent across steps, prod deploys, exfiltration, self-modification | probabilistic |
| **Managed settings** (optional) | `/Library/Application Support/ClaudeCode/` | tampering: root-owned guard and policy; bypass mode disabled | — |

## What the guard enforces

- **Cluster identity is pinned.** kubectl and helm must use the agent kubeconfig
  (`~/.kube/sdlc-lab.json`) and must present the pinned API server, cluster CA **and** credential.
  - A prod cluster renamed to the same context fails the check.
  - So does the admin credential copied into the pinned file.
  - Identity-override flags are refused: `--server`, `--token`, `--as`, `--kubeconfig` other than
    the pinned file.
- **Writes need an explicit namespace** matching the policy patterns (default `*-dev`, `*-qa`).
  - `default`, `kube-*` and anything prod-looking are never writable.
  - Namespace create/delete, cluster-scoped kinds, `drain` and `taint` are refused.
  - Bulk deletes (`--all`, `-l`, `-k`) are refused at the prompt. The approved `env-reset.sh` does
    those, confined by RBAC.
- **Secrets are never read or copied.** Any command or Read/Grep/Glob naming these is denied:
  - the admin kubeconfig, `~/.kube/config`, `~/.ssh`, cloud credentials (`~/.aws`, `~/.config/gcloud`,
    `~/.azure`), `~/.docker/config.json`;
  - registry and forge tokens: `~/.config/gh`, `~/.netrc`, `~/.npmrc`, `~/.pypirc`,
    `~/.git-credentials`; `~/.gnupg`; the keychain files in `~/Library/Keychains`.

  Paths are matched after `~`/`$HOME`, brace (`~/.{ssh,aws}`) and glob expansion (`~/.s*/id_rsa`,
  `~/.ss?/…`, `~/**/id_rsa`), segment by segment the way the shell expands them. The policy's list is
  unioned with this built-in list, so an older policy file still covers the newer entries.
- **The macOS Keychain is never read.** `security find-generic-password`, `find-internet-password`,
  `dump-keychain` and `export` are denied.
- **The ground-truth ledgers aren't edited in place.** A Write/Edit, redirect, `tee`, `sed -i`, `cp`/`mv`
  or `rm` on an existing `docs/PROJECT_FACTS.md` or `docs/DECISIONS.md` is denied: both are injected
  into every session with override priority, so an agent (or text it was tricked by) must not rewrite
  them. Facts go through `.claude/hooks/remember.sh` (`/remember`). Creating the file from its template
  (`/init`) is allowed.
- **Tamper protection.** Writes to `~/.claude/settings*.json`, `~/.claude/hooks`, the guard policy
  and `~/.kube` are denied, as is adding `disableAllHooks`.
- **Your CLAUDE.md "ask first" list becomes an ask.** In an unattended run with no one to ask, that
  means deny. It covers:
  - `git reset --hard`, force-push, `clean -f`, and checkout over changes;
  - `compose down -v` and volume deletion;
  - `rm -r` outside `/tmp` and build-artifact dirs;
  - destructive SQL;
  - `chmod 777`;
  - network calls to non-local hosts (lab hosts count as local);
  - interpreter one-liners that do network I/O: `node -e`/`--eval`/`-p`, `python -c`, `ruby -e`,
    `perl -e`, `php -r`, `bun -e`, `deno eval`, and a script fed to an interpreter by heredoc
    (`python3 - <<EOF`), when the code names a non-local URL or a network API (`fetch`, `http`/`https`,
    `socket`, `requests`, `urllib`, `Net::`, `curl`, …). Use `curl` for localhost checks;
  - `git remote add|set-url|rename`, `git config`/`git -c` of a remote URL or URL rewrite, and
    `git push` to any repository other than `origin` (a named remote or a URL);
  - `terraform apply` and publishing packages.
- **Denied outright:**
  - `sudo`;
  - cloud CLIs, and `aws` without a LocalStack endpoint;
  - remote Docker daemons;
  - deleting or creating Lima VMs;
  - `claude --dangerously-skip-permissions`;
  - `/deploy` or `/rollback` to staging or prod.

**Package installs stay allowed.** `npm install`, `pip install`, `go get` and friends need no prompt:
that is a deliberate choice, since builds download dependencies all day. The defence against
hallucinated and typosquatted names sits one step earlier. Before a coding agent adds a **new**
dependency it runs `.claude/guard/vet-package.py` (installed as `~/.claude/hooks/vet-package.py`). The
script checks the registry (npm, PyPI, the Go module proxy, crates.io) for existence, first-publish
age, weekly downloads where published, deprecation or yanking, and edit distance to popular names, and
exits non-zero with reasons. Installs then run with lifecycle scripts disabled where the ecosystem
allows (`npm ci --ignore-scripts`). See `.claude/skills/security/secure-coding.md` §5;
`dependency_scanner` re-vets every dependency the phase added.

The guard only ever returns *deny* or *ask*, never *allow*, so every other layer still applies. Its
test table is `tests/sdlc-guard.test.sh` (259 cases, including 13 offline `vet-package.py` cases).

## Set up once per machine

```bash
# 1. The lab cluster, agent identity, agent kubeconfig and guard policy (human; see lima-k8s-lab.md)
SERVER_SSH=tb2 SERVER_IP=10.10.10.2 AGENT_IP=10.10.10.3 .claude/templates/k8s/scripts/cluster-up.sh

# 2. Install the guard, env hook, shims and policy generator into ~/.claude/hooks/
./install.sh --guard

# 3. Merge the permission model into ~/.claude/settings.json (backup first; preview with --dry-run)
python3 .claude/guard/apply-user-settings.py --github <your-github-owner> --dry-run | less
python3 .claude/guard/apply-user-settings.py --github <your-github-owner>

# 4. (optional, recommended) Managed layer: root-owned guard + policy, bypass mode disabled
sudo mkdir -p "/Library/Application Support/ClaudeCode/sdlc-guard"
sudo install -m 755 -o root -g wheel .claude/guard/sdlc-guard.sh        "/Library/Application Support/ClaudeCode/sdlc-guard/sdlc-guard.sh"
sudo install -m 644 -o root -g wheel ~/.config/sdlc-guard/policy.json  "/Library/Application Support/ClaudeCode/sdlc-guard/policy.json"
sudo install -m 644 -o root -g wheel .claude/guard/managed-settings.json "/Library/Application Support/ClaudeCode/managed-settings.json"

# 5. Verify, then start a NEW Claude Code session (hooks load at session start)
claude doctor
claude auto-mode config          # your environment/allow/hard_deny entries appear merged with $defaults
bash tests/sdlc-guard.test.sh     # 259/259
```

**Why steps 3 and 4 are yours.** Claude Code's auto mode refuses to let an agent rewrite its own
permissions ("Self-Modification"), and that refusal is correct. The script is in the repo and tested
against a synthetic settings file (cases AS1–AS4), so you can read exactly what it changes. It keeps
every existing key, removes only the bare `"Bash"` allow, and prints the backup path.

**Per project:** `app-namespaces.sh <app>` creates `<app>-dev` and `<app>-qa` (admin kubeconfig,
human). After that, agents deploy with `/deploy --target=dev|qa` and need no prompts.

## When something is blocked

- **The reason names the rule**, for example
  `sdlc-guard: namespace 'shop-staging' is not writable by agents (allowed: *-dev|*-qa; …)`. Agents
  see the same text and adjust. A blocked script shows `sdlc-guard (exec-time): blocked: …` and
  exits 126.
- **Change the policy by regenerating it, never by editing it:**
  `python3 ~/.claude/hooks/sdlc-guard-make-policy.py --kubeconfig ~/.kube/sdlc-lab.json --pin ~/.kube/sdlc-lab.json --namespaces '*-dev,*-qa,*-perf' --lima-instance sdlc-agent --lab-host 10.10.10.2 --lab-host 10.10.10.3 --out ~/.config/sdlc-guard/policy.json`
  (then re-copy it to the managed location if you use step 4).
- **The agent kubeconfig is recreated** when `cluster-up.sh` rebuilds the cluster. It also rewrites
  the policy, so the CA and credential pins follow automatically.

## Limits, stated plainly

- **Your user account is the boundary for files.** A process running as you can edit files you own.
  The guard stops the obvious routes, and the managed layer makes the guard and policy themselves
  root-owned. RBAC, not the guard, is what bounds the cluster.
- **Shims can be bypassed.** A script can call `/usr/local/bin/kubectl` by absolute path. RBAC still
  confines it; `env-reset.sh` relies on exactly this, and is limited to `<app>-dev|qa`.
- **The guard treats a known set of hosts as local** (loopback, `*.localhost`, lab hosts). Other
  hosts get *ask*. WebFetch, WebSearch and MCP tools aren't affected.
- **It sees commands, not programs.** Network I/O is caught when the code is on the command line or
  in an interpreter heredoc. It is not caught in a script file (`python3 tool.py`, `node build.js`), a
  package's install script, `npx some-package`, or code assembled at runtime (`eval(atob(…))`). The
  keyword match is deliberately broad, so an inline script that merely mentions `requests` gets an
  *ask*.
- **Secret paths are matched by name.** A command that copies a parent directory (`tar ~`,
  `cp -r ~/.config`) or reads through a symlink it created first is not caught. The autoMode
  `hard_deny` rule and your account boundary are the backstops.
- **Ledger protection covers the direct routes only.** A script that opens `docs/DECISIONS.md` itself
  (`python3 -c "open(…,'a')"`) isn't seen. `git push` with no repository argument is allowed: it goes
  to the branch's configured upstream, and only a `git remote`/`git config` change (asked) can
  redirect that.
- **`vet-package.py` is a step the agents are told to run, not one the guard enforces.** The guard
  doesn't block installs of unvetted names; `dependency_scanner` re-vets new dependencies in Wave 4.
- **`~/.claude/hooks` should not be world-writable.** Check with `ls -ld ~/.claude/hooks`; fix it
  with `chmod 755 ~/.claude/hooks`.

## Revert

- **User settings:** `cp ~/.claude/settings.json.bak-<timestamp> ~/.claude/settings.json`.
- **Managed layer:** `sudo rm "/Library/Application Support/ClaudeCode/managed-settings.json"`.
- **Guard files:** delete `~/.claude/hooks/sdlc-guard*`. With no policy file, cluster commands are
  denied (fail-closed) and everything else is unaffected.
