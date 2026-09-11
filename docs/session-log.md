# twicetold-npc — Session log

Split out of `status.md` on 2026-07-28 (full-repo audit). Entries are moved **verbatim**.

This is the project's narrative record: what actually happened each session — landed,
blocked, or abandoned — in the honest wording the `/wrap-up` protocol asks for. It lived
inside the auto-loaded living file, where ~19.4k tokens of history rode into every session's
context whether or not the session needed it. It is history, and history is worth keeping and
worth not re-reading every time.

**Append-only.** Add one entry per session at the END. Never edit a past entry except to add
a dated correction note. The living state — current phase, queues, open questions — is in
`status.md`; the evidence table is in `floors.md`.

---

- **2026-07-12** — Docs established as the in-repo source of truth. Authorial seam surfaced, ruled
  (replace model), and propagated into `decisions.md`, `test-suite.md`, `migration-01.md`.
- **2026-07-12** — Claude Code workflow stack completed: CLAUDE.md files, slash commands
  (/build-task, /log-decision, /wrap-up), plan-mode default, floor-verifier and doc-auditor
  subagents, format + suite-gate hooks, .env read-deny, and MCP go-live runbooks (`mcp-setup.md`).
  This repo is now self-sufficient; the Claude Chat Project is no longer load-bearing.
- **2026-07-12** — Full-tree doc-auditor sweep. Three schema-now gaps surfaced and ruled by Jack,
  then propagated into `migration-01.md`: `scoring_failed` column on `memories`, a schema-only
  `corrections` table (diegetic correction record; mechanism deferred), and removal of the stale
  `identity_components` pruning `[SETTLE-AT-BUILD]` tag. Dated ruling appended to `decisions.md`
  (also fixes the drift-anchor wording to "the corrected head"). Re-audit clean — migration 01 is
  unblocked with no known schema omissions.
- **2026-07-13** — DB + MCP floor stood up ahead of migration 01. Committed `docker-compose.yml`
  runs `pgvector/pgvector:pg16` as `longmem-pg` (secrets interpolated from the new gitignored
  `.env`, the connection-string source); pgvector 0.8.5 confirmed available (extension enable
  deferred to migration 01). Postgres MCP registered local-scope in restricted (read-only) mode and
  verified `✓ Connected`; floor-verifier given its `mcpServers: postgres` line + MCP-preference
  directive. **Runbook deviation:** `postgres-mcp`'s `pglast` dep has no Python 3.14 wheel and won't
  build on Windows, so the MCP runs in an isolated uv-managed Python 3.13 venv (project stays on
  3.14; recorded in `decisions.md`, and `mcp-setup.md` §1 wants a matching one-line note). Live
  in-session `/mcp` tool check still pending a Claude Code restart.
- **2026-07-13** — **Migration 01 built, verified, and committed.** Seven `[SETTLE-AT-BUILD]` forks
  ruled by Jack (see the dated `decisions.md` entry): `diagnosticity_goal` text; `decay_class`
  free-text + config map with a new `decay_class_unknown` degradation flag; `affect` as three columns
  (valence/arousal/jsonb); gist child table; `identity_relevant` boolean; HNSW cosine; Python runner
  with an atomic apply-and-record `schema_migrations` ledger. `db\migrations\001_foundation.sql` +
  `db\migrate.py` + `db\smoke_test.py` written; `requirements.txt` pins `psycopg[binary]==3.3.4`
  (global 3.14). floor-verifier returned **pass** on the live DB. **Flag:** floor-verifier couldn't
  call the postgres MCP tools (fell back to `psql`); its `mcpServers` directive isn't yet effective —
  revisit before the write path. **(Resolved 2026-07-13 — see the next entry.)**
- **2026-07-13** — **Floor-verifier MCP access fixed and verified.** Root cause was the verifier's
  explicit `tools: Read, Grep, Glob, Bash` allowlist, which filters out every `mcp__postgres__*` tool
  (the `mcpServers: postgres` line authorizes the server connection but does not override the
  allowlist — the sub-agents docs use that exact `tools` line as their canonical "can't use any MCP
  tools" example). Added the `mcp__postgres` pattern to the allowlist in
  `.claude\agents\floor-verifier.md`. Agent definitions load at Claude Code startup, so the fix took
  effect only after a restart; a read-only probe then confirmed the floor-verifier can call
  `mcp__postgres__execute_sql` (`SELECT 1` → ok). Verification is now MCP-driven as intended.
- **2026-07-13** — **Write-path v1 build target specced** (`write-path.md`). Consolidates
  architecture §4–§5 into a build spec over the frozen migration-01 schema (no new migration). Jack
  ruled three scope forks (dated entry in `decisions.md`): surface = one ingest service (the sole
  instrumentation seam) with a thin FastAPI route and a structured `IngestResult` (IDs + scores);
  v1 events = observe + scene-boundary (accept+instrument only) + pin/unpin, with correction/purge
  deferred; models = per-role provider interfaces with a real impl + a deterministic fake. doc-auditor
  run clean after fixing one unsatisfiable done-when (byte-identical two-caller payload →
  route-is-pass-through) and three schema-alignment nits. Remaining physical shapes tagged
  `[SETTLE-AT-BUILD]` for the build.
- **2026-07-13** — **Write path v1 built, verified, and committed.** Jack ruled the four major
  build forks up front (render seam confirmed; embedding failure → NULL embedding; NLP stack =
  spaCy lg + fastcoref + VADER + **Warriner VAD** — NRC-VAD failed the Apache-2.0 license gate;
  full five-trigger escalation with fail-loud hard-stop as a **build-phase stance to re-rule
  before the demo**); minor shapes approved with the plan (dated `decisions.md` entry has all of
  it). New: `app\` (config, schemas, providers, nlp, db, ingest, api, serve),
  `data\lexicons\warriner_2013_vad.csv` (CC-BY 4.0, attributed), `tests\verify_write_path.py`
  (35-assertion structural walker), `db\migrate.py --database-uri` flag (floor re-verified).
  Environment learnings recorded in `decisions.md`: `transformers<5` pin for fastcoref;
  `en_core_web_sm` needed by fastcoref internally; spaCy model installs must use pip wheel URLs
  (spaCy's downloader hits uv and dies outside a venv); psycopg async needs a SelectorEventLoop on
  Windows → serve via `python -m app.serve`. Verification ran on scratch DB `longmem_test`
  (created/migrated/dropped around the walker); floor-verifier **pass** — walker re-run
  independently, `longmem` confirmed pristine via the postgres MCP, plus an independent
  spot-check. Route pass-through proven twice: ASGITransport JSON-equality in the walker and a
  live `python -m app.serve` HTTP session (observe + pin + scene-boundary).
- **2026-07-13** — **Full-project audit (build paused at Jack's request) + remediation.** Three
  lanes: a doc-auditor full-tree sweep, a code-vs-decisions review of the write path, and
  operational/toolchain checks. **Code verdict: clean** — the implementation matches every dated
  ruling; installed deps match the `requirements.txt` pins; live `longmem` re-confirmed pristine
  (9 tables + ledger, pgvector 0.8.5, product tables empty; the container had been down only
  because Docker Desktop wasn't started). **Fixed:** (1) the ruff format hook had been silently
  dormant since it was written — ruff is module-installed, not on PATH — `format-on-edit.ps1` now
  falls back to `python -m ruff`; proven live, and the accumulated drift was normalized
  (`python -m ruff format .`, 7 files, formatting only, imports re-verified). (2) Eleven doc
  findings (4 contradictions, 7 unpropagated rulings) + 2 re-audit residuals propagated:
  `write-path.md` (BUILT banner, settle-tag/flag ruling annotations, five triggers, hard-stop
  ladder row + principles exception, IngestResult `embedding_failed`/escalation fields, the four
  build-ruled done-when bullets), `architecture.md` (five triggers, hard-stop exception in §2,
  ruled NLP stack, escalation model role), `CLAUDE.md` (escalation in the role list),
  `mcp-setup.md` (uv `--python 3.13` pglast note — closes the flagged follow-up; floor-verifier
  runbook now prescribes the `tools: mcp__postgres` allowlist, the proven fix), `test-suite.md`
  (unknown-decay-class, embedding-failure, and hard-stop degradation cases), and a
  superseded-in-part note on the 2026-07-12 decay/gist entry in `decisions.md` (the register
  header's own convention). (3) `app\config.py`'s unused `nlp_confidence_threshold` comment now
  reads RESERVED (not consulted in v1 — no confidence source exists). **No floor changed; no new
  decisions ruled** — the escalation failure-path re-rule remains the open question. Doc-auditor
  re-audit clean apart from the two residuals, which were fixed and grep-verified.
- **2026-07-14** — **Full pre/post-demo scope audit + re-slating ruling.** A read-path spec attempt
  was aborted mid-scoping at Jack's request (its tentative scoping answers discarded, nothing
  recorded). The audit found the demo as slated demonstrated the record — storage, decay,
  correction-override, gate-recollect — but not the thesis: reconstruction, the claim-axis
  carrier, sat post-August, and the 60-day drift plot beat was contingent. **Jack ruled:
  reconstruction moves pre-demo** (dated entry in `decisions.md`, superseding-in-part *Schema
  now, mechanism later*), with the schedule cost explicitly flagged and accepted. Four gap
  slatings ruled with it: authorial-correction endpoint pre-demo (after reconstruction);
  scene-boundary consumers split (reputation snapshot → dialogue turn; identity recompile →
  reconstruction, seed-prose-only document pre-demo; prompt caching → post-August); purge →
  post-August, before the public flip; reflection's August hedge resolved to explicitly
  post-August. Immediate queue re-slated; `architecture.md` §2/§7 markers updated. Doc-auditor
  re-audit: **no contradictions**; two residual annotations for the scene-boundary consumer split
  (`write-path.md`, `architecture.md` §6) fixed and grep-verified. Docs only — no code, no floors
  changed.
- **2026-07-14** — **Read-path v1 build target specced** (`read-path.md`). Consolidates
  architecture §4.2 + §6 (and the artifact queue's retrieval scoring function) into a build spec
  over the frozen migration-01 schema (no new migration). Surface was pre-fixed by the re-slating
  ruling (retrieval-only; the Sonnet dialogue call rides with the CLI harness); Jack ruled two
  scope forks at spec time (dated entry in `decisions.md`): query input = **text + reserved
  context** (`query_text` embedded as-is; location/entities/event_time accepted-not-consumed —
  slots for the post-August encoding-context term; server-side composition rejected as
  double-counting + a hidden hardcoded template), and v1 serving = **verbatim-only**
  (`read_mode = verbatim` on every item; decay math lands now as the recency score component so
  Set B asserts through scores; theta/cache/`reconstructed` land with reconstruction, which swaps
  the serving stage only — retrieval and scoring untouched, pre-warm hooks this seam). Remaining
  physical shapes tagged `[SETTLE-AT-BUILD]` for the build (wire shape, relevance mapping +
  over-fetch, recency knobs, importance_norm method, k default, `as_of` override,
  `weight_overrides` shape, empty-store behavior, embedding-failure fallback). Doc-auditor run:
  one wording contradiction — the reserved-slot mirror overstated (three of four context stamps);
  Jack ruled **affect deliberately not reserved** (query-side shape undesigned; it arrives with
  the encoding-context term), exclusion now stated in the spec — plus three residuals fixed
  (architecture §6 spec-pending marker, Set B score-surface note, empty-store settle-tag);
  grep-verified.
- **2026-07-14** — **Read path v1 built, verified, and committed.** Jack ruled the two genuine
  settle-forks at plan approval (`as_of` **adopted**; query-embedding failure → **fail-quiet
  fallback** with per-item `relevance = null`) and one build-surfaced conflict
  (**importance_norm = clamp + floor, superseding the spec's min-max suggestion** — min-max
  bounds over live rows would let an invalidated extreme row move *other* items' scores, breaking
  Set B's decay-vs-invalidation separation); the remaining shapes were approved with the plan
  (dated "Read-path build rulings" entry in `decisions.md` records all nine + the
  `(−score, memory_id)` determinism sort). New: `app\retrieval.py` (the retrieval seam),
  `app\decay.py` (THE decay implementation — the reconstruction theta check imports it at
  item 3), read wire models in `app\schemas.py`, read-only candidate SQL in `app\db.py`,
  `POST /v1/dialogue/init` in `app\api.py`, five knobs in `app\config.py`,
  `tests\verify_read_path.py` (34-assertion structural walker), and the `as_of` mechanic added to
  `tests\CLAUDE.md`'s time-travel line. Verification ran on scratch `longmem_test`
  (created/migrated/dropped around the walkers); `tests\verify_write_path.py` re-run clean
  (35/35 — shared files touched, floor intact); a live `python -m app.serve` session returned
  byte-identical items across repeated reads. floor-verifier **pass** — both walkers re-run
  independently, `longmem` confirmed pristine, independent read-only SQL spot-checks. **Flag:**
  the floor-verifier dispatch again had no `mcp__postgres__*` tools (it fell back to equivalent
  read-only `docker exec psql` checks) — the 2026-07-13 allowlist fix did not hold for this
  dispatch; revisit before the next verification. Docs propagated: BUILT banner + inline ruling
  annotations in `read-path.md`, architecture §6 built marker, dated `decisions.md` entry.
- **2026-07-14** — **CLI-harness v1 build target specced** (`cli-harness.md`). Consolidates
  architecture §9 (behavior output & turn topology) + §11 (instrumentation & load driver) into a
  build spec over the frozen migration-01 schema (no new migration). The surface was pre-fixed: the
  harness composes the two built seams (ingest, retrieval) in-process via one `run_dialogue_turn`
  seam + the single Sonnet call; no HTTP route (that rides with Unity). Jack ruled two scope forks
  at spec time (dated entry in `decisions.md`): **reputation delta = persist in-place** (UPDATE
  `agents.reputation` with clamp + sensitivity, client override wins; scene-start snapshot frozen in
  the prompt prefix until the next boundary — an in-place UPDATE of an agent-row runtime scalar, the
  same class as the existing pin-flag toggle (`set_pinned`) and likewise outside the memory-content
  non-destructive invariant;
  compute-and-return-only and non-destructive-history both rejected), and **drive surface = an
  interactive REPL over a shared session-runner core** the synthetic load driver reuses (scripted-
  only and divergent-paths rejected). The single-Sonnet reconciliation is baked in (one call carries
  prose + action directive + reputation delta; §9's "Haiku call emits a delta" is the post-August
  split-brain, not this slice). Remaining physical shapes tagged `[SETTLE-AT-BUILD]` for the build
  (`LONGMEM_MODEL_DIALOGUE` name, structured-output schema, reputation apply shape, action-vocabulary
  source, prompt-assembly block, never-blank fallback, CLI meta-command surface, load-driver shape,
  wire-model form). Docs only — no code, no floors changed. Doc-auditor sweep: **no contradictions**;
  two fixes propagated + grep-verified — the "first in-place UPDATE" wording (the `set_pinned` pin
  toggle is precedent for a runtime-scalar UPDATE) and a stale queue number (reconstruction feeds
  immediate-queue item 2, not 3), the latter also renumbered in `read-path.md`'s two reconstruction
  references at Jack's request.
- **2026-07-15** — **CLI harness v1 built, verified, and committed — the vertical slice is
  complete.** Jack ruled two forks via explicit questions at plan approval (action-vocabulary
  source = **per-call field → `agents.config` fallback**, neither → directives drop soft with
  reason, no hardcoded default vocabulary; cost units = **tokens unconditionally, USD only via
  optional `LONGMEM_PRICE_*` env vars** — pricing never hardcoded, a plan-raised choice implicit in
  the spec's instrumentation contract); the spec's remaining nine settle-tags were approved with
  the plan (dated "CLI-harness build rulings" entry in `decisions.md`; count annotation added by
  the 2026-07-16 audit).
  New: `app\dialogue.py` (the `run_dialogue_turn` seam: retrieval → labeled-block prompt assembly →
  single dialogue call → vocabulary validation → atomic clamped in-place `agents.reputation`
  UPDATE), `app\session.py` (session-runner core owning frozen-snapshot scene state — the
  scene-boundary reputation-snapshot consumer landed), `app\cli.py` (REPL,
  `python -m app.cli --agent <uuid> [--debug]`), `app\load_driver.py` (deterministic seeded
  generator or JSON script; emits §11's latency p50/p95 + itemized per-100-turn cost table),
  `tests\verify_cli_harness.py` (36-assertion structural walker), the dialogue provider triad
  (streaming real + deterministic fake + failure-injection fakes), turn wire models, reputation
  SQL, and the dialogue-role/reputation/pricing config. The CLAUDE.md invariant clarification for
  agent-row runtime scalars landed with the UPDATE, as ruled. **Build-surfaced interpretation
  flagged for Jack:** a client `reputation_delta_override` still applies on the never-blank
  degraded path (client-authoritative; the ladder's zero delta is the no-override default).
  Verification ran on scratch `longmem_test` (created/migrated/dropped around the walkers); both
  prior walkers re-run clean (35/35, 34/34); live piped REPL session + standalone load-driver run;
  floor-verifier **pass** — and its `mcp__postgres__*` tools **worked this dispatch** (the
  2026-07-14 MCP-allowlist flag resolved). Environment learnings in `decisions.md`: Windows decodes
  piped stdin with the ANSI codepage (PowerShell here-string pipes deliver a mojibake UTF-8 BOM) —
  the REPL reconfigures non-tty stdin to `utf-8-sig`. Docs propagated: BUILT banner + inline ruling
  annotations in `cli-harness.md`, architecture §6/§9/§11 built markers, queue renumbered
  (reconstruction → item 1) with refs updated in `read-path.md`/`cli-harness.md` — including
  read-path refs already stale from the prior renumber. **Known nit left in place:** stale code
  comments citing reconstruction as "item 3" — the 2026-07-16 audit found **four** such files
  (`app\api.py`, `app\decay.py`, `app\retrieval.py`, `app\schemas.py`), not the two named here
  originally; comment-only, left untouched at build time to keep the floors byte-identical.
  *(Fixed 2026-07-16 by audit ruling; walkers re-run — see that entry.)*
- **2026-07-16** — **Full-project audit + remediation (at Jack's request).** Three lanes: a
  doc-auditor full-tree sweep, a code-vs-rulings review, and operational/toolchain checks.
  **Code verdict: clean** — the only write surfaces are the atomic observe insert and the two
  ruled runtime-scalar UPDATEs; the auditor's independent spot-checks (schema SQL vs.
  migration-01.md, config knobs vs. rulings, the reputation-apply SQL shape, the dialogue seam
  vs. its rulings) all passed. **Operations: clean** — container healthy, migrate no-arg a no-op,
  `longmem` pristine, all `requirements.txt` pins match installed versions, ruff hook live,
  suite-gate hook correctly dormant until the pytest suite lands. **Docs: six findings, all in
  the 2026-07-15 wrap-up prose; Jack ruled on all of them** (dated "Full-project audit rulings"
  entry in `decisions.md`): five mechanical fixes applied and grep-verified (the missed "Item 3"
  renumber ref in `read-path.md`; the `write-path.md` scene-boundary landing annotation; the
  settle-count correction annotated onto the 2026-07-15 decisions entry; the CLAUDE.md
  "agent-row" → "runtime scalars" rewording; this log's nit sentence corrected to four files);
  the **override-on-degraded-path interpretation CONFIRMED as built** (flag closed, no code
  change); and the four stale "item 3" code comments **fixed** with all three walkers re-run on
  fresh scratch (35/35, 34/34, 36/36 — floors intact, comment-only diffs). Observations carried
  without ruling: `httpx` unpinned but used directly by two walkers; `max_tokens=1024` hardcoded
  in the three real providers (write-path-era pattern). Also this session: a CLI-harness usage
  guide was written up for Jack (operator prerequisites incl. the no-agent-provisioning-surface
  gap, the turn pipeline, meta-commands, reputation semantics, fake/real modes, load driver).
- **2026-07-17** — **Reconstruction v1 build target specced** (`reconstruction.md`). Consolidates
  architecture §7 (+ §4.2/§4.3/§6) and the 2026-07-14 re-slating scope into a build spec over the
  frozen migration-01 schema (no new migration — `reconstruction_cache`, `identity_documents`, and
  the `write_cause` enum are already live); it swaps the read path's reserved serving stage only.
  Jack ruled three scope forks at spec time (dated "Reconstruction spec scope rulings" entry in
  `decisions.md`): reconstructor input **includes the current live head** ("how you currently tell
  it" — retellings compound, the drift budget gets real work); the cache key's version component
  **composes `identity_version` with a quantized, scene-frozen decay band** (the pre-demo drift
  driver — spec-surfaced tension: a seed-only identity is static, so the plain key would
  reconstruct each memory exactly once and flatten the 60-day beat; the band both keys the cache
  and sets the thinning level); and identity-document plumbing is **hybrid, reputation-style**
  (scene-boundary handler recompiles server-side and returns `identity_version`; the caller
  freezes it as scene state and passes it per request — the handler's first real server-side
  consumer). Two derived design lines stated in the spec: **serve only persisted text** and **the
  dialogue-init route becomes a writing endpoint**. Remaining physical shapes tagged
  `[SETTLE-AT-BUILD]` for the build (theta knob, band quantum + key composition, thinning
  function, prompt + batched output schema, retry policy, drift metric + threshold, write-back
  `valid_at`,
  refusal caching, scene-state request fields, scene-boundary response shape, hash/NULL-seed/
  unknown-version shapes, wire deltas, walker shape). Propagated: architecture §7 input/cache/
  marker + §4.3/§6 plumbing notes; `test-suite.md` Set C cache-hit clause refined to "stable
  identity + same band." Doc-auditor sweep: one contradiction (the `migration-01.md` cache-column
  line still read pure-content-hash — annotated with the ruling) + five propagation residuals
  fixed and grep-verified (`read-path.md` serving-boundary key note, the register's annotation
  convention on the 2026-07-14 re-slating entry, `write-path.md` scene-boundary specced marker,
  this log's settle-tag list + the phase header's stale "nine" count). **Known nit left in
  place:** `app\retrieval.py`'s module comment still sketches the plain
  `(memory_id, identity_version)` cache key — comment-only in a floor-verified file, and the
  reconstruction build rewrites that comment when it swaps the serving stage; left untouched to
  keep this session docs-only. Docs only — no code, no floors changed.
- **2026-07-17** — **Reconstruction v1 built, verified, and committed — the thesis mechanism is
  live.** Jack ruled two forks via explicit questions at plan approval (**fake-mode drift =
  locality-sensitive fake embedding** — the drift budget surfaced that the shake_256 hash fake
  made any two texts ~orthogonal, so every fake-mode write-back would have been refused;
  `FakeEmbeddingProvider` is now trigram-bucket + L2-normalized; and **`drift_budget_threshold`
  default = 0.35** cosine distance); the spec's remaining settle-shapes were approved with the
  plan (dated "Reconstruction build rulings" entry in `decisions.md` records all of them + three
  build-surfaced shapes flagged for confirmation). New: `app\reconstruction.py` (the
  serving-stage engine: theta/band/thinning bound to the scene-frozen basis; batched retelling
  call; drift check embedding candidate + anchor at check time; atomic supersede+insert+cache
  transaction; serve-only-persisted-text), `app\identity.py` (seed-verbatim render + sha256
  version + upsert), `tests\verify_reconstruction.py` (41-assertion walker incl. the band-crossing
  and identity-bump drift drivers), the reconstruction provider triad + failure/drifting fakes,
  reconstruction SQL (identity docs, cache batch fetch, retelling sources + derivable anchor,
  write-back), wire deltas (`read_mode` three-state real; scene-state request fields;
  reconstruction counters), scene-boundary recompile (the handler's first server-side consumer),
  session-runner frozen `identity_version` + `scene_started_at`, CLI debug + load-driver
  aggregate rows, the 422 unknown-version mapping, and the `LONGMEM_MODEL_RECONSTRUCTION` role +
  three knobs. The prior read-side walkers pin `reconstruction_theta = 0` in fixture configs
  (assertion bodies untouched — the v1 serving contract holds with the stage knob-disabled;
  flagged). The 2026-07-17 known-nit (stale plain-key comment in `app\retrieval.py`) closed with
  the rewritten module docstring. Verification: all four walkers on fresh scratch (41/41, 35/35,
  34/34, 36/36); live piped REPL drift beat (verbatim → 46-day `:as-of` jump + `:scene` →
  reconstructed with write-back → call-free cache hit); standalone load-driver run; floor-verifier
  **pass** with working postgres MCP tools and independent code spot-checks. **Environment
  deviation found and flagged (not fixed):** `.env`'s DATABASE_URI names a nonexistent
  `longmem_sandbox` DB — no-arg migrate can't connect; the no-op criterion was verified against
  `/longmem` explicitly. *(Resolved the same day — see the wrap-up entry below.)*
- **2026-07-17** — **Wrap-up: the `.env` deviation is closed.** Jack restored `DATABASE_URI` to
  `longmem`; no-arg `db\migrate.py` re-verified as a clean no-op ("Up to date, 0 pending") — the
  schema-frozen criterion reads exactly as recorded for every prior floor again. The two
  build-surfaced reconstruction shapes (prior walkers' `reconstruction_theta = 0` pin;
  blind-check refusals not cached) remain flagged for confirmation in open questions.
- **2026-07-17** — **Flagged-shapes confirmation session (docs only).** Jack walked the three
  open reconstruction flags and confirmed all three as built/written (dated "Reconstruction
  flagged-shapes confirmations" entry in `decisions.md`): the prior walkers' fixture-only
  `reconstruction_theta = 0` pin (confirmed after correcting a misread — reconstruction is
  **production-active** at default theta 0.5 and has its own 41-assertion walker; the pin exists
  only in the two older walkers' fake NPCs, preserving single-cause layer isolation); blind-check
  refusals staying uncached (a transient embedding outage never pins a key); and
  pin-after-reconstruction `read_mode = "verbatim"` kept as written ("verbatim" is the
  serving-stage claim; `pinned` rides in every payload — observation closed, no spec amendment).
  No code, no floors touched. **The escalation hard-stop failure-path re-rule is now the sole
  open question.**
- **2026-07-17** — **Scope-limiter reframing (rules + docs; ruled by Jack).** The
  authorial-correction spec session was paused when Jack flagged a standing bias: rules written
  as verification discipline had hardened into design pressure — correct-but-larger options
  arrived pre-labeled "blocked", "deferred", or "would re-open a floor". A full sweep of every
  instruction surface (CLAUDE.md, docs\, tests\CLAUDE.md, .claude\) found four limiter families;
  Jack ruled the reframe (dated "Scope-limiter reframing" entry in `decisions.md`). Changes:
  CLAUDE.md gains the schema-evolves-by-migration rule, the floors-are-re-openable line, and the
  full-options report contract; this file's "Post-August ledger" renamed **"Sequenced-later
  ledger (pull-forward eligible)"** with the standing pull-forward rule, and "revisit only if
  demo latency demands" struck; architecture §2/§10 sequencing clauses became pointers to the
  queues; `/build-task` Phase 2's report contract amended. Kept deliberately: the
  deadline-never-drives rule, staged verification, the invariants, structural-only tests. Built
  specs, old register entries, and session logs stand as history. The freeze's recorded
  casualties (idempotency/dedup column, scene-boundary schema home, reputation history's schema
  objection, VAD dominance in jsonb, location description column) are now *eligible* for
  re-opening, each its own future ruling. **The authorial-correction spec resumes next — its
  four open forks re-presented fairly priced under the new framing.**
- **2026-07-17** — **Authorial-correction v1 build target specced** (`authorial-correction.md`)
  — the first spec session under the scope-limiter reframing (paused mid-forks by that ruling;
  resumed with all four forks re-presented fairly priced). Jack ruled four scope forks (dated
  "Authorial-correction spec scope rulings" entry in `decisions.md`): scope = **chain content
  now + a slated fact-level correction target** (ruled into the immediate queue as item 2,
  ahead of the gate — versioned memories-row facts + corrected embedding, migration-002-class,
  own spec session); the reconstructor's **fixed constraint follows the drift anchor** on
  corrected chains (the recommendation that flipped once floor re-verification was priced as a
  step — deliberately re-opens the reconstruction floor at build); surface = **memory-scoped
  operator verb** (the pin pattern; `/v1/events/*` stays diegetic-only) + a REPL `:correct`
  meta-command; **immediate mid-scene effect**, with the within-scene invariant's wording
  amended (CLAUDE.md, architecture §7, `test-suite.md` Set C — authorial correction is now the
  second sanctioned text-change cause). Endpoint design lines: no model calls (operator text
  byte-verbatim), no `corrections` row (diegetic-only by CHECK), one supersede-guarded
  transaction with cache eviction, fail-loud operator surface. No migration needed as a fact of
  this target. Remaining physical shapes tagged `[SETTLE-AT-BUILD]`. Queue renumbered (gate →
  3, suite → 4) with stale refs updated in `read-path.md`, `cli-harness.md`,
  `reconstruction.md`. Doc-auditor sweep: **no contradictions**; two residuals fixed and
  grep-verified — `reconstruction.md` gained the house-style constraint-follows-anchor
  annotations (scope boundary, reconstructor-input item 1, cache-contract band line — the last
  hedged as a `[SETTLE-AT-BUILD]` suggestion, not a ruling), and the register's 2026-07-12
  within-scene-invariant statement gained its amendment note per the annotation convention.
  Docs only — no code, no floors changed.
- **2026-07-18** — **Authorial-correction endpoint v1 built, verified, and committed — the
  correction-override beat is live.** Jack ruled one criterion via an explicit question at a
  mid-build stop-and-report: the spec's "time travel coherent" done-when **re-ruled to stored
  bi-temporal coherence** — its original "as_of before t_c serves the prior telling" wording
  over-claimed (`as_of` is an age-computation override by the 2026-07-14 read-path ruling; the
  candidate SQL always joins the live head); the walker asserts windowed-SQL re-derivation
  instead, and the alternative (as_of-windowed chain serving) was presented fairly priced and
  not adopted. The spec's remaining settle-shapes were approved with the plan, including the
  **compare-and-swap refinement** (optional `expected_detail_id`: stale → 409 with rollback;
  omitted → correct the live head — the REPL default). New: `apply_authorial_correction`
  (`app\db.py`, one transaction: predicate supersede + CAS + corrected head at t_c + cache
  eviction; the module's first sanctioned DELETE — derived cache rows only),
  `IngestService.correct` + `CorrectionConflictError` (`app\ingest.py`),
  `POST /v1/memories/{id}/correction` with 404/409/422 (`app\api.py`),
  `CorrectionRequest`/`CorrectionResult` (`app\schemas.py`), the anchor-cause-aware pure
  `build_reconstruction_item` + `ReconstructionSource.anchor_cause` (the constraint-follows-
  anchor delta — the reconstruction floor deliberately re-opened and re-verified, its walker
  grown 41 → 42 by addition only), `runner.correct` + the REPL `:correct` meta-command, and
  walker `tests\verify_authorial_correction.py` (31 assertions). Verification: all five walkers
  on fresh scratch (31/31, 42/42, 36/36, 34/34, 35/35); a live piped REPL correction-override
  beat (read verbatim → `:correct` head swap → corrected read, one scene; fake mode — note the
  REPL smoke now needs `$env:LONGMEM_PROVIDER_MODE = "fake"` since `.env` runs real mode);
  `db\migrate.py` no-arg a clean no-op; floor-verifier **pass** with working postgres MCP tools
  and independent code spot-checks. Queue renumbered (fact-level correction → item 1, gate → 2,
  suite → 3) with stale refs updated in `read-path.md`, `cli-harness.md`, `reconstruction.md`,
  `authorial-correction.md`.
- **2026-07-18** — **Fact-level correction v1 build target specced** (`fact-level-correction.md`)
  — immediate-queue item 1's own spec session, as slated. Consolidates the 2026-07-17 slating
  (versioned memories-row facts + corrected embedding so retrieval follows the fix) into a build
  spec; **migration 002 is a fact of the target — the first spec for which that is true** (the
  002 ledger seam designed 2026-07-13 finally gets its migration). Jack ruled four scope forks
  (dated "Fact-level correction spec scope rulings" entry in `decisions.md`), presented twice —
  technically, then re-introduced in plain prose at his request — and each ruled on the
  recommended option: **fact scope = embedding only** (importance/typology/decay/entities/affect
  stand as write-time event facts; the entities honest-deferral recorded — its first reader, the
  gate's GIN path, is queue item 2); **version shape = a fact-version child table** (the
  `memory_details` precedent applied to the semantic basis: one-live-head partial unique index +
  partial HNSW, `original` rows backfilled; read-path + write-path floors re-open at build as
  re-verification steps); **surface = one combined verb** (the correction endpoint becomes
  fact-following — corrected text is both telling head and embedded fact basis; verified
  coupling: a fact-only correction would leave reconstruction re-injecting corrected-away data
  from original-anchored gist spans); **embed failure = all-or-nothing fail-loud** (embed before
  the transaction; the honest price — an embedding outage blocks telling corrections too — was
  stated and accepted). Premise corrections verified in code before presenting: entities is
  write-only today; gist re-derivation on corrected chains has zero consumers; purge is a
  docs-only contract. Design lines: one model call stated honestly (v1's "no model calls"
  purity superseded, not silently dropped; the existing embedding role — no new model role or
  env var); the reconstruction delta is **none** (the drift check embeds text fresh; the
  corrected-anchor branch ignores spans) — `verify_reconstruction.py` re-running unmodified is
  the build's proof. Remaining physical shapes `[SETTLE-AT-BUILD]`. Propagated: CLAUDE.md
  invariant parenthetical (fact chain), architecture §4.4 (new) + §6 + §8 + §12,
  `authorial-correction.md` five annotations, `migration-01.md` 002 pointers, `test-suite.md`
  Set A fact assertions + the all-or-nothing degradation case. Docs only — no code, no floors
  changed.
- **2026-07-18** — **Fact-level correction v1 built, verified, and committed — retrieval
  follows the fix, and migration 002 is the ledger seam's first use.** Jack ruled two shapes
  via explicit questions at plan approval (dated "Fact-level correction build rulings" entry in
  `decisions.md`): **dual-write vs freeze = FREEZE** (against the dual-write recommendation —
  observe no longer writes `memories.embedding`; the `original` fact head is the sole vector
  home; the epoch split accepted; the queryable embed-degradation signal moved to the live fact
  head, and the write-path walker's signal assertion moved with it — the build's one
  non-additive walker change, ruling-driven) and **the old `memories_embedding_hnsw` dropped in
  002**; the eight mechanical shapes were approved as proposed. New:
  `db\migrations\002_fact_versions.sql` (fact chain + guarded backfill before the indexes +
  one-live-head partial unique + partial HNSW + the index drop), the fact-following verb
  (`apply_authorial_correction` grown — fact supersede + insert in the same transaction, embed
  BEFORE it; `CorrectionEmbedFailedError` → 502, the escalation precedent), the freeze at
  observe (`insert_observation` mints the fact head), the probe on the live fact head
  (`fetch_vector_candidates`; degraded path deliberately unjoined), wire deltas
  (`CorrectionResult` += fact IDs + embed_ms/embedding_tokens; `IngestResult` +=
  fact_version_id), REPL surfacing (both head swaps + embed timing), and walker
  `tests\verify_fact_correction.py` (32 assertions — incl. the db-layer distance-0
  retrieval-follows-the-fix pair, the backfill guard proven against a legacy-shaped row, and
  the correction-repairs-degraded-rows beat: correcting a NULL-fact-embedding memory re-embeds
  it into vector reach). Verification: all six walkers on fresh scratch (32/32, 38/38, 36/36,
  36/36, 42/42, 33/33 — reconstruction and CLI harness byte-untouched, `app\retrieval.py` and
  `app\reconstruction.py` byte-identical to HEAD: the no-reconstruction-delta proof); migration
  002 applied to `longmem`, no-arg migrate → "Up to date: 2 applied, 0 pending"; `longmem`
  pristine via the postgres MCP; floor-verifier **pass**; and a live piped REPL beat where the
  same query's relevance moved 0.4686 → 0.5637 across a `:correct` — the fix moving recall,
  visible in the debug view. Queue renumbered (gate → 1 and it inherits the entities fact-chain
  column, suite → 2, Unity → 3, pre-ship gates → 4).
- **2026-07-19** — **Mid-dialogue gate v1 build target specced** (`mid-dialogue-gate.md`) —
  immediate-queue item 1's own spec session. Consolidates architecture §6 (gate + degradation
  ladder + the prompt-caching boundary), §4.3 (the two identity structures), §7 (the mid-scene
  block-with-signal miss path deferred here by `reconstruction.md`), §11 (efficacy definitions
  + the reserved gate-check latency term), and the 2026-07-18 entities honest-deferral into a
  build spec; **migration 003 is a fact of the target — the second spec for which that is
  true**. Jack ruled five scope forks (dated "Mid-dialogue gate spec scope rulings" entry in
  `decisions.md`; forks 1/2/4/5 re-presented in plain prose at his request and ruled on the
  re-presentation): **loaded set = caller-held scene state** (reputation-style; absent fields ⇒
  loader turn ⇒ v1 byte-parity); **migration 003 entities = FREEZE** (fact head the sole home;
  guarded backfill; partial GIN on live heads; `memories_entities_gin` dropped;
  `memories.entities` frozen — the coverage-check-consistency argument was decisive);
  **correction entities = NLP pass + optional operator field** (observe's merge mirrored — the
  fact-level NLP-re-pass rejection's premise ends with this target); **per-signal fire logs =
  instrumentation-only** (`gate_events` stays pull-forward eligible); **reconstructing signal
  = post-hoc fields + an in-process pre-serve callback** (fields-only was un-recommended
  mid-session — it cannot show anything *during* the pause; the reconstruction floor re-opens
  at build for one defaulted parameter, a step priced as a step). The fruitless damper stays
  `[SETTLE-AT-BUILD]` with a full suggested mechanism, flagged promotable. Design lines: one
  embed per turn (the novelty embedding IS the probe); tripwire = live `identity_components`
  vs coverage = fact-head entities (keyed fetch) + degraded fetch = their partial GIN — never
  conflated; the reserved
  read-request slots stay inert; loaded set append-only within a scene; caller-side reset (no
  fourth scene-boundary server consumer); CLAUDE.md deliberately unchanged (which memories
  surface was never under the byte-identity guarantee). Propagated: architecture §4.4/§5/§6/§11
  annotations, register annotations (audit ruling #3 GIN home; fact-level fork-1 deferral
  closed), `fact-level-correction.md`, `reconstruction.md`, `read-path.md`, `cli-harness.md`,
  `authorial-correction.md`, `migration-01.md` 003 pointers, `test-suite.md` **Set D** (new,
  ~8–10 scenarios) + ladder-row pointer. Docs only — no code, no floors changed.
- **2026-07-19** — **Mid-dialogue gate v1 built, verified, and committed — retrieval is
  conditional, and the reserved §11 gate term is live.** Jack ruled two shapes via explicit
  questions at plan approval (dated "Mid-dialogue gate build rulings" entry in `decisions.md`):
  **damper = as suggested** (fruitless = zero new IDs; 2 consecutive suppress novelty for the
  scene remainder; tripwire live; scene reset — the spec's promotable flag closed) and
  **correction-path NER failure = clean loud error** (`CorrectionNlpFailedError` → 502, the
  embed precedent; nothing written). The remaining shapes were approved with the plan, incl.
  **`gate_enabled`** (fixture pin + kill-switch scaffold). New: `app\gate.py` (pure decision
  module — the decay.py precedent; named signal constants, the `TRIGGER_*` mirror),
  `db\migrations\003_fact_entities.sql` (entities fact-chain column + guarded backfill +
  partial GIN on live heads + old GIN dropped; applied to `longmem` — "001 + 002 + 003
  applied, 0 pending"), the gated/loader branch in `app\retrieval.py` (loader = v1
  byte-parity; closed = zero probe SQL; fire = SQL-excluded probe reusing the turn's one
  embed, or the GIN entity-only rung), the entities freeze at observe + `GateRow` + three
  gate fetchers (`app\db.py`), the correction NER merge (`app\ingest.py` + 502 in
  `app\api.py`), the fork-5 pre-serve callback (`app\reconstruction.py`, one defaulted
  param), caller-held loaded-set/streak state (`app\session.py`), the prompt recollection
  partition (`app\dialogue.py`), `GateInstrumentation` (`app\schemas.py`), four knobs
  (`app\config.py`), the CLI gate line + `(reconstructing…)` print, and the load-driver
  `gate_check` series + gate block. Walker `tests\verify_gate.py` (**51 assertions**); prior
  walkers 40/40 (write, +2 freeze), 36/36 (read, **byte-untouched** — the loader-parity
  proof), 36/36 (CLI, pin + label only), 42/42 (reconstruction, pin only), 34/34 (authorial,
  +1), 34/34 (fact, +2), each on fresh scratch; floor-verifier **pass** with working postgres
  MCP tools; live piped REPL beat with **`(reconstructing…)` printed during the blocked
  mid-scene turn**; standalone driver run with real gate fire/efficacy rows.
  **Build-surfaced learnings** (recorded in `decisions.md`): pgvector rows need `.to_list()`
  (the bug hid behind the fail-quiet ladder — the loader fallback worked as designed);
  fake-mode calibration corrected (ordinary distinct prose ~0.45–0.75, not ~1.0; the 0.5
  threshold stands; guaranteed-novel fixtures need trigram-rare wording — chosen by
  measurement). Queue renumbered (suite → 1, Unity → 2, pre-ship gates → 3); the gate
  pointers in prior specs gained "built" markers.
- **2026-07-20** — **Structural pytest suite v1 built, verified, and committed — the
  suite-gate Stop hook is live.** `docs\test-suite.md` was already the spec, so the session
  went plan-mode orient → three explicit-question rulings → scoped build (dated "Test-suite
  build rulings" entry in `decisions.md`): **the Stop hook runs the `-m "not nlp"` subset**
  (the 7 marked scenarios call the write pass at the service level and pay the lazy
  spaCy+fastcoref load — measured: full suite 82 s cold / ~30 s warm, subset ~14 s);
  **Postgres unreachable ⇒ loud clean skip, exit green** (the hook's dormant philosophy
  extended to the DB prerequisite; pure no-DB scenarios still run); **CI-ready now,
  workflow later** (public-flip-sprint home; until then regressions are caught
  on-machine — stated and accepted). New: `pytest.ini`, `tests\conftest.py` (scratch
  **`longmem_suite`** lifecycle, deliberately distinct from the walkers' `longmem_test`;
  db-layer `InsertPlan` seeding with the pure fake embedding so unmarked scenarios never
  trigger the loaders; per-set configs with production-vs-fixture pins stated), and 38
  scenarios across `test_set_a_correction.py` (8), `test_set_b_decay.py` (5),
  `test_set_c_reconstruction.py` (7), `test_set_d_gate.py` (9), `test_degradation.py` (9);
  `requirements.txt` pins pytest 9.1.1 + httpx 0.28.1 (closing the 2026-07-16 unpinned
  observation). `app\`, `db\`, and all seven walkers byte-untouched — the floors stand by
  construction. floor-verifier **pass** on all nine criteria (two independent full-suite
  runs, the keyless subset run, the unreachable beat, the hook contract both ways, the
  structural-only audit, migrate no-op, `longmem` pristine via the postgres MCP with no
  scratch residue). The escalation hard-stop test asserts the current build-phase stance
  and says so in its docstring — the owed re-rule changes exactly that test. Queue
  renumbered (Unity → 1, pre-ship gates → 2).
- **2026-07-20** — **Fake-mode latency/compute pass + two measured perf fixes + a
  suite-concurrency fix (Jack ordered the profiling, then ruled "apply both").** A
  scratchpad-only profiler (load-driver instrumentation + `EXPLAIN ANALYZE` + a cProfile of
  the NLP pass + a psycopg vector-param micro-benchmark) found two big, corpus-independent
  pits — full write-up in the dated "Latency-fix + suite-concurrency rulings" entry in
  `decisions.md`. Fixes (three files, no floor behavior changed): **(pit #2)** `app\db.py` —
  the four vector-probe queries bind the 1536-dim query vector as a **named** param so it
  rides the wire once instead of twice, killing a ~44 ms Windows-loopback Nagle/delayed-ACK
  stall (server did the query in 1.3 ms; EXPLAIN confirms HNSW used); **reads ~54 ms →
  ~5–10 ms, a gate fire ~55 ms → ~7 ms** (measured). **(pit #1)** `app\nlp.py`
  `_tame_datasets_fingerprint()` (called from the `_coref()` loader) — `disable_caching()` +
  a guarded short-circuit of the `datasets` fingerprint Hasher, which otherwise dill-pickles
  fastcoref's internal spaCy model every observe; coref output unchanged; **writes ~215 ms →
  ~63 ms** (measured). **(b)** `tests\conftest.py` — scratch DB is now `longmem_suite_<pid>`
  so two overlapping suite runs (the Stop hook fires one per turn-end) can't force-drop each
  other (the `AdminShutdown` false-RED seen during the profiling turns). Re-verified: full
  suite **38/38**, all seven walkers green (40/36/36/42/34/34/51 on fresh scratch), migrate a
  clean no-op, `longmem` pristine, no scratch residue. The pit #1 fix is the one library
  monkeypatch — guarded to degrade to the slow-but-correct path; flagged as a version-fragility
  cost, trivially revertible. Deferred (recorded in the decisions entry): connection-per-query
  churn (secondary); and a real-mode COST flag — escalation fired 24/40 (60%) on realistic
  prose, each an extra LLM call in real mode. **Next: a real-mode smoke run to confirm the
  end-to-end picture, then the demo work.**

- **2026-07-20 → 21** — **Research sweep + adoption slate: Target A (encoding-context term)
  built, floor-verified, and committed.** A 45-paper literature sweep (31 curated + 14
  arXiv-discovered; map-reduce reader agents against a baseline brief; consolidated in
  `docs\research\FINDINGS.md` — *at the time, gitignored working material under
  `Research Papers\`; tracked and moved 2026-07-28*) found the two
  biggest gaps already on our radar (no judged eval harness; no graph/associative retrieval)
  and one strictly-better mechanism with a slot already reserved: RaMem-style encoding-context
  re-ranking. Jack ruled the adoption slate via four explicit questions (dated
  "Research-adoption slate + encoding-context build rulings" entry in `decisions.md`): two
  targets now (A: context term + TARG calibration; B: hybrid lexical channel), context =
  client-supplied fields (no LLM decomposition — the 2026-07-14 as-is ruling stands), the
  queued eval harness includes judged categories from v1, recall-reinforced decay gets its own
  future session. **Target A landed:** the three reserved request fields are consumed as a
  soft multiplicative score nudge (entity coverage on live fact heads + event-time kernel +
  location match; ≥ 1 always, never a filter), byte-identical v1 scoring when absent (the
  parity contract), knobs per-agent overridable, instrumentation-level surfacing so
  `app\reconstruction.py`/`app\gate.py`/`app\decay.py` stay byte-identical to HEAD; plus the
  report-only `--gate-budget` calibration recipe. Read-path walker 36 → 42 (criterion [7]
  re-scoped — the one ruling-driven change); suite 38 → 40; floor-verifier **pass** with
  working postgres MCP tools; live REPL `:context` beat (exact ×1.75). No migration. A
  mid-session laptop crash cost nothing: the working tree survived and every check re-ran
  green post-crash.
- **2026-07-21** — **Target B (hybrid lexical channel) built, floor-verified, and committed —
  the research-adoption slate is landed.** Migration 004 (index-only: partial FTS GIN over
  live fact heads) + a token-OR lexical candidate fetch unioned into the loader's vector
  over-fetch before scoring — dedup exact, scoring formula untouched, lexical hits carrying
  true cosine relevance, NULL-embedding rows lexically reachable with relevance null (the
  embed-degradation consequence honestly softened; read walker criterion [9] sharpened to
  assert the vector-path exclusion on the probe itself). **Build-surfaced correction:**
  websearch/plainto AND semantics would have made the channel inert for utterances — the
  token-OR shape (casefolded ≥3-letter runs, capped 16) was built instead, recorded in the
  dated "Hybrid lexical channel build rulings" entry. `lexical_fetch_k` kill-switch (0.0 =
  pure-vector v1); `text_search_config` string knob ('simple' baked into the index expression,
  overrides run unindexed — stated). Read walker 42 → 48; gate walker's ledger pin +004 (its
  sole change); suite 40 → 41 + keyless subset 34/34; 004 applied to `longmem` ("4 applied,
  0 pending", idempotent); floor-verifier **pass**; live k=1/overfetch-1.0 REPL beat (the
  pinned rare-name row served via lexical-only reach, `lex=2 candidates=2 k=1`). Session end:
  the research queue items slated (immediate queue 3–6), and
  `docs\research\CHANGES-FROM-RESEARCH.md` written (*gitignored then; tracked 2026-07-28*)
  tracing every landed and queued change to its source papers for the future README.
- **2026-07-21** — **Real-mode testing session: pre-ship gates (b) and (c) closed — real mode
  proven end-to-end, after a build-surfaced parse fix (the first session ever to construct
  the real providers).** Env preflight: real mode requires all six model vars —
  `LONGMEM_MODEL_RECONSTRUCTION` was missing from `.env`; Jack ruled it **`claude-sonnet-5`**
  (env-injected this session; the `.env` line is his to add) and ruled the run **priced at
  standard rates** (the nine `LONGMEM_PRICE_*` per-Mtok: sonnet-5 3.00/15.00,
  haiku-4.5 1.00/5.00, embedding 0.02 — intro pricing declined so the cost table stays honest
  after 2026-08-31). **The first smoke FAILED and surfaced a real defect:** sonnet-5 emits a
  leading thinking block, so `content[0].text` crashed reconstruction with an uncaught
  AttributeError; haiku-4.5 wrapped its escalation JSON in markdown fences 3/3 despite
  "No other text" — every escalating observe hard-stopped. **Jack ruled parse-side
  hardening** (dated "Real-mode parse hardening ruling" entry in `decisions.md`; commit
  `1388bf6`): `_first_text_block` + `_lenient_json_text` at the four JSON-in-text parse
  sites in `app\providers.py`; fakes/prompts/seams untouched; re-verified suite 41/41 ×2 +
  all seven walkers green (40/48/36/42/34/34/51) + floor-verifier **pass** (diff exactly the
  two helpers + four sites; helper edge cases proven in-process; `longmem` pristine, zero
  scratch residue). **Gate (b) receipts** (piped REPL on scratch `longmem_smoke`, production
  knobs, no pins): live observe `[escalated]` with real render + tokens; one batched
  sonnet-5 reconstruction — 6 misses → **5 write-backs + 1 honest drift refusal**
  (in 856/out 853 tok, drift-embed 441); streaming dialogue first_token 2.9 s with a
  `recall` directive carrying memory IDs and the model delta applied 0.0 → 0.02; call-free
  cache-hit reread (recon 3.4 ms, turn 4.3 s vs 17.6 s cold); gate evaluated + closed with
  **zero probe SQL** (min_dist 0.408); `lex=` + `context: active` debug lines live.
  **Gate (c)** (staged scratchpad probe on `longmem_real`, diffed vs the surviving fake
  baseline; artifacts scratchpad-only/gitignored: `latency_report_real.json`,
  `diff_summary.txt`, `driver_report_real.json`, `explain_real.txt`): every infra series
  FLAT; the real numbers are the phase-header headline set. **Escalation re-measured:
  63/80 = 79% on realistic prose** (real haiku importance p50 0.61 vs the 0.45 threshold;
  triggers: importance 43, unresolved_reference 31, novel_entity 11, low_confidence 9,
  identity_affect 6; ~1.4 s + ~$0.0021 per fire ⇒ ~+$0.17/100 observes) **vs 0/26 on the
  driver's synthetic prose** — the rate is prose-distribution-dependent; 0 hard-stops in 80
  observes post-fix (feeds open question (a)). **Gate under real embeddings:** all four
  fixture scenarios reproduce exactly (closed 0/20 echo dist 0.0; novelty 20/20 at 0.64;
  tripwire 20/20; both 20/20); novelty CDF class p50s echo 0.00 / paraphrase 0.15 /
  related 0.50 / unrelated 0.70 — the current 0.5 threshold ≈ a 40% fire budget;
  recommendations (report-only): budget 0.2 → 0.65, 0.3 → 0.59, 0.4 → 0.50 on realistic
  prose vs the driver's 0.3 → 0.33 on its generator prose — calibration must run on real
  game prose. **Drift budget well-placed:** 16 live retellings re-embedded vs original
  anchors: p50 0.157 / p95 0.239 / max 0.244 — all under 0.35; observed refusals (1 smoke +
  1 probe) are the tail working. **Lexical channel:** EXPLAIN proves the 004 partial GIN is
  chosen (Bitmap Index Scan); the cost is ts_rank over the match set — the ≥3-letter
  tokenizer admits "the"/"did" and 'simple' keeps stopwords, so common words match ~every
  row: ~77 ms p50 at 5 k rows (3 ms on the 7-row smoke), linear in matches — watch-item
  with report-only options (tokenizer stoplist / min length 4); kill-switch verified =
  byte-shape v1. **Context term: ~0.03 ms** (score p50 0.08 → 0.11, active 50/50).
  **Stock driver (6×10 turns, priced): $0.44/100 turns** (dialogue $0.41 of it), turn p50
  2.9 s, gate 15 fires/100 with novelty efficacy 0.857, 2 fruitless, 3 damper-active turns.
  Spend for the whole session: order $2 (~205 haiku-class + ~110 sonnet-class calls,
  ~1 200 embeds). `longmem` pristine via the postgres MCP; zero scratch residue.
- **2026-07-21** — **Latency review + split-brain spec session (same day): the latency slate
  is ruled and the split-brain topology is pulled forward — specced.** Jack reviewed the
  real-mode table and ruled the viability bar (**first word < ~1 s** — perceived latency =
  prose TTFT, the honest decomposition being ~190 ms of our layer inside a ~4 s
  LLM-dominated turn) and that **all four latency levers land pre-demo** (dated "Latency
  slate + split-brain pull-forward rulings" entry in `decisions.md`): A split-brain
  streaming (specced now), B1/B2 dialogue-call experiments, C1 scene-boundary pre-warm, D
  async observes + the trigger fold-in. **Topology altered by ruling:** §9's serial sketch
  would put ~0.8–1.5 s of behavior call before the first prose token; Jack re-read the
  asymmetry — the prose call sees PAST behaviors as world facts ("why did you do that a
  minute / a week ago"), never the current turn's — so the calls run **concurrently** and
  the action enters the record for later turns. Two gray areas were surfaced at his request
  and ruled: same-turn word/action incoherence **accepted as an instrumented design fact**
  (the turn result records both calls' ranked views + directive — §13's explanation-cause
  divergence measurable from day one), and the world record is **game-authored action
  observes + the caller-held recent-actions block** (seam auto-write rejected — it would
  record unresolved intent as fact). Also ruled: the reserved `WeightOverrides` slot goes
  **live on the behavior view** via a second scoring pass (dialogue-view byte-parity kept);
  streaming = **seam + REPL + driver** this slice (SSE rides with Unity).
  `split-brain-streaming.md` written (ruled topology, scope boundary, mechanism,
  settle-tags, ten done-when criteria); architecture §9 amended (supersedes-in-part its
  serial wording); queue restructured (split-brain build → item 1; the pre-ship item grown
  by the slate; research items renumbered 4–8); the ledger's split-brain entry moved off —
  the second use of the pull-forward template. Docs only — no code, no floors changed.
- **2026-07-21** — **Split-brain streaming v1 built, verified, and committed — the latency
  topology is live, specced and built the same day.** Jack ruled four forks via explicit
  questions at plan approval (dated "Split-brain streaming build rulings" entry in
  `decisions.md`): **behavior model role = a new `behavior` role** (`LONGMEM_MODEL_BEHAVIOR` +
  `LONGMEM_PRICE_BEHAVIOR_IN/OUT`); **seam shape = async generator** (yields prose chunks then
  the terminal result; `first_word_ms` = time to the first yielded chunk); **mid-stream prose
  drop = keep the partial + degraded flag**; **behavior view = re-rank the served top-k set**
  (not the full pool — reuses served text, zero extra SQL/model calls). Build resolutions:
  exponent-form weighting (`behavior_score = item.score · rel^(w−1) · rec^(w−1) · imp^(w−1)`,
  so all-1.0 is dialogue-view parity and any other value re-ranks; clamp `[0,4]`); identity
  shared by BOTH prompts so the asymmetry stays statistical not architectural (§9), the
  recent-actions block the one ruled prose-only info difference. New: the prose streamer +
  behavior provider + fakes/failure-injection (`app\providers.py`), the async-generator
  split-brain seam with the worker-thread + `asyncio.Queue` bridge and the prompt split
  (`app\dialogue.py`), the `behavior` role + knobs (`app\config.py`), the divergence record +
  split-brain instrumentation + `RecentAction` + live `weight_overrides` (`app\schemas.py`),
  caller-held recent-actions + `stream_utterance`/`utterance` (`app\session.py`), the live
  streaming REPL + divergence debug view (`app\cli.py`), the `first_word`/`behavior` series +
  behavior cost row (`app\load_driver.py`). Verification inline: CLI-harness walker re-opened
  36 → 55 (concurrency proved — first chunk 0.008 s vs behavior 300 ms), read-path
  weight_overrides criterion re-scoped (48), gate walker rename-only (51), four walkers
  byte-untouched and green (40/42/34/34), suite 41 → 42 ×2 + keyless subset 35, migrate no-op,
  `longmem` pristine via the postgres MCP, live REPL streaming beat + driver run. No migration.
  **floor-verifier pass** — independent fresh-context re-run of all ten done-when + all seven
  walkers on fresh scratch (55/48/51/40/42/34/34), suite 42 ×2 + keyless 35, migrate no-op,
  `longmem` pristine, the ten untouched app files + four untouched walkers git-diff
  byte-identical, no invariant violated. **Flagged (operator-owned
  `.env`):** a malformed consolidated `LONGMEM_PRICE_DIALOGUE_IN=…` note-line crashes
  `load_settings` on any run reading `.env` prices — Jack's to fix (the fix: one `KEY=NUMBER`
  per line + add `LONGMEM_MODEL_BEHAVIOR` for real mode). Queue renumbered (Unity →
  item 1, pre-ship → 2, research → 3–7).

- **2026-07-22** — **External-persona agent-team audit + pre-demo replan (docs only — no code, no
  floors, no migration).** Ran a four-persona read-only Claude Code agent team (Convai/Inworld-type
  founder/CEO, senior runtime engineer, memory/cognition researcher, skeptic) through a 3-round
  critique + a solutions round; findings in `external-audit-2026-07-22.md` +
  `external-audit-2026-07-22-solutions.md`; persona defs in `.claude\agents\audit-*.md`. Lead-verified
  the load-bearing findings against source: **`app\api.py` has no HTTP dialogue-turn route** (cognition
  is REPL-only; Unity can't reach it), `first_word_ms` clocks after retrieval (blind to the 16.3 s cold
  stall), and the behavior view is byte-parity at default weights (the divergence record is a near-no-op
  until non-default weights). Jack ruled three forks (dated `decisions.md` entry): split-brain
  divergence → a **separate interview clip**; the demo records **real-providers-only** (the `.env` fix
  is now a hard prerequisite); the **judged eval harness is pulled pre-demo** (+ a judge-free demo
  panel, a hand-labeled gold set, and the fixed-gist ON/OFF ablation). Immediate queue restructured to
  the pre-demo build path (`.env` fix → `POST /v1/dialogue/turn` + perceived-TTFT → Unity + The Ledger →
  judged eval); C1 pre-warm BUILD proposed post-demo (off-camera warm-init covers the demo — flagged for
  confirmation); R7 self-referential drift budget logged as an open question. The build target is now
  **immediate-queue item 1: the HTTP dialogue-turn route.**

- **2026-07-22** — **Escalation failure path handled — soft-degrade built + floor-verified (migration
  005).** The first pre-ship item taken off the queue after the audit replan. Jack ruled the escalation
  fail-loud hard-stop retired (a failed gist-escalation must not halt a live write) and, at build,
  ruled the degraded-gist signal a **dedicated queryable column** (`memories.escalation_failed`,
  migration 005 — over a wire-only flag or reusing `scoring_failed`). Build (`decisions.md` "Escalation
  soft-degrade build"): `_escalate_with_retry` returns `None` on double failure; the observe path
  proceeds with the base NLP-pass gist + sets the flag; `EscalationHardStopError` + its 502 removed; the
  flag rides `InsertPlan` → the column + `IngestResult`. Scope observe-path only — the correction verb's
  fail-loud paths untouched. Suite `test_escalation_hard_stop_zero_rows` →
  `test_escalation_failure_soft_degrades`; walker [11] flipped. **The floor-verifier caught two misses
  in the first pass** — an `EscalationHardStopError` consumer left in `app\cli.py` (would have broken
  the CLI at import) and the gate walker's ledger pin not bumped for 005 — both fixed and re-verified →
  **pass** (write-path 42, cli-harness 55, gate 51, read/recon/authorial/fact 48/42/34/34, suite 42 +
  keyless 35, migrate 005 idempotent, `longmem` pristine 001–005). Trigger-set/threshold tuning
  (79%-fire) stays a separate open item.

- **2026-07-23** — **HTTP dialogue-turn route + perceived-TTFT metric built, floor-verified, and
  committed — the audit's #1 blocker is closed; Unity has a front door.** Plan-as-spec session (the
  design was pre-stated by the queue entry + the audit solutions doc's engineering spec — the
  test-suite precedent); Jack ruled one fork via explicit question at plan approval: the
  **thread-pool cap is deferred post-demo** (dated "HTTP turn route + perceived-TTFT build rulings"
  entry in `decisions.md` records it + the build shapes). New: `POST /v1/dialogue/turn`
  (`app\api.py` — `DialogueService` joins the lifespan; stateless non-streaming drain of the
  async-generator seam to the terminal `DialogueTurnResult`; 404/422 per the existing precedents;
  pass-through; a future SSE `/turn/stream` iterates the same generator) and
  `perceived_first_word_ms` on `DialogueTurnInstrumentation` (captured at the same first-chunk
  instant as `first_word_ms`, clocked from turn start — retrieval-inclusive; 0.0 when no chunk
  arrives; the <1 s bar is measured against it), surfaced in the CLI debug line + the
  `perceived_first_word` driver series. No migration; no new knobs or roles. Verification:
  CLI-harness walker 55 → 62 on fresh scratch; six walkers byte-untouched and green
  (48/51/42/42/34/34); suite 42 → 43 ×2 + keyless subset 35 → 36 (the new route-contract scenario
  is unmarked, so it rides the Stop-hook subset); migrate no-op ("5 applied, 0 pending"); `longmem`
  pristine via the postgres MCP; live serve HTTP beat (observe → turn → unknown-agent 404;
  perceived 22.87 ms vs first_word 0.42 ms on the fake-mode smoke — the retrieval-inclusive gap
  visible) + a standalone driver run. floor-verifier **pass** (independent re-run of all eight
  done-when criteria + all seven walkers + the suite ×2 + the keyless subset; no invariant
  concerns — the sole persisted write of a turn remains the sanctioned reputation UPDATE inside
  the seam). The build target is now **immediate-queue item 2: Unity + reference scene + The
  Ledger**.

- **2026-07-23** — **Escalation trigger tuning: measured, ruled, and the thin_gist trigger built +
  floor-verified (second task of the day) — the last escalation open question is CLOSED.** The
  "measure, then rule" item taken off the queue at Jack's direction before the Unity phase. A
  report-only real-mode probe (scratch `longmem_esc`, the 2026-07-21 corpus construction reproduced
  exactly, ~$0.25) recorded the per-observe RAW trigger inputs the old probe aggregated away. The
  findings (full table in the dated "Escalation trigger tuning" `decisions.md` entry): the fire rate
  reproduced (75% vs 79%) and is **productive, not runaway** — 85% of escalations add net gist
  spans/components; the importance threshold is a weak lever (real scores cluster ≥0.60, and its p50
  moved 0.61 → 0.47 between runs — decimal-tuning would be false precision); ~$0.15/100 observes,
  latency off the dialogue path under async observes; and the **zero-gist hole** — 16/80 observes
  landed with NO gist spans because no trigger fires on an empty base gist, leaving reconstruction's
  fixed constraint empty on exactly those rows. Jack ruled three ways: **the shipped defaults
  stand** (trims declined — gist capture is load-bearing for the thesis); **a sixth `thin_gist`
  trigger** protects the gist floor directly (fire when base spans < `escalation_min_base_spans`,
  new knob, default 1.0 = fire on zero, 0.0 disables — 75% → 95% on the corpus, +$0.03/100
  observes, the zero-gist class eliminated); **Engram-style deferred write cognition → the
  sequenced-later ledger** as its own spec target (viability assessed: the degradation flags are the
  natural deferred-work queue; the async-observe contract covers the latency motivation; frozen
  write-time facts + a new `write_cause` migration are the spec's real forks). Build: the trigger +
  knob + knob-fetch across `app\nlp.py`/`app\config.py`/`app\ingest.py`; write-path walker 42 → 46;
  suite 43 → 44 ×2 + keyless 36 → 37; six walkers byte-untouched and green; migrate no-op;
  `longmem` pristine. floor-verifier **pass** (all eight criteria; the fake-mode
  stored-rows-byte-identical prediction verified, not assumed). **Known nit left in place**
  (verifier observation, pre-existing at HEAD): the `app\ingest.py:234` comment still says
  "hard-stop on double failure" — stale since the 2026-07-22 soft-degrade, comment-only; fix when
  that file next opens. Next: **Unity + reference scene + The Ledger (immediate-queue item 2)**.

- **2026-07-27** — **Demo-vehicle fork weighed and ruled + item 2 specced (docs only — no code, no
  floors, no migration).** At the state review, Jack re-opened the vehicle question: custom Unity
  scene vs modding the NPC into an established game (Skyrim named), his premise being that Unity
  scene-building has been a time-sink in past projects. A five-agent read-only panel — the four
  audit personas + a web-research scout on the mid-2026 LLM-NPC modding landscape — weighed it;
  findings + the ruling in the dated "Demo-vehicle ruling" `decisions.md` entry. **Ruled: Unity
  gray-box with three de-riskers** — `NpcMemory.Core` built engine-agnostic first (plain .NET,
  zero `UnityEngine` types, one flat client class; a `dotnet run` console harness plays every
  demo beat headless, moving the interop go/no-go Wk-2 → Wk-1), **the Ledger as a browser page**
  (not Unity UI), and the established-game integration deferred to a **post-demo clip on a
  C#-moddable game** (not Skyrim: zero C# reuse, the Mantella comparison class, state-delta
  observes, AGPL on a published fork); the week-3 fallback deliberately NOT pre-ruled.
  **`unity-client.md` written** (the item-2 spec): mechanism per stage (core client + `NpcSession`
  port + console harness + Unity adapter + gray-box set + browser Ledger + choreography hooks)
  and seven open forks for Jack's rulings at plan approval — the headline three: SSE
  `/turn/stream` scope (the <1 s perceived-first-word beat is unrecordable without it; recommended
  in), an agent-provisioning route (`POST /v1/agents` does not exist — the demo agent is hand-SQL;
  recommended in, small), and the Ledger's data source (direct read-only SQL vs a read-only
  `GET /v1/memories/{id}/chain` route — the product-surface option recommended). Queue item 2
  reshaped to the ruled sequence; the artifact-queue Unity entry annotated; the established-game
  clip added to the sequenced-later ledger.

- **2026-07-27** — **Unity-client fork rulings + stage 0 built and floor-verified (second task of
  the day) — the C# client's full backend surface exists.** Jack completed the operator steps
  (Unity 6 project at `unity\`, uv + .NET SDK verified) and **MCP for Unity went live** (read
  probe found the scene camera; `McpVerificationCube` created at origin and deleted;
  console clean — the spec's early-verification step done). All seven `unity-client.md` forks
  ruled via explicit questions (dated "Unity-client fork rulings + stage-0 build" entry in
  `decisions.md`): SSE **in**, `POST /v1/agents` **in**, Ledger data = **the chain read route**,
  Newtonsoft everywhere, targets/layout as proposed, static-HTML Ledger, render shape at build.
  Stage 0 built: the SSE stream route (queue-bridged pump task; pre-stream 404/422 preserved;
  chunk events byte-identical to the terminal content), agent provisioning (server-minted UUID;
  the only new write surface — an agents row, outside the memory-content invariant's subject),
  and the two **unscored** inspector reads (superseded rows present, `has_embedding` never the
  vector, `memories.entities` deliberately not echoed). No migration; no new knobs or roles.
  Verification: walkers 46 → **51** (write, [15] provisioning), 48 → **56** (read, [14]
  inspector), 62 → **67** (CLI, [14] SSE); four untouched walkers green (51/42/34/34) and
  byte-identical to HEAD; suite 44 → **48** ×2 + keyless 37 → **41**; migrate no-op ("5 applied,
  0 pending"); `longmem` pristine via the postgres MCP; floor-verifier **pass** (floor economy:
  exactly nine files). Next: **stage 1 — `NpcMemory.Core` + console harness (the Wk-1 interop
  go/no-go)**.

- **2026-07-27** — **Unity-client stage 1 built and the Wk-1 interop gate is GREEN (third task of
  the day) — the project's first C# is live end-to-end.** `client\NpcMemory.Core\` (netstandard2.1,
  sole dep Newtonsoft 13.0.3, zero `UnityEngine` types): `NpcJson` (the ONE serializer config —
  snake_case naming, `NullValueHandling.Include`, `DateTimeOffset` end-to-end; the null-vs-`[]`
  tri-state never collapsed), `Models.cs` (field-for-field mirror of every wire model), the flat
  `NpcMemoryClient` (ten routes 1:1, per-route settable timeouts, loud typed errors, the SSE
  consumer), `NpcSession` (the `_apply_turn_result` port keyed on the server's gate record;
  boundary snapshot refresh from the last `reputation_after` — exact for a single-client session;
  a multi-client integration would want an agent-state read route, noted in the artifact queue) +
  `client\NpcMemory.Harness\` (net8.0). **The harness ran 21/21 checks green** against a live
  served backend (fake mode, scratch `longmem_smoke`): provisioning → time-travel observes → the
  tri-state wire proof → SSE byte-identity → correction/chain/index → 46-day drift + byte-identical
  reread → gate fire → warm-init pure cache hit → both views; 9 directives resolved through the
  callback path. One build-surfaced fixture fix: the harness config's episodic tau lengthened
  (1 → 7 days) so the fresh-read beat sits inside theta — the first run honestly caught the
  arithmetic (a 2-day-old memory on a 1-day tau serves reconstructed, as designed). floor-verifier
  **pass** (independent full-gate re-run incl. server lifecycle + port-fidelity review;
  interrupted once by a session limit and resumed to completion — the criterion-6d pristine query
  re-ran identically). A NuGet source was absent on the fresh .NET SDK; nuget.org added
  (machine-level, one-time). **Sixteen floors stand verified.** Next: **stage 2 — the Unity
  adapter + gray-box set** (MCP for Unity already verified), then the browser Ledger (stage 3).

- **2026-07-27** — **Unity-client stage 2 built — the adapter + gray-box set, Play-mode gate
  GREEN (fourth task of the day).** The Unity 6 project (URP template, `unity\`) joins the repo
  (79 files; the embedded third-party MCP bridge package + generated solution/caches
  gitignored — the manifest git URL re-resolves the bridge on a fresh clone). New:
  `Assets\Scripts\NpcMemoryNpc.cs` (the thin MonoBehaviour adapter — flat client + `NpcSession`,
  inspector config incl. auto-provision agent fields and decay taus, thin async passthroughs,
  directive/reputation events, zero blocking) and `NpcDemoDriver.cs` (the gray-box demo
  surface — **fork 7 settled at build: an IMGUI dev-tool overlay**, the intended systems
  aesthetic; live streamed dialogue, directive flash on the capsule, gate/reputation readouts,
  a +46d time-jump button; `autoRun` plays scripted Play-mode verification beats with
  `[npc-demo]` console receipts + `Application.runInBackground` so unattended runs keep
  pumping). The set: floor + three walls + Keeper capsule + nameplate + framed camera, built
  via MCP for Unity; the core DLL in `Assets\Plugins` (Release build), Newtonsoft via
  `com.unity.nuget.newtonsoft-json` 3.2.2. **Play-mode gate 8/8**: in-engine provisioning,
  injected-time observes, boundary freeze, loader turn, live streamed chunks byte-identical to
  content, **chunk callbacks ON the main thread (thread 1)**, session bookkeeping live
  in-engine, +9 frames pumped through both turns. **Two build-surfaced fixes, both caught by
  the Play gate:** (1) the core client had `ConfigureAwait(false)` throughout (the standard
  library idiom) — chunk callbacks landed on thread-pool thread 731; ALL removed so
  continuations honor the caller's SynchronizationContext (blocking is banned by the adapter
  contract, so the deadlock hazard the idiom guards against does not apply; documented in
  `NpcMemoryClient`; the console harness re-ran **21/21** after the change); (2) overlapping
  directive flashes captured each other's yellow as "original" — the true color is now
  captured once. One environment fix en route: a PowerShell text edit mojibake'd the core
  files' UTF-8 (ANSI round-trip); restored from git and re-edited UTF-8-safely. Receipts: the
  `[npc-demo]` console transcript + `unity\Captures\graybox-stage2-receipt.png` (*tracked since
  2026-07-28 — it was cited as evidence while gitignored, so the citation pointed at nothing on
  any other machine*); scene saved with `autoRun` off; server torn down, `longmem_smoke` dropped,
  port 8000 free, `longmem` pristine. Next: **stage 3 — the browser Ledger.**

- **2026-07-27** — **Unity-client stage 3 built — The Ledger is live (fifth task of the day;
  item 2's build stages are COMPLETE).** `ledger\index.html` — one static file, vanilla JS, no
  build step (fork 6 as ruled), dev-tool dark aesthetic — **served BY the API at `GET /ledger`**
  (a build-settled shape: same origin as the two inspector routes it polls, so no CORS surface
  and no second server; the inspector ships WITH the service, completing fork 3's
  product-surface logic). Renders: the per-agent index (newest-first, live telling head +
  version count + pinned badges), and per memory the full record — the immutable observation
  with **gist spans marked from the stored offsets**, the current telling, the telling chain
  with **superseded rows greyed-but-present**, the fact chain with embedded/degraded badges +
  entities, and the honest counts (gist spans / telling versions / superseded-kept / fact
  versions; item 3's gist-precision & detail-recall bind here later, stated in the page
  footer). **Turn-feed v1 settled at build:** paste/drop a `DialogueTurnResult` JSON renders
  read_mode/scores/IDs per served item + both scored views + the TTFT line; a live feed rides
  the demo choreography. All text renders via textContent (no injection surface). Verification:
  suite 48 → **49** ×(full) + keyless 41 → **42** (the `/ledger` route contract); a live beat —
  server on scratch `longmem_smoke`, the console harness populated a real fixture agent
  (21/21), then the Ledger in a real browser rendered 4/4 memories and the corrected memory's
  chain read **original (greyed) → authorial_correction (greyed) → reconstruction (live)** —
  the 46-day retelling visibly built ON the corrected content, the record's whole story on one
  screen; the crafted turn-JSON drop rendered the score table + views. Teardown clean (port
  free, smoke dropped, `longmem` pristine). Next: **demo choreography + the pre-ship latency
  items (B1/B2 measure-then-rule) + the judged eval harness (item 3).**

- **2026-07-28** — **Full-repo audit + remediation (Jack's request: audit everything, plan, then
  implement on approval).** Seven read-only dimension auditors, each dimension's findings then
  handed to an adversarial verifier told to refute them: 107 raw findings, 4 refuted, ~20
  downgraded, 64 surviving. Two refutations were because the "problem" was an existing dated
  ruling (CI-later; the gate's cosine import) — the register defending itself. **The audit's
  verdict on the codebase was that it is sound**: zero prose assertions across suite and walkers,
  every UPDATE/DELETE sanctioned, `.env` never in any git ref, all thirty C# wire models
  field-for-field with the tri-state intact, all SQL parameterized. Four rulings and the full
  finding set: the dated "Full-repo audit rulings" entry in `decisions.md`. Eight commits:
  - **Phase 1 — code defects.** The one real defect: `NpcMemoryClient` drove its SSE loop off
    `StreamReader.EndOfStream`, a **synchronous** read, on a client deliberately built without
    `ConfigureAwait(false)` — so it stalled the **Unity main thread** between chunks, on the path
    the <1 s perceived-first-word beat runs on. *The Play-mode gate had passed 8/8 with it
    present* (fake-mode streaming masks the stall), and the verifier later confirmed the blocking
    call was compiled into the shipped DLL. Also: `tests\scratch_uri.py` (one shared, verified URI
    rewrite — the old path-only swap let a `?dbname=` query parameter survive and point the
    suite's TRUNCATE at the product database, proven with libpq's own parser); three dead symbols
    removed (`span_sources` was not merely unread — it was built parallel to `spans` and never
    deduped alongside them, so it was already misaligned); `MalformedWriteProvider` **wired into**
    the write walker rather than deleted, closing the ladder's malformed-output row (51 → 53);
    `load_driver`'s hand-written agents INSERT replaced by `db.insert_agent`; stale comments
    describing the retired escalation hard-stop and the "future" SSE route.
  - **Phase 2 — the mechanical gates.** CLAUDE.md says formatting is "enforced mechanically"; only
    `ruff format` was, `ruff check` had never run as a gate, and **`ruff` was not pinned at all**
    (already drifted — one test file had been out of format since `edf9820`). Pinned; `ruff.toml`
    added with the walkers' deliberate E402 ignored so the two real findings stop drowning in 65;
    `ruff check` joined the edit hook. floor-verifier's allowlist gained the Unity MCP (its
    absence would have reproduced the exact 2026-07-13 incident its own runbook documents);
    doc-auditor's reading list named 5 of 17 docs, omitting every build spec; the `.env` deny
    covered one tool; the Unity `.gitignore` block was unanchored at repo root (the hazard that
    already forced rescue commit `ae54af8`).
  - **Phase 3 — coverage.** Enumerating every route against every test found `PUT /pin` and
    `POST /events/scene-boundary` with **no HTTP test anywhere**, the SSE `reconstructing` and
    `error` events untested, and `CorrectionNlpFailedError` → 502 ruled and built with neither a
    test nor a spec row. Writing the SSE test surfaced a design fact worth recording: the
    pre-serve callback rides **gated turns only** (the signal that earns a spinner is a pause
    appearing mid-scene, not a scene's first read) — the first draft used a loader turn and
    correctly failed. Suite 49 → 53.
  - **Phase 4 — propagation.** The four 2026-07-27 build sessions had propagated into `status.md`
    only. `architecture.md` — self-declared design truth — knew nothing of the five routes shipped
    that day; the IDs-and-scores invariant was **false as written** for the two unscored inspector
    reads, in three files including auto-loaded CLAUDE.md; the model-role claim was wrong in two
    ways (seven vars, not nine roles; three cannot diverge); the register still called the
    escalation hard-stop an open decision owed before the demo, and stopped at stage 0. Fixed,
    plus a 42-entry index for `decisions.md`. `client_total_ms` was **built** rather than struck —
    `unity-client.md` asserted the client recorded it and no C# file did.
  - **Phase 5 — the split** (ruled). `status.md` 1294 → 319 lines, 145,787 → 24,728 chars: roughly
    **30k tokens off every future session's baseline**, history moved not lost.
  - **Phase 6 — onboarding.** LICENSE (canonical text, not recalled), NOTICE (licences read from
    installed metadata — psycopg is LGPL-3.0-only and was unremarked anywhere), `.env.example`,
    `docs\SETUP.md` (the clone-to-running path, including the DLL refresh procedure that existed
    nowhere), `docs\README.md` (the index, and the first definition of "walker" vs "suite" vs
    "floor" — vocabulary used 150+ times and defined nowhere).
  - **Phase 7 — research writing into version control** (ruled), and the stage-2 Play-mode receipt
    PNG un-ignored: `session-log.md` cited it as verification evidence while `.gitignore` excluded
    it.
  - **`.gitattributes` + a self-inflicted repair.** My own phase-7 path rewrite used
    `docs\research\` in a non-raw Python string, so `\r` became a literal CR in six docs. That
    stray CR also made git decline to normalize those files, which is how a two-line edit rendered
    as a 971-line rewrite. Repaired at the byte level; `.gitattributes` now pins `* text=auto
    eol=lf` so it cannot recur. Found by checking the diff rather than trusting it — and the
    grep primitive I first reached for was itself lying (same count for a pure-LF control as for
    CRLF), which is why the first look seemed fine.
  - **floor-verifier: FAIL, then fixed.** The first pass returned **fail** on one real point: a
    `ruff format` run with `target-version` briefly set had stripped the parentheses from
    `except (A, B):` in `app\ingest.py` — the exact hazard `ruff.toml`'s own comment describes,
    shipped in the same commit as the comment. Behaviour on 3.14 was unchanged (the forms are
    AST-identical, which is why every test passed and an AST-level diff showed nothing); the
    verifier found it with a token-stream diff. Restored, and `tests\test_repo_hygiene.py` now
    guards it plus the SQL-only-in-db.py stack constant — both pure, both on the turn-end subset.
    Suite 53 → **55**, keyless **48**. Walkers unchanged at 53/56/67/51/42/34/34.
  - **Not claimed:** the Unity **Play-mode gate** was not re-run — its MCP tools were not exposed
    to this session, so it is an operator step and is reported blocked, not passed. It matters
    more than usual here because the DLL Unity loads was rebuilt twice.
  - **Independent verification, second round: floor-verifier PASS.** Seven walkers on fresh
    scratch, suite 55 twice, keyless 48, ruff clean, migrate no-op, `longmem` pristine, interop
    gate 21/21, all 220 tracked text blobs LF with no lone CR, and the docs split proven lossless
    by extraction against `49a635b` (18/18 floor rows, 851/851 session-log lines byte-identical at
    the split commit). It also mutated a temp copy to prove the new hygiene guard is *capable* of
    failing, and diffed the committed Unity DLL against a fresh build down to the five
    build-identity fields (COFF timestamp, PDB GUID, MVID, checksums) — 0 differing bytes
    outside them, so the shipped binary really is current source.
  - **It found one more defect, in my own phase-4 work.** `ClientTotalMs` was subscriber-gated:
    `Measure()` returned early when nothing was subscribed to `OnCallMeasured`, so the property sat
    at 0 while its own doc comment claimed it held the last call's wall time. A Unity adapter or
    eval script reading it without subscribing would have gotten a plausible-looking zero — exactly
    the failure "instrument at the seam" exists to prevent. Fixed to always record then notify, and
    the harness now asserts both halves (a client with NO subscriber reports a real number; the
    event fires once per call with the route path). **Interop gate 21 → 23.**
  - **doc-auditor: six contradictions, fourteen stale items — all actioned.** The sharpest was
    `log-decision.md` still instructing the next session to append session-log lines to
    `status.md`, which would have silently undone the split. Also: suite counts stale *again*
    (I updated the docs before adding the hygiene tests), `test-suite.md` claiming "every route"
    asserts its error statuses when `POST /v1/dialogue/init`'s 404/422 are asserted nowhere (now
    stated as a known gap rather than implied away), `tests\CLAUDE.md` still carrying the
    un-amended invariant wording, two files still locating the session log inside `status.md`,
    and `decisions.md`'s index mixing two slug conventions — regenerated, 44 entries, every anchor
    verified to resolve.
  - **And I made the `\r`-in-a-non-raw-string mistake a third time**, in the same session, on the
    same path. Caught only because I had kept the repair script from the second time. That is the
    honest lesson of this session's mechanical work: batch text rewrites through a file, never a
    shell heredoc.
  - **Two rulings from Jack at close.** (i) **Reconstruction is Haiku-class** — the register was
    right and the shipped config had drifted to sonnet-5 since 2026-07-21 (a stopgap for a missing
    env var, never a class decision). Jack corrected `.env`; verified live — all seven roles
    resolve, reconstruction Haiku-class, prices on the Haiku tier, `load_settings()` OK in real
    mode. **Live consequence: every real-mode reconstruction number on record — the 16.3 s cold
    figure, the cost table's reconstruction rows, the drift-refusal rate — was measured against
    sonnet-5 and needs re-running (new pre-ship item (b2)).** (ii) **Applied migrations are
    immutable, comments included** — the audit's own path rewrite had edited an applied migration's
    header; restored byte-identical, and `db\migrations\` is now byte-for-byte what it was
    pre-audit. Both in `decisions.md`. Jack also confirmed the LICENSE attribution
    (`Copyright 2026 Jackson Zane`) as written.
  - **Final state:** twelve commits, nothing pushed. Walkers 53/56/67/51/42/34/34, suite 55,
    keyless 48, interop gate 23/23, ruff clean, ledger 001–005, `longmem` pristine, tree clean.

- **2026-07-28/29** — **Re-audit of the two Opus 5 sessions (Fable 5; cut short by usage
  limits — continuation queued as status.md item 0.5).** Jack's request: both 2026-07-28
  sessions ran on the newly released Opus 5, which he found unreliable mid-work-session;
  stress-test everything it touched (the 13 unreverted audit commits `49a635b..91b1ad6` above
  all) and stand as a reliable audit in its own right.
  - **Forensics on the aborted work session landed (full 733-message transcript sweep):** the
    revert was total — tree clean at `91b1ad6`, no commits, product DB untouched, the walker
    scratch self-dropped. Its walker-run "failure" was a wrapper bug (PowerShell turned
    fastcoref stderr INFO lines into `NativeCommandError` via `2>&1`), NOT a walker
    regression — proven by this session's clean run. Survivals: an inert plan file, an inert
    temp script, and `origin/main` force-rewound to `49a635b` at Jack's direction — local is
    ahead 13 and the `docs\research\` corpus is single-machine again. **Jack ruled:
    fast-forward push (`git push origin main`, never force) once the audit completes; a
    blocked Unity gate does not block it.**
  - **Every mechanical gate re-run fresh — all green, and every 7/28-recorded number
    reproduces except one:** baseline (HEAD/tree clean/migrate no-arg "5 applied, 0 pending"/
    `longmem` pristine — ten product tables 0 rows, ledger exactly 001–005); ruff 0.15.21
    format 35/35 + check clean; suite **55 ×2** (determinism) + keyless **48**; both C# builds
    0 warnings; console interop gate **23/23** (9 directives) live on scratch `longmem_smoke`;
    `GET /ledger` 200 with all markers; **all seven walkers on fresh scratch
    53/56/67/51/42/34/34**; no lone CR in any tracked blob (Python byte-count, not grep). The
    one non-reproducing number: the floors.md re-verification note's "interop gate 21/21" —
    fresh measurement and source both say 23 (the [11] client-timing checks landed mid-audit;
    `docs\SETUP.md:192` carries the same stale 21). Correction queued, not applied (the
    append-only-scope ruling below governs how).
  - **DLL provenance proven stronger than the audit claimed:** the committed
    `unity\Assets\Plugins\NpcMemory\NpcMemory.Core.dll` is byte-identical to a fresh Release
    build of current source except 146 bytes, ALL build-identity: COFF stamp, MVID, PDB GUID,
    and the SDK-embedded `1.0.0+<HEAD-sha>` strings — the committed DLL embeds `ae967cf`,
    exactly consistent with its rebuild-then-commit in `750a9dd`. No source/binary drift.
  - **Blocked: the stage-2 Unity Play-mode gate — still the one outstanding verification.**
    Attempted per Jack's ruling: Editor open, bridge listening on 8080, fake-mode server
    live — but zero `mcp__UnityMCP__*` tools reach a session (or its subagents) that started
    before the Editor opened; the floor-verifier dispatched anyway and returned an honest
    **blocked** (nothing simulated). Root cause is session-start ordering, NOT the
    `~\.claude.json` duplicate repo keys (confirmed real — the forward-slash key carries
    UnityMCP+postgres, the backslash key is empty — but this session resolved the good key).
    **Needs attention: open Unity BEFORE launching the Claude Code session; clean the
    duplicate keys.** Jack declined the manual-run fallback and ruled it recorded blocked.
  - **Abandoned mid-flight (usage limits, twice): the 20-finder + refuter fan-out.**
    Completed and journal-preserved (3/20): (i) **check-8 coverage gap CONFIRMED** —
    `NpcDemoDriver.cs` check 8's frame window spans both turns so it cannot see an
    inter-chunk SSE stall, and NO automated test anywhere covers the SSE main-thread-stall
    regression (harness [11] measures a plain GET; harness [5] asserts only concatenation);
    (ii) **the (b2) "Zero code" adjudication came back PARTIAL** — the aborted session's
    premises are true (the driver handles only observe/utterance/scene; only the CLI sets
    `as_of`) but its conclusion overreached: theta-crossing needs no `as_of` (wall-clock decay
    + per-agent `reconstruction_theta`/tau knobs + the driver's `--agent`/`--database-uri`
    re-targeting reach it), and the 16.3 s figure came from the REPL/scratchpad probe, not the
    driver series — the probe's instruments were scratchpad-only, so "re-staged, not
    one-command" is the surviving grain; (iii) the Ledger score panel is paste-only and the
    REPL has no warm-init verb (verdict complete, in the journal). **NONE of the three are
    adversarially refereed — treat all as unverified.** Never ran (17): the seven diff
    reviewers (app/client/tests/gates/docs-split/docs-claims/misc), register reconciliation,
    CRLF classification, and all eight dimension audits (incl. field-for-field wire parity).
  - **Continuation pointers (lose nothing):** the plan file
    `~\.claude\plans\the-two-most-recent-giggly-newell.md` (full phase design + Jack's seven
    rulings); the workflow script
    `~\.claude\projects\C--Users-jacks-Projects-longmem-npc\7d10cda7-b3cc-4055-ab65-b730d405e572\workflows\scripts\opus5-stress-audit-wf_5810df26-b8a.js`
    and journal `...\subagents\workflows\wf_5810df26-b8a\journal.jsonl` beside it (run id
    `wf_5810df26-b8a`; in-session resume only — a future session re-runs the 17 or harvests
    the journal). Remaining work is enumerated in status.md queue item 0.5.
  - **Continuation (same session, later 2026-07-29).** A usage-limit diagnosis interlude
    measured the burn mechanics (request-count × context size dominates; the 7/28 dual-repo
    audit marathons ≈ 252M weighted tokens in one day; Opus 5's loop takes ~2–3× more, smaller
    steps than Fable's; the status.md split already cut per-request context ~283k → ~106k).
    **Two rulings from Jack:** (i) **quality over token thrift** — never degrade work scope or
    effort to save tokens; no thrift prescriptions in the repo (he would rather upgrade the
    plan); (ii) after the resumed 17-finder fan-out burned ~10% of a usage window in three
    minutes (every subagent inheriting xhigh effort), **the exhaustive fan-out was descoped by
    ruling** and replaced with a main-loop tail of the four highest-value checks. The three
    completed finder verdicts stand as recorded-unrefereed.
  - **Main-loop tail — all four checks green:** sanctioned-writes sweep (every UPDATE/DELETE in
    `app\`+`db\` maps to the sanctioned set — pin toggle, reputation apply, `invalid_at`
    supersession ×3, the sole cache-eviction DELETE, 003's self-sanctioned backfill; nothing
    else exists); `.env` in zero of the 72 commits across all refs; wire parity **31/31 classes,
    zero field-name mismatches** (scripted, both sides); docs-split losslessness re-proof —
    **all 18 floor rows and all 851 session-log lines present**, six carrying deliberate dated
    in-place annotations from phase 7's research-folder move, so the 7/28 "verbatim /
    byte-identical" attestations were true-at-measurement but stale-at-wrap-up (the same error
    class as the 21/21 figure).
  - **Series B corrections applied (rulings 3 + 5):** `SETUP.md` 21→23 checks; `status.md`
    30→31 wire models; `floors.md` 21/21→23/23 plus the verbatim-preamble exception and the
    lossless-claim clarification — each corrected in place with a 2026-07-29 date per the
    append-only-scope ruling. Still surfaced, not built: check-8/F3 teeth, the Ledger live feed
    + REPL warm-init verb, CRLF renormalization, `~\.claude.json` duplicate keys, the Unity
    session-ordering procedure.
  - **Final state:** two commits (both docs/registers only — zero app/db/client/tests changes);
    scratch DBs dropped (`longmem_smoke`, `longmem_test`), port 8000 free, `longmem` pristine;
    **pushed to `origin/main` (fast-forward) per the ruling — the off-machine backup is
    restored.**

**2026-07-29 — measurement session (Fable 5): (b2) Haiku reconstruction re-measure + B1
dialogue A/B — all green; rulings queued.** Began as a state-observation request; the approved
next action was queue items (b)+(b2), env-swap arms only (B2 thinking-off variants deliberately
untouched — they need Jack's ruling). All runs real-mode on scratch DBs (`longmem_b2`,
`longmem_driver` — created, migrated 001–005, dropped); product `longmem` untouched; zero
app/db/client/tests changes.

  - **`.env` was already correct.** The (b2) prerequisite ("correct `.env`, then re-run") was
    pre-satisfied: the reconstruction role already named `claude-haiku-4-5-20251001` and both
    reconstruction price rows already carried 1.00/5.00 — verified by a boolean-only line check
    (no values echoed; `load_settings` ok; provider mode real). The ruling session evidently
    fixed the live file alongside `.env.example`.
  - **Re-staged, as the audit's PARTIAL verdict predicted.** The 2026-07-21 `probe_real.py` no
    longer runs against current source: it imports the removed `EscalationHardStopError`, awaits
    `run_dialogue_turn` as a coroutine (pre-split-brain), and builds a five-field `Providers`.
    A focused rebuild (`probe_b2_haiku.py`: the a1 seed subset + the five stage-d recon snaps +
    the drift addendum inline, corpora/labels/request shapes byte-matched to the baseline) went
    through a keyless fake-mode dry run first, then ran real.
  - **(b2) — Haiku is faster, ~4× cheaper, and drifts LESS than the stale sonnet-5 numbers.**
    Cold batched retellings (8 rows/batch): 16257→8071 ms (the 16.3 s headline), 14938→5112,
    9211→3307, 8838→7997; cache-hit reread stays call-free (13 ms). Whole probe $0.0157 at
    Haiku list rates (~$0.0039/batch vs ~$0.0158 sonnet). The drift re-check — the one feared
    real regression — came back better: distances p50 0.1074 / p95 0.1627 / max 0.1924 (sonnet
    0.1571/0.239/0.2437), 0 over the 0.35 budget, 0 refusals in 32 attempts (sonnet 1/32).
    Qualitatively the 16 raw tellings keep gist near-verbatim and add first-person identity
    color; the max-distance telling reframes the keep-well fact as hearsay. Demo consequence:
    the cold stall is ~3.3–8.6 s pre-warm-init (was 9–16 s).
  - **B1 haiku-dialogue A/B (product driver, 6×10 turns, seed 7, gate-budget 0.3, same-day
    arms):** `perceived_first_word` — the <1 s bar's field — p50/p95 **951/1701 ms (haiku)** vs
    1201/2775 (sonnet-5): haiku meets the bar at p50; sonnet misses. `first_word` p50 657 vs
    900; `dialogue_total` p50 1751 vs 2559; 60 turns, 0 degraded, both arms. Dialogue cost
    $0.109 vs $0.415/100 turns — the 3× rate gap × a ~1.36× tokenizer difference (sonnet-5
    counts the same prompts higher: 85.5k vs 62.8k in/100 turns; write/embedding rows identical
    across arms, which pins the artifact). Prose quality deliberately unassessed — that is item
    3's judged-eval territory.
  - Side notes, report-only: gate novelty efficacy 1.0 both arms (0.857 on 07-21); the
    calibration block recommends ~0.38–0.39 for a 0.3 target (0.33 then). Sonnet-5 currently
    has intro API pricing ($2/$10 through 2026-08-31); the cost table used list 3/15 — if the
    billed rate is the intro one, the sonnet arm's USD shrinks ~33% and the latency verdict is
    unchanged.
  - **Queued for rulings (measure-then-rule):** (i) lift the quote embargo on the reconstruction
    numbers (now Haiku-measured); (ii) dialogue model for the demo — haiku wins the bar and the
    cost, prose quality unjudged; (iii) B2 thinking-off one-liners — measure or drop.
  - Artifacts scratchpad-only per precedent (session `85779bb1-…`): `probe_b2_haiku.py`,
    `run_ab_driver.py`, `b2_report.real.json` (16 raw drift records with texts),
    `driver_report_A/B.json`, driver stdout tees. Docs touched: two queue rows + the (c) stall
    figure in `status.md`, and this entry.
  - **Continuation (same session): all three rulings landed; the model-decision task is
    CLOSED.** Jack lifted the quote embargo, ruled the dialogue role **Haiku as-is for now**,
    and deferred sonnet-5 + the B2 thinking-off variants to the judged-eval harness (re-assess
    when prose can actually be scored). Propagated: `.env` switched live (booleans-only script;
    `load_settings` ok) + `.env.example` with a dated comment and haiku price placeholders; the
    `architecture.md` roles line — found ALSO still claiming Sonnet-class for reconstruction, a
    2026-07-28 propagation miss, fixed with dated notes — and its §7 embargo sentence resolved;
    `unity-client.md`'s init-timeout annotation re-pointed at the Haiku numbers; `status.md`
    rows (b)/(b2) + the remaining-before-recording list; the dated **"Haiku dialogue +
    quote-embargo lift"** register entry + TOC line. Deliberately untouched: the v1 `sonnet_*`
    wire-instrumentation names (kept by an in-line note in `app\schemas.py`; mirrored
    field-for-field by the C# client) — renaming that contract would be its own scoped task.

**2026-07-29 — stage-2 Unity Play-mode gate LANDED as a floor + real-mode corroboration (Opus
4.8).** The one verification outstanding before demo recording — blocked on 2026-07-29 by
session-start ordering (the session began before the Editor opened, so no `mcp__UnityMCP__*` tools
registered). This session started with Unity already open; the bridge reached the main loop AND the
floor-verifier subagent, so the block is cleared and root-caused, not worked around. Nineteen floors
now stand.

  - **MCP bridge verified read-only first** (the user's explicit requirement): one instance
    `unity@5c4691b082890e05` (Unity 6000.3.17f1), `ready_for_tools: true`, `project/info` =
    `…\longmem-npc\unity`, `read_console` round-trip clean, `NpcDemo` live (instanceID 47906). No
    diagnosing session needed.
  - **Fake-mode gate 8/8 GREEN — the gate-of-record.** Backend up in fake mode on scratch DB
    `longmem_smoke` (`docker compose` → migrate 001–005 → `python -m app.serve`; `/docs` 200 — there
    is no `/health` route; the ~30 s warmup is the spaCy/fastcoref load fake mode still does).
    `autoRun` flipped true via `manage_components` in edit mode (before Play — scene mutations fail in
    Play), entered Play via `manage_editor`, read the `[npc-demo]` receipts: all 8 PASS + `ALL
    PLAY-MODE BEATS PASSED (8 checks)` (agent 552052c0, +11 frames; the transient `no_unity_session`
    right after Play-enter is the domain-reload window, expected and retried).
  - **Independent floor-verifier: PASS — and it re-drove the gate live** (subagent bridge reachable —
    the 2026-07-29 failure did NOT recur): fresh 8/8, new agent 1bbd6b3b, +12 frames, 0 console
    errors. DLL build-identity provenance re-proven — a fresh `dotnet build -c Release` differs from
    the committed `NpcMemory.Core.dll` by **150 bytes, all build-identity** (COFF stamp, MVID, PDB
    GUID/checksum, embedded version sha), fresh sha == HEAD `5bec081`, all IL/metadata byte-identical →
    no source/binary drift (the committed DLL's embedded sha `ae967cf` lags one commit — built 5 min
    before `750a9dd` — but its IL is current). Two non-blocking soft spots recorded: check #1 is a
    guarded `Check(true,…)` (protected by the 30 s Ready-wait timeout) and directive/reputation
    callbacks are subscribed-but-not-asserted (delegated to the stage-1 console floor). Quirk: only
    `mcp__UnityMCP__`-prefixed tool names resolve for a subagent, not bare names.
  - **Real-mode corroboration pass 8/8 (Jack ruled it in at plan approval) — exercises the SSE fix
    fake mode masks.** Swapped the backend to real mode (Haiku dialogue, fresh scratch DB; real config
    validated at startup — all 7 model roles + keys present or it refuses to start), re-entered Play:
    8/8 again (agent 41d3838e), 0 errors — and check #8 read **+1061 frames** through the real streamed
    turn (vs +11/+12 fake). That is the regression test the fake path can't be: real inter-chunk gaps
    mean a main-thread block would collapse the frame count; ~1000 frames proves the
    `ConfigureAwait(false)`-removal / `ReadLineAsync` SSE fix holds under real streaming.
  - **State restored, nothing leaked.** `autoRun` set back to `false`, scene NOT saved (committed
    `autoRun: 0` preserved); real server stopped, `longmem_smoke` dropped, port 8000 free; `longmem`
    pristine by construction (every `DATABASE_URI` used was the scratch DB — `databases present:
    ['longmem']` after the drop).
  - **Records + commit:** `floors.md` row 19 + counting convention 18→19 + the blocked note resolved;
    `status.md` (new dated block, remaining-before-recording, floor counts, queue item 2); the dated
    **"Stage-2 Play-mode gate verification + real-mode corroboration"** register entry + TOC line; this
    entry. Docs-only commit (zero app/db/client/tests/scene changes). Still surfaced for a ruling, not
    fixed here: a DLL staleness guard.
  - **Follow-on (same session): the `~\.claude.json` empty backslash project key was removed
    in-session** — surgical single-span deletion (backup first, hard safety assertions, a verify
    pass), the live forward-slash key with postgres+UnityMCP untouched. **Caveat — likely
    non-durable:** `.claude.json` is Claude Code's own live state file and the running process
    rewrites it from an in-memory model that still holds the key (it rewrote the file mid-task —
    `tengu_*` flags changed between the backup and the edit), so the deletion will probably be
    re-added on the next config flush / session exit. The durable fix is to run the removal with
    Claude Code fully CLOSED, so the next session starts from a clean file; the verified removal
    script lives in the session scratchpad. Not a repo change (`.claude.json` is outside the repo).

**2026-07-29 — eval-harness v1 planned + stage 1 built and floor-verified (Fable 5).** Started as
a queue-confirmation question; Jack picked the eval harness (item 3) over choreography-first at an
explicit ask, then ruled four plan forks at plan time (AskUserQuestion, all on the recommended
options): judge role eval-runner-only, v1 judged categories = core 3 + prose quality, Ledger
binding = a new read route, no migration. Plan explored (3 read-only agents), designed (Plan
agent), spot-verified against source (one real catch at plan verification: the Plan agent's
"31/31 wire-parity mechanism" claim is an attestation, not a mechanical gate — no reflective
enumerator exists; and the ablation OFF arm must exclude correction-anchored chains, whose gist
slot IS the corrected head — recorded as fork 11), approved, and stage 1 built in the same
session.

  - **Landed:** `docs\eval-harness.md` (plan-as-spec, all four stages contracted, 12-fork
    settle-at-build table, stage-1 BUILT banner) + README spec row; `app\eval_metrics.py` (pure
    judge-free metrics — anchor-cause-aware gist facts, threshold presence rule, honest-None
    denominators, whole-word fabrication grounding, keyword retention, band parser);
    `nlp.lemma_content_set` (write-pass filter promoted); `metric_gist_match_threshold` knob
    (1.0); `ReconstructionMetricsResult` (18 fields); read-only `db.fetch_cache_keys`;
    `RetrievalService.reconstruction_metrics` (live-head-only, pure identity render, spaCy in a
    worker thread); `GET /v1/memories/{id}/reconstruction-metrics` (404 the /chain shape); the
    Ledger numbers panel now fetches + renders the three metrics (try/catch — a metrics failure
    never hides the chain) with the footer promise flipped to bound; C# mirror (Models.cs 31→32,
    `ReconstructionMetricsAsync`, harness check 23→24); suite Set G (5 pure unmarked + 3
    nlp-marked, incl. the non-perturbation pair). Docs propagated in-pass: test-suite.md (63/53 +
    Set G section + route row), architecture.md (§6 metric-read paragraph, twelve-route table,
    eleven client verbs), CLAUDE.md (the unscored-reads carve-out grew its third member — the
    floor-verifier's catch).
  - **Verified:** suite **63 ×1 full + the 8 new twice more** (5 pure fast-pass, 3 nlp), keyless
    subset collects 53; walkers `verify_read_path` 56 + `verify_reconstruction` 42 on
    `longmem_test` (provisioned this session — it had not survived since the audit); ruff
    format+check clean at 0.15.21; both C# builds 0 warnings; live interop gate **24/24** on
    fresh `longmem_smoke` (the new check hit the honest-denominator path live: gist 0/0 → null,
    bands [3]); the live route payload on the corrected chain exactly per contract
    (reconstruction head over a correction anchor: gist 1/1 = 1.0, detail null, zero fabricated,
    retention 1.0, band 3, metrics 48.74 ms inside total 71.82 ms); browser beat — The Ledger
    rendered **gist precision 1.00 (1/1 facts held)** beside the four counts. **Independent
    floor-verifier PASS** (all eight done-when re-run fresh; zero-write proven three ways; both
    floors beneath intact; teardown verified — smoke DB dropped, `longmem` untouched). Floor
    row 20.
  - **Honest notes:** the Windows `execve` quirk detached the smoke server from its background
    task handle (killed by port at teardown — worked, but the serve script should spawn-and-wait
    instead, a stage-2 nicety); the suite's non-perturbation pair compares `/chain` with
    `total_ms` excluded (a per-call timing field — the plan's "byte-identical" wording
    overpromised by one field and the test says so); the floor-verifier noted my brief
    undercounted the wire model (18 fields, not 17 — the mirror itself is exact). Nothing
    blocked; nothing abandoned. Remaining for item 3: stages 2–4 (runner, judge layer, ablation).

- **2026-08-04 — Road-to-completion re-plan (planning session; Fable 5).** Nothing built — by
  design. Jack asserted the remaining scope was disorganized and re-planned it end to end from
  his own draft schedule; Claude's review raised the load-bearing gaps (the demo-date
  collision, reputation living inside the behavior call, the hidden-weights inversion, the
  missing purge / async-observes / conflict-detection items, harness sequencing); Jack ruled on
  all of it — research scrapped, behavior side + reputation scrapped (hidden weights move to
  the speech side), graph memory cut, conflict/staleness cut, the August demo date dropped, end
  products defined (video + Unity Package + one-command backend spin-up + public repo). Full
  ruling set: the dated "Scope consolidation + road-to-completion rulings" entry in
  `decisions.md`.
  - **Landed:** the phased roadmap (A re-shape → B measurement rig → C components → D
    optimization → E demo → F release → G optional epilogue; ~18–22 sessions) written into
    `status.md`, which was rewritten as lean live state; the displaced dated narrative blocks
    and the superseded queue/ledger/deadline text moved VERBATIM (heading levels demoted one
    step) into this file's archive, below, per the 2026-07-28 losslessness pattern. CLAUDE.md
    deliberately untouched — its seven-role and reputation wording stays true until Phase A
    lands (A1 owns that edit).
  - **Honest notes:** no code, no tests, no floors touched; the Stop-hook subset is the only
    gate this session. Next session: Phase A1 — the split-brain re-shape (strip behavior
    call/directive/reputation end to end; move `weight_overrides` onto the prose view).

- **2026-08-04 — Phase A1: split-brain removal + weights-on-speech (the re-shape session).**
  Planned in plan mode (three explorers + a plan agent); Jack ruled the four spec forks at plan
  approval — post-cut re-rank at the dialogue seam, the recent-actions channel removed whole,
  the provisioning surface + four reputation knobs stripped, the init-side `weight_overrides`
  removed — recorded with the seam contracts in the dated A1 entry in `decisions.md`.
  - **Landed:** the removal end to end — the behavior call + `behavior` role (real mode 7 → 6
    vars), the action directive, the divergence record, the recent-actions channel, and the
    reputation system whole (`apply_reputation_delta` deleted; provisioning writes neither
    column; **a dialogue turn persists nothing**) — and weights-on-speech: the exponent re-rank
    re-pointed at the served view feeding the prose prompt
    (`resolve_dialogue_weights`/`weighted_score`/`rank_dialogue_view`, `weight_*` knobs,
    `WEIGHT_MIN/MAX`; loader-turn parity at all-1.0; `dialogue_view` re-defined as the
    weight-ranked view beside the raw `items` echo). C# mirror shrunk field-for-field and the
    harness re-composed (the gate stays **24 checks** — the divergence + reputation-callback
    checks replaced by the [10a] parity / [10b] re-rank pair); Unity adapter + demo driver
    shrunk; the Ledger turn panel single-view; docs propagated (architecture §9 rewritten as
    the living seam + §13 re-scoped to the surviving signature claim, CLAUDE.md's six-role +
    one-scalar wording — the edit A1 owned, `split-brain-streaming.md` retired with a banner,
    cli-harness/read-path/unity-client/test-suite annotated, eight `floors.md` supersede notes
    + the new A1 row). Net −923 lines.
  - **Verified:** independent floor-verifier **PASS**, everything re-run fresh — all seven
    walkers (write 53 / read 56 / CLI **51, rewritten from 67** / gate 51 / reconstruction 42 /
    authorial 34 / fact 34) + smoke test, full suite **63** + keyless subset **53**, both C#
    builds 0 warnings, the live interop gate **24/24**,
    retrieval/gate/eval_metrics/reconstruction/migrations byte-identical to HEAD, product DB
    pristine, config surface exactly six roles.
  - **Blocked:** the Unity Play-mode gate re-run — the Editor wasn't open before session start,
    so no `mcp__UnityMCP` tools registered (the known 2026-07-28 ordering constraint).
    Mitigation on record: the committed plugin DLL is sha256-identical to a fresh Release build
    of the tree (the verifier's provenance proof); the 8/8 re-run is the next editor session's
    first move, and the stage-2 floor row carries the dated re-open note.
  - **Honest notes:** harness beat [10b] needed one re-aim — the first utterance was too
    generic for the recency-kill to re-order the fixture, so it now targets the 94-day-old toll
    observe (the flip is structurally argued, not tuned; one red gate run in between).
    `app\gate.py:29`'s stale "reputation_snapshot trust class" comment phrase deliberately left
    — the file's byte-identity to HEAD is verification evidence; logged as a post-A1 hygiene
    item for whenever gate.py is next legitimately touched.

- **2026-08-05 — Unity gate re-run + Phase B1: eval-harness stage 2 (the runner).**
  - **Landed (1 of 2):** A1's pending proof CLOSED as the session's first move — the Editor
    was open before session start (the ordering constraint held), and the Play-mode gate
    re-ran **8/8 GREEN** fake-mode (agent 594b2a18, +13 frames, 0 console errors/warnings —
    the shrunk adapter compiled clean; `longmem_smoke` created/migrated/dropped; scene not
    saved). Fake-only by ruling; committed as `97bbf80` with the floors 19/21 resolution notes.
  - **Landed (2 of 2):** eval-harness stage 2, built to the contract paragraph verbatim:
    `app\scratch_db.py` (the promoted `scratch_uri` + pid-scoped provision/drop with the
    double product-DB refusal), `app\eval_scenarios.py` (strict schema, one loader,
    membership-only `check_expected`), `app\eval_runner.py` (`run` + `drift-validate`), the
    two-hunk `drift_observer` seam, the smoke + drift fixtures, `.gitignore` runs rule, suite
    Set H (72 total). Four forks ruled at plan approval (all recommended options, first
    pass); forks 7/8/10 settled as the spec recommended; details in the dated `decisions.md`
    entry.
  - **Verified:** independent floor-verifier **PASS**, everything re-run fresh — suite 72 +
    keyless 61, reconstruction walker 42 (the None-default byte-identity proof) + read-path
    56, fake e2e 6/6 twice byte-identical, plumbing drift 7/7 + the exit-2 mode-gate
    refusal, TEST-NET no-dial-out refusal proof, `longmem` pristine, ledger 001–005. The
    ruled single real-mode `drift-validate`: **7/7 items, 0 over budget, p50 0.030 / p95
    0.100 / max 0.120** vs threshold 0.35 — the stage-2 BUILT banner's numbers.
  - **Honest notes:** the first e2e smoke of the runner ran in REAL provider mode by
    accident — `.env` carries `LONGMEM_PROVIDER_MODE=real` from earlier real-mode work and
    the runner (correctly) honors it; ~$0.03 of unplanned spend, all six checks passed, and
    every subsequent offline run set the fake override explicitly. The first fake run then
    exposed two expected-ID k-cut flips — hash-derived fake importance outranked similarity —
    fixed by pinning fixture scoring with explicit config facts (`importance_norm_floor:
    1.0` + `decay_k_importance: 0.0`), not by mining probe text; recorded as build latitude.
    Nothing blocked; nothing abandoned. Next session: Phase B2, the judge layer.

- **2026-08-07 — Phase B2: eval-harness stage 3, the judge layer (Fable 5).**
  - **Landed:** stage 3 built to the spec contract with one API-forced correction,
    floor-verified (the twenty-third `floors.md` row; the dated B2 `decisions.md` entry
    records the four plan-approval rulings — **Opus 4.8 judge** (the spec's sonnet-class
    recommendation would have self-graded the sonnet arm of the first real compare), the
    `LONGMEM_DIALOGUE_THINKING` knob built now (the queued "measure or drop" resolves to
    measure), the smoke+gold sequencing, the three spec knobs as recommended — plus the
    build latitude). The pieces: config (`LONGMEM_MODEL_JUDGE` loaded-never-required — the
    2026-07-29 ruling as Set I's regression test — `LONGMEM_JUDGE_MAX_TOKENS`, the thinking
    knob, judge prices, all on the override allowlist); providers (Fake/Real judge +
    failure fakes + standalone `build_judge_provider`; the real judge runs adaptive
    thinking with NO sampling params — the spec's "temperature 0" was unimplementable on
    the 4.7+ API, corrected in place, dated); the pure `app\eval_judge.py` (four versioned
    rubrics, pydantic verdicts, position-swap combine with disagreement⇒tie, hand-rolled
    kappa with honest-None, Pareto non-domination, blind gold rows); the runner's judged
    pass (prose capture judged-only, per-item `judge_failed`, judge ms/tokens/USD at the
    seam, the `models` provenance stamp) + three verbs (`compare` over arm-overlay JSON
    files, `emit-gold`, `agreement --kappa-bar 0.6`); fixtures (`judged.jsonl` — 8
    scenarios, 24 sf + 24 abstention with a true-premise control per trio; three committed
    arm files incl. `sonnet5-thinking-off`); suite Set I (14; suite 72 → 86, keyless
    61 → 74).
  - **The ruled single real judged smoke** (~$0.58 of the $2 budget; judge $0.398,
    36,784/8,574 tokens, ~2.8 s/verdict): 12 scenarios / 62 turns / 44 observes /
    0 degraded, 6/6 structural checks, **0 judge_failed across all 78 verdict items** —
    sf 18/24, abstention 23/24, faithfulness 88/89 facts + 63 fabricated-claim flags
    (7 never-reconstructed memories honestly skipped). *Pre-agreement readings, not yet
    quotable.* The instrument earned itself on run one: lexical gist-precision 0.765 vs
    the judge's semantic support 0.9888 — the paraphrase-slack gap the spec predicted —
    and 63 judged embellishment flags where the lexical entity-detector saw 2. `emit-gold`
    produced `data\eval\gold\candidates-2026-08-07.jsonl` — **78 blind rows (24/24/30)
    awaiting Jack's labels**.
  - **Honest notes:** (i) the spec's "temperature 0" and "seven-role" wordings were both
    stale/unimplementable — corrected in place, dated, with the supersede noted in the
    decisions entry; (ii) `docs\test-suite.md` had not been touched since stage 1 (no
    Set H section, 63/53 counts) — that propagation debt cleared this session alongside
    Set I's section; (iii) the session was interrupted mid-fixtures by an external task
    and resumed clean (the Unity MCP bridge disconnected in the gap — irrelevant, B2
    touches nothing Unity-side); (iv) a heredoc doc-append corrupted one path in the
    decisions entry with a BELL byte (the fifth bite of the known trap) — caught by the
    standing grep-verify rule, fixed, the entry swept byte-clean; (v)
    `unity\Assets\Scenes\SampleScene.unity` sits dirty in the worktree (A1-removal
    serialization fallout from an Editor save, predates this session) — deliberately kept
    OUT of the B2 commit, awaiting Jack's call. *Resolved same session:* Jack ruled Unity
    an extension of the repo (the dated "Unity state is ordinary repo state" entry in
    `decisions.md`); the scene diff was inspected (exactly the three stale A1 fields
    dropped, `autoRun: 0` preserved), the Editor console verified clean, and the scene
    committed in the wrap-up commit.
  - Nothing blocked; nothing abandoned. `agreement` and the real haiku-vs-sonnet-5
    (± thinking-off) `compare` are built and fake-verified but deliberately unrun in real
    mode — next session opens with Jack's labels → `agreement` vs the 0.6 bar → the first
    real `compare`, then B3 (stage 4, the fixed-gist ablation → R7's deciding data).

- **2026-08-07 — Full-repo audit, run parallel to Jack's offline gold labeling (Fable 5).**
  - **Landed:** the mechanical re-verification of all standing floors — everything green
    (full evidence in the dated 2026-08-07 entry of `floors.md`'s re-verification-passes
    section: suite 86, walkers 53/56/51/51/42/34/34, migrate no-op, `longmem` pristine,
    C# 0 warnings + DLL provenance clean, interop gate 24/24, eval fake e2e all three verbs,
    blobs CR-free, gold blind intact). A six-file doc-drift fix set, each edit under its
    register's rules: `SETUP.md` (suite 55→86, subset 48→74, ten→eleven routes),
    `decisions.md` index header (45→49, recounted, one-to-one with the body),
    `unity-client.md` (dated banner note — gate 21→24, stage-2 closure history; the eleventh
    verb row `ReconstructionMetricsAsync`; the done-when §2 field list), `mid-dialogue-gate.md`
    (two dated `assemble_system_prompt` → `assemble_prose_prompt` rename notes),
    `test-suite.md` + `tests\CLAUDE.md` (the unscored carve-out grown to its ruled three
    members). Sub-agent usage held to ONE doc-auditor (sonnet) per Jack's economy constraint;
    it returned 8 findings — 7 fixed as mechanical drift, 1 reported for Jack's judgment
    (status.md narrative accumulation vs "live state only"). Roadmap-ordering audit: sound —
    no dependency inversions found; next-session queue verified ready on disk (arm files
    tracked, gold file well-formed).
  - **Honest notes:** (i) the interop-gate first attempt FAILED on the audit's own runner
    (undrained stdout pipe deadlocked the served backend mid-harness) — diagnosed runner-side
    (port free, DB pristine), re-run clean 24/24; (ii) one eval e2e invocation ran REAL by
    omission of the fake-mode override — ~$0.03 measured plus a real `drift-validate`
    (incidentally corroborating the ruled 2026-08-05 drift numbers) and a judged leg killed
    within ~a minute; orphan scratch dropped, all three legs re-run fake and green;
    (iii) the agreement input `data\eval\runs\run_20260807T193049Z_pid_31688.json` is
    gitignored and exists ONLY on this machine — losing it before next session's `agreement`
    means re-buying the ~$0.58 judged smoke (surfaced, not acted on); (iv) Jack's in-progress
    gold labels were never touched and no per-row judge verdicts were surfaced anywhere in the
    audit output (blind preserved).
  - *Post-report, same session:* Jack took the one judgment finding — `status.md` pruned back
    to live-state-only (−26 net lines of re-accumulated ruling-narrative: the phase header
    compressed to queue + pointers, the DONE A/B roadmap bullets shrunk to landed-pointers with
    their *Why* rationale lines kept — ruling 7 of the 2026-08-04 scope entry names the roadmap
    as the rationale's recorded home — and A1's stale "pending Unity proof" cross-reference
    fixed in passing; every removed fact was verified present in `decisions.md` / `floors.md` /
    this file before cutting). An application of the standing 2026-07-28 live-state-only rule,
    not a new ruling — no decision-register entry. All eight audit findings now closed.
  - Nothing blocked; nothing abandoned.

- **2026-08-12 — The measurement line executed end to end under the gold-label workaround
  (Fable 5, one long autonomous run; plan approved + four forks ruled by Jack at spec).**
  - **The occasion:** Jack ruled he cannot make time to hand-label the 78 blind gold rows and
    directed a workaround that keeps the line moving. Plan-mode exploration found a second,
    independent blocker no labeler could fix: the judge-side marginals on the emitted
    candidates are degenerate (rf 30/30 `supported`, abstention 23/24), so kappa was
    undefined-or-zero by arithmetic regardless of who labeled. Both problems were ruled on at
    plan approval (single blind model pass; a constructed-truth set; scope through B3;
    fork 11 = exclude) — the two dated 2026-08-12 rulings entries plus the stage-4 build
    record in `decisions.md`.
  - **Landed (eight commits):** the rulings entry + the single-copy judged artifact preserved
    tracked; the blind Fable-5 reference pass on all 78 naturals + the first `agreement`
    (sf kappa 0.75 PASS, abstention 1.0 PASS — same single failure flagged by both raters —
    rf honestly degenerate); the `judge-gold` verb (sixth) + Set I tests; the 34-row
    constructed-truth set (authored by an isolated subagent, reviewed row-by-row, one
    transcription slip caught in review) → the real Opus judge discriminated **every known
    case correctly (rf kappa 1.0 n 18, abstention 1.0 n 16)** — every category now clears the
    bar on at least one instrument, per-category quotability recorded; BOTH queued compares
    (sonnet-5 prose judge-preferred 46–7 and 41–9 thinking-off; haiku alone under the 1 s bar
    at 943 ms p50 vs 2626/2086 ms, ~20% cheaper; artifacts: A preserved tracked, B gitignored
    with numbers quoted here per fork 7 — run B's accuracies 0.901/0.9738 vs run A's tied
    0.9688s are single-run judged variance, stated as such); the pairwise gold round (30 rows,
    position-shuffled blind labeling un-swapped at merge) whose `agreement` **failed the bar
    honestly — kappa 0.37**, decomposed in the provenance sidecar (2 tie-protocol mismatches +
    3 close-pair flips against 25/3/2 marginals) — pairwise judged numbers stay unquotable;
    **B3 built, floor-verified (the twenty-fourth row, 7/7), and run real: R7's deciding data
    — the drift budget is blind to the gist constraint (0 over-budget both arms, mean paired
    |Δ| 0.056) while gist-precision drops 0.8335 → 0.7036.** Docs: stage-4 BUILT banner,
    fork 11 ruled in the table, floors row 24, status re-pointed at the two open rulings.
  - **Honest notes:** (i) the first compare-B attempt CRASHED ~6 min in — the real write model
    emitted typology `observed|told`, nothing clamps model-emitted typology to vocabulary, and
    the `memories_typology_check` CheckViolation killed the run (no artifact; scratch DBs
    dropped cleanly by the `finally`); the retry passed; the robustness fork (clamp / re-ask /
    degrade-per-observe) is chipped for its own scoped task and carried in `status.md`;
    (ii) the intended fake dry-run of `judge-gold` ran REAL by the `.env` real-mode trap
    (`--plumbing` permits fake, never forces it) — $0.16, join clean, kept as the real
    measurement (recorded in the validation entry); (iii) `verify_reconstruction.py` first
    failed with a 30 s `PoolTimeout` that turned out to be `longmem_test` MISSING entirely
    (dropped at some point since the 2026-08-07 audit; psycopg_pool masks
    database-does-not-exist) — recreated + migrated, walker 42/42 green; the walkers'
    carried-item note in `status.md` records the bite; (iv) the heredoc backslash trap bit a
    SIXTH time writing floors row 24 (`\r`/`\a`/`\t` costumes, the collapse CONSUMING the next
    letter — `app<CR>econstruction`), and the lone CR additionally made `text=auto` refuse LF
    normalization so one commit carried a CRLF blob; caught by the byte-audit ritual, repaired
    via Write-tool scripts, blob re-normalized (zero-CR-at-HEAD restored, follow-up commit);
    (v) total real spend ≈ $6.10 (constructed round $0.16 + compare A ≈ $2.5 + the crashed
    partial + retry ≈ $3 + the judge-free ablation ≈ $0.4), inside the plan's $5–6.50 estimate
    plus the crash's partial loss.
  - **Blocked / for Jack:** R7's ruling (deciding data delivered); the dialogue-model
    re-ruling (deciding data delivered; pairwise quotability caveat stated); the typology
    robustness fork (chipped); pairwise gold quotability (needs Jack's labels or a
    tie-aware two-pass reference protocol — surfaced, not self-ruled). Nothing abandoned.
  - *Post-wrap, same session:* **Jack ruled R7 on the delivered data** — the budget keeps its
    mechanism and 0.35 threshold and is re-scoped as a TOPIC guard (wholesale
    nonsense/topic-swaps); factual faithfulness is policed by fact-survival (gist constraint +
    gist-precision) and the LLM judge; nothing changes at runtime. The dated "R7 resolved"
    entry in `decisions.md` records it with the rejected alternatives; propagated to
    `architecture.md` §7, `reconstruction.md`, the knob comment in `app\config.py`, the
    stage-4 banner, and `status.md` (R7 → recently-closed; no tuning follow-up — the ruling
    changed documentation, not the metric).
  - *Second post-wrap ruling, same session:* **Jack re-ruled the dialogue model — HAIKU
    stands, latency rules.** Perceived time-to-first-word is decisive (943 ms p50 vs
    sonnet-5's 2626/2086 ms against the 1 s bar); sonnet-5's 46–7 / 41–9 prose preference is
    on the record and rejected as not justifying the latency; the B2 thinking-off question is
    closed by the same measurement (recovers ~21%, still >2× the bar). The dated "Dialogue
    model re-ruled" entry carries the numbers, caveats (pairwise below its agreement bar —
    direction-only; latency is structural and quotable), and rejected alternatives; the
    2026-07-29 deferral is discharged in `architecture.md` and the harness doc. No config
    change — `.env` and the arm files already carry the ruled state. **Phase B is fully
    closed; the queue opens at C1 with zero open rulings.**
  - *Third post-wrap ruling, same session:* **Jack ruled the typology fork CLAMP** (the chip
    superseded — executed in-session instead). Built at the parse seam in `app\providers.py`:
    `TYPOLOGY_VOCABULARY` + `clamp_typology` (in-vocab passes through; first vocabulary member
    found in a malformed value wins — `observed|told` → `observed`; no member → None → ingest's
    existing `typology_default` path; confidence dropped with an unusable label; every clamp
    logged). The declared path stays a loud 422 by wire contract — clamping applies only to
    model output. New structural test in the degradation suite (the real crash value among its
    cases + the tri-source vocabulary canary); suite `-m "not nlp"` **82**;
    `verify_write_path.py` **53/53** — the write-path floor holds. Flagged in passing, carried
    unruled in `status.md`: `typology_confidence`'s `float()` sits outside the parse try —
    a non-numeric confidence would still crash rather than degrade (same class, one seat
    over). The dated "Typology robustness ruled" entry carries the shape and the rejected
    alternatives (re-ask; degrade-the-observe; status quo).

- **2026-08-12 (second session) — Phase C1: deferred write processing, spec-to-floor in one
  pass.**
  - **Landed:** the full C1 target (`deferred-writes.md`; migration 006; the three dated C1
    entries in `decisions.md`). Spec first: three explorers + a plan agent under plan mode;
    the four forks + the carried `typology_confidence` seat presented as an AskUserQuestion
    batch with recommendations — **Jack took all five recommended options first pass** (the
    A1 precedent holds). Build: migration 006 (both write_cause CHECKs widened for
    `'enrichment'`; pending/attempts/triggers bookkeeping on `memories`; the
    `memory_enrichment_runs` per-attempt instrumentation table — a background worker has no
    response payload to ride); four `SERVICE_DEFAULTS` knobs (kill-switch landing 0.0);
    the ingest seam's extract-only refactor (write-call / typology / escalation / span
    stages promoted module-level; sync path byte-unchanged — `verify_write_path.py` 53/53
    untouched is the parity proof) + the deferred branch (NLP + embedding + insert stay
    synchronous; scalars land NULL under `enrichment_pending`; the five non-importance
    triggers persisted); `app\deferred.py` (skip-locked claims, one attempt per row per
    drain pass, orphan sweep, terminal fill byte-equivalent to the sync scoring-failed
    end-state; started at BOTH construction sites); completion by supersession
    (`'enrichment'` joins the drift-anchor set; cache eviction on every completion shape);
    the `salvage_confidence` seat fix; wire deltas mirrored in `Models.cs`; the Ledger
    badge; the load driver's `observe_total` series. Two invariant amendments propagated
    (CLAUDE.md, architecture, read-path, test-suite Set C): the one-shot NULL→value
    completion carve-out beside `pinned`, and deferred-enrichment completion as
    byte-identity's third sanctioned cause.
  - **Verified:** suite grew 95 → **108** (Set K: 12 unmarked + 1 nlp; subset 94, ×2 green);
    all EIGHT walkers passed on fresh `longmem_test` — including the new
    `verify_deferred_writes.py` **51/51** and the gate walker's mechanical ledger-pin bump
    to 006; migrate idempotency (001→006 + clean re-run); both C# builds 0-warning; the
    24-check console harness gate; independent floor-verifier **PASS → floors row 25,
    verdict returned 2026-08-13** (the laptop closed overnight mid-dispatch; re-dispatched
    next morning and the verifier re-ran the full slate itself, including its own 10/10
    migration-shape probe and a live product-DB pristine re-check after its runs). Its one
    non-failing flag, recorded honestly: four docs had pre-recorded the pass ahead of the
    verdict — a wording-habit note for future landings (write the claim after the verdict,
    not before).
  - **Build-latitude findings** (recorded in the build-record entry): the first Set K run
    caught same-drain re-claiming (a failed row burned its whole budget back-to-back —
    fixed with a per-pass exclusion list; the poll loop is the retry spacing); escalation
    novels write components + spans, never memory entities (sync parity — the approved
    plan's entity-union sketch was corrected against the actual sync semantics); the
    stale-comment carried note at `ingest.py:234` was found already fixed. **Blocked:**
    nothing. **Abandoned:** nothing — though three migration pins took their routine +006
    bumps (the eval-runner's ledger count and table census — the census one surfaced only on
    the FULL suite run, it is nlp-marked — and the gate walker's ledger list).
  - The walkers' shared fixed-name scratch DB stays a carried item (re-provisioned
    per-walker this session without incident).

- **2026-08-13 — Interim public README: the repo's public face until the demo.**
  - **Landed:** the session target ruled at plan approval (four-question batch: full
    showcase ~210 lines; mermaid + a REAL Ledger screenshot — Jack chose more than the
    diagram-only recommendation; the AI-assisted build owned in one paragraph; stale counts
    fixed alongside). README.md rewritten in 13 blocks — thesis kept, "dissonance-driven
    defense" trimmed from the pitch (unbuilt; moved to the roadmap), status blockquote,
    mermaid turn pipeline, the record section with the Ledger capture, measured numbers with
    the quotability rulings respected (the prose-preference counts stay out; the natural-rf
    degeneracy reported as a failed bar beside its constructed-truth closure), verification
    section with the AI-pair paragraph, quickstart, the what-this-is-not paragraph F1 had
    planned (no auth / no rate limiting / loopback-bound — written now), plain-name roadmap,
    layout/reading/lineage/license. The Ledger gained `?agent=&memory=` chain deep-links
    (the capture mechanism; also a demo-choreography hook; dated addendum in
    `unity-client.md`) and an overlapping-gist-span render fix — the first capture showed
    duplicated observation text where escalation spans overlap base spans; the stored record
    was never wrong, the inspector's render was. Screenshot: real-mode seed against a
    throwaway scratch DB (`longmem_readme_shot`, migrated 001–006, dropped after; the
    product DB untouched) — agent Maren, four observes (one pinned, one authorially
    corrected, two aged 35 days), one init reconstructing both aged rows (2 write-backs,
    0 drift refusals) — captured headless to `docs\media\ledger-memory-chain.png` (126 KB;
    gist precision 1.00 visible on screen). Stale-count propagation: SETUP.md (001–006;
    108/94), docs\README.md (eight walkers), test-suite.md (Set I sixteen).
  - **Verified:** screenshot QA'd after the render fix (chain fully rendered, superseded row
    greyed, gist marks clean); bare `/ledger` regression-shot unchanged; suite subset run
    mid-session after all edits — **94 passed in 19.2 s**; README relative links audited
    against the tree.
  - **Blocked:** nothing. **Abandoned:** nothing. No floors row — no layer landed. The
    flip itself (push + GitHub visibility) is Jack's action after this session; the dated
    ruling entry is in `decisions.md`.
  - *Post-review addendum, same session:* Jack ruled zero em-dashes in the README after
    reading it (a standing taste for public-facing prose under his name; en-dashes and
    hyphens stay). Applied throughout, mermaid labels and tables included, verified by
    character count, committed as its own follow-up. Internal registers keep their existing
    register. The ruling was recorded in `decisions.md` at the 2026-08-15 wrap-up.

- **2026-08-15 — C2 design dossier: reflection's six forks ruled (second session this date).**
  - **Landed:** the session target ruled at plan approval (dossier + in-session fork rulings;
    one file, `docs\reflection.md`, maturing into the build spec). The dossier written in
    house style — the ruled shape collected (twelve standing items + two leaned-on facts),
    eight design areas, the scope boundary against the cut list, the C3 contract, a
    contradictions register, the verification preview, the settle ledger. The six forks
    presented in two batches (4 + 2, the C1 rhythm) — **Jack took all six recommended
    options first pass**: (1) scheduling composes — the endpoint stays the verb, an optional
    sibling `ReflectionWorker` on C1's lifecycle contract, default OFF, pressure-thresholded;
    (2) beliefs live in the dormant-since-001 `reflections` table only — retrieval untouched,
    citations in the existing `source_memory_ids`; (3) the identity package — model-free
    concatenative render, LLM consolidation landing as a new reflection that bi-temporally
    absorbs what it summarizes, and the dialogue prompt moves onto the rendered document
    (the raw-seed asymmetry found this session at `app\dialogue.py:311` — without the move,
    NPC speech would never see a reflection); (4) component trim gains
    constraint-follows-liveness (found: `fetch_reconstruction_sources` reads spans with no
    liveness join, `app\db.py:916-923`, so a trim would remove nothing today) + its eviction
    ruled the FOURTH sanctioned mid-scene cause (invariant text amends with the build);
    (5) RRR is a guard on identity consolidation, not telemetry; (6) `LONGMEM_MODEL_REFLECTION`
    judge-shaped. Rider ruled the same session: the stale habituation wording annotated in
    architecture §2/§8 (cut 2026-08-04). Propagated: the dated `decisions.md` entry (+ index
    line, count 60 → 61, and the amendment note on the primary "endpoint + pressure gauge"
    entry), architecture §10 rewritten to the ruled composition + the §3 role parenthetical,
    CLAUDE.md's role sentence, `docs\README.md` spec-table row, `status.md`, this entry.
  - **Verified:** control-byte grep clean over the new doc (the standing scripted-write trap
    — not triggered, checked anyway); decisions index recounted 61/61; docs-only session, so
    the Stop-hook subset is the only suite gate.
  - **Blocked:** nothing. **Abandoned:** nothing. No floors row — no layer landed. Next: the
    C2 build spec session turns the dossier's settle ledger into spec rulings in the same
    file, then the build (Set L, the ninth walker — which inherits the walkers' carried
    shared-scratch-DB limitation — and migration 007 iff the worker's `reflection_runs`
    table).

- **2026-08-15 — C2 build spec: `reflection.md` matured to the build target (same sitting
  as the dossier, at Jack's call — the session was short).**
  - **Landed:** targeted seam reads (route idioms, `SERVICE_DEFAULTS` comment style,
    `app\decay.py`, the session runner, provider factories, Set K's suite conventions),
    then the full rewrite of `docs\reflection.md` into the Phase C2 build target:
    the reflect pipeline, deterministic top-k sampling (decay-module recency ×
    importance-norm, ties on memory_id), the pure prompt + conclusions-only output
    contract, RRR mechanics, render/consolidation/dialogue-seam contracts, the worker
    (`sweep()` deterministic entry; NO attempts ledger — pressure persistence is the
    retry, the stated contrast with enrichment), the pressure formula, the degradation
    ladder, ten knobs, migration 007 (`reflection_runs`, agent-keyed, worker runs only),
    instrumentation/wire, the verification plan, `[SETTLE-AT-BUILD]`, done-when 1–11.
    The four spec forks presented as one batch: **three recommended options taken; trim
    criteria ruled AGAINST the recommendation — PURELY MECHANICAL** (the first divergence
    in the C2 line; the concrete three-clause rule — span-evidence-only,
    all-evidence-stale within `reflection_trim_stale_seconds`, never the current sample —
    plus the 0.0 kill-switch and the no-pin-clause reasoning, shaped under spec latitude
    and recorded in the dated entry).
  - **Honest note:** the spec draft went to disk with its rulings section phrased
    post-verdict BEFORE the batch went out — the C1 floor-verifier's "write the claim
    after the verdict" lesson, nearly repeated. The batch followed immediately and the
    divergent trim ruling was reworked in before anything else happened; no verdict was
    recorded that Jack had not given, but the order was wrong and is named here so it is
    not repeated.
  - **Verified:** control-byte grep clean over every doc touched; decisions index
    recounted 62/62; docs-only sitting — the Stop-hook subset is the only suite gate.
  - **Blocked:** nothing. **Abandoned:** nothing. No floors row — no layer landed. Next:
    the C2 build session (`app\reflection.py`, migration 007, Set L, the ninth walker,
    the dialogue-seam + reconstruction walker re-runs, the independent floor-verify, the
    post-landing believability run).

- **2026-08-15 — Phase C2 build: reflection landed, spec-to-floor in one sitting (third
  session this date).**
  - **Landed:** the full `reflection.md` spec as code — migration 007 (`reflection_runs`;
    the three pins bumped, the census order confirmed against real collation);
    `app\reflection.py` (pipeline 1–9, `compute_rrr`, `ReflectionWorker` with `sweep()`,
    NO attempts ledger); the judge-shaped `LONGMEM_MODEL_REFLECTION` role + standalone
    factory + Fake/Failing/Malformed/Real providers; db.py's reflection section (the
    3-clause mechanical trim, the pressure aggregate, the step-7/8 transactions, run
    rows) + the constraint-follows-liveness join in `fetch_reconstruction_sources`; the
    extended model-free identity render; THE DIALOGUE-SEAM MOVE (the prose prompt rides
    the rendered document for the caller-frozen version — zero reflections render
    seed-verbatim, byte parity walker-asserted); the reflect route (404/409/422/502) +
    REPL `:reflect` + the worker at both construction sites; eleven `SERVICE_DEFAULTS`
    knobs; suite Set L (20 scenarios, ALL unmarked — subset 94 → 114); the ninth walker
    (60/60); the C# mirror field-for-field + four interop beats (24 → 28); the Set I
    load-rule amendment; the fourth-sanctioned-cause invariant amendments (CLAUDE.md +
    architecture §7) + the `mid-dialogue-gate.md` "only grows" expiry + the doc sweep.
    Jack ruled four plan-batch forks (all recommended options taken: post-commit
    re-render; tri-state REPL tokens; the keyword-only provider test seam; the real-mode
    believability run) and the approved plan resolved the spec's `[SETTLE-AT-BUILD]`
    ledger — the dated build record in `decisions.md`.
  - **Verified:** the independent floor-verifier returned **PASS**, re-running everything
    itself — suite 128 full / 114-subset, all NINE walkers on fresh scratches (write
    53/53 + read 56/56 byte-untouched = the zero-retrieval-change evidence; gate 51 with
    the +007 ledger pin), migrate 001→007 fresh + idempotent, the 13-table census, both
    C# builds 0-warning, the 28-check interop gate re-run live, the product DB pristine
    (ledger exactly 001–006, zero reflection rows — applying 007 to the product store is
    Jack's action, deliberately left to him). Believability: the real-mode stage-2 smoke
    vs the 2026-08-07 real baseline — checks 6/0 both, gist 0.7667 → 0.9, keyword
    retention equal, the rest single-run noise; no regression. Floors row 26.
  - **Honest notes:** (1) the deterministic fake's repeat conclusions tripped RRR
    (measured 0.905) inside the suppress-when-due scenario that was not testing the
    guard — fixed with the fixture-pin discipline (threshold pinned >1 there), and the
    RRR scenario itself asserts ≥ threshold rather than an exact 1.0 (the identity block
    shifts between calls, so repeats are near- not byte-identical: the guard working as
    designed); (2) same-transaction reflection inserts share one `created_at` (Postgres
    stamps transaction time), so Set L asserts membership, not row order — the happy
    path's first green run was UUID luck, caught by an immediate re-run; (3) the
    verifier's one finding — three stale `SETUP.md` counts the propagation sweep
    missed — fixed before commit; (4) the spec sitting's "ten knobs" phrase was a
    miscount of its own eleven-row table; the build followed the table and the build
    record says so (the applied entries stay unedited, append-only).
  - **Surfaced, not fixed:** `reconstruction_metrics`' fabricated-entities baseline uses
    the seed-only 1-arg render, so a belief-introduced entity would count "fabricated"
    once identity-relevant reflections exist. `retrieval.py` is ruled untouched and
    reflection ships default OFF — flagged for Phase D (or C5's neighborhood).
  - **Blocked:** nothing. **Abandoned:** nothing. Next: C3 (reflection → parameter
    compiler) per the roadmap; the deferred + reflection default flips stay Phase D
    questions.

- **2026-08-17 — Phase C3 build: the parameter compiler landed, plan-to-floor in one
  session.**
  - **Landed:** the seven rulings settled at the plan-mode fork batches BEFORE any file
    changed — five design forks (feedstock = ALL live beliefs; typed core = the three
    weight multipliers only; scheduling = the STANDALONE third worker, where Jack took
    the LARGER option over the recommended reflect-pipeline stage and the follow-up
    fork ruled it lands WITHOUT the generic jobs table; the all-mechanical staleness
    guard; the judge-shaped role) plus the two migration-freeze rulings (the
    [0.25, 4.0] clamp; `:compile` sweep semantics). Then: migration 008
    (`compiled_bundles` append-only with liveness DERIVED by join + `compiler_runs`;
    the FOUR mechanical pins bumped — the documented three plus `verify_reflection`'s
    own A5 ledger pin, found at plan time by grepping the prior migration's filename);
    `app\compiler.py` (service + the pure consume functions + `CompilerWorker` — no
    endpoint, no route, no jobs table, no attempts ledger); the provider quartet +
    `build_compiler_provider`; the dialogue-seam consume splice (`scene_type` on the
    turn request, six instrumentation terms incl. `bundle_fetch_ms`,
    `resolve_dialogue_weights` untouched, zero-bundle byte parity); session/CLI
    (`:compile` with the visible attempt count; `:scene <type>` extended — the type
    always rode the boundary event, now it also sticks as session state riding turns);
    Set M (21 scenarios, all unmarked; suite 135 subset / 149 total); the TENTH walker
    (48/48 — its docstring carries the persistent-scratch rule and the
    stop-the-poll-loop-before-counting rule); the C# mirror + interop beats [13]
    (28 → 32); the docs sweep incl. `parameter-compiler.md` and the stale-text
    corrections (architecture §12's twelve-routes/eleven-verbs/missing-reflect — a C2
    propagation miss; README's "Reflection isn't built"; `docs\README.md`'s 006 note).
    Floor-verifier **PASS** → floors row 27. Believability: no regression (checks 6/0
    both; gist 0.7667 → 0.85, above the 2026-08-07 baseline; keyword retention equal).
  - **Found along the way:** the verifier demonstrated `verify_reflection` is
    non-re-runnable on the persistent `longmem_test` — its B6/E9 DB-global counts get
    poisoned by its OWN prior green run's rows (the carried walker-scratch item's
    SECOND documented bite; root-caused airtight as pre-existing, not a C3 regression;
    60/60 on a fresh scratch, that walker's documented precondition). `longmem_test`
    currently holds those rows plus aborted-run fixtures — normal walker writes, left
    as-is for the carried item's own future task.
  - **Honest notes:** (1) the floors row was first appended via a Python heredoc and
    the backslash doc-corruption trap bit a SEVENTH time, in a NEW silent costume:
    `\t`/`\v` are VALID Python escapes, so TAB/VT landed and ATE the following letter
    with no SyntaxWarning (unlike the invalid-escape spots, which warn and preserve),
    and `write_text`'s newline translation CRLF'd the whole file besides; the standing
    grep-verify-control-bytes rule caught it, the row was rewritten byte-level from raw
    strings, and the file re-verified clean. (2) The interop gate's first run failed on
    the new beat's own premise — earlier beats' narrative boundary types now stick as
    session state by design; fixed with a clearing bare boundary in the beat, not a
    code change. (3) The stage-6 probe first raced the auto-started poll worker's
    startup sweep — the deterministic-count rule (stop the loop before seeding) is now
    recorded where it belongs.
  - **Verified:** control-byte grep clean over every touched doc (after the repair);
    the product DB pristine before and after (ledger exactly 001–006 — applying
    007 + 008 to the product store stays Jack's action).
  - **Blocked:** nothing. **Abandoned:** nothing. Next: C4 (dissonance path +
    diegetic-correction event) per the roadmap; the three default flips (deferred,
    reflection, compiler) stay Phase D questions.

- **2026-08-17 — Session-effort audit: session growth measured, diagnosed, one lever
  adopted.**
  - **Landed:** a full parse of the project's own session transcripts (58 main + 202
    subagent files, 46,755 records, fork-copied history deduped by uuid) clustered into
    27 work sessions and reconciled three ways against this log and all 21 commit days.
    Diagnosis: per-unit efficiency is flat-to-improving (the best lines-per-hour week was
    Aug 09–15); what grew is the arc per queue item (~96 attributed minutes per landing in
    mid-July → ~260–290 for C2/C3), driven roughly two-thirds by the planning phase (the
    settle-at-spec discipline: the C3 arc spent 2.4 h in plan for a 1.1 h build+verify)
    and one-third by the standing per-landing apparatus (8 areas incl. the C# mirror vs
    3–5 and no client in July). Verify redundancy is real (40–65% of verify events fire
    with no code edits since the previous one) but cheap in wall time; the docs sweep +
    four-register ritual is ~10 min per arc; the auto-loaded boot cost was the one proven
    pathology (~38k tokens on 07-12 → ~100k by 07-27, cut to ~53k by the 07-28 split +
    08-07 prune, crept back to ~58.6k as status.md regrew 12 → 17.5 KB). **Jack ruled:
    option 1 only** — status.md re-pruned to live state (the trimmed prose moved verbatim
    into this file's archive, below) plus a standing ≤12 KB wrap-up tripwire recorded as a
    CLAUDE.md rule (the dated `decisions.md` entry). Options 2–6 (Stop-hook scoping, the
    walker runner as an audit rider, plan-phase sizing, rider unbundling, floor-verifier
    scoping) explicitly DECLINED — the remaining growth is accepted as the repo's real
    character. Also fixed in the prune: status.md's stale "twenty-six floors" prose count
    (27 rows stand; replaced with the pointer form its own rule asks for).
  - **Honest notes:** the audit's backing data (per-session metrics, the verify-run
    ledger, per-arc phase timelines) lives in the audit session's scratchpad, which
    evaporates in ~5 days — the load-bearing numbers are in the decisions entry, and the
    rest re-derives in a ~2-minute re-parse of the transcript store. The Stop-hook
    per-turn suite cost is an ESTIMATE (turn-ends × observed same-era subset runtime; the
    hook logs itself only when it blocks). No transcripts exist for 07-16 or the
    pre-17:53 part of 07-17; one 08-12 floor-verifier transcript spans 17 idle hours
    (left open overnight) and was capped, not counted.
  - **Blocked:** nothing. **Abandoned:** nothing (options 2–6 were declined by ruling,
    not abandoned). Next: C4 per the roadmap, unchanged.

- **2026-08-17 — C4: the dissonance path + diegetic-correction event, plan-to-floor in
  the ruled ONE session (floors row 28).**
  - **Landed:** everything the task named, on the eight plan-batch rulings (two
    AskUserQuestion batches at plan mode, all settled before a line of code; the dated C4
    build record). NO migration — the ruled per-target scope fact; the `corrections`
    table and both diegetic `write_cause` values had waited in 001 since day one, and the
    build's job was to make the mechanism real: `app\dissonance.py` (the mechanical
    defend-vs-update formula with every term a knob; the stance-forked retell through the
    RECONSTRUCTION role — ruling 2, taken AGAINST the recommended new judge-shaped var,
    the second such divergence after the C2 trim), `db.apply_diegetic_correction` (the
    chain-preserving transaction: supersede + verb-typed head + the corrections record +
    eviction; CAS; no pin/drift/fact code by design), the fourteenth route
    `POST /v1/events/diegetic-correction`, ruling 4 closing the fork the authorial spec
    deferred (`FIXED_CONSTRAINT_ANCHORS` gains `update_with_resentment`;
    `verify_reconstruction` deliberately re-opened, re-closed at 46), the REPL
    `:confront`, the chain inspector's corrections block, the C# mirror + interop beats
    32 → 36, suite Set N (23, all unmarked — the Set A diegetic pair landed after 28 days
    specced), the eleventh walker (38), and the docs sweep incl. the two ruling-8
    architecture.md `enrichment` fixes. Suite 172 full / 158 subset at the pins.
    Believability: no regression (real-mode smoke vs the 2026-08-07 baseline — checks 6/0
    both, gist 0.7667 → 0.825, keyword retention equal, the same single fabricated
    entity).
  - **Honest notes:** (1) The first walker sweep FAILED — the third documented bite of
    the carried walker-scratch item: the re-opened `verify_reconstruction`'s [13] section
    wrote correction records, and `verify_authorial_correction`'s "no corrections row"
    assert is DB-global. Resolved minimally ([13] now writes chain rows + eviction only —
    the anchor claim under test derives from the telling chain alone); the elder walkers
    stay byte-untouched and order-fragile by construction (the carried item's own future
    task; detail in the build record). (2) The floor-verifier's one finding — the product
    ledger at 001–008 against the dispatch's 001–006 expectation — was adjudicated by
    Jack the same day as HIS OWN morning apply of 007+008 (the reserved operator action,
    performed ~90 min before this session's first tool call; ledger rows byte-exact, zero
    content-table writes); the report converted to a clean pass and the standing operator
    action is DONE. (3) A suite-hygiene false positive: the guard's SQL heuristic matched
    the prompt constant `_TASK_UPDATE`; renamed `_TASK_ACCEPT` rather than widening the
    guard. (4) The committed Unity DLL is now stale against `NpcMemory.Core` (the C#
    mirror grew) — the staleness check stays Phase F's by ruling.
  - **Blocked:** nothing. **Abandoned:** nothing. Next: C5 per the roadmap — the
    agent-state read route (backend + C#) + async observes.

- **2026-08-17 — C5: client contract completion (the agent-state read + async observes),
  plan-to-floor in one session (floors row 29).**
  - **Landed:** both halves the task named, on seven plan-batch rulings (two
    AskUserQuestion batches at plan mode, all recommended options taken — the dated C5
    build record). C5 had no spec doc, so the approved plan served as the spec; the
    contract landed in `unity-client.md` + `architecture.md`, no new file. **The read:**
    `GET /v1/agents/{agent_id}/state` — the fourth unscored-by-contract member (the
    ruling `reflection.md` had pre-assigned here), NO migration (the ruled per-target
    scope fact; both 007/008 index comments had named this read as their consumer since
    they landed) — the STANDARD payload: the stored row as stored, identity currency,
    the pressure gauge (one implementation with reflect, same loud norm guard), live
    beliefs in the compiler-window order, derived-liveness bundles incl. the passthrough
    (its recorded integrator read, finally real), both workers' run logs newest-first.
    Set O (10 scenarios, unmarked; suite 172 → 182), the twelfth walker
    `verify_agent_state.py` (26 assertions, runs LAST in sweeps), the C# mirror
    (`AgentStateAsync` + five DTOs, client-only per the inspector precedent). **Async
    observes:** `NpcSession.ObserveAndForget` + `PendingObserves` + `OnObserveFailed` +
    `DrainObservesAsync` (~40 lines, no queue, no pump; world time stamped synchronously
    at the call so arrival order cannot reorder the record; failures never swallowed —
    event at failure time + ONE AggregateException at drain, cleared on drain; no verb
    auto-drains by ruling — "drain at scene edges" guidance, E2 places the drains).
    Harness beats [15]/[16] grew the interop gate 36 → 50 checks, re-run LIVE green.
  - **Honest notes:** (1) One first-run full-suite failure — the new docstrings' phrase
    "pure SELECT " tripped the SQL-containment hygiene scan (it reads docstring prose
    too); reworded to "SELECT-only", no rule change. (2) The walker's gauge hand-math
    compare needed the float32 tolerance class (importance_raw is float4) — 1e-6, not
    1e-9. (3) Believability non-regression rests on the C3 evidence class (zero
    retrieval/scoring/dialogue changes; Sets A–N green + elder walkers byte-untouched),
    not a harness compare run — flagged in the build record if Jack wants the full
    compare anyway. (4) Two stale client-doc counts corrected in-pass, dated:
    unity-client.md's verb table had been missing `ReflectAsync` since C2; SETUP.md's
    pinned harness check count had rotted twice and now points at the output line
    instead. (5) The committed Unity DLL stays stale by ruling (Phase F), now five Core
    builds behind.
  - **Blocked:** nothing. **Abandoned:** nothing. Next: C6 per the roadmap — the purge
    endpoint, the ruled release-blocker and the sole sanctioned DELETE.

## **Phase C6 — the purge endpoint landed 2026-08-18, plan-to-floor in one session (floors row 30).**
  - **Landed:** everything the task named, on the four plan-batch rulings (one AskUserQuestion
    batch at plan mode, all four recommended options taken — the dated C6 build record):
    per-memory scope, the `DELETE` verb, no guard, NO migration (the ruled per-target scope
    fact — the ledger stays at 008; purge only deletes from the existing 001–008 tables). The
    release-blocker and the SOLE sanctioned CONTENT delete, live as a docs-only contract since
    001. Backend: `db.purge_memory` (the seven-table child-before-parent delete in ONE
    transaction — no FK cascades exist, so the order is forced: corrections before
    memory_details, the six memory-child tables before the memories row; a `SELECT ... FOR
    UPDATE` existence-lock opens it for the clean 404 + race safety; honest per-table `rowcount`
    counts), `PurgeOutcome` + `PurgeResult`, `IngestService.purge_memory` (timed at the seam),
    the sixteenth route `DELETE /v1/memories/{memory_id}`. The `db.py` header's sanctioned-write
    enumeration gained purge as the FIRST content DELETE and, in the same edit, reconciled its
    stale eviction-site list (two → four — C2/C4 had added `apply_reflection` /
    `apply_diegetic_correction`). Reflections survive by design — the `parameter-compiler.md` C6
    note is closed: purge does NOT reach reflections. Suite Set P (7, unmarked; 182 → 189 full /
    168 → 175 subset), the thirteenth walker `verify_purge.py` (21 assertions, sections A–G,
    id-scoped, incl. the wire contract over `httpx.ASGITransport`). Live beat green through real
    uvicorn (fake mode, scratch DB): DELETE → 200 + counts → `/chain` 404 → reflection survives
    → re-DELETE 404. Product `longmem` DB pristine (14 tables at 0, ledger 001–008).
  - **Honest notes:** (1) Set P's first run FAILED — the seed inserted a second LIVE detail/fact
    head, tripping the one-live-head partial unique index; fixed by seeding the second rows
    superseded (`invalid_at` set), row counts unchanged. A staged-verification catch, not a
    purge bug. (2) `write-path.md`'s "Deferred, documented only" list was stale for BOTH entries
    (diegetic-correction built C4, purge now C6); reframed the whole two-item list honestly in
    the same pass rather than flip one and leave a false "no handler in v1" beside it — flagged
    for Jack. (3) `status.md` crossed the 12 KB tripwire (12518 B) on the C6 additions; trimmed
    the redundant "Recently closed" pointer litany (it lives in `decisions.md`'s index) back
    under the line (12266 B) — the tripwire's second firing.
  - **Blocked:** nothing. **Abandoned:** nothing. Next: C7 per the roadmap — the latency trio
    (concurrency cap + scene-boundary reconstruction pre-warm; then prompt caching).

## **Phase C7 — the latency PAIR landed 2026-08-18 (a trio no more), plan-to-floor in one session (floors rows 31–32).**
  - **The reframe (three forks ruled, one AskUserQuestion batch at plan mode):** exploration
    surfaced that C7's third leg, **prompt caching, is inert on the ruled Haiku slate** —
    Anthropic's cacheable-prefix minimum is 4096 tokens on Haiku 4.5 (non-monotonic: 1024 on
    Sonnet 5 / Opus 4.8, 512 on Opus 5) while the dialogue/reconstruction heads are ~0.5–1K, so
    `cache_control` would silently never cache (`cache_creation_input_tokens: 0`, no error). Ruled
    **DEFERRED to Phase D / D1** (a caching-capable model changes the math; the byte-stable head
    groundwork already exists). So C7 is the latency **pair**. The other two rulings: pre-warm
    **probe-driven** (Jack's choice over my probe-free recommendation) and the R8 guardrail
    **reuses `serve`'s drift-budget refusal** over a new gist-precision gate. All in `decisions.md`.
  - **Stage A — the concurrency cap (audit R8; floors row 31):** there was NO concurrency limiting
    anywhere; every provider call is a sync SDK call on the default thread pool, a streaming NPC
    holding a thread for its whole stream. One process-level `ModelCallGate` (`asyncio.Semaphore(cap)`
    + a bounded `ThreadPoolExecutor(max_workers=cap)`) carried on the `Providers` bundle via a
    default-factory, so every seam + worker reaches it as `self._providers.gate` with ZERO
    service-constructor churn. All 13 provider call sites → `gate.run`/`gate.acquire`; the prose
    stream holds one slot for its life; local NLP stays on the default pool by design (the knob
    names model calls). Knob `LONGMEM_MAX_CONCURRENT_MODEL_CALLS` (default 8 = the DB pool);
    `gate_wait_ms` on the dialogue instrumentation; gate shutdown at both teardowns. NO migration.
    The fourteenth walker `verify_concurrency.py` (11 assertions). Committed `ec5bf4b`.
  - **Stage B — probe-driven scene-boundary pre-warm (floors row 32):** the scene-boundary
    handler's second consumer. Optional `SceneBoundaryEvent.prewarm_context`; when present,
    `_prewarm_reconstruction` reuses `retrieve_dialogue_init` (embed → fetch → score → `serve`) with
    the probe as the query, at the freshly recompiled `identity_version` + the boundary basis, so
    `serve`'s write-backs warm the cache under the exact composed keys the first on-camera read looks
    up — folding the demo's off-camera warm-init trick into the boundary call. The R8 guardrail by
    INHERITANCE (reuse `serve` → inherit its drift-budget refusal, no new gate). Fail-quiet (a broad
    try/except → degraded record; the boundary never fails). `RetrievalService` injected into
    `IngestService` (optional, default None; both sites build retrieval before ingest; a
    `TYPE_CHECKING` import breaks the ingest↔retrieval cycle). Warm stats → new
    `ScenePrewarmInstrumentation` on `SceneResult.prewarm`. NO migration. The fifteenth walker
    `verify_prewarm.py` (14 assertions).
  - **Honest notes:** (1) `verify_concurrency` A2 first asserted `pending == 2`, wrong — at the
    settle point all N+2 tasks are pending (the admitted 2 are barrier-held in their threads, not
    "done"); A1's `in_flight == cap` already proves the cap; fixed to `pending == cap + 2`. (2)
    `verify_prewarm` B3 first asserted `reconstruction_ms == 0.0` on the cache-hit read — wrong:
    `reconstruction_ms` times the whole serve stage (theta partition + cache fetch) even with zero
    misses, so it is ~8 ms on a hit; the honest call-free signal is zero reconstruction TOKENS,
    which `cache_misses == 0` corroborates. (3) A build refinement from the approved plan: it said
    "gate everything including NLP"; the build scoped the cap to *provider* calls (NLP is local CPU,
    already default-pool-bounded, and the knob's name says model calls) — the floor-verifier
    confirmed this as sound, not a gap.
  - **Blocked:** nothing. **Abandoned:** the prompt-caching leg (deferred, not abandoned — parked
    for Phase D). **Next: Phase D** — full-system latency + believability passes, knob tuning, the
    final model-slate confirmation (the natural revisit for prompt caching). Phase C is complete.

## **Phase D1 — latency, believability, and the model-slate lock landed 2026-08-19 (measure→rule→tune→re-verify, one session, no new code, no new floor).**
  - **The shape.** D1 is the optimization phase: confirm the numbers that go on screen. The
    measurement rig was already built, so this was a pure measure→rule→tune→re-verify pass — no
    layer built, hence no floors row. Three forks settled at plan approval (the settle-at-spec
    AskUserQuestion batch): stronger batch-role models; judge-free + judged believability; and
    authority to flip worker defaults / lock knobs in D1 from the data. Real-providers-only; ~$2.5
    total spend across five real-mode stages, each on a disposable pid-scoped scratch DB (product
    `longmem` never touched — confirmed pristine, ledger 001–008, all tables 0 rows).
  - **Landed — the numbers (all real mode, current slate).** (1) Latency (load driver, 60 turns):
    perceived-first-word **p50 938 ms** / p95 1516 ms — matches the ruled 943 ms; Haiku holds the
    sub-1s bar. (2) Believability (`run` judged.jsonl): gist_precision **0.765→0.823** up,
    fabrication 0.043 low, latency 918 ms — **no regression** (reconstruction fired, 34 write-backs).
    (3) Compare/Pareto (haiku vs sonnet5, judged): haiku 0.913/1020 ms/$0.93 vs sonnet5
    0.954/2049 ms/$1.18; prose 44–4 sonnet5 — reaffirms the 2026-08-12 ruling, **haiku stands for
    dialogue, latency rules**. (4) Batch roles (real reflect+compile, Opus 4.8): 3 coherent
    evidence-cited beliefs in 17.8 s (~$0.033), 4 bundles in 7.8 s — **Opus 4.8 validated** for the
    idle-time batch roles.
  - **Landed — the config lock.** `.env.example` batch roles set to **Opus 4.8**
    (`LONGMEM_MODEL_REFLECTION`/`_COMPILER` + 5.00/25.00 prices) — the real-mode slate is now exactly
    two models (Haiku + Opus 4.8). `config.py` UNCHANGED: worker defaults stay OFF ("flip on the
    data" → per-agent opt-in, not a global flip); dissonance multipliers kept; no knob change.
    Prompt caching confirmed DEFERRED (Haiku 4096-token min > ~0.5–1K heads; re-verified vs current
    Anthropic docs). `-m "not nlp"` 175 passed (no regression). Full rulings in the dated
    `decisions.md` D1 entry.
  - **Blocked / handed to Jack (non-blocking to the landing).** (1) The **dissonance multipliers**
    have no objective tuning metric — the plan slated them for "tuning from measurements" but the
    defend-vs-update split is a design prior, not a measured quantity, and no eval scores dissonance
    correctness; kept the principled ordering unchanged, flagged for Jack's ratify/redirect (an
    eyeball run available on request). (2) Judged **prose kappa stays 0.37** (< 0.6) — unquotable;
    clearing it is Jack's offline re-labeling, non-blocking since the on-screen numbers are
    judge-free. (3) Syncing the live `.env` batch roles is Jack's action (the C2 product-store
    precedent).
  - **Abandoned:** nothing. **Tooling note:** the D1 measurement harnesses (latency-driver wrapper,
    batch-role reflect/compile validator) live in the session scratchpad, not the repo — throwaway
    measurement scripts, not product. **Next: Phase E (demo).**

## **Phase E1 — the identity authoring guide + demo corpus landed 2026-08-19 (docs + data only, no code, no floor by ruling).**

- **Session (2026-08-19).** Phase E opened; the delegated scope decision made: **three sessions**
  (E1 authoring, E2 choreography + rehearsal, E3 record). Jack's four spec rulings (new
  character, first-person paragraph seed, held-out run in-session, docs+data-only scope) in the
  dated `decisions.md` entry.
  - **Landed:** `docs\identity-authoring.md` (integrator guide, em-dash-free, indexed in
    `docs\README.md`; §8 = the worked example with real numbers); the demo NPC **Branwen of the
    Waystone Inn**; `data\eval\corpora\demo-waystone.jsonl` (9 observes, June in-world);
    `data\eval\scenarios\demo-waystone.jsonl` (3 held-out probes: Halvard correction, drovers
    drift, lodger abstention). Real-provider validation: coverage drift-validate 9/9 under
    budget (p50 0.06 / p95 0.11 / max 0.121 vs 0.35); beat-condition (drovers probe, k=3)
    membership every roll, 0.082 on a retell-mode roll; held-out judge-free run exit 0, 2/2
    checks, fabrication 0.000, keyword retention 0.979, gist_p 0.720, detail recall 0.664.
  - **The authoring loop earned its keep** (five corpus revisions, every failure caught
    pre-recording): gist saturation made the chimney fire retell-flaky (8/9 checked, diagnosed
    via kept scratch + forensic re-probe); the render witness-voices the NPC's own actions
    (first-person authoring rule); the diagnosticity goal couples importance AND gist (widening
    it fixed membership and simultaneously froze house-flavored texture); first-aged-read
    retells are per-call bimodal (rich vs verbatim echo) — mitigated by the freeze/pin
    property, handed to E2 as the inspect-then-re-provision rehearsal guard.
  - **Blocked:** nothing.
  - **Abandoned:** the chimney fire as the CERTIFIED drift target (echo-prone escalation
    magnet) — switched to the turned-away drovers (drifted 6 of 7 rolls); the fire stays in the
    corpus as the closing incident and a possible second take. Also surfaced, not built (scope
    ruling): drift-validate does not echo the turn's `degraded_reasons` into its report.
  - **Spend note:** ~10 small real-mode runs (drift-validate coverage/beat + one held-out run
    + two forensic probes), cents each; runs-dir artifacts gitignored, numbers quoted in the
    `decisions.md` entry and the guide. **Next: E2 (choreography + rehearsal).**

## **Phase E2 — choreography + the code gaps landed 2026-08-19 (demo-scoped by ruling: no floors row; rehearsal staged, blocked on two Jack-side steps).**

- **Session (2026-08-19).** Jack's four spec rulings (server tee + poll for the Ledger live
  feed with the explicit pass-through carve-out; worker flags merged at load end via the new
  `db.merge_agent_config` — the second sanctioned in-place write site; demo-scoped
  verification, NO floors row; no migration confirmed) in the dated `decisions.md` entry.
  - **Landed (code):** the Ledger live turn feed (`GET /v1/ledger/turns` + the tee at both
    dialogue routes, in-memory only); **`app\demo_loader.py`** (`--fresh`-guarded corpus →
    `longmem_demo` loader printing the provisioned-roll report + hand-off ids); C# prewarm
    parity (`SceneBoundaryEvent.PrewarmContext`, `ScenePrewarmInstrumentation`,
    `SceneResult.Prewarm`, the session param) + harness beat [17]; `NpcMemoryNpc`
    ObserveAndForget/Drain/PendingObserves passthroughs; `NpcDemoDriver` beat controls;
    the Unity scene retargeted to Branwen (attach-mode) + the stale plugin DLL refreshed
    (was four phases behind — nothing C2+ compiled in Unity until now).
  - **Landed (docs):** **`docs\demo-beat-script.md`** (three beats + close, timeline, rig,
    rehearsal checklist); unity-client.md drift fixes (prewarm contract, warm-init trick
    retired); architecture.md route census 16 → 17; SETUP.md §8 attach-mode + gate ordering.
  - **Verified (build-time):** subset 177 green throughout; new `test_ledger_feed.py` +
    `test_demo_loader.py`; the 17-beat harness GREEN (53 checks) vs a fake serve; Unity
    batch compile + scene re-import clean; loader CLI smoke (refusal exit 2 + full roll);
    a LIVE browser beat of the Ledger — identity pane + a real HTTP turn rendering through
    the 2 s poll with no paste. All scratch DBs dropped after.
  - **Blocked (the rehearsal, staged not run):** (a) the live `.env` lacks BOTH batch roles
    (checked by key presence, values never echoed) — the demo agent's workers are ON by
    ruling, so Jack's pending Opus sync now binds before the real rehearsal; (b) no Unity
    MCP bridge this session — the interactive Play-mode gate + on-screen dry-run need an
    editor session, ordering encoded in the beat script (gate BEFORE pasting the agent id).
  - **Abandoned:** nothing. **Next: the real rehearsal (beat-script checklist), then E3.**

## **E2 rehearsal — executed 2026-08-22 (blockers cleared; the recording state pinned in `longmem_demo`).**

- **Session (2026-08-22).** Jack cleared both blockers (`.env` batch roles + Unity MCP);
  this session verified them and ran the rehearsal end to end.
  - **Blockers verified, deeply:** `load_settings` clean in real mode, both batch roles at
    `claude-opus-4-8`, then PROVEN on live calls — a real reflect wrote 3 reflections and
    the compiler worker auto-ran (`completed`, 3 pairs, 1246/175 tokens, 3 bundles, 0
    failed); the interactive Unity play-mode gate ran GREEN through the live bridge
    (8 checks; autoProvision/autoRun flipped in-memory and restored, scene file untouched
    by the gate).
  - **Rehearsed (two provisions, real providers):** a full dry-run (beats 1–3 + the owed
    beat-1 relevance-move guard — PASSED; the beat-2 take echoed on that roll, the E1
    bimodal case working as documented), then the final provision: June layer + beat-2 take
    pinned (real edit, gist_precision 1.00, detail_recall 0.58, 0 fabrications, constancy
    byte-identical), correction + beat 3 VIRGIN for camera. The Ledger verified camera-ready
    on the pinned state (identity pane, drift visible per row, turn feed live). The scene's
    inspector carries the pasted agent + correction ids (committed).
  - **Found (folded into the beat script):** beat-1 asks need **k=9** — at the June-25
    basis real decay buries the June-2 Halvard memory below k=3 (the E1 correction probe
    had certified k=3 only under the NEUTRALIZED eval config; "validate in the beat's own
    condition" now proven against beat 1 too). Also: the June basis serves reconstructed
    (a June-2 memory is past theta by June 25), so scene 1 carries its own prewarm probe;
    the post-correction ask visibly re-forms the telling (cache eviction) — kept as a beat;
    re-firing the same correction is the retake lever.
  - **Blocked / Abandoned:** nothing. Session tooling (serve launchers, the rehearse.py
    beat driver) lives in the session scratchpad, not the repo (the D1 precedent).
  - **Spend note:** two real loader provisions + ~14 turns + 1 reflect + 1 compile —
    roughly a dollar. **Next: E3 (record + edit) on the pinned state.**

## **E3 first attempt — recorded + QA'd 2026-08-24; master not cut (presentation redesign ruled).**

- **Session (2026-08-24).** Forks settled at plan approval (edit = Claude + ffmpeg;
  captions-only silent; demo-scoped, no floors row, docs-only commit — amended mid-session
  by the sanctioned rig edits).
  - **Landed:** the attach-mode recording rig — driver `startAsOf` (a stop-and-report: no
    operator surface existed for the June basis; ruled, built, live-verified through the
    bridge), the overlay em-dash fix, the committed scene-1 start state; OBS + ffmpeg
    installed; the close card + run sheet; GET-only pre-flight probes (pinned state PASS at
    every step). All four segments recorded with live QA — every beat guard PASSED (wrong
    belief → correction → the five-shillings answer; the pinned drovers take with constancy
    byte-identical on the served retelling, the streamed wrapper varying by design; owned
    beat-3 recall in verbatim mode). The SEG B frame restored via the ruled re-fire lever.
  - **Blocked / redirected:** the cut. Footage QA (full-res frame pulls) found the Branwen
    nameplate mirrored in every Unity frame (TextMesh rotY 180 — invisible to the API-level
    gates) plus browser chrome, the Game toolbar strip, and the ford-era input default. Beat
    1 is unreproducible on a spent provision (the correction moves the fact chain), so no
    selective re-shoot exists. **Jack ruled: he redesigns the demo presentation in his own
    session first; the flaws stay noted, NOT fixed; then a fresh provision + full re-record
    (`--fresh` sanctioned).**
  - **Abandoned:** the ffmpeg assembly of today's footage (a flawed master is not worth
    cutting). Raw takes + assets kept under `C:\Users\jacks\Videos\longmem-demo\`.
  - **Spend note:** ~7 real dialogue turns + 1 re-fired correction; the takes themselves
    replayed pinned caches.
  - **Re-sequenced at the session close (ruled, the second dated 2026-08-24 entry):** the
    demo pauses entirely. The road is now F0 (a NEW whole-project audit/test/improve pass —
    latency, believability wording, polish) → F1–F3 → the presentation redesign → the
    re-record → the video publish. Phase G stays optional but re-pointed: the real-game
    plug-in clip is out, replaced by a personal-website embed of the project (details
    deferred until the step is ever brought forward). **Next: F0.**

## **F0 — the whole-project audit/test/improve pass landed 2026-08-26 (spec-at-plan → build → independent floor-verify pass, one session).**

- **Landed:** the whole F0 scope as ruled at the plan batch (four forks, three recommendations
  taken; README ruled wholly to F1 — the fourth divergence). (1) Register repair: floors.md's
  five newest rows moved back inside the table (they rendered as literal text — the file's
  founding failure mode, recurred); every live count reconciled to MEASURED reality (suite
  193/178 — the docs' "175" had silently drifted since E2; fifteen walkers named everywhere;
  CLAUDE.md 002–008); the doc-auditor's 16 mechanical findings all fixed (five real
  contradictions incl. architecture.md's verb count and the packaging-before-video ordering;
  one flag adjudicated not-stale by the doc's own stands-as-specced banner). (2) The init
  404/422 route-contract test — the suite's one named Known gap, closed (193rd test). (3) The
  turn-path overlap (bundles + identity + agent-state fetches under the retrieval leg;
  error primacy preserved; cancel-and-drain) + the `LONGMEM_DB_POOL_MAX_SIZE` knob (the last
  hardcoded capacity number; .env.example also gained the C7-A cap var it had been missing)
  + the driver's `pre_prose` series. (4) The dialogue-prompt UUID strip (vestigial since A1;
  three test-apparatus consumers reworked; **dialogue input −51%, all-in −23% to
  $0.084/100 turns**) and the write-prompt voice clause (identity-authoring §5's measured
  register rules, at the source) — both landed through the ruled believability gate:
  **no regression, three metrics up** (gist 0.8309, detail_recall 0.8448, fabrication 0.0159).
  Latency truth: perceived p50 sat 826–917 across the day's provider windows; the overlap's
  target component (non-embed pre-prose) fell 27–28 → 18–21 ms as designed; the D1
  attribution gap is closed (pre-prose ≈ 90% embed); the ceiling recorded (embed swap ≈
  770–870 ms headline; caching inert on Haiku; slate stands). Full suite 193 green, fifteen
  walkers green fresh+serial, C# interop 53 checks green, floor-verifier **pass** — the
  floors.md Re-verification entry + the dated decisions.md entry carry the evidence.
- **Blocked (temporarily, self-inflicted):** ~3 hours lost to a verification-chain double-hang
  — my runner let walker children inherit a backgrounded shell's never-closing stdin
  (verify_cli_harness's REPL beat blocks on it), stacked on a `pytest | tail &&` chain that
  bound `&&` to tail's exit. Diagnosed by CPU-time signature, fixed (stdin=DEVNULL
  everywhere, un-piped stages), leaked scratches dropped; lessons recorded. The hunt also
  flushed the third in-prompt-UUID consumer the static grep had missed.
- **Abandoned:** nothing. Surfaced-not-built by ruling: the duplicate-read dedupe, the
  min_size sibling knob, the driver time-jump arm, cache markup, the embed-swap spec.
- **Spend:** ≈ $0.55 real (five 60-turn driver runs + two believability legs).
- **Next: F1** (the full README build — now also inheriting F0's corrected reality:
  32 floors rows, 193 tests, fifteen walkers, purge built, $0.084/100 turns).

## **Consumer-context scan — the pre-release market pass — 2026-09-01 (research-only; run started 2026-08-31).**

- **Landed:** the five-stream internet scan Jack requested before continuing Phase F — OSS
  agent-memory reception (Mem0/Zep/Letta/Cognee/LangMem + criticism synthesis), AI-NPC
  platform + game-dev/player sentiment, the novelty stress test + name-collision check,
  release-hygiene norms (license chain, no-auth service norms, UPM packaging, erasure
  norms), and a cold consumer sub-agent (a role-played Unity indie engineer, read-only, no
  project context — verdict: adopt-for-a-spike, prototype-only; one BLOCKED walkthrough
  step: the shipped-game deployment story). Synthesis report with evidence links and the
  negative-search record: `docs\research\consumer-context-scan-2026-08-31.md`. Headlines:
  the novelty claim SURVIVES (the "reconstructed, not replayed" slogan was claimed twice in
  mid-2026 and gets cited-and-differentiated, never led with); the license chain is CLEAN
  for the Apache-2.0 flip (one NOTICE line queued); provider coupling and per-agent erasure
  are the category's two table-stakes gaps; README staleness is active trust damage (the
  consumer nearly walked at the ~10x cost discrepancy between README and status). Four
  forks ruled at one batch (the dated decisions.md entry): the OpenAI-compatible provider
  path builds PRE-release (with the documented small-model quality warning); the per-agent
  purge verb builds; the project RENAMES before the flip (naming session queued before F1);
  the Ledger TrustedHost guard lands in F3. Queue re-sequenced: naming session →
  provider-path + per-agent-purge build → F1.
- **Blocked:** Reddit was fetch-blocked for the research agents, so r/LocalLLaMA and
  r/gamedev sentiment is triangulated (HN, GitHub issues, Unity Asset Store, press) rather
  than read directly — flagged in the report's method note. Two of the five research agents
  needed a relaunch after their first launch was interrupted.
- **Abandoned:** nothing. By design, nothing in the product changed this session — every
  finding routed into the report and the ruled queue. No floors row (nothing built, nothing
  verified).
- **Next:** the naming session (Jack picks; collision-check + rename + docs sweep), then
  the provider-path + per-agent-purge build, then F1 with the scan's input pack.

## **The naming session — longmem-npc → twicetold-npc — 2026-09-02 (in-repo + operator swap landed + verified; local folder rename dropped; finalization carried).**

- **Landed:** the whole in-repo rename. Name **twicetold-npc** ruled at the plan batch (from
  "a twice-told tale"); collision check at execution start came back clean (PyPI/npm/OpenUPM
  none; no GitHub repo; only K-pop TWICE + the dictionary term). Four scope forks ruled and
  executed: the env prefix `LONGMEM_`→`TWICETOLD_` (29 keys), full DB/infra rename, the local
  folder (queued), and the GitHub repo (queued). A scoped byte-level sweep made **243
  replacements across 55 files** (the do-not-touch allowlist — immutable migration, append-only
  register bodies, dated research/spec sections, third-party `LongMemEval`/etc., frozen gold
  artifacts — simply excluded; every third-party string protected per-file, no blanket
  replace). Verification battery all green: ruff clean, **full suite 193 passed**, **15/15
  walkers** fresh+serial elder-first on `twicetold_test`, **C# harness 53 checks** (recompiled
  client), real-mode `load_settings` boots on the renamed keys, grep gate returns only the
  allowlist. The dated `decisions.md` entry carries the full record incl. the
  `PRODUCT_DB`↔`.env` lockstep note.
- **Operator swap LANDED + verified (same session):** Jack ran the `.env` key/value rename and
  the GitHub repo rename + `git remote set-url`; Claude drove the non-spend infra — `docker
  compose down`/`up` (old `longmem-pgdata` orphaned intact, fresh `twicetold-pgdata`
  initialized with the new user/DB), migrations fresh-applied to `twicetold` (001–008) + a
  no-op idempotency re-run, the **`PRODUCT_DB`↔`.env` lockstep proven** (guard now refuses the
  real product `twicetold`), `.env` parses in real mode with both keys, the **178-subset green**
  on the recreated container. Committed `ec64ad8`.
- **Abandoned — the local folder rename (ruled 2026-09-02):** Windows held a file lock across
  repeated attempts and Jack ruled not to spend further effort — the path is local-only,
  invisible, and no tracked file depends on it, so `C:\Users\jacks\Projects\longmem-npc` stays
  by choice. The Claude project-state copy is therefore moot (the memory-dir key is unchanged).
  Also deliberately NOT done: a shared walker-scratch constant (the 15 literals were swapped in
  place — the constant-refactor stays the carried task).
- **Finalization LANDED (same session):** the **DLL rebuilt + copied** to
  `unity\Assets\Plugins\` and verified (carries `"twicetold-npc API error"` utf-16-le, old
  string gone; the committed HEAD had still shipped the old binary); the **independent
  floor-verifier pass** returned **pass** on the code + infra re-verification (grep gate within
  the allowlist, suite 193, four walkers across eras, the lockstep + guard, migrate idempotency,
  the DLL string) — the dated floors.md re-verification entry carries it; **no new floors row,
  count 32**. It also confirmed 5 `LONGMEM_` env refs + 1 `longmem_demo` sit in dated/BUILT
  spec sections (consciously kept — history, not current contract; the living docs are clean).
- **Folded onward, not dropped:** the **hero-PNG re-capture → F1** (Jack's ruling 2026-09-02 —
  F1 rebuilds the README image with real spend already scoped, so `demo_loader --fresh` is not
  paid twice; the PNG keeps the old name in-pixels until then, covered by README's continuity
  note) — which is why the demo rebuild was NOT run; the **Unity Editor compile/import re-check
  → F3** (UnityMCP unreachable all session; carried with the Unity MCP pin).
- **Next:** the provider-path + per-agent-purge build, then F1 (which absorbs the hero PNG).
  The rename is complete bar those two folded items.

## **The provider-path + per-agent-purge build — 2026-09-02 (both halves landed plan-to-floor: the OpenAI-compatible backend seam + the embedding knobs, and the per-agent purge verb; Ollama installed for the live beats).**

- **Landed:** both ruled halves, in one session, plan-mode spec → build → live beats →
  independent floor-verify. Four forks settled at the plan batch (three recommended options
  taken, ONE divergence — Jack chose zero-padded embedding widths over the recommended strict
  check; the dated `decisions.md` entry). **Half 1:** `TWICETOLD_MODEL_BACKEND` (anthropic |
  openai) + base URL + optional key for all nine LLM roles, the embedding role's own
  model-name / base-URL / key knobs (the 1536 dimension stays locked, fitted at the seam — pad
  narrower, refuse wider), the loud `load_settings` matrix, ONE `ChatBackend` seam in
  `app\providers.py` (the seven real roles keep prompts/parses/wrappers; Anthropic requests
  byte-for-byte, PINNED by tests), `tests\provider_transport.py` (canned in-process HTTP for the
  real classes — offline, keyless), **Set Q 26** + **the sixteenth walker `verify_provider_path`
  40/40**. **Half 2:** `DELETE /v1/agents/{id}/memories` over ONE shared delete-order helper
  (`_delete_memory_rows`), `FOR NO KEY UPDATE` on the agents row (a plain `FOR UPDATE` would
  have added a deadlock class), summed counts, 200-with-zeros for an empty agent, **Set P +7**,
  **`verify_purge` section H +15 (36/36)**. Suite **226 full / 211 subset**, the full suite green
  twice; the serial sweep on a fresh scratch green (write_path 53, cli_harness 51,
  reconstruction 46, purge 36, provider_path 40). Docs: `.env.example` (the new blocks + the
  small-model quality warning), `SETUP.md` §4b (the Ollama shape, the width contract, the wire
  notes, the warning), `architecture.md` §2/§3/§12, `CLAUDE.md`, `test-suite.md`,
  `write-path.md`, `parameter-compiler.md`, `migration-01.md`. NO migration for either half
  (the explicit scope fact); no C# work, no DLL rebuild. Two mid-session commits (one per
  half) so a session cut left a clean state, then the wrap-up commit.
- **Live beats (all four ruled substrates ran; keys never printed):** fake-mode purge beat
  clean; the Anthropic path with the real key clean after the seam move (parsed JSON on both
  observes, a streamed turn at 545 ms first word / 1177 ms perceived, the purge); hosted OpenAI
  through the base-URL path with `gpt-4.1-mini` clean (parsed JSON, usage through the stream, 29
  chunks, the purge); hosted OpenAI with `gpt-5-mini` reproduced the documented `max_tokens`
  limitation exactly — every LLM call 400, the system degrading by the ruled ladder and
  rejecting nothing (scoring_failed observes at neutral importance, the never-blank fallback
  turn, the purge still 200). Ollama: absent on the machine → installed via winget (announced;
  the per-user installer), the server started with `OLLAMA_CONTEXT_LENGTH=16384`, four models
  pulled (`llama3.2:3b`, `nomic-embed-text`, `qwen3-embedding:4b`, `llama3.1:8b`); both local
  beats clean — `llama3.2:3b` + `nomic-embed-text` (parsed JSON on a 3B model under JSON mode,
  usage through the stream, the 768-wide embedding zero-padded with the warn-once firing
  exactly once: Ollama answers an oversize `dimensions` request with the native width, no
  error) and `llama3.1:8b` + `qwen3-embedding:4b` (parsed JSON, the Matryoshka model emitting
  exactly 1536 through `dimensions=`, no padding). The pre-ruled fallback (drop `dimensions`
  on the base-URL path) was NOT triggered. CPU-only latencies (10–100 s per call cold)
  recorded, never a headline.
- **Verified:** the independent floor-verifier returned **PASS** on all nine criteria — the
  suite 226 twice + 211, all sixteen walkers serial on its own fresh scratch, the invariant
  audit, the route count, boot parity, its own fake and Ollama beats, the product DB pristine
  before and after, the docs propagation — **floors row 33** landed, row 30 carries the dated
  re-verification note. Two stale comment lines it flagged were fixed after the pass.
- **Blocked:** nothing.
- **Abandoned:** nothing. Surfaced, not built (the adjacent-work register in the decisions
  entry): a token-limit-field knob for hosted OpenAI's reasoning-class models (the live evidence
  makes it the top item), timeout/retry knobs, a cross-backend compare arm, a
  `DeadlockDetected` retry-once, `reasoning_effort` for the judge, a temperature knob, a
  balanced-object parser, the startup width probe, and the cosmetic doubled "prose call failed"
  prefix at `dialogue.py:491` (pre-existing).
- **Next:** F1 (the full README — inherits the scan's input pack, the hero PNG, and now the
  providers-section pointer + the token-limit knob question), then F2–F3; the demo endgame
  follows Phase F.

## **F1 — the full README build — 2026-09-03 (README + two integrator pages + both captures, drafted in one session; no code, no floors row).**

- **Landed:** the plan-mode spec (two batches of four; three divergences and a rider — the
  dated entry), then the full draft in one pass per ruling 4: README.md rebuilt (259 lines /
  2,345 words; first person throughout; zero em-dashes; every number dated and defined),
  `docs\first-npc.md`, `docs\shipping.md`, the NOTICE f-coref-weights + spaCy-provenance
  lines, the docs index (an Integrator-guides group, two Start-here rows, the layout table
  moved out of the README), the `architecture.md` §13 pick (LangChain — closed after two
  months "unpicked"), and the two captures on a throwaway scratch (`twicetold_readme_shot`,
  provisioned twice by the E2 loader in real mode, cents): the hero PNG re-taken under the new
  name (the rename's fold-forward closed) and the new `correction-override.gif` (the beat-1
  correction, REPL above the Ledger). Memory notes updated (the deliverable-shape rulings;
  the two divergences).
- **Blocked:** the desktop session was locked all session, so the planned screen recording
  (ffmpeg gdigrab over Windows Terminal + a Chrome app window) captured only the lock
  screen; the GIF was composed headlessly instead (the cast driver + renderer live in the
  session scratchpad; the dated entry has the mechanics). The first take was discarded (the
  correction line read 16.6 s: the lazy NLP load on a fresh process) and re-run warm (524 ms).
- **Abandoned:** a `?poll=1` Ledger deep-link parameter (it would have made a live-desktop
  capture self-refreshing — a code change, out of scope) and the screen-recorded terminal
  (the locked session). Nothing else.
- **Next:** the token-limit knob (its own half-session target, with the README touch that
  rides on it), then F2 packaging, then F3 and the public flip; the demo endgame follows.

- **Review round 1 (same day):** Jack's brief pass over the first draft: lead with the
  retelling machinery (identity-conditioned reconstruction, the gist pin + drift budget,
  retellings that compound), not the corrections and the record; drop the rename note; and
  the desktop was unlocked, so the GIF was re-shot as a TRUE screen recording of the real REPL
  above the Ledger (`docs\media\retelling-drift.gif`: July, September, and a third ask that
  leaves the record untouched; the beat, the band arithmetic and the capture mechanics are in
  the dated entry). README re-shaped (the opening, the numbers order, reconstruction first,
  the correction moved into the record section, the honest "thins rather than transforms"
  wording). The one code touch of the session: the CLI banner's em-dash → a comma, because it
  is on camera. The headless composition is superseded. His deep review is the next gate.
  - **Review round 2 (2026-09-11):** the retelling GIF read as undecipherable to a cold viewer
    ("what do all these numbers mean, what am I meant to take away"), so the hero was rebuilt
    for the Bay Area agentic-AI recruiter audience. Landed: a `?view=showcase` display mode in
    `ledger\index.html` (additive over the same live reads, the default inspector untouched, a
    real code change; `markGist` extracted and shared; JS node-syntax-checked, both views
    screenshot-verified), a richer authored memory (`data\eval\corpora\readme-shot.jsonl`,
    Aldous the wool factor; decay tuned so a seven-month gap shows graded wear: 11/11 facts
    held, detail_recall 0.647, 0 fabricated), the static showcase swapped in as the README hero
    (`docs\media\showcase-hero.png`), the opening realigned from the drovers to the wool factor
    to match it, and `retelling-drift.gif` dropped (Jack ruled static-image-over-GIF). Deferred:
    the approved agent-framing / verification-loop copy reframe, held for Jack's deep-review
    pass (creative work that wants his eye). Abandoned: the motion GIF (superseded). Next: the
    copy reframe + deep review, then the token-limit knob, then F2.

---

## Archived phase headers

*Moved here from `status.md` on 2026-07-28. These were the "Prior phase" blocks stacked
at the top of the living file — each a snapshot of what the current phase was when it was
written. Kept verbatim: they are the most readable summary of each build era, and the
session-log entries below them carry the detail. Newest first, as they were.*

**(moved 2026-08-24 at the E3 wrap-up, the ≤12 KB tripwire — the E2 phase-header paragraph,
verbatim from `status.md`:)**

**E2 landed 2026-08-19** (demo-scoped by ruling: no floors row): the beat script
**`docs\demo-beat-script.md`**, the corpus→demo-DB loader (`python -m app.demo_loader`,
`--fresh`-guarded), the Ledger live turn feed (`GET /v1/ledger/turns` — the server tee, an
explicit ruled carve-out to the route pass-through contract) + identity pane + em-dash label
sweep, C# prewarm parity (`PrewarmContext` / `SceneResult.Prewarm`) + harness beat [17]
(17 beats, 53 checks GREEN), the `NpcMemoryNpc` observe passthroughs, the Unity scene
retargeted to Branwen (attach-mode; the stale plugin DLL refreshed). New in-place write site
sanctioned: `agents.config` via `db.merge_agent_config` (the pinned-toggle precedent). **The
real rehearsal is staged, not run** — see the pending items. Full record in `decisions.md`'s
E2 entry.

**(moved 2026-08-19 at the E2 wrap-up, the ≤12 KB tripwire — the E1 phase-header paragraph
and the Phase C/D roadmap blocks, verbatim from `status.md`:)**

**E1 landed 2026-08-19** (docs + data only, no code, no floor by ruling): the integrator
authoring guide **`docs\identity-authoring.md`** + the demo NPC **Branwen of the Waystone Inn**
(`data\eval\corpora\demo-waystone.jsonl` + 3 held-out probes in
`data\eval\scenarios\demo-waystone.jsonl`), validated on real providers — coverage
drift-validate 9/9 under budget (max 0.121 vs 0.35), beat-condition target certified (drovers,
0.082), held-out run 2/2 checks, fabrication 0.000. Phase E was scoped at plan approval to
**three sessions** (E1 authoring / E2 choreography + rehearsal / E3 record). Full record +
the five authoring lessons in `decisions.md`'s E1 entry.

- **C1–C6 ✅ ALL LANDED** (each plan-to-floor + floor-verified; full records in `floors.md`
  rows 25–30 + `decisions.md`): **C1** deferred writes (`deferred-writes.md`, migration 006,
  default OFF); **C2** reflection (`reflection.md`, migration 007, default OFF per agent,
  endpoint always live); **C3** parameter compiler (`parameter-compiler.md`, migration 008,
  default OFF per agent); **C4** dissonance path + diegetic-correction event (`dissonance.md`,
  no migration, always live — client-invoked); **C5** client contract completion (no spec doc,
  no migration — the agent-state read, the FOURTH unscored member, + fire-and-forget observes,
  drains at scene edges); **C6** purge endpoint (`architecture.md` §12, no migration — per-memory
  `DELETE /v1/memories/{id}`, reflections survive, no guard).
- **C7. Latency pair ✅ DONE** (plan-to-floor 2026-08-18): Stage A concurrency cap (floors row 31)
  + Stage B probe-driven scene-boundary reconstruction pre-warm (floors row 32); NO migration.
  Prompt caching was DEFERRED to Phase D (Haiku-4096 finding); D1 confirmed it stays deferred.

- **D1.** ✅ DONE 2026-08-19 (plan-to-landing, no new code — a measure→rule→tune→re-verify pass on
  the built rig). Latency CONFIRMED (938 ms p50), believability NO REGRESSION, **model slate
  LOCKED** (Haiku latency-bound + Opus 4.8 batch roles), workers stay OFF (per-agent opt-in),
  prompt caching DEFERRED confirmed. NO new floors row (built no layer). Full record in
  `decisions.md`. Exit criterion met: the on-screen latency + believability + cost numbers.

**(moved 2026-08-17 at the C5 wrap-up, the ≤12 KB tripwire's first firing — the C4
landing narrative + the closed operator action, verbatim from the phase header:)**
C4 (the dissonance
path + diegetic-correction event) landed 2026-08-17, plan-to-floor in one session — floors
row 28; the dated C4 build record in `decisions.md` carries the eight plan-batch rulings
(NO migration — the `corrections` table waited since 001); believability confirmed no
regression. **No operator action stands:** Jack applied migrations 007 + 008 to the product
`longmem` DB himself the same morning (the reserved action, done — the product ledger now
reads 001–008 with zero reflection, bundle, or corrections rows).

### Pruned from status.md 2026-08-17 — the ≤12 KB tripwire's first application

*The session-effort audit ruled a standing size line for the auto-loaded living file.
These are the trimmed blocks, verbatim; the compressed pointers that replaced them remain
in status.md.*

**The C3 phase header as it stood:**

**Phase:** **Road to completion — Phases A, B, C1, C2, and C3 are DONE.** (The roadmap
below, consolidated 2026-08-04.) The 2026-08-17 session landed **PHASE C3 — the parameter
compiler**, plan-to-floor in one session. The seven C3 rulings settled at the plan-mode
fork batches BEFORE any file changed: feedstock = ALL live beliefs; typed core = the three
prose-view weight multipliers only (§10's dead "action-set biases" corrected with the
build); scheduling = the STANDALONE third background worker — Jack took the larger option
over the recommended reflect-pipeline stage, with the follow-up fork ruling it lands
WITHOUT the generic jobs table (that unification stays its own later task) — no endpoint,
no route; the all-mechanical staleness guard (the K-window at discovery AND consume +
liveness-by-join + hard clamps); the judge-shaped `LONGMEM_MODEL_COMPILER` (the THIRD such
var); the multiplier clamp **[0.25, 4.0]** frozen into migration 008's CHECK; and
`:compile` = sweep semantics. Landed: migration 008 (`compiled_bundles` append-only,
liveness DERIVED by join + `compiler_runs`), `app\compiler.py` (service + worker + the
pure consume functions), the dialogue-seam consume splice (`scene_type` on the turn
request; composed multiplier products over the untouched weight resolver; zero-bundle
byte parity walker-asserted), the session/CLI surface, suite Set M (21 scenarios, ALL
unmarked — subset 114 → 135, total 128 → 149), the TENTH walker (48/48), the C# mirror +
interop beats [13] (28 → 32), and the docs sweep incl. `parameter-compiler.md` and the
§12 stale-count corrections. The independent floor-verifier returned **PASS** (floors row
27); believability shows no regression (real-mode smoke vs the 2026-08-07 baseline:
checks 6/0 both, gist 0.7667 → 0.85, keyword retention equal). **Applying migrations
007 + 008 to the product `longmem` DB is Jack's action** (builds touch scratches only;
the product ledger sits at 001–006 with zero reflection or bundle rows). **NEXT UP: C4 —
dissonance path + diegetic-correction event.**

**The "Recently closed" litany as it stood:**

**Recently closed** (pointers; full trail in `decisions.md`): **the C3 forks — seven
ruled 2026-08-16/17 at the plan-mode batches** (feedstock; typed core; the standalone
third worker — the one larger-than-recommended pick, with the jobs-table follow-up ruled
standalone; the mechanical staleness guard; the judge-shaped role; the [0.25, 4.0] clamp
frozen pre-migration; `:compile` sweep semantics — the dated build record); **the C2
build-plan forks —
four ruled 2026-08-15 at the build session, all recommended options taken** (post-commit
re-render; the tri-state REPL surface; the keyword-only provider test seam; the real-mode
believability run), with the spec's `[SETTLE-AT-BUILD]` ledger resolved by the approved
plan (the dated build record); **the C2 spec forks — the
four ruled 2026-08-15 at the spec sitting** (consolidation auto-threshold + override;
trim PURELY MECHANICAL — against the recommendation, the one divergence in the C2 line;
per-affected eviction; C# mirror at build; the dated entry); **the C2 dossier forks — all
six + the habituation rider ruled 2026-08-15 at the dossier session** (scheduling
composition; belief home; the identity package incl. the dialogue-seam move; trim teeth +
the fourth sanctioned cause; the RRR guard; the judge-shaped role; the dated entry);
**the interim public README +
the early public flip — ruled 2026-08-13** (repo public ahead of Phase F; F1's demo-time
rewrite unchanged; the dated entry); **em-dashes banned from public-facing prose — ruled
2026-08-13, recorded at the 2026-08-15 wrap-up** (zero U+2014 in Jack's-voice deliverables,
F1 included; en-dashes and hyphens stay; the dated entry); **the C1 spec forks + the
`typology_confidence` seat — all five ruled 2026-08-12 at the C1 spec** (defer-LLM-calls-only;
supersession via chains + the one-shot scalar sanction; worker default OFF; the byte-identity
third cause; confidence salvage); **the dialogue model — HAIKU
re-ruled 2026-08-12 on the first real compares** (perceived first word is decisive: 943 ms p50
vs sonnet-5's 2626/2086 ms against the 1 s bar; sonnet's 46–7 / 41–9 prose preference on the
record and rejected as not justifying the latency; the thinking-off variant measured and
closed the same way); **R7 — resolved 2026-08-12 on the stage-4 ablation's data** (the drift
budget keeps its mechanism and 0.35 threshold and is re-scoped as a TOPIC guard — wholesale
nonsense/topic-swaps; factual faithfulness is policed by gist-precision (fact survival) and
the judged faithfulness category; nothing changes at runtime, the claim is corrected in
`architecture.md` §7, `reconstruction.md`, the `drift_budget_threshold` knob comment, and the
stage-4 banner); the 2026-08-04 scope rulings (below); haiku ships as the dialogue role +
quote embargo lifted (2026-07-29); reconstruction's model class — Haiku stands (2026-07-28;
re-measured on Haiku 2026-07-29); escalation failure path + trigger tuning (2026-07-22/23).

**Carried-item parentheticals as they stood:**

*(Bite recorded 2026-08-12: the DB was found
MISSING — dropped at some point since the 2026-08-07 audit — and psycopg_pool masked
"database does not exist" as a 30 s `PoolTimeout`; recreated + migrated 001–005 in-session.)*
*(SECOND bite recorded 2026-08-17 at the C3 floor-verify: `verify_reflection`'s B6/E9
DB-global counts make that walker non-re-runnable on the persistent scratch once its own
prior green run has landed rows — it needed a fresh pid-scoped scratch to pass 60/60; the
C3 walker ships a persistent-scratch rule in its docstring to stay out of this class.)*
*(The `typology_confidence` parse seat flagged earlier on 2026-08-12 was **ruled SALVAGE
and closed the same day inside C1** — the dated entry in `decisions.md`; the typology gap
itself was ruled CLAMP and built that morning. Neither is carried any longer.)*

**Prior phase:** **the HTTP dialogue-turn route is LIVE — Unity's front door exists** (2026-07-23,
immediate-queue item 1, the audit's #1 blocker closed; plan-as-spec session). `POST
/v1/dialogue/turn` (`app\api.py`; `DialogueService` joins the lifespan) drains the split-brain
seam's async generator to the terminal `DialogueTurnResult` — **stateless** (all scene state rides
the request; the runner bookkeeping is the CLIENT'S job — the future C# `NpcSession` ports
`_apply_turn_result`), non-streaming, `UnknownAgentError` → 404 / `UnknownIdentityVersionError` →
422, pass-through by ruling, `on_reconstruct=None`; a future SSE `/turn/stream` iterates the SAME
generator — no rewrite. Beside it the **honest latency metric**: `perceived_first_word_ms` clocks
the same first-chunk instant from TURN START (retrieval-inclusive — it sees the cold-reconstruction
stall `first_word_ms` is blind to; 0.0 when no chunk arrives); the **<1 s bar is measured against
it**; surfaced in the CLI debug line + a `perceived_first_word` driver series. Ruled at plan
approval: the audit engineer's **thread-pool cap is deferred post-demo** (the build is exactly the
queue item; dated `decisions.md` entry). No migration (ledger 001–005); no new knobs or roles.
**Fourteen floors stand verified** — floor-verifier **pass** twice today (CLI-harness walker 55 →
62; suite 42 → 43 ×2 + keyless subset 36; migrate no-op; `longmem` pristine; live serve HTTP beat —
perceived 22.87 ms vs first_word 0.42 ms on the smoke — + a standalone driver run). **Same-day
follow-on: the escalation trigger-tuning open question is CLOSED** (measured, then ruled): the fire
rate is productive (85% of escalations add real gist content), the defaults stand, and a sixth
**thin_gist** span-floor trigger closes the measured zero-gist hole (16/80 observes had landed with
no gist spans — reconstruction's fixed constraint empty on those rows); Engram-style deferred write
cognition is queued to the ledger; write-path walker 42 → 46, suite 43 → 44, floor-verifier
**pass**. Next: **Unity project + reference scene + The Ledger** (immediate-queue item 2) — **the
demo vehicle is ruled 2026-07-27** (Unity gray-box, not an established-game mod; engine-agnostic
`NpcMemory.Core` + a console harness first with the interop gate moved to Wk-1; the Ledger a
browser page; the established-game clip deferred post-demo to a C# game — dated "Demo-vehicle
ruling" entry in `decisions.md`, specced in `unity-client.md`) — then the pre-ship gates.

**Prior phase:** **external-persona audit landed — the pre-demo path is re-planned** (2026-07-22). A
four-persona read-only agent-team audit (critique + solutions; `external-audit-2026-07-22.md` +
`external-audit-2026-07-22-solutions.md`; rulings in the dated `decisions.md` entry) surfaced the
true blocker, confirmed against source: **`app\api.py` has no HTTP dialogue-turn route**, so Unity/C#
cannot reach a dialogue turn today. Three rulings: split-brain divergence → a **separate interview
clip** (not a main-video beat); the demo records **real-providers-only** (so the `.env` fix is now a
hard prerequisite); the **judged eval harness is pulled pre-demo** (with a judge-free demo panel + a
hand-labeled gold set + the fixed-gist ON/OFF ablation). Build order: `.env` fix → `POST
/v1/dialogue/turn` + honest perceived-TTFT → Unity + **The Ledger** → judged eval. First pre-ship item
since taken off the queue: the **escalation soft-degrade** (migration 005, floor-verifier **pass** —
the 2026-07-13 fail-loud hard-stop retired). **Prior phase: split-brain streaming is BUILT — the latency topology is
live** (2026-07-21,
immediate-queue item 1, specced and built the same day). The dialogue seam is now an async
generator: a streaming **pure-prose** call and a concurrent **behavior** call (directive +
delta, a new model role) fire off one retrieval; **first word = prose TTFT** (`first_word_ms`,
the headline latency term). Two scored views ride one candidate set — the dialogue view (served
ranking) and the behavior view (same served set re-ranked with the now-live `WeightOverrides`,
exponent-form so all-1.0 is byte-parity with the dialogue view) — and the turn result carries
both as the **divergence record** (§13's raw data). A caller-held **recent-actions** block feeds
past actions to later prose prompts as world facts; the four split-brain degradation rows
(behavior fail, prose-fail-pre-chunk, mid-stream keep-partial, both-fail) all landed. No
migration. **Twelve floors stand verified.** Verification (this session, inline): CLI-harness
walker re-opened 36 → 55; read-path walker weight_overrides criterion re-scoped (48); gate
walker rename-only (51); write/reconstruction/authorial/fact walkers byte-untouched and green
(40/42/34/34); full suite 41 → 42 (twice) + keyless subset 35; no-arg migrate "4 applied, 0
pending"; `longmem` pristine via the postgres MCP; live piped REPL streaming beat + a driver run
with the `first_word` + `behavior` series and the behavior cost row. **Flagged (operator-owned
`.env`, not fixed):** a malformed consolidated `LONGMEM_PRICE_DIALOGUE_IN=…` line crashes
`load_settings` on any run that reads `.env` prices — Jack's to fix before real-mode demo runs
*(fixed and verified 2026-07-22 — queue item 0)*.

**Prior phase:** **real mode is proven — pre-ship gates (b) and (c) are closed** (2026-07-21, the
first-ever real-provider session, run with live ANTHROPIC + OPENAI keys). The smoke's
live observe/reconstruction/dialogue receipts are on record, and the real-mode profiling is
diffed against the 2026-07-20 fake baseline: **every infra series flat** (sql, nlp, insert,
gate, correction txn, degraded scan, connection floor — the fake-mode fixes held), with the
true picture LLM-dominated as predicted — observe p50 3.4 s (haiku 1.7 s + escalation 1.4 s
when it fires), dialogue turn p50 4.1 s (first-token 2.2 s), loader read ~180 ms (real query
embed ~175 ms), cold 8-item reconstruction 16.3 s, cache-hit reread 3.7 ms call-free,
**$0.44/100 priced turns** (standard rates). **A build-surfaced defect was ruled, fixed, and
floor-verified same-session** (commit `1388bf6`, `app\providers.py` parse hardening —
sonnet-5's leading thinking block crashed reconstruction and haiku's markdown-fenced JSON
hard-stopped every escalating observe; suite 41/41 ×2, all seven walkers green,
floor-verifier **pass**). **Report-only calibration findings now await rulings:** escalation
fires **79% on realistic prose** (0% on synthetic driver prose — prose-dependent; feeds the
owed failure-path re-rule, now with real data and 0 hard-stops in 80 observes); the gate
novelty CDF separates cleanly under real embeddings (0.3 fire-budget ⇒ threshold ~0.59 on
realistic prose); the 0.35 drift budget is well-placed (max observed accepted drift 0.244);
the lexical channel's ts_rank cost is a linear-in-matches watch-item (the 004 GIN is proven
by EXPLAIN). **Prior phase:** the research-adoption slate landed 2026-07-21 (Target A
encoding-context term + Target B hybrid lexical channel, migration 004);
`docs\research\CHANGES-FROM-RESEARCH.md` traces provenance. **One open decision owed before
the demo ships:** the escalation failure-path re-rule — now widened by the data to cover the
trigger set/threshold too. **Same-day follow-on: the latency slate is ruled and the split-brain
topology is pulled forward + specced** (`split-brain-streaming.md`; viability bar **first word <
~1 s**; all four latency levers land pre-demo — see the queue and the dated register entry).

### Status narrative + queues as of 2026-07-29 (moved 2026-08-04)

*Moved verbatim from `status.md` by the 2026-08-04 road-to-completion re-plan (dated "Scope
consolidation + road-to-completion rulings" entry in `decisions.md`); heading levels demoted one
step to nest here, text otherwise untouched. Superseded as live state by the roadmap; preserved
because the queue texts carry stage histories, receipts pointers, and the audit's still-surfaced
list in a form not restated elsewhere. The in/out status of every item below is governed by the
2026-08-04 register entry, not by this text.*

**2026-07-28 — full-repo audit + remediation.** Seven read-only dimension auditors plus an
adversarial verification pass over their findings; four refuted (two because the "problem" was an
existing dated ruling of Jack's). The audit's own verdict on the codebase was that it is in good
shape — zero prose assertions across the suite and walkers, every UPDATE/DELETE sanctioned, `.env`
never in any git ref, the C# client mirroring all 31 wire models field-for-field. The pass fixed
one real defect and a systematic layer of drift:

- **The SSE consumer stalled the Unity main thread.** `NpcMemoryClient` drove its SSE loop off
  `StreamReader.EndOfStream` — a synchronous read — on a client that deliberately has no
  `ConfigureAwait(false)`, so it blocked between chunks on exactly the path the <1 s
  perceived-first-word beat runs on. Fake-mode streaming is fast enough that the Play-mode gate
  passed 8/8 with it present.
- **Verification gaps closed:** `PUT /pin` and `POST /events/scene-boundary` had no HTTP test at
  all; the SSE `reconstructing` and `error` events had none; `CorrectionNlpFailedError` → 502 was
  ruled and built with neither a test nor a spec row. Suite 49 → 55, keyless subset 48.
- **Gates now match the rules that claim them:** `ruff` was unpinned (the one mechanically-enforced
  tool — and already drifted), `ruff check` had never run as a gate, the `.env` deny covered one
  tool, and floor-verifier's allowlist excluded the Unity MCP.
- **Propagation caught up:** `architecture.md` knew nothing of the five routes shipped 2026-07-27;
  the IDs-and-scores invariant was false as written for the two unscored inspector reads; the
  register still called a closed decision open. This file was split three ways (below).

**2026-07-29 — re-audit of the Opus 5 sessions (Fable 5): all gates reproduce; continuation
queued.** Both 2026-07-28 sessions ran on Opus 5, so everything they touched was re-verified
fresh: suite 55 ×2 + keyless 48, all seven walkers 53/56/67/51/42/34/34, ruff clean at the pin,
both C# builds 0 warnings, interop gate **23/23** live, `/ledger` 200, migrate no-op, `longmem`
pristine, no lone CR — and the committed Unity DLL proven byte-identical to a fresh build of
current source (build-identity bytes only). The aborted work session's revert is verified total
(full transcript sweep); its one standing consequence: `origin/main` sits at `49a635b` (local
ahead 13) — **push ruled: fast-forward once the audit completes, not blocked by the Unity
gate**. The stage-2 Play-mode gate was attempted and blocked in that pass (session-start ordering —
open Unity BEFORE launching the session). **It has since LANDED (2026-07-29, Unity opened first) —
see the dated block below.** The finding fan-out was cut
short twice by usage limits (3/20 finders done, none refereed); the exhaustive re-run was then
**descoped by ruling** in favor of a main-loop verification tail — all green — and the audit is
**complete** (details in queue item 0.5, now DONE). The ruled fast-forward push is executed;
`origin/main` matches local again.

Remaining before recording: demo choreography + the demo corpus, and the judged
eval harness (item 3 — **now staged and underway: stage 1 of 4 BUILT + floor-verified
2026-07-29**, spec `eval-harness.md`; stages 2–4 remain). *(The **stage-2 Unity Play-mode gate** — long the one outstanding
verification — LANDED 2026-07-29: fake 8/8 + an independent floor-verifier re-run + a real-mode 8/8
corroboration; floor row 19.)* *(The 2026-07-29 measurement rulings closed the model slate: haiku ships
as the dialogue role, the reconstruction quote embargo is lifted, and sonnet-5 + the B2
thinking-off variants are re-assessed after the eval harness exists.)* Stages 1 and 3's re-runnable halves — the C#
build, the console interop gate (**now 23/23**, grown by the client-timing assertions), wire
parity, and the `/ledger` route contract — were independently re-verified during the audit pass.

**2026-07-29 — stage-2 Unity Play-mode gate LANDED as a floor (Opus 4.8).** The last verification
outstanding before recording is done. Unity was opened before the session, clearing the
session-ordering block — the MCP bridge reached both the main loop and the floor-verifier subagent
(the read-only bridge check ran first, as required: instance up, `ready_for_tools`, right project,
`read_console` round-trip; no diagnosing session needed). The gate ran **8/8 in fake mode** (the
gate-of-record, scratch DB `longmem_smoke`, `autoRun` toggled via MCP before Play); an independent
**floor-verifier re-ran it 8/8 live** (fresh agent, +12 frames, 0 console errors) and re-proved DLL
build-identity provenance (150 build-identity bytes vs a fresh HEAD build, fresh sha == `5bec081`,
no source/binary drift). A **real-mode pass** (Haiku dialogue, Jack ruled it in) also went **8/8** —
check #8 read **+1061 frames** through the real streamed turn (vs +11/+12 fake), the regression test
the fake path cannot be for the SSE main-thread fix. `autoRun` restored (scene unsaved — committed
`autoRun: 0` preserved), `longmem_smoke` dropped, `longmem` pristine, port free. **Nineteen floors**
now stand (`docs\floors.md` row 19). Dated register entry: **"Stage-2 Play-mode gate verification +
real-mode corroboration."**

**2026-07-29 — eval-harness v1 planned (four rulings) + stage 1 LANDED as floor 20 (Fable 5).**
Item 3 chosen over choreography-first (three deferred consumers wait on the harness; nothing
new waits on choreography). Four plan-time rulings (dated register entry): judge role
**eval-runner-only** (server real mode stays seven-role), v1 judged categories = **core 3 +
prose quality**, the Ledger binding = a **new read route**, and **no migration** (the explicit
per-target scope fact). Stage 1 then built and floor-verified the same session: the judge-free
metric layer (`app\eval_metrics.py` — gist-precision / detail-recall / fabrication / keyword
retention, honest-None denominators), `GET /v1/memories/{id}/reconstruction-metrics` (the third
unscored-by-contract read; zero writes, proven three ways), and The Ledger's numbers panel now
rendering the metrics live (browser beat: **gist precision 1.00 (1/1 facts held)** on a
corrected-then-reconstructed chain). Suite 55 → **63** (Set G; keyless subset 53), interop gate
23 → **24**, walkers 56/42 re-run, both C# builds 0 warnings, ruff clean at the pin.
**Remaining for item 3:** stage 2 (eval runner + scratch provisioning + drift capture +
`drift-validate`), stage 3 (judge layer + rubrics + gold + A/B-Pareto — the sonnet-5/B2
re-assessment instrument), stage 4 (the fixed-gist ON/OFF ablation → R7's deciding data).

**Prior phases:** the stacked phase blocks moved to `docs\session-log.md` ("Archived phase headers") on 2026-07-28 — they are era summaries, not live state.

### Deadline & framing

Single-call demo video: **mid-to-late August 2026**. Do **not** sacrifice vital features or quality
for the deadline — flag deadline pressure when relevant, but never let it drive a decision without
Jack's explicit confirmation. Portfolio target: tier-1 embodied-agent / game-AI employers. Artifact
roles are distinct: the demo video gets the introduction; the instrumentation table, the test suite,
and the structured behavior output survive the interview. Research publication comes after the demo.

### Open questions needing Jack's ruling

*One open. Closed items move to the "Recently closed" note below rather than staying at the top
of this list (tidied 2026-07-28: the escalation item had led this section since it closed on
2026-07-23).*

- **R7 — the self-referential drift budget (logged 2026-07-22 from the external-persona audit).** The
  reconstruction drift budget is cosine candidate-vs-anchor < 0.35; it cannot catch a retelling that
  stays under budget while dropping or contradicting a gist fact, or fabricating a never-observed
  detail. Challenges the 2026-07-17 drift-metric/threshold ruling. **Deferred to the Unity/eval build
  phase (ruled 2026-07-22)** — not acted on now; the fixed-gist-constraint ON/OFF ablation (in the
  pre-demo judged-eval work) produces the deciding data, and any metric/threshold change waits on it.

**Recently closed** (kept as pointers so the trail is short, not gone):

- **Reconstruction's model class — CLOSED 2026-07-28: Haiku-class stands.** Surfaced by the doc
  audit (the register and three specs said Haiku; the shipped config had been sonnet-5 since
  2026-07-21, a stopgap when the env var was found missing, never a class ruling). Jack confirmed
  Haiku. `.env.example` corrected; the annotations in `architecture.md` §7 and `reconstruction.md`
  became resolution notes. **Live consequence — see the queue: the real-mode reconstruction
  measurements taken in that window were against sonnet-5 and need re-measuring.**

- **Escalation failure path + trigger set / thresholds — CLOSED 2026-07-22 / 2026-07-23.** The
  failure path became a soft-degrade (migration 005). The trigger half was measured, then ruled:
  the fire rate is **productive** (85% of fires add real gist content, ~$0.15/100 observes), the
  shipped defaults stand, and a sixth **thin_gist** span-floor trigger closed the measured
  zero-gist hole (16/80 observes had landed with no gist spans). See "Escalation trigger tuning"
  in `decisions.md`.
- **Reconstruction flagged shapes — confirmed 2026-07-17.** See "Reconstruction flagged-shapes
  confirmations" in `decisions.md`.

### Immediate queue

**Pre-demo build path — re-planned 2026-07-22 from the external-persona audit**
(`external-audit-2026-07-22.md` + `external-audit-2026-07-22-solutions.md`; three rulings in the dated
`decisions.md` entry). The audit's #1 finding, confirmed against source: **`app\api.py` has no HTTP
dialogue-turn route** — the cognition layer is REPL-only, and Unity is C# over HTTP. *(CLOSED
2026-07-23 — item 1 below is built and floor-verified; the route is live.)*

0. **Unblock real mode — DONE (verified 2026-07-22).** Jack fixed the malformed `.env` price line and
   `LONGMEM_MODEL_BEHAVIOR` is present (prior thread); verified via `config.load_settings` (no values
   printed): all eleven `LONGMEM_PRICE_*` keys parse, provider mode `real`, `load_settings()` OK. The
   2026-07-21 flagged crash is resolved; real mode is unblocked for the real-providers-only demo.
0.5. **Re-audit continuation — DONE (2026-07-29, same session).** The exhaustive 17-finder
   fan-out was **descoped by ruling** (it burned ~10% of a usage window in minutes; Jack chose a
   main-loop tail instead). Tail results, all green: sanctioned-writes sweep clean; `.env` in
   zero refs across all 72 commits; wire parity **31/31 classes, zero field-name mismatches**;
   docs-split losslessness re-proven — content complete, with the 7/28 "byte-identical"
   attestations shown measurement-time-true (six lines/rows gained dated phase-7 annotations;
   floors.md corrected in place per the append-only-scope ruling). Register corrections applied:
   SETUP 21→23, status 30→31, floors 21/21→23/23. The three completed-but-unrefereed finder
   verdicts stand as recorded in the session log (check-8/SSE-stall coverage gap; (b2) "Zero
   code" PARTIAL; Ledger score panel paste-only + no REPL warm-init verb). **Still surfaced for
   rulings:** F3 check-8 teeth, Ledger live feed + REPL warm-init verb, CRLF renormalization
   (16 files; blobs are LF), `~\.claude.json` duplicate keys, Unity-gate session-ordering.
   **Pushed to `origin/main` (fast-forward) per the ruling.**
1. **HTTP dialogue-turn route + honest latency metric — DONE (built + floor-verified 2026-07-23).**
   `POST /v1/dialogue/turn` is live (stateless, non-streaming, 404/422, pass-through), with
   `perceived_first_word_ms` beside `first_word_ms` — the <1 s bar's field — surfaced in the CLI
   debug line + the driver series. SSE `/turn/stream` still rides later on the SAME generator (no
   rewrite). The thread-pool cap is ruled deferred post-demo. See `floors.md` +
   session log; the build target is now item 2.
2. **Unity project + reference scene + The Ledger** — **demo vehicle ruled 2026-07-27** (dated
   "Demo-vehicle ruling" entry in `decisions.md`: Unity gray-box over an established-game mod; the
   five-agent panel — four audit personas + a modding-landscape scout — weighed it — Skyrim
   declined on zero C# reuse, the
   Mantella comparison class, state-delta observes, and AGPL). Spec: **`unity-client.md`**. The ruled
   sequence: **(i) `NpcMemory.Core` first** — engine-agnostic C# client (plain .NET, HTTP + JSON, the
   `NpcSession` port of `_apply_turn_result` with directive + reputation callbacks, zero `UnityEngine`
   types, one flat client class), driven by a `dotnet run` **console harness playing every demo beat
   headless — the Unity↔backend interop go/no-go moves to Wk-1** (was Wk-2; zero `.cs` today).
   **(ii)** Unity = a thin MonoBehaviour adapter + the gray-box scene as the **intended**
   systems/dev-tool aesthetic (a set, not a game — art-risk stays off the critical path); connect MCP
   for Unity at this step (`mcp-setup.md`; verify the bridge early — scene-manipulation operations
   fail during Play mode). **(iii) The Ledger = a browser page** over the existing HTTP API (not Unity UI), composited
   in OBS: original vs current telling side by side + `read_mode`/scores/IDs + superseded rows
   greyed-but-present + a real gist/detail number on screen — bound to the same `DialogueTurnResult`
   fields the eval harness scores. **Off-camera cache warm-init** (fire `/v1/dialogue/init` at each
   scene basis during camera cuts) removes the 9–16 s cold stall with zero pre-warm code. Beats:
   **lead with correction-override**, then **reconstructive drift (constancy-first — gist flat,
   detail thinning)**; the split-brain divergence is a **separate interview clip** (ruled
   2026-07-22), not a main-video beat. The game-authored action-observe beat + async observes (old
   pre-ship (d)) ride here. **All seven spec forks ruled + stage 0 BUILT and floor-verified
   2026-07-27** (dated "Unity-client fork rulings + stage-0 build" register entry): SSE
   `/turn/stream`, `POST /v1/agents`, and the chain/index inspector reads are LIVE; Newtonsoft
   everywhere; netstandard2.1 core + net8 harness layout; static-HTML Ledger; MCP for Unity
   verified. **ALL FOUR BUILD STAGES LANDED 2026-07-27**: stage 1 (`NpcMemory.Core` + console
   harness — the Wk-1 interop gate 21/21, floor-verified; the C# null-vs-absent proof runs live
   in the gate), stage 2 (Unity adapter + gray-box set — Play-mode gate 8/8), stage 3 (The
   Ledger at `GET /ledger` — live browser beat, suite 49). Remaining for this item:
   **demo choreography + the demo-corpus register** (shipped-game dialogue style + the held-out
   eval arm). The REPL still drives all beats today (`:as-of` jumps + scene boundaries + band
   crossings; `:correct` moves retrieval AND entities; the gate debug line + `(reconstructing…)`).
   *(2026-07-28: stage 1's re-runnable half — build, console interop gate, wire parity — was
   independently re-verified twice during the audit pass. **The stage-2 Unity Play-mode gate LANDED
   2026-07-29** — fake 8/8 + an independent floor-verifier re-run 8/8 + a real-mode 8/8
   corroboration (check #8 +1061 frames under real streaming; DLL provenance re-proven, no drift) —
   closing the last outstanding verification; it is now floor row 19.)*

**Pre-ship latency items** (2026-07-21 latency slate; **audit re-sequenced 2026-07-22** — the
   perceived-TTFT metric moved into item 1; pre-warm build proposed post-demo):
   - **(a) escalation failure path — BUILT 2026-07-22 (soft-degrade; migration 005).** The fail-loud
     hard-stop is retired: a gist-escalation double failure now proceeds with the base NLP-pass gist and
     sets the dedicated `memories.escalation_failed` flag — never a lost write (`EscalationHardStopError`
     + its observe-route 502 removed; suite 42 green). **Still open (separate, non-blocking):** the
     trigger-set/threshold tuning — escalation fires on **79% of realistic prose** (importance p50 0.61
     vs the 0.45 threshold; +1.4 s + ~$0.0021 per fire), a cost/latency item and latency lever **D**'s
     server half.
   - **(b) B1 haiku-dialogue A/B — MEASURED + RULED 2026-07-29: haiku ships as the dialogue
     role.** Same-day arms, product driver, 6×10 turns, seed 7: `perceived_first_word` p50/p95
     **951/1701 ms on the haiku arm** vs 1201/2775 on sonnet-5 — haiku meets the <1 s bar at
     p50, sonnet does not; dialogue cost $0.109 vs $0.415/100 turns (~3× rate × ~1.36×
     tokenizer difference). `.env`/`.env.example` switched; dated register entry. Prose QUALITY
     deliberately unassessed — sonnet-5 and the **B2 thinking-off variants** are deferred to
     the judged-eval harness (item 3), re-assessed once prose can be scored. Receipts: session
     log.
   - **(b2) Re-measure reconstruction on Haiku — DONE 2026-07-29.** The stale sonnet-5 figures
     are retired: cold batched retelling **16.3 s → 8.1 s** on the headline snap (3.3–8.6 s
     across the four cold snaps), ~4× cheaper per batch, cache-hit path still call-free. The
     drift re-check — the one feared real regression — came back **better** on Haiku: distances
     p50 0.107 / max 0.192 vs sonnet's 0.157 / 0.244, zero over the 0.35 budget, zero refusals
     in 32 attempts (sonnet 1/32). `.env` was found already corrected (model + both price rows)
     by the ruling session. The 2026-07-21 instrument no longer runs against current source; a
     fresh probe was staged and fake-mode-verified first — receipts + method in the session log.
     The quote embargo is LIFTED (ruled 2026-07-29): the Haiku-measured numbers are the
     quotable ones.
   - **(c) C1 scene-boundary reconstruction pre-warm BUILD → CONFIRMED POST-demo (ruled 2026-07-22).**
     The demo's cold stall (9–16 s on the stale sonnet-5 numbers; re-measured 2026-07-29 at
     ~3.3–8.6 s on the ruled Haiku class) is removed by off-camera warm-init choreography (fire
     `/v1/dialogue/init` at each scene basis during a camera cut; within-scene byte-stability ⇒ identical
     on-camera bytes), so the full pre-warm build is not demo-blocking. This relaxes the latency slate's
     "all pre-demo" wording for C1. (The scene-frozen cache key still supports the full background build
     when it lands post-demo.)
   - **(d) D async observes** (client contract): the Unity client fires observe events
     without blocking dialogue — the 3.4 s real observe is throughput, not latency.
   *(Done 2026-07-21: the old **(b) real-provider smoke** and **(c) real-mode profiling
   re-run** — receipts + headline numbers in the session log; artifacts scratchpad-only.)*

*(Research-adoption queue — slated 2026-07-21 with the landed slate, each its own
spec/build session; ordering after the Unity/pre-ship items is Jack's to re-slate. Papers per
item are traced in `docs\research\CHANGES-FROM-RESEARCH.md`.)*

3. **Judged eval harness v1 — PULLED PRE-DEMO (ruled 2026-07-22 with the Ledger scope); SPECCED
   + STAGE 1 BUILT AND FLOOR-VERIFIED 2026-07-29** (spec **`eval-harness.md`**, plan-as-spec;
   floor row 20; four plan rulings in the dated "Eval-harness v1 plan rulings + stage-1 build"
   register entry — judge role eval-runner-only, v1 categories = core 3 + prose quality, Ledger
   binding = the new `GET /v1/memories/{id}/reconstruction-metrics` route, no migration). The
   judge-free layer is LIVE: gist-precision / detail-recall / fabrication / keyword-retention
   computed server-side and rendered on The Ledger's numbers panel. **Remaining: stage 2**
   (eval runner over `SessionRunner` + scratch provisioning + `drift_observer` capture +
   `drift-validate`), **stage 3** (judge role plumbing + four rubrics + gold emission +
   A/B-Pareto), **stage 4** (the fixed-gist ON/OFF ablation → R7's data). Judge
   model role/env var + LLM-judged categories (judged signal real-mode-only — sequenced with that).
   **Audit additions:** (i) a judge-free gist-precision/detail-recall metric (from existing gist spans +
   spaCy, no judge call) feeding The Ledger's on-screen numbers; (ii) a small **hand-labeled gold set**
   so the judge has proven rigor (judge-agreement / meta-eval); (iii) the **fixed-gist-constraint ON/OFF
   ablation** — turns the self-referential drift-budget hole (R7) into a shown finding; (iv)
   **real-embedding drift validation** of the demo memory, run EARLY (Wk3, not Wk4).
   Starter categories: selective-forgetting single/multi-hop (MemoryAgentBench 2507.05257),
   abstention/premise (LongMemEval 2410.10813, LME-V2 2605.12493), reconstruction FactScore
   **retargeted** — gist-precision stays ~100%, detail-recall may decay (LoCoMo 2402.17753),
   FAMA stale-leakage (2604.20006), MemTrace trajectory probe + reach-vs-use attribution
   (2606.17328), and the judge-free keyword-retention check (2511.10277) which fits the
   structural suite today. Harness shape: Insert/Query over the existing session-runner loop;
   accuracy-vs-latency Pareto reporting.
4. **Graph/associative memory** — spec session with the de-risked design notes: Postgres-native,
   no graph DB (SPRIG 2602.23372 — app-side seeded PPR is sparse linear algebra);
   concept-mediated edges against `identity_components`, NOT raw entities (GAAMA 2603.27910 —
   entity graphs mega-hub, concept graphs stay ~30× sparser); bi-temporal edge supersession is
   our extension (edges from live heads only; corrections re-derive); the lexical channel
   (Target B) is the hybrid seeding base; graph term = a small additive nudge (GAAMA's 0.1
   ablation). Cheapest first step: HippoRAG's node-specificity IDF on the entity tripwire.
5. **Recall-reinforced decay** — spec session (ruled 2026-07-20: its own session). The "what
   counts as recall" fork + a migration; must not conflate decay with invalidation (invariant)
   nor break within-scene byte-identity. MemoryBank 2305.10250; survey 2512.13564 §5.2.3.
6. **Automatic conflict/staleness detection** — spec session; the write-time counterpart of the
   dissonance path. STALE 2605.06527 (CUPMEM-style adjudication riding `identity_components`);
   Nous 2606.22030 (trust provenance-capped, never content-inferred — maps to
   `typology`/`typology_source`); MemConflict 2605.20926 (taxonomy + near-floor SOTA = a
   differentiator). Non-destructive: detection routes through supersession, never delete.
7. Smaller queued notes: the reflection design dossier (ground reflective writes in cited
   memory_ids + an RRR repetition detector — honest-lying 2605.29463; periodic
   evidence-conditioned identity refresh — AI-YOU 2607.10539; persona-lensed retrieval routing
   — self-reports; idle-time scheduling — sleep-time 2504.13171); richer `seed_identity`
   authoring guidance (interview-depth beats a persona paragraph, self-reports study); the
   Whisper soft-steering hook + safe-default action fallback for the Unity C# API surface item
   (bounded-autonomy 2604.04703).

*(Done 2026-07-23: **HTTP dialogue-turn route + perceived-TTFT v1** — the Unity/C# front door +
the honest retrieval-inclusive latency metric; see `floors.md` and `session-log.md`.
Done 2026-07-21: **Split-brain streaming v1** — concurrent streaming-prose + behavior calls
off one retrieval, two scored views + the divergence record, the new `behavior` model role;
first word = prose TTFT. Also done 2026-07-21: **Encoding-context read term v1 +
gate-calibration utility** and **Hybrid lexical retrieval channel v1 (migration 004)** — the
research-adoption slate's two targets; see `floors.md` and `session-log.md`.
Done 2026-07-20: **Structural pytest suite v1** — 38 scenarios green, the Stop hook live
on the `-m "not nlp"` subset; see `floors.md` and `session-log.md`. Done 2026-07-19: **Mid-dialogue gate v1** — retrieval is conditional; migration 003
applied; see `floors.md` and `session-log.md`. Done 2026-07-18: **Fact-level correction v1** — retrieval follows the fix; migration 002
applied; see `floors.md` and `session-log.md`. Also done 2026-07-18:
**Authorial-correction endpoint v1** — the correction-override beat is live;
see `floors.md` and `session-log.md`. Done 2026-07-17: **Reconstruction v1** — the
thesis mechanism is live; see the verified-floors
table and session log (now `floors.md` and `session-log.md`). Done 2026-07-15: **CLI harness v1 + synthetic load driver** — the vertical
slice completed. Done 2026-07-14: **Read path v1**. Done 2026-07-13: **Write path v1**; earlier
same day: **Migration 01 foundational schema**; connect the Postgres MCP + floor-verifier MCP
access.)*

### Open artifact queue (writing tasks against settled decisions — not decisions)

- Event-ingestion API contract — **v1 subset specced in `write-path.md` and now BUILT** (observe +
  scene-boundary + pin/unpin; phase tag and event_id accepted without a schema home; idempotency
  accepted-not-enforced). Still to spec/build: the diegetic-correction event (references a target
  memory_id; mechanism post-August) and purge (post-August, before the public flip — ruled
  2026-07-14). Scene-boundary's consumers were slated 2026-07-14: reputation snapshot → the
  dialogue turn (**landed 2026-07-15** — the session-runner re-reads `agents.reputation` at each
  boundary), identity recompile → reconstruction (**landed 2026-07-17** — the handler recompiles
  server-side and returns `identity_version`), prompt-head rebuild → post-August.
- Retrieval scoring function: relevance × recency(decay class) × importance_norm; pin exemption;
  normalization; slots for the future context term and per-call split-brain overrides *(both
  slots since ruled live: context landed 2026-07-20; behavior-view overrides **built**
  2026-07-21 — split-brain streaming)*. —
  **Consolidated into `read-path.md` 2026-07-14 and now BUILT** (shapes ruled at build; dated
  `decisions.md` entry).
- Reconstruction call spec: operator-structured prompt with gist as fixed constraint; determinism;
  batching shape. — **Consolidated into `reconstruction.md` 2026-07-17 and now BUILT** (built &
  floor-verified the same day; shapes ruled at build; dated `decisions.md` entry).
- Reflection spec end-to-end (mechanism explicitly post-August — ruled 2026-07-14).
- Gate threshold values + efficacy definitions wired to instrumentation. — **Consolidated into
  `mid-dialogue-gate.md` 2026-07-19 and now BUILT** (same day; thresholds ruled with the build
  plan; the efficacy comparators live in `GateInstrumentation` + the load-driver gate block;
  instrumentation-only fire logs as ruled).
- Unity client C# API surface: send event, open dialogue, directive callback, reputation read,
  reconstructing-signal hook, scene-boundary emission. *(Grown by the 2026-07-21 split-brain
  spec: the SSE streaming route + the game-authored action-observe contract land here.)*
  *(Shape ruled 2026-07-27: engine-agnostic `NpcMemory.Core` — zero `UnityEngine` types, one flat
  client class — + a thin Unity adapter; consolidated into `unity-client.md`.)*
  *(Stage-1 observation 2026-07-27: no HTTP agent-state read exists — the C# session refreshes its
  boundary reputation snapshot from the last turn's `reputation_after`, exact for a single-client
  session; a multi-client integration wants a small read route. Future surface item.)*
- Demo choreography: injected-timestamp time travel; decay + correction-override + gate-recollect
  beats; the 60-day drift plot — a planned beat since the 2026-07-14 re-slating (reconstruction is
  pre-demo). *(Grown 2026-07-21: the game-authored action-observe beat —
  `split-brain-streaming.md`.)*
- README destructive-compression counter-example pick.

### Sequenced-later ledger (pull-forward eligible)

*Sequencing orders work; it never rules an option out of a design discussion. Any item here may
be pulled into the immediate queue by a dated ruling when a current target shows it is
architecturally load-bearing — the 2026-07-14 reconstruction re-slating is the template.
(Reframed from "Post-August ledger" by the 2026-07-17 "Scope-limiter reframing" ruling in
`decisions.md`.)*

Reflection pipeline mechanism (sequenced post-August — hedge resolved 2026-07-14; the pre-demo
identity document is seed-prose-only); dissonance path + the diegetic suite pair; the purge
endpoint (before the public flip — ruled 2026-07-14); prompt caching / prompt-head rebuild
(revisit when a target needs it or demo latency demands — reframed 2026-07-17 from the ruled
"only if demo latency demands" wording); habituation *(the encoding-context read term itself
landed 2026-07-21 — Target A)*; **Engram-style deferred write cognition** (own spec target,
ruled onto the ledger 2026-07-23 — raw observe stored immediately, gist/enrichment at the
service's own timing; the existing degradation flags are the natural deferred-work queue; forks:
add-only gist annotation vs the frozen write-time facts, the un-enriched-window retrieval
contract, a new `write_cause` = a migration; Engram 2606.09900 + the sleep-time-compute family —
the async-observe client contract covers the latency motivation and the thin_gist trigger covers
correctness inline, so this is a cost/throughput optimization); **the established-game
integration clip** (ruled 2026-07-27 — post-demo, the split-brain interview-clip template: a
C#-moddable game reusing `NpcMemory.Core` — Stardew/SMAPI days-scale or RimWorld's rich event
stream — NOT Skyrim: zero C# reuse, the Mantella comparison class, AGPL on a published fork);
reflection → parameter compiler;
Unity Package Manager packaging; docs final + public flip
(Apache-2.0). *(Reconstruction — mechanism, drift budget, Set C scenarios — moved off this ledger
into the immediate queue by the 2026-07-14 re-slating ruling.)* *(Split-brain topology with per-call
weights — moved off this ledger into the immediate queue by the 2026-07-21 latency-slate
ruling, the second use of the pull-forward template; specced AND built same day,
`split-brain-streaming.md`.)*

**Research track:** asymmetry ablation (on/off, judge-measured explanation-cause divergence); judged
drift / Bartlett-style evals; unified-thesis write-up (identity-conditioned reconstructive memory +
information-asymmetric cognition).

**Later / optional:** disclosure gate; full modulator suite for the parameter compiler;
faithful-vs-reconstructive dual read modes; the dormant-agent memory-injection overseer (next
project; wake trigger = context match); local-model packaging (note: a second embedding model
collides with the locked 1536 dimension).

---

## Archived from status.md at the E1 wrap-up (2026-08-19, size tripwire)

*Moved verbatim; the live pointers stay in `status.md`.*

### Cut from scope (ruled 2026-08-04)

- The research track entirely: write-up, submission, asymmetry ablation, Bartlett-style judged
  evals. (The stage-4 gist ablation SURVIVES — it answers R7, an engineering question.)
- The behavior/action side of split-brain: the action directive, the reputation system whole,
  the divergence record + its interview clip. NPC actions are the game developer's domain; the
  NPC's own actions arrive as ordinary observes.
- Graph/associative memory (too large a task for not enough benefit), recall-reinforced decay,
  automatic conflict/staleness detection, habituation, the Whisper soft-steering hook +
  safe-default action fallback.
- The optional/stretch list: disclosure gate, faithful-vs-reconstructive dual read modes,
  local-model packaging, the dormant-agent overseer (next project), the full modulator suite.
- The mid-to-late-August demo date (see the framing section in `status.md`).

### Roadmap Phase A — Re-shape the dialogue seam — DONE

- **A1. Split-brain removal + weights-on-speech.** ✅ LANDED 2026-08-04, floor-verified
  (floors row 21; Play-mode re-run closed 2026-08-05 — floors rows 19/21).

### Roadmap Phase B — Finish the measurement rig — DONE

- **B1. Eval-harness stage 2.** ✅ LANDED 2026-08-05, floor-verified (floors row 22).
- **B2. Eval-harness stage 3.** ✅ LANDED 2026-08-07, floor-verified (floors row 23; first
  real use 2026-08-12).
- **B3. Eval-harness stage 4.** ✅ LANDED 2026-08-12, floor-verified (floors row 24; its
  first real run decided R7).

## Archived from status.md at the F0 wrap-up (2026-08-26, size tripwire)

**E3 first attempt 2026-08-24:** all four segments recorded through the new attach-mode rig
and every beat PASSED live QA (the per-segment receipts in the dated E3 entry; one nuance
carried to the captions — constancy binds the SERVED retelling, the streamed wrapper varies
by design). The cut was NOT made: footage QA found the Branwen nameplate MIRRORED in every
Unity frame plus lesser blemishes (the register: the beat script's E3 record) — **noted,
deliberately NOT fixed by ruling**: the presentation redesign owns them; the re-record runs
on a fresh provision (`--fresh` sanctioned). **The
2026-08-22 pinned state is SPENT** — a provision serves beat 1 exactly once (the correction
moves the fact chain and evicts the June caches). The E3 rig is provision-independent and
ready (driver `startAsOf`, committed scene-1 start state, OBS + ffmpeg, close card + run
sheet + raw takes under `C:\Users\jacks\Videos\longmem-demo\`); full record: the dated E3
entry + `demo-beat-script.md`'s E3 record.

**E2 landed 2026-08-19** (demo-scoped, no floors row): beat script + loader + Ledger live
feed + C# prewarm parity + the Branwen retarget; rehearsal executed 2026-08-22. The verbatim
block moved to `session-log.md`'s archive at the E3 wrap-up (size tripwire); full record in
`decisions.md`'s E2 entries.
**E1 landed 2026-08-19** (docs + data, no floor by ruling): `identity-authoring.md` +
Branwen, the drovers memory certified as the drift target — the roadmap bullet below; the
five authoring lessons in `decisions.md`'s E1 entry.
D1 (optimization, 2026-08-19, no new code): perceived-first-word **p50 938 ms**, believability
no regression (gist_precision 0.823), **model slate LOCKED** (Haiku latency-bound; Opus 4.8
batch roles in `.env.example`), workers OFF per-agent, prompt caching DEFERRED — the D1 entry.

## Archived from status.md at the consumer-scan wrap-up (2026-09-01, size tripwire)

**F0 landed 2026-08-26** (no new floors row — the floors.md Re-verification entry + the
dated F0 decisions.md entry carry the evidence): registers reconciled to MEASURED reality
(suite **193 full / 178 subset**; fifteen walkers named everywhere; floors.md's stranded
rows 28–32 back inside the table; 16 doc-auditor findings fixed), the init 404/422 gap
test, the turn-path overlap + the `LONGMEM_DB_POOL_MAX_SIZE` knob, and the gated wording
pair — the dialogue-prompt UUID strip (**dialogue input −51%; all-in $0.084/100 turns**)
+ the write-prompt voice clause (gate: NO regression — gist 0.8309, recall 0.8448,
fabrication 0.0159). Latency: perceived p50 826–917 ms across the day's provider windows;
the D1 attribution CLOSED (pre-prose ≈ 90% embed; the overlap cut the rest to ~20 ms);
the ceiling recorded (embed swap ≈ 770–870 ms; caching inert on Haiku; slate stands).
Surfaced-not-built forks: the F0 entry.

**E3 first attempt 2026-08-24:** recorded + QA'd, master NOT cut (mirrored-nameplate flaw
— the presentation redesign owns it); **the 2026-08-22 pinned state is SPENT** (a
provision serves beat 1 exactly once; `--fresh` sanctioned); the rig is
provision-independent and ready. Full record: the dated E3 entry +
`demo-beat-script.md`'s E3 record; the verbatim header block moved to `session-log.md`'s
archive at the F0 wrap-up (size tripwire).

**E2 roadmap bullet as it stood before the 2026-09-01 trim:** ✅ DONE (built 2026-08-19,
demo-scoped by ruling — no floors row; rehearsal executed 2026-08-22 after the blockers
cleared). Landed: `demo-beat-script.md` (correction-override lead → constancy-first drift
on the certified drovers memory → the action-observe beat + the executed rehearsal
record), the corpus→demo-DB loader, the Ledger live feed + identity pane + label sweep,
the C# `PrewarmContext` mirror + harness beat [17], the `NpcMemoryNpc` passthroughs, the
Branwen scene retarget + DLL refresh. The recording state is pinned.

**The walker three-bites register as it stood before the 2026-09-01 trim:** THREE
documented bites (the first two verbatim in this archive, moved 2026-08-17): 2026-08-12
(the DB found MISSING; psycopg_pool masked it as a 30 s `PoolTimeout`), 2026-08-17
(`verify_reflection` is non-re-runnable on the persistent scratch — a fresh pid-scoped
scratch is that walker's documented precondition), and 2026-08-17 again at the C4 landing
(the elder correction walkers' DB-global corrections-emptiness asserts vs the re-opened
`verify_reconstruction` — sweeps must run fresh + serial, elder walkers first; the C4
build record has the detail).

## Archived from status.md at the provider-path wrap-up (2026-09-02, size tripwire)

*The two header paragraphs the 2026-09-02 provider-path wrap-up replaced with pointers — the
rename paragraph and the consumer-scan paragraph — verbatim from `status.md` as they stood
that morning (the naming session's own wrap-up wrote the first; the scan's the second).*

**The rename → `twicetold-npc` DONE + re-verified 2026-09-02:** in-repo sweep + operator swap
(`.env` + GitHub by Jack; Docker recreated to `twicetold-pg`/`twicetold-pgdata`) + DLL
rebuild/copy + the **independent floor-verifier pass** all landed — suite **193**, **15
walkers**, **C# 53**, the `PRODUCT_DB`↔`.env` lockstep + guard, `git grep -i longmem` = the
ruled allowlist only; **no new floors row, count 32**. The **local folder rename is DROPPED**
(Windows lock + ruling — the folder and this memory-dir key stay `longmem-npc`). **Folded
onward:** hero PNG → F1, Unity Editor re-check → F3. Full record: the dated `decisions.md`,
`floors.md`, and `session-log.md` entries.

**Consumer-context scan landed 2026-09-01** (research-only; no floors row): novelty claim
SURVIVES, license chain CLEAN for the flip, README staleness is active trust damage; the
cold consumer's one BLOCKED step (the shipped-game deployment story) is F1's top addition.
Four rulings (the dated `decisions.md` entry): provider path pre-release, per-agent purge,
the rename, the Ledger F3 guard. Report + per-phase input packs:
`docs\research\consumer-context-scan-2026-08-31.md`.

---

## Archived from status.md at the F1 wrap-up (2026-09-03, size tripwire)

*The provider-path header block, moved here verbatim; the dated `decisions.md` entry and
floors row 33 carry the full record.*

**The provider-path + per-agent-purge build DONE 2026-09-02:** `TWICETOLD_MODEL_BACKEND`
(anthropic | openai) + base URL + optional key for all nine LLM roles over ONE `ChatBackend`
seam (Anthropic requests byte-for-byte); the embedding role's own model-name / base-URL / key
knobs (the 1536 dimension stays locked, fitted at the seam — narrower zero-padded by Jack's
ruling, wider refused); the small-model quality warning beside the knob (`.env.example`,
`SETUP.md` §4b); `DELETE /v1/agents/{id}/memories` as the thin C6 extension (reflections
survive). Suite **226 / 211**, **16 walkers** (`verify_provider_path` 40, `verify_purge` 36),
NO migration, no C# change. Four live beats ran (fake, Anthropic, hosted OpenAI, Ollama); the
dated entry has the record.
