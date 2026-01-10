#!/usr/bin/env python3
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_path = get_package_share_directory('my_robot_ai_identification')
    yolo_params = os.path.join(pkg_path, 'config', 'yolo_signals.yaml')

    use_sim_time = LaunchConfiguration('use_sim_time')

    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Use simulation clock if true'
    )

    yolo_node = Node(
        package='my_robot_ai_identification',
        executable='rubot_detection_yolo_exec',
        name='object_detection',
        output='screen',
        parameters=[
            yolo_params,
            {'use_sim_time': use_sim_time},
        ],
    )

    return LaunchDescription([
        declare_use_sim_time,
        yolo_node
    ])
