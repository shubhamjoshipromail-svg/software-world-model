# Changelog

## 0.1.0 (2026-11-15)

First public release.

- Phase 0 benchmark: 4 self-hosted apps, 72 tasks per app, whole-database diff verifiers, 3 perturbations.
- Baselines: GPT-6 Luna and UI-TARS-1.5-7B; 635 scored episodes published in `results/phase0_episodes.jsonl`.
- `swm` command: `doctor`, `up`, `down`, `run`, `report`, `export-results`.
- Agents: any OpenAI-compatible endpoint via `OPENAI_BASE_URL`, or your own class via `--model custom:module:Class`.
- Latent dynamics probe (Track 2) and its results.
