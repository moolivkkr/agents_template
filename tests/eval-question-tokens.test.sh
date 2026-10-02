#!/usr/bin/env bash
# eval-question-tokens.test.sh — the A/B token harness (scripts/eval-question-tokens.py) on synthetic
# stream-json transcripts: totals come from the result's modelUsage (all models), API steps are distinct
# main-loop message ids (parallel tool calls share one), the budget cap stops a run before it starts,
# the grading sheet hides the arm, and the report applies the keep/disable bar. No `claude` call is made.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 - "$ROOT/scripts/eval-question-tokens.py" <<'EOF'
import importlib.util, json, os, subprocess, sys, tempfile
S = sys.argv[1]
spec = importlib.util.spec_from_file_location("eqt", S)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
fails = total = 0


def check(cid, want, got, label):
    global fails, total
    total += 1
    ok = want == got
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'} {cid} {label}" + ("" if ok else f"\n      want={want!r}\n      got ={got!r}"))


W = tempfile.mkdtemp(prefix="eqt.")
ev = [
    {"type": "system", "subtype": "init", "model": "claude-x"},
    {"type": "assistant", "parent_tool_use_id": None, "message": {"id": "m1", "content": [
        {"type": "tool_use", "name": "Bash", "input": {"command": "python3 .claude/hooks/sdlc-graph.py find x"}}]}},
    {"type": "assistant", "parent_tool_use_id": None, "message": {"id": "m1", "content": [
        {"type": "tool_use", "name": "Read", "input": {}}]}},
    {"type": "assistant", "parent_tool_use_id": "t9", "message": {"id": "sub1", "content": [
        {"type": "tool_use", "name": "Grep", "input": {}}]}},
    {"type": "assistant", "parent_tool_use_id": None, "message": {"id": "m2", "content": [{"type": "text", "text": "partial"}]}},
    {"type": "result", "subtype": "success", "is_error": False, "result": "the answer", "total_cost_usd": 0.5,
     "num_turns": 3, "duration_ms": 1000, "permission_denials": [{"tool": "Bash"}],
     "usage": {"input_tokens": 1, "output_tokens": 2, "cache_read_input_tokens": 3, "cache_creation_input_tokens": 4},
     "modelUsage": {"big": {"inputTokens": 10, "outputTokens": 20, "cacheReadInputTokens": 300, "cacheCreationInputTokens": 40},
                    "small": {"inputTokens": 5, "outputTokens": 1, "cacheReadInputTokens": 0, "cacheCreationInputTokens": 0}}},
]
p = os.path.join(W, "s.jsonl")
open(p, "w").write("noise line\n" + "\n".join(json.dumps(e) for e in ev) + "\n")
r = m.parse_stream(p)
check("E01", (15, 21, 300, 40, 376), (r["input"], r["output"], r["cache_read"], r["cache_creation"], r["total_tokens"]),
      "totals = modelUsage summed over every model (helpers/subagents count), not the main-loop usage")
check("E02", (2, 2, {"Bash": 1, "Read": 1}), (r["api_steps"], r["tool_calls"], r["tools"]),
      "API steps = distinct main-loop message ids; subagent messages excluded from the main-loop counts")
check("E03", ("the answer", 0.5, 1, "claude-x"), (r["answer"], r["cost_usd"], r["permission_denials"], r["model"]),
      "answer, cost, denials and model come from the result/init messages")
open(p, "w").write(json.dumps(ev[0]) + "\n" + json.dumps(ev[4]) + "\n")
check("E04", ("no result message", "partial"), (m.parse_stream(p).get("error"), m.parse_stream(p).get("answer")),
      "a transcript with no result message is recorded as an error with the text so far")

# budget cap: prior spend + per-run cap > budget → stop before any claude call
out = os.path.join(W, "out")
os.makedirs(out)
q = os.path.join(W, "q.json")
json.dump({"questions": [{"id": "q1", "kind": "k", "question": "?", "key": "K", "grade": "G"},
                         {"id": "q2", "kind": "j", "question": "??", "key": "K2", "grade": "G2"}]}, open(q, "w"))
rows = []
for qid, kind_tok in (("q1", (1000, 700)), ("q2", (1000, 900))):
    for arm, t in zip("AB", kind_tok):
        rows.append({"qid": qid, "arm": arm, "rep": 1, "total_tokens": t, "api_steps": 2, "cost_usd": 4.0, "answer": f"{qid}-{arm} sdlc-graph.py said"})
with open(os.path.join(out, "runs.jsonl"), "w") as f:
    for x in rows:
        f.write(json.dumps(x) + "\n")
pr = subprocess.run([sys.executable, S, "run", "--questions", q, "--arm", "A=/nonexistent", "--arm", "B=/nonexistent", "--out", out,
                     "--reps", "2", "--budget-usd", "17", "--per-run-usd", "1.5"], capture_output=True, text=True)
check("E05", (3, True), (pr.returncode, "STOP" in pr.stdout), "the budget cap stops before a run that could exceed it ($16 spent, cap $17, run cap $1.5)")
subprocess.run([sys.executable, S, "sheet", "--out", out, "--questions", q], capture_output=True, text=True)
sheet = open(os.path.join(out, "grading-sheet.md")).read()
mp = json.load(open(os.path.join(out, "grading-map.json")))
check("E06", (4, False, False), (len(mp), " A " in sheet.replace("\n", " ") and "arm A" in sheet, "sdlc-graph" in sheet),
      "grading sheet: one entry per run, arm label hidden, tool name redacted")
grades = {gid: ("correct" if v["arm"] == "B" or v["qid"] == "q1" else "partial") for gid, v in mp.items()}
json.dump(grades, open(os.path.join(out, "grades.json"), "w"))
rp = subprocess.run([sys.executable, S, "report", "--out", out, "--questions", q], capture_output=True, text=True)
check("E07", (True, True), ("(saving +20.0%; bar 20%)" in rp.stdout, "VERDICT: KEEP enabled" in rp.stdout),
      "report: median per-question tokens 1000 → 800 is a 20% drop with accuracy not lower → KEEP")
grades = {gid: ("wrong" if v["arm"] == "B" else "correct") for gid, v in mp.items()}
json.dump(grades, open(os.path.join(out, "grades.json"), "w"))
rp = subprocess.run([sys.executable, S, "report", "--out", out, "--questions", q], capture_output=True, text=True)
check("E08", True, "VERDICT: DISABLE by default" in rp.stdout, "report: accuracy drop → DISABLE even when tokens fall")
rp = subprocess.run([sys.executable, S, "report", "--out", out, "--questions", q, "--fixed-overhead-tokens", "1000"], capture_output=True, text=True)
check("E09", True, "A 3,000 → B 2,800" in rp.stdout,
      "report --fixed-overhead-tokens adds the per-step overhead the run did not load (2 steps × 1000)")
print(f"\neval-question-tokens: {total - fails}/{total} passed")
sys.exit(1 if fails else 0)
EOF
