"""After the stress run: what held, what didn't, and how it ran.

    python3 ros2/sim/check_stress.py <mind> <report.json> <resources.log> <log> [...]

Hours of a random life can't be checked line by line, so this checks what
must always hold, judged against the world's own record, and measures how
it ran: how long the robot's dialogue waited for context, whether that grew,
what memory and CPU the bridge used, and how big the mind became.
"""
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from themind import Mind  # noqa: E402
from themind.envelope import valid_record  # noqa: E402

mind_dir, report_path, res_path, logs = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
mind = Mind(mind_dir, readonly=True)
w = json.load(open(report_path, encoding="utf-8"))
xs = mind.live("experiences")
archived = mind.stores["experiences"].load() and \
    [json.loads(l) for l in open(os.path.join(mind_dir, "archive", "experiences.jsonl"))
     if l.strip()] if os.path.exists(os.path.join(mind_dir, "archive", "experiences.jsonl")) else []
everything = xs + archived
failures = []


def check(cond, label):
    print(("PASS  " if cond else "FAIL  ") + label)
    if not cond:
        failures.append(label)


def times(text):
    return sum(int(x.get("times") or 1) for x in everything if x["text"] == text)


print("the run: %.0f simulated seconds in %.0f real seconds (%.1fx)\n"
      % (w["sim_seconds"], w["wall_seconds"], w["sim_seconds"] / max(1.0, w["wall_seconds"])))

# it stayed alive and kept up
states = w["states"]
gaps = [b["t"] - a["t"] for a, b in zip(states, states[1:])]
check(states and states[-1]["t"] >= w["sim_seconds"] - 30 and (max(gaps) if gaps else 99) <= 30,
      "the bridge stayed alive and kept publishing its state to the end (longest gap %.0f "
      "simulated s, %d states)" % (max(gaps) if gaps else -1, len(states)))
bad = []
for path in logs:
    for line in open(path, encoding="utf-8", errors="replace"):
        if "Traceback" in line or "[ERROR]" in line or "Exception" in line:
            bad.append("%s: %s" % (os.path.basename(path), line.strip()[:140]))
check(not bad, "no errors in any log" + ("" if not bad else " (%d): %s" % (len(bad), bad[0])))
pubs = w.get("themind_publishes")
check(isinstance(pubs, list) and not any("cmd_vel" in p for p in pubs)
      and set(pubs) <= {"/themind/context", "/themind/reach", "/themind/state", "/rosout",
                        "/parameter_events"},
      "it published nothing but what it offers, never a command")

# the folder
recs = [r for name in mind.stores for r in mind.stores[name].load()]
check(all(valid_record(r) for r in recs) and all(x["src"]["kind"] == "sensed" for x in xs)
      and len(xs) <= 500,
      "every record valid, every moment with its sensor evidence, %d moments held (%d faded "
      "to the archive)" % (len(xs), len(archived)))

# rooms, against the world
places = json.load(open(os.path.join(mind_dir, "stores", "places.json")))["places"]
real = {z: sum(1 for e in w["zones"] if e["zone"] == z) for z in ("kitchen", "garden")}
held = {z: int((places.get(z) or {}).get("visits") or 0) for z in ("kitchen", "garden")}
check(real == held, "rooms: the robot really entered them %s times; the mind counts %s" % (real, held))

# people, against the camera
for key, name in (("sam", "Sam"), ("ana", "Ana"), ("tom", "Tom")):
    entered = sum(1 for a, b in zip([{"who": []}] + w["present"], w["present"])
                  if name in b["who"] and name not in a["who"])
    check(times("%s came in." % name) == entered,
          "%s came into view %d times; the mind lived it %d times"
          % (name, entered, times("%s came in." % name)))

# talking, and how long the dialogue waited
ctxs = w["contexts"]
check(len(ctxs) == len(w["lines"]) and len(ctxs) > 0,
      "every one of the %d things said got the mind's context back (%d)" % (len(w["lines"]), len(ctxs)))
ms = [c["ms"] for c in ctxs if c["ms"] is not None]
if ms:
    q = max(1, len(ms) // 4)
    early, late = statistics.median(ms[:q]), statistics.median(ms[-q:])
    p95 = sorted(ms)[int(0.95 * (len(ms) - 1))]
    check(p95 < 1000 and late < max(3 * early, early + 100),
          "context came back in %.0f ms typically, %.0f ms at the 95th percentile, %.0f ms at "
          "worst; early in the run %.0f ms, late %.0f ms"
          % (statistics.median(ms), p95, max(ms), early, late))

# privacy, in the contexts actually sent
def key_of(name):
    return mind.people.resolve(name)
leaks = []
for c in ctxs:
    k = key_of(c["who"])
    mine = {x["text"] for x in everything if not x.get("with") or k in x["with"]}
    theirs = {x["text"] for x in everything if x.get("with") and k not in x["with"]} - mine
    leaks += [(c["who"], t) for t in theirs if t in c["context"]]
check(not leaks, "no context ever carried a moment its speaker wasn't there for"
      + ("" if not leaks else ": %s" % (leaks[:2],)))

# the battery, against its real level
lv = [b["level"] for b in w["battery"]]
lows = sum(1 for a, b in zip(lv, lv[1:]) if a > 0.15 >= b)
backs, down = 0, False
for v in lv:
    if v <= 0.15:
        down = True
    elif v > 0.35 and down:
        backs, down = backs + 1, False
check(times("My energy ran very low.") == lows,
      "the battery really ran low %d times; the mind lived it %d times"
      % (lows, times("My energy ran very low.")))
check(times("My energy came back.") == backs,
      "the battery really came back %d times; the mind lived it %d times"
      % (backs, times("My energy came back.")))

# a chatty perception stack
chatty = [x for x in everything if x["text"] == "I see the floor in front of me."]
check(chatty and len(chatty) <= 4 and sum(int(x.get("times") or 1) for x in chatty)
      >= 0.95 * w["burst"]["sent"],
      "a perception stack repeating itself %d times in a simulated minute became %d moment(s), "
      "strengthened %d times, and nothing was lost"
      % (w["burst"]["sent"], len(chatty), sum(int(x.get("times") or 1) for x in chatty)))

# resources
rows = [l.split() for l in open(res_path) if l.strip()]
if rows:
    rss = [int(r[1]) for r in rows]
    cpu = float(rows[-1][2]) - float(rows[0][2])
    span = float(rows[-1][0]) - float(rows[0][0])
    print("\nthe bridge: memory %.1f MB at the start, %.1f MB at the end, %.1f MB at most; "
          "%.1f s of CPU over %.0f s (%.0f%% of one core)"
          % (rss[0] / 1024, rss[-1] / 1024, max(rss) / 1024, cpu, span,
             100 * cpu / max(1.0, span)))
size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _d, fs in os.walk(mind_dir) for f in fs)
print("the mind's folder: %.1f KB" % (size / 1024))
print("\n%d checks failed" % len(failures) if failures else "\nall checks held")
sys.exit(1 if failures else 0)
