#!/usr/bin/env bash
# Milestone 1: arm -> takeoff -> hover -> move -> land, repeated N times in a row on SITL (default 5).
# Usage: bash ~/coding/ros2_ws/src/uav_nav/scripts/milestone1.sh [N] [launch args...]
#   e.g. ... milestone1.sh 5                      (1 waypoint, default config)
#        ... milestone1.sh 5 router:=true         (through mavlink-router)
# Output: ~/coding/ros2_ws/results/milestone1_<time>/SUMMARY.md + run_<i>/ (log, ulog, flight.png)
N=${1:-5}; shift || true
HERE=$(cd "$(dirname "$0")" && pwd)
M=$HOME/coding/ros2_ws/results/milestone1_$(date +%Y%m%d_%H%M%S)
mkdir -p "$M"

pass=0
{
  echo "# Milestone 1 — $N consecutive runs ($(date '+%Y-%m-%d %H:%M'))"
  echo
  echo "Launch args: \`${*:-default}\`"
  echo
  echo "| Run | Result | Error on arrival | Error after hold | Duration (s) | Note |"
  echo "|---|---|---|---|---|---|"
} > "$M/SUMMARY.md"

for i in $(seq 1 "$N"); do
  echo "=============== Run $i/$N ==============="
  start=$(date +%s)
  OUT="$M/run_$i" bash "$HERE/sitl_test.sh" "$@" > "$M/run_$i.console.log" 2>&1
  dur=$(( $(date +%s) - start ))
  L="$M/run_$i/gps_goto.log"
  touch_err=$(grep -oE "REACHED WP1.*error [0-9.]+ m" "$L" | grep -oE "[0-9.]+ m$" | head -1)
  hold_err=$(grep -oE "After holding .* WP1: error [0-9.]+ m" "$L" | grep -oE "[0-9.]+ m$" | head -1)
  if grep -q "\[LANDING\] -> \[DONE\]" "$L" && grep -q "Disarmed" "$M/run_$i/px4.log" \
     && ! grep -qE "ABORT|\[ERROR\] \[[0-9.]+\] \[gps_goto\]" "$L"; then
    res="PASS"; pass=$((pass + 1)); note=""
  else
    res="FAIL"; note=$(grep -E "ERROR|ABORT" "$L" | grep gps_goto | head -1 | sed -E 's/.*\]: //')
  fi
  echo "| $i | $res | ${touch_err:--} | ${hold_err:--} | $dur | $note |" >> "$M/SUMMARY.md"
  echo "Run $i: $res, error after hold ${hold_err:--}, ${dur}s"
  python3 "$HERE/plot_flight.py" "$M/run_$i" > /dev/null 2>&1
  sleep 3
done

{
  echo
  echo "**Total: $pass/$N runs passed** (pass = reached DONE, PX4 reported Disarmed, no ERROR/ABORT from the node)."
} >> "$M/SUMMARY.md"
echo; cat "$M/SUMMARY.md"
echo "Results: $M"
