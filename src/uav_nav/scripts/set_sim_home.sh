#!/usr/bin/env bash
# Set the PX4 SITL takeoff point (SIM_GZ_HOME_LAT/LON/ALT) before a GUI demo.
#
# Usage: bash ~/coding/ros2_ws/src/uav_nav/scripts/set_sim_home.sh [<lat> <lon> <alt>]
#   no arguments = NTUT East Dorm field 25.042486 121.537627 10 (the project default)
#   e.g.  ... set_sim_home.sh 47.397742 8.545594 488.0        PX4's own default (Zurich)
#
# Why a separate step: gz_bridge reads SIM_GZ_HOME_* only once at startup (GZBridge.cpp:
# _pos_ref.initReference), and PX4 saves "param set" to rootfs/parameters.bson. So the value is
# written in a short headless PX4 run here and used by the next PX4 start (e.g. demo_up.sh).
# Takes ~20-40 s. Does nothing if the saved home already matches (within ~6 m).
PX4_DIR=${PX4_DIR:-$HOME/coding/tools/PX4-Autopilot}
LAT=${1:-25.042486}; LON=${2:-121.537627}; ALT=${3:-10}

if pgrep -x px4 >/dev/null; then
  echo "PX4 is already running: stop it first (demo_down.sh)"; exit 1
fi

TMP=$(mktemp -d)
mkfifo "$TMP/px4.stdin"
setsid bash -c "cd '$PX4_DIR' && HEADLESS=1 make px4_sitl gz_x500 < '$TMP/px4.stdin'" >"$TMP/px4.log" 2>&1 &
PID=$!
exec 3>"$TMP/px4.stdin"
cleanup() {
  exec 3>&- 2>/dev/null
  pkill -INT -x px4; sleep 2
  kill -- -"$PID" 2>/dev/null
  pkill -9 -x px4 2>/dev/null
  rm -rf "$TMP"
}
trap cleanup EXIT

echo "[home] starting PX4 headless..."
for _ in $(seq 1 90); do grep -q "Ready for takeoff" "$TMP/px4.log" && break; sleep 2; done
grep -q "Ready for takeoff" "$TMP/px4.log" || { echo "PX4 did not start:"; tail -5 "$TMP/px4.log"; exit 1; }

param_value() {   # param show prints 4 decimals
  echo "param show $1" >&3; sleep 1
  sed 's/\x1b\[[0-9;]*m//g' "$TMP/px4.log" | grep -E "$1 \[" | tail -1 | sed -E 's/.*: *//'
}
OLD_LAT=$(param_value SIM_GZ_HOME_LAT); OLD_LON=$(param_value SIM_GZ_HOME_LON)
if awk -v a="$OLD_LAT" -v b="$OLD_LON" -v c="$LAT" -v d="$LON" \
     'BEGIN { exit !((a-c)^2 < 3.6e-9 && (b-d)^2 < 3.6e-9) }'; then
  echo "[home] already $OLD_LAT $OLD_LON, nothing to change"
  exit 0
fi
echo "param set SIM_GZ_HOME_LAT $LAT" >&3
echo "param set SIM_GZ_HOME_LON $LON" >&3
echo "param set SIM_GZ_HOME_ALT $ALT" >&3
sleep 2   # let PX4 write parameters.bson
echo "[home] $OLD_LAT $OLD_LON -> $LAT $LON (alt $ALT m), used from the next PX4 start"
