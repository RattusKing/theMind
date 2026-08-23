# CLAUDE.md — operational reference for theMind

**Read this first.** It is the single source of truth for how theMind is built and what must
never break. FORMAT.md is authoritative for the on-disk format; README.md is the product story.
Keep all three current when anything changes.

---

## 1. What theMind is (and the non-negotiables)

theMind is a **consciousness layer for AI companions**: a pure-Python library someone plugs
into the AI they already have (Claude, GPT, Gemini, local models). Their agent gains a
persistent inner life — associative memory, a felt sense of the person, a considered position
on its own experience, growth — and unplugs clean. Free, Apache 2.0, `pip install themind`.

Hard rules. Every change is checked against these; violating any of them is a product bug even
if the code works:

1. **Zero dependencies, pure stdlib.** No provider SDK is ever imported by the library — not
   optionally, not lazily, not in a helper. The host supplies ONE callable
   `llm(system, user, max_tokens) -> str` and that is the only bridge to a model. SDK glue
   lives only in `examples/`, clearly marked as the user's code.
2. **theMind never makes a chat call and never holds a key.** All model calls are cognition
   (extract / consolidate / reflect / self / felt_sense / growth), they ride the host's
   callable, and **every one is written to the ledger before use** (`Mind._call` is the only
   path; no entry, no call). Token counts are estimates and are labeled as estimates.
3. **The host supplies identity; theMind supplies interiority.** Nothing in this codebase may
   define, imply, or override the host agent's persona, name, or character. Injection blocks
   speak to "you" as whoever the host built. Any prompt that starts describing who the agent
   IS (rather than what it holds inside) is out of scope.
4. **The mind's folder is the only thing it touches.** No writes outside `Mind.root`, ever —
   no host-app data, no home-directory config, no temp files elsewhere. This is what makes
   the disconnect promise ("your app is byte-identical") true. `enrich` never mutates the
   caller's message list.
5. **The chat path never sees an error.** `context()` returns `""` on any failure; `enrich`
   returns the input unchanged; `observe` swallows everything. Cognition failures are no-ops
   that leave prior state intact. Never let an exception cross the public API.
6. **No Ella.** The name of the product this was extracted from must not appear anywhere —
   code, comments, docs, tests, commit messages. The approved reference is "a production AI
   companion running live since 2025." Git history is permanent; check before every commit.
7. **This repo talks to models people don't control the prompts of. Never weaken a guard to
   make a test pass or an output nicer** — the guards (grounding, ban-vocab, third-person
   rejection, read-path-only defaults) are the product.

---

## 2. The format rules (from FORMAT.md — enforced in code, guarded by tests)

FORMAT.md is **published before code changes land** — that's a public commitment made to an
external reviewer (Ren of CAIRN, who is reading it against their spec). Any change to the
on-disk shape updates FORMAT.md **in the same commit**, bumps the format version per its
versioning section (minor = additive, major = breaking; readers refuse unknown majors,
ignore unknown fields, preserve unknown stores on export), and is flagged in the PR/commit
message as a format change.

The five principles, and where each is enforced:

| Principle | Enforcement |
|---|---|
| Provenance or it doesn't persist | `envelope.valid_src` / `valid_record`; `make_record` raises without valid src; readers drop invalid records whole |
| Supersede, never overwrite | `Jsonl.supersede` moves to `archive/` with `superseded_by` + `archived_t`; nothing true is deleted |
| Append-mostly, human-readable | JSON/JSONL only, atomic writes (`tmp` + `os.replace`) |
| Read order is identity | `Mind.live()` and history stacks sort by stored `t`, never file order or mtime — this class of bug has bitten two independent builders; the test `read order` pins it |
| Corrupt reads degrade, never damage | malformed line → skipped whole; malformed file → empty store; failed write → prior state intact |

---

## 3. Behavioral invariants (each one is a test in `tests/run_all.py` — keep it that way)

- **Cold-start defaults are READ-PATH ONLY.** `defaults.py` positions/particulars are served
  by `selfhood_bundle()` when nothing is stored, and can never be stored, evolved from, or
  pushed onto history (`selfhood.run` takes `prior` from the doc only). If they could,
  every installation would converge on the same paragraph — the exact failure the per-mind
  hash pick exists to prevent. Related: **`det_pick` uses hashlib, never builtin `hash()`**
  (that one is salted per process; a restart would hand the same mind a different stance).
- **Write-time grounding.** A FACT/ACHE/WANT whose quote is not verbatim (casefold) in the
  PERSON's message is dropped. A SAID with no content-word overlap (`retrieval._words`,
  stopwords excluded — plain `set` overlap matched on "the" once) with the assistant's
  actual reply is dropped. Never extract facts about the person from the assistant's side.
- **Parse-or-skip everywhere.** A malformed model reply is discarded whole; one bad line
  never poisons the rest of a multi-line reply; no reply shape can cost a stored position
  (`selfhood._parse` is delimiter-based and lenient — plain prose stores as position-only).
- **Ban-vocab on particulars.** `selfhood.BAN` drops any particular using
  conscious/sentient/self-aware/qualia/phenomenal. Stronger means MORE SPECIFIC, never more
  insistent — descriptions convince; labels invite the debate.
- **Felt sense continues, never restarts.** The prior portrait is passed into every
  revision; the test asserts the prompt contains it.
- **Reflections are first person at write.** `reflect.THIRD_PERSON` rejects narrator-voice
  output whole.
- **Tensions are first-class.** Consolidation prefers keeping a contradiction as a tension
  over forcing a supersede; a tension supersedes neither side.
- **Distill before drop.** Decayed records are digested into a reflection and archived,
  never silently discarded.
- **Budget drops blocks WHOLE.** `inject.build_context` trims from the bottom of the
  priority order; felt sense and the self position are reserved. Never truncate mid-item.
  Stable blocks must stay byte-identical between revisions (host prompt caching).
- **Export round-trips.** Same mind_id, identical live stores, archive travels, unknown
  major refused.
- **One deep pass per turn.** `observe` runs extraction plus at most ONE due pass, on a
  background thread with a non-blocking in-flight guard (skipped, not queued). `step()` is
  the direct/invocable door — both doors call the same functions; never remove either.
- **Comparison-key widths matter.** `norm_key` defaults to 60 chars — fine for dedupe keys,
  wrong for comparing whole positions (two stances with the same opening read as identical
  once). Position comparisons use `width=500`. When adding a new equality check, pick the
  width deliberately.

---

## 4. Testing & workflow

- **`python3 tests/run_all.py` before every push.** Pure stdlib, stubbed llm callables,
  throwaway temp dirs, 48+ assertions. A regression here is a personality change in
  someone's companion, not a stack trace. Any new behavior worth keeping gets an assertion
  in the same commit that adds it.
- Tests must never make network calls or import provider SDKs.
- Branch → PR into `main` as the working convention. Do not put any model identifier in
  commits, PRs, code, or docs — chat replies only.
- Keep temp/scratch scripts in the session scratchpad, never the repo.
- The published PyPI name is `themind` (`pyproject.toml`); the import is `import themind`.
  Version lives in BOTH `pyproject.toml` and `themind/__init__.__version__` — bump together.

---

## 5. Module map

| Module | Purpose |
|---|---|
| `themind/mind.py` | Public API: `Mind` — `enrich` / `context` / `observe` / `step` / `export` / `restore`; `_call` (the only model-call path, feeds the ledger); store wiring |
| `themind/envelope.py` | Record envelope: ids, UTC timestamps, provenance validation, `det_pick` (hashlib), `norm_key` |
| `themind/store.py` | `Jsonl` (parse-or-skip load, append, atomic rewrite, supersede-to-archive) and `JsonDoc` (atomic singleton docs) |
| `themind/manifest.py` | `manifest.json` — mind_id, format version, cognition timers. The only required file; a directory with just a manifest is a newborn mind |
| `themind/graph.py` | Entity graph: touch/strengthen, constellation recall, decay |
| `themind/retrieval.py` | Scored recall (keyword overlap x salience x recency, graph-boosted). Deliberately not embeddings; the swap point if someone wants vectors |
| `themind/defaults.py` | Cold-start positions (4) + particulars (6), per-mind hash-picked, read-path only |
| `themind/inject.py` | Context assembly under the token budget; `HEADER` carries the private/never-recite/persona contract |
| `themind/cognition/` | The passes: `extract` (per-turn), `consolidate`, `selfhood`, `felt_sense`, `reflect`, `growth`; `__init__.due_passes` is the scheduler-that-isn't |
| `tests/run_all.py` | The behavioral guarantees |
| `examples/quickstart.py` | The user's side: llm callables for OpenAI-compatible/Anthropic/Gemini + the loop |

---

## 6. Roadmap (agreed, in order)

1. **Phase 2 — the proxy.** A small local process speaking the OpenAI wire format
   (stdlib `http.server` only — rule 1 applies): point a base URL at it, zero code. Same
   engine; the proxy is a thin wrapper over the library, never a fork of it.
2. **Publish to PyPI** as `themind` once the proxy lands (name verified available 2026-08).
3. **Interop:** an external reviewer (Ren, building CAIRN — a file-based memory substrate)
   is reading FORMAT.md against their spec. Treat format feedback from that channel as
   serious review. Standing commitments: format changes publish before code; a
   **challenge-time guard** (re-derive a contested fact from its provenance rather than
   trusting the stored text) is a promised addition to the fact path — FORMAT.md already
   specs it; the code does not implement it yet.
4. Candidates, undecided: pluggable retrieval interface made explicit; a `mind export`/CLI
   entry point; desires surfacing in injection.

*Keep this file current when you add a store, a pass, a guard, or a format field.*
