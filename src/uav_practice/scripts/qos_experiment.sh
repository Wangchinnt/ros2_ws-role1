#!/usr/bin/env bash
# QoS experiment: run the 4 talker/listener reliability combinations, count messages the listener receives.
# Usage: bash src/uav_practice/scripts/qos_experiment.sh   (from ~/coding/ros2_ws, after building)
source /opt/ros/humble/setup.bash
source "$(dirname "$0")/../../../install/setup.bash"
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-77}
EXE="$(ros2 pkg prefix uav_practice)/lib/uav_practice"
LOG=$(mktemp)

run() { # $1 = QoS talker, $2 = QoS listener
  "$EXE/talker" --ros-args -p reliability:="$1" >/dev/null 2>&1 & a=$!
  "$EXE/listener" --ros-args -p reliability:="$2" >"$LOG" 2>&1 & b=$!
  sleep 4
  kill -INT "$a" "$b"; wait "$a" "$b" 2>/dev/null
  printf '%-12s -> %-12s : listener received %s messages\n' "$1" "$2" "$(grep -c 'I heard' "$LOG")"
}

echo "talker QoS   -> listener QoS"
run reliable    reliable
run best_effort best_effort
run reliable    best_effort
run best_effort reliable
rm -f "$LOG"
