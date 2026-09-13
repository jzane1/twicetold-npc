# docs\ — index and reading order

Written 2026-07-28 (full-repo audit); leaned to the integrator/evaluator set at the 2026-09-11
public lean-down. Add new files to the right group below.

---

## Start here

| If you want to… | Read |
|---|---|
| get it running | **`SETUP.md`** — clone to running system, PowerShell throughout |
| understand what it *is* | **`architecture.md`** — the design truth |
| author an NPC for it | **`identity-authoring.md`** — identity, memory prose, knobs, and the authoring-time checks |
| wire it into a game | **`first-npc.md`** — your first NPC in about thirty lines: the calls, in order, and why |
| ship a game with it | **`shipping.md`** — hosting, keys and cost, the trust model, Steam's disclosure rules, the platform matrix |

---

## The repository, folder by folder

Moved here from the README at F1 (2026-09-03) so the front page stays short.

| Path | What it is |
|---|---|
| `app\` | the service: ingest, retrieval, reconstruction, the gate, dialogue, the two model backends, the routes, the eval runner |
| `db\` | migrations 001–008 and the transactional migration runner |
| `tests\` | the pytest suite and the sixteen walkers |
| `client\` | `NpcMemory.Core`, the engine-agnostic C# client, and its console harness |
| `unity\` | the Unity 6 gray-box project: a thin adapter over the client, plus the set |
| `ledger\` | The Ledger, served by the API at `/ledger` |
| `data\` | eval corpora, arms, blind gold labels, and the bundled affect lexicon |
| `docs\` | design truth, layer specs, the integrator guides (this index) |
| `.claude\` | the AI-pair apparatus: auditor agents, hooks, session commands |

---

## Design truth

- **`architecture.md`** — the whole system in thirteen numbered sections: principles, data model,
  write path, read path, reconstruction, correction verbs, turn topology, instrumentation,
  integrator surface, positioning. Read the sections your task touches *before* touching a layer.
  Changes only when the design changes.

---

## Layer specs

Each consolidates the relevant architecture sections into a buildable target with done-when
criteria and carries a **dated BUILT banner**: the banner tells you the spec is no longer a
plan, it is the contract the layer was verified against. The specs published here are the ones
an integrator or evaluator still needs; `architecture.md` is the living summary of every layer.

| Spec | Layer | Migration |
|---|---|---|
| `migration-01.md` | the foundational schema — 9 tables, CHECKs, indexes | 001 |
| `mid-dialogue-gate.md` | conditional retrieval mid-scene, and the caller-held loaded-set contract | 003 |
| `unity-client.md` | SSE + provisioning + inspector reads, C# client, Unity, Ledger — the verb/route/error and timeout tables | — |
| `eval-harness.md` | judged eval harness: judge-free metrics + metrics route (stage 1); runner, judge, ablation (stages 2–4) | — |
| `deferred-writes.md` | deferred write processing: the pending window, the enrichment worker, the completion contract | 006 |
| `reflection.md` | reflection (C2): the reflect verb + optional default-OFF worker, evidence-cited beliefs, the mechanical component trim | 007 |
| `parameter-compiler.md` | the parameter compiler (C3): beliefs compiled into per-scene-type weight multipliers, the standalone worker | 008 |

**Note on `migration-01.md`:** it documents migration **001 only**. Migrations 002–008 live in
`db\migrations\`; for the current schema, read the SQL.

---

## Integrator guides

Written for the person wiring this into a game, not for the build. Public pages in Jack's
voice (zero em-dashes by ruling); the third of the set is `identity-authoring.md` above.

- **`first-npc.md`** — your first NPC in about thirty lines: the exact create-agent request,
  the MonoBehaviour call order (observe → say → scene boundary + drain, and why that order),
  persisting the agent UUID, real calendar time vs `as_of`. Written F1 (2026-09-03).
- **`shipping.md`** — shipping a game with this: who hosts it and who pays for keys, the
  per-player cost math, why player-local distribution is a non-starter, the trust model (no
  auth; loopback by default; the reverse-proxy recipe), Steam's live-AI disclosure rules, the
  platform matrix (WebGL no), and the erase flow. Written F1 (2026-09-03).

---

## Discipline

- **`test-suite.md`** — what the tests must and must not assert. The one rule: structural only,
  never generated prose. Also the degradation-ladder and route-contract inventories — the
  consolidated failure-behavior reference for integrators.
- **`SETUP.md`** — bring-up, tests, C# build, the embedded Unity package, teardown.

---

## The working record

The project's full build record — the append-only decision register, session log, and floors
ledger, the live status file, the per-layer build-history specs, the July 2026 research sweep,
the dated external audits, and the demo choreography — is maintained in the working tree but
stays out of the public tip (leaned 2026-09-11): it documents the build, not the integration.
The README's verification section summarizes what it holds and how the loop runs.

---

## Vocabulary

Two words appear constantly and are defined nowhere else:

- **walker** — one of the sixteen `tests\verify_*.py` scripts. Each walks a single layer's
  done-when criteria end to end against a scratch database and prints
  `ALL CHECKS PASSED (N assertions)`. Run by hand and at floor verification; they are the
  *evidence* behind a row in the floors ledger.
- **suite** — the pytest scenarios in `tests\test_*.py`. Self-managing scratch DB, offline,
  keyless, deterministic; the turn-end hook runs the `-m "not nlp"` subset after every session
  turn. This is the *regression net*.

They overlap deliberately: a walker proves a layer once, thoroughly, at build time; the suite
keeps it proven forever, cheaply.

- **floor** — a layer that has been independently verified and can be built on. Floors are
  **re-openable**: re-verifying one is a normal step, never an argument against a change.
