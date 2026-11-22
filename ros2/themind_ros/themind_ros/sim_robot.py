"""A simulated robot: one scripted morning, for trying the bridge without one.

    ros2 run themind_ros sim_robot

It does what a real robot's own nodes would: reports its battery, where it
is and who is in the room, says what happens, and holds one conversation,
waiting for the mind's context before it answers. Its replies are scripted;
a real robot's would come from its own model, with the context added to its
system prompt. With `-p report:=/path/file.json` it writes down what it got
back, so the bridge can be checked end to end.
"""
import json

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import BatteryState
from std_msgs.msg import String

# (seconds after start, topic, payload). The battery is its own message type.
MORNING = [
    (1.0, "battery", 0.9),
    (1.5, "/themind/place", "kitchen"),
    (2.0, "/themind/experience", {"text": "The kettle whistled.", "kind": "heard",
                                  "source": "microphone"}),
    (3.0, "/themind/present", ["Sam"]),
    (4.0, "/themind/heard", {"who": "Sam", "text": "Morning! I start my new job at the "
                                                   "bakery today and I'm nervous."}),
    (7.0, "/themind/place", "garden"),
    (7.5, "/themind/experience", {"text": "Frost on the garden path.", "kind": "saw",
                                  "source": "camera"}),
    (8.0, "battery", 0.12),
    (9.0, "/themind/present", []),
    (10.0, "battery", 0.95),
]
REPLY = "Good luck at the bakery today. You'll be great."
DONE_AT = 12.0


class SimRobot(Node):
    def __init__(self):
        super().__init__("sim_robot")
        self.report_path = self.declare_parameter("report", "").value
        self.pubs = {}
        self.battery = self.create_publisher(BatteryState, "/battery_state",
                                             qos_profile_sensor_data)
        self.said = self.create_publisher(String, "/themind/said", 10)
        self.create_subscription(String, "/themind/context", self._on_context, 10)
        self.create_subscription(String, "/themind/state", self._on_state, 10)
        self.got = {"context": None, "states": [], "replied": False}
        for _at, topic, _payload in MORNING:
            if topic != "battery":
                self._pub(topic)
        self.t = 0.0
        self.step = 0
        self.started = False
        self.create_timer(0.25, self._on_tick)

    def _pub(self, topic):
        if topic not in self.pubs:
            self.pubs[topic] = self.create_publisher(String, topic, 10)
        return self.pubs[topic]

    def _on_tick(self):
        if not self.started:
            # A morning nobody is listening to is lost: wait for the mind.
            listening = [self.battery] + list(self.pubs.values())
            if any(p.get_subscription_count() == 0 for p in listening):
                return
            self.started = True
            self.get_logger().info("the mind is listening; the morning begins")
        self.t += 0.25
        while self.step < len(MORNING) and MORNING[self.step][0] <= self.t:
            _at, topic, payload = MORNING[self.step]
            self.step += 1
            if topic == "battery":
                msg = BatteryState()
                msg.percentage = float(payload)
                self.battery.publish(msg)
            else:
                msg = String()
                msg.data = payload if isinstance(payload, str) else json.dumps(payload)
                self._pub(topic).publish(msg)
            self.get_logger().info("%s: %s" % (topic, payload))
        if self.t >= DONE_AT:
            self._finish()

    def _on_context(self, msg):
        # The robot's dialogue would add this to its system prompt and answer
        # with its own model; the simulation answers with a scripted line.
        data = json.loads(msg.data)
        self.got["context"] = data
        reply = String()
        reply.data = REPLY
        self.said.publish(reply)
        self.got["replied"] = True
        self.get_logger().info("answered %s, with the mind's context in hand" % data.get("who"))

    def _on_state(self, msg):
        self.got["states"].append(json.loads(msg.data))

    def _finish(self):
        if self.report_path:
            with open(self.report_path, "w", encoding="utf-8") as f:
                json.dump(self.got, f, ensure_ascii=False, indent=1)
        raise SystemExit(0)


def main(args=None):
    rclpy.init(args=args)
    node = SimRobot()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException, SystemExit):
        pass
    except Exception:
        if rclpy.ok():
            raise   # a real failure, not the context closing under it at Ctrl-C
    finally:
        try:   # a second Ctrl-C (launch sends one too) must not break the goodbye
            node.destroy_node()
            if rclpy.ok():
                rclpy.shutdown()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
