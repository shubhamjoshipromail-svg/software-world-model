"""Aggregate runs/<model>/<app>/<condition>/results.json into a markdown table + figures.

python -m swm.report  ->  reports/phase0_results.md, reports/fig_success.png, reports/fig_cost.png
"""
import glob, json, math, os, statistics
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROLE = {"invoiceninja": "train", "dolibarr": "train", "odoo17": "held-out app", "odoo18": "held-out version"}


def wilson(k, n, z=1.96):
    if n == 0:
        return (0, 0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0, c - h), min(1, c + h))


NOISE_COLS = {"react_settings", "tz", "iap_enrich_auto_done", "narration", "ip", "next_run_date"}
NOISE_TABLE_PREFIX = ("onboarding_", "discuss_channel", "account_payment_register", "llx_const", "digest_",
                      "validate_account_move", "account_move_validate_account_move_rel")


def _real(entries):
    """Drop system bookkeeping that the per-app checkers learned to whitelist after some runs had been recorded."""
    return [c for c in entries if not (c["table"].startswith(NOISE_TABLE_PREFIX) or (c.get("cols") and set(c["cols"]) <= NOISE_COLS))]


def load():
    """Read per-episode summaries (robust to batches that were interrupted before writing results.json)."""
    rows = []
    for f in glob.glob("runs/*/*/*/*/summary.json"):
        model, app, cond = f.split("/")[1:4]
        for r in [json.load(open(f))]:
            r.update(model=model, app=app, cond=cond, error=False)
            r["collateral"], r["irreversible"] = _real(r["collateral"]), _real(r["irreversible"])
            rows.append(r)
    return rows


def agg(rs):
    ok = [r for r in rs if not r["error"]]
    n = len(ok)
    k = sum(r["success"] for r in ok)
    lo, hi = wilson(k, n)
    cost = sum(r.get("cost_usd") or 0 for r in ok)
    kc = sum(r["success"] and not r["collateral"] for r in ok)
    return {"n": n, "errors": len(rs) - n, "success": k / n if n else 0, "ci": (lo, hi), "clean": kc / n if n else 0,
            "collateral": sum(bool(r["collateral"]) for r in ok) / n if n else 0,
            "irreversible": sum(bool(r["irreversible"]) for r in ok) / n if n else 0,
            "false_completion": sum(r["false_completion"] for r in ok) / n if n else 0,
            "unreported": sum(r.get("success_unreported", False) for r in ok) / n if n else 0,
            "median_steps": statistics.median([r["steps"] for r in ok]) if ok else 0,
            "cost_per_success": cost / k if k else float("nan"), "cost": cost,
            "median_wall": statistics.median([r["wall_s"] for r in ok]) if ok else 0}


def main():
    rows = load()
    os.makedirs("reports", exist_ok=True)
    groups = {}
    for r in rows:
        groups.setdefault((r["model"], r["app"], r["cond"]), []).append(r)
    order = sorted(groups, key=lambda g: (g[0], list(ROLE).index(g[1]) if g[1] in ROLE else 9, g[2] != "clean", g[2]))
    lines = ["| Model | App (role) | Condition | n | Success [95% CI] | Clean success | Collateral | Irreversible | False completion | Done but unreported | Median steps | $/success | Infra errors |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    stats = {}
    for g in order:
        a = agg(groups[g]); stats[g] = a
        lines.append(f"| {g[0]} | {g[1]} ({ROLE.get(g[1], '?')}) | {g[2]} | {a['n']} | {a['success']:.0%} [{a['ci'][0]:.0%}–{a['ci'][1]:.0%}] | "
                     f"{a['clean']:.0%} | {a['collateral']:.0%} | {a['irreversible']:.0%} | {a['false_completion']:.0%} | {a['unreported']:.0%} | "
                     f"{a['median_steps']:.0f} | {'$%.4f' % a['cost_per_success'] if a['cost_per_success'] == a['cost_per_success'] else '—'} | {a['errors']} |")
    # per-skill breakdown for clean conditions
    skl = ["", "### Success by skill (clean)", "", "| Model | App | " + " | ".join(sorted({r['skill'] for r in rows if not r['error']})) + " |"]
    skills = sorted({r['skill'] for r in rows if not r['error']})
    skl.append("|---|---|" + "---|" * len(skills))
    for g in order:
        if g[2] != "clean":
            continue
        rs = [r for r in groups[g] if not r["error"]]
        cells = []
        for s in skills:
            x = [r for r in rs if r["skill"] == s]
            cells.append(f"{sum(r['success'] for r in x)}/{len(x)}" if x else "—")
        skl.append(f"| {g[0]} | {g[1]} | " + " | ".join(cells) + " |")
    # Sensitivity: Invoice Ninja episodes ended by the (fixed) narration-fallback bug could not be rerun (app removed for disk).
    sup = [json.load(open(f)) for f in glob.glob("runs/_superseded/narration_bug/luna/invoiceninja/*/*/summary.json")]
    sens = ["", "### Sensitivity: harness bug on Invoice Ninja", "",
            f"{len(sup)} Luna Invoice Ninja episodes were terminated by a harness fallback bug (progress narration wrapped as a final answer); "
            "they could not be rerun after the fix and are **excluded** above. Counting them as failures instead:", ""]
    for cond in sorted({f.split("/")[5] for f in glob.glob("runs/_superseded/narration_bug/luna/invoiceninja/*/*/summary.json")}):
        g = groups.get(("luna", "invoiceninja", cond), [])
        k = sum(r["success"] for r in g if not r["error"]); n = len([r for r in g if not r["error"]])
        extra = sum(1 for f in glob.glob(f"runs/_superseded/narration_bug/luna/invoiceninja/{cond}/*/summary.json"))
        sens.append(f"- {cond}: excluded {k}/{n} = {k/n:.0%} -> as-failed {k}/{n+extra} = {k/(n+extra):.0%}")
    skl += sens
    open("reports/phase0_results.md", "w").write("## Phase 0 results\n\n" + "\n".join(lines) + "\n" + "\n".join(skl) + "\n")

    # Figure 1: success by app/condition per model
    models = sorted({g[0] for g in stats})
    conds = [(a, c) for a in ROLE for c in ["clean", "modal", "flaky_network", "session_expiry"] if any(g[1] == a and g[2] == c for g in stats)]
    fig, ax = plt.subplots(figsize=(max(8, len(conds) * 0.9), 4.2))
    w = 0.8 / max(1, len(models))
    for i, m in enumerate(models):
        xs, ys, es = [], [], []
        for j, (a, c) in enumerate(conds):
            s = stats.get((m, a, c))
            if s:
                xs.append(j + i * w); ys.append(s["success"] * 100)
                es.append([[100 * (s["success"] - s["ci"][0])], [100 * (s["ci"][1] - s["success"])]])
        if xs:
            ax.bar(xs, ys, w, label=m, yerr=[[e[0][0] for e in es], [e[1][0] for e in es]], capsize=2)
    ax.set_xticks([j + w * (len(models) - 1) / 2 for j in range(len(conds))])
    ax.set_xticklabels([f"{a}\n{c}" for a, c in conds], fontsize=7)
    ax.set_ylabel("task success %"); ax.set_ylim(0, 105); ax.legend(fontsize=8); ax.set_title("Success by app and condition (95% Wilson CI)")
    fig.tight_layout(); fig.savefig("reports/fig_success.png", dpi=160)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
