"""
Run MAVROS (MAVLink <-> ROS 2) + gps_goto with parameters from config/gps_goto.yaml.

Usage: ros2 launch uav_nav gps_goto.launch.py
       ros2 launch uav_nav gps_goto.launch.py config:=gps_goto_abc.yaml   (another file in config/)
       ros2 launch uav_nav gps_goto.launch.py router:=true   (through mavlink-router, like VOXL 2)
       ros2 launch uav_nav gps_goto.launch.py start_mavros:=false   (MAVROS already running)
SITL: PX4 sends MAVLink for the onboard computer to UDP 14540.
  router:=false  MAVROS connects directly to 14540.
  router:=true   mavlink-routerd listens on 14540 and fans out to MAVROS (14640) + GCS (14551).
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, EmitEvent, ExecuteProcess,
                            IncludeLaunchDescription, OpaqueFunction, RegisterEventHandler)
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.launch_description_sources import AnyLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

DIRECT_URL = 'udp://:14540@127.0.0.1:14557'
ROUTER_URL = 'udp://:14640@'   # MAVROS listens on 14640, replies to the router's address


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
        actions.append(IncludeLaunchDescription(
            AnyLaunchDescriptionSource(
                os.path.join(get_package_share_directory('mavros'), 'launch', 'px4.launch')),
            launch_arguments={'fcu_url': fcu_url,
                              'gcs_url': LaunchConfiguration('gcs_url').perform(context)
                              }.items()))
    gps_goto = Node(package='uav_nav', executable='gps_goto', name='gps_goto',
                    output='screen', parameters=[config])
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
        OpaqueFunction(function=launch_setup),
    ])
