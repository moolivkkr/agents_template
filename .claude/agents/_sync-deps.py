#!/usr/bin/env python3
"""_sync-deps.py — keep every agent's `dependencies:` block consistent across the whole graph.

Model (see AGENT_SCHEMA.md §Dependency Fields):
  upstream    HAND-AUTHORED. Hard ordering — these must complete before this agent starts.
  runs_after  HAND-AUTHORED. Soft ordering — this agent reads their output when it exists.
  downstream  DERIVED. Exactly the agents that list this one in their upstream or runs_after.
              Never edit it by hand; this script rewrites it.

What a run does, for core/*.md, templates/*.tmpl (and generated/*.md when present):
  1. Renames retired/misspelled agent names (RENAMES) and drops names that resolve to no agent.
  2. MIGRATES one-sided claims: if A lists B downstream but B lists A in neither upstream nor
     runs_after, A is added to B.runs_after (the author said B consumes A — keep that, softly).
     Skipped when it would create a 2-cycle (B already in A.upstream).
  3. Re-derives every downstream list and rewrites the block in flow style.

Usage:  python3 _sync-deps.py            # rewrite in place
        python3 _sync-deps.py --check    # exit 1 if any file would change (CI / tests)
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Names that appear in dependency lists but are not (or no longer) agent files.
RENAMES = {
    "frontend_developer": ["ui_developer"],
    "test_developer": ["unit_test_agent", "integration_test_agent"],
}

# Curated corrections where the frontmatter contradicted /develop-orchestrator (the canonical executor).
# (agent, field) -> (remove from upstream, add to runs_after)
OVERRIDES = {
    # Track B acceptance runs IN PARALLEL with Track A reviewers; its real prerequisite is the Wave 3
    # e2e tier + the Wave 3.5 deploy. It reads reviewer reports only if present.
    "acceptance_test_agent": {"upstream_remove": ["code_reviewer_II", "security_reviewer"],
                              "upstream_add": ["e2e_orchestrator"],
                              "runs_after_add": ["code_reviewer_II", "security_reviewer"]},
    # code_reviewer_I and _II run in parallel in Track A; II de-duplicates against I's report IF it exists.
    "code_reviewer_II": {"upstream_remove": ["code_reviewer_I"], "runs_after_add": ["code_reviewer_I"]},
    # threat_model_agent both consumed and fed spec_writer (a 2-cycle). It runs in /plan after specs.
    "threat_model_agent": {"downstream_drop": ["spec_writer"]},
}


def files():
    out = []
    for sub, ext in (("core", ".md"), ("templates", ".tmpl"), ("generated", ".md"), ("", ".md")):
        d = os.path.join(HERE, sub)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.endswith(ext) and f not in ("AGENT_SCHEMA.md", "INVENTORY.md", "README.md"):
                out.append(os.path.join(d, f))
    return out


def agent_name(path):
    return re.sub(r"\.(md|tmpl)$", "", os.path.basename(path))


FM = re.compile(r"\A---\n(.*?)\n---\n", re.S)
DEP_BLOCK = re.compile(r"^dependencies:[ \t]*(?:\{\}|\[\])?\n((?:[ \t]+.*\n|[ \t]*\n)*)", re.M)


def parse_list(block, key):
    """Parse `key: [a, b]` or `key:\n  - a\n  - b` inside a dependencies block."""
    m = re.search(rf"^[ \t]+{key}:[ \t]*\[(.*?)\][ \t]*$", block, re.M)
    if m:
        return [x.strip().strip("\"'") for x in m.group(1).split(",") if x.strip()]
    m = re.search(rf"^([ \t]+){key}:[ \t]*\n((?:\1[ \t]+-[^\n]*\n)*)", block, re.M)
    if m:
        return [re.sub(r"\s*#.*$", "", x).strip().lstrip("-").strip().strip("\"'")
                for x in m.group(2).splitlines() if x.strip()]
    return []


def norm(n):
    n = re.sub(r"_\{\{PROJECT_NAME\}\}$", "", n)
    return n.split("(")[0].split("#")[0].strip().strip("`\"'")


def main():
    check = "--check" in sys.argv
    paths = files()
    names = {agent_name(p) for p in paths}
    data = {}
    for p in paths:
        text = open(p, encoding="utf-8").read()
        fm = FM.match(text)
        if not fm:
            continue
        m = DEP_BLOCK.search(fm.group(1) + "\n")
        block = m.group(1) if m else ""
        d = {k: [] for k in ("upstream", "runs_after", "downstream")}
        for k in d:
            for raw in parse_list(block, k):
                for n in RENAMES.get(norm(raw), [norm(raw)]):
                    if n in names and n != agent_name(p) and n not in d[k]:
                        d[k].append(n)
        data[agent_name(p)] = {"path": p, "text": text, "deps": d, "had_block": bool(m)}

    for a, ov in OVERRIDES.items():
        if a not in data:
            continue
        d = data[a]["deps"]
        for x in ov.get("upstream_add", []):
            if x in data and x not in d["upstream"]:
                d["upstream"].append(x)
        for x in ov.get("upstream_remove", []):
            d["upstream"] = [y for y in d["upstream"] if y != x]
        for x in ov.get("runs_after_add", []):
            if x in data and x not in d["runs_after"]:
                d["runs_after"].append(x)
        for x in ov.get("downstream_drop", []):
            d["downstream"] = [y for y in d["downstream"] if y != x]

    # 2. migrate one-sided downstream claims into the consumer's runs_after
    for a, info in data.items():
        for b in info["deps"]["downstream"]:
            bd = data[b]["deps"]
            if a in bd["upstream"] or a in bd["runs_after"]:
                continue
            if b in info["deps"]["upstream"]:  # would be a 2-cycle
                continue
            bd["runs_after"].append(a)
    # a name in upstream never also needs runs_after
    for info in data.values():
        d = info["deps"]
        d["runs_after"] = sorted(x for x in d["runs_after"] if x not in d["upstream"])

    # 3. derive downstream
    for info in data.values():
        info["deps"]["downstream"] = []
    for a, info in sorted(data.items()):
        for b in info["deps"]["upstream"] + info["deps"]["runs_after"]:
            if a not in data[b]["deps"]["downstream"]:
                data[b]["deps"]["downstream"].append(a)

    changed = []
    for a, info in sorted(data.items()):
        d = info["deps"]
        lines = ["dependencies:", f"  upstream: [{', '.join(d['upstream'])}]"]
        if d["runs_after"]:
            lines.append(f"  runs_after: [{', '.join(d['runs_after'])}]")
        lines.append(f"  downstream: [{', '.join(sorted(d['downstream']))}]  # derived by _sync-deps.py — do not hand-edit")
        new_block = "\n".join(lines) + "\n"
        text = info["text"]
        fm = FM.match(text)
        if fm is None:
            continue
        body = fm.group(1) + "\n"
        if info["had_block"]:
            new_fm = DEP_BLOCK.sub(lambda _: new_block, body, count=1)
        else:
            if not (d["upstream"] or d["runs_after"] or d["downstream"]):
                continue
            # insert before skill_packs: if present, else at end of frontmatter
            if re.search(r"^skill_packs:", body, re.M):
                new_fm = re.sub(r"^skill_packs:", new_block + "skill_packs:", body, count=1, flags=re.M)
            else:
                new_fm = body + new_block
        new_text = "---\n" + new_fm.rstrip("\n") + "\n---\n" + text[fm.end():]
        if new_text != text:
            changed.append(os.path.relpath(info["path"], HERE))
            if not check:
                open(info["path"], "w", encoding="utf-8").write(new_text)

    if check:
        if changed:
            print("dependency blocks out of sync (run .claude/agents/_sync-deps.py):")
            for c in changed:
                print("  " + c)
            sys.exit(1)
        print("dependency blocks in sync")
    else:
        print(f"rewrote {len(changed)} dependency blocks")


if __name__ == "__main__":
    main()
