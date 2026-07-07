# T-002 — UI form (frontend slice)
Surface: UI form | Est. cost: ~8 agents | Path: /plan (UI spec) → /develop (UI wave)

## Requirement
Build a "Create Widget" form (React) that POSTs to `POST /api/v1/widgets`. The form has a required
`name` field (1–64 chars) and an optional `description`. On submit it disables the button, shows a
spinner, and renders an inline field error if the API returns 400. On success it clears and shows a
success toast. The form must be keyboard-navigable and every input must have an associated `<label>`.

TC IDs the UI spec must enumerate and the component tests must annotate:
- **TC-UI-001** — empty `name` blocks submit and shows the required-field error.
- **TC-UI-002** — a 400 from the API renders the inline server error, button re-enabled.
- **TC-A11Y-001** — every input has an associated label; form is reachable by keyboard (tab order).

## Definition of done
- Component + its test file exist; tests annotate TC-UI-001, TC-UI-002, TC-A11Y-001 and pass.
- Client-side required validation on `name`; no submit fires with an empty name.
- Every input has a `<label htmlFor>` (or `aria-label`) — no orphan inputs.
- No `TODO`, `@ts-ignore`, or `.only(`/`skip(` left in the test file.

## Why this task exists (regression class it guards)
Catches the "UI shipped without the ux_designer spec / accessibility check" class and the
"validation exists in the spec but not the component" drift. If a wave change drops the
design_quality_reviewer or the ui_test_agent, this task's trajectory score falls.
