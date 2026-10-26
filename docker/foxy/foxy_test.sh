#!/usr/bin/env bash
# Build the ROS 2 Foxy image (like the VOXL 2) and run uav_nav's unit tests in it.
#   bash ~/coding/ros2_ws/docker/foxy/foxy_test.sh
# Flying with this image: docs/FOXY_DOCKER.md (by hand) or FOXY=1 src/uav_nav/scripts/sitl_test.sh.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$(cd "$HERE/../../src/uav_nav" && pwd)

docker build -t uav_nav_foxy "$HERE"

# The source is mounted read-only: build into /tmp, and no pytest cache.
docker run --rm -v "$SRC:/ws/src/uav_nav:ro" uav_nav_foxy bash -c '
  source /opt/ros/foxy/setup.bash
  colcon build --packages-select uav_nav --build-base /tmp/build --install-base /tmp/install >/dev/null
  source /tmp/install/setup.bash
  python3 --version
  echo mavros $(dpkg-query -W -f="\${Version}" ros-foxy-mavros)
  python3 -m pytest -q -p no:cacheprovider /ws/src/uav_nav/test/test_geo.py /ws/src/uav_nav/test/test_state_machine.py
  python3 -c "import uav_nav.gps_goto; print(\"import gps_goto OK on Foxy\")"'
