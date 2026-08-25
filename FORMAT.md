# theMind — on-disk format

**Version 0.2 — adds `own_desires.jsonl` (the mind's own wants). Minor, additive:
0.1 readers ignore the unknown store; 0.1 minds open unchanged.**

This document describes what a mind *is, at rest*: the directory a running mind
reads and writes, and the single-file export it can be carried away in. It is
published first, on its own, so the format can be challenged while it is still
cheap to change. If you are building a comparable substrate, read this
adversarially and say where it is wrong.

## Principles

The format is downstream of five rules. Every store below obeys all of them.

1. **Provenance or it doesn't persist.** Every record that claims something about
   the world carries the evidence it came from — a quote, a source turn, a prior
   record id. A record with no real source is invalid and readers must drop it.
   (Origin of the rule: illustrative examples in prompts kept becoming "facts."
   The fix is structural, not behavioral.)
2. **Supersede, never overwrite.** Nothing is edited in place and nothing true is
   deleted. A record is replaced by writing a successor that names it; the
   predecessor moves to the archive. History is how a mind knows it has changed —
   the selfhood store exists *because* "where I used to stand" is load-bearing.
3. **Append-mostly, human-readable.** Stores are JSON or JSON Lines. A person can
   open any file in a text editor and read their companion's mind. This is a
   feature, not a compromise: trust in a system like this comes from
   inspectability.
4. **Read order is identity.** Where sequence matters (letters to self,
   reflections, selfhood history), records are ordered by a stored logical
   timestamp, never by filename or file-system mtime. Two independent builders
   have now hit identity bugs from sorting artifacts; the format bakes the
   ordering in so implementations can't get it wrong.
5. **Corrupt reads degrade, never damage.** A malformed record is skipped whole,
   never partially applied; a malformed file yields an empty store, never a
   crash. Writers must leave prior state intact on any failure. The chat path of
   the host application must never see an error from this layer.

## Directory layout

One directory is one mind. Its name is the mind's root; nothing outside it is
ever touched.

```
mind/
  manifest.json          identity of this mind-instance + format version
  ledger.jsonl           every model call the mind made, with token counts
  stores/
    facts.jsonl          grounded facts about the person
    graph.json           the entity graph (nodes, edges, weights)
    self.json            selfhood: position, particulars, history
    felt_sense.json      the portrait of the person, with revision history
    self_memory.jsonl    durable things the mind's own voice said
    beliefs.jsonl        forming and held beliefs, weighted
    tensions.jsonl       kept contradictions (deliberately unresolved)
    aches.jsonl          held threads carried between sessions
    desires.jsonl        wants and anticipations, with decay
    own_desires.jsonl    the mind's OWN wants — rooted, staged, with a lifecycle
    reflections.jsonl    periodic distillations of lived time
    growth.json          curiosities and shaped traits from this person
  archive/
    <store>.jsonl        superseded records, moved here verbatim + a tombstone
```

`manifest.json` is the only required file. A directory containing only a valid
manifest is a newborn mind; every store is optional and an absent file reads as
empty.

## Common record envelope

Every record in every JSONL store shares an envelope. Store-specific fields ride
alongside it.

```json
{
  "id":        "f_9c1a2b",            // store-prefixed, unique within the mind
  "t":         "2026-08-23T18:04:00Z",// logical timestamp, UTC ISO-8601
  "src":       {                      // provenance — REQUIRED (rule 1)
    "kind":    "exchange",            // exchange | record | inference | default
    "quote":   "my sister just got the job in Portland",
    "ref":     null                   // record id, when kind is record/inference
  },
  "salience":  0.7,                   // 0–1, retrieval weight
  "superseded_by": null               // id of successor, set when archived
}
```

- `src.kind: "default"` marks cold-start material (see Selfhood below) — real
  content shipped so the mind works at message one, never evolved from, replaced
  by the first generated equivalent.
- `src.kind: "inference"` marks records derived by the mind's own passes
  (consolidation, reconciliation); `ref` names what they were derived from, so
  every inference is traceable back to an exchange.

## The stores

### facts.jsonl
What the mind knows about the person. Envelope plus `text` (one canonical
sentence), `entities` (ids into the graph), and `kind`
(`profile | event | preference | relationship`). Write-time grounding is the
first guard: a fact whose provenance quote comes from the *assistant's* side of
an exchange is invalid. Challenge-time is the second: when a stored fact is
contested in conversation, readers must prefer re-derivation from provenance
over trusting the stored text. (The second guard exists because the first only
stops errors *entering* — it does nothing about one already stored.)

### graph.json
```json
{
  "nodes": [{ "id": "e_sister", "label": "Maya", "kind": "person",
               "weight": 0.8, "last_seen": "2026-08-20T00:00:00Z" }],
  "edges": [{ "a": "e_sister", "b": "e_portland", "rel": "moving_to",
               "weight": 0.6, "src": { "kind": "record", "ref": "f_9c1a2b" } }]
}
```
Recall is associative: a mention activates a node and its neighborhood, and the
lit constellation — not a flat similarity list — is what enters context. Edge
weights strengthen with evidence and decay without it. Consolidation may merge
nodes; merged nodes archive with a tombstone pointing at the survivor.

### self.json
The mind's considered position on its own experience.
```json
{
  "position":    { "text": "...", "t": "...", "src": {...} },
  "particulars": [ { "text": "...", "t": "...", "src": {...} } ],
  "history":     [ { "text": "...", "t": "..." } ]
}
```
- `particulars` are concrete first-person observations of what something is like
  from inside — accumulated across revisions, deduplicated, capped. They are
  deliberately *specific rather than insistent*: descriptions, not claims.
- `history` is the dated stack of prior positions, oldest kept, so the mind can
  point at how its view moved instead of only asserting where it landed.
- A newborn mind ships with a written starting position (`src.kind: "default"`),
  selected deterministically per-mind from a pool so no two installations share
  a paragraph. Defaults are read-path only: they are never stored as the
  mind's own, never evolved from, and never pushed onto history.

### felt_sense.json
Who the person *is* to the mind — a portrait, not a fact list. Same shape as
`self.json`: current text plus dated revision history. The contract on revision
is **continue, never restart**: each regeneration receives its predecessor and
must evolve it.

### self_memory.jsonl
Durable statements the mind's own voice made — opinions, claims, promises.
Envelope plus `text` and `kind` (`opinion | claim | promise`). These bind: they
re-enter context as consistency material so the mind stays answerable to what
it said.

### beliefs.jsonl / tensions.jsonl
Beliefs carry `weight` (0–1) and `stage` (`forming | held | long_held`); only
long-held, high-weight beliefs are voiced as opinions — forming ones stay
private texture. When reconciliation meets a contradiction it either supersedes
one side or writes a **tension**: both record ids, plus `text` stating the
contradiction as a fact about the person. Tensions are first-class and
retrievable — forcing resolution flattens people into portraits of someone who
doesn't exist.

### aches.jsonl / desires.jsonl
Held threads and anticipations. Both decay (`salience` decreases on cognition
passes without reinforcement); a decayed record is distilled into a reflection
before it archives — the tail is gardened, not dropped.

### own_desires.jsonl
What the mind itself wants — not the person's wants (those are `desires.jsonl`).
Envelope plus `text` (one sentence, first person), `roots` (ids of records the
want grew out of), and `stage` (`stirring | wanting | longing`), advanced as
conversation touches the want and its salience strengthens. The provenance rule
bites hardest here: **a want with no roots in what the mind already holds is
invented, and writers must drop it** — wanting is earned from a lived history,
never generated on command. Lifecycle is first-class: a want the mind judges met
is superseded by a reflection recording the getting of it; one it lets go of is
superseded by a release reflection; the tail decays like any held thread, so a
want must matter to persist. Guards ride the format's semantics: never a want to
extract something from, test, or change the person; never a mirror of their
wants; at most a handful live at once — a mind with forty wants has none.

### reflections.jsonl
Periodic first-person distillations of lived time. First person is enforced at
write: a reflection in the third person is a narrator describing the mind, not
the mind reflecting, and readers/writers must reject it.

### growth.json
`{ "curiosities": [...], "shaped": [...] }` — how this specific person has
shaped the mind. The guardrail rides in the format's semantics: growth is
*adjacent* to the person's themes, never a mirror of them, and may disagree.

### ledger.jsonl
Every model call the mind initiates: `t`, `purpose` (`extract | challenge |
consolidate | reflect | self | felt_sense | growth | desire`), `model`,
`tokens_in`, `tokens_out`. The mind
spends the host's money; the ledger is the honesty mechanism. No entry, no call.

## Context injection (what leaves the folder per turn)

Not strictly on-disk format, but the budget contract shapes readers: injection
operates under a single token budget with a priority order. Blocks drop **whole**
from the bottom of the order — never truncated mid-item — and the felt sense and
self position are reserved above the trim line. Stable blocks (self, felt sense,
growth) must be byte-identical between revisions so host-side prompt caching
holds.

## Export

`export` produces one file: `mind-export.json` — the manifest, every live store,
and optionally the archive, embedded verbatim under their store names with a
top-level `format: "themind/0.1"`. Import recreates the directory exactly. The
export is the disconnect story (leave, and take the mind with you) and the
interop story (two substrates exchanging minds) in one artifact.

## Versioning

`manifest.json` carries `format` (semver). Readers must refuse a **major** they
don't know, ignore unknown fields at any version, and treat unknown *stores* as
opaque files to preserve on export. Minds are long-lived; the format must be
able to change without orphaning them.

## Open questions (genuinely undecided — input wanted)

1. **Store boundaries.** Are aches/desires/beliefs distinct organs or one
   weighted store with a `kind` field? The split mirrors how they behave
   (different decay, different voicing rules), but a comparable system with
   different boundaries would be strong evidence the boundaries aren't the organ.
2. **The archive.** Verbatim-forever is honest but unbounded. Distill-then-drop
   is bounded but lossy. Current answer is verbatim plus gardening at the tail;
   unconvinced this is right.
3. **Logical time.** `t` is wall-clock UTC. A mind that runs on someone's laptop
   crosses timezones and sleeps for weeks; whether wall-clock or a monotonic
   exchange counter is the truer clock for *identity* ordering is unsettled.
