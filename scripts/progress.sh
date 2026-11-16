#!/bin/zsh
# Per-condition progress: completed episodes, successes, infra errors
cd "$(dirname "$0")/../runs" || exit 1
for d in */*/*(/); do
  [[ $d == _debug* || $d == smoke* ]] && continue
  n=$(ls $d/*/summary.json 2>/dev/null | wc -l | tr -d ' ')
  ok=$(cat $d/*/summary.json 2>/dev/null | grep -c '"success": true')
  echo "$d: $n done, $ok ok"
done
df -h /System/Volumes/Data | tail -1 | awk '{print "disk free:", $4}'
