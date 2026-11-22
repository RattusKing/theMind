"""The rest of a robot, inside a physics simulation.

    python3 ros2/sim/sim_senses.py --ros-args -p use_sim_time:=true -p report:=/tmp/r.json

A real robot has nodes that work out where it is, what it sees, who is in the
room, and what was said to it. In Gazebo this node stands in for them, from
what the physics actually does: the wheel odometry says which room the robot
is in, the logical camera says what is in front of it, and the battery drains
on its own. It also drives the robot through the doorway, brings Sam into the
kitchen and out again, and holds one conversation.

At the end it writes down what really happened, so the mind can be checked
against the world rather than against a script: where the robot was when the
battery ran low, what was in view and when, and which topics theMind's node
published.
"""
import json
import subprocess
import threading
import time

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from ros_gz_interfaces.msg import LogicalCameraImage
from sensor_msgs.msg import BatteryState
from std_msgs.msg import String

THINGS = {"kettle": "the kettle", "bench": "the bench", "apple_tree": "the apple tree"}
PEOPLE = {"sam": "Sam"}
SAM_IN = (-2.2, -0.4)     # in front of the robot, in the kitchen, well inside its view
SAM_OUT = (-30.0, 0.0)
GARDEN_STOP = 3.6         # metres past the doorway's line, x


def zone(x):
    return "kitchen" if x < 0 else "garden"


class SimSenses(Node):
    def __init__(self):
        super().__init__("sim_senses")
        self.report_path = self.declare_parameter("report", "").value
        self.spawn_x = float(self.declare_parameter("spawn_x", -4.0).value)
        self.duration = float(self.declare_parameter("duration", 75.0).value)
        self.world = self.declare_parameter("world", "house").value
        self.pub = {t: self.create_publisher(String, t, 10) for t in (
            "/themind/place", "/themind/present", "/themind/experience", "/themind/heard",
            "/themind/said")}
        self.drive = self.create_publisher(Twist, "/model/robot/cmd_vel", 10)
        self.create_subscription(Odometry, "/model/robot/odometry", self._on_odom, 10)
        self.create_subscription(LogicalCameraImage, "/robot/eyes", self._on_eyes, 10)
        self.create_subscription(BatteryState, "/model/robot/battery/linear_battery/state",
                                 self._on_battery, 10)
        self.create_subscription(String, "/themind/context", self._on_context, 10)
        self.x = None
        self.ready = False     # nothing is said until the mind is listening
        self.place = None
        self.present = []
        self.seen_here = set()
        self.t0 = None
        self.wall0 = time.time()
        self.stage = 0
        self.driving = False
        self.report = {"zones": [], "seen": [], "present": [], "battery_low": None,
                       "context": None, "replied": False, "themind_publishes": None}
        self.create_timer(0.1, self._on_tick)

    # ── the world, as the physics has it ─────────────────────────────────────
    def _now(self):
        return self.get_clock().now().nanoseconds / 1e9

    def _send(self, topic, data):
        msg = String()
        msg.data = data if isinstance(data, str) else json.dumps(data)
        self.pub[topic].publish(msg)

    def _on_odom(self, msg):
        self.x = self.spawn_x + msg.pose.pose.position.x
        here = zone(self.x)
        if self.ready and here != self.place:
            self.place = here
            self.seen_here = set()
            self.report["zones"].append({"t": self._now(), "zone": here})
            self._send("/themind/place", here)

    def _on_odom_place(self):
        self.place = zone(self.x)
        self.seen_here = set()
        self.report["zones"].append({"t": self._now(), "zone": self.place})
        self._send("/themind/place", self.place)

    def _on_eyes(self, msg):
        if not self.ready or self.place is None:
            return
        names = {m.name for m in msg.model}
        people = sorted(PEOPLE[n] for n in names if n in PEOPLE)
        if people != self.present:
            self.get_logger().info("in view: %s" % people)
            self.present = people
            self.report["present"].append({"t": self._now(), "who": people, "zone": self.place})
            self._send("/themind/present", people)
        for n in sorted(names):
            if n in THINGS and n not in self.seen_here and self.place:
                self.seen_here.add(n)
                self.report["seen"].append({"t": self._now(), "thing": n, "zone": self.place})
                self._send("/themind/experience", {"text": "I saw %s." % THINGS[n], "kind": "saw",
                                                   "source": "gazebo:/robot/eyes"})

    def _on_battery(self, msg):
        if self.report["battery_low"] is None and msg.capacity > 0:
            level = msg.charge / msg.capacity
            if level <= 0.15:
                self.report["battery_low"] = {"t": self._now(), "x": self.x,
                                              "zone": self.place, "level": level}

    def _on_context(self, msg):
        data = json.loads(msg.data)
        self.report["context"] = data
        self._send("/themind/said", "Good luck at the bakery today, Sam.")
        self.report["replied"] = True

    # ── the morning ──────────────────────────────────────────────────────────
    def _teleport(self, name, xy):
        req = 'name: "%s", position: {x: %f, y: %f, z: 0.85}' % (name, xy[0], xy[1])
        cmd = ["gz", "service", "-s", "/world/%s/set_pose" % self.world, "--reqtype",
               "gz.msgs.Pose", "--reptype", "gz.msgs.Boolean", "--timeout", "3000", "--req", req]

        def run():
            out = subprocess.run(cmd, capture_output=True, text=True)
            ok = out.returncode == 0 and "true" in out.stdout
            (self.get_logger().info if ok else self.get_logger().warning)(
                "moved %s to %s: %s" % (name, xy, "done" if ok else
                                         (out.stdout + out.stderr).strip()[:200]))
        threading.Thread(target=run, daemon=True).start()

    def _on_tick(self):
        now = self._now()
        if now <= 0 or self.x is None:
            return
        if not self.ready:
            # A morning nobody is listening to is lost: wait for the mind.
            if any(p.get_subscription_count() == 0 for p in self.pub.values()):
                return
            self.ready = True
            self.get_logger().info("the mind is listening; the morning begins")
            self._on_odom_place()
        if self.t0 is None:
            self.t0 = now
        t = now - self.t0
        if self.stage == 0 and t >= 4:
            self._teleport("sam", SAM_IN)
            self.stage = 1
        elif self.stage == 1 and t >= 7 and self.present == ["Sam"]:
            self._send("/themind/heard", {"who": "Sam",
                                          "text": "Morning! I start at the bakery today."})
            self.stage = 2
        elif self.stage == 2 and t >= 14:
            self._teleport("sam", SAM_OUT)
            self.stage = 3
        elif self.stage == 3 and t >= 17:
            self.driving = True
            self.stage = 4
            self.get_logger().info("driving to the garden from x=%.2f" % self.x)
        if self.driving:
            cmd = Twist()
            if self.x < GARDEN_STOP:
                cmd.linear.x = 0.4
            else:
                self.driving = False
            self.drive.publish(cmd)
        if t >= self.duration:
            self._finish(now)

    def _finish(self, now):
        try:
            names = self.get_publisher_names_and_types_by_node("themind", "/")
            self.report["themind_publishes"] = sorted(n for n, _types in names)
        except Exception as e:
            self.report["themind_publishes"] = "unknown: %s" % e
        self.report["sim_seconds"] = now - (self.t0 or now)
        self.report["wall_seconds"] = time.time() - self.wall0
        if self.report_path:
            with open(self.report_path, "w", encoding="utf-8") as f:
                json.dump(self.report, f, indent=1)
        raise SystemExit(0)


def main(args=None):
    rclpy.init(args=args)
    node = SimSenses()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException, SystemExit):
        pass
    except Exception:
        if rclpy.ok():
            raise   # a real failure, not the context closing under it at Ctrl-C
    finally:
        try:
            node.destroy_node()
            if rclpy.ok():
                rclpy.shutdown()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
