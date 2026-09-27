source /opt/ros/humble/setup.bash; source /home/wangchinnt/coding/ros2_ws/install/setup.bash; cd /home/wangchinnt/coding/ros2_ws
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
