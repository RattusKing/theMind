# theMind for ROS 2

A robot's senses in, a mind of its own beside it. This package is a ROS 2 node
(`bridge`) that listens to what your robot's other nodes report (its battery,
where it is, who is in the room, what happens, what is said to it) and turns
it into what its mind lives through. It is tested on ROS 2 Jazzy.

**It never commands anything.** Nothing it publishes moves the robot. It offers
context to your robot's own dialogue, and says when there is something the mind
would bring up first. What the robot does stays your code's.

## Install

theMind itself is plain Python with no dependencies. Install it for the Python
your ROS 2 uses:

```
pip install --break-system-packages git+https://github.com/RattusKing/theMind.git
```

(or put a clone on `PYTHONPATH`). Then put this package in your workspace and
build it:

```
cd ~/ros2_ws/src
git clone https://github.com/RattusKing/theMind.git
cp -r theMind/ros2/themind_ros .
cd ~/ros2_ws && colcon build --packages-select themind_ros
source install/setup.bash
```

## Run

```
ros2 run themind_ros bridge --ros-args -p mind:=/home/robot/mind
# or
ros2 launch themind_ros themind.launch.py mind:=/home/robot/mind
```

To let the mind think with a model on the robot, give it any OpenAI-compatible
endpoint, such as a local Ollama:

```
ros2 launch themind_ros themind.launch.py mind:=/home/robot/mind \
    model_base_url:=http://localhost:11434/v1 model:=<your model's name>
```

If the endpoint needs a key, set `THEMIND_MODEL_KEY` (or `OPENAI_API_KEY`) in
the node's environment. It is held in memory and never written to the mind.
Without a model the mind still lives through everything, and its thinking is
handed out over the web API for whatever model your robot has.

## What it listens to

All `std_msgs/String` except the battery.

| Topic | What to send |
| --- | --- |
| `/battery_state` | `sensor_msgs/BatteryState` (its `percentage`) |
| `/themind/body` | `{"energy": 0.4, "heat": 0.7, "strain": 0.2, "damage": 0}`, each 0 to 1 |
| `/themind/place` | where it is now, by name: `kitchen` |
| `/themind/present` | who is in the room: `["Sam", "Ana"]` or `Sam, Ana` |
| `/themind/experience` | a moment: `The kettle whistled.`, or `{"text", "kind", "where", "with", "source", "intensity"}` |
| `/themind/heard` | what someone said to it: plain words, or `{"who": "Sam", "text": "..."}` |
| `/themind/said` | what it said aloud: plain words, or `{"text": "...", "reach_id": "..."}` |

Moments are tagged with where it is and who is there, unless they say
otherwise. A moment that says where it happened tells the bridge where the
body is. Someone coming into the room, or leaving, is a moment of its own.
What happened around someone is only ever brought up with the people who were
there.

## What it publishes

| Topic | When | What |
| --- | --- | --- |
| `/themind/context` | after something is heard | `{"who", "heard", "context"}`: add `context` to your dialogue's system prompt before it answers |
| `/themind/reach` | when there is exactly one person in the room and something real to raise | `{"id", "text", "kind", "who", "messages"}`: say it if you choose, then publish what you said on `/themind/said` with its `reach_id` |
| `/themind/state` | every few seconds | `{"where", "present", "body", "stage"}` |

## The conversation loop

1. Your speech recognizer publishes what it heard on `/themind/heard`, naming
   the speaker if it knows. A speaker nobody names is taken to be the person
   the mind usually talks with. It never guesses.
2. The bridge publishes the mind's context on `/themind/context`.
3. Your dialogue node answers with its own model and persona, with that
   context added to its system prompt.
4. It publishes what the robot said on `/themind/said`. The mind learns from
   the exchange.

## Parameters

| Name | Default | |
| --- | --- | --- |
| `mind` | `~/themind-mind` | the mind's folder |
| `api_port` | `6464` | the web API and MCP door, on the same mind (0 turns it off) |
| `api_token` | | require a secret on the web API |
| `model_base_url`, `model` | | an OpenAI-compatible endpoint it may think with |
| `think_seconds` | `300` | its heartbeat: one owed thought this often, when it has a model |
| `reach_seconds` | `60` | how often it checks for something to bring up first |
| `state_seconds` | `10` | how often it publishes its state |
| `battery_topic` | `/battery_state` | where your battery reports |

## Try it without a robot

A simulated robot lives one scripted morning: the kitchen, a kettle, Sam coming
in to say he starts at the bakery today, the garden, frost, a battery running
low and coming back.

```
ros2 run themind_ros bridge --ros-args -p mind:=/tmp/sim-mind     # in one terminal
ros2 run themind_ros sim_robot                                   # in another
python3 -m themind show /tmp/sim-mind                            # what it lived
```

`ros2/live_check.sh` in the repository does all of that and checks the result.
It runs on every change, on ROS 2 Jazzy.

## The two halves

`senses.py` turns plain values into calls on the mind and knows nothing about
ROS, so it can be used under any robot framework. `bridge.py` is the thin ROS 2
node around it.
