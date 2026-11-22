#!/usr/bin/env bash
# The physics test: Gazebo, headless, faster than real time. A robot drives
# from the kitchen to the garden while its battery drains, Sam comes in and
# goes, and theMind's bridge listens. Then the mind is checked against what
# the physics really did.
#   ros2/sim_check.sh       (with ROS 2 Jazzy and Gazebo: ros-jazzy-ros-gz)
set -eo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/.." && pwd)
PY=${PYTHON:-python3}
WS=$(mktemp -d)
echo "working in $WS"
mkdir -p "$WS/src" && cp -r "$HERE/themind_ros" "$WS/src/"
source "/opt/ros/${ROS_DISTRO:-jazzy}/setup.bash"
cd "$WS"
$PY -m colcon build > "$WS/build.log" 2>&1 || { cat "$WS/build.log"; exit 1; }
source install/setup.bash
export PYTHONPATH="$REPO:$PYTHONPATH"
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-43}
export GZ_PARTITION="themind_$$"
BIN="$WS/install/themind_ros/lib/themind_ros"
PIDS=()
stop() { for p in "${PIDS[@]}"; do kill -INT "$p" 2>/dev/null || true; done; sleep 2;
         for p in "${PIDS[@]}"; do kill -9 "$p" 2>/dev/null || true; done; }
trap stop EXIT

gz sim -s -r "$HERE/sim/house.sdf" > "$WS/gazebo.log" 2>&1 &
PIDS+=($!)
# Run directly (not through `ros2 run`) so that stopping it stops it.
"/opt/ros/${ROS_DISTRO:-jazzy}/lib/ros_gz_bridge/parameter_bridge" \
    /clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock \
    /model/robot/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist \
    /model/robot/odometry@nav_msgs/msg/Odometry[gz.msgs.Odometry \
    /model/robot/battery/linear_battery/state@sensor_msgs/msg/BatteryState[gz.msgs.BatteryState \
    /robot/eyes@ros_gz_interfaces/msg/LogicalCameraImage[gz.msgs.LogicalCameraImage \
    > "$WS/gz_bridge.log" 2>&1 &
PIDS+=($!)
$PY "$BIN/bridge" --ros-args -p use_sim_time:=true -p mind:="$WS/mind" -p api_port:=0 \
    -p battery_topic:=/model/robot/battery/linear_battery/state \
    -p reach_seconds:=1.0 -p state_seconds:=5.0 > "$WS/bridge.log" 2>&1 &
PIDS+=($!)
sleep 3
timeout 180 $PY "$HERE/sim/sim_senses.py" --ros-args -p use_sim_time:=true \
    -p report:="$WS/report.json" > "$WS/senses.log" 2>&1 \
    || { tail -n 20 "$WS/senses.log" "$WS/bridge.log" "$WS/gz_bridge.log" "$WS/gazebo.log";
         exit 1; }
stop
trap - EXIT
$PY "$HERE/sim/check_sim.py" "$WS/mind" "$WS/report.json" "$WS/bridge.log" "$WS/senses.log" \
    || { tail -n 30 "$WS/bridge.log" "$WS/senses.log"; exit 1; }
