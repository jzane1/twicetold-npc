# Deferred write processing — Phase C1 build target

Engram-style deferred write cognition (the 2026-07-23 ruling that created the target: raw text
stored immediately, enrichment at the service's own timing — Engram arXiv 2606.09900 + the
sleep-time-compute family). A **cost/throughput optimization by ruling**, never a correctness
fix: `thin_gist` closed the zero-gist correctness case inline (2026-07-23) and observe latency
was ruled a client concern (async observes, roadmap C5). Design truth is
[architecture.md](architecture.md) §5/§7; the five C1 spec rulings are the dated 2026-08-12
entries in `decisions.md`; the schema delta is migration 006. This doc points, it
does not re-derive.

> **Status: BUILT 2026-08-12, floor-verified 2026-08-13** (an overnight pause sat between the
> build and the verifier's verdict; the twenty-fifth floor row; suite Set K + the eighth walker
> `tests\verify_deferred_writes.py`). Ships **default OFF** (`deferred_writes_enabled` 0.0) —
> the sync path is byte-for-byte the pre-C1 path; the default flips at Phase D if the numbers
> earn it.

## The five spec rulings (2026-08-12, all Jack's)

1. **Defer only the LLM calls.** The local NLP pass (gist spans + entities) and the embedding
   stay in the request path; the single write call and the escalation call move to the worker.
   A deferred observe returns after NLP + embed + insert, fully vector- and lexically-reachable.
2. **Enrichment writes by supersession via the existing chains.** The render supersedes the raw
   `original` head as a new `memory_details` head, `write_cause = 'enrichment'`; a repaired
   embedding supersedes the fact head (`'enrichment'` there too); gist spans append add-only;
   only the chainless `memories` scalars fill in place, **one-shot NULL→value** (the sanctioned
   completion carve-out — the `pinned` class, see the invariant amendment). `'enrichment'`
   **joins the drift-anchor set**. If a retelling or correction superseded the raw head first,
   enrichment completes **facts only** — no prose supersede — and still evicts the cache.
3. **In-process async worker, default OFF.** Started at BOTH construction sites (`app\api.py`
   lifespan and `app\session.py` `SessionRunner.create`), knob-governed, with a directly
   callable `drain()` as the deterministic test entry. **No new model role** — the worker uses
   `settings.model_write`; the six-role slate and the same-model constraint are untouched.
4. **The byte-identical-within-a-scene invariant is amended**: deferred-enrichment completion is
   the **third sanctioned cause** of mid-scene text change (after diegetic events and authorial
   correction). The exposure window is bounded by the poll interval.
5. **The `typology_confidence` parse seat is fixed with salvage semantics**
   (`providers.salvage_confidence`): non-numeric/NaN model-emitted confidence → None (render,
   importance, and typology all survive); numeric out-of-range → clamped into [0, 1]; WARNING
   logs; the client-declared 422 stays loud. Closes the 2026-08-12 carried item.

## The deferred observe (the un-enriched window's row shape)

With the knob on, `ingest_observation` skips both LLM calls and inserts:

- the raw `observation_text` as the live `original` head (**the raw head IS the un-enriched
  head** — the existing scoring-failed fallback shape),
- `importance_raw` / `typology` / `typology_confidence` / `typology_source` **NULL** (the
  pending marker; a **declared** typology has nothing to defer and stores at insert),
- `scoring_failed = false` — pending is the signal, nothing failed,
- the NLP pass's spans, entities, affect, and embedding exactly as the sync path,
- `enrichment_pending = true`, `enrichment_attempts = 0`, and
  `enrichment_pending_triggers` = the **five non-importance escalation triggers** evaluated at
  observe time (their NLP raw material — unresolved references, low-confidence spans, novelty —
  is not recoverable from the DB; a write-time fact, never cleared). The importance trigger is
  the worker's to add once a model importance exists.
- `IngestResult`: nullable scalars + `enrichment_pending`, with honest **zero** LLM
  instrumentation (the per-attempt truth lives in the run log).

## The un-enriched window's retrieval contract

**Retrieval is untouched — zero code changes** (the byte-parity contract stands). The window is
a composition of already-ruled shapes:

- **Vector + lexical reachability from t = 0** (embedding stays inline — ruling 1). This is
  also the answer to the question A1 delegated here: a fresh action-observe has full same-scene
  retrieval reachability the moment the observe returns.
- **Scoring**: NULL importance takes the `importance_neutral` fallback (`retrieval.py`; the
  payload's `importance_raw` carries the effective value, as always).
- **Serving**: the raw text serves verbatim (`read_mode = "verbatim"`, honest).
- **Reconstruction during the window**: possible in principle (a fresh row rarely crosses
  theta); a retelling that wins the head triggers the facts-only completion path. Gist spans
  exist from t = 0 (NLP inline), so the stage-4 zero-gist hole does **not** re-open.

## The worker (`app\deferred.py`)

One `DeferredWriteWorker` per process; `start()` before the lifespan yield / after
`SessionRunner.create`'s services, `stop()` (cancel + await) **before** the pool closes. The
poll loop is catch-log-continue — the task never dies; a poisoned row burns its attempt budget
and falls to the orphan sweep.

**`drain(limit=None)`** — the deterministic entry (tests and walkers call it directly; no
timers): first the **orphan sweep** (rows still pending with `attempts >= max` — a process died
mid-final-attempt — terminal-filled **without** model calls), then claim/process batches until
the queue is empty. **At most one attempt per row per drain pass** — a failed row stays pending
for a *later* pass; the poll loop is the retry spacing, never a back-to-back re-claim.

**Per attempt** (`_process`): fetch the source snapshot (gone/not-pending → silent skip) → the
write call through the SAME `run_write_call` the sync branch uses → on failure, a `failed` run
row (the row stays pending; the budget-spending attempt terminal-fills instead) → typology via
the shared `resolve_typology` (COALESCE downstream keeps declared values) → escalation with the
stored triggers + the importance trigger when the model importance clears the knob (double
failure stays SOFT, the 2026-07-22 stance: completion proceeds, `escalation_failed` set) → an
**opportunistic embedding repair** when the live fact head is NULL (failure → stays NULL) → the
one completion transaction, `db.apply_enrichment`.

**The completion transaction** (all model calls happen before it): (a) the guarded one-shot
scalar fill (`WHERE enrichment_pending` — the idempotency guard; rowcount 0 → rolled-back
no-op); (b) escalation-novel `identity_components`; (c) the prose supersede, CAS on the
captured raw head — already-moved → SKIP (facts-only); (d) the fact supersede only on a real
delta (a repaired embedding; `basis_text` carried byte-verbatim server-side); (e) add-only span
appends; (f) **cache eviction, always, on every completion shape** (enrichment is a chain
writer — the generalized eviction invariant); (g) the run-log row.

**Sync parity rule for escalation novels:** they become identity components and mention spans,
**never memory entities** — the sync path's fact entities are the NER + client merge stored at
insert, and enrichment reproduces what the sync path would have written, nothing more. (This is
why the common completion touches only the telling chain; the fact chain supersedes only for
the embedding repair.)

**The terminal fill** (`deferred_max_attempts` spent): neutral importance + `scoring_failed` +
the config-default typology (COALESCE — declared values stand), pending cleared —
**byte-equivalent to the sync scoring-failed end-state**; `escalation_failed` stays false (that
call never ran; the run log is the honest signal).

## Failure semantics vs the sync ladder (the deliberate difference)

| Event | Sync path (knob off) | Deferred path |
|---|---|---|
| write call fails / malformed | degrade NOW: neutral importance, `scoring_failed`, raw-text head | retry LATER: `failed` run row, row stays pending; terminal attempt reproduces the sync end-state |
| escalation double failure | soft: base gist + `escalation_failed` | same (completion proceeds) |
| embedding fails | NULL embedding, lexically reachable | n/a at observe (embed is inline); the worker's repair failure leaves NULL — same end-state |
| malformed `typology_confidence` | salvage (ruling 5): None / clamped, write lands | same seat, same salvage |

Every path still lands the write. Deferral never adds a lost-write rung.

## Concurrency & idempotency

Claims take skip-locked row locks and increment `enrichment_attempts` in the same short
transaction (a crash mid-work deliberately consumes the attempt). A claimed row stays pending
while worked, so a second process (API + REPL against one DB) can re-claim it mid-flight — the
completion guard makes the loser a rolled-back no-op. **Worst case is duplicate model spend,
never duplicate rows**, and the run log makes it measurable. The client `event_id` dedup stays
deferred (the standing write-path `[SETTLE-AT-BUILD]`). The worker holds a pool connection only
inside db calls, never across a model call; the pool (`max_size` = `TWICETOLD_DB_POOL_MAX_SIZE`,
default 8 — knobbed at F0, 2026-08-26) is shared with request handlers.

## Knobs (all in `SERVICE_DEFAULTS`, floats, `agent_knob` contract)

| Knob | Default | Meaning |
|---|---|---|
| `deferred_writes_enabled` | **0.0** | Kill-switch; 0.0 = sync path byte-for-byte. Per-agent overridable. Gates DEFERRAL only — the worker always drains, so flipping off never strands a row. |
| `deferred_poll_seconds` | 1.0 | Worker pass interval. Process-level (no agent context — an agents.config override is inert by design). |
| `deferred_batch_size` | 8.0 | Rows claimed per batch (int at the call site). |
| `deferred_max_attempts` | 3.0 | Failed attempts before the terminal fill (int at the call site). |

## Instrumentation (instrument-at-the-seam, persisted)

A background worker has no response payload to ride, so per-attempt accounting persists in
**`memory_enrichment_runs`** (migration 006): attempt, outcome
(`completed | completed_facts_only | failed | terminal_degraded`), error, triggers, flags, the
per-stage timings (`write_ms` / `escalation_ms` / `embed_ms` / `insert_ms` / `total_ms` —
`insert_ms` measured inside the completion transaction up to the run-row statement), and the
token columns. Surfaced on the **unscored `/chain` inspector read** (its unscored-by-contract
wording untouched) together with `enrichment_pending` + `enrichment_attempts`; The Ledger
renders the `enrichment` cause badge. The load driver gains an `observe_total` p50/p95 series;
its cost table sums SEAM tokens, so with the knob on the write/escalation rows read ~0 — the
run log is the deferred-spend source of truth (wiring the driver to query it is a Phase D
sequencing note, not C1).

## Wire deltas

`IngestResult`: the four write-call scalars are now Optional + `enrichment_pending: bool`
(default-OFF sync observes still populate everything). `MemoryChainResult`: `enrichment_pending`,
`enrichment_attempts`, `enrichment_runs` (the new `EnrichmentRunOut`). Mirrored field-for-field
in `client\NpcMemory.Core\Models.cs` (nullable `double?`/`string?` + `EnrichmentPending`;
`EnrichmentRunOut`); both C# projects build 0-warning and the 24-check console harness gate
re-ran. No client behavior change — the harness reads `MemoryId` + `DecayClass`, both always
present.

## Verification

Suite **Set K** (`tests\test_deferred_writes.py`, 13 scenarios, 1 nlp-marked) + the **eighth
walker** `tests\verify_deferred_writes.py` (51 criteria: migration shape, kill-switch parity,
the deferred observe shape, the full completion/retry/terminal/facts-only/repair/orphan ladder,
anchor-set membership, worker lifecycle at both construction sites). The write-path walker
staying byte-identical at **53/53** is the deferred-OFF parity evidence. The walker runs on the
fixed-name `twicetold_test` scratch DB like the other seven (the shared-DB mechanism stays a
carried item awaiting its own ruling).
