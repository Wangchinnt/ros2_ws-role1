source /opt/ros/humble/setup.bash; source /home/wangchinnt/coding/ros2_ws/install/setup.bash; cd /home/wangchinnt/coding/ros2_ws
echo "== TALKER, QoS reliable (default). Check the LISTENER tab: messages arrive."
echo "   Step 2: Ctrl+C, then run the best_effort version (listener goes SILENT, no error):"
echo "   ros2 run uav_practice talker --ros-args -p reliability:=best_effort"
echo
ros2 run uav_practice talker
exec bash
