# Environment matching the VOXL 2 drone (ROS 2 Foxy, Ubuntu 20.04, Python 3.8) to try uav_nav before deploying.
# MAVROS for Foxy is on apt: ros-foxy-mavros 2.4.0 (the Humble dev machine uses 2.15.1 built from source).
FROM ros:foxy-ros-base

RUN apt-get update && apt-get install -y --no-install-recommends \
        ros-foxy-mavros ros-foxy-mavros-extras ros-foxy-mavros-msgs \
        ros-foxy-geographic-msgs python3-pytest python3-colcon-common-extensions \
    && /opt/ros/foxy/lib/mavros/install_geographiclib_datasets.sh \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /ws
# Code is mounted into /ws/src at run time (see foxy_test.sh), not copied into the image.
