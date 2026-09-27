source /opt/ros/humble/setup.bash
sleep 4
echo "== Actual QoS of each side (re-run this after changing the talker):"
echo "   ros2 topic info /chatter --verbose | grep -E 'Node name|Reliability'"
echo
ros2 topic info /chatter --verbose | grep -E 'Node name|Reliability'
exec bash
