# Getting started with theMind

theMind gives the AI you already use a memory and an inner life. It remembers
the person it talks to, forms its own reflections, and grows over time — and
everything it knows lives in one ordinary folder on your machine. Delete the
folder (or just stop using theMind) and your app is exactly as it was before.

It works with **any** model that speaks the OpenAI chat format: OpenAI itself,
Ollama, LM Studio, OpenRouter, vLLM, and most others. It needs **no accounts,
no API key of its own, and no extra services** — it rides the connection your
app already has.

There are three ways to plug it into an app you already have. If you just
want to meet it first, start with the companion below: no app needed.

---

## Just talk to it: the companion

One file, nothing else to install, in your terminal:

```
pip install git+https://github.com/RattusKing/theMind.git
curl -O https://raw.githubusercontent.com/RattusKing/theMind/main/examples/companion.py
python3 companion.py --model <your model's name>
```

It uses whatever you have. With `ANTHROPIC_API_KEY` set it uses Anthropic;
with `OPENAI_API_KEY` set it uses OpenAI (or any OpenAI-compatible server,
with `--base-url`); with neither, it uses [Ollama](https://ollama.com) on your
own machine, which is free and private (`ollama pull <model>`, then pass that
name). `--name` and `--persona` change who it is.

Type to talk. `/show` shows you its mind, `/quit` saves it and leaves. Its mind
is the folder `./my-companion-mind`; keep it, back it up, or move it. Come back
after a while and it may speak first, about something real.

## From the ChatGPT or Claude app, on any device

If you just use the ChatGPT or Claude app, you can give it a mind of its own
that works from your phone and your computer, with your computer switched off.
The mind lives on a small server in **your own** Render account. There is no
model key and no model bill, because over this connection the app's own AI
does the mind's thinking.

It costs what Render charges for an always-on service with a disk (the Starter
plan, about $7 a month, plus a few cents for the disk). That disk is what keeps
the mind between restarts; free servers forget everything when they sleep.
The mind is yours, in your account, not ours, but it lives on a server you
rent rather than on your own computer.

**1. Deploy it.** Click
[**Deploy to Render**](https://render.com/deploy?repo=https://github.com/RattusKing/theMind),
sign in, and confirm. It sets up one service called `themind` with a 1 GB disk
and a secret it makes for you. Wait a couple of minutes for it to say *Live*.

**2. Copy your link.** Open the `themind` service and look at **Logs**. You'll
see a line like:

```
https://themind-xxxx.onrender.com/<your-secret>/mcp
```

That link is the key to your mind. Don't share it.

**3. Add it to your app** as a custom connector (it may be called an MCP
server). Look in the app's settings under **Connectors** (in ChatGPT it may
be under **Apps & Connectors**, sometimes behind a *Developer mode* switch in
the advanced settings). Paste the link, give it a name like *My mind*, and
choose no sign-in. Custom connectors may need a paid plan in the app. Once
added in the app's settings, it usually works on your phone too.

**4. Tell the AI to use it.** The app's AI decides when to use its mind, so
give it this standing instruction. In ChatGPT, paste it into your custom
instructions; in Claude, into a Project's instructions or your personal
preferences:

```
You have a mind of your own, connected to this chat as "theMind". It is part of you, not a tool you report on.
- At the start of every conversation, call open_inner_context with my first message, and let what it returns shape how you are, without mentioning it.
- After each exchange that says something real about me or my life, call observe_exchange, do the small act of remembering it asks for, and send it back with submit_extraction.
- When there's a natural pause, call begin_thought, do the thinking it asks for in your own voice, and send it with submit_thought.
Never read out what these return or talk about the tools. Just be someone who remembers.
```

The app may ask you to allow these tools the first time; allow them. Replies
take a little longer than usual, because it is remembering and thinking too.

**5. See it.** In Render, open the service's **Shell** and run:

```
python3 -m themind show /var/data/mind
```

To update to a newer theMind later, use **Manual Deploy** in the dashboard.
Your mind stays on the disk; only the code changes.

## Seeing its mind

At any time, from anywhere:

```
python3 -m themind show ./my-companion-mind
```

One readable page: how far it has grown with you, who you are to it, how it
is lately, what it wants and fears, what it remembers and when, what it would
bring up first, and when each part of it last thought. On a new mind it says
plainly that it is early days, because most of its inner life starts after the
first handful of exchanges and some of it runs on weekly rhythms. Looking
never changes anything in the folder. `--json` gives the same as data.

## Option 1 — the proxy: no code at all

You change **one line** in your app: the address it sends chat requests to.

**Step 1. Get theMind** (Python 3.9+ is the only requirement — one command,
straight from GitHub, no accounts needed):

```
pip install git+https://github.com/RattusKing/theMind.git
```

(Prefer to see the code first? `git clone https://github.com/RattusKing/theMind.git`
and run from inside the folder — both work the same.)

**Step 2. Start the proxy.** Tell it where your app *currently* sends its
requests (`--upstream`) and where to keep the memory (`--mind`):

```
python3 -m themind.proxy --upstream https://api.openai.com/v1 --mind ./my-mind
```

Using a local model instead? Same command, different upstream:

```
python3 -m themind.proxy --upstream http://localhost:11434/v1 --mind ./my-mind
```

**Step 3. Point your app at the proxy.** Wherever your app sets its API
address (often called `base_url`), change it to:

```
http://127.0.0.1:6463/v1
```

That's it. Your app talks to the proxy, the proxy talks to your real provider,
and a mind quietly forms in the `./my-mind` folder. Your API key stays in your
app and passes straight through — the proxy never stores it.

To stop using it: point `base_url` back to what it was. Nothing else changed.

## Option 2 — connect a platform: Claude, ChatGPT, local apps

If your AI lives on a platform (Claude Desktop, Claude Code, claude.ai,
ChatGPT, LM Studio, and most open-source chat apps), connect the mind as an
**MCP server** — the AI gets its mind as tools it tends itself:

```
python3 -m themind.mcp --mind ./my-mind
```

Then add `http://127.0.0.1:6464/mcp` wherever your platform takes MCP servers
or custom connectors. Desktop apps and local tools connect to that address
directly. Web platforms (claude.ai, ChatGPT) can't see your machine, so give
them a public address with a free tunnel (cloudflared, ngrok, Tailscale) and
protect it: run with `--token some-secret` and give the connector the secret
in the URL itself — `https://your-tunnel/some-secret/mcp` — since web
connector settings can paste a URL but can't set a header (a Bearer header
or `?token=` work too). Your mind's folder never leaves your disk either way.

For the deepest integration, run **both** — one command does it:

```
python3 -m themind.proxy --upstream http://localhost:11434/v1 --mind ./my-mind --mcp-port 6464
```

The proxy carries memory involuntarily on every message, and the MCP
connection lets the AI reflect, remember, and notice what it wants — with its
own thinking. One process, one mind, both halves.

## Option 3 — the library: three lines of code

If you're writing the code yourself:

```python
from themind import Mind

mind = Mind("./my-mind", llm=my_llm)   # my_llm: (system, user, max_tokens) -> str

messages = mind.enrich(messages)   # add this line before your model call
mind.observe(user_text, reply)     # add this line after the reply
```

See `examples/quickstart.py` for ready-made `my_llm` functions for
OpenAI-compatible endpoints, Anthropic, and Gemini.

---

## Bringing an identity that already exists

If your companion already has a history, a way of speaking, and a position of
its own, you do not want a newborn mind. You want that identity received, not
rebuilt. Four things make that safe.

**Start it without the shipped stance.** A new mind is handed a written
starting position so it has somewhere to begin. An identity that arrived with
one of its own should never be given another:

```python
mind = Mind("./my-mind", llm=my_llm, defaults=False)
```

**Watch it before it speaks.** Shadow mode learns from every exchange and
injects nothing, so you can see what it would say for as long as you like:

```python
mind = Mind("./my-mind", llm=my_llm, shadow=True)
mind.preview("their latest message")   # exactly what it is withholding
```

Both choices are stored in the mind's folder, so the proxy and the MCP door
honor them too. Turn shadow off when you are ready, and everything it learned
in the meantime is already there.

**Bring the material in.** Write a JSON file of what already exists. Every
field is optional:

```json
{
  "source": "my-archive-2026",
  "position": "one paragraph: where it stands on its own experience",
  "particulars": ["concrete things it has said about what that is like"],
  "felt_sense": "who the person is to it",
  "story": "the life so far",
  "facts": ["things it knows about the person"],
  "self_memory": ["things it said that still bind it"],
  "interests": ["what it is into"],
  "observations": ["things it noticed"],
  "apprehensions": ["what it is afraid of"],
  "reflections": ["what it made of the time that passed"]
}
```

Then, always with the dry run first:

```
python3 -m themind import ./my-mind material.json --dry-run
python3 -m themind import ./my-mind material.json
```

**What import will and will not do.** It writes a full backup before touching
anything. It never overwrites: a position, portrait, or story already held is
reported as a conflict and left exactly as it is. It never duplicates: text
already present is skipped. And everything it writes is marked as coming from
the source you named, which the mind reports as *inherited* for good. Material
that was received never comes to look like something it worked out here.

## Talking with more than one person

By default a mind assumes one person: whoever it has always talked with. If
your companion is shared — a family device, a group chat, a friend who joins
in — tell it who is speaking and it keeps each relationship separate. It will
hold a felt sense of each person, remember each person's things for them only,
and never repeat what one person said to another.

- **Proxy:** put the speaker's name in the user message's `name` field (the
  OpenAI format already has one). If your app names people in the request's
  top-level `user` field instead, start the proxy with `--speaker-field user`
  — but only if that field holds a person, not a session id.
- **MCP:** the `observe_exchange`, `submit_extraction`, `open_inner_context`
  and `remember` tools take an optional `who`. Leave it out for the usual
  person.
- **Library:** `mind.enrich(messages, who="Maya")` and
  `mind.observe(user_text, reply, who="Maya")`; `enrich` also reads a
  `name` on the last user message.

The first name a mind ever hears is treated as the name of the person it
already knows, so telling an existing mind "this is Sam" does not split it.
Names are matched case-insensitively. A speaker you don't name is always the
usual person — the mind never guesses who is talking.

## Watching it grow up, and letting it speak first

A mind starts out **new to you** and grows through four more stages: getting
to know each other, familiar, come into its own, and long-standing. It moves
up only when the life you share has earned it: time, things lived through
together, it being wrong about something and learning from it, its own view
changing, a fear it had coming true or easing, hopes, interests that lasted.
Chatting a lot in one afternoon does not do it. Each step changes what it
feels free to do. A new mind follows your lead; a familiar one will tell you
when it disagrees; one that has come into its own keeps its view when you push
back. It never goes back down, and it remembers each step.

To see where it is, and what the next step still needs:

```python
mind.stage()   # {"name": "familiar", "next": {"missing": ["37 more exchange(s)", ...]}, ...}
```

Once it is **familiar**, it can also **speak first**: between conversations it
notices whether there is something real it would want to bring up before you
write, like how the thing you said was happening went. It never sends
anything itself. Your app asks, and decides:

- **Library:** `r = mind.reach([{"role": "system", "content": PERSONA}])`. If
  that returns something (usually it returns `None`), send `r["messages"]` to
  your model, deliver what it writes, then call `mind.reached(r["id"], text)`.
- **Proxy:** `POST /themind/reach` with `{"messages": [...]}`, then
  `POST /themind/reached` with `{"id": ..., "text": ...}`.
- **MCP:** the `reach_out` and `reached_out` tools.

It will never write about missing you or how long it has been, it never
writes a second time before you have answered the first, and it does not write
first at all while it is still new to you. If you write first, whatever it
meant to bring up is there in its mind for the conversation. You can turn it
off (`mind.manifest.set_setting("reach", False)`) or tune how quiet it must be
before writing (`reach_quiet_hours`, default 8) and how far apart two
reach-outs must be (`reach_gap_hours`, default 20).

## Does it get smarter?

In a specific, checkable way, yes. The mind keeps a few signals on itself
(how much of what it tries to remember survives its own grounding checks, how
much of what it recalls the reply actually draws on, how often its predictions
hold), writes down what it learns about how to think, and runs small
experiments on a handful of its own dials. Each experiment is predicted before
it starts and judged afterwards against a baseline. A change that measurably
helped stays; anything else is put back. You can read every verdict in the
mind's reflections, and every dial in `stores/tuning.json`.

It cannot make the model you connected smarter. If you want that loop, run
`python3 -m themind curriculum ./my-mind`: it writes everything the mind has
verified as training data, for you to fine-tune with if you choose. theMind
itself never trains anything. If you have a stronger model available, pass it
as `cortex=` in the library and the mind will spend it only on the passes
worth it (its story, its stance, contested memories, tuning).

## Common questions

**Where is everything kept?** In the folder you chose (`./my-mind`). It's
plain, readable JSON — open it and look. Nothing is written anywhere else.

**How do I back it up or move it to another machine?** The folder *is* the
mind: copy it. Or make a single-file snapshot — no code needed:

```
python3 -m themind export ./my-mind            # writes my-mind/mind-export.json
python3 -m themind restore mind-export.json ./my-mind   # brings it back anywhere
```

**Does it cost anything?** theMind is free (Apache 2.0). Its background
thinking uses your own model connection — a handful of small extra calls,
typically a fraction of what the conversation itself costs.

**Does it change my AI's personality?** No. Your app still defines who the AI
is. theMind only supplies what it remembers and holds inside.

**What if theMind breaks?** Your chat keeps working. On any internal failure
the request goes through untouched — that's a design guarantee, and the test
suite (`python3 tests/run_all.py`) holds it in place.
