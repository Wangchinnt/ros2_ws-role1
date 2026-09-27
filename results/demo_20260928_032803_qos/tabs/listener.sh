source /opt/ros/humble/setup.bash; source /home/wangchinnt/coding/ros2_ws/install/setup.bash; cd /home/wangchinnt/coding/ros2_ws
sleep 2
echo "== LISTENER, QoS reliable (default)"
ros2 run uav_practice listener
exec bash
