"""Pack every per-episode summary under runs/ into one small JSONL file that can be committed.

python -m swm.export_results [--out results/phase0_episodes.jsonl]

Each line is one episode's summary.json plus where it came from (model, app, cond, superseded). Screenshots and
step logs stay in runs/ (hundreds of MB); this file is enough to rebuild every table with
`python -m swm.report --from results/phase0_episodes.jsonl`.
"""
import argparse, glob, json, os


def collect():
    rows = []
    for f in sorted(glob.glob("runs/*/*/*/*/summary.json")):
        model, app, cond = f.split("/")[1:4]
        rows.append({**json.load(open(f)), "model": model, "app": app, "cond": cond, "superseded": None})
    for f in sorted(glob.glob("runs/_superseded/*/*/*/*/*/summary.json")):
        reason, model, app, cond = f.split("/")[2:6]
        rows.append({**json.load(open(f)), "model": model, "app": app, "cond": cond, "superseded": reason})
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/phase0_episodes.jsonl")
    a = ap.parse_args()
    rows = collect()
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w") as f:
        for r in rows:
            f.write(json.dumps(r, default=str, sort_keys=True) + "\n")
    print(f"wrote {len(rows)} episodes to {a.out}")
