#!/usr/bin/env bash
# startup-agents installer
# Installs commands, core agents, templates, and skill packs to ~/.claude/
# After install, /init /plan /develop are available in any project.

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
DEST_COMMANDS="$CLAUDE_DIR/commands/startup"
DEST_AGENTS="$CLAUDE_DIR/agents"
DEST_SKILLS="$CLAUDE_DIR/skills"
DEST_TEMPLATES="$CLAUDE_DIR/agents/templates"

echo "startup-agents installer"
echo "========================"
echo "Source: $REPO_DIR"
echo "Target: $CLAUDE_DIR"
echo

# ── Commands ─────────────────────────────────────────────────────────────────
echo "Installing commands → $DEST_COMMANDS/"
mkdir -p "$DEST_COMMANDS"
cp "$REPO_DIR/.claude/commands/"*.md "$DEST_COMMANDS/"
echo "  ✅ $(ls "$REPO_DIR/.claude/commands/"*.md | wc -l | tr -d ' ') commands installed"

# ── Core agents ───────────────────────────────────────────────────────────────
echo "Installing core agents → $DEST_AGENTS/"
mkdir -p "$DEST_AGENTS"
cp "$REPO_DIR/.claude/agents/core/"*.md "$DEST_AGENTS/"
echo "  ✅ $(ls "$REPO_DIR/.claude/agents/core/"*.md | wc -l | tr -d ' ') core agents installed"

# ── Agent templates ───────────────────────────────────────────────────────────
echo "Installing agent templates → $DEST_TEMPLATES/"
mkdir -p "$DEST_TEMPLATES"
cp "$REPO_DIR/.claude/agents/templates/"*.md "$DEST_TEMPLATES/"
echo "  ✅ $(ls "$REPO_DIR/.claude/agents/templates/"*.md | wc -l | tr -d ' ') templates installed"

# ── Skill packs ───────────────────────────────────────────────────────────────
echo "Installing skill packs → $DEST_SKILLS/"
mkdir -p "$DEST_SKILLS"
cp -r "$REPO_DIR/.claude/skills/"* "$DEST_SKILLS/"
SKILL_COUNT=$(find "$REPO_DIR/.claude/skills" -name "*.md" | wc -l | tr -d ' ')
echo "  ✅ $SKILL_COUNT skill packs installed"

# ── settings.json (merge, don't overwrite) ────────────────────────────────────
SETTINGS_SRC="$REPO_DIR/.claude/settings.json"
SETTINGS_DEST="$CLAUDE_DIR/settings.json"
if [ ! -f "$SETTINGS_DEST" ]; then
  cp "$SETTINGS_SRC" "$SETTINGS_DEST"
  echo "  ✅ settings.json created"
else
  # Back up existing, then show diff so user knows what changed
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

echo
echo "✅ Installation complete"
echo
echo "Getting started:"
echo "  1. cd <your-new-project>"
echo "  2. mkdir requirements"
echo "  3. Copy your specs, user stories, or pitch deck into requirements/"
echo "  4. Optionally add requirements/IMPLEMENTATION_GUIDELINES.md"
echo "  5. Open Claude Code and run: /startup/init"
echo
echo "Command prefix: /startup/<command>"
echo "  /startup/init     — create BRD + IMPLEMENTATION_GUIDELINES, generate agents"
echo "  /startup/plan     — generate phase specs (TRDs + wireframes)"
echo "  /startup/develop  — implement + test + review + gate"
echo "  /startup/accept   — global acceptance after all phases"
echo "  /startup/test     — run tests standalone"
echo "  /startup/deploy   — build + migrate + deploy"
echo "  /startup/status   — show phase progress"
echo "  /startup/review   — standalone code review"
