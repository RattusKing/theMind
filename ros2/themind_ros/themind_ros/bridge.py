"""The ROS 2 node: a robot's senses in, a mind of its own beside it.

    ros2 run themind_ros bridge --ros-args -p mind:=/home/robot/mind

It listens, and it never commands anything. Nothing it publishes moves the
robot: it offers context to the robot's own dialogue, and says when there is
something the mind would bring up first. What the robot does stays the
robot's.

Topics it listens to (all std_msgs/String unless said otherwise):

    /battery_state        sensor_msgs/BatteryState   its energy
    /themind/body         {"energy", "heat", "strain", "damage"}, each 0..1
    /themind/place        where it is now, by name
    /themind/present      who is in the room: ["Sam", "Ana"] or "Sam, Ana"
    /themind/experience   a moment: plain words, or {"text", "kind", "where", ...}
    /themind/heard        what someone said to it: plain words, or {"who", "text"}
    /themind/said         what it said aloud: plain words, or {"text", "reach_id"}

Topics it publishes (std_msgs/String, JSON):

    /themind/context      after something is heard: {"who", "heard", "context"},
                          the inner context for the robot's reply
    /themind/reach        something it would bring up first, to the one person
                          in the room: {"id", "text", "kind", "who", "messages"}
    /themind/state        now and then: {"where", "present", "body", "stage"}

It also serves the web API and the MCP door on `api_port` (default 6464), on
the same mind, so anything else on the robot can reach it over HTTP.

With `use_sim_time:=true` (as in a Gazebo simulation) the mind lives on the
simulation's clock, at whatever pace it runs.

Parameters: `mind` (the folder), `api_port` (0 turns it off), `api_token`,
`model_base_url` and `model` (an OpenAI-compatible endpoint the mind may
think with, such as a local Ollama; the key, if any, is read from
THEMIND_MODEL_KEY or OPENAI_API_KEY and kept in memory only), `think_seconds`,
`reach_seconds`, `state_seconds`, and `battery_topic`. With no model, the
mind still lives through everything; its thinking is then handed out over the
web API, for whatever model the robot has.
"""
import json
import os
import threading
import urllib.request
from datetime import datetime, timedelta, timezone

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import BatteryState
from std_msgs.msg import String

from themind import Mind
from themind.envelope import set_clock

from .senses import Senses


def openai_llm(base_url, model):
    """The mind's one bridge to a model: an OpenAI-compatible endpoint. The
    key, if the endpoint needs one, comes from the environment and never
    touches the mind's folder."""
    key = os.environ.get("THEMIND_MODEL_KEY") or os.environ.get("OPENAI_API_KEY")
    url = base_url.rstrip("/") + "/chat/completions"

    def llm(system, user, max_tokens):
        body = json.dumps({"model": model, "max_tokens": max_tokens, "stream": False,
                           "messages": [{"role": "system", "content": system},
                                        {"role": "user", "content": user}]}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = "Bearer " + key
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"].get("content") or ""
    return llm


class Bridge(Node):
    def __init__(self):
        super().__init__("themind")
        p = {name: self.declare_parameter(name, default).value for name, default in (
            ("mind", os.path.expanduser("~/themind-mind")), ("api_port", 6464),
            ("api_token", ""), ("model_base_url", ""), ("model", ""),
            ("think_seconds", 300.0), ("reach_seconds", 60.0), ("state_seconds", 10.0),
            ("battery_topic", "/battery_state"))}
        llm = openai_llm(p["model_base_url"], p["model"]) \
            if p["model_base_url"] and p["model"] else None
        # In a simulation the robot lives on simulated time, so the mind must
        # too: ages, freshness, how much an hour may add, when a rhythm is due.
        self._anchor = None
        self.sim_time = bool(self.get_parameter("use_sim_time").value)
        if self.sim_time:
            set_clock(self._sim_now)
        self.mind = Mind(p["mind"], llm=llm)
        self.senses = Senses(self.mind)
        self._thinking = threading.Lock()
        self.server = None
        if int(p["api_port"] or 0) > 0:
            from themind import mcp
            self.server = mcp.serve(mind=self.mind, port=int(p["api_port"]),
                                    token=p["api_token"] or None)
            threading.Thread(target=self.server.serve_forever, daemon=True).start()

        self.create_subscription(BatteryState, p["battery_topic"], self._on_battery,
                                 qos_profile_sensor_data)
        for topic, fn in (("/themind/body", self._on_body), ("/themind/place", self._on_place),
                          ("/themind/present", self._on_present),
                          ("/themind/experience", self._on_experience),
                          ("/themind/heard", self._on_heard), ("/themind/said", self._on_said)):
            self.create_subscription(String, topic, fn, 10)
        self.context_pub = self.create_publisher(String, "/themind/context", 10)
        self.reach_pub = self.create_publisher(String, "/themind/reach", 10)
        self.state_pub = self.create_publisher(String, "/themind/state", 10)
        if float(p["think_seconds"]) > 0 and llm is not None:
            self.create_timer(float(p["think_seconds"]), self._on_think)
        if float(p["reach_seconds"]) > 0:
            self.create_timer(float(p["reach_seconds"]), self._on_reach)
        if float(p["state_seconds"]) > 0:
            self.create_timer(float(p["state_seconds"]), self._on_state)
        self.get_logger().info("theMind is listening (mind: %s%s; %s)" % (
            p["mind"], ", web API on port %d" % int(p["api_port"]) if self.server else "",
            "thinking with %s" % p["model"] if llm else "no model: its thinking is handed "
            "out over the web API"))

    def _publish(self, pub, data):
        msg = String()
        msg.data = json.dumps(data, ensure_ascii=False)
        pub.publish(msg)

    # ── senses ───────────────────────────────────────────────────────────────
    def _on_battery(self, msg):
        self.senses.battery(msg.percentage, msg.charge, msg.capacity)

    def _on_body(self, msg):
        self.senses.body(msg.data)

    def _on_place(self, msg):
        self.senses.place(msg.data)

    def _on_present(self, msg):
        self.senses.people(msg.data)

    def _on_experience(self, msg):
        if not self.senses.experience(msg.data):
            self.get_logger().debug("not kept: %r" % (msg.data[:80],))

    # ── talking ──────────────────────────────────────────────────────────────
    def _on_heard(self, msg):
        out = self.senses.hear(msg.data)
        if out is not None:
            self._publish(self.context_pub, out)

    def _on_said(self, msg):
        self.senses.said(msg.data)

    def _on_reach(self):
        offer = self.senses.reach()
        if offer is not None:
            self._publish(self.reach_pub, offer)

    def _on_state(self):
        self._publish(self.state_pub, self.senses.state())

    # ── its own heartbeat ────────────────────────────────────────────────────
    def _on_think(self):
        """One owed thought, off the executor so the senses keep flowing."""
        if not self._thinking.acquire(blocking=False):
            return

        def run():
            try:
                self.mind.step()
            except Exception:
                pass
            finally:
                self._thinking.release()
        threading.Thread(target=run, daemon=True).start()

    def _sim_now(self):
        """Simulated time, as a moment the mind can live in: anchored to the
        real clock when the first simulated tick arrives, then running at
        whatever pace the simulation runs. Before the first tick, None, and
        the real clock stands in."""
        ns = self.get_clock().now().nanoseconds
        if ns <= 0:
            return None
        if self._anchor is None:
            self._anchor = (ns, datetime.now(timezone.utc))
        ns0, wall0 = self._anchor
        return wall0 + timedelta(microseconds=(ns - ns0) / 1000.0)

    def destroy_node(self):
        if self.sim_time:
            set_clock(None)
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = Bridge()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
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
