#!/usr/bin/env bash
# Stop everything demo_up.sh (or a manual sitl/qgc) started: gps_goto, MAVROS, router, PX4, Gazebo, QGC.
# Usage: bash ~/coding/ros2_ws/src/uav_nav/scripts/demo_down.sh
for p in gps_goto mavros_node mavlink-routerd px4; do pkill -INT -x "$p" 2>/dev/null; done
sleep 2
pkill -f "gz sim" 2>/dev/null          # gz server/GUI (ruby process)
pkill -f "make px4_sitl" 2>/dev/null   # make left hanging after px4 exits
pkill -x QGroundControl 2>/dev/null       # match the process name, not the full command line
pkill -x QGroundControl- 2>/dev/null      # AppImage process (name truncated to 15 chars)
sleep 1
pkill -9 -x px4 2>/dev/null
left=$(ps -eo comm | grep -cE "^(px4|ruby|mavros_node|gps_goto|QGroundControl|mavlink-routerd)$")
echo "Stopped. Remaining processes: $left"
