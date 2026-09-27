#!/usr/bin/env bash
# Automated SITL test (headless): start PX4, run MAVROS + gps_goto, (optionally) inject a fault, shut everything down.
#
# Usage: bash ~/coding/ros2_ws/src/uav_nav/scripts/sitl_test.sh [launch args...]
#   e.g. ... sitl_test.sh config:=gps_goto_abc.yaml       fly A -> B -> C
#        ... sitl_test.sh router:=true                    go through mavlink-router
#        SCENARIO=gps_loss ... sitl_test.sh               inject a fault mid-flight
#
# SCENARIO (fault injected 3 s after the flight to WP1 starts):
#   none         normal flight (default)
#   kill_node    kill gps_goto (and MAVROS) -> PX4 loses Offboard setpoints -> PX4 failsafe
#   mode_switch  switch mode to AUTO.LOITER as if the pilot took over -> node must ABORT
#   gps_loss     SIM_GPS_USED=0 -> GPS loses fix -> node must land, EKF/PX4 react
#
# WIND="<East> <North>" (m/s): fly in a windy world (ros2_ws/sim), e.g. WIND="6 0"
# Output: ~/coding/ros2_ws/results/sitl_test_<time>[_<scenario>]/ (gps_goto.log, px4.log, flight.ulg, summary.txt)
PX4_DIR=${PX4_DIR:-$HOME/coding/tools/PX4-Autopilot}
WS=$HOME/coding/ros2_ws
SCENARIO=${SCENARIO:-none}
TAG=$(date +%Y%m%d_%H%M%S); [ "$SCENARIO" != none ] && TAG="${TAG}_${SCENARIO}"
[ -n "$WIND" ] && TAG="${TAG}_wind$(echo "$WIND" | tr ' ' '_')"
OUT=${OUT:-$WS/results/sitl_test_$TAG}
mkdir -p "$OUT"
touch "$OUT/.start"

source /opt/ros/humble/setup.bash
source "$WS/install/setup.bash"

cleanup() {
  [ "$SCENARIO" = gps_loss ] && echo "param set SIM_GPS_USED 10" >&3 2>/dev/null && sleep 1  # restore GPS
  exec 3>&- 2>/dev/null
  pkill -INT -x px4; sleep 2
  kill -- -"$HOLD_PID" 2>/dev/null   # whole process group: make, px4, gz
  [ -n "$GZ_PID" ] && kill -- -"$GZ_PID" 2>/dev/null   # gz server of the windy world
  pkill -9 -x px4 2>/dev/null
  # copy this flight's log (.ulg)
  local ulg
  ulg=$(find "$PX4_DIR/build/px4_sitl_default/rootfs/log" -name '*.ulg' -newer "$OUT/.start" 2>/dev/null | sort | tail -1)
  [ -n "$ulg" ] && cp "$ulg" "$OUT/flight.ulg"
  rm -f "$OUT/px4.stdin" "$OUT/.start"
}
trap cleanup EXIT

# PX4's stdin is a FIFO: keeps the pxh> shell from hitting EOF (on EOF it loops forever and the log
# balloons) and lets the script type commands into PX4 (param set, commander ...) via fd 3.
if [ -n "$WIND" ]; then
  # The x500 copy with <enable_wind> (ros2_ws/sim/models) is found BEFORE PX4's original model.
  read -r WE WN <<< "$WIND"
  sed "s/WIND_E/$WE/; s/WIND_N/$WN/" "$WS/sim/worlds/windy.sdf.in" > "$OUT/windy.sdf"
  export GZ_SIM_RESOURCE_PATH="$WS/sim/models:$PX4_DIR/Tools/simulation/gz/models:$PX4_DIR/Tools/simulation/gz/worlds"
  setsid gz sim -r -s "$OUT/windy.sdf" >"$OUT/gz.log" 2>&1 &
  GZ_PID=$!
  echo "[test] wind East=$WE North=$WN m/s, waiting for gz server..."
  for _ in $(seq 1 30); do gz topic -l 2>/dev/null | grep -q "/world/windy/clock" && break; sleep 1; done
fi
mkfifo "$OUT/px4.stdin"
setsid bash -c "cd '$PX4_DIR' && HEADLESS=1 make px4_sitl gz_x500 < '$OUT/px4.stdin'" >"$OUT/px4.log" 2>&1 &
HOLD_PID=$!
exec 3>"$OUT/px4.stdin"
pxh() { echo "$*" >&3; echo "[test] pxh> $*"; }
# PX4 SAVES parameters to disk (rootfs/parameters.bson): if an earlier test set SIM_GPS_USED=0,
# later runs lose GPS too. Always reset to the default (10 satellites) on startup.
pxh param set SIM_GPS_USED 10 > /dev/null

echo "[test] scenario=$SCENARIO, waiting for PX4 to be ready..."
for _ in $(seq 1 90); do grep -q "Ready for takeoff" "$OUT/px4.log" && break; sleep 2; done
grep -q "Ready for takeoff" "$OUT/px4.log" || { echo "PX4 not ready, see $OUT/px4.log"; exit 1; }

# The launch starts MAVROS (+ router if enabled) and gps_goto; when gps_goto exits (DONE/ABORT) the launch shuts down.
timeout -s INT 400 ros2 launch uav_nav gps_goto.launch.py "$@" >"$OUT/gps_goto.log" 2>&1 &
LAUNCH_PID=$!

if [ "$SCENARIO" != none ]; then
  for _ in $(seq 1 120); do grep -q "WP1: .* to go" "$OUT/gps_goto.log" && break; sleep 1; done
  sleep 3
  echo "[test] >>> injecting fault: $SCENARIO"
  case "$SCENARIO" in
    kill_node)   pkill -INT -f "lib/uav_nav/gps_goto" ;;
    mode_switch) ros2 service call /mavros/set_mode mavros_msgs/srv/SetMode "{custom_mode: AUTO.LOITER}" >/dev/null ;;
    gps_loss)    pxh param set SIM_GPS_USED 0 ;;
    *) echo "Invalid SCENARIO: $SCENARIO"; exit 2 ;;
  esac
fi
wait $LAUNCH_PID 2>/dev/null

# The node has exited. If the drone is not disarmed yet (e.g. PX4 holding position after failsafe),
# wait for PX4 to handle it; after 40 s command a landing via pxh to end the test.
if ! grep -q "Disarmed" "$OUT/px4.log"; then
  echo "[test] node exited, drone not disarmed -> waiting up to 40 s for PX4 to handle it"
  for _ in $(seq 1 40); do grep -q "Disarmed" "$OUT/px4.log" && break; sleep 1; done
  if ! grep -q "Disarmed" "$OUT/px4.log"; then
    pxh commander land
    for _ in $(seq 1 60); do grep -q "Disarmed" "$OUT/px4.log" && break; sleep 1; done
  fi
fi

{
  echo "scenario: $SCENARIO   wind: ${WIND:-none}   args: $*"
  echo "--- gps_goto:"
  sed -E 's/.*\[gps_goto\]: //' "$OUT/gps_goto.log" \
    | grep -E "Projection origin|WP[0-9] GPS|->|REACHED|After holding|Done|ERROR|Lost|GPS degraded" | grep -v "to go"
  echo "--- PX4:"
  sed 's/\x1b\[[0-9;]*m//g; s/pxh> //g' "$OUT/px4.log" \
    | grep -E "INFO  \[commander\]|WARN|ERROR|navigator" | grep -vE "param|Startup|parameters" | uniq | head -30
  echo "--- conclusion: $(grep -q 'Disarmed' "$OUT/px4.log" && echo 'drone landed and disarmed' || echo 'NOT disarmed')"
} > "$OUT/summary.txt"
cat "$OUT/summary.txt"
echo "Log: $OUT"
