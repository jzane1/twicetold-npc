# Authorial correction — v1 build target

Sixth build target, on top of migration 01, write path v1, read path v1, CLI harness v1, and
reconstruction v1. This specs **the authorial-correction endpoint** — the operator's
fix-wrong-data verb (**replace model, ruled 2026-07-12**) and the correction-override demo beat.
It inherits reconstruction's two stated obligations (evict all cache rows for the memory_id; the
corrected head re-anchors the drift budget) and rules the reconstructor-input consequence the
inheritance surfaced. Design truth is [architecture.md](architecture.md) §8 (+ §7 cache/anchor
obligations); the rulings behind it are in [decisions.md](decisions.md); the schema it writes is
recorded in [migration-01.md](migration-01.md) — the `write_cause` chain enum
(`authorial_correction` a member since day one), `reconstruction_cache`, and the one-live-head
index are already live, so **no migration is needed as a fact of this target** (if the build
surfaces a schema need, stop and report — migration 002 is available under the 2026-07-17
scope-limiter reframing). This doc points, it does not re-derive.

Four scope forks were ruled at spec time (dated "Authorial-correction spec scope rulings" entry
in `decisions.md`) — **the first spec authored under the 2026-07-17 scope-limiter reframing**:

1. **Scope = chain content now; fact-level correction slated as its own target** (immediate-queue
   item 2, ruled by explicit question). This target corrects the telling chain. The honest gap it
   leaves — retrieval still ranks a corrected memory by the original observation's embedding, and
   gist spans still index the original text — is closed by the slated fact-correction target
   (versioned memories-row facts, corrected embedding; migration-002-class design with its own
   spec pass), not silently accepted. *(Specced 2026-07-18 — `fact-level-correction.md`.)*
2. **The reconstructor's fixed constraint follows the drift anchor.** On a chain whose derivable
   anchor is an `authorial_correction` head, the corrected head — not the stale gist spans —
   is the fixed constraint. One notion of ground truth per chain: the constraint and the drift
   anchor derive from the same `write_cause` rule. *(This ruling reversed the pre-reframing
   recommendation, which had leaned on "re-opens the reconstruction floor" as a deterrent.)*
3. **Surface = memory-scoped operator verb** (mirroring pin), not an `/v1/events/*` event —
   `/v1/events/*` stays diegetic (the future diegetic-correction event keeps a clean namespace).
4. **Immediate mid-scene effect.** Wrong data stops serving the moment the operator fixes it; the
   within-scene stability invariant's wording gains authorial correction as the second sanctioned
   text-change cause (amended in CLAUDE.md, architecture §7, and `test-suite.md` Set C).

> **Status: BUILT & floor-verified 2026-07-18.** Every `[SETTLE-AT-BUILD]` item below was ruled at
> build time (dated "Authorial-correction build rulings" entry in `decisions.md`): one criterion
> was **re-ruled via an explicit question at a mid-build stop-and-report** — the done-when
> "time travel coherent" bullet became **stored bi-temporal coherence** (its original wording
> over-claimed; see the annotation below) — and the rest were approved with the plan, including
> the **compare-and-swap refinement** of the 409 suggestion (optional `expected_detail_id`).
> **No migration was needed, as the spec stated** (`db\migrate.py` no-arg still a clean no-op).
> The endpoint landed in `app\db.py` (`apply_authorial_correction`) + `app\ingest.py`
> (`IngestService.correct`) + `app\api.py` + `app\schemas.py`; the reconstruction delta in
> `app\reconstruction.py` (`build_reconstruction_item`, anchor-cause-aware — the deliberately
> re-opened floor, re-verified with its walker grown 41 → 42 by addition only); the REPL surface
> in `app\session.py` + `app\cli.py` (`:correct`); walker `tests\verify_authorial_correction.py`
> (31 assertions). floor-verifier **pass** — all five walkers re-run independently on fresh
> scratch, `longmem` confirmed pristine via the postgres MCP, independent code spot-checks
> (transaction + CAS rollback shape, byte-verbatim no-model path, retrieval/scoring untouched),
> plus a live piped REPL correction-override beat.

## Principles this build honors

- **Non-destructive supersession.** The correction **inserts** a corrected head
  (`write_cause = authorial_correction`) and supersedes the prior head by setting `invalid_at` —
  ordinary supersession under the permanent `memory_id`. Never UPDATE content, never DELETE chain
  rows. Prior tellings stay queryable under `as_of`.
- **No model calls.** The corrected head is the operator's text, stored **byte-verbatim**. A
  render pass would alter the fix, and any composition template would be a hidden hardcoded
  authorial artifact (the query-composition rejection's reasoning). This endpoint is pure
  storage discipline. *(Superseded in part by the fact-level spec, 2026-07-18: at that build the
  verb gains exactly one embed call — the corrected basis must be embedded so retrieval follows
  the fix. The operator text itself stays byte-verbatim in both chains; no render pass, ever.
  `fact-level-correction.md`.)*
- **Verb discrimination by `write_cause` alone** (ruled 2026-07-12): no marker on prior rows, and
  **no `corrections`-table row** — that table is diegetic-only by CHECK
  (`rationalization | update_with_resentment`).
- **The eviction invariant** (standing, `reconstruction.md`): this writer evicts **all**
  `reconstruction_cache` rows for the memory_id, in the same transaction (application code, not
  triggers).
- **Re-anchoring is automatic.** The drift anchor is derivable, no pointer — the corrected head
  is selected by the existing anchor SQL the moment it commits (proven at the db layer by
  `tests\verify_reconstruction.py` [8]).
- **Correction outranks pin; the corrected head inherits it** (§8 final ruling). Pin lives on the
  memories row, so inheritance is structural; a pinned corrected memory serves the corrected head
  verbatim on the next read.
- **Fail-loud operator surface.** Gameplay reads degrade quietly; operator tooling does not — the
  operator must know a fix failed to land. No soft paths in this endpoint.
- **Honest self-description, IDs in payloads, instrument at the seam** — unchanged contracts; the
  result carries IDs and instrumentation like every other seam.

## Scope boundary — do NOT build

**Fact-level correction** — slated as its own spec + build, immediate-queue item 1 as of this
build's completion (a sequencing note, not a rejection: it needs a fact-versioning design the
memories row doesn't have, and that design deserves its own fork surface). *(That fork surface
ran 2026-07-18 — specced in `fact-level-correction.md`; at its build the combined verb grows
this endpoint.)* **The diegetic
correction event + dissonance path** (sequenced post-August; the `corrections` table stays
write-less until then). **Purge.** **The mid-dialogue gate** (immediate-queue item 1 since the
2026-07-18 fact-level build; specced & built 2026-07-19, `mid-dialogue-gate.md`). If adjacent work
looks necessary, stop and report —
with the correct option and its real cost stated, per the reframed contract.

## Surface (where this attaches)

A thin route delegating to an `IngestService` method (the `set_pin` pattern —
`app\api.py` route, `app\ingest.py` seam, SQL in `app\db.py`):

- **Route:** memory-scoped operator verb. `[SETTLE-AT-BUILD]` exact path/verb — suggested
  `POST /v1/memories/{memory_id}/correction`.
- **Request:** the corrected content (required, non-empty — `[SETTLE-AT-BUILD]` validation
  shape) + the correction's world time. `[SETTLE-AT-BUILD]` `valid_at` policy — suggested: a
  required tz-aware field, like the observe event (bi-temporal rule: `valid_at` is client-sent
  world time; the operator states when the corrected fact takes effect).
- **Response:** `[SETTLE-AT-BUILD]` exact wire shape — suggested `CorrectionResult` with
  `memory_id`, `detail_id` (the corrected head), `superseded_detail_id`, `evicted_cache_rows`,
  and instrumentation (`correction_ms`). IDs-in-payloads, as everywhere.
- **CLI:** a `:correct` meta-command on the REPL so the correction-override demo beat is drivable
  pre-Unity; debug view shows the result fields. `[SETTLE-AT-BUILD]` exact syntax — suggested
  `:correct <memory_id> <corrected text…>`.
- **Errors, loud:** unknown `memory_id` → 404; invalid content → 422; a lost concurrency race →
  `[SETTLE-AT-BUILD]` — suggested 409 (see below). Transaction failure → 5xx, nothing partial
  (single transaction).

## Mechanism — one transaction

The reconstruction write-back is the precedent (`write_back_reconstruction`, `app\db.py`): one
transaction, supersede-guarded.

1. **Supersede the live head:** `invalid_at = t_c` on the current head, guarded by
   `invalid_at IS NULL` + rowcount (the optimistic-concurrency pattern; the one-live-head index
   is the structural backstop). `[SETTLE-AT-BUILD]` loser behavior — suggested: a concurrent
   writer having superseded first is a 409 to the operator (they should re-read and re-issue
   against the new head — silent retry would correct a telling they never saw).
2. **Insert the corrected head:** `write_cause = 'authorial_correction'`,
   `valid_at = t_c` — prior `invalid_at` = new `valid_at`, the coherent-chain-timeline precedent,
   so `as_of` time travel before/after t_c serves the right telling.
3. **Evict all cache rows** for the memory_id — the inherited invariant, same transaction.

No `corrections` row. No `memories`-row writes of any kind (fact correction is item 1 of the
queue as of this build's completion). *(Fact-level correction specced 2026-07-18: at its build
this transaction grows the fact-chain supersede + insert — still no `memories`-row writes; the
fact versions live on their own chain. `fact-level-correction.md`.)*

## The reconstruction delta: constraint follows the anchor

Ruled at spec time (fork 2). Prompt assembly (`assemble_reconstruction_prompt`,
`app\reconstruction.py`) becomes **anchor-cause-aware**:

- **Original-anchored chains: unchanged.** Gist spans stay the fixed constraint; thinned detail
  and the current live head ride as today.
- **Authorial-corrected chains** (anchor `write_cause = authorial_correction`): the **corrected
  anchor text is the fixed constraint**. `[SETTLE-AT-BUILD]` exact corrected-chain input shape —
  suggested: constraint block = the anchor content; the current live head still included ("how
  you currently tell it" — retellings compound above the correction too); the observation-derived
  gist/detail blocks **omitted** (they may contain exactly the data the operator corrected away —
  re-injecting it so the drift budget can refuse it burns a call to fail; the decay band still
  keys the cache and the trajectory, it just no longer selects a thinning slice for these
  chains).
- **`update_with_resentment`-anchored chains:** decided with the dissonance path (sequenced
  post-August as written; **ruled and built at C4, 2026-08-17** — `dissonance.md` ruling 4
  gives accepted heads the authorial fixed-anchor treatment; annotated at the F0 audit,
  2026-08-26). Until C4, no mechanism wrote that cause.
- The drift budget itself is unchanged — candidates embed against the corrected anchor, as
  already built.

**This re-opens the reconstruction floor** — a prompt-assembly change plus walker updates, then
`tests\verify_reconstruction.py` re-runs and the floor-verifier re-passes. That is the step, in
full; it is not a design cost.

## Immediate effect & the amended invariant

Eviction + supersession mean the very next read — same scene included — misses the cache and
serves the corrected chain: pre-theta or pinned → the corrected head verbatim; past theta → a
fresh reconstruction constrained by the corrected anchor. The within-scene stability invariant
now reads: *absent a diegetic event **or an authorial correction** on a memory, repeated reads
within one scene return byte-identical text* (amended 2026-07-17 in CLAUDE.md and architecture
§7; `test-suite.md` Set C matches). The invariant protects the character from non-diegetic
flicker; an operator override of wrong data is not flicker.

## Instrumentation (rides the seam)

`correction_ms` + `evicted_cache_rows` in the result; the REPL `:correct` output and debug view
surface them. No token accounting — this endpoint makes no model calls. `[SETTLE-AT-BUILD]`
exact field names with the wire shape. *(The no-token line is superseded at the fact-level
build, specced 2026-07-18: one embed call rides the verb and `CorrectionResult` widens —
`fact-level-correction.md`.)*

## `[SETTLE-AT-BUILD]` — physical shapes, ruled at build (stop and report, never silently choose)

**All ruled 2026-07-18 with the build plan** (dated "Authorial-correction build rulings" entry in
`decisions.md`; the time-travel done-when was re-ruled via an explicit question):

- **Route** — **ruled:** `POST /v1/memories/{memory_id}/correction` (POST — each call mints a
  chain row; pin's PUT is a toggle).
- **Wire models** — **ruled:** `CorrectionRequest { content (min_length 1), client_timestamp
  (required, tz-aware — the ObserveEvent naming), expected_detail_id (optional, see CAS) }`
  *(gate spec 2026-07-19, fork 3: gains an optional `entities` field at the gate build — NER +
  operator merge populate the corrected fact head's entities; `mid-dialogue-gate.md`)*;
  `CorrectionResult { memory_id, detail_id, superseded_detail_id, evicted_cache_rows, total_ms }`
  (the PinResult naming; no token fields — no model calls). *(Superseded at the fact-level
  build, specced 2026-07-18: `CorrectionResult` widens and one embed call rides the verb —
  `fact-level-correction.md`.)*
- **`valid_at` policy** — **ruled as suggested:** required tz-aware `client_timestamp` → t_c.
- **Validation** — **ruled:** pydantic `min_length=1` + a stripped-non-empty check in the seam;
  whitespace-only content is invalid (422).
- **Concurrency** — **ruled with a refinement of the spec's 409 suggestion:** the supersede
  targets the live head by predicate (race-safe under row locking); an optional
  `expected_detail_id` makes it a compare-and-swap — stale → **409**, transaction rolled back,
  nothing changed (the ruled no-silent-correction behavior, opt-in); omitted (the REPL default)
  → correct the current live head.
- **Corrected-chain prompt input shape** — **ruled as suggested:** the pure
  `build_reconstruction_item` branches on `anchor_cause` — corrected anchor text in the
  constraint (gist) slot, empty detail, `current_telling` kept; `_SYSTEM_TASK` and the JSON
  shape unchanged; original-anchored chains byte-identical to the prior stage.
- **CLI** — **ruled as suggested:** `:correct <memory_id> <corrected text…>`; t_c = the
  session's effective time (`as_of` under time travel); prints the head swap, eviction count,
  and timing.
- **Error mapping** — **ruled:** 404 unknown memory / 409 stale CAS / 422 invalid content /
  5xx raw. Fail-loud, no soft paths.
- **Walker** — **ruled:** `tests\verify_authorial_correction.py` (31 assertions, scratch
  pattern); `tests\verify_reconstruction.py` grew one corrected-item assertion (41 → 42,
  addition only).

## Done when

- **Replace-model chain shape.** A correction on a drifted chain: prior head superseded
  (`invalid_at = t_c`), exactly one live head, `write_cause = authorial_correction`, content
  **byte-identical to the operator's input**; `observation_text` and gist rows untouched.
- **Eviction.** All `reconstruction_cache` rows for the memory_id are gone, atomically with the
  chain write.
- **No `corrections` row** was written.
- **Re-anchoring.** `fetch_reconstruction_sources` resolves the anchor to the corrected head.
- **Constraint follows the anchor, assertably.** The pure assembly function shows the corrected
  anchor as the fixed constraint on a corrected chain (and gist unchanged as the constraint on
  an original-anchored chain) — no model call.
- **Post-correction serving.** Pre-theta / pinned → corrected head verbatim, `read_mode` honest;
  past theta → reconstructs under the corrected constraint, drift-checked against the corrected
  anchor, write-back lands (fake providers).
- **Immediate mid-scene effect.** Within one scene: read → correct → read serves the corrected
  content (the amended invariant's sanctioned change).
- **Pin inheritance.** Correcting a pinned memory proceeds; the corrected head serves verbatim;
  no reconstruction row ever grows on it.
- **Time travel coherent.** `as_of` before t_c serves the prior telling; at/after t_c the
  corrected chain. *(Re-ruled at build via explicit question, 2026-07-18: **stored bi-temporal
  coherence** — the walker asserts a windowed SQL query re-derives the pre-correction telling,
  with no gap or overlap at t_c. The original wording over-claimed: serving always follows the
  live head, and `as_of` is an age-computation override per the 2026-07-14 read-path ruling.
  The alternative — as_of-windowed chain serving — was presented fairly priced and not
  adopted.)*
- **Concurrency guarded.** A stale supersede (rowcount ≠ 1) changes nothing and reports per the
  settled loser shape.
- **Errors loud.** Unknown memory 404; invalid content 422; route is a pass-through of the seam
  result (ASGITransport JSON-equality, the house pattern).
- **CLI drivable.** A piped REPL session performs the correction-override beat: read → `:correct`
  → read, with debug fields visible.
- **Floors intact, one re-opened deliberately.** `tests\verify_reconstruction.py` re-runs clean
  against the anchor-cause-aware assembly (its own assertions updated as part of this target);
  the other three walkers re-run clean untouched; `db\migrate.py` no-arg still a clean no-op
  (no migration was needed).
- Every touched `[SETTLE-AT-BUILD]` was reported and confirmed before being built, and recorded
  in `decisions.md`.
