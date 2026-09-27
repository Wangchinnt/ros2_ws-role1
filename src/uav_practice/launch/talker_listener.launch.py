"""
Run talker + listener together.

Usage: ros2 launch uav_practice talker_listener.launch.py
"""
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(package='uav_practice', executable='talker', name='talker',
             output='screen', parameters=[{'period': 0.5}]),
        Node(package='uav_practice', executable='listener', name='listener',
             output='screen'),
    ])
