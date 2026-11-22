"""After the physics simulation: did the mind live what really happened?

    python3 ros2/sim/check_sim.py <mind folder> <report.json> <log> [<log> ...]

The report is the world's own account (where the robot was when its battery
ran low, what was in view and when, who came and went, and which topics
theMind's node published). Every check compares the mind against that, not
against a script, and the logs must hold no error at all.
"""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from themind import Mind  # noqa: E402
from themind.envelope import valid_record  # noqa: E402

mind_dir, report_path, logs = sys.argv[1], sys.argv[2], sys.argv[3:]
mind = Mind(mind_dir, readonly=True)
world = json.load(open(report_path, encoding="utf-8"))
xs = mind.live("experiences")
failures = []


def check(cond, label):
    print(("PASS  " if cond else "FAIL  ") + label)
    if not cond:
        failures.append(label)


def first(text):
    return next((x for x in xs if x["text"] == text), None)


def secs(a, b):
    f = "%Y-%m-%dT%H:%M:%SZ"
    return (datetime.strptime(b, f) - datetime.strptime(a, f)).total_seconds()


places = json.load(open(os.path.join(mind_dir, "stores", "places.json")))["places"]
check([z["zone"] for z in world["zones"]] == ["kitchen", "garden"]
      and set(places) == {"kitchen", "garden"}
      and places["kitchen"]["first_t"] < places["garden"]["first_t"],
      "it knows the two rooms the robot really drove through, in the order it drove them")
for seen in world["seen"]:
    x = first("I saw %s." % {"kettle": "the kettle", "bench": "the bench",
                             "apple_tree": "the apple tree"}[seen["thing"]])
    check(x is not None and x.get("where") == seen["zone"]
          and x["src"]["ref"] == "gazebo:/robot/eyes",
          "what the camera really saw (%s) is remembered where it was seen (%s)"
          % (seen["thing"], seen["zone"]))
check(any(s["thing"] == "kettle" for s in world["seen"])
      and any(s["thing"] in ("bench", "apple_tree") for s in world["seen"]),
      "it saw something in each room")
came, left = first("Sam came in."), first("Sam left.")
check(came and left and came.get("where") == left.get("where") == "kitchen"
      and came.get("with") == [None] and came["t"] <= left["t"]
      and [p["who"] for p in world["present"]] == [["Sam"], []],
      "Sam coming in and leaving, as the camera saw it, in the kitchen")
low = first("My energy ran very low.")
check(world["battery_low"] is not None and low is not None
      and low.get("where") == world["battery_low"]["zone"] == "garden",
      "the battery ran low where the robot really was when it did (the garden)")
check(low is not None and int(low.get("times") or 1) == 1
      and first("My energy came back.") is None,
      "the battery only ever ran down, and the mind never thought it came back")
arrived = first("I arrived at the kitchen.")
sim_gap = world["battery_low"]["t"] - world["zones"][0]["t"] if world["battery_low"] else 0
mind_gap = secs(arrived["t"], low["t"]) if arrived and low else 0
check(arrived and low and abs(mind_gap - sim_gap) <= 3
      and world["wall_seconds"] < world["sim_seconds"] * 0.6,
      "the mind lived on simulated time: %.0f s between those moments, as the simulation had "
      "it, in %.0f s of real time" % (mind_gap, world["wall_seconds"]))
ctx = world.get("context") or {}
check(ctx.get("who") == "Sam" and "You are here: kitchen" in (ctx.get("context") or "")
      and "I saw the kettle." in ctx["context"] and world["replied"]
      and int(mind.manifest.state.get("exchanges") or 0) == 1,
      "the robot answered Sam with the mind's context: where it was, and what it had seen")
pubs = world.get("themind_publishes")
check(isinstance(pubs, list) and set(pubs) <= {"/themind/context", "/themind/reach",
                                               "/themind/state", "/rosout",
                                               "/parameter_events"}
      and "/themind/context" in pubs and not any("cmd_vel" in p for p in pubs),
      "theMind's node published only what it offers, and never a command: %s" % pubs)
records = [r for name in ("experiences", "facts", "reflections", "observations")
           for r in mind.stores[name].load()]
check(records and all(valid_record(r) for r in records)
      and all(x["src"]["kind"] == "sensed" for x in xs),
      "every record in the folder is valid, and every moment carries the body's own report")
bad = []
for path in logs:
    for line in open(path, encoding="utf-8", errors="replace"):
        if "Traceback" in line or "[ERROR]" in line or "Exception" in line:
            bad.append("%s: %s" % (os.path.basename(path), line.strip()[:160]))
check(not bad, "no errors in any log" + ("" if not bad else ": " + " | ".join(bad[:3])))
total = 10 + len(world["seen"])
print("\n%d of %d" % (total - len(failures), total))
sys.exit(1 if failures else 0)
