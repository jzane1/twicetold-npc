# Deferred write processing

Engram-style deferred write cognition: the raw observation text is stored immediately and the
expensive enrichment happens on the service's own schedule (the design follows Engram, arXiv
2606.09900, and the sleep-time-compute family). This is a cost and throughput optimization, not
a correctness fix: the zero-gist case is closed inline by the `thin_gist` escalation trigger, and
observe latency is a client concern served by async observes. Design truth is
[architecture.md](architecture.md) §5 and §7; the schema delta is migration 006. This document
describes the mechanism; it does not restate the data model.

The feature ships **default OFF** (`deferred_writes_enabled` 0.0). With the knob off the write path
is byte-for-byte the synchronous path.

## What is deferred, and what is not

Only the LLM calls defer. The local NLP pass (gist spans and entities) and the embedding stay in
the request path; the single write call and the escalation call move to the worker. A deferred
observe returns after NLP, embedding, and insert, so the row is fully vector- and
lexically-reachable the moment the observe returns. Enrichment writes back by supersession through
the existing chains, never by mutating stored content.

## The deferred observe (the un-enriched window's row shape)

With the knob on, `ingest_observation` skips both LLM calls and inserts:

- the raw `observation_text` as the live `original` head (the raw head is the un-enriched head, the
  same shape as the scoring-failed fallback),
- `importance_raw`, `typology`, `typology_confidence`, and `typology_source` NULL (the pending
  marker; a declared typology has nothing to defer and stores at insert),
- `scoring_failed = false` (pending is the signal; nothing failed),
- the NLP pass's spans, entities, affect, and embedding exactly as the synchronous path,
- `enrichment_pending = true`, `enrichment_attempts = 0`, and `enrichment_pending_triggers` set to
  the five non-importance escalation triggers evaluated at observe time. Their NLP raw material
  (unresolved references, low-confidence spans, novelty) is not recoverable from the database, so it
  is captured as a write-time fact and never cleared. The importance trigger is the worker's to add
  once a model importance exists.
- an `IngestResult` carrying the nullable scalars plus `enrichment_pending`, with honest zero LLM
  instrumentation (the per-attempt truth lives in the run log).

## The un-enriched window's retrieval contract

Retrieval is untouched, with no code changes; the window composes shapes the read path already
defines (architecture.md §6):

- **Vector and lexical reachability from t = 0**, because the embedding stays inline. A fresh
  action-observe therefore has full same-scene retrieval reachability the moment the observe returns.
- **Scoring**: a NULL importance takes the `importance_neutral` fallback, and the payload's
  `importance_raw` carries the effective value as always.
- **Serving**: the raw text serves verbatim (`read_mode = "verbatim"`).
- **Reconstruction during the window** is possible in principle (a fresh row rarely crosses the
  decay threshold); a retelling that wins the head triggers the facts-only completion path below.
  Gist spans exist from t = 0, so the reconstruction pipeline's zero-gist hole does not reopen.

## The worker (`app\deferred.py`)

One `DeferredWriteWorker` runs per process. It starts before the lifespan yield (and after
`SessionRunner.create`'s services), and stops (cancel then await) before the pool closes. The poll
loop is catch-log-continue, so the task never dies: a poisoned row burns its attempt budget and
falls to the orphan sweep. The worker uses `settings.model_write`; it adds no new model role.

`drain(limit=None)` is the deterministic entry that tests and walkers call directly, with no timers.
It first runs the orphan sweep (rows still pending with attempts at the maximum, left by a process
that died mid-attempt, terminal-filled without model calls), then claims and processes batches until
the queue is empty. Each row gets at most one attempt per drain pass: a failed row stays pending for
a later pass, and the poll loop is the retry spacing, never a back-to-back re-claim.

Per attempt, `_process` fetches the source snapshot (gone or not-pending is a silent skip), makes the
write call through the same `run_write_call` the synchronous branch uses (a failure records a `failed`
run row and leaves the row pending, the budget-spending attempt terminal-fills instead), resolves
typology through the shared `resolve_typology` (a downstream COALESCE keeps declared values), runs
escalation with the stored triggers plus the importance trigger once the model importance clears the
knob (a double failure stays soft: completion proceeds and `escalation_failed` is set), attempts an
opportunistic embedding repair when the live fact head is NULL (a failure leaves it NULL), and then
runs the one completion transaction, `db.apply_enrichment`.

The completion transaction (all model calls happen before it) does: (a) the guarded one-shot scalar
fill (`WHERE enrichment_pending`, the idempotency guard; rowcount 0 is a rolled-back no-op); (b)
escalation-novel `identity_components`; (c) the prose supersede, compare-and-set on the captured raw
head, where an already-moved head is skipped (facts-only); (d) the fact supersede, only on a real
delta such as a repaired embedding, with `basis_text` carried byte-verbatim server-side; (e)
add-only span appends; (f) cache eviction on every completion shape, since enrichment is a chain
writer; (g) the run-log row.

Escalation-novel entities become identity components and mention spans, never memory entities. The
synchronous path's fact entities are the NER-plus-client merge stored at insert, and enrichment
reproduces exactly what the synchronous path would have written and nothing more. This is why the
common completion touches only the telling chain, and the fact chain supersedes only for the
embedding repair.

The terminal fill (once `deferred_max_attempts` is spent) writes neutral importance,
`scoring_failed`, and the config-default typology (COALESCE keeps declared values), and clears
pending. The result is byte-equivalent to the synchronous scoring-failed end-state.
`escalation_failed` stays false, because that call never ran; the run log is the honest signal.

## Enrichment and the non-destructive invariant

`write_cause = 'enrichment'` is a sanctioned cause of mid-scene text change (alongside diegetic
events and authorial correction), and the exposure window is bounded by the poll interval. The
render supersedes the raw `original` head as a new `memory_details` head; a repaired embedding
supersedes the fact head; gist spans append add-only. Only the chainless `memories` scalars fill in
place, one-shot NULL-to-value (the sanctioned completion carve-out, the same class as `pinned`). If a
retelling or correction superseded the raw head first, enrichment completes facts only, with no prose
supersede, and still evicts the cache. `'enrichment'` joins the drift-anchor set.

## Failure semantics versus the synchronous ladder

The difference is deliberate: the synchronous path degrades immediately, the deferred path retries.

| Event | Synchronous path (knob off) | Deferred path |
|---|---|---|
| write call fails or malformed | degrade now: neutral importance, `scoring_failed`, raw-text head | retry later: `failed` run row, row stays pending; the terminal attempt reproduces the synchronous end-state |
| escalation double failure | soft: base gist plus `escalation_failed` | same (completion proceeds) |
| embedding fails | NULL embedding, lexically reachable | not applicable at observe (embed is inline); the worker's repair failure leaves NULL, the same end-state |
| malformed `typology_confidence` | salvage: None or clamped, write lands | same seat, same salvage |

Every path still lands the write. Deferral never adds a lost-write rung.

The `typology_confidence` parse seat salvages a bad value (`providers.salvage_confidence`): a
non-numeric or NaN model-emitted confidence becomes None (render, importance, and typology all
survive), a numeric out-of-range value is clamped into [0, 1], and a WARNING is logged. A
client-declared 422 stays loud.

## Concurrency and idempotency

Claims take skip-locked row locks and increment `enrichment_attempts` in the same short transaction,
so a crash mid-work deliberately consumes the attempt. A claimed row stays pending while worked, so a
second process (for example the API and a REPL against one database) can re-claim it mid-flight; the
completion guard makes the loser a rolled-back no-op. The worst case is duplicate model spend, never
duplicate rows, and the run log makes it measurable. The worker holds a pool connection only inside
database calls, never across a model call; the pool (`max_size` = `TWICETOLD_DB_POOL_MAX_SIZE`,
default 8) is shared with request handlers.

## Knobs

All live in `SERVICE_DEFAULTS` as floats under the `agent_knob` contract.

| Knob | Default | Meaning |
|---|---|---|
| `deferred_writes_enabled` | **0.0** | Kill-switch; 0.0 is the synchronous path byte-for-byte. Per-agent overridable. Gates deferral only: the worker always drains, so flipping it off never strands a row. |
| `deferred_poll_seconds` | 1.0 | Worker pass interval. Process-level (an agents.config override is inert by design). |
| `deferred_batch_size` | 8.0 | Rows claimed per batch (int at the call site). |
| `deferred_max_attempts` | 3.0 | Failed attempts before the terminal fill (int at the call site). |

## Instrumentation

A background worker has no response payload to ride, so per-attempt accounting persists in
`memory_enrichment_runs` (migration 006): the attempt number, the outcome
(`completed`, `completed_facts_only`, `failed`, or `terminal_degraded`), the error, the triggers, the
flags, the per-stage timings (`write_ms`, `escalation_ms`, `embed_ms`, `insert_ms`, `total_ms`, with
`insert_ms` measured inside the completion transaction up to the run-row statement), and the token
columns. The unscored `/chain` inspector read surfaces these together with `enrichment_pending` and
`enrichment_attempts`, and The Ledger renders the `enrichment` cause badge. The load driver carries
an `observe_total` p50/p95 series; its cost table sums seam tokens, so with the knob on the write and
escalation rows read near zero and the run log is the deferred-spend source of truth.

## Wire deltas

`IngestResult` carries the four write-call scalars as Optional plus `enrichment_pending: bool`
(default-off synchronous observes still populate everything). `MemoryChainResult` gains
`enrichment_pending`, `enrichment_attempts`, and `enrichment_runs` (the new `EnrichmentRunOut`).
These are mirrored field-for-field in the C# core (nullable `double?` and `string?`,
`EnrichmentPending`, and `EnrichmentRunOut`). No client behavior changes: the client reads `MemoryId`
and `DecayClass`, both always present.

## Verification

Suite Set K (`tests\test_deferred_writes.py`, 13 scenarios, one nlp-marked) and the walker
`tests\verify_deferred_writes.py` (51 criteria: migration shape, kill-switch parity, the deferred
observe shape, the full completion/retry/terminal/facts-only/repair/orphan ladder, anchor-set
membership, and worker lifecycle at both construction sites). The write-path walker staying
byte-identical is the deferred-off parity evidence. See [test-suite.md](test-suite.md) for the walker
scratch-database convention.
