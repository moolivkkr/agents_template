#!/usr/bin/env bash
# startup-agents installer
# Installs commands, core agents, templates, skill packs, and docs to ~/.claude/
# After install, /startup:<command> is available in any project.

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ./install.sh --rule-board <project-dir> : install only the rule board specialists into one project.
if [ "${1:-}" = "--rule-board" ]; then
  PROJECT="${2:?Usage: $0 --rule-board <project-dir>}"
  [ -d "$PROJECT" ] || { echo "No such project directory: $PROJECT" >&2; exit 1; }
  mkdir -p "$PROJECT/.claude/agents/rule_board"
  rsync -a --include='*/' --include='*.md' --exclude='*' "$REPO_DIR/.claude/agents/rule_board/" "$PROJECT/.claude/agents/rule_board/"
  echo "✅ $(find "$PROJECT/.claude/agents/rule_board" -name '*.md' | wc -l | tr -d ' ') rule board agents installed → $PROJECT/.claude/agents/rule_board/"
  exit 0
fi
# ./install.sh --guard : install only the user-level permission guard (docs/PERMISSIONS_GUIDE.md).
# Copies files; never edits settings.json or writes the policy (both are human steps in the guide).
if [ "${1:-}" = "--guard" ]; then
  HOOKS="$HOME/.claude/hooks"; SHIMS="$HOOKS/sdlc-guard-shims"
  mkdir -p "$SHIMS"
  install -m 755 "$REPO_DIR/.claude/guard/sdlc-guard.sh"     "$HOOKS/sdlc-guard.sh"
  install -m 755 "$REPO_DIR/.claude/guard/sdlc-guard-env.sh" "$HOOKS/sdlc-guard-env.sh"
  install -m 755 "$REPO_DIR/.claude/guard/make-policy.py"    "$HOOKS/sdlc-guard-make-policy.py"
  install -m 755 "$REPO_DIR/.claude/guard/vet-package.py"    "$HOOKS/vet-package.py"      # secure-coding §5: vet new dependencies
  install -m 755 "$REPO_DIR/.claude/guard/shims/kubectl"     "$SHIMS/kubectl"
  ln -sf kubectl "$SHIMS/helm"; ln -sf kubectl "$SHIMS/limactl"
  echo "✅ sdlc-guard installed → $HOOKS/ (hook, env hook, policy generator, shims)"
  [ -f "$HOME/.config/sdlc-guard/policy.json" ] \
    && echo "   policy: $HOME/.config/sdlc-guard/policy.json" \
    || echo "   ⚠ no policy yet: cluster commands are denied until you run sdlc-guard-make-policy.py (see docs/PERMISSIONS_GUIDE.md)"
  exit 0
fi
CLAUDE_DIR="$HOME/.claude"
DEST_COMMANDS="$CLAUDE_DIR/commands/startup"
DEST_AGENTS_CORE="$CLAUDE_DIR/agents"
DEST_AGENTS_DOCS="$CLAUDE_DIR/agents"
DEST_TEMPLATES="$CLAUDE_DIR/agents/templates"
DEST_SKILLS="$CLAUDE_DIR/skills"

echo "startup-agents installer"
echo "========================"
echo "Source: $REPO_DIR"
echo "Target: $CLAUDE_DIR"
echo

# ── Commands ─────────────────────────────────────────────────────────────────
echo "Installing commands → $DEST_COMMANDS/"
mkdir -p "$DEST_COMMANDS"
cp "$REPO_DIR/.claude/commands/"*.md "$DEST_COMMANDS/"
CMD_COUNT=$(ls "$REPO_DIR/.claude/commands/"*.md | wc -l | tr -d ' ')
echo "  ✅ $CMD_COUNT commands installed"

# ── Core agents ───────────────────────────────────────────────────────────────
echo "Installing core agents → $DEST_AGENTS_CORE/"
mkdir -p "$DEST_AGENTS_CORE"
cp "$REPO_DIR/.claude/agents/core/"*.md "$DEST_AGENTS_CORE/"
AGENT_COUNT=$(ls "$REPO_DIR/.claude/agents/core/"*.md | wc -l | tr -d ' ')
echo "  ✅ $AGENT_COUNT core agents installed"

# ── Agent documentation ───────────────────────────────────────────────────────
echo "Installing agent docs → $DEST_AGENTS_DOCS/"
if ls "$REPO_DIR/.claude/agents/"*.md &>/dev/null; then
  cp "$REPO_DIR/.claude/agents/"*.md "$DEST_AGENTS_DOCS/"
  DOC_COUNT=$(ls "$REPO_DIR/.claude/agents/"*.md | wc -l | tr -d ' ')
  echo "  ✅ $DOC_COUNT agent docs installed (AGENT_SCHEMA.md, INVENTORY.md)"
fi

# ── Contract sync script (keeps reference-packs + operating-contract blocks current) ──
cp "$REPO_DIR/.claude/agents/_sync-contract.sh" "$DEST_AGENTS_CORE/_sync-contract.sh"
chmod +x "$DEST_AGENTS_CORE/_sync-contract.sh"
echo "  ✅ _sync-contract.sh installed"
for h in _sync-deps.py _add-packs.py; do
  cp "$REPO_DIR/.claude/agents/$h" "$DEST_AGENTS_CORE/$h" && chmod +x "$DEST_AGENTS_CORE/$h"
done
echo "  ✅ _sync-deps.py + _add-packs.py installed (dependency-graph maintenance)"
# ── Hooks (copied into each project by new-project.sh / /autonomous Step 0; settings reference $CLAUDE_PROJECT_DIR/.claude/hooks) ──
mkdir -p "$CLAUDE_DIR/hooks/startup"
cp "$REPO_DIR/.claude/hooks/"*.sh "$REPO_DIR/.claude/hooks/"*.py "$REPO_DIR/.claude/hooks/"*.mjs "$CLAUDE_DIR/hooks/startup/" && chmod +x "$CLAUDE_DIR/hooks/startup/"*.sh "$CLAUDE_DIR/hooks/startup/"*.py
install -m 755 "$REPO_DIR/.claude/guard/vet-package.py" "$CLAUDE_DIR/hooks/vet-package.py"   # agents call ~/.claude/hooks/vet-package.py
cp "$REPO_DIR/.claude/settings.json" "$CLAUDE_DIR/hooks/startup/project-settings.json"
echo "  ✅ hooks staged in $CLAUDE_DIR/hooks/startup/ (project copies made by new-project.sh / /autonomous)"
# ── Scripts run from a project directory (one shared copy; they act on $PWD or --project) ──
mkdir -p "$CLAUDE_DIR/scripts/startup"
install -m 755 "$REPO_DIR/scripts/startup-autonomous-run.sh" "$CLAUDE_DIR/scripts/startup/startup-autonomous-run.sh"
echo "  ✅ unattended /autonomous supervisor → $CLAUDE_DIR/scripts/startup/startup-autonomous-run.sh (docs/AUTONOMOUS_GUIDE.md §10)"

# ── Agent templates (for agent_factory to generate project-specific agents) ──
echo "Installing agent templates → $DEST_TEMPLATES/"
mkdir -p "$DEST_TEMPLATES"
# Install from both generated/ and templates/ directories
# Templates use .tmpl (not .md) so Claude Code never loads an unfilled template as a live agent.
# Remove copies left by older installs under the old .tmpl.md name.
rm -f "$DEST_TEMPLATES/"*.tmpl.md
cp "$REPO_DIR/.claude/agents/templates/"*.tmpl "$DEST_TEMPLATES/" 2>/dev/null || true
TMPL_COUNT=$(ls "$DEST_TEMPLATES/"*.tmpl 2>/dev/null | wc -l | tr -d ' ')
echo "  ✅ $TMPL_COUNT agent templates installed"

# ── Rule board specialists (EDR/SIEM/CSPM/DSPM/KSPM/NSPM/AI-security) ─────────
# Rule board specialists are project-specific (vertix security-rule boards). The /rules-board*
# commands read .claude/agents/rule_board/ project-relative, so they are installed into a project
# with `./install.sh --rule-board <project-dir>`, never into ~/.claude - installing them globally
# would load 49 unrelated agents into every session.
echo "Rule board specialists: not installed globally (project-specific)."
echo "  To add them to a project: ./install.sh --rule-board <project-dir>"

# ── Project templates (CLAUDE.md template for /init) ─────────────────────────
echo "Installing project templates → $CLAUDE_DIR/templates/"
mkdir -p "$CLAUDE_DIR/templates"
if ls "$REPO_DIR/.claude/templates/"*.template &>/dev/null; then
  cp "$REPO_DIR/.claude/templates/"*.template "$CLAUDE_DIR/templates/"
  # k8s lab cluster + per-project deploy layer (deployment_agent runs templates/k8s/app/instantiate.sh)
  rsync -a --delete --exclude '__pycache__' "$REPO_DIR/.claude/templates/k8s/" "$CLAUDE_DIR/templates/k8s/"
  PROJ_TMPL_COUNT=$(ls "$REPO_DIR/.claude/templates/"*.template | wc -l | tr -d ' ')
  echo "  ✅ $PROJ_TMPL_COUNT project templates installed"
fi

# ── Skill packs (recursive — preserves subdirectory structure) ────────────────
echo "Installing skill packs → $DEST_SKILLS/"
mkdir -p "$DEST_SKILLS"
# Use rsync if available for clean recursive copy, otherwise cp -r
if command -v rsync &>/dev/null; then
  rsync -a --include='*/' --include='*.md' --exclude='*' "$REPO_DIR/.claude/skills/" "$DEST_SKILLS/"
else
  cp -r "$REPO_DIR/.claude/skills/"* "$DEST_SKILLS/"
fi
SKILL_COUNT=$(find "$REPO_DIR/.claude/skills" -name "*.md" | wc -l | tr -d ' ')
echo "  ✅ $SKILL_COUNT skill packs installed"

# ── Breakdown by category ────────────────────────────────────────────────────
echo "     Skill pack breakdown:"
for dir in "$REPO_DIR/.claude/skills"/*/; do
  if [ -d "$dir" ]; then
    category=$(basename "$dir")
    count=$(find "$dir" -name "*.md" | wc -l | tr -d ' ')
    echo "       $category: $count"
  fi
done

# ── settings.json (merge, don't overwrite) ────────────────────────────────────
SETTINGS_SRC="$REPO_DIR/.claude/settings.json"
SETTINGS_DEST="$CLAUDE_DIR/settings.json"
if [ ! -f "$SETTINGS_DEST" ]; then
  cp "$SETTINGS_SRC" "$SETTINGS_DEST"
  echo "  ✅ settings.json created"
else
  cp "$SETTINGS_DEST" "$SETTINGS_DEST.bak"
  echo "  ⚠  settings.json already exists — backed up to settings.json.bak"
  if command -v diff &>/dev/null; then
    DIFF_OUTPUT=$(diff "$SETTINGS_DEST" "$SETTINGS_SRC" 2>/dev/null || true)
    if [ -n "$DIFF_OUTPUT" ]; then
      echo "     Changes in new version:"
      echo "$DIFF_OUTPUT" | head -20
      echo "     Full diff: diff $SETTINGS_DEST $SETTINGS_SRC"
      echo "     To accept new version: cp $SETTINGS_SRC $SETTINGS_DEST"
    else
      echo "     No differences found — already up to date"
    fi
  else
    echo "     Compare: $SETTINGS_SRC vs $SETTINGS_DEST"
  fi
fi

# ── Verify critical files ─────────────────────────────────────────────────────
echo "Verifying critical test enforcement files..."
CRITICAL_FILES=(
  "$DEST_SKILLS/testing/test-case-traceability.md"
  "$DEST_SKILLS/testing/test-case-generation.md"
  "$DEST_AGENTS_CORE/spec_test_reconciler.md"
  "$DEST_AGENTS_CORE/acceptance_test_agent.md"
  "$DEST_AGENTS_CORE/pipeline_completeness_agent.md"
  "$DEST_AGENTS_CORE/e2e_orchestrator.md"
  "$DEST_COMMANDS/develop-orchestrator.md"
)
MISSING=0
for f in "${CRITICAL_FILES[@]}"; do
  if [ ! -f "$f" ]; then
    echo "  ⚠ MISSING: $f"
    MISSING=$((MISSING + 1))
  fi
done
if [ "$MISSING" -eq 0 ]; then
  echo "  ✅ All critical test enforcement files present"
else
  echo "  ⚠ $MISSING critical file(s) missing — test enforcement may not work correctly"
fi

echo
echo "════════════════════════════════════════════════════════════"
echo "✅ Installation complete"
echo
echo "  $CMD_COUNT commands | $AGENT_COUNT agents | $TMPL_COUNT templates | $SKILL_COUNT skill packs"
echo
echo "════════════════════════════════════════════════════════════"
echo
echo "Getting started:"
echo "  1. cd <your-new-project>"
echo "  2. mkdir requirements"
echo "  3. Copy your specs, user stories, or pitch deck into requirements/"
echo "  4. Optionally add requirements/IMPLEMENTATION_GUIDELINES.md"
echo "  5. Open Claude Code and run: /startup:init   (or /startup:autonomous for the full pipeline)"
echo
echo "Commands (/startup:<command>):"
echo "  ┌─────────────────┬────────────────────────────────────────────────┐"
echo "  │ Pipeline         │                                                │"
echo "  ├─────────────────┼────────────────────────────────────────────────┤"
echo "  │ product-workflows│ Product workflow intelligence (docs+video+API) │"
echo "  │ research         │ Deep market & product research                 │"
echo "  │ init             │ Create BRD + IMPL_GUIDELINES, generate agents  │"
echo "  │ map              │ Codebase knowledge base (4 focus areas)        │"
echo "  │ discuss          │ Surface assumptions + decisions before /plan   │"
echo "  │ plan             │ Generate phase specs + goal verification       │"
echo "  │ develop          │ Implement + test + review + gate               │"
echo "  │ deploy           │ Build + migrate + deploy + health check        │"
echo "  │ autonomous       │ Full pipeline end-to-end (one checkpoint)      │"
echo "  │ accept           │ Global acceptance + release notes              │"
echo "  ├─────────────────┼────────────────────────────────────────────────┤"
echo "  │ Session/Workflow │                                                │"
echo "  ├─────────────────┼────────────────────────────────────────────────┤"
echo "  │ pause            │ Save session state for later resumption        │"
echo "  │ resume           │ Restore paused session and continue            │"
echo "  │ workstream       │ Manage parallel workstreams (create/merge)     │"
echo "  ├─────────────────┼────────────────────────────────────────────────┤"
echo "  │ Standalone       │                                                │"
echo "  ├─────────────────┼────────────────────────────────────────────────┤"
echo "  │ test             │ Run tests standalone                           │"
echo "  │ review           │ Code review on current changes                 │"
echo "  │ optimize         │ Dead code removal + performance                │"
echo "  │ benchmark        │ Performance tracking + regression detection    │"
echo "  │ status           │ Show phase progress                            │"
echo "  ├─────────────────┼────────────────────────────────────────────────┤"
echo "  │ Issue Resolution │                                                │"
echo "  ├─────────────────┼────────────────────────────────────────────────┤"
echo "  │ hotfix           │ Fast-track bug fix (scoped test + review)      │"
echo "  │ diagnose         │ Trace symptom to root cause                    │"
echo "  │ rollback         │ Roll back deployment to previous state         │"
echo "  │ reset-phase      │ Reset a phase for re-development              │"
echo "  ├─────────────────┼────────────────────────────────────────────────┤"
echo "  │ Diagnostics      │                                                │"
echo "  ├─────────────────┼────────────────────────────────────────────────┤"
echo "  │ health           │ Pipeline state diagnosis + auto-repair         │"
echo "  │ forensics        │ Post-mortem for failed pipeline runs           │"
echo "  └─────────────────┴────────────────────────────────────────────────┘"
echo
