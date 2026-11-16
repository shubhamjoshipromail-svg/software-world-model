# Contributing

Thanks for looking. This is a small research codebase kept deliberately simple; contributions that keep it that
way are the easiest to merge.

## Setup

```bash
make install
make test        # no Docker or API key needed
```

## What helps most

1. **Results for a model we have not run.** See "Sharing a result" in [docs/ADDING_AN_AGENT.md](docs/ADDING_AN_AGENT.md).
2. **Verifier bugs.** If an episode is scored wrong, open an issue with its `summary.json` and say what the
   verdict should be. A false collateral flag and a missed one are equally worth reporting.
3. **A new app or app version.** See [docs/ADDING_AN_APP.md](docs/ADDING_AN_APP.md). Version pairs of the same
   app (like Odoo 17 and 18) are especially useful.
4. **Linux fixes.** The harness was developed on macOS.

## Ground rules

- Do not change a verifier or whitelist without saying which published numbers move and by how much.
  `tests/test_report.py` rebuilds the published table and will fail if they do.
- Never commit `.env` files, snapshots or raw `runs/`.
- Keep every app bound to localhost with outbound mail disabled.
- Add a test for any change to `swm/dbdiff.py` or the UI-TARS action adapter.

## Pull requests

One change per pull request, with the command you ran to check it. For anything larger than a bug fix, open an
issue first so we can agree on the shape.
