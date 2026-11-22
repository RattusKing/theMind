"""The web API: the mind over plain HTTP and JSON, for any language on any device (v1.11).

    python3 -m themind.api --mind ./my-mind     # http://127.0.0.1:6464/api

Anything that can send a web request can have a mind now: a JavaScript app,
a game engine, a robot's control loop, a ChatGPT custom GPT (point its
Actions at /api/openapi.json). It is the same server as the MCP door, on
the same port with the same secret, so one process serves an AI platform at
/mcp and everything else at /api, both on one mind.

BORROWED COGNITION, as over MCP. This server holds no model and no key. When
the mind needs to think, the API hands you a TASK: a system prompt, a user
prompt and a token limit. Run it on whatever model you use, then POST the
reply to /api/submit. Every guard still runs here on what comes back, so the
mind stays honest whatever model did the thinking. A mind that was given a
model of its own (mounted by the proxy) thinks for itself and hands you
nothing to do.

Every route answers JSON. Reading the mind never writes to it; nothing here
ever moves a body. See GETTING_STARTED.md for the walk-through.
"""
import threading
import time

from . import __version__
from .cognition import extract
from .envelope import new_id
from .manifest import FORMAT

TASK_TTL = 3600       # a task nobody answered within the hour is let go
MAX_TASKS = 64        # pending extraction tasks held at once; the oldest go first
MAX_EVENTS = 100      # experiences in one request


class APIError(Exception):
    def __init__(self, status, message):
        Exception.__init__(self, message)
        self.status, self.message = status, message


def _text(body, key, limit=4000):
    v = body.get(key)
    return v.strip()[:limit] if isinstance(v, str) else ""


class MindAPI:
    """Routes in, (status, JSON-able dict) out. `core` is the MCP door's
    core, whose borrowed-cognition machinery (and open thought) this shares,
    so a thought begun over one door can never be begun twice over the other."""

    def __init__(self, mind, core):
        self.mind = mind
        self.core = core
        self._tasks = {}
        self._lock = threading.Lock()

    # ── dispatch ─────────────────────────────────────────────────────────────
    def handle(self, method, route, body, base_url=""):
        route = "/" + route.strip("/") if route.strip("/") else ""
        body = body if isinstance(body, dict) else {}
        fn = ROUTES.get((method, route))
        if fn is None:
            if any(r == route for _m, r in ROUTES):
                return 405, {"error": "use %s for %s" % (
                    " or ".join(m for m, r in ROUTES if r == route), "/api" + route)}
            return 404, {"error": "no such route: /api%s (GET /api lists them)" % route}
        try:
            return 200, fn(self, body, base_url)
        except APIError as e:
            return e.status, {"error": e.message}
        except Exception as e:
            return 500, {"error": "the mind could not do that: %s" % e}

    # ── reading ──────────────────────────────────────────────────────────────
    def index(self, body, base_url):
        return {"themind": __version__, "format": FORMAT,
                "docs": "https://github.com/RattusKing/theMind/blob/main/GETTING_STARTED.md",
                "openapi": base_url + "/api/openapi.json",
                "routes": ["%s /api%s" % (m, r) for m, r in sorted(ROUTES, key=lambda k: k[1])]}

    def openapi(self, body, base_url):
        return spec(base_url)

    def context(self, body, base_url):
        return {"context": self.mind.context(_text(body, "message") or None,
                                             who=_text(body, "who", 80) or None)}

    def enrich(self, body, base_url):
        msgs = body.get("messages")
        if not isinstance(msgs, list):
            raise APIError(400, "messages must be a list of {role, content}")
        return {"messages": self.mind.enrich(msgs, who=_text(body, "who", 80) or None)}

    def remember(self, body, base_url):
        from .retrieval import recall, recent
        from .people import of
        from .envelope import confidence, ago
        query = _text(body, "query")
        facts = of(self.mind.live("facts"), self.mind.people.resolve(_text(body, "who", 80) or None))
        lit = self.mind.graph.constellation(query) if query else []
        retrieve = self.mind.retriever or recall
        chosen = retrieve(facts, query, lit, 8) if query else recent(facts, 5)
        return {"memories": [{"text": f.get("text", ""), "how": confidence(f),
                              "when": ago(f.get("t"))} for f in chosen]}

    def stage(self, body, base_url):
        return self.mind.stage()

    def show(self, body, base_url):
        from .show import report
        return report(self.mind)

    # ── learning: the exchange, and the thinking it owes ─────────────────────
    def observe(self, body, base_url):
        user_text, reply = _text(body, "user_text"), _text(body, "reply")
        if not user_text:
            raise APIError(400, "user_text is required: what the person said")
        who = _text(body, "who", 80) or None
        own = self.mind.llm is not None
        self.mind.observe(user_text, reply, who=who)   # it happened, whoever does the thinking
        if own:
            return {"task": None, "thinking": "its own model is learning from this"}
        key = self.mind.people.resolve(who)
        need = self.core._capture(lambda m: extract.run(m, user_text, reply, who=key))
        if need is None:
            return {"task": None, "thinking": "nothing to remember from this"}
        task = self._task("extract", need, {"user_text": user_text, "reply": reply, "who": key})
        return {"task": task, "thinking": "yours: run the task on your model, then POST "
                                          "the reply to /api/submit"}

    def think(self, body, base_url):
        if self.mind.llm is not None:
            name = self.mind.step()
            return {"task": None, "thought": name}
        from .cognition import due_passes
        with self.core._lock:
            if self.core._pending is not None:
                name, _fn, need = self.core._pending
                tid = getattr(self.core, "_pending_id", None)
                if tid is None:
                    tid = self.core._pending_id = new_id("t")
                return {"task": self._shape(tid, name, need), "open": True}
            due = due_passes(self.mind)
            if not due:
                return {"task": None, "thought": None, "rest": "nothing owed right now"}
            name, fn = due[0]
            need = self.core._capture(fn)
            if need is None:
                return {"task": None, "thought": None,
                        "rest": "the %s pass found nothing to work with yet" % name}
            self.core._pending = (name, fn, need)
            tid = self.core._pending_id = new_id("t")
        return {"task": self._shape(tid, name, need), "open": False}

    def submit(self, body, base_url):
        tid, output = _text(body, "task", 80), _text(body, "output", 20000)
        if not tid:
            raise APIError(400, "task is required: the id of the task you ran")
        with self._lock:
            self._expire()
            held = self._tasks.pop(tid, None)
        if held is not None:
            if not output:
                return {"ok": False, "message": "empty output: nothing changed"}
            d = held["data"]
            stored = self.core._one_shot_run(
                "extract", output,
                lambda: extract.run(self.mind, d["user_text"], d["reply"], who=d["who"]))
            self._grew()
            return {"ok": True, "held": stored or 0,
                    "message": "remembered what held; anything ungrounded was dropped"}
        with self.core._lock:
            if self.core._pending is None or getattr(self.core, "_pending_id", None) != tid:
                raise APIError(404, "no open task %s (it was answered, or it expired)" % tid)
            name, fn, need = self.core._pending
            self.core._pending = None
            self.core._pending_id = None
        if not output:
            return {"ok": False, "message": "empty output: the thought was let go"}
        self.core._one_shot_run(need.purpose, output, lambda: fn(self.mind))
        self._grew()
        return {"ok": True, "thought": name,
                "message": "the %s thinking is part of it now; whatever failed its guards "
                           "was dropped" % name}

    # ── speaking first ───────────────────────────────────────────────────────
    def reach(self, body, base_url):
        msgs = body.get("messages") if isinstance(body.get("messages"), list) else None
        return {"reach": self.mind.reach(msgs, who=_text(body, "who", 80) or None)}

    def reached(self, body, base_url):
        return {"ok": bool(self.mind.reached(_text(body, "id", 80), _text(body, "text")))}

    # ── a body ───────────────────────────────────────────────────────────────
    def experience(self, body, base_url):
        events = body.get("events")
        if isinstance(events, list):
            if len(events) > MAX_EVENTS:
                raise APIError(413, "at most %d events per request" % MAX_EVENTS)
            return {"ids": [self._one(e) if isinstance(e, dict) else None for e in events]}
        return {"id": self._one(body)}

    def _one(self, e):
        what = e.get("text") if isinstance(e.get("text"), str) else e.get("what")
        if not isinstance(what, str) or not what.strip():
            raise APIError(400, "an experience needs text: what happened")
        present = e.get("with", e.get("present"))
        if isinstance(present, str):
            present = [present]
        ents = e.get("entities") if isinstance(e.get("entities"), list) else None
        return self.mind.experience(
            what, kind=e.get("kind"), where=e.get("where") if isinstance(e.get("where"), str)
            else None, present=present if isinstance(present, list) else None,
            source=e.get("source") if isinstance(e.get("source"), str) else None,
            intensity=e.get("intensity"), entities=ents,
            at=e.get("at") if isinstance(e.get("at"), str) else None)

    def body_get(self, body, base_url):
        from . import body as body_
        return {"body": _rows(body_.read(self.mind))}

    def body_post(self, body, base_url):
        readings = body.get("readings") if isinstance(body.get("readings"), dict) else body
        readings = {k: v for k, v in readings.items() if k != "at"}
        return {"body": _rows(self.mind.sense_body(
            readings, at=body.get("at") if isinstance(body.get("at"), str) else None))}

    def place(self, body, base_url):
        from . import body as body_
        return {"place": self.mind.place(),
                "known": [{"name": p.get("name"), "visits": int(p.get("visits") or 0),
                           "first": p.get("first_t")} for p in body_.known_places(self.mind)]}

    # ── tasks ────────────────────────────────────────────────────────────────
    def _task(self, kind, need, data):
        tid = new_id("t")
        with self._lock:
            self._expire()
            while len(self._tasks) >= MAX_TASKS:
                oldest = min(self._tasks, key=lambda k: self._tasks[k]["made"])
                self._tasks.pop(oldest, None)
            self._tasks[tid] = {"kind": kind, "made": time.time(), "data": data}
        return self._shape(tid, kind, need)

    def _shape(self, tid, name, need):
        return {"id": tid, "purpose": name, "system": need.system, "user": need.user,
                "max_tokens": need.max_tokens}

    def _expire(self):
        now = time.time()
        for k in [k for k, v in self._tasks.items() if now - v["made"] > TASK_TTL]:
            self._tasks.pop(k, None)

    def _grew(self):
        try:
            from . import development
            development.check(self.mind)
        except Exception:
            pass


def _rows(rows):
    return [{"signal": n.replace("body ", "", 1), "level": lv, "note": note}
            for n, lv, note in rows]


ROUTES = {
    ("GET", ""): MindAPI.index,
    ("GET", "/openapi.json"): MindAPI.openapi,
    ("POST", "/context"): MindAPI.context,
    ("POST", "/enrich"): MindAPI.enrich,
    ("POST", "/remember"): MindAPI.remember,
    ("GET", "/stage"): MindAPI.stage,
    ("GET", "/show"): MindAPI.show,
    ("POST", "/observe"): MindAPI.observe,
    ("POST", "/think"): MindAPI.think,
    ("POST", "/submit"): MindAPI.submit,
    ("POST", "/reach"): MindAPI.reach,
    ("POST", "/reached"): MindAPI.reached,
    ("POST", "/experience"): MindAPI.experience,
    ("GET", "/body"): MindAPI.body_get,
    ("POST", "/body"): MindAPI.body_post,
    ("GET", "/place"): MindAPI.place,
}

PUBLIC = {("GET", "/openapi.json")}   # the description of the API holds nothing of the mind


# ── the description, for code generators and ChatGPT custom GPT Actions ──────
def _obj(props, required=()):
    out = {"type": "object", "properties": props}
    if required:
        out["required"] = list(required)
    return out


_S = {"type": "string"}
_WHO = {"type": "string", "description": "who is speaking, by name, only if it is not the "
                                         "person the mind usually talks with. Never guessed."}
_TASK = _obj({"id": _S, "purpose": _S, "system": _S, "user": _S,
              "max_tokens": {"type": "integer"}})
_TASK_OUT = _obj({"task": {"anyOf": [_TASK, {"type": "null"}],
                           "description": "thinking for your model to do, or null"},
                  "thinking": _S, "thought": _S, "rest": _S, "open": {"type": "boolean"}})


def _op(op_id, summary, req=None, res=None, method="post"):
    out = {"operationId": op_id, "summary": summary,
           "responses": {"200": {"description": "OK", "content": {
               "application/json": {"schema": res or {"type": "object"}}}}}}
    if req is not None and method == "post":
        out["requestBody"] = {"required": True, "content": {"application/json": {"schema": req}}}
    return out


def spec(base_url=""):
    """OpenAPI 3.1 for this API. `base_url` becomes the server address."""
    exp = _obj({"text": _S, "kind": {"type": "string", "enum": [
        "saw", "heard", "touched", "did", "felt", "arrived", "left", "happened"]},
        "where": {"type": "string", "description": "the place it happened"},
        "with": {"type": "array", "items": _S, "description": "who was there"},
        "source": {"type": "string", "description": "the sense that reported it"},
        "intensity": {"type": "number", "minimum": 0, "maximum": 1},
        "entities": {"type": "array", "items": _S},
        "at": {"type": "string", "description": "ISO time, if earlier than now"}}, ["text"])
    readings = {k: {"type": "number", "description": d} for k, d in (
        ("energy", "battery or charge, 0..1 or a percentage"),
        ("heat", "how hot, 0..1 of its limit"),
        ("strain", "mechanical load, 0..1 of its limit"),
        ("damage", "how damaged, 0..1"))}
    body_out = _obj({"body": {"type": "array", "items": _obj(
        {"signal": _S, "level": _S, "note": _S})}})
    paths = {
        "/api": {"get": _op("index", "What this API offers", method="get")},
        "/api/context": {"post": _op(
            "getInnerContext", "The mind's inner context for this turn, to add to your "
            "system prompt", _obj({"message": _S, "who": _WHO}), _obj({"context": _S}))},
        "/api/enrich": {"post": _op(
            "enrichMessages", "OpenAI-shaped messages in, the same with the inner context "
            "folded into the system side",
            _obj({"messages": {"type": "array", "items": {"type": "object"}}, "who": _WHO},
                 ["messages"]))},
        "/api/remember": {"post": _op(
            "remember", "What it remembers about the person, most relevant first",
            _obj({"query": _S, "who": _WHO}))},
        "/api/observe": {"post": _op(
            "observeExchange", "Tell the mind about an exchange. Returns a task for your "
            "model: the act of remembering it", _obj({"user_text": _S, "reply": _S,
                                                      "who": _WHO}, ["user_text"]),
            _TASK_OUT)},
        "/api/think": {"post": _op(
            "think", "A quiet moment: returns thinking the mind owes itself, as a task, or "
            "null", _obj({}), _TASK_OUT)},
        "/api/submit": {"post": _op(
            "submitTask", "Your model's reply to a task. Its guards run here",
            _obj({"task": _S, "output": _S}, ["task", "output"]))},
        "/api/reach": {"post": _op(
            "reachOut", "Something it would bring up first, before they write, or null",
            _obj({"messages": {"type": "array", "items": {"type": "object"}}, "who": _WHO}))},
        "/api/reached": {"post": _op(
            "reachedOut", "You sent what reach offered: record it",
            _obj({"id": _S, "text": _S}, ["id", "text"]))},
        "/api/experience": {"post": _op(
            "recordExperience", "Something it lived through, as its body or world reported "
            "it. One experience, or {events: [...]}", {"anyOf": [
                exp, _obj({"events": {"type": "array", "items": exp}}, ["events"])]})},
        "/api/body": {
            "get": _op("getBody", "How its body is", method="get", res=body_out),
            "post": _op("senseBody", "The body's readings", _obj(readings), body_out)},
        "/api/place": {"get": _op("getPlace", "Where it is, and every place it knows",
                                  method="get")},
        "/api/stage": {"get": _op("getStage", "How far it has grown with them", method="get")},
        "/api/show": {"get": _op("showMind", "Everything it holds, as one report",
                                 method="get")},
    }
    return {"openapi": "3.1.0",
            "info": {"title": "theMind", "version": __version__,
                     "description": "A mind of its own for your AI. This server holds no "
                                    "model: when the mind needs to think, it returns a task "
                                    "for your model, and you submit the reply."},
            "servers": [{"url": base_url or "/"}],
            "components": {"securitySchemes": {"bearer": {"type": "http", "scheme": "bearer"}}},
            "security": [{"bearer": []}, {}],
            "paths": paths}


def main(argv=None):
    from .mcp import main as serve_main
    return serve_main(argv, banner="api")


if __name__ == "__main__":
    import sys
    sys.exit(main())
