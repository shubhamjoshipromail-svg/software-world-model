#!/bin/zsh
# Usage: lane.sh <app> <steps...>   step := luna_clean | uitars_clean | luna_modal | explore
# Runs steps sequentially against one app database. Env SWM_IN_INST respected for invoiceninja.
cd ~/software-world-model
# Chromium temp profiles go to a RAM disk: on this Mac an OS-update snapshot pins every deleted block on the data volume
[ -d /Volumes/swmtmp ] && export TMPDIR=/Volumes/swmtmp/
APP=$1; shift
U=$(grep ^UITARS_URL .env | cut -d= -f2)
for s in "$@"; do
  echo "=== $APP $s $(date +%H:%M)"
  case $s in
    luna_clean)   .venv/bin/python -m swm.run_batch --app $APP --per-skill 8 --tag luna/$APP/clean --skip-done ;;
    uitars_clean) .venv/bin/python -m swm.run_batch --app $APP --per-skill 4 --model "uitars:$U" --tag uitars/$APP/clean --skip-done ;;
    luna_modal)   .venv/bin/python -m swm.run_batch --app $APP --per-skill 4 --perturb modal --tag luna/$APP/modal --skip-done ;;
    luna_flaky)   .venv/bin/python -m swm.run_batch --app $APP --per-skill 4 --perturb flaky_network --tag luna/$APP/flaky_network --skip-done ;;
    luna_session) .venv/bin/python -m swm.run_batch --app $APP --per-skill 4 --perturb session_expiry --tag luna/$APP/session_expiry --skip-done ;;
    uitars_clean8) .venv/bin/python -m swm.run_batch --app $APP --per-skill 8 --model "uitars:$U" --tag uitars/$APP/clean --skip-done ;;
    explore)      .venv/bin/python -m swm.explore --app $APP --episodes 30 --steps 40 ;;
  esac 2>&1 | grep -v Warning | grep -E "SUMMARY|error|done|===" 
done
echo "=== $APP lane finished $(date +%H:%M)"
