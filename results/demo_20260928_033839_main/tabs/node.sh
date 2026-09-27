source /opt/ros/humble/setup.bash; source /home/wangchinnt/coding/ros2_ws/install/setup.bash; cd /home/wangchinnt/coding/ros2_ws
clear
echo "== NODE gps_goto (config: gps_goto_abc.yaml)"
echo "Wait for the PX4 tab to print 'Ready for takeoff!' and QGC to see the drone, then press Enter to fly."
read -r _
ros2 launch uav_nav gps_goto.launch.py config:=gps_goto_abc.yaml 2>&1 | tee "/home/wangchinnt/coding/ros2_ws/results/demo_20260928_033839_main/gps_goto.log"
ULG=$(find "/home/wangchinnt/coding/tools/PX4-Autopilot/build/px4_sitl_default/rootfs/log" -name '*.ulg' -newer "/home/wangchinnt/coding/ros2_ws/results/demo_20260928_033839_main/.start" | sort | tail -1)
if [ -n "$ULG" ]; then
  cp "$ULG" "/home/wangchinnt/coding/ros2_ws/results/demo_20260928_033839_main/flight.ulg"
  python3 src/uav_nav/scripts/plot_flight.py "/home/wangchinnt/coding/ros2_ws/results/demo_20260928_033839_main" && xdg-open "/home/wangchinnt/coding/ros2_ws/results/demo_20260928_033839_main/flight.png"
fi
echo
echo "Logs + plot: /home/wangchinnt/coding/ros2_ws/results/demo_20260928_033839_main"
echo "Fly again: ros2 launch uav_nav gps_goto.launch.py config:=gps_goto_abc.yaml"
exec bash
