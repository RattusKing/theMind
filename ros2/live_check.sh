#!/usr/bin/env bash
# End to end on real ROS 2: build the package, run the bridge beside the
# simulated robot, and check what the mind came away with.
#   ros2/live_check.sh            (with ROS 2 installed; PYTHON=python3.12 if needed)
set -eo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/.." && pwd)
PY=${PYTHON:-python3}
WS=$(mktemp -d)
mkdir -p "$WS/src" && cp -r "$HERE/themind_ros" "$WS/src/"
source "/opt/ros/${ROS_DISTRO:-jazzy}/setup.bash"
cd "$WS"
$PY -m colcon build > "$WS/build.log" 2>&1 || { cat "$WS/build.log"; exit 1; }
source install/setup.bash
export PYTHONPATH="$REPO:$PYTHONPATH"
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-42}
# The nodes run directly, not through `ros2 run`, so an interrupt reaches them.
BIN="$WS/install/themind_ros/lib/themind_ros"
$PY "$BIN/bridge" --ros-args -p mind:="$WS/mind" -p api_port:=0 \
    -p reach_seconds:=1.0 -p state_seconds:=2.0 > "$WS/bridge.log" 2>&1 &
BRIDGE=$!
timeout 90 $PY "$BIN/sim_robot" --ros-args -p report:="$WS/report.json" \
    > "$WS/sim.log" 2>&1 || { cat "$WS/sim.log" "$WS/bridge.log"; kill -9 $BRIDGE; exit 1; }
kill -INT $BRIDGE
for _ in 1 2 3 4 5 6 7 8 9 10; do kill -0 $BRIDGE 2>/dev/null || break; sleep 1; done
kill -9 $BRIDGE 2>/dev/null || true
$PY "$HERE/check_morning.py" "$WS/mind" "$WS/report.json" || { cat "$WS/bridge.log"; exit 1; }
