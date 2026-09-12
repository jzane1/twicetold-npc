# twicetold-npc — operating rules for Claude Code

Long-term-memory service for game NPCs: FastAPI + Postgres/pgvector backend + Unity-embeddable
client package. This file is rules. Design knowledge lives in docs/ — point, don't duplicate.

## Current state (auto-loaded; a local file — the internal record is not in the public tip)
@docs/status.md

## Read before building
- docs/README.md — the index: what every file in docs\ is for, and the reading order.
- docs/architecture.md — design truth. Read the relevant sections before touching any layer.
- docs/decisions.md — append-only decision register with rationale. Never edit old entries.
- docs/migration-01.md — the FOUNDATIONAL schema (001). Migrations 002–008 live in
  db\migrations\ and are not restated there. docs/test-suite.md — test discipline.
- docs/floors.md — the verified-floors table (evidence per layer). Not auto-loaded; read it
  when you need to know what a floor actually proved.
- docs/session-log.md — append-only narrative history. Not auto-loaded; read it for context on
  why something is the way it is.
- docs/SETUP.md — clone-to-running, for a fresh machine.

## Environment — hard rules
- Windows 11. ALWAYS PowerShell syntax and backslash paths in commands, scripts, and anything
  shown to the operator. Never bash syntax.
- Python 3.14 (global, on PATH). Postgres 16 + pgvector via Docker (pgvector/pgvector image).
- Secrets live only in .env at repo root. Never print, log, or commit .env contents.
- C# root namespace: NpcMemory. The client ships as an embedded UPM package (settled F2,
  2026-09-12) at unity\Packages\com.jacksonzane.twicetold-npc\ (Runtime\Core is the
  engine-agnostic core, Runtime\ the MonoBehaviour adapter). NpcDemoDriver stays under
  Assets\Scripts\ as the project dev rig, not shipped. There is no committed DLL: the dotnet
  harness compiles the same Runtime\Core sources via client\NpcMemory.Core\NpcMemory.Core.csproj.

## Stack constants — do not substitute
- FastAPI; psycopg v3 with AsyncConnectionPool; hand-written SQL. No ORM, no query builder.
- UUID primary keys minted server-side. Embedding dimension 1536, locked.
- The schema evolves by numbered migration (ruled 2026-07-17). When the correct design needs a
  column, table, or index, the target adds migration NNN via the db\migrate.py ledger, updates
  the schema docs, and the floor re-verifies (migrate idempotency + walkers). "No new migration"
  may appear in a spec only as a per-target scope fact Jack explicitly ruled — never as an
  inherited default.
- **An APPLIED migration is immutable — including its comments** (ruled 2026-07-28). Once a file
  is recorded in `schema_migrations`, the ledger attests to those exact bytes and `migrate.py`
  has no checksum to catch a rewrite. Corrections go in a new numbered migration or in the docs
  that reference it. A stale path inside an applied migration's comment stays stale on purpose.
- Model roles are env vars, never hardcoded. **Six exist today** (`TWICETOLD_MODEL_` + IMPORTANCE,
  RENDER, TYPOLOGY, ESCALATION, DIALOGUE, RECONSTRUCTION), all six required in real mode. One
  documented limit: v1's single write call serves importance+render+typology, so those three vars
  must name the SAME model (`load_settings` errors if they diverge — never a silent pick).
  **The backend is a knob too** (the provider-path build, ruled 2026-09-01, shape ruled
  2026-09-02): `TWICETOLD_MODEL_BACKEND` = `anthropic` (default; today's requests byte-for-byte)
  | `openai` (any OpenAI-compatible chat-completions server behind `TWICETOLD_MODEL_BASE_URL`,
  optional `TWICETOLD_MODEL_API_KEY`) for ALL nine LLM roles, one `ChatBackend` seam in
  `app\providers.py`; the openai backend's token-limit FIELD is the
  `TWICETOLD_MODEL_TOKEN_LIMIT_FIELD` knob (ruled 2026-09-03, built 2026-09-11):
  `max_tokens` (default; local servers) | `max_completion_tokens` (hosted reasoning-class
  models) — field name only, values unchanged, the non-default value refused under anthropic;
  the embedding role has its own `TWICETOLD_EMBEDDING_MODEL` (the model NAME
  is a knob, default `text-embedding-3-small`; the 1536 DIMENSION stays locked and is fitted at
  the seam — narrower zero-padded, wider refused), `TWICETOLD_EMBEDDING_BASE_URL`, optional key.
  Misconfigurations are loud at load; fake mode reads no URL or key. The small-model quality
  warning ships beside the knob (`.env.example`, `docs\SETUP.md` §4b).
  The retrieval gate is non-LLM — there is no gate model. The diegetic-correction retell
  reuses the RECONSTRUCTION role (C4, ruled 2026-08-17 — no new var; the defend-vs-update
  decision itself is mechanical, no model call). (`dialogue` streams pure prose — the dialogue turn's only model call; the `behavior`
  role was removed by the A1 re-shape, 2026-08-04. Three more vars are judge-shaped — loaded in
  both modes, required by NEITHER, loud at first real use: `TWICETOLD_MODEL_JUDGE`,
  eval-runner-only (B2, 2026-08-07); `TWICETOLD_MODEL_REFLECTION`, the reflect verb's role
  (C2, built 2026-08-15 — `build_reflection_provider` raises `ConfigError` at the first real
  reflect without it; the server starts fine); and `TWICETOLD_MODEL_COMPILER`, the compiler
  worker's role (C3, built 2026-08-17 — the same shape; C3 has no endpoint, so the first real
  compile is always the worker's, which lands a `failed` run row and logs loud once).)
- Python formatting: ruff, enforced mechanically by a PostToolUse hook. Don't hand-format.

## Invariants — never violate, regardless of how a task is worded
- Non-destructive bi-temporal storage: supersede by setting invalid_at. Never UPDATE stored
  content in place. Never DELETE rows — the purge carve-out is the sole exception (built C6,
  2026-08-18 — per-memory `DELETE /v1/memories/{id}`; extended 2026-09-02 by the per-agent
  `DELETE /v1/agents/{id}/memories`, the same seven-table delete over every memory of one
  agent — both over ONE statement list in `app\db.py`, reflections surviving under either). This governs
  memory content (memories / memory_details and their chains, including the fact-version chain —
  migration 002, built 2026-07-18, docs\fact-level-correction.md); the one runtime scalar —
  memories.pinned (pin toggle) — is deliberately updated in place and sits outside it, and so
  does the ONE-SHOT NULL→value completion of a deferred row's chainless write-time scalars +
  the enrichment bookkeeping flags (ruled 2026-08-12, docs\deferred-writes.md — the original
  write finishing under the enrichment_pending guard, never a mutation of a stored value; the
  render itself supersedes, it never overwrites). (A second sanctioned scalar,
  agents.reputation, was removed by the A1 re-shape 2026-08-04; the column stays in the schema,
  unwritten and unread — a dialogue turn persists nothing.)
- Recency decay and bi-temporal invalidation are distinct mechanisms. Never conflate them.
- Read endpoints **that run retrieval** always return memory IDs and scores alongside prose. The
  test suite dies without this. Carve-out (ruled 2026-07-27, propagated 2026-07-28; third member
  2026-07-29; FOURTH member 2026-08-17): the two inspector reads — `GET /v1/memories/{id}/chain`
  and `GET /v1/agents/{id}/memories` — the judge-free metric read
  (`GET /v1/memories/{id}/reconstruction-metrics`, eval-harness.md), and the agent-state read
  (`GET /v1/agents/{id}/state`, C5 — unity-client.md) run no retrieval, so no scores exist to
  return; they carry IDs and structured fields (the metric read: IDs + numbers) and are unscored
  *by contract*, not by omission.
- Nothing integrator-configurable is ever hardcoded: vocabularies, thresholds, model roles, knobs.
- Within a scene, absent a diegetic event, an authorial correction on a memory, a
  deferred-enrichment completion (the third sanctioned text-change cause, ruled 2026-08-12,
  docs\deferred-writes.md — the window is bounded by the worker's poll interval), or a
  reflection-trim cache eviction (the FOURTH sanctioned cause, ruled 2026-08-15 and built with
  C2, docs\reflection.md — a mechanically pruned component evicts the affected memories'
  reconstruction caches; integrator guidance: reflect at scene edges and the window vanishes),
  repeated reads return byte-identical text (correction added by the 2026-07-17
  authorial-correction ruling).

## Working discipline
- IMPORTANT: Build only what the task names. If adjacent work seems necessary, stop and report
  instead of expanding scope.
- Stop and report on: ambiguity, a failed verification, any [SETTLE-AT-BUILD] tag, any conflict
  between the task and docs/. Never resolve an architectural fork yourself — surface it.
  Decisions are Jack's. The report must include the architecturally correct option even when it
  exceeds the task's scope, with its real cost stated — "bigger than this task" is a sequencing
  note, never a rejection reason (ruled 2026-07-17).
- Staged verification: verify each layer against the known-good layer beneath it before building
  on top. Renamed or ported code is re-verified before it counts as a floor.
- Floors are re-openable (ruled 2026-07-17). The walkers and floor-verifier exist to make
  revision safe and cheap — re-running them is the normal cost of a design improvement, never an
  argument against one. When presenting options, state re-verification as the step it is, not as
  a design cost.
- The August deadline never drives a decision. Flag deadline pressure; never act on it without
  Jack's explicit confirmation.
- Instrument at the seam: when building a layer, add its timing and token accounting in the
  same task.

## The public tip is lean (ruled 2026-09-11)
The internal record — the four registers (`docs\status.md`, `docs\decisions.md`,
`docs\session-log.md`, `docs\floors.md`), the built/retired layer specs (write-path, read-path,
reconstruction, authorial-correction, fact-level-correction, cli-harness, dissonance,
split-brain-streaming), `docs\research\`, the two external audits, `demo-beat-script.md`,
`mcp-setup.md`, the raw `data\eval\gold\*-artifact.json` dumps, and the Unity capture — is
**untracked-local** via `.gitignore`. The files keep their exact paths, every rule about them
still applies, and wrap-ups still update the registers; they are simply never part of a commit,
so their only backup is this machine. **Never run `git clean -fdx` (or any -x clean) in this
repo** — it would destroy the record.

## End of every task
1. Update the living record (split three ways 2026-07-28 so status.md stays cheap to auto-load):
   - **docs/status.md** — Last-updated date, the phase header if the phase moved, and any queue
     changes. Keep it live state only; do not let history accumulate here again. **Size tripwire
     (ruled 2026-08-17): status.md leaves every wrap-up at or under ~12 KB.** Past the line, move
     history verbatim into session-log.md's archive section — trimmed, never deleted (the
     session-effort audit measured the auto-loaded boot cost; the dated decisions.md entry).
   - **docs/session-log.md** — append ONE entry for the session, honest about what landed, what
     was blocked, and what was abandoned.
   - **docs/floors.md** — append a row ONLY if a layer landed and the floor-verifier returned
     pass. Add the TOC line in docs/decisions.md if you appended an entry there.
2. If Jack ruled on a decision during the task, append a dated entry to docs/decisions.md.
3. Commit with a descriptive message. Never push unless asked.
