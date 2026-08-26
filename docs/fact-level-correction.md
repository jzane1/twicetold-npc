# Fact-level correction — v1 build target

Seventh build target, on top of migration 01, write path v1, read path v1, CLI harness v1,
reconstruction v1, and authorial-correction v1. This specs **the fact-level correction target** —
slated by explicit ruling 2026-07-17 ("versioned memories-row facts + corrected embedding so
retrieval follows the fix; migration-002-class design with its own spec pass") and immediate-queue
item 1 since the authorial build completed. The gap it closes, recorded twice: after an authorial
correction, **retrieval still ranks the memory by the original observation's embedding** — the
operator's fix does not move recall. (The slating's second half — gist spans indexing the original
text — was closed from the consumer side by the built constraint-follows-anchor mechanism:
corrected-anchored chains never read spans. What remained open is the retrieval half; this target
closes it.) Design truth is [architecture.md](architecture.md) §6/§8 (+ the §4.4 fact-chain
subsection added with this spec); the rulings are in [decisions.md](decisions.md); the 001 schema
is in [migration-01.md](migration-01.md). **A new migration is a fact of this target — the first
spec for which that is true**: migration 002 lands on the `db\migrate.py` ledger seam built for
exactly this (2026-07-17 schema-evolves-by-migration rule). This doc points, it does not
re-derive.

Four scope forks were ruled at spec time (dated "Fact-level correction spec scope rulings —
2026-07-18" entry in `decisions.md`; presented twice at Jack's request — technical, then a
plain-prose re-introduction — and ruled on the re-presentation):

1. **Fact scope = embedding only.** The corrected text is re-embedded (one embedding-provider
   call); importance, typology, decay class, entities, and affect stand as write-time facts about
   the *event* — consistent with the deliberately-disregarded 2026-07-12 staleness tension.
   Honest deferral recorded with the ruling: the entities column's first read consumer is the
   gate's GIN path (immediate-queue item 2, the next target); until an additive fact-chain column
   rides there, a fact-corrected memory carries its original entities. *(Closed 2026-07-19:
   migration 003 rides the gate target, and the correction verb re-derives entities —
   `mid-dialogue-gate.md`.)* **Rejected:** +mechanical
   NLP pass (entities/affect feed nothing readable today; gist re-derivation has zero consumers
   on corrected chains; spaCy latency on the operator verb); +Haiku re-score (a second model
   call; importance moves to the fact head, widening the candidate-SQL delta); operator per-field
   overrides (no model calls, but the same candidate-SQL widening for importance).
2. **Version shape = a fact-version child table** — the exact `memory_details` precedent applied
   to the semantic basis: chain rows under the stable `memory_id`, supersession by `invalid_at`,
   a one-live-head partial unique index, the non-destructive invariant untouched. Migration 002
   creates the table and backfills one `original` row per existing memory. The read-path and
   write-path floors re-open at build (candidate SQL joins the fact head; observe mints the fact
   row) — re-verification steps, priced as steps. **Rejected:** history table + in-place-updated
   live columns (candidate SQL untouched, but "never UPDATE stored content in place" would narrow
   — an invariant rewording propagated through every rule doc); self-chaining the memories row
   (`memory_id` is simultaneously the PK and the stable FK target of four tables and every wire
   payload — a new anchor ID touches everything for the same semantics).
3. **Surface = one combined verb.** `POST /v1/memories/{memory_id}/correction` becomes
   fact-following: the operator's corrected text is both the telling head (byte-verbatim, the v1
   contract) and the embedded fact basis, in one transaction. One truth per memory — a fact-only
   correction would leave an original-anchored chain whose reconstructor keeps re-injecting the
   corrected-away data from stale gist spans. **Rejected:** a separate fact verb (needs a second
   ground-truth rule keyed on fact-version state — two truths per chain, against the
   one-ground-truth-per-chain ruling of authorial fork 2 — and re-opens the reconstruction
   floor); a scope field (inherits the same problem in facts-only mode, triples the behavior
   matrix).
4. **Embed failure = all-or-nothing, fail-loud.** Embed *before* the transaction opens (never
   hold a transaction across a network call — the reconstruction path's shape); on provider
   failure nothing is written and the operator retries on a loud error. Honest price recorded:
   during an embedding outage, telling corrections are blocked too — v1 needed no model.
   **Rejected:** land-with-NULL-embedding (the memory vanishes from the vector probe entirely —
   worse than the stale embedding — and needs a retry verb that doesn't exist);
   land-with-stale-embedding (retrieval keeps following the old semantics, the exact problem this
   target exists to fix).

> **Status: BUILT & floor-verified 2026-07-18** (same day as the spec). Every `[SETTLE-AT-BUILD]`
> item below was ruled at build time (dated "Fact-level correction build rulings" entry in
> `decisions.md`): two via explicit questions — **dual-write vs freeze ruled FREEZE** (observe no
> longer writes `memories.embedding`; the fact head is the sole vector home for post-002 rows,
> and the queryable embed-degradation signal moved there — the recommendation had been
> dual-write), and **the old `memories_embedding_hnsw` index dropped in 002** — the remaining
> eight mechanical shapes approved as proposed. Migration `db\migrations\002_fact_versions.sql`
> applied to `longmem` (ledger: 001 + 002, no-arg migrate a clean no-op under the new wording).
> The verb landed in `app\db.py` (`apply_authorial_correction` grown: fact supersede + insert in
> the same transaction; `insert_observation` mints the `original` fact head; the vector probe
> joins the live fact head) + `app\ingest.py` (embed-before-transaction, `CorrectionEmbedFailedError`)
> + `app\api.py` (502) + `app\schemas.py` (widened `CorrectionResult`, `IngestResult.fact_version_id`)
> + `app\cli.py` (both head swaps + embed timing in `:correct`). **`app\retrieval.py` and
> `app\reconstruction.py` are byte-untouched — the no-reconstruction-delta claim held.** Walker
> `tests\verify_fact_correction.py` (32 assertions); prior walkers 35→38 (write; incl. the one
> ruling-driven modification — the [14] degradation-signal query moved to the fact head),
> 34→36 (read, addition only), 31→33 (authorial, addition only); reconstruction 42/42 and CLI
> harness 36/36 **unmodified**. floor-verifier **pass** with working postgres MCP tools; live
> piped REPL beat: the `:correct` line prints both head swaps, and the same query's relevance
> moved 0.4686 → 0.5637 across the correction — retrieval following the fix, visible in the
> debug view.

## Principles this build honors

- **Non-destructive supersession — now on two chains under one `memory_id`.** The fact chain
  supersedes by `invalid_at` and inserts, exactly like the telling chain. Never UPDATE content,
  never DELETE chain rows. The superseded fact row keeps the original embedding — the
  ground-truth record still never lies.
- **One model call, stated honestly.** v1's "no model calls" purity line is **superseded, not
  silently dropped**: embedding the corrected basis *is* the target. The call uses the existing
  embedding role and provider — **no new model role, no new env var, no new knob expected**
  (stop and report if the build surfaces one). The operator's text itself is stored byte-verbatim
  in both chains; no render pass ever touches it.
- **Verb discrimination by `write_cause` alone.** The fact chain reuses the existing vocabulary —
  its writers are the observe insert (`original`), this verb (`authorial_correction`), and — since
  migration 006 — the deferred-enrichment worker's embedding-repair version (`enrichment`; the
  CHECK widened with C1, 2026-08-12, and this line missed it until the F0 audit, 2026-08-26).
  No `corrections`-table row (still diegetic-only by CHECK); no marker on prior rows.
- **The eviction invariant** (standing): the combined verb is still a chain writer — it evicts
  **all** `reconstruction_cache` rows for the memory_id, same transaction, unchanged from v1.
- **Re-anchoring unchanged.** The drift anchor derives from the *telling* chain's `write_cause`
  rule; fact versions never participate in anchor selection.
- **Correction outranks pin; the corrected heads inherit it.** Pin lives on the memories row,
  untouched by this target; inheritance stays structural.
- **Fail-loud operator surface.** No soft paths; the one new failure mode (embed) fails the whole
  verb loudly (fork 4).
- **The 1536 dimension lock** holds: same embedding model, same column type, both tables.
- **Honest self-description, IDs in payloads, instrument at the seam** — the result carries the
  new fact IDs and the embed call's timing/tokens like every other seam.

## Scope boundary — do NOT build

**Re-derivation beyond the embedding** — no NLP re-pass, no re-score, and explicitly **no gist
re-derivation**: gist spans on corrected chains have zero consumers (the corrected-anchor prompt
branch ignores them), and the span rows remain immutable facts about the original observation.
**The entities fact column + the gate's GIN path** — rides with the gate (immediate-queue
item 2); the honest deferral is recorded in fork 1. *(Specced & built 2026-07-19 — migration 003 applied,
`mid-dialogue-gate.md`; the gate is item 1 since the 2026-07-18 renumber.)* **Purge** (its docs contract now names fact
versions — architecture §12). **Diegetic fact-writes** — unslated; any future in-world mechanism
that moves *facts* rather than tellings needs its own ruling. **Re-embedding on an
embedding-model migration** (the 1536 lock stands; a model-swap story is its own future target).
**as_of-windowed fact serving** — the 2026-07-18 stored-coherence ruling extends to the fact
chain: candidate SQL always joins the live fact head; prior fact versions are asserted via
windowed SQL, never served. If adjacent work looks necessary, stop and report — with the correct
option and its real cost stated.

## Surface (where this attaches)

The existing operator verb, grown — no new route, no new REPL command:

- **Route:** `POST /v1/memories/{memory_id}/correction` (built 2026-07-18), now fact-following.
- **Request: unchanged.** `CorrectionRequest { content, client_timestamp, expected_detail_id? }`.
  The corrected content plays two roles — the telling head and the embedded fact basis — both
  byte-verbatim. No new fields under these rulings.
- **Response:** `CorrectionResult` **widens**. `[SETTLE-AT-BUILD]` exact fields — suggested
  `+ fact_version_id, superseded_fact_version_id, embed_ms, embedding_tokens`; `total_ms` keeps
  covering the verb end-to-end. v1's "no token fields — no model calls" line is superseded.
- **Observe path:** `insert_observation` mints the `original` fact row in the same transaction
  (basis = `observation_text`, the write-time embedding; an embed-failure degradation carries
  NULL into the fact head as honestly as it does into `memories.embedding`).
- **CLI:** `:correct` syntax unchanged; the debug view surfaces the new result fields
  (`[SETTLE-AT-BUILD]` exact rendering).
- **Errors, loud:** 404 / 409 / 422 unchanged; embedding-provider failure → 5xx-class with
  nothing written — `[SETTLE-AT-BUILD]` exact status (suggested 502, aligned with how provider
  failures surface at the route layer today).

## Mechanism — embed first, then one transaction

1. **Embed the corrected content before the transaction opens** (never hold a transaction across
   a network call — the reconstruction write-back precedent). Provider failure here → the loud
   all-or-nothing error; no row anywhere has changed.
2. **One transaction** (grows `apply_authorial_correction`, `app\db.py`):
   1. Supersede the live telling head — predicate + rowcount, optional `expected_detail_id`
      compare-and-swap (v1, unchanged; stale → 409, rollback).
   2. Insert the corrected telling head — `write_cause = 'authorial_correction'`,
      `valid_at = t_c` (v1, unchanged).
   3. Supersede the live fact head — predicate + rowcount. No second CAS field: the telling-head
      CAS already serializes racing corrections, and this verb was the fact chain's only
      post-observe writer as built *(since migration 006 the enrichment worker's embedding
      repair also writes the chain; its interaction with in-flight corrections is
      deferred-writes.md's contract — annotated at the F0 audit, 2026-08-26)*.
   4. Insert the corrected fact row — `basis_text` = operator content byte-verbatim,
      `embedding` = the pre-computed vector, `write_cause = 'authorial_correction'`,
      `valid_at = t_c`. Prior `invalid_at` = new `valid_at` on both chains — the
      coherent-chain-timeline precedent.
   5. Evict all `reconstruction_cache` rows for the memory_id (the inherited invariant).
3. **One live fact head, always.** Observe mints it, the 002 backfill guarantees existing rows,
   the correction supersedes-and-inserts atomically, and the one-live-head partial unique index
   is the structural backstop — the same shape that guards the telling chain.

## Migration 002 — the fact-version chain

Lands on the ledger seam exactly as designed 2026-07-13: one file, DDL + ledger row in one
transaction, `IF NOT EXISTS` defense-in-depth, second run a no-op. Sketch (all names
`[SETTLE-AT-BUILD]`, suggested):

```sql
-- 002_fact_versions.sql (suggested name)
CREATE TABLE IF NOT EXISTS memory_fact_versions (
    fact_version_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_id        uuid NOT NULL REFERENCES memories (memory_id),
    basis_text       text NOT NULL,   -- the embedded text, byte-verbatim
    embedding        vector(1536),    -- NULL = embed-failure degradation, mirrors memories
    write_cause      text CHECK (write_cause IN ('original', 'authorial_correction')),
    created_at       timestamptz NOT NULL DEFAULT now(),
    valid_at         timestamptz NOT NULL,
    invalid_at       timestamptz
);

-- Backfill: one 'original' fact head per existing memory — before the indexes,
-- so the HNSW builds on the populated table.
INSERT INTO memory_fact_versions (memory_id, basis_text, embedding, write_cause, valid_at)
SELECT m.memory_id, m.observation_text, m.embedding, 'original', m.valid_at
FROM memories m
WHERE NOT EXISTS (SELECT 1 FROM memory_fact_versions f WHERE f.memory_id = m.memory_id);

CREATE UNIQUE INDEX IF NOT EXISTS memory_fact_versions_one_live_head
    ON memory_fact_versions (memory_id) WHERE invalid_at IS NULL;
CREATE INDEX IF NOT EXISTS memory_fact_versions_embedding_hnsw
    ON memory_fact_versions USING hnsw (embedding vector_cosine_ops)
    WHERE invalid_at IS NULL;
CREATE INDEX IF NOT EXISTS memory_fact_versions_memory_id_idx
    ON memory_fact_versions (memory_id);
```

- The backfill's `WHERE NOT EXISTS` guard mirrors the `IF NOT EXISTS` stance: the ledger is the
  primary idempotency, the guard is the backstop.
- The **partial HNSW** (`WHERE invalid_at IS NULL`) keeps superseded vectors out of the probe;
  partial indexes are a planner feature orthogonal to the access method, and the candidate SQL
  must state the predicate verbatim so the planner matches it. `[SETTLE-AT-BUILD]` partial vs
  full.
- Under the suggested dual-write default, `memories.embedding` remains the **write-time event
  fact** (the 001 principle: all write-time fact columns exist); the freeze arm would leave the
  column NULL for post-002 observes, splitting its meaning across an epoch — that price rides
  the tag. `[SETTLE-AT-BUILD]` dual-write vs freeze at observe — suggested dual-write; and the
  fate of `memories_embedding_hnsw` (an index is a derived structure, not stored content —
  dropping it in 002 is sanctioned; leaving it dormant is also priceable). *(Ruled at build via
  explicit questions, 2026-07-18: **FREEZE** — the epoch split accepted, one vector home; the
  column stays as written for pre-002 rows and is never written again. The queryable
  embed-degradation signal (2026-07-13) moves to the live fact head. And the old index is
  **dropped in 002**.)*
- After 002, the standing floor criterion "001 the only migration; no-arg migrate a clean no-op"
  reads **"001 + 002 applied, 0 pending"** — the build updates that wording wherever it is
  recorded. *(Since the gate build, 2026-07-19: **"001 + 002 + 003 applied, 0 pending"** —
  migration 003, `mid-dialogue-gate.md`.)*

## The retrieval delta

The candidate SQL joins the **live fact head** and the probe orders by its embedding — this is
the entire mechanism by which retrieval follows the fix. The read-path floor re-opens (candidate
SQL + walker re-run): the step, in full. Scoring inputs are otherwise unchanged —
`importance_raw`, `pinned`, `decay_class`, `valid_at` still read from `memories`; only
`distance` moves to the fact head. **Scores change only through relevance.** The degraded path
(`fetch_live_candidates`) join is `[SETTLE-AT-BUILD]` — post-backfill it is a tautology; join
for uniformity or skip for economy.

**Named asymmetry, accepted:** for corrected memories the embedding basis shifts from
observation-class text (the raw event) to the operator's corrected text. This is the same
asymmetry constraint-follows-anchor accepted — after an authorial correction, the operator's
text *is* the ground truth for that memory, in the constraint slot and now in the retrieval
probe.

## The reconstruction delta: none

Stated as a claim the build proves, not an omission: the drift check embeds candidate and anchor
*text* fresh at check time — it never reads the stored vector; the corrected-anchor prompt
branch ignores `observation_text` and gist spans; `fetch_reconstruction_sources` is untouched.
The reconstruction floor **stays closed** at this build, and `tests\verify_reconstruction.py`
re-running clean *without modification* is the done-when assertion of exactly that.

## Immediate effect & invariants

No cache sits in front of the vector probe — the corrected embedding steers the very next
retrieval, mid-scene included. The within-scene stability invariant needs **no further
amendment**: fact correction rides the same authorial-correction verb the invariant already
sanctions (amended 2026-07-17), and the invariant governs served *text* — which memories
retrieval surfaces was never under the byte-identity guarantee.

## Instrumentation (rides the seam)

The embed call's timing and tokens land in `CorrectionResult` (`[SETTLE-AT-BUILD]` names —
suggested `embed_ms`, `embedding_tokens`); the REPL debug view surfaces them; the load driver is
untouched (correction is not a driven verb — stop and report if the build finds otherwise).

## `[SETTLE-AT-BUILD]` — physical shapes, ruled at build (stop and report, never silently choose)

**All ruled 2026-07-18 with the build plan** (dated "Fact-level correction build rulings" entry
in `decisions.md`; two via explicit questions, marked):

- Exact table/column/index names — **ruled as suggested:** `memory_fact_versions`,
  `fact_version_id`, `basis_text`; index names per the sketch.
- Fact-chain `write_cause` CHECK vocabulary — **ruled as suggested:** the two live causes only.
- Partial vs full HNSW; the fate of `memories_embedding_hnsw` — **ruled: partial (live heads
  only); the old index DROPPED in 002 (explicit question)** — derived structure, zero readers
  once the probe moves.
- Dual-write vs freeze of `memories.embedding` at observe — **ruled: FREEZE (explicit question,
  against the dual-write recommendation)** — one vector home; the epoch split accepted; the
  degradation signal moves to the live fact head.
- Degraded-path (`fetch_live_candidates`) fact-head join — **ruled: unjoined** (no distance is
  computed there; the query stays byte-identical to v1).
- Backfill guard shape — **ruled as sketched:** `WHERE NOT EXISTS`, before the indexes.
- Wire deltas — **ruled:** `CorrectionResult += fact_version_id, superseded_fact_version_id,
  embed_ms, embedding_tokens` (flat, the v1 `total_ms` style); `IngestResult += fact_version_id`.
- REPL `:correct` debug-view rendering — **ruled:** both head swaps + embed ms/tokens in the
  printed line; the new error prints loudly (the hard-stop pattern).
- Embed-failure status code — **ruled: 502** (`CorrectionEmbedFailedError`, following the
  escalation hard-stop then live at the observe route). *(That observe-route hard-stop was retired
  2026-07-22 — escalation now soft-degrades; this correction path stays fail-loud on its own
  all-or-nothing ruling.)*
- Walker — **ruled:** `tests\verify_fact_correction.py` (32 assertions, scratch pattern);
  write-path walker 35 → 38 (incl. the one ruling-driven modification: the [14]
  degradation-signal query moved to the fact head), read-path 34 → 36 and authorial 31 → 33 by
  addition only; reconstruction and CLI-harness walkers untouched.

## Done when

- **Retrieval follows the fix, structurally.** Fake-mode mechanic (a *fixture* property —
  production uses real embeddings): the deterministic fake embedding is a pure function of text,
  so probe text == stored basis ⇒ cosine distance exactly 0. Seed a memory and an unrelated
  decoy; probe with the corrected text *before* the correction → the memory's distance is
  bounded away from 0; *after* → it ranks **first at the db layer** with distance < 1e-6, and is
  present at the service layer with relevance ≈ 1.0. (The ranking claim anchors at the db layer,
  where order is pure distance — a service-level rank assertion would hang on hash-derived fake
  importance.)
- **Fact-chain shape.** Exactly one live fact head; the corrected head
  `write_cause = authorial_correction`, `basis_text` **byte-identical to the operator's input**,
  `valid_at = t_c`; the superseded row `invalid_at = t_c` and **still carrying the original
  embedding** (value-assertable — the non-destructive record survives).
- **Telling-side contract intact.** Every v1 done-when — chain shape, CAS, eviction, no
  `corrections` row, `observation_text` and gist rows untouched — still holds; the combined verb
  changed nothing v1 asserts.
- **Stored bi-temporal coherence, second chain.** A windowed SQL query re-derives which fact
  version was live at any instant, with no gap or overlap at t_c (the v1 walker's exact
  pattern applied to the fact chain).
- **Observe mints the fact row.** A new observation lands with exactly one `original` fact head
  in the same transaction; embed-failure degradation carries NULL into the fact head.
- **Backfill + ledger.** Post-migration: live fact-head count equals memories count; `migrate.py`
  applies 002 once, then no-ops; the floor criterion wording updated to "001 + 002, 0 pending".
- **All-or-nothing failure.** A failing embedding provider on the correction → nothing written
  anywhere (telling chain, fact chain, cache all unchanged), loud error through the route.
- **Reconstruction floor untouched.** `tests\verify_reconstruction.py` re-runs clean **without
  modification** — the proof of the no-delta claim.
- **Floors re-verified.** The read-path and write-path walkers re-run with their grown
  assertions; the authorial walker grows the fact-side assertions; fresh-scratch pattern;
  `longmem` pristine; floor-verifier pass.
- Every touched `[SETTLE-AT-BUILD]` was reported and confirmed before being built, and recorded
  in `decisions.md`.

## Propagated with this spec

CLAUDE.md (the non-destructive invariant's parenthetical grows the fact chain);
`architecture.md` §4.4 (new subsection), §6 (probe marker), §8 (authorial bullet), §12 (purge
prose); `authorial-correction.md` (gap-closure annotations); `migration-01.md` (002 pointers);
`test-suite.md` (Set A authorial pair + a degradation case); `decisions.md` (the dated rulings
entry); `status.md` (phase, log, queue annotation).
