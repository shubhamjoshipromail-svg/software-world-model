"""Track 2 seed experiment: does a latent dynamics model of software, trained on label-free exploration of the
TRAIN apps, predict state transitions in a HELD-OUT app better than trivial baselines? (kill criteria K1, K2)

State z = [DINOv2-small CLS of the screenshot ; MiniLM mean-embedding of the accessibility tree text], frozen.
Action a = [MiniLM embedding of "type role name text" ; one-hot type].
Predictor f(z_t, a_t) -> z_{t+1} - z_t (JEPA-style: predict in embedding space, not pixels/text).

Eval on transitions where the state actually changed, retrieval of the true next state among 10 candidates:
  easy  = negatives are random next-states from the same app
  hard  = negatives are next-states on the same page type (same URL path) -> must preserve record-specific content (K2 proxy)
Baselines: identity (z_{t+1} = z_t), action-blind MLP f(z_t), mean delta.
python -m swm.track2 embed   # cache embeddings
python -m swm.track2 train   # train + eval, writes reports/track2.json and reports/track2.md
"""
import glob, gzip, json, os, random, re, sys
import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA = os.path.join(ROOT, "data", "explore")
CACHE = os.path.join(ROOT, "data", "track2_cache")
TRAIN_APPS, HELDOUT_APPS = ["invoiceninja", "dolibarr"], ["odoo17", "odoo18"]
TYPES = ["click", "fill", "back", "scroll"]


def episodes(app):
    for d in sorted(glob.glob(f"{DATA}/{app}/ep*")):
        if os.path.exists(f"{d}/transitions.jsonl"):
            yield d, [json.loads(l) for l in open(f"{d}/transitions.jsonl")]


def embed(only=None):
    import torch
    from PIL import Image
    from transformers import AutoImageProcessor, AutoModel
    from sentence_transformers import SentenceTransformer
    dev = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
    ip = AutoImageProcessor.from_pretrained("facebook/dinov2-small")
    vm = AutoModel.from_pretrained("facebook/dinov2-small").to(dev).eval()
    tm = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device=dev)
    os.makedirs(CACHE, exist_ok=True)

    def ax_text(path):
        t = gzip.open(path, "rt").read()
        t = re.sub(r"\[\d+\]", "", t)  # drop element ids
        words = t.split()
        chunks = [" ".join(words[i:i + 180]) for i in range(0, min(len(words), 180 * 12), 180)] or [""]
        e = tm.encode(chunks, normalize_embeddings=True)
        v = e.mean(0)
        return v / (np.linalg.norm(v) + 1e-8)

    for app in (only or TRAIN_APPS + HELDOUT_APPS):
        out = f"{CACHE}/{app}.npz"
        if os.path.exists(out):
            continue
        Z, A, AT, ep_ids, t_ids, urls, nurls = [], [], [], [], [], [], []
        Znext = []
        for d, trans in episodes(app):
            n = len(trans)
            imgs = [Image.open(f"{d}/step{t:02d}.jpg").convert("RGB") for t in range(n + 1)]
            with torch.no_grad():
                feats = []
                for i in range(0, len(imgs), 16):
                    x = ip(images=imgs[i:i + 16], return_tensors="pt").to(dev)
                    feats.append(vm(**x).last_hidden_state[:, 0].float().cpu().numpy())
                feats = np.concatenate(feats)
            feats /= np.linalg.norm(feats, axis=1, keepdims=True) + 1e-8
            axs = np.stack([ax_text(f"{d}/ax{t:02d}.txt.gz") for t in range(n + 1)])
            states = np.concatenate([feats, axs], 1)
            descs = [f"{tr['desc'].get('type')} {tr['desc'].get('role', '')} {tr['desc'].get('name', '')} {tr['desc'].get('text', '')}" for tr in trans]
            aemb = tm.encode(descs, normalize_embeddings=True)
            for t, tr in enumerate(trans):
                Z.append(states[t]); Znext.append(states[t + 1]); A.append(aemb[t])
                AT.append(TYPES.index(tr["desc"].get("type", "click")))
                ep_ids.append(d); t_ids.append(t)
                urls.append(re.sub(r"\d+", "#", tr["url"].split("?")[0])); nurls.append(re.sub(r"\d+", "#", tr["next_url"].split("?")[0]))
            print(app, d, flush=True)
        np.savez_compressed(out, Z=np.array(Z), Zn=np.array(Znext), A=np.array(A), AT=np.array(AT), ep=np.array(ep_ids),
                            t=np.array(t_ids), url=np.array(urls), nurl=np.array(nurls))


def train():
    """Configs x seeds. Each config: train on some (app, episode<24) data; test on held-out episodes of the same apps,
    other versions, and other apps. Retrieval top-1 among 10 candidates on transitions where the state changed."""
    import torch, torch.nn as nn
    CONFIGS = {
        "A: train InvoiceNinja+Dolibarr": {"train": ["invoiceninja", "dolibarr"],
                                            "tests": {"same apps, unseen episodes": ["invoiceninja", "dolibarr"],
                                                      "held-out app (Odoo 17)": ["odoo17"], "held-out app (Odoo 18)": ["odoo18"]}},
        "B: train Odoo 17": {"train": ["odoo17"],
                             "tests": {"same app, unseen episodes": ["odoo17"], "next version (Odoo 18)": ["odoo18"],
                                       "other apps (IN+Dolibarr)": ["invoiceninja", "dolibarr"]}},
    }
    data = {a: dict(np.load(f"{CACHE}/{a}.npz")) for a in TRAIN_APPS + HELDOUT_APPS if os.path.exists(f"{CACHE}/{a}.npz")}
    epnum = lambda d: np.array([int(e.rsplit("ep", 1)[1]) for e in d["ep"]])

    def subset(apps, which):
        parts = []
        for a in apps:
            d = data[a]; m = epnum(d) < 24 if which == "train" else (epnum(d) >= 24 if which == "test_same" else np.ones(len(d["Z"]), bool))
            parts.append({k: v[m] for k, v in d.items()})
        return {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}

    def feats(d):
        oh = np.eye(len(TYPES))[d["AT"]]
        return (torch.tensor(np.concatenate([d["Z"], d["A"], oh], 1), dtype=torch.float32),
                torch.tensor(d["Z"], dtype=torch.float32), torch.tensor(d["Zn"] - d["Z"], dtype=torch.float32))

    def fit(inp, Y, D, seed):
        torch.manual_seed(seed); np.random.seed(seed)
        m = nn.Sequential(nn.Linear(inp.shape[1], 1024), nn.GELU(), nn.Linear(1024, 1024), nn.GELU(), nn.Linear(1024, D))
        opt = torch.optim.AdamW(m.parameters(), lr=1e-3, weight_decay=1e-4)
        idx = np.arange(len(inp))
        for _ in range(60):
            np.random.shuffle(idx)
            for b in range(0, len(idx), 256):
                j = idx[b:b + 256]
                loss = ((m(inp[j]) - Y[j]) ** 2).sum(1).mean()
                opt.zero_grad(); loss.backward(); opt.step()
        return m.eval()

    def evaluate(d, models, mean_delta, seed):
        Xe, Ze, Ye = feats(d); Zn = Ze + Ye
        changed = (torch.nn.functional.cosine_similarity(Ze, Zn) < 0.995).numpy()
        with torch.no_grad():
            preds = {"identity": Ze, "mean delta": Ze + mean_delta, "action-blind": Ze + models["blind"](Ze),
                     "action-conditioned": Ze + models["cond"](Xe)}
        rng = np.random.default_rng(seed); ids = np.where(changed)[0]; out = {}
        for mode in ["easy", "hard"]:
            hits = {k: [] for k in preds}
            for i in ids:
                pool = np.setdiff1d(ids, [i]) if mode == "easy" else np.array([j for j in ids if j != i and d["nurl"][j] == d["nurl"][i]])
                if len(pool) < 9:
                    continue
                cands = torch.cat([Zn[i:i + 1], Zn[rng.choice(pool, 9, replace=False)]])
                for k, p in preds.items():
                    hits[k].append(int(((cands - p[i:i + 1]) ** 2).sum(1).argmin() == 0))
            out[mode] = {k: (float(np.mean(v)) if v else None) for k, v in hits.items()}
            out[mode]["n"] = len(hits["identity"])
        return out

    results = {}
    for cname, cfg in CONFIGS.items():
        tr = subset(cfg["train"], "train"); X, Zt, Y = feats(tr)
        for seed in range(3):
            models = {"cond": fit(X, Y, Zt.shape[1], seed), "blind": fit(Zt, Y, Zt.shape[1], seed)}
            for tname, apps in cfg["tests"].items():
                d = subset(apps, "test_same" if set(apps) == set(cfg["train"]) else "all")
                r = evaluate(d, models, Y.mean(0), seed)
                results.setdefault(cname, {}).setdefault(tname, []).append(r)
            print(cname, "seed", seed, "done", flush=True)
    os.makedirs(f"{ROOT}/reports", exist_ok=True)
    json.dump(results, open(f"{ROOT}/reports/track2.json", "w"), indent=1)
    K = ["identity", "mean delta", "action-blind", "action-conditioned"]
    lines = ["## Track 2 seed: does a latent dynamics model of software transfer?", "",
             "Top-1 retrieval of the true next state among 10 candidates (chance = 10%), on transitions where the screen changed. "
             "Mean over 3 seeds (± std across seeds). *Hard* = all candidates are on the same page type, so the prediction must "
             "preserve record-specific content (K2 proxy). K1 margin = action-conditioned − identity.", "",
             "| Trained on | Tested on | Mode | n | identity | mean delta | action-blind | action-conditioned | K1 margin |",
             "|---|---|---|---|---|---|---|---|---|"]
    for cname, tests in results.items():
        for tname, runs in tests.items():
            for mode in ["easy", "hard"]:
                vals = {k: [r[mode][k] for r in runs if r[mode][k] is not None] for k in K}
                f = lambda k: f"{100*np.mean(vals[k]):.0f}% ± {100*np.std(vals[k]):.0f}" if vals[k] else "—"
                margin = 100 * (np.mean(vals["action-conditioned"]) - np.mean(vals["identity"])) if vals["identity"] else float("nan")
                lines.append(f"| {cname} | {tname} | {mode} | {runs[0][mode]['n']} | " + " | ".join(f(k) for k in K) + f" | {margin:+.0f} pts |")
    open(f"{ROOT}/reports/track2.md", "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    if sys.argv[1] == "embed":
        embed(sys.argv[2:] or None)
    else:
        train()
