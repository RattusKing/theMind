"""After the simulated robot's morning: did the mind live it, as it happened?

    python3 ros2/check_morning.py <mind folder> <the robot's report.json>

Used by ros2/live_check.sh. Exits non-zero, saying what was missing, if the
mind did not come away with the morning the robot actually had.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from themind import Mind  # noqa: E402

mind_dir, report_path = sys.argv[1], sys.argv[2]
mind = Mind(mind_dir, readonly=True)
report = json.load(open(report_path, encoding="utf-8"))
xs = mind.live("experiences")
by_text = {x["text"]: x for x in xs}
failures = []


def check(cond, label):
    print(("PASS  " if cond else "FAIL  ") + label)
    if not cond:
        failures.append(label)


check(set(by_text) >= {"I arrived at the kitchen.", "The kettle whistled.", "Sam came in.",
                       "I arrived at the garden.", "Frost on the garden path.",
                       "My energy ran very low.", "Sam left.", "My energy came back."},
      "every moment of the morning was lived")
check(by_text.get("The kettle whistled.", {}).get("where") == "kitchen"
      and by_text["The kettle whistled."]["src"] == {"kind": "sensed",
                                                     "quote": "The kettle whistled.",
                                                     "ref": "microphone"},
      "a moment keeps where it happened and the sense that reported it")
check(by_text.get("My energy ran very low.", {}).get("where") == "garden"
      and by_text["My energy ran very low."]["src"]["quote"] == "energy 0.12",
      "the battery running low was lived where it happened, with the reading as evidence")
check(by_text.get("Sam came in.", {}).get("with") == [None]
      and mind.people.primary_name == "Sam",
      "the first person it was ever with became the one it knows")
check(int(mind.manifest.state.get("exchanges") or 0) == 1,
      "the one conversation counted as having happened")
ctx = (report.get("context") or {})
check(ctx.get("who") == "Sam" and "INNER CONTEXT" in (ctx.get("context") or "")
      and "You are here: kitchen" in ctx["context"] and "The kettle whistled." in ctx["context"],
      "the robot's dialogue got the mind's context, knowing where it was and what had happened")
check(report.get("replied") is True, "the robot answered with that context in hand")
places = set(json.load(open(os.path.join(mind_dir, "stores", "places.json")))["places"])
check(places == {"kitchen", "garden"}, "it knows both places it was in")
wheres = [s.get("where") for s in report.get("states") or []]
check("kitchen" in wheres and "garden" in wheres and any(
    b.get("signal") == "energy" for s in report["states"] for b in s.get("body") or []),
      "its state was published for anyone watching, as it moved and as its body changed")
print("\n%d of %d" % (9 - len(failures), 9))
sys.exit(1 if failures else 0)
