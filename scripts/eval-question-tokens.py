#!/usr/bin/env python3
"""eval-question-tokens.py — what does a question cost the main session? A/B token accounting with real
`claude -p` runs. Stdlib only.

  run     --questions Q.json --arm A=DIR --arm B=DIR [--reps N] --out OUT [--budget-usd 25] [--per-run-usd 1.5]
          [--model M] [--allow-bash "python3 .claude/hooks/sdlc-graph.py *"] [--only q01,q02] [--dry-run]
              Runs every question in every arm (cwd = that arm's directory), one fresh, non-persisted, read-only
              session per run, interleaved A/B per question so cache warmth and time drift hit both arms alike.
              Resumable: a run already recorded in OUT/runs.jsonl is skipped. Stops BEFORE a run that could push
              the summed total_cost_usd past --budget-usd (each run is also capped by --max-budget-usd).
  sheet   --out OUT [--seed 7]
              Writes OUT/grading-sheet.md: every answer, shuffled, labelled only by an opaque id (arm hidden),
              next to the question's answer key; and OUT/grading-map.json (id → run). Fill OUT/grades.json
              {"<id>": "correct"|"partial"|"wrong"}.
  report  --out OUT [--questions Q.json] [--bar 0.20] [--fixed-overhead-tokens N]
              Per-question and aggregate tables (median/mean total tokens, cost, turns, API steps, tool calls,
              wall time, accuracy per arm) and the keep/disable verdict against the bar: KEEP only if the median
              total tokens per question drops by >= bar AND accuracy does not drop.

Token accounting (verified against https://code.claude.com/docs/en/agent-sdk/cost-tracking and
https://code.claude.com/docs/en/headless, Claude Code 2.1.285):
  * the final `result` message carries total_cost_usd, num_turns, duration_ms, usage (main loop only) and
    modelUsage (every model, subagents included: inputTokens, outputTokens, cacheReadInputTokens,
    cacheCreationInputTokens, costUSD). Totals here come from modelUsage, so helper/subagent calls count.
  * per-step `assistant` messages share an id across parallel tool calls: API steps = distinct message ids
    (main loop, parent_tool_use_id null); their output_tokens are placeholders and are not used.
  * total tokens = input + cache_read + cache_creation + output (all models).

Read-only harness (verified against https://code.claude.com/docs/en/cli-reference and
https://code.claude.com/docs/en/permission-modes): --tools Read,Grep,Glob,Bash (no Write/Edit/Agent/Web);
--permission-mode dontAsk + --permission-prompts none (anything not pre-approved is denied, never prompted;
read-only commands like ls/cat/grep still run); --allowedTools Read Grep Glob + the one Bash pattern;
--setting-sources project (the user's and the project's local allow rules do not apply);
--no-session-persistence; --max-budget-usd per run.
"""
import argparse, hashlib, json, os, random, statistics, subprocess, sys, time

SUFFIX = "\n\n(Answer concisely, citing file paths. This is a read-only question: do not modify any file.)"


def load_questions(p):
    q = json.load(open(p))
    return q["questions"] if isinstance(q, dict) else q


def done_runs(out):
    p = os.path.join(out, "runs.jsonl")
    if not os.path.exists(p):
        return []
    return [json.loads(l) for l in open(p) if l.strip()]


def parse_stream(path):
    """→ dict of the metrics for one stream-json transcript."""
    res, init, steps, tools, bash, texts = None, None, set(), {}, [], []
    for line in open(path, errors="replace"):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        t = d.get("type")
        if t == "system" and d.get("subtype") == "init":
            init = d
        elif t == "assistant" and not d.get("parent_tool_use_id"):
            m = d.get("message") or {}
            if m.get("id"):
                steps.add(m["id"])
            for c in m.get("content") or []:
                if c.get("type") == "tool_use":
                    tools[c.get("name")] = tools.get(c.get("name"), 0) + 1
                    if c.get("name") == "Bash":
                        bash.append(str((c.get("input") or {}).get("command", ""))[:300])
                elif c.get("type") == "text":
                    texts.append(c.get("text", ""))
        elif t == "result":
            res = d
    out = {"model": (init or {}).get("model"), "api_steps": len(steps), "tool_calls": sum(tools.values()),
           "tools": tools, "bash": bash}
    if res is None:
        out.update({"error": "no result message", "answer": "\n".join(texts)[-4000:]})
        return out
    mu = res.get("modelUsage") or {}
    tok = {k: sum(int(v.get(f) or 0) for v in mu.values()) for k, f in
           (("input", "inputTokens"), ("output", "outputTokens"), ("cache_read", "cacheReadInputTokens"),
            ("cache_creation", "cacheCreationInputTokens"))}
    if not mu:                                   # older CLI: fall back to the main-loop usage
        u = res.get("usage") or {}
        tok = {"input": u.get("input_tokens", 0), "output": u.get("output_tokens", 0),
               "cache_read": u.get("cache_read_input_tokens", 0), "cache_creation": u.get("cache_creation_input_tokens", 0)}
    out.update(tok)
    out.update({"total_tokens": sum(tok.values()), "cost_usd": res.get("total_cost_usd") or 0.0,
                "num_turns": res.get("num_turns"), "duration_ms": res.get("duration_ms"),
                "subtype": res.get("subtype"), "is_error": res.get("is_error"),
                "permission_denials": len(res.get("permission_denials") or []),
                "models": sorted(mu), "answer": res.get("result") if isinstance(res.get("result"), str) else "\n".join(texts)})
    return out


def run_one(arm_dir, prompt, a, raw_path):
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose",
           "--tools", "Read,Grep,Glob,Bash", "--allowedTools", "Read", "Grep", "Glob", f"Bash({a.allow_bash})",
           "--permission-mode", "dontAsk", "--permission-prompts", "none", "--setting-sources", "project",
           "--no-session-persistence", "--max-budget-usd", str(a.per_run_usd)]
    if a.model:
        cmd += ["--model", a.model]
    env = dict(os.environ)
    if a.cache_ttl:
        env["CLAUDE_CODE_PROMPT_CACHE_TTL"] = a.cache_ttl
    t0 = time.time()
    with open(raw_path, "w") as f:
        p = subprocess.run(cmd, cwd=arm_dir, stdout=f, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, text=True,
                           env=env, timeout=a.timeout)
    m = parse_stream(raw_path)
    m["wall_s"] = round(time.time() - t0, 1)
    m["exit_code"] = p.returncode
    if p.stderr.strip():
        m["stderr"] = p.stderr.strip()[-500:]
    return m


def cmd_run(a):
    qs = load_questions(a.questions)
    if a.only:
        keep = set(a.only.split(","))
        qs = [q for q in qs if q["id"] in keep]
    arms = dict(x.split("=", 1) for x in a.arm)
    os.makedirs(os.path.join(a.out, "raw"), exist_ok=True)
    prev = done_runs(a.out)
    have = {(r["qid"], r["arm"], r["rep"]) for r in prev}
    spent = sum(r.get("cost_usd") or 0 for r in prev)
    print(f"already recorded: {len(prev)} run(s), ${spent:.2f}", flush=True)
    for rep in range(1, a.reps + 1):
        for q in qs:
            order = sorted(arms) if int(hashlib.sha1(f"{q['id']}{rep}".encode()).hexdigest(), 16) % 2 else list(reversed(sorted(arms)))
            for arm in order:
                if (q["id"], arm, rep) in have:
                    continue
                if spent + a.per_run_usd > a.budget_usd:
                    print(f"STOP: ${spent:.2f} spent; another run could exceed the ${a.budget_usd} cap", flush=True)
                    return 3
                if a.dry_run:
                    print(f"would run {q['id']} {arm} rep {rep} in {arms[arm]}")
                    continue
                raw = os.path.join(a.out, "raw", f"{q['id']}-{arm}-{rep}.jsonl")
                m = run_one(arms[arm], q["question"] + SUFFIX, a, raw)
                rec = {"qid": q["id"], "kind": q.get("kind"), "arm": arm, "rep": rep, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **m}
                with open(os.path.join(a.out, "runs.jsonl"), "a") as f:
                    f.write(json.dumps(rec) + "\n")
                spent += m.get("cost_usd") or 0
                print(f"{q['id']} {arm} r{rep}: {m.get('total_tokens')} tok ${m.get('cost_usd', 0):.3f} steps {m.get('api_steps')} "
                      f"tools {m.get('tool_calls')} {m.get('wall_s')}s {m.get('subtype')} — total ${spent:.2f}", flush=True)
    return 0


def cmd_sheet(a):
    runs = [r for r in done_runs(a.out) if r.get("answer") is not None]
    qs = {q["id"]: q for q in load_questions(a.questions)} if a.questions else {}
    rnd = random.Random(a.seed)
    rnd.shuffle(runs)
    mp, lines = {}, ["# Grading sheet (arm hidden)\n"]
    for k, r in enumerate(sorted(runs, key=lambda r: r["qid"])):
        gid = hashlib.sha1(f"{a.seed}{r['qid']}{r['arm']}{r['rep']}".encode()).hexdigest()[:8]
        mp[gid] = {"qid": r["qid"], "arm": r["arm"], "rep": r["rep"]}
        q = qs.get(r["qid"], {})
        ans = (r.get("answer") or "").replace("sdlc-graph.py", "<tool>").replace("sdlc-graph", "<tool>")
        lines += [f"## {r['qid']} · {gid}", f"**Q:** {q.get('question', '')}", f"**Key:** {q.get('key', '')}",
                  f"**Grade rule:** {q.get('grade', '')}", "", "```", ans.strip()[:3000], "```", ""]
    open(os.path.join(a.out, "grading-sheet.md"), "w").write("\n".join(lines))
    json.dump(mp, open(os.path.join(a.out, "grading-map.json"), "w"), indent=1)
    print(f"{len(mp)} answers → {a.out}/grading-sheet.md")
    return 0


def med(xs):
    return statistics.median(xs) if xs else 0


def mean(xs):
    return statistics.mean(xs) if xs else 0


def cmd_report(a):
    runs = done_runs(a.out)
    grades = {}
    gp, mp_p = os.path.join(a.out, "grades.json"), os.path.join(a.out, "grading-map.json")
    if os.path.exists(gp) and os.path.exists(mp_p):
        mp = json.load(open(mp_p))
        for gid, g in json.load(open(gp)).items():
            k = mp[gid]
            grades[(k["qid"], k["arm"], k["rep"])] = g
    qs = {q["id"]: q for q in load_questions(a.questions)} if a.questions else {}
    arms = sorted({r["arm"] for r in runs})
    score = {"correct": 1.0, "partial": 0.5, "wrong": 0.0}
    fixed = a.fixed_overhead_tokens

    def tot(r):
        return (r.get("total_tokens") or 0) + fixed * (r.get("api_steps") or 0)
    lines = ["| q | kind | " + " | ".join(f"{x} tokens (med) | {x} $ | {x} steps | {x} grade" for x in arms) + " | Δ tokens B vs A |",
             "|---|---|" + "---|" * (4 * len(arms)) + "---|"]
    per_q = {}
    for qid in sorted({r["qid"] for r in runs}):
        row = [qid, qs.get(qid, {}).get("kind", "")]
        meds = {}
        for arm in arms:
            rs = [r for r in runs if r["qid"] == qid and r["arm"] == arm]
            meds[arm] = med([tot(r) for r in rs])
            gs = [grades.get((qid, arm, r["rep"])) for r in rs]
            row += [f"{int(meds[arm]):,}" + (f" ({', '.join(f'{int(tot(r)):,}' for r in rs)})" if len(rs) > 1 else ""),
                    f"{sum(r.get('cost_usd') or 0 for r in rs) / max(1, len(rs)):.3f}",
                    f"{med([r.get('api_steps') or 0 for r in rs]):g}", "/".join(g[0] if g else "?" for g in gs)]
        d = (meds[arms[-1]] - meds[arms[0]]) / meds[arms[0]] if len(arms) > 1 and meds[arms[0]] else 0
        per_q[qid] = (meds, d)
        row.append(f"{d:+.0%}")
        lines.append("| " + " | ".join(row) + " |")
    agg = ["", "| arm | runs | median total tokens / question | mean | median $ | total $ | median steps | median tool calls | "
               "median wall s | accuracy (correct=1, partial=.5) | correct | partial | wrong | ungraded |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    summary = {}
    for arm in arms:
        rs = [r for r in runs if r["arm"] == arm]
        qmed = [per_q[q][0][arm] for q in per_q]            # per-question median, then the median over questions
        gs = [grades.get((r["qid"], arm, r["rep"])) for r in rs]
        graded = [g for g in gs if g]
        acc = mean([score[g] for g in graded]) if graded else None
        summary[arm] = {"median": med(qmed), "mean": mean(qmed), "acc": acc}
        agg.append(f"| {arm} | {len(rs)} | {int(med(qmed)):,} | {int(mean(qmed)):,} | {med([r.get('cost_usd') or 0 for r in rs]):.3f} | "
                   f"{sum(r.get('cost_usd') or 0 for r in rs):.2f} | {med([r.get('api_steps') or 0 for r in rs]):g} | "
                   f"{med([r.get('tool_calls') or 0 for r in rs]):g} | {med([r.get('wall_s') or 0 for r in rs]):g} | "
                   f"{'' if acc is None else f'{acc:.2f}'} | {gs.count('correct')} | {gs.count('partial')} | {gs.count('wrong')} | {gs.count(None)} |")
    verdict = ""
    if len(arms) == 2:
        A, B = arms
        drop = (summary[A]["median"] - summary[B]["median"]) / summary[A]["median"] if summary[A]["median"] else 0
        acc_ok = summary[A]["acc"] is None or summary[B]["acc"] is None or summary[B]["acc"] >= summary[A]["acc"]
        keep = drop >= a.bar and acc_ok
        verdict = (f"\nmedian total tokens per question: {A} {int(summary[A]['median']):,} → {B} {int(summary[B]['median']):,} "
                   f"(saving {drop:+.1%}; bar {a.bar:.0%}); accuracy {A} {summary[A]['acc']} → {B} {summary[B]['acc']}\n"
                   f"VERDICT: {'KEEP enabled' if keep else 'DISABLE by default'}"
                   + (f" (fixed overhead {fixed} tok/step added)" if fixed else ""))
        kinds = {}
        for qid, (meds, d) in per_q.items():
            kinds.setdefault(qs.get(qid, {}).get("kind", "?"), []).append(d)
        verdict += "\nmedian Δ tokens by kind (B vs A): " + ", ".join(f"{k} {med(v):+.0%} (n={len(v)})" for k, v in sorted(kinds.items()))
    txt = "\n".join(lines + agg) + verdict + "\n"
    print(txt)
    open(os.path.join(a.out, "report.md" if not fixed else f"report-overhead{fixed}.md"), "w").write(txt)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("run")
    r.add_argument("--questions", required=True); r.add_argument("--arm", action="append", required=True)
    r.add_argument("--reps", type=int, default=1); r.add_argument("--out", required=True)
    r.add_argument("--budget-usd", type=float, default=25.0); r.add_argument("--per-run-usd", type=float, default=1.5)
    r.add_argument("--model"); r.add_argument("--allow-bash", default="python3 .claude/hooks/sdlc-graph.py *")
    r.add_argument("--only"); r.add_argument("--dry-run", action="store_true"); r.add_argument("--timeout", type=int, default=900)
    r.add_argument("--cache-ttl", default="5m", help="CLAUDE_CODE_PROMPT_CACHE_TTL for the runs (cost only; '' = CLI default)")
    s = sp.add_parser("sheet"); s.add_argument("--out", required=True); s.add_argument("--questions"); s.add_argument("--seed", type=int, default=7)
    rp = sp.add_parser("report"); rp.add_argument("--out", required=True); rp.add_argument("--questions")
    rp.add_argument("--bar", type=float, default=0.20); rp.add_argument("--fixed-overhead-tokens", type=int, default=0)
    a = ap.parse_args()
    return {"run": cmd_run, "sheet": cmd_sheet, "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
