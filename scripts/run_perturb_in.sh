#!/bin/zsh
cd ~/software-world-model
for p in modal flaky_network session_expiry; do
  .venv/bin/python -m swm.run_batch --app invoiceninja --per-skill 4 --perturb $p --tag luna/invoiceninja/$p --skip-done 2>&1 | grep -v Warning
done
