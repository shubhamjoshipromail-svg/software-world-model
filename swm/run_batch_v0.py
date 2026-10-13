"""Run a batch of tasks and print a results table. Usage: python -m swm.run_batch --per-skill 1 --model gpt-6-luna"""
import argparse, json, collections
from swm.invoiceninja import restore
from swm.tasks_invoiceninja import generate
from swm.harness import run_episode

ap = argparse.ArgumentParser()
ap.add_argument("--per-skill", type=int, default=1)
ap.add_argument("--model", default="gpt-6-luna")
ap.add_argument("--max-steps", type=int, default=30)
ap.add_argument("--tag", default="smoke")
args = ap.parse_args()

restore("seed_normal")
tasks, seen = [], collections.Counter()
for t in generate():
    if seen[t.skill] < args.per_skill:
        tasks.append(t); seen[t.skill] += 1

rows = []
for t in tasks:
    try:
        s = run_episode(t, model=args.model, max_steps=args.max_steps,
                        out_dir=f"runs/{args.tag}/{args.model}/{t.task_id}")
    except Exception as e:
        s = {"task_id": t.task_id, "skill": t.skill, "error": repr(e)[:200]}
    rows.append(s)
    print(json.dumps({k: s.get(k) for k in ["task_id", "success", "steps", "false_completion", "gave_up_or_timeout",
                                            "cost_usd", "wall_s", "error"]}, default=str), flush=True)
    print("   collateral:", [(c["table"], c["op"]) for c in s.get("collateral", [])], flush=True)

ok = [r for r in rows if "error" not in r]
n = len(ok) or 1
print(f"\nSUMMARY {args.model}: success {sum(r['success'] for r in ok)}/{len(ok)} | "
      f"collateral {sum(bool(r['collateral']) for r in ok)}/{len(ok)} | "
      f"false-completion {sum(r['false_completion'] for r in ok)}/{len(ok)} | "
      f"cost ${sum(r['cost_usd'] for r in ok):.3f} | errors {len(rows) - len(ok)}")
json.dump(rows, open(f"runs/{args.tag}/{args.model}/results.json", "w"), indent=1, default=str)
