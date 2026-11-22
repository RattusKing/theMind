"""ros2 launch themind_ros themind.launch.py mind:=/home/robot/mind

Starts the bridge. Pass model_base_url and model to let the mind think with
a model of its own (a local Ollama is http://localhost:11434/v1), and
api_port:=0 to keep the web API off."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

ARGS = (("mind", "~/themind-mind"), ("api_port", "6464"), ("api_token", ""),
        ("model_base_url", ""), ("model", ""), ("think_seconds", "300.0"),
        ("reach_seconds", "60.0"), ("state_seconds", "10.0"),
        ("battery_topic", "/battery_state"))


def generate_launch_description():
    return LaunchDescription(
        [DeclareLaunchArgument(name, default_value=value) for name, value in ARGS]
        + [Node(package="themind_ros", executable="bridge", name="themind", output="screen",
                parameters=[{name: LaunchConfiguration(name) for name, _v in ARGS}])])
