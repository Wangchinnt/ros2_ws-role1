#!/usr/bin/env bash
# Try uav_nav on ROS 2 Foxy (like VOXL 2) using Docker.
#
# Step 1 (every time):  build the image + build uav_nav on Foxy + run unit tests
#   bash ~/coding/ros2_ws/docker/foxy/foxy_test.sh
# Step 2 (optional):    actually fly against SITL running on the host
#   T1: sitl-headless          (PX4 SITL on the host, Humble)
#   T2: bash ~/coding/ros2_ws/docker/foxy/foxy_test.sh fly
#   -> MAVROS 2.4.0 + gps_goto run INSIDE the Foxy container, reaching PX4 over UDP 14540 (--net=host)
#
# Requires Docker: sudo apt install docker.io && sudo usermod -aG docker $USER  (log out / log in again)
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$HOME/coding/ros2_ws/src/uav_nav
IMAGE=uav_nav_foxy

docker build -t "$IMAGE" "$HERE"

# Separate ROS_DOMAIN_ID so Foxy nodes in the container do not mix with Humble nodes on the host.
RUN=(docker run --rm -it --net=host -e ROS_DOMAIN_ID=42 -v "$SRC:/ws/src/uav_nav:ro" "$IMAGE")
BUILD='source /opt/ros/foxy/setup.bash && colcon build --packages-select uav_nav --build-base /tmp/build --install-base /tmp/install >/dev/null && source /tmp/install/setup.bash'

if [ "${1:-}" = fly ]; then
  "${RUN[@]}" bash -c "$BUILD && ros2 launch uav_nav gps_goto.launch.py"
else
  "${RUN[@]}" bash -c "$BUILD && python3 --version && python3 -m pytest -q /ws/src/uav_nav/test/test_geo.py \
    && python3 -c 'import uav_nav.gps_goto as g; print(\"import gps_goto OK on Foxy\")'"
fi
