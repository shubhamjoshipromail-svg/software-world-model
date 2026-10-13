# Do computer-use agents transfer to business software they've never seen?
## Phase 0 report: benchmark, baselines, and a first world-model probe

*Status: internal draft, **not published, no outreach done**. Every number below is regenerated from `runs/` and `data/` by `python -m swm.report`, `python -m swm.taxonomy`, and `python -m swm.track2 train`. Run date: 2026-10-13.*

### TL;DR
1. **Version upgrades break things quietly.** On Odoo 17 → 18, Luna's task success holds (78% → 76%), but collateral damage rises from 15% to 21% and irreversible changes from 6% to 10%. In one recurring pattern, Odoo 18 locks fields on posted invoices. To change a reference, the agent clicks "Reset to Draft", which **silently un-reconciles the customer's payment**. It then re-posts and reports success.
2. **Success rates hide damage.** "Clean success" (task done *and* nothing else touched) is up to 12 points lower than raw success on Odoo.
3. **Composition collapses everywhere.** Single-step skills reach up to 100%. The 3-step composite (find the oldest unpaid invoice → pay it → report the new balance) succeeded **0 of 54** times across 4 apps and 2 agents. On Odoo, Luna paid *something* in 15 of 16 runs, but only 6 of those were clean.
4. **App identity matters more than "seen vs unseen" for zero-shot agents.** Luna scores 87% on Invoice Ninja, 49% on Dolibarr and 76–78% on Odoo. UI-TARS-1.5-7B scores 8–22% everywhere, and its dominant failure is repeating the same click (stuck loops).
5. **Track 2 (latent world model).** A small dynamics model trained on **label-free random exploration** predicts state transitions within the same app (+20 to +37 points over "nothing changes") and **transfers across a version upgrade** (Odoo 17 → 18: +7 to +8). It does **not** transfer across apps (about 0). Kill criterion K1 fails for held-out apps at this scale (1–2 training apps, 24 exploration episodes each). The obvious next variable is app diversity.

Scale: 491 Luna episodes ($5.13 API), 180 UI-TARS episodes (about 33 Colab compute units), 4,800 exploration transitions, 4 apps, 9 skills, 3 perturbation types.

### 1. Setup (all self-hosted, resettable, verified at the database level)
| Role in later phases | App | Notes |
|---|---|---|
| Train-side app 1 | Invoice Ninja v5 (React UI) | MySQL. Mail goes to a log |
| Train-side app 2 | Dolibarr 22 ERP | MySQL. Server-rendered classic UI. Replaced Akaunting (§6) |
| Held-out app | Odoo 17 Invoicing | Postgres. Very different UI paradigm |
| Held-out version | Odoo 18 Invoicing | Same app, next major version |

- **Data:** one synthetic company per app from one generator: 60 clients (about 15% near-duplicate names such as "Dunder Health Ltd" vs "Dunder Health Limited"), 250 invoices (draft/sent/partial/paid), about 109 payments.
- **Tasks:** 9 skills × 8 instances = 72 per app: find, count, cross-record total, create client, create invoice, edit field, bulk status change, record payment, and the composite.
- **Verification:** every episode starts from an identical DB snapshot. A **whole-database diff** then decides:
  - success;
  - **collateral damage**: changes outside what the task legitimately requires, including that app's derived bookkeeping. App-generated system noise (sessions, digests, wizards, IP logs) is whitelisted and listed in code;
  - **irreversible changes**: deletions, reconciliation changes, state transitions on non-target records;
  - **false completion**: the agent says "done" but the DB says no.
- **Perturbations (seeded, Invoice Ninja; modal also on Dolibarr and Odoo 17):** a blocking "What's new" modal; a flaky network (1–4 s latency, 8% HTTP 500 on API calls); session expiry mid-task.
- **Agents (same harness, same 30-step budget):**
  - **GPT-6 Luna (API):** accessibility tree + screenshot, element-id actions.
  - **UI-TARS-1.5-7B (open weights, vLLM on a Colab A100):** screenshot only, native coordinate action space through an adapter.
- **Sandbox:** agents can't navigate off localhost, and no real email can be sent.

### 2. Results
**Important framing:** neither agent was trained on any of these apps. "Train/held-out" names the role each app plays in Phases 1–2 (BC/RL on the train-side apps). For zero-shot baselines, it measures app difficulty, not transfer.

| Model | App | Condition | n | Success [95% CI] | Clean success | Collateral | Irreversible | False completion | Median steps | $/success |
|---|---|---|---|---|---|---|---|---|---|---|
| Luna | Invoice Ninja | clean | 67 | 87% [76–93] | 87% | 0% | 0% | 6% | 8 | $0.009 |
| Luna | Invoice Ninja | flaky network | 34 | 76% [60–88] | 76% | 0% | 0% | 15% | 10 | $0.012 |
| Luna | Invoice Ninja | modal | 35 | 83% [67–92] | 83% | 0% | 0% | 9% | 9 | $0.010 |
| Luna | Invoice Ninja | session expiry | 32 | 84% [68–93] | 84% | 3% | 3% | 6% | 15 | $0.012 |
| Luna | Dolibarr | clean | 72 | 49% [37–60] | 44% | 6% | 0% | 18% | 20 | $0.032 |
| Luna | Dolibarr | modal | 35 | 51% [36–67] | 40% | 14% | 0% | 20% | 19 | $0.031 |
| Luna | Odoo 17 | clean | 72 | 78% [67–86] | 68% | 15% | 6% | 6% | 9 | $0.012 |
| Luna | Odoo 17 | modal | 36 | 75% [59–86] | 64% | 19% | 8% | 8% | 12 | $0.015 |
| Luna | Odoo 18 | clean | 72 | 76% [65–85] | 64% | 21% | 10% | 6% | 10 | $0.012 |
| UI-TARS-7B | Invoice Ninja | clean | 72 | 19% [12–30] | 18% | 14% | 3% | 26% | 30 | GPU |
| UI-TARS-7B | Dolibarr | clean | 36 | 8% [3–22] | 8% | 0% | 0% | 22% | 30 | GPU |
| UI-TARS-7B | Odoo 17 | clean | 36 | 17% [8–32] | 14% | 19% | 11% | 17% | 30 | GPU |
| UI-TARS-7B | Odoo 18 | clean | 36 | 22% [12–38] | 19% | 31% | 8% | 22% | 30 | GPU |

Full table with infrastructure errors: `reports/phase0_results.md`. Figure: `reports/fig_success.png`.

**Success by skill (clean):**

| Model | App | find | count | total | new client | new invoice | edit | bulk | payment | composite |
|---|---|---|---|---|---|---|---|---|---|---|
| Luna | Invoice Ninja | 8/8 | 5/7 | 7/7 | 8/8 | 8/8 | 7/8 | 7/7 | 8/8 | **0/6** |
| Luna | Dolibarr | 2/8 | 7/8 | 5/8 | 6/8 | 0/8 | 7/8 | 7/8 | 1/8 | **0/8** |
| Luna | Odoo 17 | 8/8 | 8/8 | 1/8 | 8/8 | 8/8 | 8/8 | 8/8 | 7/8 | **0/8** |
| Luna | Odoo 18 | 8/8 | 8/8 | 2/8 | 7/8 | 7/8 | 7/8 | 8/8 | 8/8 | **0/8** |
| UI-TARS | Invoice Ninja | 0/8 | 0/8 | 6/8 | 0/8 | 0/8 | 3/8 | 4/8 | 1/8 | **0/8** |
| UI-TARS | Dolibarr | 3/4 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 | **0/4** |
| UI-TARS | Odoo 17 | 3/4 | 1/4 | 0/4 | 0/4 | 0/4 | 1/4 | 1/4 | 0/4 | **0/4** |
| UI-TARS | Odoo 18 | 3/4 | 0/4 | 0/4 | 1/4 | 2/4 | 2/4 | 0/4 | 0/4 | **0/4** |

**Composite partial credit (clean):** Luna on Odoo 17/18 recorded *a* payment in 7/8 and 8/8 runs. Only 3/8 and 3/8 were free of collateral, meaning the right invoice was paid without touching others. Most runs then hit the step budget before reporting the balance. On Invoice Ninja and Dolibarr, Luna rarely got as far as paying (1/6, 1/8). UI-TARS paid something on Odoo (4/4, 3/4) but cleanly only 1/4 each.

**Perturbations (Luna, Invoice Ninja):**
- A flaky network cost 11 points and **more than doubled false completions** (6% → 15%): the agent reports success on actions whose API call failed.
- Session expiry barely moved success, but **nearly doubled median steps** (8 → 15).
- The modal had little effect on Luna.

On Dolibarr, the modal kept raw success flat (49 → 51%) but **cut clean success (44 → 40%) and raised collateral (6 → 14%)**. Episodes that pushed through the popup left more damage behind.

### 3. What failed, and how (heuristic taxonomy over all failed episodes)
| Model | App | Failed | False "done", nothing changed | False "done", wrong change | Honest refusal | Stuck loop | Wandering timeout | Wrong answer |
|---|---|---|---|---|---|---|---|---|
| Luna | Invoice Ninja | 28 | 8 | 0 | 1 | 2 | 12 | 5 |
| Luna | Dolibarr | 54 | 6 | 0 | 0 | 20 | 13 | 14 |
| Luna | Odoo 17 | 25 | 0 | 4 | 0 | 5 | 13 | 3 |
| Luna | Odoo 18 | 17 | 0 | 4 | 0 | 7 | 6 | 0 |
| UI-TARS | Invoice Ninja | 58 | 1 | 8 | 0 | 32 | 7 | 10 |
| UI-TARS | Dolibarr | 33 | 1 | 0 | 0 | 18 | 7 | 7 |
| UI-TARS | Odoo 17 | 30 | 0 | 2 | 0 | 19 | 5 | 4 |
| UI-TARS | Odoo 18 | 28 | 0 | 4 | 0 | 17 | 3 | 4 |

(One Dolibarr failure was classified as action errors.)

**Manual audit notes** (stratified sample of 48 failed episodes in `reports/audit_sample.json`; I inspected the final actions and answers of 14 and read 4 in full with screenshots):
- **UI-TARS "stuck loops" are real.** It repeats the identical click 4+ times when the page doesn't visibly change: the tab is already active, or the content is below the fold. The clicks are correctly grounded (verified by overlaying click coordinates on screenshots). The failure is in not scrolling or re-planning.
- **Luna's Dolibarr loops center on one UI quirk.** Dolibarr's date widget only commits on blur, so Luna re-fills the date and re-submits.
- **Luna "false done, nothing changed" on Invoice Ninja:** the agent claims success right after opening the right record, before saving.
- **Odoo 18 "reset to draft" damage** is the most consequential pattern (TL;DR #1). It appears as successful task + irreversible collateral, which raw success rates never show.

### 4. Track 2 seed: does a latent model of software dynamics transfer?
Setup:
- **Inputs:** frozen DINOv2-small screenshot embedding ⊕ MiniLM embedding of the accessibility tree.
- **Model:** an MLP predicts the next-state embedding from (state, action). JEPA-style: embedding space, no pixels or text.
- **Training data:** label-free random-novelty exploration, 30 episodes × 40 steps per app. Training uses episodes 0–23.
- **Metric:** top-1 retrieval of the true next state among 10 candidates (chance = 10%), on transitions where the screen changed. Mean of 3 seeds.

| Trained on | Tested on | identity (easy / hard) | action-conditioned (easy / hard) | K1 margin (easy / hard) |
|---|---|---|---|---|
| Invoice Ninja + Dolibarr | same apps, unseen episodes | 51% / 6% | **71% / 42%** | **+20 / +37** |
| Invoice Ninja + Dolibarr | Odoo 17 (held-out app) | 55% / 33% | 51% / 33% | −4 / −1 |
| Invoice Ninja + Dolibarr | Odoo 18 (held-out app) | 56% / 37% | 52% / 34% | −4 / −3 |
| Odoo 17 | same app, unseen episodes | 55% / 23% | **64% / 35%** | **+9 / +12** |
| Odoo 17 | **Odoo 18 (next version)** | 56% / 37% | **65% / 43%** | **+8 / +7** |
| Odoo 17 | Invoice Ninja + Dolibarr | 44% / 23% | 43% / 24% | −1 / +1 |

*Hard* = every candidate is on the same page type, so the prediction must keep record-specific content (K2 proxy). Seed std ≤ 2 points throughout. Full table: `reports/track2.md`.

**Reading:**
- Software dynamics are learnable from label-free exploration and **survive a major version upgrade**, but **do not transfer across apps** when trained on only 1–2 apps.
- The pre-registered K1 (≥ +20 on a held-out app) **fails**.
- The within-app "hard" gains (+12 to +37) suggest the latent keeps some record-level content. K2 isn't settled, though: the hard sets are small, and the identity baseline is near floor there.
- **Next experiment this points to:** scale the *number of distinct apps* in exploration (VeriEnv reports the same lever for policies), rather than the model.

### 5. What this means for the research direction
- **Track 1 (transfer benchmark) is already producing non-obvious, publishable findings:**
  - version-upgrade damage invisible to success metrics;
  - a universal composition collapse;
  - perturbation-driven false completions.
- **Track 2 isn't killed.** It has been narrowed to a sharper question: *how many distinct apps does a latent dynamics model need before it transfers to an unseen one?* That is cheap to test: exploration data is free, and the probe trains in minutes on a laptop.
- **For Phases 1–2 (BC/RL on small models):** UI-TARS-7B's 8–22% zero-shot leaves wide headroom. Its dominant failure (stuck loops on unchanged screens) is exactly what a transition model should help with ("my action changed nothing → do something else").

### 6. Real-world findings from building this
- **Self-hosted Akaunting can't create invoices without vendor registration.** It calls `api.akaunting.com` for plan limits, gets 403, and blocks invoice creation. I replaced it rather than patch out a licensing check.
- **Dolibarr also phones home** (`MAIN_LAST_PING_KO_DATE`), but doesn't block anything.
- **Dolibarr's date widget commits only on blur.** A typed date is ignored until focus leaves the field.
- **Odoo autosaves on navigation,** and opening an invoice can rewrite its terms text (`narration`). That's harmless UI noise and is whitelisted.
- **Odoo 18 locks fields on posted invoices,** which pushes agents into "Reset to Draft", which un-reconciles payments (TL;DR #1).
- **Invoice Ninja shows a first-login welcome modal,** a natural perturbation present in every condition.

### 7. Limitations (honest list)
- **One run per task**, with Wilson binomial confidence intervals over tasks. UI-TARS has 4 instances per skill on Dolibarr and Odoo (8 on Invoice Ninja).
- **Harness bug, found and fixed mid-run.** My format-retry fallback turned Luna's progress narration ("I'll open the invoice list…") into a final answer, ending 35 episodes early. After the fix, all affected Dolibarr and Odoo episodes were rerun. The 12 affected Invoice Ninja episodes couldn't be rerun (app removed for disk space) and are excluded. Counting them as failures instead gives Invoice Ninja clean 81%, flaky 72%, modal 81%, session 75% (`reports/phase0_results.md`). Originals are kept in `runs/_superseded/`.
- **Host is macOS:**
  - `Control+` is mapped to `ControlOrMeta+` for all agents.
  - BrowserGym's hard-coded 500 ms actuation timeout fired on 0–2.8% of steps (highest on Dolibarr). Agents can retry.
- **Infrastructure incidents.** The disk filled twice: a macOS update snapshot pins every rewritten block. Databases were moved to RAM-backed tmpfs and Chromium temp to a RAM disk, then runs resumed from per-episode summaries. Interrupted episodes were rerun from scratch. One Dolibarr modal episode is missing (35/36).
- **UI-TARS adapter.** Runs go through my action adapter. Adapter bugs (key names, select-all on macOS) were fixed before the final UI-TARS runs, and those runs were restarted from zero after the fix.
- **Collateral whitelists are hand-built per app.** Each whitelisted item is app-generated noise identified by inspection and listed in `swm/tasks_*.py` and `swm/report.py`. A different whitelist would shift collateral rates by a few points. The reset-to-draft and wrong-invoice cases don't depend on it.
- **Track 2 limits:** frozen generic encoders, a small MLP, and random (not curiosity-optimal) exploration. A negative cross-app result at this scale says little about larger scale.

### 8. Reproduce
See `README.md`. App images are pinned by digest in `envs/image-digests-phase0.txt` and `envs/invoiceninja/image-digests.txt`. Seed snapshots are in `snapshots/`.
