# software-world-model

Do computer-use agents transfer to software they've never seen? And can a latent world model of software dynamics make small agents generalize better?

Research plan, hypotheses, and kill criteria live in the IDEAS repo: `01_research/ai-trends/2026-10-1*_research_native-cua-*`.

## Phase 0 status: complete (2026-10-13)

Read **`reports/phase0_writeup.md`** first. Supporting files: `reports/phase0_results.md` (full table), `reports/failure_taxonomy.md`, `reports/track2.md`, `reports/fig_success.png`.

| Piece | Status |
|---|---|
| 4 self-hosted apps: Invoice Ninja v5, Dolibarr 22, Odoo 17, Odoo 18 (pinned digests, localhost-only, no outbound mail) | done |
| Same synthetic company in each app (60 clients incl. near-duplicates, 250 invoices, ~109 payments), snapshot/restore | done |
| Whole-DB diff verifiers: success, collateral damage, irreversible changes, false completion | done |
| 72 tasks × 4 apps, 9 skills (incl. a 3-step composite) | done |
| Perturbations: blocking modal, flaky network, session expiry | done |
| Baselines: GPT-6 Luna (491 episodes, $5.13) and UI-TARS-1.5-7B on a Colab A100 (180 episodes) | done |
| Label-free exploration data: 4 apps × 30 episodes × 40 steps = 4,800 (s, a, s') transitions | done |
| Track 2 probe: latent dynamics model, within-app / cross-version / cross-app transfer | done (K1 fails cross-app; works within app and across versions) |

Note: Akaunting was dropped. It blocks invoice creation unless registered with the vendor's API (see write-up §6).

## Run

```bash
cd envs/<app> && docker compose -p swm-<app> up -d       # DBs run on tmpfs: restore() reloads them from snapshots/
.venv/bin/python -m swm.seed_invoiceninja                  # once, then:
.venv/bin/python -c "from swm.invoiceninja import snapshot; snapshot('seed_normal')"
scripts/set_key.sh                                         # OpenAI key, hidden input, stored in .env (gitignored)
.venv/bin/python -m swm.run_batch --per-skill 1 --tag smoke
```

## Metrics per episode

success · collateral damage (any DB change outside what the task requires) · irreversible changes · false completion (claims done, verifier says no) · gave up / timeout · steps · tokens · $ · wall time.
