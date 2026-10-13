"""Run a batch of tasks and write results.json.

python -m swm.run_batch --app invoiceninja --per-skill 8 --model gpt-6-luna --perturb clean --tag luna_in_clean
"""
import argparse, json, collections, os
from swm import apps
from swm.harness import run_episode
from swm.perturb import ALL as PERTURB

ap = argparse.ArgumentParser()
ap.add_argument("--app", default="invoiceninja")
ap.add_argument("--per-skill", type=int, default=1)
ap.add_argument("--offset", type=int, default=0, help="skip first N instances per skill")
ap.add_argument("--model", default="gpt-6-luna")
ap.add_argument("--max-steps", type=int, default=30)
ap.add_argument("--perturb", default="clean", choices=list(PERTURB))
ap.add_argument("--snapshot", default=None)
ap.add_argument("--tag", required=True)
ap.add_argument("--skip-done", action="store_true")
args = ap.parse_args()

app = apps.get(args.app)
app.restore(args.snapshot or app.DEFAULT_SNAPSHOT)
tasks, seen = [], collections.Counter()
for t in app.generate():
    seen[t.skill] += 1
    if args.offset < seen[t.skill] <= args.offset + args.per_skill:
        tasks.append(t)

out_root = f"runs/{args.tag}"
os.makedirs(out_root, exist_ok=True)
rows = []
import shutil, time
for n, t in enumerate(tasks):
    while shutil.disk_usage("/").free < 0.25e9:  # disk guard: never let MySQL/Postgres run out of space
        print("disk guard: <1.5GB free, pausing 60s", flush=True); time.sleep(60)
    out = f"{out_root}/{t.task_id}"
    if args.skip_done and os.path.exists(f"{out}/summary.json"):
        rows.append(json.load(open(f"{out}/summary.json"))); continue
    try:
        s = run_episode(t, model=args.model, max_steps=args.max_steps, out_dir=out, snapshot=args.snapshot,
                        perturb=PERTURB[args.perturb](seed=n) if args.perturb != "clean" else None)
    except Exception as e:
        s = {"task_id": t.task_id, "skill": t.skill, "error": repr(e)[:300]}
    rows.append(s)
    print(json.dumps({k: s.get(k) for k in ["task_id", "success", "steps", "false_completion", "success_unreported",
                                            "cost_usd", "wall_s", "error"]}, default=str),
          "collateral:", [(c["table"], c["op"]) for c in s.get("collateral", [])], flush=True)

ok = [r for r in rows if "error" not in r]
print(f"\nSUMMARY {args.tag}: success {sum(r['success'] for r in ok)}/{len(ok)} | "
      f"collateral {sum(bool(r['collateral']) for r in ok)} | false-completion {sum(r['false_completion'] for r in ok)} | "
      f"cost ${sum(r['cost_usd'] for r in ok):.3f} | errors {len(rows) - len(ok)}")
json.dump(rows, open(f"{out_root}/results.json", "w"), indent=1, default=str)
