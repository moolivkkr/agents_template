# Track C: spec-driven / SDLC-process frameworks (checked 2026-10-02)

Scope: what is new since our 2026-09-30 review (§2–3) for frameworks it covered, plus frameworks it
missed (Kiro, Tessl, Agent OS, cc-sdd v3, MoAI-ADK, Spec Kitty, Conductor). The focus is the owner's
current situation: release 1 is done and new phases are starting. All URLs below were checked on 2026-10-02.

## Headline

**No framework treats a "release" as a first-class unit** (release N contains phases, has a baseline,
a version bump, its own changelog and a readiness verdict). Several frameworks hold good pieces of
that, and they fit together:
- OpenSpec: living specs plus delta changes that are archived on completion.
- cc-sdd v3: an intake router that decides whether new work extends an existing spec or needs a new one.
- BMAD: an evidence-based epic retrospective whose verdict gates the next epic.
- Kiro: bugfix specs with "SHALL CONTINUE TO" regression clauses.

Our model has a single release. `/accept` Step 6 assigns `v1.0.0`, or `v0.<phase>.0` when phases are
partial (`.claude/commands/accept.md` ~L725–790). Phases are tagged `phase-N-complete`, but nothing
represents "release 2". That is the gap most relevant to the owner right now.

## What changed since 2026-09-30 (covered frameworks)

| Framework | New | Source |
|---|---|---|
| Spec Kit | **1.1.0 (2026-10-02)**: custom workflow step types, workflow slots, exact catalog release pinning. **1.0.13 (09-29)**: task→GitHub-issue conversion moved into a bundled GitHub extension (`/speckit.taskstoissues` is being deprecated in core). **1.0.9 (09-21)**: first-party **bugfix** bundle (assess → human review gate → fix → test) and **assess** bundle (intake → research → define → shape → decide → verdict gate; handing off to `/speckit.specify` stays manual). 1.0.6–1.0.8: "contribution evidence gate", per-step integration config, contract-driven guidance. I didn't read what the evidence gate actually checks. | https://github.com/github/spec-kit/releases, PR #4504 |
| OpenSpec | **v1.14.0 (09-30)**: browse archived changes (JSON), workflow status dashboard per active change, 10 more tools supported. **v1.13.x**: warns on changes that have **no delta specs**, retires capabilities through delta sections, protects fenced code blocks from silent rewrites, "Next:" guidance in status. Multi-repo "stores" (beta). | https://github.com/Fission-AI/OpenSpec/releases |
| BMAD | Latest stable is **v6.12.0 (09-04)**: "Build decides how much ceremony a change needs *after* investigating it", and review triage logs a verdict plus evidence for every finding. v6.11 (08-10): 14 core skills reduced to 8, `bmad-review` gained configurable lenses, and the retrospective was rebuilt to judge an epic against its real artifacts. Our 09-30 table mentioned "v7"; the releases page shows v6.12 as latest, so treat v7 as pre-release/unverified. | https://github.com/bmad-code-org/BMAD-METHOD/releases |
| Superpowers | **v6.4.2 (09-25)**: "a plan records decisions, not a transcript of the code". Plans now hold signatures, test assertions and spec values, and a self-check compares plan length to spec length. Vendor claim: 9/9 planted-defect probes still caught. | https://github.com/obra/superpowers/releases |
| Compound Eng. | v3.29.0 (09-25): learnings name their retirement condition. v3.30.2 (10-01): caps whole-run spend and shows workers why cases fail. v3.26.3: review depth sized by consequence, not line count. | https://github.com/EveryInc/compound-engineering-plugin/releases |
| Task Master | No release after mid-September is visible. The page's latest is 0.43.1; the year shown (2025) looks wrong. **Unverified.** | https://github.com/eyaltoledano/claude-task-master/releases |
| Kiro (new to us) | **09-30 IDE 1.2.4 / CLI 2.26 / Web: Workflows**: reusable multi-step plans where **each step runs in its own agent session**, with live "Steer". Also asks before an agent edits hook/power/workflow files in untrusted workspaces. CLI 2.25 adds a `SessionEnd` hook. | https://kiro.dev/changelog/ |

## Capability table

| Capability | Who does it best (how, URL) | Us | Value | Effort | Caveats |
|---|---|---|---|---|---|
| **Release as a unit** (R2 = set of phases, baseline, semver bump, per-release changelog, readiness) | Nobody end to end. OpenSpec: `specs/` = current truth after archive, archive history browsable (v1.14). Spec Kit community catalog lists *Spec Changelog*, *Ship Release*, *Spec Roadmap*, *API Evolve* (semver/deprecation). https://github.github.com/spec-kit/community/extensions.html | **Partial**: one-shot `/accept` Step 6 numbering, `phase-N-complete` tags, `docs/RELEASE_NOTES.md` | **H** | M | Community extension quality unverified |
| **Living specs + delta changes (brownfield)** | OpenSpec ADDED/MODIFIED/REMOVED/RENAMED. v1.13 now *flags changes without deltas* and supports capability retirement | **No** (known open item); specs rewritten per phase | **H** | M | Merge must refuse to drop scenarios (OpenSpec does) |
| **New-work intake router** (extend spec / new spec / no spec / decompose; ceremony sized after investigating) | cc-sdd v3 `/kiro-discovery` → `brief.md` + `roadmap.md`; BMAD 6.12 Build; Spec Kit `assess` bundle with verdict gate. https://cdn.jsdelivr.net/gh/gotalab/cc-sdd@main/README.md | **Partial**: `product_manager` amends BRD; `/discuss`, `/hotfix` are separate entry points; nothing routes | **H** | S–M | |
| **Evidence-based retrospective that gates the next unit** | BMAD `bmad-retrospective`: aggregate defects across sessions (architecture drift, duplicated helpers, file bloat), cross-ticket seams, spec reconciliation, **follow-through on the previous retro's action items**, verdict accepted / accepted-with-open-items / rejected that gates the next epic. https://docs.bmad-method.org/build/finish-an-epic/ | **Partial**: per-phase lessons, `carried_forward[]` escalates to BLOCKING after 3 phases (`backend_audit_agent.md` L111–130), `/worklog`. No cross-phase aggregate-defect view, no action-item follow-through check | M–H | S | |
| **Bugfix spec with "unchanged behavior" clauses** | Kiro `bugfix.md`: Current (WHEN…THEN), Expected (SHALL), **Unchanged (SHALL CONTINUE TO)**, each made into properties (bug reproduces / fixed / no regression). https://kiro.dev/docs/specs/bugfix-specs/ | **Partial**: `/hotfix` is reproduction-first; no unchanged-behavior clause | M | S | |
| **Correctness properties derived from EARS → property-based tests, linked to requirement and task** | Kiro: properties extracted at design time; hovering a property shows its requirement and task; shrinking; on failure, choose code vs test vs requirement. https://kiro.dev/docs/specs/correctness/ | **Partial**: `.claude/skills/testing/property-based.md` exists; `spec_writer` emits no TC-PROP rows | M | M | Kiro's PBT quality not independently verified |
| **Scoped steering / standards injection** | Kiro steering: always / fileMatch / manual / auto inclusion, global vs workspace, AGENTS.md. Agent OS v3 (2026-01-20): `/discover-standards` mines standards from code, `index.yml` auto-selects them, `/inject-standards`. https://kiro.dev/docs/steering/ , https://github.com/buildermethods/agent-os/discussions/310 | **Partial**: agent `skill_packs` frontmatter, CLAUDE.md, PROJECT_FACTS. Nothing mines a target project's *own* conventions into path-scoped rules | M | S | |
| **Multi-spec roadmap → dependency-wave batch with cross-spec interface review** | cc-sdd `/kiro-spec-batch` | **Partial**: `project_planner` + Phase N+1 sketch; `breaking_change_reviewer` after the fact | M | M | |
| **Fresh agent session per workflow step** | Kiro Workflows (09-30), Spec Kit 1.x engine | **No** (known open item) | — | — | Kiro adds independent confirmation that this is the direction |
| **Spec-task completion hook** | Kiro *Pre/Post Task Execution* hook triggers. https://kiro.dev/docs/hooks/types/ | **No** (known open item B7) | — | — | Useful model for B7 |
| **Issue-tracker sync** | Spec Kit bundled GitHub extension (1.0.13); community Jira/Linear | **No** (no Jira/Linear/`gh issue` in commands) | L | S | Solo owner, so low value |
| **Logical revert by track/phase/task** | Conductor `/conductor-revert` (git-aware). https://github.com/gemini-cli-extensions/conductor (3.8k★) | **Partial**: `/reset-phase`, phase tags, `/rollback` (deploy) | L | S | |
| **Plans as decisions, not code** | Superpowers 6.4.2 | Our TRDs are already contracts, not code | L | — | |

## Strongest recommendations

1. **Release ledger (`/release`) on top of the phase model.** Add `docs/RELEASES.md` and
   `agent_state/releases/<R>/release.json`. Each release records its phases, the FR set it targets, a
   baseline git sha/tag (`release-1.0.0`), and a semver bump rule: a MAJOR when breaking_change_reviewer
   reports breaks, MINOR for new FRs, PATCH for hotfixes. `/accept --release=R` re-proves only that
   release's FRs plus full regression and writes `CHANGELOG.md` (Keep-a-Changelog format) from deltas,
   not from all manifests. `/status` shows the current release. *This is the owner's immediate need.*
2. **Living specs + delta changes (build the known open item now, scoped to R2).** Freeze R1's specs
   as `docs/specs/` (current truth). Phase specs for R2 must carry ADDED/MODIFIED/REMOVED FR/TC
   sections against them. The gate merges deltas at `gate.passed` and refuses a merge that drops a TC
   row without a REMOVED entry. Add OpenSpec's "warn on a change with no delta" check to `brd_spec_reconciler`.
3. **Intake router before `/plan`.** One `/intake <request>` step classifies new work in one of four ways:
   extend existing FR/spec, new FR, bugfix (go to `/hotfix` with Kiro-style *Unchanged Behavior* clauses that
   become regression TCs), or roadmap-sized (decompose into phases). It sizes ceremony *after* a short
   investigation, as BMAD 6.12 does, and writes `brief.md` plus a release/phase assignment that
   `product_manager` turns into BRD amendments.
4. **Phase retrospective with verdict and follow-through.** Extend the gate's post-step with a
   `retrospective` pass over the phase diff from `phase-(N-1)-complete`. It covers architecture drift,
   duplicated helpers, files growing across phases, and whether the previous retro's action items
   closed. The verdict is accepted / accepted-with-open-items / rejected, and open items become
   `carried_forward[]` with owners.
5. **EARS → TC-PROP rows.** `spec_writer` marks universally quantified SHALLs (validation, round-trips,
   tenant isolation, idempotency) as properties and emits TC-PROP-* rows for the unit tier, using the
   existing property-based skill. Do this after items 1–3.

## Do NOT copy

- **Tessl "spec-as-source" regeneration.** The framework is still closed beta, it was repositioned as a
  "Skills Registry" in January 2026, and a June 2026 review found the same spec produced different code
  on each run (https://codemyspec.com/blog/tessl-review; that review is the source for all three points). The registry's
  "3,000+/10,000+ specs" figures are vendor claims.
- **Agent OS v3's removal of orchestration.** It removed implementation and orchestration on the grounds
  that frontier models handle them now. Our evidence (dropped reviews, the roster gate) says the
  opposite for us. Borrow only `/discover-standards`.
- **Kiro `/tools trust-all`** (CLI 2.24) and Task Master's skip-permissions loop. Both conflict with sdlc-guard.
- **Spec Kit community extensions as installs** (Spec Changelog, Ship Release, Time Machine, BrownKit).
  Borrow the ideas only; their quality is unreviewed, and our supply-chain rule applies.
- **The heavy BMAD persona and agile ceremony** (sprint planning, story points). BMAD itself is cutting it
  back (from 14 core skills to 8).

## Unverified

- What Spec Kit's "contribution evidence gate" (1.0.6) checks.
- The quality and maintenance of the Spec Kit community extensions named above (descriptions are from catalog listings only).
- Whether BMAD v7 exists as a pre-release. The releases page shows v6.12.0 (2026-09-04) as latest.
- Task Master's latest release date; the page's dates look inconsistent.
- Kiro's PBT effectiveness, and the Superpowers "9/9 probes" figure (vendor claims).
- cc-sdd v3 release date (not shown in the README), and the MoAI-ADK v3.1.x details (from the README only: GEARS
  requirements, plan/run/sync, TRUST 5, @MX/@NAV tag graph, DDD with characterization tests for
  low-coverage brownfield).
- Spec Kitty is at 4.0.0rc2 with review→accept→merge lanes and retrospectives (README); release date unknown.
