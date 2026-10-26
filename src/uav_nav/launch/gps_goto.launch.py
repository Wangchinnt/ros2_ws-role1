"""
Run MAVROS (MAVLink <-> ROS 2) + gps_goto with parameters from config/gps_goto.yaml.

Usage: ros2 launch uav_nav gps_goto.launch.py
       ros2 launch uav_nav gps_goto.launch.py config:=gps_goto_ntut.yaml  (another file in config/)
       ros2 launch uav_nav gps_goto.launch.py router:=true   (through mavlink-router, like VOXL 2)
       ros2 launch uav_nav gps_goto.launch.py start_mavros:=false   (MAVROS already running)
Override the waypoints of the config file from the terminal (quotes needed):
       ros2 launch uav_nav gps_goto.launch.py waypoints:="[25.042833, 121.537612, 10.0]"
       ros2 launch uav_nav gps_goto.launch.py waypoint_frame:=offset waypoints:="[10, 0, 5]"
         (offset = [north_m, east_m, alt_rel] from the takeoff point: 10 m North, 5 m up)
SITL: PX4 sends MAVLink for the onboard computer to UDP 14540.
  router:=false  MAVROS connects directly to 14540.
  router:=true   mavlink-routerd listens on 14540 and fans out to MAVROS (14640) + GCS (14551).
"""
import os

import yaml

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, EmitEvent, ExecuteProcess,
                            OpaqueFunction, RegisterEventHandler)
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

DIRECT_URL = 'udp://:14540@127.0.0.1:14557'
ROUTER_URL = 'udp://:14640@'   # MAVROS listens on 14640, replies to the router's address


def mavros_node(fcu_url, gcs_url):
    """
    Start mavros_node directly instead of including MAVROS' px4.launch.

    ros-foxy-mavros 2.4.0 (VOXL 2) still ships ROS 1 launch/YAML files ($(find), <rosparam>,
    no ros__parameters), which ROS 2 cannot load. Its PX4 YAML files are only passed when they
    are in ROS 2 format (MAVROS 2.15.1 on Humble); otherwise MAVROS runs with its defaults
    except for a plugin denylist.
    """
    launch_dir = os.path.join(get_package_share_directory('mavros'), 'launch')
    params = [{'fcu_url': fcu_url, 'gcs_url': gcs_url}]
    ros2_yaml = []
    for name in ('px4_pluginlists.yaml', 'px4_config.yaml'):
        path = os.path.join(launch_dir, name)
        if os.path.exists(path):
            with open(path) as f:
                if 'ros__parameters' in f.read():
                    ros2_yaml.append(path)
    if not ros2_yaml:
        # Same plugins the Humble px4_pluginlists.yaml disables, plus odometry: without a TF
        # tree it logs a TF error at 30 Hz.
        params[0]['plugin_denylist'] = ['image_pub', 'vibration', 'distance_sensor',
                                        'rangefinder', 'wheel_odometry', 'odometry']
    return Node(package='mavros', executable='mavros_node', output='screen',
                parameters=params + ros2_yaml)


def launch_setup(context):
    share = get_package_share_directory('uav_nav')
    use_router = LaunchConfiguration('router').perform(context).lower() == 'true'
    fcu_url = LaunchConfiguration('fcu_url').perform(context) or \
        (ROUTER_URL if use_router else DIRECT_URL)
    config = os.path.join(share, 'config', LaunchConfiguration('config').perform(context))

    actions = []
    if use_router:
        actions.append(ExecuteProcess(
            cmd=[LaunchConfiguration('router_bin').perform(context),
                 '-c', os.path.join(share, 'config', 'mavlink-router-sitl.conf')],
            name='mavlink_router', output='screen'))
    if LaunchConfiguration('start_mavros').perform(context).lower() == 'true':
        actions.append(mavros_node(fcu_url, LaunchConfiguration('gcs_url').perform(context)))
    # Terminal overrides come after the config file, so they win.
    overrides = {}
    wps = LaunchConfiguration('waypoints').perform(context).strip()
    if wps:
        values = yaml.safe_load(wps)
        if not isinstance(values, list):
            raise ValueError('waypoints:=%r is not a list like "[lat, lon, alt, ...]"' % wps)
        overrides['waypoints'] = [float(v) for v in values]
    frame = LaunchConfiguration('waypoint_frame').perform(context).strip()
    if frame:
        overrides['waypoint_frame'] = frame
    gps_goto = Node(package='uav_nav', executable='gps_goto', name='gps_goto',
                    output='screen', parameters=[config, overrides])
    actions.append(gps_goto)
    # gps_goto finished (DONE/ABORT) -> shut down the whole launch, incl. MAVROS and router.
    actions.append(RegisterEventHandler(OnProcessExit(
        target_action=gps_goto, on_exit=[EmitEvent(event=Shutdown())])))
    return actions


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('config', default_value='gps_goto.yaml'),
        DeclareLaunchArgument('router', default_value='false'),
        DeclareLaunchArgument('router_bin', default_value=os.path.expanduser(
            '~/coding/tools/mavlink-router/install/bin/mavlink-routerd')),
        DeclareLaunchArgument('fcu_url', default_value='',
                              description='empty = choose automatically based on router'),
        DeclareLaunchArgument('gcs_url', default_value=''),
        DeclareLaunchArgument('start_mavros', default_value='true'),
        DeclareLaunchArgument('waypoints', default_value='',
                              description='"[a, b, alt, ...]" overrides the config file'),
        DeclareLaunchArgument('waypoint_frame', default_value='',
                              description='gps | offset; empty = from the config file'),
        OpaqueFunction(function=launch_setup),
    ])
