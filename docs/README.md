# docs\ — index and reading order

Written 2026-07-28 (full-repo audit). Seventeen files had accumulated here with no index; five
were reachable only by already knowing they existed. Add new files to the right group below.

---

## Start here

| If you want to… | Read |
|---|---|
| get it running | **`SETUP.md`** — clone to running system, PowerShell throughout |
| understand what it *is* | **`architecture.md`** — the design truth |
| know where the project stands today | **`status.md`** — live state + queues (auto-loaded into every session) |
| know why something is the way it is | **`decisions.md`** — append-only ruling register, with an index |
| know what has actually been proven | **`floors.md`** — the verified-floors table |
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
| `docs\` | design truth, specs, the integrator guides, the registers (this index) |
| `.claude\` | the AI-pair apparatus: auditor agents, hooks, session commands |

---

## The four registers

These are the living record. They have different jobs and different rules.

- **`status.md`** — *live state only.* Current phase, open questions, the roadmap. Small on
  purpose: `CLAUDE.md` auto-loads it into every session, so anything that is not current state
  costs tokens forever. Update at the end of every session.
- **`session-log.md`** — *append-only narrative.* One entry per session: what landed, what was
  blocked, what was abandoned. Also holds the archived phase headers. Never edit a past entry.
- **`floors.md`** — *append-only evidence.* One row per verified layer, recording what was
  actually re-run. A row lands only after an independent floor-verifier pass returns **pass**.
- **`decisions.md`** — *append-only rulings.* What was decided, what it beat, and why. Never edit
  an old entry except to add a dated *superseded* note. Has its own index.

*(The first three were one 1,294-line file until 2026-07-28. It was split because ~36k tokens
rode into every session and the file had grown too large to hand-maintain accurately.)*

---

## Design truth

- **`architecture.md`** — the whole system in thirteen numbered sections: principles, data model,
  write path, read path, reconstruction, correction verbs, turn topology, instrumentation,
  integrator surface, positioning. Read the sections your task touches *before* touching a layer.
  Changes only when the design changes.

---

## Build-target specs

One per layer, in build order. Each consolidates the relevant architecture sections into a
buildable target with Gherkin done-when criteria, then carries a **dated BUILT banner** recording
that it shipped and was floor-verified. They are history plus contract: the banner tells you the
spec is no longer a plan.

| Spec | Layer | Migration |
|---|---|---|
| `migration-01.md` | the foundational schema — 9 tables, CHECKs, indexes | 001 |
| `write-path.md` | ingest seam, NLP pass, escalation, atomic insert | — |
| `read-path.md` | retrieval seam, decay math, scoring | — |
| `cli-harness.md` | the dialogue-turn seam, REPL, load driver | — |
| `reconstruction.md` | the thesis mechanism: identity-conditioned retelling | — |
| `authorial-correction.md` | the operator correction verb | — |
| `fact-level-correction.md` | the fact-version chain — retrieval follows the fix | 002 |
| `mid-dialogue-gate.md` | conditional retrieval mid-scene | 003 |
| `split-brain-streaming.md` | RETIRED 2026-08-04 (the A1 re-shape) — historical spec of the concurrent prose + behavior topology; the living seam is `architecture.md` §9 | — |
| `unity-client.md` | SSE + provisioning + inspector reads, C# client, Unity, Ledger | — |
| `eval-harness.md` | judged eval harness: judge-free metrics + metrics route (stage 1); runner, judge, ablation (stages 2–4) | — |
| `deferred-writes.md` | deferred write processing: the pending window, the enrichment worker, the completion contract | 006 |
| `reflection.md` | reflection (C2): the reflect verb + optional default-OFF worker, evidence-cited beliefs, identity consolidation, the mechanical component trim; dossier + spec + BUILD all 2026-08-15 | 007 |
| `parameter-compiler.md` | the parameter compiler (C3): live beliefs compiled into per-scene-type weight-multiplier bundles, the standalone third worker (no endpoint), the all-mechanical staleness guard; rulings + BUILD 2026-08-17 | 008 |
| `dissonance.md` | the dissonance path + diegetic-correction event (C4): the mechanical defend-vs-update formula, the chain-preserving confrontation verb (`rationalization` \| `update_with_resentment`), tellings-only; rulings + BUILD 2026-08-17 | — (the `corrections` table waited in 001) |

**Note on `migration-01.md`:** it documents migration **001 only**. Migrations 002–008 (fact
versions, fact entities, the lexical index, `escalation_failed`, deferred writes, reflection
runs, the parameter compiler) are specced in the targets above and live in `db\migrations\`.
For the current schema, read the SQL.

---

## Integrator guides

Written for the person wiring this into a game, not for the build. Public pages in Jack's
voice (zero em-dashes by ruling); the third of the set is `identity-authoring.md` below.

- **`first-npc.md`** — your first NPC in about thirty lines: the exact create-agent request,
  the MonoBehaviour call order (observe → say → scene boundary + drain, and why that order),
  persisting the agent UUID, real calendar time vs `as_of`. Written F1 (2026-09-03).
- **`shipping.md`** — shipping a game with this: who hosts it and who pays for keys, the
  per-player cost math, why player-local distribution is a non-starter, the trust model (no
  auth; loopback by default; the reverse-proxy recipe), Steam's live-AI disclosure rules, the
  platform matrix (WebGL no), and the erase flow. Written F1 (2026-09-03).

---

## Discipline and runbooks

- **`identity-authoring.md`** — the integrator guide to authoring an agent: seed identity,
  diagnosticity goal, config knobs, memory-prose register, `drift-validate`, and the held-out
  arm. Written Phase E1 (2026-08-19) and proven on the demo NPC. Read after `architecture.md`
  §4 and §9 for the concepts, before `eval-harness.md` for the tooling it drives.
- **`demo-beat-script.md`** — the E3 recording's choreography: the three beats + close, the
  rig, the timeline, and the rehearsal checklist (the inspect-then-re-provision guard).
  Written Phase E2 (2026-08-19); reads on top of `identity-authoring.md` §6 and §8.
- **`test-suite.md`** — what the tests must and must not assert. The one rule: structural only,
  never generated prose. Also the degradation-ladder and route-contract inventories.
- **`SETUP.md`** — bring-up, tests, C# build, DLL refresh, Unity, teardown.
- **`mcp-setup.md`** — reproduction runbook for the read-only Postgres MCP and the Unity bridge.
  Both live; neither is required by the service.

---

## Archival

Point-in-time records. They describe what was true on their date and are **not** kept current —
do not report them as stale.

- **`external-audit-2026-07-22.md`** — a four-persona read-only critique (competitor CEO, runtime
  engineer, memory researcher, skeptic).
- **`external-audit-2026-07-22-solutions.md`** — the solutions round from the same team.
- **`research\`** — the July 2026 literature sweep: `FINDINGS.md` (45 papers consolidated),
  `CHANGES-FROM-RESEARCH.md` (the provenance trace: every landed and queued change mapped to its
  source paper), and the per-paper reader notes behind them. Start at `research\README.md`. The
  source PDFs deliberately stay out of the tree.

---

## Vocabulary

Two words appear constantly and are defined nowhere else:

- **walker** — one of the sixteen `tests\verify_*.py` scripts. Each walks a single layer's
  done-when criteria end to end against a scratch database and prints
  `ALL CHECKS PASSED (N assertions)`. Run by hand and at floor verification; they are the
  *evidence* behind a row in `floors.md`.
- **suite** — the pytest scenarios in `tests\test_*.py`. Self-managing scratch DB, offline,
  keyless, deterministic; the turn-end hook runs the `-m "not nlp"` subset after every session
  turn. This is the *regression net*.

They overlap deliberately: a walker proves a layer once, thoroughly, at build time; the suite
keeps it proven forever, cheaply.

- **floor** — a layer that has been independently verified and can be built on. Floors are
  **re-openable**: re-verifying one is a normal step, never an argument against a change.
