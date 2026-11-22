#!/usr/bin/env bash
# The stress run: hours of a random life in the physics simulation, then a
# judgement of what held and a measure of how it ran. Seeded and repeatable.
#   ros2/stress_check.sh                 (STRESS_SECONDS=7200 STRESS_SEED=7 by default)
set -eo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/.." && pwd)
PY=${PYTHON:-python3}
SECONDS_SIM=${STRESS_SECONDS:-7200}
SEED=${STRESS_SEED:-7}
WS=$(mktemp -d)
echo "working in $WS"
mkdir -p "$WS/src" && cp -r "$HERE/themind_ros" "$WS/src/"
source "/opt/ros/${ROS_DISTRO:-jazzy}/setup.bash"
cd "$WS"
$PY -m colcon build > "$WS/build.log" 2>&1 || { cat "$WS/build.log"; exit 1; }
source install/setup.bash
export PYTHONPATH="$REPO:$PYTHONPATH"
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-44}
export GZ_PARTITION="themind_stress_$$"
BIN="$WS/install/themind_ros/lib/themind_ros"
PIDS=()
stop() { for p in "${PIDS[@]}"; do kill -INT "$p" 2>/dev/null || true; done; sleep 2;
         for p in "${PIDS[@]}"; do kill -9 "$p" 2>/dev/null || true; done; }
trap stop EXIT

gz sim -s -r "$HERE/sim/stress.sdf" > "$WS/gazebo.log" 2>&1 &
PIDS+=($!)
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
    -p reach_seconds:=5.0 -p state_seconds:=10.0 > "$WS/bridge.log" 2>&1 &
BRIDGE=$!
PIDS+=($BRIDGE)
# memory (kB) and CPU seconds of the bridge, every 15 real seconds
TICK=$(getconf CLK_TCK)
( while kill -0 $BRIDGE 2>/dev/null; do
    RSS=$(awk '/VmRSS/ {print $2}' /proc/$BRIDGE/status 2>/dev/null || echo 0)
    CPU=$(awk -v t="$TICK" '{print ($14 + $15) / t}' /proc/$BRIDGE/stat 2>/dev/null || echo 0)
    echo "$(date +%s) $RSS $CPU" >> "$WS/resources.log"; sleep 15
  done ) &
PIDS+=($!)
sleep 3
timeout $(( SECONDS_SIM / 2 + 600 )) $PY "$HERE/sim/stress_senses.py" --ros-args \
    -p use_sim_time:=true -p report:="$WS/report.json" -p seconds:="${SECONDS_SIM}.0" \
    -p seed:="$SEED" > "$WS/senses.log" 2>&1 \
    || { tail -n 20 "$WS/senses.log" "$WS/bridge.log" "$WS/gz_bridge.log"; exit 1; }
stop
trap - EXIT
$PY "$HERE/sim/check_stress.py" "$WS/mind" "$WS/report.json" "$WS/resources.log" \
    "$WS/bridge.log" "$WS/senses.log"
