cd "/home/wangchinnt/coding/tools/PX4-Autopilot"
{ echo "param set SIM_GPS_USED 10"; cat; } | make px4_sitl gz_x500
exec bash
