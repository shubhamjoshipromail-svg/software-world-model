"""Label-free exploration: a novelty-seeking random agent that records (s, a, s') transitions. No tasks, no rewards.

python -m swm.explore --app invoiceninja --episodes 40 --steps 50
Output: data/explore/<app>/ep<k>/stepNN.jpg (+ axNN.txt.gz) and transitions.jsonl
"""
import argparse, gzip, json, os, random, hashlib, io
from PIL import Image
from browsergym.core.env import BrowserEnv
from browsergym.utils.obs import flatten_axtree_to_str
from swm import apps
from swm.harness import AppTask, EXEC_ACTIONS as ACTIONS
from swm.tasks_invoiceninja import Task

AVOID = ("log out", "logout", "sign out", "delete account", "purge", "cancel account")
WORDS = ["Acme", "test", "100", "2026-10-05", "Q3 review", "42.50", "north", "invoice", "PO-12345", "x"]


def small_jpeg(arr, path):
    im = Image.fromarray(arr).convert("RGB").resize((960, 600))
    im.save(path, format="JPEG", quality=60)


def candidates(obs):
    props = obs["extra_element_properties"]
    out = []
    for node in obs["axtree_object"]["nodes"]:
        bid = node.get("browsergym_id")
        if not bid or bid not in props:
            continue
        p = props[bid]
        if not p.get("clickable") or (p.get("visibility") or 0) < 0.5:
            continue
        role = (node.get("role") or {}).get("value", "")
        name = (node.get("name") or {}).get("value", "") or ""
        if any(a in name.lower() for a in AVOID):
            continue
        out.append((bid, role, name))
    return out


def run(app_name, episodes, steps, seed):
    app = apps.get(app_name)
    rng = random.Random(seed)
    root = f"data/explore/{app_name}"
    os.makedirs(root, exist_ok=True)
    seen = {}
    for ep in range(episodes):
        d = f"{root}/ep{ep:03d}"
        if os.path.exists(f"{d}/transitions.jsonl"):
            continue
        import shutil, time
        while shutil.disk_usage("/").free < 0.6e9:
            print("disk guard: pausing", flush=True); time.sleep(60)
        os.makedirs(d, exist_ok=True)
        marker = os.path.join("runs", f".clean_{app.NAME}_{os.environ.get('SWM_IN_INST', '1')}")
        if os.path.exists(marker):
            os.remove(marker)  # exploration dirties the DB; force the next agent episode to restore
        app.restore(app.DEFAULT_SNAPSHOT)
        task = Task("explore", app_name, "explore", "Explore the app.", {})
        env = BrowserEnv(task_entrypoint=AppTask, task_kwargs={"task": task, "app": app}, headless=True,
                         action_mapping=ACTIONS.to_python_code)
        obs, _ = env.reset(seed=ep)

        def _guard(route):  # sandbox: never navigate away from the local app
            req = route.request
            host = req.url.split("/")[2].split(":")[0] if "://" in req.url else ""
            if req.is_navigation_request() and host not in ("localhost", "127.0.0.1"):
                return route.abort()
            return route.continue_()
        env.context.route("**/*", _guard)
        trans = []
        for t in range(steps):
            ax = flatten_axtree_to_str(obs["axtree_object"], extra_properties=obs["extra_element_properties"],
                                       with_clickable=True, filter_visible_only=True)
            small_jpeg(obs["screenshot"], f"{d}/step{t:02d}.jpg")
            with gzip.open(f"{d}/ax{t:02d}.txt.gz", "wt") as f:
                f.write(ax)
            cands = candidates(obs)
            r = rng.random()
            if not cands or r < 0.06:
                action, desc = "go_back()", {"type": "back"}
            elif r < 0.10:
                action, desc = "scroll(0, 400)", {"type": "scroll"}
            else:
                # novelty: prefer elements (by url+role+name) we have clicked least
                key = lambda c: (obs["url"].split("?")[0], c[1], c[2])
                w = [1.0 / (1 + seen.get(key(c), 0)) ** 2 for c in cands]
                bid, role, name = rng.choices(cands, weights=w)[0]
                seen[key((bid, role, name))] = seen.get(key((bid, role, name)), 0) + 1
                if role in ("textbox", "searchbox", "spinbutton", "combobox") and rng.random() < 0.7:
                    txt = rng.choice(WORDS)
                    action, desc = f"fill({bid!r}, {txt!r})", {"type": "fill", "role": role, "name": name, "text": txt}
                else:
                    action, desc = f"click({bid!r})", {"type": "click", "role": role, "name": name}
            url = obs["url"]
            try:
                obs, *_ = env.step(action)
                err = obs.get("last_action_error") or None
            except Exception as e:
                err = repr(e)[:200]
            trans.append({"t": t, "url": url, "action": action, "desc": desc, "next_url": obs["url"], "error": err})
        small_jpeg(obs["screenshot"], f"{d}/step{steps:02d}.jpg")
        with gzip.open(f"{d}/ax{steps:02d}.txt.gz", "wt") as f:
            f.write(flatten_axtree_to_str(obs["axtree_object"], extra_properties=obs["extra_element_properties"],
                                          with_clickable=True, filter_visible_only=True))
        env.close()
        with open(f"{d}/transitions.jsonl", "w") as f:
            for r_ in trans:
                f.write(json.dumps(r_) + "\n")
        print(f"{app_name} ep{ep} done, {sum(1 for x in trans if x['error'])} errors", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", default="invoiceninja")
    ap.add_argument("--episodes", type=int, default=40)
    ap.add_argument("--steps", type=int, default=50)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    run(a.app, a.episodes, a.steps, a.seed)
