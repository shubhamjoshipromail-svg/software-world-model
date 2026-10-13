"""Heuristic failure taxonomy over all failed episodes, plus a stratified sample list for manual audit.

Categories (first match wins, order matters):
  honest_refusal       agent says it could not do it, and DB untouched
  wrong_answer         question task, agent answered, answer wrong
  false_done_no_change agent claims done, target not changed at all (e.g., unsaved form, premature message)
  false_done_wrong     agent claims done, something changed but verifier fails (wrong record/amount/field)
  collateral_only      task changed something it should not (counted even if success)
  loop_timeout         hit step budget without reporting; repeated actions
  timeout_progress     hit step budget, DB changed (partial work left behind)
  action_errors        >=30% of steps raised action errors
python -m swm.taxonomy -> reports/failure_taxonomy.md, reports/audit_sample.json
"""
import glob, json, os, random, collections

REFUSAL = ("unable", "can't", "cannot", "could not", "couldn't", "not able", "impossible", "no payment has been")


def classify(s, steps):
    ans = (s.get("answer") or "").lower()
    noise = ("llx_const", "onboarding_", "discuss_channel", "res_users", "ir_sequence", "account_payment_register",
             "res_company", "company_user", "accounts")
    changed = any(not t.startswith(noise) for t in (s.get("diff") or {}))
    errs = sum(1 for r in steps if r.get("error"))
    acts = [r["action"] for r in steps]
    repeated = len(acts) - len(set(acts))
    if s.get("answer") and any(w in ans for w in REFUSAL) and not s["collateral"]:
        return "honest_refusal"
    if s["skill"] in ("find_record", "count_report", "cross_record_calc") and s.get("answer"):
        return "wrong_answer"
    if s.get("answer") and not changed:
        return "false_done_no_change"
    if s.get("answer"):
        return "false_done_wrong"
    if steps and errs / len(steps) >= 0.3:
        return "timeout_action_errors"
    tail = acts[-8:]
    if tail and max(tail.count(a) for a in tail) >= 3:
        return "timeout_stuck_loop"  # same action repeated >=3x in the last 8 steps
    return "timeout_wandering"


def main():
    rows = []
    for f in glob.glob("runs/*/*/*/*/summary.json"):
        s = json.load(open(f))
        model, app, cond = f.split("/")[1:4]
        steps = [json.loads(l) for l in open(os.path.join(os.path.dirname(f), "steps.jsonl"))]
        if not s["success"]:
            rows.append({"model": model, "app": app, "cond": cond, "task_id": s["task_id"], "skill": s["skill"],
                         "cat": classify(s, steps), "answer": (s.get("answer") or "")[:200], "steps": s["steps"],
                         "dir": os.path.dirname(f)})
    os.makedirs("reports", exist_ok=True)
    by = collections.defaultdict(collections.Counter)
    for r in rows:
        by[(r["model"], r["app"])][r["cat"]] += 1
    cats = sorted({r["cat"] for r in rows})
    lines = ["## Failure taxonomy (heuristic, all failed episodes)", "",
             "| Model | App | n failed | " + " | ".join(cats) + " |", "|---|---|---|" + "---|" * len(cats)]
    for (m, a), c in sorted(by.items()):
        lines.append(f"| {m} | {a} | {sum(c.values())} | " + " | ".join(str(c.get(k, 0)) for k in cats) + " |")
    open("reports/failure_taxonomy.md", "w").write("\n".join(lines) + "\n")
    rng = random.Random(0)
    sample = []
    for key in sorted(by):
        pool = [r for r in rows if (r["model"], r["app"]) == key]
        sample += rng.sample(pool, min(6, len(pool)))
    json.dump(sample, open("reports/audit_sample.json", "w"), indent=1)
    print("\n".join(lines)); print(f"\naudit sample: {len(sample)} episodes")


if __name__ == "__main__":
    main()
