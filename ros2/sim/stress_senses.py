"""The stress run's robot: hours of a random life, inside the physics simulation.

    python3 ros2/sim/stress_senses.py --ros-args -p use_sim_time:=true \
        -p report:=/tmp/r.json -p seconds:=7200 -p seed:=7

Seeded, so a run can be repeated exactly. Over the simulated hours it:
- drives between the kitchen and the garden, to random spots, at random times;
- brings Sam, Ana and Tom in front of the robot at random, and lets the robot
  drive away from them (the logical camera decides who is really there);
- talks: whoever is in view says something, and the robot answers once it has
  the mind's context, timing how long that took in real milliseconds;
- docks to recharge when the battery runs down, and undocks when it is full;
- once, for a simulated minute, behaves like a chatty perception stack that
  reports the same sighting five times a second.

It writes down everything that really happened (rooms, who was in view, the
battery's real level, every line said, every context and how long it took,
every state the mind published) so the run can be judged against the world.
"""
import json
import random
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
PEOPLE = {"sam": "Sam", "ana": "Ana", "tom": "Tom"}
BATTERY = "/model/robot/battery/linear_battery"


def zone(x):
    return "kitchen" if x < 0 else "garden"


class StressSenses(Node):
    def __init__(self):
        super().__init__("stress_senses")
        self.report_path = self.declare_parameter("report", "").value
        self.seconds = float(self.declare_parameter("seconds", 7200.0).value)
        self.rng = random.Random(int(self.declare_parameter("seed", 7).value))
        self.spawn_x = -4.0
        self.pub = {t: self.create_publisher(String, t, 10) for t in (
            "/themind/place", "/themind/present", "/themind/experience", "/themind/heard",
            "/themind/said")}
        self.drive = self.create_publisher(Twist, "/model/robot/cmd_vel", 10)
        self.create_subscription(Odometry, "/model/robot/odometry", self._on_odom, 10)
        self.create_subscription(LogicalCameraImage, "/robot/eyes", self._on_eyes, 10)
        self.create_subscription(BatteryState, BATTERY + "/state", self._on_battery, 10)
        self.create_subscription(String, "/themind/context", self._on_context, 10)
        self.create_subscription(String, "/themind/state", self._on_state, 10)
        self.x, self.place, self.present = None, None, []
        self.ready, self.t0, self.wall0 = False, None, time.time()
        self.target = None
        self.next_move = self.next_person = self.next_talk = 0.0
        self.burst_at = self.rng.uniform(0.3, 0.6) * self.seconds
        self.burst_until = None
        self.docked = False
        self.level = None
        self.asked = None        # (wall time, line) waiting for context
        self.n_said = 0
        self.r = {"zones": [], "present": [], "battery": [], "docks": [], "lines": [],
                  "contexts": [], "states": [], "seen": [], "burst": {"sent": 0},
                  "themind_publishes": None}
        self.create_timer(0.2, self._on_tick)

    def _now(self):
        return self.get_clock().now().nanoseconds / 1e9

    def _t(self):
        return round(self._now() - (self.t0 or self._now()), 2)

    def _send(self, topic, data):
        msg = String()
        msg.data = data if isinstance(data, str) else json.dumps(data)
        self.pub[topic].publish(msg)

    def _gz(self, args):
        threading.Thread(target=subprocess.run, daemon=True, args=(["gz"] + args,),
                         kwargs={"capture_output": True}).start()

    # ── the world, as the physics has it ─────────────────────────────────────
    def _on_odom(self, msg):
        self.x = self.spawn_x + msg.pose.pose.position.x
        if self.ready and zone(self.x) != self.place:
            self._arrive()

    def _arrive(self):
        self.place = zone(self.x)
        self.seen_here = set()
        self.r["zones"].append({"t": self._t(), "zone": self.place})
        self._send("/themind/place", self.place)

    def _on_eyes(self, msg):
        if not self.ready or self.place is None:
            return
        names = {m.name for m in msg.model}
        people = sorted(PEOPLE[n] for n in names if n in PEOPLE)
        if people != self.present:
            self.present = people
            self.r["present"].append({"t": self._t(), "who": people, "zone": self.place})
            self._send("/themind/present", people)
        for n in sorted(names):
            if n in THINGS and n not in self.seen_here:
                self.seen_here.add(n)
                self.r["seen"].append({"t": self._t(), "thing": n, "zone": self.place})
                self._send("/themind/experience", {"text": "I saw %s." % THINGS[n], "kind": "saw",
                                                   "source": "gazebo:/robot/eyes"})
        if self.burst_until is not None and self._t() < self.burst_until and self.place:
            # a chatty perception stack: the same sighting, every frame
            self._send("/themind/experience", {"text": "I see the floor in front of me.",
                                               "kind": "saw", "source": "chatty"})
            self.r["burst"]["sent"] += 1

    def _on_battery(self, msg):
        if msg.capacity <= 0 or not self.ready:
            return
        level = msg.charge / msg.capacity
        if self.level is None or abs(level - self.level) >= 0.02 or \
                (level <= 0.15) != (self.level <= 0.15) or (level > 0.35) != (self.level > 0.35):
            self.r["battery"].append({"t": self._t(), "level": round(level, 4),
                                      "zone": self.place})
            self.level = level
        if not self.docked and level <= 0.08:
            self.docked = True
            self.r["docks"].append({"t": self._t(), "dock": True, "zone": self.place})
            self._gz(["topic", "-t", BATTERY + "/recharge/start", "-m", "gz.msgs.Boolean",
                      "-p", "data: true"])
        elif self.docked and level >= 0.97:
            self.docked = False
            self.r["docks"].append({"t": self._t(), "dock": False, "zone": self.place})
            self._gz(["topic", "-t", BATTERY + "/recharge/stop", "-m", "gz.msgs.Boolean",
                      "-p", "data: true"])

    def _on_context(self, msg):
        data = json.loads(msg.data)
        waited = None
        if self.asked is not None:
            waited = round((time.time() - self.asked[0]) * 1000.0, 1)
            self.asked = None
        self.r["contexts"].append({"t": self._t(), "who": data.get("who"), "ms": waited,
                                   "chars": len(data.get("context") or ""),
                                   "context": data.get("context") or ""})
        self.n_said += 1
        self._send("/themind/said", "I hear you (%d)." % self.n_said)

    def _on_state(self, msg):
        data = json.loads(msg.data)
        self.r["states"].append({"t": self._t(), "wall": round(time.time() - self.wall0, 2),
                                 "where": data.get("where"), "present": data.get("present")})

    # ── a random life ────────────────────────────────────────────────────────
    def _on_tick(self):
        now = self._now()
        if now <= 0 or self.x is None:
            return
        if not self.ready:
            if any(p.get_subscription_count() == 0 for p in self.pub.values()):
                return
            self.ready = True
            self.t0 = now
            self._arrive()
            self.get_logger().info("the mind is listening; the stress run begins")
        t = self._t()
        if t >= self.next_move and not self.docked:
            self.target = self.rng.choice((self.rng.uniform(-4.5, -1.0),
                                           self.rng.uniform(1.0, 4.0)))
            self.next_move = t + self.rng.uniform(60, 360)
        cmd = Twist()
        if self.target is not None and not self.docked and abs(self.x - self.target) > 0.15:
            cmd.linear.x = 0.5 if self.target > self.x else -0.5
        self.drive.publish(cmd)
        if t >= self.next_person:
            name = self.rng.choice(sorted(PEOPLE))
            ahead = self.x + self.rng.uniform(1.2, 2.2)
            self._gz(["service", "-s", "/world/house/set_pose", "--reqtype", "gz.msgs.Pose",
                      "--reptype", "gz.msgs.Boolean", "--timeout", "3000", "--req",
                      'name: "%s", position: {x: %f, y: %f, z: 0.85}'
                      % (name, ahead, self.rng.uniform(-0.5, 0.5))])
            self.next_person = t + self.rng.uniform(45, 240)
        if t >= self.next_talk and self.present and self.asked is None:
            who = self.rng.choice(self.present)
            line = "%s here, line %d: how is it going?" % (who, len(self.r["lines"]) + 1)
            self.r["lines"].append({"t": t, "who": who, "zone": self.place,
                                    "present": list(self.present)})
            self.asked = (time.time(), line)
            self._send("/themind/heard", {"who": who, "text": line})
            self.next_talk = t + self.rng.uniform(30, 180)
        if self.burst_until is None and t >= self.burst_at:
            self.burst_until = t + 60.0
            self.r["burst"]["start"] = t
        if t >= self.seconds:
            self._finish()

    def _finish(self):
        try:
            names = self.get_publisher_names_and_types_by_node("themind", "/")
            self.r["themind_publishes"] = sorted(n for n, _types in names)
        except Exception as e:
            self.r["themind_publishes"] = "unknown: %s" % e
        self.r["sim_seconds"] = self._t()
        self.r["wall_seconds"] = round(time.time() - self.wall0, 1)
        if self.report_path:
            with open(self.report_path, "w", encoding="utf-8") as f:
                json.dump(self.r, f, indent=1)
        raise SystemExit(0)


def main(args=None):
    rclpy.init(args=args)
    node = StressSenses()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException, SystemExit):
        pass
    except Exception:
        if rclpy.ok():
            raise
    finally:
        try:
            node.destroy_node()
            if rclpy.ok():
                rclpy.shutdown()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
