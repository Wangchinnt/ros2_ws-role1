#!/usr/bin/env bash
# Automated SITL test (headless): start PX4, run MAVROS + gps_goto, optionally inject a fault, stop everything.
# It does the same steps as docs/MANUAL_RUN.md, without the GUI. Use it to re-check the code after a change.
#
# Usage: bash ~/coding/ros2_ws/src/uav_nav/scripts/sitl_test.sh [launch args...]
#   ... sitl_test.sh                                      1 waypoint (config gps_goto.yaml)
#   ... sitl_test.sh config:=gps_goto_ntut.yaml           3 waypoints on the NTUT field
#   ... sitl_test.sh waypoint_frame:=offset waypoints:="[10.0, 0.0, 5.0]"   10 m North, 5 m up
#
# Environment variables:
#   SCENARIO  none (default) | kill_node | mode_switch | gps_loss   fault injected 3 s after the flight to WP1 starts
#   WIND      "<East> <North>" air velocity in m/s, e.g. "-3 0" = 3 m/s wind FROM the East
#   FOXY=1    run MAVROS 2.4.0 + gps_goto in the ROS 2 Foxy container (build it: docker/foxy/foxy_test.sh);
#             SCENARIO=none|gps_loss only
#
# The SITL takeoff point is PX4's saved SIM_GZ_HOME_* parameter: set it once by hand (docs/MANUAL_RUN.md §2).
# Output: results/runs/<time>[_<scenario>]/ with gps_goto.log, px4.log, flight.ulg, summary.txt
PX4_DIR=${PX4_DIR:-$HOME/coding/tools/PX4-Autopilot}
WS=$(cd "$(dirname "$0")/../../.." && pwd)
SCENARIO=${SCENARIO:-none}
TAG=$(date +%Y%m%d_%H%M%S)
[ "$SCENARIO" != none ] && TAG="${TAG}_${SCENARIO}"
[ -n "$WIND" ] && TAG="${TAG}_wind$(echo "$WIND" | tr ' ' '_')"
[ -n "$FOXY" ] && TAG="${TAG}_foxy"
OUT=$WS/results/runs/$TAG
mkdir -p "$OUT"
touch "$OUT/.start"

source /opt/ros/humble/setup.bash
source "$WS/install/setup.bash"

if [ -n "$FOXY" ]; then
  case "$SCENARIO" in none|gps_loss) ;; *) echo "FOXY=1 supports SCENARIO=none|gps_loss only"; exit 2 ;; esac
  docker image inspect uav_nav_foxy >/dev/null 2>&1 || { echo "No uav_nav_foxy image: run docker/foxy/foxy_test.sh first"; exit 1; }
fi

pxh() { echo "$*" >&3; echo "[test] pxh> $*"; }   # type a command into PX4's pxh> shell

cleanup() {
  [ -n "$FOXY" ] && docker rm -f uav_nav_foxy_sitl >/dev/null 2>&1
  [ "$SCENARIO" = gps_loss ] && pxh param set SIM_GPS_USED 10 && sleep 1   # restore GPS (saved to disk)
  exec 3>&-
  pkill -INT -x px4; sleep 2
  kill -- -"$PX4_PID" 2>/dev/null                    # whole process group: make, px4, gz
  [ -n "$GZ_PID" ] && kill -- -"$GZ_PID" 2>/dev/null
  pkill -9 -x px4 2>/dev/null
  ulg=$(find "$PX4_DIR/build/px4_sitl_default/rootfs/log" -name '*.ulg' -newer "$OUT/.start" | sort | tail -1)
  [ -n "$ulg" ] && cp "$ulg" "$OUT/flight.ulg"
  rm -f "$OUT/px4.stdin" "$OUT/.start"
}
trap cleanup EXIT

# 1. Wind: start Gazebo with the windy world first; PX4 then uses the running world.
if [ -n "$WIND" ]; then
  read -r WE WN <<< "$WIND"
  sed "s/WIND_E/$WE/; s/WIND_N/$WN/" "$WS/sim/worlds/windy.sdf.in" > "$OUT/windy.sdf"
  # The x500 copy with <enable_wind> in ros2_ws/sim/models is found before PX4's own model.
  export GZ_SIM_RESOURCE_PATH="$WS/sim/models:$PX4_DIR/Tools/simulation/gz/models:$PX4_DIR/Tools/simulation/gz/worlds"
  setsid gz sim -r -s "$OUT/windy.sdf" >"$OUT/gz.log" 2>&1 &
  GZ_PID=$!
  echo "[test] wind East=$WE North=$WN m/s, waiting for gz server..."
  for _ in $(seq 1 30); do gz topic -l 2>/dev/null | grep -q "/world/windy/clock" && break; sleep 1; done
fi

# 2. PX4 SITL. Its stdin is a FIFO so this script can type pxh commands (fd 3); with /dev/null as stdin
#    pxh hits EOF, loops forever and the log grows to GBs.
mkfifo "$OUT/px4.stdin"
setsid bash -c "cd '$PX4_DIR' && HEADLESS=1 make px4_sitl gz_x500 < '$OUT/px4.stdin'" >"$OUT/px4.log" 2>&1 &
PX4_PID=$!
exec 3>"$OUT/px4.stdin"
pxh param set SIM_GPS_USED 10 > /dev/null   # an earlier gps_loss run may have saved 0
echo "[test] scenario=$SCENARIO, waiting for PX4 to be ready..."
for _ in $(seq 1 90); do grep -q "Ready for takeoff" "$OUT/px4.log" && break; sleep 2; done
grep -q "Ready for takeoff" "$OUT/px4.log" || { echo "PX4 not ready, see $OUT/px4.log"; exit 1; }

# 3. MAVROS + gps_goto. The launch ends when gps_goto exits (DONE/ABORT).
if [ -n "$FOXY" ]; then
  timeout -s INT 400 docker run --rm --init --name uav_nav_foxy_sitl --net=host -e ROS_DOMAIN_ID=42 \
    -v "$WS/src/uav_nav:/ws/src/uav_nav:ro" uav_nav_foxy bash -c \
    "source /opt/ros/foxy/setup.bash \
     && colcon build --packages-select uav_nav --build-base /tmp/build --install-base /tmp/install >/dev/null \
     && source /tmp/install/setup.bash && exec ros2 launch uav_nav gps_goto.launch.py $*" \
    >"$OUT/gps_goto.log" 2>&1 &
else
  timeout -s INT 400 ros2 launch uav_nav gps_goto.launch.py "$@" >"$OUT/gps_goto.log" 2>&1 &
fi
LAUNCH_PID=$!

# 4. Optional fault, 3 s after the flight to WP1 starts.
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

# 5. Node gone but drone still armed (e.g. PX4 holding after a failsafe): give PX4 40 s, then land via pxh.
if grep -q "Armed by" "$OUT/px4.log" && ! grep -q "Disarmed" "$OUT/px4.log"; then
  echo "[test] node exited, drone not disarmed -> waiting up to 40 s for PX4"
  for _ in $(seq 1 40); do grep -q "Disarmed" "$OUT/px4.log" && break; sleep 1; done
  grep -q "Disarmed" "$OUT/px4.log" || pxh commander land
  for _ in $(seq 1 60); do grep -q "Disarmed" "$OUT/px4.log" && break; sleep 1; done
fi

# 6. Summary.
{
  echo "scenario: $SCENARIO   wind: ${WIND:-none}   ros: $([ -n "$FOXY" ] && echo 'foxy (docker)' || echo humble)   args: $*"
  echo "--- gps_goto:"
  sed -E 's/.*\[gps_goto\]: //' "$OUT/gps_goto.log" \
    | grep -E "Projection origin|WP[0-9] |->|REACHED|After holding|Done|ERROR|Lost|GPS degraded" | grep -v "to go"
  echo "--- PX4:"
  sed 's/\x1b\[[0-9;]*m//g; s/pxh> //g' "$OUT/px4.log" \
    | grep -E "INFO  \[commander\]|WARN|ERROR|navigator" | grep -vE "param|Startup|parameters" | uniq | head -30
  if ! grep -q "Armed by" "$OUT/px4.log"; then
    echo "--- conclusion: drone never armed (node stopped before takeoff)"
  elif grep -q "Disarmed" "$OUT/px4.log"; then
    echo "--- conclusion: drone landed and disarmed"
  else
    echo "--- conclusion: NOT disarmed"
  fi
} > "$OUT/summary.txt"
cat "$OUT/summary.txt"
echo "Log: $OUT"
