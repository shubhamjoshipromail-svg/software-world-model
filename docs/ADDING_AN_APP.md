# Adding an app

An app is a Docker Compose stack, a seeder, a task file and a small adapter. `dolibarr` is the shortest
complete example to copy.

| Piece | File | What it must do |
|---|---|---|
| Stack | `envs/<app>/docker-compose.yml`, `.env.example` | Bind only to `127.0.0.1`, disable outbound mail, pin images. Put the database on tmpfs so restores are fast. Use `__NAME__` placeholders in `.env.example` for anything secret |
| Client | `swm/<app>.py` | `BASE`, `CFG`, an API client for seeding, `snapshot(name)`, `restore(name)` |
| Seeder | `swm/seed_<app>.py` | Create the shared synthetic company using `FIRST`, `SUFFIX`, `PRODUCTS` and `near_duplicate` from `swm/seed_invoiceninja.py` with the same seed, then `snapshot("seed_normal")` |
| Tasks | `swm/tasks_<app>.py` | `generate(seed=0, per_skill=8)` returning `Task` objects for the 9 skills in the app's own vocabulary, and `verify(task, diff, answer, after_state)` |
| Adapter | `swm/apps/<app>.py` | `NAME`, `DISPLAY`, `BASE`, `CREDS`, `DEFAULT_SNAPSHOT`, `restore`, `snapshot`, `connect()`, `login(page)`, optional `capture(conn)` |
| CLI | `APPS` in `swm/cli.py` | Compose project name, URL to wait for, seeder environment |

## The verifier contract

`verify` returns:

```python
{"success": bool,
 "collateral": [{"table": ..., "op": "created|deleted|updated", "pk": ..., "cols": [...]}, ...],
 "irreversible": [...]}   # the subset of collateral that cannot be undone
```

`diff` is the output of `swm.dbdiff.diff(before, after)`:
`{table: {"created": {pk: row}, "deleted": {pk: row}, "updated": {pk: {col: (old, new)}}}}`.

Write the verifier as an allow-list: start from "every change is collateral" and explain away only what the task
legitimately causes, including the app's own derived bookkeeping (ledger lines, counters, activity rows).
Anything you whitelist as system noise should be listed in code with a comment saying how you know it is noise.

## Checklist before opening a pull request

- A do-nothing agent produces an empty diff on every task (no noise leaks into collateral).
- Each skill has been done by hand once in the UI and the verifier says success with no collateral.
- `restore` followed by `capture` is identical across two runs.
- No request leaves localhost during an episode.
