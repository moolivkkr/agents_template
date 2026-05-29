---
command: rules-plugin
description: "Run the full plugin rule development pipeline: market research → rule authoring → FP optimization → corpus completeness → DB publish → UI registration → tests. Works for any plugin: edr, dlp, certificates, siem, soar, secrets."
arguments:
  - name: plugin
    required: true
    description: "Plugin ID to operate on: edr | dlp | certificates | siem | soar | secrets"
  - name: scope
    required: false
    description: "Scope for research — interpreted per plugin. EDR: tactic IDs (TA0006,TA0008) or technique IDs (T1003). DLP: data categories (pii,financial) or channels (email,web). Omit to use --gap-fill."
  - name: gap_fill
    required: false
    default: false
    description: "Auto-discover all uncovered HIGH-priority items for the plugin and fill them."
  - name: wave
    required: false
    description: "Start at a specific wave number. Omit to auto-detect from pipeline state."
  - name: stage
    required: false
    description: "Resume at a specific stage (1-7) without re-running earlier stages."
  - name: no_ui
    required: false
    default: false
    description: "Skip Stage 6 UI registration. Use for backend-only or CLI-only plugins."
  - name: dry_run
    required: false
    default: false
    description: "Run all stages but skip API push and Artifactory publish."
  - name: max_loops
    required: false
    default: 5
    description: "Maximum feedback loop iterations before forcing proceed to publish."
---

# /plugin — Plugin Rule Development Pipeline

Read `.claude/agents/generated/rule_pipeline_orchestrator.md` and execute it for the specified plugin.

## Plugin Manifest

First, verify the plugin manifest exists:

```bash
PLUGIN_ID="{{plugin}}"
PLUGIN_MANIFEST=".claude/agents/plugins/${PLUGIN_ID}.json"

if [ ! -f "$PLUGIN_MANIFEST" ]; then
  echo "No plugin manifest found at $PLUGIN_MANIFEST"
  echo ""
  echo "Available plugins:"
  ls .claude/agents/plugins/*.json | xargs -I{} basename {} .json
  echo ""
  echo "To add a new plugin, create $PLUGIN_MANIFEST"
  echo "Use .claude/agents/plugins/edr.json as a template."
  exit 1
fi

PLUGIN_NAME=$(python3 -c "import json; print(json.load(open('$PLUGIN_MANIFEST'))['plugin_name'])")
echo "Plugin: $PLUGIN_NAME ($PLUGIN_ID)"
```

## Execute Pipeline

Execute the rule_pipeline_orchestrator for this plugin, spawning separate agents per stage and verifying outputs between stages.

Arguments to pass through:
- `--plugin {{plugin}}`
- `--scope {{scope}}` (if provided)
- `--gap-fill` (if gap_fill is true or scope is empty)
- `--wave {{wave}}` (if provided)
- `--stage {{stage}}` (if provided)
- `--no-ui` (if no_ui is true)
- `--dry-run` (if dry_run is true)
- `--max-loops {{max_loops}}`

Follow the orchestrator exactly — spawn separate agents per stage, verify gate artifacts between stages, and write pipeline state to `agent_state/{{plugin}}_pipeline/state.json`.
