#!/usr/bin/env bash
# Open every window for a live demo (GUI): 1 gnome-terminal window, one tab per job.
#
#   bash ~/coding/ros2_ws/src/uav_nav/scripts/demo_up.sh          main demo (PX4 + Gazebo + QGC + node), NTUT
#   CONFIG=gps_goto.yaml bash .../demo_up.sh                      fly 1 point instead of 3
#   (default SITE=ntut: NTUT East Dorm field, Taipei, 3 waypoints)
#   SITE=zurich bash .../demo_up.sh                               PX4's default location, A -> B -> C
#   FOXY=1 bash .../demo_up.sh                                    node + MAVROS 2.4.0 on ROS 2 Foxy (Docker)
#   bash ~/coding/ros2_ws/src/uav_nav/scripts/demo_up.sh qos      self-study demo: QoS talker/listener
#   bash ~/coding/ros2_ws/src/uav_nav/scripts/demo_down.sh        stop everything after the demo
#
# Main demo, 4 tabs:
#   1 PX4    PX4 SITL + Gazebo GUI. Type pxh commands here (param set, commander ...).
#   2 QGC    QGroundControl (auto-connects on UDP 14550).
#   3 NODE   Press Enter when the PX4 tab prints "Ready for takeoff!" -> MAVROS + gps_goto.
#            After the flight: save logs, plot the trajectory, open the image.
#   4 WATCH  Monitoring and fault-injection commands to copy and paste.
WS=$HOME/coding/ros2_ws
PX4_DIR=${PX4_DIR:-$HOME/coding/tools/PX4-Autopilot}
QGC=$HOME/Applications/QGroundControl-v5.0.8-x86_64.AppImage
# SITE picks the SITL takeoff point and the default waypoint file together.
case "${SITE:-ntut}" in
  zurich) HOME_LLA="47.397742 8.545594 488.0"; DEFAULT_CONFIG=gps_goto_abc.yaml ;;
  ntut)   HOME_LLA="25.042486 121.537627 10";  DEFAULT_CONFIG=gps_goto_ntut.yaml ;;
  *) echo "Unknown SITE=$SITE (zurich | ntut)"; exit 2 ;;
esac
CONFIG=${CONFIG:-$DEFAULT_CONFIG}
MODE=${1:-main}

OUT=$WS/results/demo_$(date +%Y%m%d_%H%M%S)_$MODE
T=$OUT/tabs
mkdir -p "$T"
touch "$OUT/.start"
SRC="source /opt/ros/humble/setup.bash; source $WS/install/setup.bash; cd $WS"

if [ "$MODE" = qos ]; then
  cat > "$T/talker.sh" <<EOF
$SRC
echo "== TALKER, QoS reliable (default). Check the LISTENER tab: messages arrive."
echo "   Step 2: Ctrl+C, then run the best_effort version (listener goes SILENT, no error):"
echo "   ros2 run uav_practice talker --ros-args -p reliability:=best_effort"
echo
ros2 run uav_practice talker
exec bash
EOF
  cat > "$T/listener.sh" <<EOF
$SRC
sleep 2
echo "== LISTENER, QoS reliable (default)"
ros2 run uav_practice listener
exec bash
EOF
  cat > "$T/watch.sh" <<'EOF'
source /opt/ros/humble/setup.bash
sleep 4
echo "== Actual QoS of each side (re-run this after changing the talker):"
echo "   ros2 topic info /chatter --verbose | grep -E 'Node name|Reliability'"
echo
ros2 topic info /chatter --verbose | grep -E 'Node name|Reliability'
exec bash
EOF
  gnome-terminal --window --title="TALKER" -e "bash $T/talker.sh" \
    --tab --title="LISTENER" -e "bash $T/listener.sh" \
    --tab --title="WATCH" -e "bash $T/watch.sh" 2>/dev/null
  echo "QoS demo window opened."
  exit 0
fi

# The SITL home (SIM_GZ_HOME_*) is read only at PX4 startup and saved to disk: set it before opening PX4.
# shellcheck disable=SC2086
bash "$WS/src/uav_nav/scripts/set_sim_home.sh" $HOME_LLA || exit 1

# PX4 tab: the first line resets SIM_GPS_USED=10 (PX4 saves params to disk; an old gps_loss test may have left 0),
# then "cat" forwards whatever you type to the PX4 pxh> shell. Ctrl+C stops PX4.
cat > "$T/px4.sh" <<EOF
cd "$PX4_DIR"
{ echo "param set SIM_GPS_USED 10"; cat; } | make px4_sitl gz_x500
exec bash
EOF

cat > "$T/qgc.sh" <<EOF
sleep 8
"$QGC"
exec bash
EOF

if [ -n "$FOXY" ]; then
  # Same as sitl_test.sh FOXY=1: MAVROS 2.4.0 + gps_goto in the uav_nav_foxy image (docker/foxy/foxy_test.sh builds it).
  LAUNCH="docker run --rm --init --net=host -e ROS_DOMAIN_ID=42 -v $WS/src/uav_nav:/ws/src/uav_nav:ro uav_nav_foxy \
bash -c 'source /opt/ros/foxy/setup.bash && colcon build --packages-select uav_nav --build-base /tmp/build \
--install-base /tmp/install >/dev/null && source /tmp/install/setup.bash && exec ros2 launch uav_nav gps_goto.launch.py config:=$CONFIG'"
else
  LAUNCH="ros2 launch uav_nav gps_goto.launch.py config:=$CONFIG"
fi

cat > "$T/node.sh" <<EOF
$SRC
clear
echo "== NODE gps_goto (site: ${SITE:-ntut}, config: $CONFIG, ROS: $([ -n "$FOXY" ] && echo 'Foxy in Docker' || echo Humble))"
echo "Wait for the PX4 tab to print 'Ready for takeoff!' and QGC to see the drone, then press Enter to fly."
read -r _
$LAUNCH 2>&1 | tee "$OUT/gps_goto.log"
ULG=\$(find "$PX4_DIR/build/px4_sitl_default/rootfs/log" -name '*.ulg' -newer "$OUT/.start" | sort | tail -1)
if [ -n "\$ULG" ]; then
  cp "\$ULG" "$OUT/flight.ulg"
  python3 src/uav_nav/scripts/plot_flight.py "$OUT" && xdg-open "$OUT/flight.png"
fi
echo
echo "Logs + plot: $OUT"
echo "Fly again: $LAUNCH"
exec bash
EOF

cat > "$T/watch.sh" <<EOF
$SRC
clear
cat <<'TXT'
== Monitoring commands (paste while the node is running):
  rqt_graph                                                   # node graph: gps_goto <-> mavros
  ros2 topic hz /mavros/setpoint_position/local               # ~20 Hz (PX4 needs > 2 Hz)
  ros2 topic echo /mavros/state --field mode                  # OFFBOARD / AUTO.LAND ...
  ros2 topic echo /mavros/gpsstatus/gps1/raw --field h_acc    # GPS accuracy (mm)
  ros2 node list

== Inject faults live (while the drone is flying to a WP):
  Pilot takeover: QGC -> click the mode name at the top -> choose "Hold"   => node ABORT
  GPS loss: type in tab 1 PX4:   param set SIM_GPS_USED 0             => node requests landing
            then remember:      param set SIM_GPS_USED 10
TXT
exec bash
EOF

gnome-terminal --window --title="1 PX4" -e "bash $T/px4.sh" \
  --tab --title="2 QGC" -e "bash $T/qgc.sh" \
  --tab --title="3 NODE" -e "bash $T/node.sh" \
  --tab --title="4 WATCH" -e "bash $T/watch.sh" 2>/dev/null
echo "Demo window opened (4 tabs). Logs for this run: $OUT"
