# twicetold-npc: Test suite

The pytest suite in `tests\test_*.py` holds roughly 228 scenarios across Sets A through Q plus the
route-contract and degradation scenarios. Fifteen carry the `nlp` marker (they call the write pass at
the service level and pay the lazy spaCy and fastcoref load), so the turn-end subset that runs on every
edit is `-m "not nlp"`, about 213 scenarios. The full suite runs on demand and at verification. The
suite is offline, keyless, deterministic, and self-managing (it creates and drops its own scratch
database, `twicetold_suite`); when Postgres is unreachable it skips loudly and exits green, so it is
CI-ready.

The scenario suite is a first-class deliverable, with its own fixture and runner in `tests\`, not an
afterthought.

## The one rule

**Structural-only.** Assert on memory IDs, row types (`write_cause`, `read_mode`, typology), chain
shape, cache state, timestamps, and byte-identity of returned text. Never assert on generated prose: a
model's wording is not a test surface. Judged evaluations (drift-toward-identity, Bartlett-style
distortion operators) belong to the evaluation story ([eval-harness.md](eval-harness.md)), not this
suite.

The corollary that makes structural testing possible: read endpoints that run retrieval return memory
IDs and scores alongside prose. That contract is load-bearing; if such an endpoint stopped returning
IDs, the suite would be dead. Four reads are unscored by contract because they run no retrieval:
`/chain`, `/agents/{id}/memories`, `/memories/{id}/reconstruction-metrics`, and `/agents/{id}/state`.
They still carry IDs and structured fields on every row, which is what their scenarios assert.

## Set A: correction-override

Forked into structural pairs by correction verb, keyed on `write_cause`.

- **Authorial pair (replace model):** the prior head is superseded (`invalid_at` set); exactly one new
  head row is typed `authorial_correction`; cache rows for the memory_id evict; the memory ID is present
  in retrieval candidates, serving the corrected head; the drift anchor resolves to that head;
  post-correction reconstruction takes the corrected head as its fixed constraint (a pure prompt-assembly
  assertion); a mid-scene correction changes served text immediately (a sanctioned cause); no
  `corrections` row. The fact chain (architecture.md §8): the prior fact head is superseded; one
  corrected fact head carries `basis_text` byte-identical to the operator input and the corrected
  embedding; the superseded fact row still carries the original embedding; the memory ranks by the
  corrected embedding (asserted at the db layer, where order is pure distance), assertable via the
  fake-mode distance-0 mechanic (the deterministic fake embedding is a pure function of text, so probe
  text equal to stored basis gives cosine distance 0; a fixture property, since production uses real
  embeddings).
- **Diegetic pair:** the chain is intact; the new head row is typed `rationalization` or
  `update_with_resentment`; a correction record is present; the cache evicts. This pair lives in Set N
  (`tests\test_set_n_dissonance.py`), both verbs as the structural pair this section specifies.

## Set B: decay-only

Exercises injected `valid_at` timestamps (time travel) to prove that recency decay and bi-temporal
invalidation are structurally distinct mechanisms: decay hides detail at read time without touching
rows, while invalidation stamps rows without touching decay. The pre-reconstruction assertable surface
is the recency score component (decay moves scores, not rows; detail-hiding assertions land with
reconstruction).

## Set C: identity-conditioned reconstruction

- Gist span rows are immutable.
- A write-back inserts a new head and supersedes the prior row under the same memory_id.
- An identity-version bump gives a cache miss; a stable identity plus the same decay band gives a cache
  hit (the cache key's version component composes `identity_version` with the scene-frozen thinning
  band; architecture.md §7).
- The same `(memory_id, composed cache key)` returns byte-identical text.
- Pinned memories never grow reconstruction chain rows and always read verbatim.
- Correction verbs evict caches and cascade or preserve the chain per the two-verb rule.
- The drift bound is enforced (an over-threshold candidate write is refused; the prior head is kept).
- Within-scene text stability: absent a diegetic event, an authorial correction on that memory, or a
  deferred-enrichment completion ([deferred-writes.md](deferred-writes.md)), repeated reads within one
  scene are byte-identical.

## Set D: mid-dialogue gate

See [mid-dialogue-gate.md](mid-dialogue-gate.md); the walker covers these.

- **Loader-parity:** a request without `loaded_memory_ids` behaves byte-identically to the loader turn
  (payload shape and SQL).
- **Closed gate:** a covered, near-loaded utterance serves exactly the loaded IDs, with zero probe SQL,
  `signals_fired == []`, relevance non-null on every embedded item (a NULL-embedding loaded row carries
  `relevance = null`), and deterministic order.
- **Novelty fire:** a far utterance fetches, appends only new IDs marked `gate_fetched`, and logs exactly
  `["novelty"]` (the deterministic fake's locality is a fixture property; production uses real
  embeddings).
- **Tripwire fire plus covered suppression:** an uncovered live-component mention fires
  `["entity_tripwire"]` and the fetch contains the entity; the same mention covered by a loaded item's
  fact-head entities does not fire.
- **Both-signal logging:** far plus uncovered logs both constants; every fire event carries non-empty
  `signals_fired`.
- **Append plus byte-stability:** the loaded set is append-only within a scene; a gate-fetched item's
  text is byte-stable from its first mid-scene serving onward (the invariant governs served text; which
  memories surface was never under it).
- **Damper plus reset:** the max of consecutive fruitless fetches suppresses novelty (the tripwire stays
  live); a scene boundary resets the streak and suppression.
- **Efficacy booleans:** `novelty_outscored` and `entity_covered` populate per the comparators on fire
  events.
- **Entities-follow-correction pair (migration 003):** a correction moves the fact head's entities (NER
  plus optional operator field, merged); windowed SQL re-derives entity liveness at any instant; and
  superseded fact rows keep their entities.

## Set E: dialogue-turn topology

These scenarios live inside `test_set_d_gate.py` and `test_degradation.py` rather than a file of their
own, because the weights and degradation claims share Set D's fixtures. The CLI-harness walker carries
the seam-level proofs.

- **Weights-on-speech parity:** at default weights `dialogue_view` is byte-identical to the (id, score)
  projection of `items` (the loader-turn parity contract).
- **Weights-on-speech re-rank:** an override re-scores the same served set; the seam's view equals a
  recomputation through the pure weight functions, and the prose prompt's `[memories]` block renders in
  the re-ranked order (asserted by ID extraction, never prose).
- **Raw-echo invariance:** `items` stays the untouched retrieval echo under any override; the read path
  has no weights surface.
- **Zero persistence:** a dialogue turn writes nothing; `agents.reputation` stays NULL through
  provisioning and every turn.
- **Degradation rows:** a prose failure pre-token gives the fallback line plus degraded, the served view
  still on the result; a mid-stream drop keeps the partial; never-blank holds.

## Set F: repo hygiene

Two pure scenarios in `tests\test_repo_hygiene.py` (no database, no NLP, about 0.1 s, so they ride the
turn-end subset). Each makes an already-written rule mechanically enforceable, and each exists because
the rule had already been broken once:

- **`test_no_version_gated_syntax_rewrites`:** no file under `app\`, `db\`, or `tests\` uses syntax newer
  than the grammar floor. The canary: ruff's formatter applies PEP 758 when `target-version` is py314 and
  silently rewrites `except (A, B):` across the tree, so `ruff.toml` leaves `target-version` unset. Neither
  `ruff check` nor `ruff format --check` flags it.
- **`test_no_sql_outside_the_db_module`:** `app\db.py` is the only module in `app\` containing SQL (a
  stack constant, and what keeps the injection surface auditable in one file).

## Set G: judge-free eval metrics

Eight scenarios in `tests\test_eval_metrics.py`, in two layers matching the build:

- **Pure arithmetic (5, unmarked, no database):** anchor-cause-aware gist facts (merged-span slices;
  correction anchors sentence-split and owe no detail); the `metric_gist_match_threshold` presence rule;
  honest denominators (empty or unmeasurable denominators return `None`, never a flattering 1.0);
  whole-word fabrication grounding and rate; keyword retention; and the composed-cache-key band parser
  round-tripping `compose_cache_key`.
- **Route contract (3, `nlp`-marked; any 200 runs the spaCy lemma and NER block):** the 200 payload with
  exact ratios against fixture tellings (db-layer writes, never model prose, so the values are byte-known
  and asserting them is structural); a zero-span memory reporting `gist_precision: null`; a 404 on an
  unknown memory; the anchor-cause contract end to end; and the non-perturbation pair (a metrics read
  leaves `/chain` identical, excluding the per-call `total_ms` timing field, and keeps the telling chain,
  reconstruction cache, and identity documents count-stable).

Judged and LLM-graded evaluations do not live in this folder; they arrive with the evaluation runner
([eval-harness.md](eval-harness.md)) as a separate surface. This set is the metric arithmetic and the
route, which are structural.

## Set H: eval runner

Nine scenarios in `tests\test_eval_runner.py` (8 unmarked plus 1 `nlp`): the committed fixture census
canary (fixture drift fails here, not at demo time); scenario-loader strictness (`extra="forbid"`,
backward-only refs, tz-aware timestamps, `path:line` context, duplicate-id rejection); `check_expected`
membership arithmetic; the product-DB hard refusal by name against a TEST-NET host (no dial-out) plus the
`scratch_uri` shim identity; the provision and drop round-trip (migrated to exactly the ledger's set); the
`drift_observer` seam (default `None`, happy path, refusal path, and attaching it perturbs nothing the Set
C floor asserts); and `run_scenarios` end-to-end in-process on scratch settings (`nlp`, driving the real
write pass): report structure, honest-`None` ratios, keyless USD `None`, a JSON-serializable artifact, and
the no-eval-tables proof. Never asserts on prose.

## Set I: the judge layer

Sixteen scenarios in `tests\test_set_i_judge.py` (15 unmarked plus 1 `nlp`), the judge mechanics with the
deterministic fake judge, never judged signal (which is real-mode-only and quotable only past the
agreement bar):

- **The load rule as a regression test:** real mode loads without `TWICETOLD_MODEL_JUDGE` (never in the
  required-roles list); both modes load it when present; judge prices and the `TWICETOLD_JUDGE_MAX_TOKENS`
  knob parse with loud `ConfigError`s.
- **The thinking knob:** value validation (`""` or `"disabled"` only), the exact request-kwargs shapes
  (`""` gives `{}`, the pre-judge call byte-for-byte), and the process-env override allowlist for all three
  keys.
- **Fake-judge determinism** (byte-identical payloads, all four categories validate under the verdict
  models); verdict validation and per-item `judge_failed` degradation (Malformed carries its 7/3 token
  spend, Failing carries zero, the run continues); rubric constants (four categories, unique version tags,
  the JSON-only output contract).
- **Position-swap tie arithmetic** (un-swap, disagreement gives a tie, score averaging); hand-computed
  Cohen's kappa (po 0.7, pe 0.5 gives exactly 0.4; perfect gives 1.0; degenerate marginals and empty inputs
  give honest `None`); Pareto non-domination including `None`-metric incomparability.
- **The `--judged` fake-mode gate** (exit 2 before any provisioning or file access); arm-overlay loading
  (an env-dict merge through `load_settings`; mode, database, key, and judge overrides refused; committed
  arm files as a canary); the gold emit-label-agreement round trip (verdicts stripped, so labels are blind;
  `judge_failed` skipped; hand-filled labels reproduce the hand-computed kappa and the bar's exit codes);
  and the judged fixture census (`judged.jsonl`: 8 scenarios, 24 sf plus 24 abstention, every abstention
  trio carrying a true-premise control for kappa balance).
- **The compare plumbing end-to-end** (`nlp`, scratch settings, fake providers plus fake judge): stamped
  arm blocks, judged summaries including reconstruction-faithfulness on the aged probe's retellings,
  deterministic pairwise verdicts, the Pareto table with honest-`None` USD, a `plumbing_only` label, a
  JSON-serializable report. Never asserts on prose.

## Set K: deferred write processing

Thirteen scenarios in `tests\test_deferred_writes.py` (12 unmarked plus 1 `nlp`); see
[deferred-writes.md](deferred-writes.md). Unmarked scenarios seed pending rows at the db layer
(`Ctx.seed_pending`: NULL write-call scalars, raw text as the `original` head, persisted trigger names)
and exercise the worker through `drain()`, the deterministic entry, with no timers and no spaCy:

- **Completion happy path:** the one-shot NULL-to-value scalar fill, the raw head superseded by the
  `'enrichment'` head, cache evicted, a `completed` run row, and a re-drain that is a 0-row no-op with the
  chain byte-stable (idempotency by the `enrichment_pending` guard).
- **COALESCE proof:** a declared typology stored at insert survives completion untouched.
- **Escalation novelty:** a novel component grows `identity_components` and its mention appends as an
  add-only span, with no fact supersede (novels become components, never memory entities).
- **Retry-later:** a failed write call records a `failed` run row and leaves the row pending; the next
  drain completes it. **Terminal:** the budget-spending attempt fills the row byte-equivalent to the
  synchronous scoring-failed end-state (neutral importance plus `scoring_failed` plus default typology; the
  raw head stays live). **Orphan sweep:** a pending row with a spent budget terminal-fills without model
  calls.
- **Facts-only:** a retelling that superseded the raw head first gives scalars filled, the prose supersede
  skipped, the cache still evicted, `completed_facts_only`.
- **Embedding repair:** a NULL-embedding pending row gains an `'enrichment'` fact version carrying the
  vector; the superseded original stays honestly NULL, `basis_text` byte-verbatim.
- **Anchor set, /chain contract, window reachability:** post-completion `fetch_reconstruction_sources`
  anchors on the enrichment head; the pending flag, attempts, and run log surface on the unscored inspector
  read; a pending row is vector-reachable with true relevance, scores under the neutral fallback, and serves
  raw text verbatim.
- **`salvage_confidence` semantics:** non-numeric or NaN gives None, out-of-range clamps, in-range untouched.
- **End-to-end** (`nlp`): an enabled agent's observe lands pending with honest zero LLM instrumentation,
  then drains to enriched.

The walker `tests\verify_deferred_writes.py` (51 criteria) covers the migration-006 shape, kill-switch
parity, the full ladder at service level, and the worker lifecycle at both construction sites; the
write-path walker staying byte-identical is the deferred-off parity evidence.

## Set L: reflection

Twenty scenarios in `tests\test_reflection.py`, all unmarked; see [reflection.md](reflection.md). Memories
and prior beliefs seed at the db layer; the seam runs through `ReflectionService.reflect` and the worker
through `sweep()`, deterministic, with no timers and no spaCy. The pipeline's time basis is the request's
`client_timestamp`, so the clock freezes by freezing the request:

- **Happy path:** grounded bi-temporal rows at the request's `valid_at` (citations non-empty and a subset
  of the sampled ids), pressure before and after served, honest instrumentation, the re-rendered document
  carrying the identity-relevant belief byte-for-byte; the endpoint writes no run row.
- **Sampling:** deterministic top-k by importance_norm times recency, ties on `memory_id`; a pinned
  ancient row takes the plain decay score and falls out of the sample a `rec = 1.0` arm would have topped.
- **Grounding:** a partial drop stores the valid subset (`dropped_ungrounded` counts); all-ungrounded is
  the 502 class with zero rows; call-failure and malformed land the same way; a genuinely empty conclusion
  list is a valid outcome.
- **The floor:** below `reflection_min_episodes` the 409 class, zero rows; an unknown agent 404.
- **RRR:** a near-duplicate repeat blocks consolidation (even under a `consolidate=true` override) while the
  reflections still store; the threshold pins inert in the scenario isolating the override arm.
- **Consolidation:** absorbs bi-temporally (`invalid_at`, rows stay queryable), provenance is the source
  union, the version bumps, the document carries the belief and not the absorbed rows; `consolidate=false`
  suppresses when due; a consolidation-call failure is soft and the earlier writes stand.
- **Trim:** the three-clause mechanical rule under a frozen clock; the authored (zero-span) and
  active-evidence exemptions hold; 0.0 disables the trim entirely; eviction is per-affected-memory only;
  `fetch_live_components` shrinks; `fetch_reconstruction_sources` drops the pruned spans; no-trim byte
  parity.
- **The dialogue seam:** zero reflections gives a seed-verbatim render and a byte-identical prose prompt;
  after a belief and recompile the `[identity]` block carries it; an unknown `identity_version` stays the
  loud 422 class.
- **The worker:** sweep determinism, the per-agent kill-switch (gates auto-pull only), at most one reflect
  per agent per sweep, pressure consumed by the reflect event, `failed` run rows and natural retry, the
  below-floor skip writing no row, idempotent start and stop.
- **Pressure math:** exact masses including the NULL-importance neutral fallback and the last-event epoch;
  the zero-norm guard is loud, never a clamp.
- **Role shape:** real mode loads without `TWICETOLD_MODEL_REFLECTION`; the first real reflect raises
  `ConfigError` naming the var, nothing written. **Route contracts:** 200, 404, 409, 422, 502 via the
  ASGI-transport pattern.

The walker `tests\verify_reflection.py` (60 criteria, lettered sections A to F) covers the migration-007
shape, the reflect verb ladder, render, consolidation, and dialogue-seam parity, trim plus liveness plus
eviction, the worker lifecycle at both construction sites, and the judge-shaped role surface.

## Set M: the parameter compiler

Twenty-one scenarios in `tests\test_set_m_compiler.py`, all unmarked; see
[parameter-compiler.md](parameter-compiler.md). Beliefs and bundles seed at the db layer; the worker runs
through the never-started factories' `sweep()` (deterministic, no poll loop to race a count) and the
consume side through the dialogue seam with `as_of` pinned:

- **The compile ladder:** the happy-path sweep (missing pairs equal the window times the vocabulary,
  clamped multipliers, namespaced passthrough, one honest run row); pair idempotency (discovery is the
  idempotency); malformed records-with-spend and retries naturally; a hard failure records without spend
  and continues across agents; clamp-at-write plus the namespace filter plus the dropped-keys count.
- **The staleness guard:** `compiler_window_k` bounds discovery and the consume fetch; belief invalidation
  evicts instantly with zero bundle writes and empties discovery; the consolidation N-to-1 collapse kills
  absorbed contributions and the survivor compiles next sweep.
- **Consume:** zero-bundle byte parity (`dialogue_view` equal to the served projection, neutral echo); the
  neutral-bundle license; the per-scene re-rank flip (one agent, two types, opposite recency extremes,
  deterministic regardless of embedding hashes) with membership constant and every view score equal to the
  hand exponent math; override times bundle clamps at the weight ceiling; unknown type log-and-continues
  flagged; a known type selects only its own bundles; newest-bundle-per-pair wins; multi-belief products
  compose exactly; the consume-side re-clamp defense.
- **Lifecycle plus role:** idempotent start and stop, kill-switch skip, the batch cap and the deterministic
  prefix; real mode loads without `TWICETOLD_MODEL_COMPILER`, the worker's first real compile lands a
  `failed` run row naming the var (logged once, worker alive), fake mode builds the deterministic fake; the
  migration-008 pins (columns, CHECK teeth, knob defaults).

The walker `tests\verify_compiler.py` (48 criteria, lettered sections A to F) re-proves it against the
scratch database: the migration-008 shape, the compile ladder, the guard, consume parity and the per-scene
flip, the worker lifecycle at both construction sites, and the judge-shaped role surface. Its module
docstring carries the persistent-scratch rule (a section leaving an enabled agent with uncompiled pairs
flips the kill-switch off, so re-runs stay deterministic).

## Set N: dissonance

Twenty-three scenarios in `tests\test_set_n_dissonance.py`, all unmarked; see architecture.md §8. Memories
seed at the db layer (`ctx.seed`, which grew a `typology` fixture param with this set; the deferred row via
`ctx.seed_pending`); the event runs through `DissonanceService.confront` and the route through
`httpx.ASGITransport`; the retell prose is never asserted (the fake reconstruction provider's output is
checked for presence and distinctness only):

- **The diegetic pair:** both verbs' chain shape (the prior head superseded at t_e, one live head typed by
  verb, the corrections record with verb, new-head FK, and `source_event` round-trip, cache evicted, the
  fact chain and observation byte-untouched, a coherent timeline under windowed SQL).
- **The decision:** pure-function hand math (extremes, the exact tie defending, NULL resolution through
  `importance_neutral`, `dissonance_rigidity_default`, and the typology fallback, every clamp), the
  per-agent knob override flipping the same fixture's verdict, the 0.0 per-side kill-switch shape, and the
  seam echoing every resolved input.
- **The ladder:** 404 unknown or foreign memory (ownership), 409 CAS with rollback proven by row counts,
  422 wire shapes (naive timestamp, unknown typology literal, out-of-range weight), 502 failing and
  malformed retells with nothing written; the route pass-through.
- **Interactions:** pin outranked and inherited (the event proceeds, `memories.pinned` untouched, the new
  head frozen); anchor semantics (update re-anchors, rationalization never); two events stacking heads and
  records; the deferred window (a pending row confronted, then the drain's already-moved guard leaving the
  diegetic head standing, facts-only completion); the fixed-constraint branch (pure assembly); the read-path
  effect (the sanctioned mid-scene change, then byte-identical repeats); and the chain inspector's
  corrections block (present after an event, empty on authorial-only chains).

The walker `tests\verify_dissonance.py` (38 criteria, lettered sections A to E) re-proves it against the
scratch database: the schema shape (corrections columns, CHECK teeth, the fact chain rejecting the diegetic
verbs), the verb ladder with hand math, chain, eviction, and anchor, the read-path effect (including the
session runner's `:confront` core under time travel), and the CAS and error ladder with rollback proof. No
worker exists, so its persistent-scratch discipline is per-run fixture scoping (unique agent names, never a
DB-global count). `verify_reconstruction` owns the fixed-constraint branch.

## Set O: agent state

Ten scenarios in `tests\test_set_o_agent_state.py`, all unmarked. Every fixture is db-layer; the seam is
`RetrievalService.agent_state` service-side and the route over `httpx.ASGITransport`:

- **The ladder plus wire baseline:** 404 unknown agent; 422 on `runs_limit` outside [1, 1000]; a name-only
  agent's wire shape (every nullable scalar present-null in the tri-state, `config` normalized `{}`,
  `identity_version` null, pressure 0.0, four empty lists, the `runs_limit` echo).
- **The gauge:** pressure hand math at the default norm (NULL importance resolving through
  `importance_neutral`), the per-agent norm override rescaling, a reflection event created after the rows
  zeroing it (even an invalidated one, since the epoch is `created_at`), and `norm <= 0` raising the reflect
  verb's ValueError (one rule at both gauges).
- **Beliefs plus bundles:** live-only membership, both `identity_relevant` values, the compiler-window
  order, `source_memory_ids` round-trip; the newest bundle per live pair, a dead belief's bundle excluded
  (liveness derived), nested passthrough verbatim, deterministic order.
- **The run logs:** full migration-007 and migration-008 column mirrors newest-first, present-null
  nullables on failed rows, `runs_limit` capping each list independently.
- **Contract proofs:** identity currency is the newest `identity_documents` row; route JSON equals service
  JSON; zero writes (count snapshots across every touched table unchanged by a read).

The walker `tests\verify_agent_state.py` (26 criteria, lettered sections A to F) re-proves it against the
scratch database and owns the no-migration shape (the agents table exactly its migration-001 columns; the
pre-laid migration-007 and migration-008 agent-id indexes present). Per-run fixture scoping; it runs last in
full sweeps (the newest, elder walkers first). The client-side half of agent state (fire-and-forget observes)
is C# and is covered by the console harness's beats over the wire.

The walker `tests\verify_purge.py` (36 criteria, lettered sections A to H) re-proves the purge against the
scratch database: the seven-table child-before-parent delete in one transaction, the honest per-table
counts, the survival boundary (a co-resident memory, the agent, an identity_component whose only
referencing gist span was purged, and a reflection whose `source_memory_ids` still names the purged memory,
dangling by design), the unknown-id path (None then 404), and the wire contract over `httpx.ASGITransport`
(200 plus counts, 404, 422). Section H re-proves the per-agent verb `DELETE /v1/agents/{id}/memories`: the
summed counts over two full-chain memories, the seven tables empty for both ids, a co-resident agent intact,
the survival boundary widened to a reflection whose every source now dangles plus its bundle and both run
logs, the all-zero outcome for a known agent with nothing left, unknown giving None or `UnknownAgentError`,
and the wire contract (200 plus counts, re-DELETE 200 with zeros, 404, 422, the per-memory verb 404ing on a
bulk-erased id). Id-scoped assertions, never a DB-global count.

The walker `tests\verify_provider_path.py` (41 criteria, lettered sections A to H) re-proves the
OpenAI-compatible provider path offline and keyless: the real provider classes driven against canned
in-process HTTP handlers (`tests\provider_transport.py`, an `httpx.MockTransport` injected as the SDK
clients' `http_client`): the config matrix (A), the offline wiring of the bundle and the lazy factories on
both backends (B), the openai backend's request shape and round-trip per role (C), streaming, usage-absent,
the pre-first-chunk versus mid-stream error contracts, and the small-model hardening (D), the Anthropic
backend's request-shape pins so the seam move is provable (E), the embedding width fit (pad, pass, refuse)
plus tokens and client selection (F), a served dialogue turn over `httpx.ASGITransport` with mock-backed
real providers, content byte-identical to the canned chunks (G), and the named failure mode made
structural: a small model's empty output landing as `scoring_failed` through the ingest ladder (H, the one
section that pays the NLP load). Only G and H touch the scratch database.

## Set Q: the provider path

`tests\test_set_q_provider_path.py`, 28 scenarios, all unmarked, no database: the real provider classes run
against canned in-process HTTP handlers (`tests\provider_transport.py`, request-recording
`httpx.MockTransport` handlers in the exact wire shapes the SDKs parse: the OpenAI chat completion as JSON
and as SSE with a trailing usage chunk, the OpenAI embeddings list in the SDK's default base64 float32
encoding, the Anthropic message as JSON and as the six-event SSE sequence; error fixtures are 4xx only,
because both SDKs retry 5xx, 408, 409, and 429 with backoff sleeps). Offline and keyless holds: no socket
is ever opened.

- **The config matrix** (9): the defaults (no new var gives anthropic byte-for-byte); the selector enum
  validated in both modes and case-folded; openai needs an http(s) base URL (trailing slash stripped),
  never an Anthropic key, the model key optional and off the repr; a base URL or key under anthropic is
  loud; the dialogue-thinking knob is refused under openai; the token-limit-field knob (defaulted on unset
  and empty, case-folded, enum-loud in both modes, `max_completion_tokens` refused under anthropic while an
  explicit `max_tokens` there is harmless); the embedding knobs are independent (a base URL lifts
  `OPENAI_API_KEY`, key-without-URL and a non-http URL are loud, the model name overrides, and the anthropic
  backend plus a routed embedding is a legal mix); fake mode loads the selector with no URL and no key; all
  seven new keys ride the process-env override allowlist.
- **The openai backend** (10): the write call's request shape (path, bearer placeholder, system plus user
  messages, `max_tokens` 1024, `response_format=json_object`, no stream, thinking, or sampling) and every
  `WriteCallResult` field with the fixture usage; with the knob at `max_completion_tokens` the per-role
  value rides that field on both call paths and `max_tokens` is absent; every JSON role round-trips its
  dataclass with its per-role `max_tokens`; usage absent gives 0/0 plus exactly one warning; null, empty,
  non-JSON content and an empty choices list give `MalformedOutputError` carrying the spend; 400, 401, and
  404 give the pinned `ProviderCallError`; the small-model hardening survives (clamp, salvage, fenced JSON);
  the dialogue stream yields the fixture chunks byte-identically with usage from the trailing chunk and
  `stream_options.include_usage` on the wire; the pre-first-chunk versus mid-stream error contracts.
- **The Anthropic backend, pinned** (2): the write request is exactly `{model, max_tokens, system,
  messages:[user]}` on `/v1/messages` with `x-api-key` and no `response_format`; the judge adds
  `thinking: adaptive` and nothing else; the streaming fixture round-trips with the knob unset (no thinking
  key) and `disabled` (thinking-off).
- **The embedding path** (2): exactly 1536 passes with `model`, `dimensions=1536`,
  `encoding_format=base64`, and `input` on the wire; 768 is zero-padded (prefix intact, zeros beyond, one
  warning); 2560 is refused naming the model, the width, and the lock; usage absent gives 0 plus one
  warning; a float-list server still lands; client selection (hosted `OPENAI_API_KEY` at `api.openai.com`, a
  base URL without a key gives the placeholder, a base URL with a key gives that key).
- **Offline wiring** (1): real-mode construction opens no socket on either backend; the bundle's four LLM
  roles share one backend object; the judge-shaped factories build real classes on openai without an
  Anthropic key; fake mode ignores the selector.

The warn-once register is process-global; scenarios that count warnings clear it first.

## Route contracts

Every route in `app\api.py` has at least one HTTP-level scenario asserting its success payload, and most
also assert their mapped error statuses, because the C# client depends on both. They live wherever their
fixtures do: mostly `tests\test_set_d_gate.py` (via `httpx.ASGITransport`), with init in
`test_set_b_decay.py`, correction in `test_set_a_correction.py`, the NER-502 row in `test_degradation.py`,
and the walkers' own route sections.

- `POST /v1/dialogue/init` (404, 422) and `POST /v1/dialogue/turn` (route JSON equal to the drained seam
  result; 404, 422)
- `POST /v1/dialogue/turn/stream` (200 `text/event-stream`; chunk events concatenate byte-identically to
  the result's content; `reconstructing` fires once before any chunk on a gated turn with a blocking
  retelling; a post-first-chunk failure arrives as an `error` event, since a 200 stream cannot change
  status; pre-stream 404)
- `POST /v1/events/observe` and `POST /v1/events/scene-boundary` (accepted plus identity_version; 404)
- `PUT /v1/memories/{id}/pin` (the row moves both directions; 404) and `POST /v1/memories/{id}/correction`
  (404, 409, 422, 502)
- `DELETE /v1/memories/{id}` (the purge verb: 200 plus honest per-table counts, the memory gone; 404
  unknown; 422 malformed id), in `tests\test_set_p_purge.py` plus the `verify_purge` route section
- `DELETE /v1/agents/{id}/memories` (the per-agent purge verb: 200 plus summed counts with
  `memories_deleted`, every memory gone; a re-DELETE 200 with zeros; 404 unknown agent; 422 malformed id),
  in `tests\test_set_p_purge.py` plus `verify_purge` section H
- `POST /v1/agents` (server-minted UUID, NULL knobs resolve; 422 on empty name)
- `GET /v1/memories/{id}/chain` and `GET /v1/agents/{id}/memories` (unscored by contract; superseded rows
  present; 404) and `GET /ledger`
- `GET /v1/memories/{id}/reconstruction-metrics` (IDs plus counts plus ratios, honest-`None` denominators,
  zero writes; 404), in `tests\test_eval_metrics.py`
- `GET /v1/agents/{id}/state` (unscored by contract; the stored row as stored, present-null tri-state,
  route JSON equal to service JSON, zero writes; 404, 422 on `runs_limit` bounds), in
  `tests\test_set_o_agent_state.py`

## Degradation cases

- Importance-scoring model failure: the write still lands, with neutral importance and a `scoring_failed`
  flag.
- Unknown `decay_class` label: the write still lands, with the agent's default class and
  `decay_class_unknown = true`, never rejected (it mirrors `scoring_failed`).
- Embedding-call failure: the write still lands with a NULL embedding; `embedding IS NULL` is the queryable
  signal and the payload carries `embedding_failed`; the signal's home is the live fact head
  (`memory_fact_versions.embedding IS NULL`).
- Embedding-call failure during an authorial correction: all-or-nothing, so nothing is written on either
  chain, the cache is intact, and the error is loud (the deliberate contrast with the observe path's
  land-with-NULL degradation; architecture.md §8).
- NER failure during an authorial correction: all-or-nothing, same shape, since the NER runs before the
  embed and before the transaction, so nothing lands on either chain and the cache is untouched;
  `CorrectionNlpFailedError` gives 502.
- Escalation call fails twice: soft-degrade, so the write lands with the base NLP-pass gist and
  `escalation_failed = true` (result plus the dedicated column, migration 005), structurally assertable as
  a row present plus the flag set.
- Gate degradation ladder: embeddings down gives an entity-only lexical fetch; no entities gives
  novelty-only; both out gives a closed gate, the loaded set served, fail-quiet (the lexical fetch reads the
  post-migration-003 fact-head entities GIN; [mid-dialogue-gate.md](mid-dialogue-gate.md)).
- Malformed model responses: log, ignore, the turn succeeds.
