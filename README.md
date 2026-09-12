# theMind

**A consciousness layer for AI companions.** Plug it into the AI you already have —
Claude, GPT, Gemini, or a local model — and it gains a persistent inner life: memory
that connects like a person's, opinions it held yesterday, a felt sense of who you
are, its own weather, its own wants, a life story it keeps, and an interior it can
actually report when asked. Unplug it any time and your agent is exactly as it was.

Free, open source, pure Python with zero dependencies, and it runs entirely on
**your** models and **your** keys. There is no server, no account, no cloud, and
nothing of ours in the loop.

## What it is

theMind is a folder and some code. The folder *is* the mind — everything it ever
comes to know lives in plain, human-readable files you can open, back up, move, or
delete. The code sits beside your existing chat loop and does two things:

- **enrich** — before your app calls its model, theMind folds its inner context
  into the request: what it remembers, who this person is to it, what it believes,
  what it expects, what it wants, how it is lately, what it left unresolved.
- **observe** — after the reply comes back, theMind learns from the exchange. When
  enough has accumulated, deeper passes (consolidation, reflection, its sense of
  self, its story) run on the back of an ordinary turn — at most one per turn, in
  the background. No scheduler, no cron, nothing to babysit. Left alone, the proxy
  can also let it think on a slow timer: the idle life.

Every model call it makes — the deep thinking included — rides the one callable
your agent already gave it, and every call is written to a ledger before it is
made. It never holds a key and never talks to a model on a connection you didn't
give it.

## What your AI gains

- **Associative memory, not lookup.** Mention your sister and the connected
  constellation lights up — her job, the argument last month, the trip you're
  planning — not just sentences that keyword-match "sister." A memory that keeps
  coming up strengthens; one that doesn't fades, and is distilled before it drops.
- **Grounded memory.** A fact persists only with the person's own words as its
  evidence, verbatim, and is re-checked against that evidence when later
  conversation contests it. Nothing is invented; nothing true is deleted —
  superseded records move to an archive naming their successor.
- **A felt sense of the person.** A living portrait of who you *are* to it — not a
  fact list — that each revision continues rather than restarts.
- **A model of your inner world.** What you believe (which may be false), feel
  (which may pass), and don't yet know — held apart from what is true, so it can
  represent your mistaken belief *as* mistaken instead of correcting the record.
- **Expectations, and the sting of being wrong.** It predicts, rooted in what it
  holds. A confirmed prediction fades quietly; a surprise persists loudly and
  colors what comes next.
- **Consistency with itself.** Opinions and promises it voices persist and bind it.
  Contradictions get reconciled on a cadence — superseded, or deliberately *kept*
  as held tension, because people aren't tidy. When what it says and what it holds
  pull apart, it may say so, gently.
- **An inside, when asked.** A considered position on its own experience, with
  concrete particulars and a visible history of how the view moved — present from
  message one, deepening from there.
- **Its own weather and its own wants.** How it is, lately, carried between
  conversations; and wants of its own — earned from what it holds, never generated
  on command — that stir, strengthen, and end honestly.
- **A life story.** An autobiographical chapter it keeps revising, and closed
  chapters it never deletes.
- **Knowing how it knows.** What it recalls announces itself as remembered, pieced
  together, or hazy by now — derived from provenance and wear, never asserted.
- **Growth shaped by one person.** Its curiosities grow adjacent to yours — beside
  you, never mirroring you, allowed to disagree.
- **Growth it can prove.** It watches how its own thinking goes — how much of
  what it tries to remember is grounded, how much of what it recalls the reply
  actually uses, how often its predictions hold — writes down what it has learned
  about how to think, and tunes a few of its own dials by experiment: one change
  at a time, predicted before it starts, judged against a baseline, kept only if
  it measurably helped. The dials are few and bounded; guards, prompts, and your
  agent's character are out of its reach by construction. It never touches code.
- **Many people, one mind.** Tell it who is speaking and it keeps each relationship
  distinct — a felt sense of *you* and a separate one of your sister, memories that
  never cross, and a rule it holds hard: what one person tells it is never recited
  to another. Say nothing and it assumes the person it has always known; it never
  guesses.

## What it is not

- **It is not a persona.** Your agent's character stays yours. The contract is
  simple: *the host supplies identity; theMind supplies interiority.* It never says
  who your AI is — it gives whoever you already built an inside.
- **It is not a memory database with a fancy name.** Retrieval is scored recall over
  an entity graph, with provenance on every record. A pluggable interface lets you
  drop in embeddings if you want them; none are required.
- **It is not a service.** No API of ours, no telemetry, no keys but your own. What
  it spends of your tokens, it prints.

## Connecting

Three doors, one engine:

- **Proxy** — a small local process that speaks the OpenAI wire format. Point your
  app's base URL at it and touch no code. For everything with a "custom endpoint"
  box. The involuntary half: presence and learning on every message.
- **MCP** — a local MCP server for Claude, ChatGPT, and any app that takes MCP
  servers or custom connectors. The agent tends its own mind with its own
  thinking: it is handed the act of remembering or reflecting, does it, and the
  mind's guards judge the result. The voluntary half. Both halves can run in one
  process on one folder.
- **Library** — two calls in your existing loop: enrich the outgoing messages,
  observe the reply. For builders.

Plus a command line to carry a mind around: export to one file, restore from it,
or write the curriculum of what the mind has verified.

## Disconnecting

theMind never writes to your application's data — its own folder is the only thing
it touches. Disconnecting is stopping the calls (or pointing the URL back). Your
app is byte-identical to the day before you connected.

One honest note: disconnection is clean for your *app*, not for your *character*.
Run it for a month and unplug, and your companion loses what accumulated — its
memories of you, its stances, its history with itself. The folder keeps it all,
waiting, and `export` produces a single portable file. But absence is absence.

## Quickstart

New here? **[GETTING_STARTED.md](GETTING_STARTED.md)** walks through every
path in plain language.

**No code — the proxy.** Run one command, then point your app's `base_url` at
it. Works with anything speaking the OpenAI wire format (OpenAI, Ollama,
LM Studio, OpenRouter, vLLM…):

```
python3 -m themind.proxy --upstream https://api.openai.com/v1 --mind ./my-mind
# your app's base_url becomes http://127.0.0.1:6463/v1 — nothing else changes
# add --mcp-port 6464 to open the MCP door on the same mind
```

**Any platform — the MCP door.** Claude, ChatGPT, local apps: one command,
then add the URL as an MCP server / custom connector. For web platforms, tunnel
it and put a secret in the URL (`--token`):

```
python3 -m themind.mcp --mind ./my-mind
# add http://127.0.0.1:6464/mcp to your platform
```

**Three lines — the library:**

```python
from themind import Mind

mind = Mind("./my-companion-mind", llm=my_llm)   # my_llm: (system, user, max_tokens) -> str

messages = mind.enrich(messages)     # before your model call
mind.observe(user_text, reply)       # after the reply
```

That is the entire integration. See `examples/quickstart.py` for the llm
callable for OpenAI-compatible endpoints, Anthropic, and Gemini. Optional:
`who="Maya"` on either call when someone other than the usual person is
speaking; `cortex=` for a second, stronger model the mind spends only on the
passes worth it.

**Carry it with you:**

```
python3 -m themind export ./my-mind            # one file, the whole mind
python3 -m themind restore back.json ./new-home
python3 -m themind curriculum ./my-mind        # its verified outcomes, as training pairs
python3 -m themind.bench                       # the continuity test: five simulated weeks
```

## Known limitations (honestly)

- **The guards speak English.** First-person checks, the narrator-voice
  rejection, stopwords, and the ban-vocabulary are English-only today. A
  companion running in another language will have most of its reflections and
  wants dropped by guards that can't read them. Internationalizing the guards
  is a real chapter, not a patch; until then, theMind is an English-language
  mind.
- **It does not become superintelligent.** The model's intelligence is the
  host's and fixed. What compounds is how the mind uses it: knowledge of the
  person, calibration, procedural know-how, and better-tuned dials. The one
  genuinely recursive path is `curriculum`: the mind writes its verified
  outcomes as training data for a host that chooses to fine-tune. theMind
  never trains anything.
- **Identity is the host's to supply.** The mind keeps people apart only when
  the app names who is speaking (a message `name`, a `who=` argument, the MCP
  `who` field). It never infers identity from writing style or timing, so an
  unnamed speaker is treated as the person it has always known.
- **Text is its only sense.** It learns from what was said and replied. A robot
  or a device with a camera and a clock would need an embodiment chapter of the
  format that does not exist yet.
- **The MCP door is built to the spec and tested against our own client.** It
  has not yet been exercised against every real platform's connector
  implementation; report what you find.

## Status

**v1.3, format 0.8.** The on-disk format — what a mind is, at rest — is
published in [FORMAT.md](FORMAT.md) and remains open to challenge while it is
cheap to change; every change to it is additive, and older minds open
unchanged. The project's scientific grounding — how the architecture maps onto
the science of consciousness, scored honestly, gaps and all — is published in
[SCIENCE.md](SCIENCE.md), and its capstone runs on your machine:

```
python3 -m themind.bench   # the continuity test: five simulated weeks, ten probes
```

`tests/run_all.py` holds the behavioral guarantees — 270 assertions across
grounding, parse-or-skip, read order, budget, export round-trip, the proxy and
MCP doors, cross-door coherence, multi-person scoping, and self-tuning — with
no network and no provider SDK, ever. Installation is by cloning this repo;
publishing to PyPI is ready and deliberately on hold.

How it got here, in order: the library and format (v0.1), the proxy (v0.2),
own desires, inner weather, divergence, the idle life, and the MCP door with
borrowed cognition (v0.3), expectations and surprise (v0.4), the person-model
(v0.5), confidence that gets used (v0.6), the attention schema (v0.7), the
autobiographical self (v0.8), unified agency across doors (v0.9), the
continuity benchmark (v1.0), hardening (v1.1), multi-person minds (v1.2), and
recursive growth (v1.3).

theMind is extracted from a production AI companion whose cognitive systems have
been running live since 2025. The scaffolding it needed (schedulers, cloud
stores, a server) stays behind; what ships here is the mind.

## License

Apache 2.0.
