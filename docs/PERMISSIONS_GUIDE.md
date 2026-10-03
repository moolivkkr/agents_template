# Permissions guide: unattended non-prod work, prod out of reach

The framework's agents build, test, deploy, reset and roll back on your own machines for hours with no
prompts. Anything that could reach production, destroy real data or change the machine stays blocked,
or waits for you. No single mechanism does this; each layer below catches what the others miss.

| Layer | Where | What it stops | What it can't stop |
|---|---|---|---|
| **Credential absence** | the machine | anything prod: there is nothing to authenticate with | a prod credential you add later to a default path |
| **RBAC + quota** | lab cluster (`cluster-up.sh`, `app-namespaces.sh`) | kubectl/helm writes outside `<app>-dev`/`<app>-qa`, including from scripts; namespace/RBAC/quota changes; kube-system secrets | misuse inside dev/qa (acceptable: disposable) |
| **sdlc-guard hook** | `~/.claude/hooks/sdlc-guard.sh` (PreToolUse) | see below: top-level commands, including `bash -c`, `eval`, `$(…)`, wrappers, `$VAR` command names | commands inside scripts (the shims cover those) |
| **PATH shims** | `~/.claude/hooks/sdlc-guard-shims/` (SessionStart) | kubectl/helm/limactl/aws/crane called by name from scripts, make, npx or python | a script calling a binary by absolute path |
| **allow / ask / deny rules** | `~/.claude/settings.json` | the usual spellings, even if hooks are disabled | anything spelled differently |
| **Auto mode classifier** | `~/.claude/settings.json` → `autoMode` | intent across steps, prod deploys, exfiltration, self-modification | probabilistic |
| **Managed settings** (optional) | `/Library/Application Support/ClaudeCode/` | tampering: root-owned guard and policy | — |

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
  - cloud CLIs, and `aws` without a LocalStack endpoint, except inside a project you listed for AWS
    (see [AWS for your projects](#aws-for-your-projects));
  - remote Docker daemons;
  - deleting or creating Lima VMs;
  - `claude --dangerously-skip-permissions`;
  - `/deploy` or `/rollback` to staging or prod.

**Package installs stay allowed.** `npm install`, `pip install`, `go get` and friends need no prompt:
that is a deliberate choice, since builds download dependencies all day. The defence against
hallucinated and typosquatted names sits one step earlier. Before a coding agent adds a **new**
dependency it runs `vet-package.py`. Agents call it as `~/.claude/hooks/vet-package.py`, so step 2 below
copies it there from `.claude/guard/`. The script checks the registry (npm, PyPI, the Go module proxy, crates.io) for existence, first-publish
age, weekly downloads where published, deprecation or yanking, and edit distance to popular names, and
exits non-zero with reasons. Installs then run with lifecycle scripts disabled where the ecosystem
allows (`npm ci --ignore-scripts`). See `.claude/skills/security/secure-coding.md` §5;
`dependency_scanner` re-vets every dependency the phase added.

The guard only ever returns *deny* or *ask*, never *allow*, so every other layer still applies. Its
test table is `tests/sdlc-guard.test.sh` (383 cases, including 13 offline `vet-package.py` cases and
92 AWS-project cases).

## AWS for your projects

By default `aws` is denied unless it targets LocalStack. For a project whose own infrastructure lives
in AWS (rera's `infra/aws-inference/*.sh` launch, tag and terminate EC2 inference boxes and copy
models through S3, across regions), you can list the project in the guard policy. Agents then use the
real AWS CLI there, in every region, with no prompt for ordinary work.

**A command counts as inside the project** when every directory it can run in is under the project
path, after symlinks are resolved. That is the session's working directory, followed through any
`cd`/`pushd` in the command:
- `cd ~/development/rera && aws …` counts;
- `cd ~/development/rera; aws …` doesn't, because the `cd` may have failed;
- `(cd rera && x); aws …` doesn't either, because the `cd` ran in a subshell;
- a `cd` to an unresolved `$VAR` makes the directory unknown, and that never counts.

| Inside a listed project | Decision |
|---|---|
| Any service, any operation, any region: `ec2 run-instances`, `terminate-instances`, `create-security-group`, `authorize-security-group-ingress`, `create-tags`, `wait`, `s3 cp/ls/presign/rm/rb`, `autoscaling …`, `delete-*`, `sts get-caller-identity` | allow |
| A service in `ask_services`. Default: `iam`, `organizations`, `account`, `sso-admin`, `identitystore`, `eks` | ask |
| An action in `ask_actions` (`service:operation` globs, e.g. `ec2:delete-vpc`; default none) | ask |
| An argument or the profile that looks like prod (`shop-prod`, `--profile prod`; same pattern as everywhere else) | ask (switch off with `--aws-prod-names off`) |
| `aws configure set\|import\|sso\|…`, `aws sso login\|logout`: they change which credentials the CLI uses | ask |
| A service or operation that is an unresolved `$VAR` | ask |
| Commands that print credentials: `sts get-session-token`, `sts assume-role*`, `sts get-federation-token`, `sso get-role-credentials`, `ecr get-authorization-token`, `codeartifact get-authorization-token`, `rds generate-db-auth-token`, `redshift get-cluster-credentials*` | deny, unless you list the action in `allow_credential_actions` |
| `ecr get-login-password` | allow only when piped straight into a `--password-stdin` login (`docker`, `podman`, `oras`, `crane auth`, `helm registry`). The login itself keeps its own rule: `docker login` still asks. Printed or redirected to a file, it's denied |
| `aws configure export-credentials`, `aws configure get <any secret/token key>`, `eks get-token`, `eks update-kubeconfig`, `--debug` (it logs the session token) | deny, always, in every project; the policy can't allow them |
| `file://~/.aws/…` and other secret paths as inputs; `s3 cp` downloads onto protected paths (`~/.claude/settings.json`, …) | deny |
| Profile, account or region outside the project's pins (below) | deny |
| **Outside every listed project** | unchanged: deny unless `--endpoint-url` is LocalStack |

Nothing else changes. Reading `~/.aws` stays denied everywhere, and the EKS release scripts
(`deploy-eks.sh`, `promote-eks.sh`, `eks-bootstrap.sh`) stay human or CI only. The guard still never
answers *allow*: inside a project it simply has no objection, so your permission rules and auto mode
apply as before. `apply-user-settings.py` writes the project paths into `autoMode` (environment and
allow), so the auto-mode classifier knows EC2, S3 and security-group work there is approved.

**Why `ask_services` defaults to those six.** IAM, Organizations, account settings and Identity Center
(`sso-admin`, `identitystore`) change who can do what across the whole account, not just the
project's own resources, and an IAM key or role an agent makes outlives the session. `eks` is on the
list because the framework's staging and prod clusters run on EKS, and those are human or CI only. To
allow everything, set `--aws-ask-services none`. The credential and kube-credential denies above still
apply.

### Policy shape

```json
"aws": {
  "projects": [
    {"path": "~/development/rera", "profiles": [], "accounts": [], "regions": "*"}
  ],
  "ask_services": ["iam", "organizations", "account", "sso-admin", "identitystore", "eks"],
  "ask_actions": [],
  "allow_credential_actions": [],
  "ask_prod_names": true
}
```

- **`profiles`**: empty means any. If profiles are listed, the effective profile must be one of them.
  The effective profile is `--profile`, else `AWS_PROFILE`/`AWS_DEFAULT_PROFILE` from the command
  prefix, an `export` in the same command, or the session environment, else `default`. Pinning also
  denies a command (or a session) that sets `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
  `AWS_SESSION_TOKEN`, `AWS_ROLE_ARN`, `AWS_WEB_IDENTITY_TOKEN_FILE` or the container-credential
  URIs, because those replace the profile's credentials. The same goes for a command that points
  `AWS_CONFIG_FILE` or `AWS_SHARED_CREDENTIALS_FILE` somewhere else.
- **`accounts`**: checked offline only. The guard reads `sso_account_id`, or the account in
  `role_arn`, for the effective profile from the CLI config file (`~/.aws/config`, never the
  credentials file). It makes no `sts` call. A profile with static keys has no account written
  down, so with `accounts` set it is denied. **Profile pinning is the reliable mechanism; treat
  `accounts` as a check on SSO/role profiles only.**
- **`regions`**: `"*"` (default) or a list of names/globs (`["ap-south-1", "ap-northeast-*"]`). The
  region is `--region`, `AWS_REGION`, `AWS_DEFAULT_REGION` or the profile's `region` in the config.
  With a list, a command whose region can't be determined is denied.
- `ask_services`, `ask_actions`, `allow_credential_actions` and `ask_prod_names` can also be set on a
  single project entry, which overrides the top-level value for that project.

### Turning it on (rera)

The policy is human-owned, so you run these, not an agent. `--update` changes only the `aws` section
and keeps the kube pin, Lima instances and lab hosts as they are. A later full `make-policy` run (for
example `cluster-up.sh` rebuilding the cluster) keeps an existing `aws` section.

```bash
cd ~/development/startup-agents
./install.sh --guard                                   # the new guard, shim and make-policy

python3 ~/.claude/hooks/sdlc-guard-make-policy.py --update --out ~/.config/sdlc-guard/policy.json \
    --aws-project ~/development/rera                   # prints the resulting aws section
#   optional: --aws-profile <name> (repeatable) to pin profiles
#             --aws-ask-services none to drop the ask list
#             --aws-allow-credential-actions sts:assume-role

python3 .claude/guard/apply-user-settings.py --github <your-github-owner>   # autoMode learns the project

# only if you use the managed layer (step 4 above): re-copy the guard and the policy
sudo install -m 755 -o root -g wheel .claude/guard/sdlc-guard.sh       "/Library/Application Support/ClaudeCode/sdlc-guard/sdlc-guard.sh"
sudo install -m 644 -o root -g wheel ~/.config/sdlc-guard/policy.json "/Library/Application Support/ClaudeCode/sdlc-guard/policy.json"
```

Then start a new Claude Code session in `~/development/rera`. To remove a project, run
`--update --out … --aws-remove-project ~/development/rera`.

### Limits

- **SDK programs are invisible.** `python3 launch.py` using boto3, a Node script using the AWS SDK,
  or Terraform's AWS provider make AWS calls the guard never sees: it checks command lines, not
  programs. Those calls run with whatever credentials the process finds, inside or outside a listed
  project. `python -m awscli` is recognised as `aws`.
- **Scripts go through the `aws` PATH shim**, which re-checks each call with the script's working
  directory and environment. There an *ask* counts as deny, so a script calling `iam …` stops with
  exit 126. A script calling `/usr/local/bin/aws` by absolute path bypasses the shim.
- **The pipe check is exact at the prompt only.** For `ecr get-login-password` inside a script, the
  shim can see that stdout is a pipe but not what reads it.
- **Allowed means allowed.** Inside a listed project an agent can terminate any instance or empty
  any bucket the profile can reach, in any region, including resources that aren't the project's.
  Use a profile scoped to the project's account, or IAM permissions, if that matters. The guard
  can't tell one EC2 instance from another.
- **Output isn't filtered.** `secretsmanager get-secret-value` or `ssm get-parameter
  --with-decryption` print application secrets. They are allowed in a listed project unless you add
  them to `ask_actions` (`secretsmanager:get-secret-value`, `ssm:get-parameter*`).

## Set up once per machine

```bash
# 1. The lab cluster, agent identity, agent kubeconfig and guard policy (human; see lima-k8s-lab.md)
SERVER_SSH=tb2 SERVER_IP=10.10.10.20 AGENT_IP=10.10.10.30 .claude/templates/k8s/scripts/cluster-up.sh

# 2. Install the guard, env hook, shims and policy generator into ~/.claude/hooks/
./install.sh --guard
#    ...and the dependency vetting tool the coding agents call (not yet copied by install.sh)
install -m 755 .claude/guard/vet-package.py ~/.claude/hooks/vet-package.py

# 3. Merge the permission model into ~/.claude/settings.json (backup first; preview with --dry-run)
python3 .claude/guard/apply-user-settings.py --github <your-github-owner> --dry-run | less
python3 .claude/guard/apply-user-settings.py --github <your-github-owner>

# 4. (optional, recommended) Managed layer: root-owned guard + policy
sudo mkdir -p "/Library/Application Support/ClaudeCode/sdlc-guard"
sudo install -m 755 -o root -g wheel .claude/guard/sdlc-guard.sh        "/Library/Application Support/ClaudeCode/sdlc-guard/sdlc-guard.sh"
sudo install -m 644 -o root -g wheel ~/.config/sdlc-guard/policy.json  "/Library/Application Support/ClaudeCode/sdlc-guard/policy.json"
sudo install -m 644 -o root -g wheel .claude/guard/managed-settings.json "/Library/Application Support/ClaudeCode/managed-settings.json"

# 5. Verify, then start a NEW Claude Code session (hooks load at session start)
claude doctor
claude auto-mode config          # your environment/allow/hard_deny entries appear merged with $defaults
bash tests/sdlc-guard.test.sh     # 383/383
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
  `python3 ~/.claude/hooks/sdlc-guard-make-policy.py --kubeconfig ~/.kube/sdlc-lab.json --pin ~/.kube/sdlc-lab.json --namespaces '*-dev,*-qa,*-perf' --lima-instance sdlc-agent --lab-host 10.10.10.20 --lab-host 10.10.10.30 --out ~/.config/sdlc-guard/policy.json`
  (then re-copy it to the managed location if you use step 4).
- **The agent kubeconfig is recreated** when `cluster-up.sh` rebuilds the cluster. It also rewrites
  the policy, so the CA and credential pins follow automatically.

## Bypass mode

`claude --dangerously-skip-permissions` stays available: the template no longer disables it. That's
safe with this setup because **PreToolUse hooks run before the permission mode is checked**. The
guard's *deny* still blocks prod, secrets, cluster-admin and destructive commands in bypass mode, and
its *ask* still prompts for your CLAUDE.md "ask first" list. Bypass removes Claude Code's own prompts
(including the always-on `.claude/` folder protection). It doesn't remove the guard. To forbid bypass
on a machine, add `"disableBypassPermissionsMode": "disable"` to the managed file's `permissions`.

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
