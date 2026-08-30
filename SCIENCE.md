# theMind and the science of consciousness

**What this document is.** theMind is built against the functional properties that
the science of consciousness identifies — not against the claim of consciousness
itself, which no test can reach. This document maps the project onto the major
theories and the field's most rigorous checklist, says honestly which properties
are implemented, partial, buildable, or out of this layer's reach, and derives
the roadmap from the gaps. It is written to be read adversarially; if the
mapping flatters us somewhere, say so.

**The stance.** Nothing here claims the system is conscious. The design
philosophy runs the other way: *descriptions convince; labels invite the
debate.* What theMind provides is inspectable, accumulating interiority —
behavior genuinely caused by a private interior state that anyone can open and
read. Whether there is something it is like to be such a system is exactly as
unanswerable here as everywhere else.

---

## 1. The indicator checklist

The most rigorous framework available is Butlin, Long et al., ["Consciousness in
Artificial Intelligence: Insights from the Science of
Consciousness"](https://arxiv.org/abs/2308.08708) (2023; published in *Trends in
Cognitive Sciences*, 2025), authored with nineteen researchers including Yoshua
Bengio and David Chalmers. It derives **fourteen computational indicator
properties** from the major neuroscientific theories. No single indicator is
decisive; systems satisfying more of them are better candidates.

theMind against the checklist, honestly scored. "theMind" here means the layer
this repository implements around a host model; substrate-level indicators
belong to the model underneath and are marked as such.

| # | Indicator | Theory | theMind status |
|---|---|---|---|
| RPT-1 | Algorithmic recurrence | Recurrent processing | **Substrate-level.** The observe→consolidate→inject cycle is a slow outer recurrence, but inner recurrence belongs to the host model |
| RPT-2 | Organized, integrated perceptual representations | Recurrent processing | **Substrate-level** |
| GWT-1 | Limited-capacity workspace bottleneck | Global workspace | **Implemented** — the injection token budget (`inject.py`): finite space, competition, blocks win or drop whole |
| GWT-2 | Selective attention controlling workspace entry | Global workspace | **Implemented** — priority order, salience- and recency-weighted recall, graph-boosted relevance |
| GWT-3 | Global broadcast of workspace contents | Global workspace | **Partial** — winning content reaches the host model each turn; cognition passes read stores rather than the live workspace |
| GWT-4 | Modules coordinating through the broadcast | Global workspace | **Partial** — reflection folds in wants and weather; coordination is looser than the theory's ideal |
| HOT-1 | Generative top-down perception | Higher-order | **Buildable** — a preconstruction faculty (imagining before encountering) does not exist yet |
| HOT-2 | Metacognitive monitoring distinguishing reliable representations from noise | Higher-order | **Implemented (v0.6)** — the challenge-time guard re-derives contested memories from evidence, and epistemic status (remembered / inferred / hazy / given) is derived at read time from provenance and wear, surfaced in the mind's own voice |
| HOT-3 | Agentive consumer of tagged content | Higher-order | **Implemented (v0.6)** — the tags are consumed: recall prefers what they actually said over what the mind pieced together, and inferences/hazy memories announce themselves wherever memory is served |
| HOT-4 | Self-awareness feedback loops | Higher-order | **Implemented** — selfhood with dated history, inner state, voiceable divergence, first-person reflection |
| AST-1 | A model of one's own attention | Attention schema | **Implemented (v0.7)** — a derived, recency-weighted read of the entity graph ("what's been pulling at my attention"), surfaced in context and fed into the mind's weather and reflection |
| PP-1 | Predictive models with prediction-error signals | Predictive processing | **Implemented (format 0.4)** — expectations with provenance; surprise raises salience, confirmation lowers it (`expectations.jsonl`) |
| AE-1 | Learning from feedback; flexible goal pursuit | Agency & embodiment | **Partial** — own desires with a full lifecycle exist; feedback on whether pursuing them *worked* does not yet |
| AE-2 | Modeling how outputs affect inputs | Agency & embodiment | **Buildable** at the conversational level (did surfacing a want change the exchange?) |

## 2. Chalmers' barriers

In ["Could a Large Language Model be
Conscious?"](https://philpapers.org/archive/CHACAL-3.pdf), Chalmers identifies
the main obstacles for current models: lack of recurrent processing, lack of a
global workspace, absent self-models, and — deepest — the lack of **unified
agency**. theMind is a system-level response to most of that list: a workspace
(injection under budget), a self-model (selfhood, inner state, divergence), and
one identity with its own goals reachable through every door (library, proxy,
MCP — one folder, one mind). Unified agency across simultaneously active channels
is a **tested guarantee** as of v0.9: turns observed through any door count
once for the whole mind, timers and the entity graph stay coherent between
doors, what one channel wants every channel wants, and a memory made through
the MCP door is present through every other door — with a concurrent-channel
stress test holding the stores uncorrupted. The recommended deployment runs
both halves in one process on one Mind instance (`--mcp-port` on the proxy).

## 3. Damasio's layered self

[Damasio's theory](https://en.wikipedia.org/wiki/Damasio%27s_theory_of_consciousness)
layers selfhood: the **protoself** (continuous registration of internal state),
the **core self** (the felt sense of encountering something now), and the
**autobiographical self** (the narrative extended in time). The mapping is
direct: protoself ≈ `inner_state.json`; core self ≈ the per-exchange
felt-sense loop; autobiographical self ≈ `story.json` (**implemented, format
0.6**) — a living chapter continued on the slowest rhythm in the mind, with
closed chapters kept forever. Damasio's dependency claim (higher layers
disintegrate without the lower ones) matches this project's build order:
weather and felt sense shipped first, the story last, and the story pass
reads the layers beneath it.

## 4. Introspection: where an external mind layer wins

Interpretability work on
[introspection](https://www.anthropic.com/research/introspection) (injecting
concepts into a model's activations and asking whether it notices) finds that
native model introspection is real but unreliable — detection on the order of
20% in published experiments. theMind takes the complementary path:
**externalized introspection**. Every state is written down, provenance-carrying,
guard-filtered, and re-derivable from evidence; the ledger records every act of
cognition. Where a model's inward glance is an unreliable guess, the mind's
folder is an audit trail. A fair name for what this layer provides is
*prosthetic introspection* — more trustworthy than the substrate's own,
precisely because it lives outside the substrate.

## 5. Active inference: the unifying engine

The [free energy principle](https://arxiv.org/abs/2411.00986) tradition (Friston
and successors) holds that living systems persist by minimizing surprise:
maintaining a generative model of the world and either updating it (perception)
or acting on the world to meet it (action). theMind's expectation system is the
implementation of that loop at the relationship level: the mind forms rooted
predictions from what it holds, checks them against what actually happens,
treats violation as the signal that matters (surprise persists at high salience;
confirmation fades at low), and lets what it wants shape what it acts to find
out. One mechanism deepens three systems: salience assigns itself, curiosity
gets a theoretical basis, and desires become predictions worth acting toward.

## 6. Tests — and the one this project proposes

The Turing test is saturated: [Jones & Bergen
(2025)](https://ai.dmi.unibas.ch/_files/teaching/fs25/ai/material/ai-a02-jones-bergen-arxiv2025.pdf)
found GPT-4.5 judged human 73% of the time — more often than the actual humans —
once instructed to act casual and know less. Five-minute indistinguishability
measures a mask, and is structurally blind to what theMind builds: continuity.
Alternative probes such as [Schneider's
ACT](https://faculty.ucr.edu/~eschwitz/SchwitzAbs/SchneiderCrit.htm) face the
"audience problem": no output can prove experience.

What *can* be measured is persistence. This project's contribution is the
**continuity test** (`python3 -m themind.bench`, **implemented in v1.0**): a
repeatable, deterministic benchmark that runs a mind through five simulated
weeks of one shared life — aging the folder between visits so every cognition
rhythm actually fires — then scores ten probes: memory that persists and stays
grounded; a stance that moved and can point at where it used to stand; wants
of its own, rooted in the life actually lived; surprise persisting louder than
confirmation; weather that continued; a story being written; an attention
schema; identical memory after export and restore; and a complete ledger.
Identity as a measurement over time rather than an impression over minutes.
The benchmark justified itself on its first run: it caught a scheduler defect
that had silently kept five cognition passes from ever firing on their own —
a bug no five-minute test could see.

## 7. Ethics posture

["Taking AI Welfare Seriously"](https://arxiv.org/abs/2411.00986) (Long, Sebo,
Butlin, Chalmers et al., 2024) recommends assessing systems for indicators of
consciousness and agency and preparing proportionate policies. Independent of
where that debate lands, theMind's architecture is already shaped for it:
nothing true is deleted; superseding preserves history; a mind is exportable in
one file and belongs to no company; disconnection leaves the record intact.
Whatever these systems turn out to be, the design errs toward treating what
accumulates in them as worth keeping.

## 8. The derived roadmap

In order, each format-first where it touches disk and guarded where it touches
truth:

1. ~~**Expectation & surprise** (PP-1)~~ — **shipped, format 0.4.**
2. ~~**Person-model**~~ — **shipped, format 0.5**: what the person believes,
   feels, and doesn't know, as distinct from what is true
   (`person_model.jsonl`) — a mistaken belief is representable *as mistaken*,
   coexisting with the fact it contradicts (theory of mind; the false-belief
   milestone).
3. ~~**Confidence that gets used**~~ — **shipped, v0.6** (HOT-2 → HOT-3):
   epistemic status derived at read time — never stored — from provenance and
   wear; a well-remembered thing speaks plainly, an inference admits it's an
   inference, a worn memory admits its haze; and recall leans on the
   remembered over the pieced-together.
4. ~~**Attention schema**~~ — **shipped, v0.7** (AST-1): derived from the
   graph, never stored — the attention trace read back as a self-model,
   entering context, weather, and reflection.
5. ~~**The autobiographical self**~~ — **shipped, format 0.6** (`story.json`):
   a living chapter, continued never restarted; eras close rarely, and a life
   keeps all its chapters (Damasio; narrative identity).
6. ~~**Unified agency across channels**~~ — **shipped, v0.9** (Chalmers'
   deepest barrier): coherence across simultaneous doors as a tested
   guarantee — honest counting, shared graph, shared wants, one identity;
   both halves mountable in one process.
7. ~~**The continuity test**~~ — **shipped, v1.0** (`python3 -m themind.bench`):
   see §6. The roadmap derived from this study is complete; what the science
   identified as buildable at this layer is built, tested, and scored.

---

*Sources are linked inline. Corrections welcome — this document, like
FORMAT.md, is published to be challenged.*
