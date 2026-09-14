# The evaluation harness

The measurement instrument for the demo and for judging the system's behavior: a judge-free metric
layer feeding The Ledger's on-screen numbers, an evaluation runner driving Insert/Query scenarios over
the existing session-runner loop, an LLM-judge layer with a hand-labeled gold set, and a fixed-gist
ON/OFF ablation. The demo-legibility artifact and the faithfulness evaluation are the same artifact, and
the judge surface is designed in from the start rather than bolted on later.

## The measured shape

- **A judge model role that is eval-runner-only.** `TWICETOLD_MODEL_JUDGE` sits beside the structural
  scenarios, but the server and REPL real-mode required list does not include it: `load_settings` never
  requires the judge var, and the runner validates it itself when a judged run starts. The judge provider
  is deliberately not a field on the frozen `Providers` bundle. Judged signal is meaningful only in real
  provider mode, and the reports make that mechanical (`plumbing_only` labels under fake mode).
- **Judged categories: the core three plus prose quality.** Selective-forgetting (single- and multi-hop,
  the MemoryAgentBench shape), abstention and false-premise (the LongMemEval premise-awareness rubric),
  reconstruction-faithfulness (a retargeted LoCoMo FactScore: gist-precision expected near 100%,
  detail-recall allowed to decay), plus a prose-quality pairwise rubric for model-versus-model
  comparisons.
- **A judge-free metric layer.** Gist-precision and detail-recall from the existing gist spans plus spaCy
  lemmas, with no judge call; binned by decay band via the reconstruction cache's composed key; a
  fabrication rate (retelling entities absent from every ground text); and keyword retention. These feed
  The Ledger's on-screen numbers.
- **The Ledger binding is a small read route.** `GET /v1/memories/{id}/reconstruction-metrics`, computed
  server-side (lemmas need spaCy). It runs no retrieval, so the IDs-and-scores invariant does not bind; it
  returns IDs plus numbers and performs zero writes.
- **A hand-labeled gold set.** The runner emits gold candidates from a run, a human labels a small set,
  and the runner reports judge-agreement (raw percentage plus Cohen's kappa). Judged numbers are quotable
  only once agreement clears the bar (kappa at least 0.6 per category).
- **A fixed-gist ON/OFF ablation.** The same seeded set, bands, model, and drift budget, with the gist
  constraint in versus removed; gist-precision and fabrication rate per arm, with per-item cosine drift
  shown near-identical in both arms (the budget-is-blind proof).
- **No new migration.** Scenarios, gold sets, and corpora are repo files under `data\eval\`; run
  artifacts are JSON files; nothing evaluation-related persists in Postgres. Runs use disposable
  pid-scoped scratch databases and never connect to the product `twicetold`.

## Principles

- **One metric implementation, three consumers.** The metrics are pure functions in
  `app\eval_metrics.py`, consumed by the API route (The Ledger), the evaluation runner, and the test
  suite. No divergent second computation anywhere.
- **Judged evaluations stay out of `tests\`** ([test-suite.md](test-suite.md)). Pure metric arithmetic
  over fixed inputs is structural and lives in the suite; anything judged or LLM-graded lives in the
  runner and its artifacts.
- **Instrument at the seam.** The metrics route reports `metrics_ms` (the spaCy plus arithmetic block)
  inside `total_ms`; the runner accounts judge tokens and USD per run with the prices-optional-to-`None`
  pattern.
- **Nothing integrator-configurable is hardcoded.** The gist match rule is the
  `metric_gist_match_threshold` knob (the `agent_knob` contract); rubric texts carry `rubric_version`
  tags; paths and caps are CLI arguments.
- **Honest denominators.** Every ratio returns `None` on an empty denominator: a memory with zero
  measurable gist facts reports `gist_precision: null`, never a flattering 1.0.

## Boundaries

There is no NLI model on gist sentences (the presence plus chain-diff floor stands); no FAMA
stale-leakage or MemTrace trajectory categories (they queue behind the core four); no DB-persisted
evaluation state; and no metric check at cache-write time. Held-out scenarios (`"held_out": true`) are
excluded from tuning and compare runs by default.

## The judge-free metrics (`app\eval_metrics.py`)

The exact rules, all pure and assertable without a database:

- **Gist facts.** One fact per merged gist span (`reconstruction.merge_spans`, the same merge
  reconstruction's constraint uses), sliced from the immutable `observation_text`. On an
  `authorial_correction`-anchored chain the anchor content is the fixed facts (mirroring
  `build_reconstruction_item`): the corrected head, sentence-split by the same deterministic splitter
  reconstruction thins with. A fact whose content-lemma set is empty (for example a bare pronoun coref
  span) is unmeasurable: excluded from both numerator and denominator, flagged `None` in the per-fact
  presence list.
- **Gist-precision** = measurable facts whose content lemmas appear in the live telling's lemma set
  (per-fact: `|fact intersect telling| / |fact| >= metric_gist_match_threshold`, default 1.0, strict
  lexical, since paraphrase slack belongs to the judged faithfulness category), divided by measurable
  facts. `None` at zero measurable facts.
- **Detail-recall** = `|detail intersect telling| / |detail|`, where detail is the content lemmas of the
  between-span remainders (`reconstruction.split_gist_detail`) minus the gist lemma union (detail never
  gets credit for words the gist already carries). Empty (`None`) on correction-anchored chains, since no
  observation detail was re-injected and none is owed.
- **Content lemmas** = `nlp.lemma_content_set(text)`: lowercased `token.lemma_` for tokens that are not
  stop, punct, or space, byte-for-byte the write pass's Warriner token filter, promoted public.
- **Fabrication** = telling entities (`nlp.extract_entities`, the write pass's NER mirror) found in none
  of the observation text, the rendered identity document, or the anchor content (`nlp.find_term_spans`,
  the same whole-word matcher the gate's tripwire uses). `fabrication_rate = fabricated / telling
  entities`, `None` at zero telling entities.
- **Keyword retention** = the fraction of the observation's NER entities still present (whole-word) in
  the live telling. `None` at zero observation entities.
- **Band binning** = `band_from_composed_key` parses the `|b<N>` tail of the reconstruction cache's
  composed key (`compose_cache_key`); the route reports the bands observed in this memory's cache rows,
  with no decay math re-run.

## The route

`GET /v1/memories/{memory_id}/reconstruction-metrics` returns `ReconstructionMetricsResult`
(pass-through by the house rule; 404 on an unknown memory). The service method lives beside the inspector
reads (`RetrievalService.reconstruction_metrics`): `fetch_memory_chain` plus
`fetch_reconstruction_sources` (the anchor) plus `fetch_agent` then `render_identity_document` (the pure
render, never the `ensure_` upsert) plus the read-only `db.fetch_cache_keys`. The spaCy work runs in a
worker thread. The scoring target is the live telling head only; a chain with no live head reports counts
with every ratio `None`. Zero writes, proven by the suite's non-perturbation pair.

The payload carries `memory_id`, `agent_id`, `live_detail_id?`, `live_write_cause?`, `anchor_cause?`,
`gist_facts_total/present` plus `gist_precision?`, `detail_lemmas_total/present` plus `detail_recall?`,
`telling_entities[]`, `fabricated_entities[]` plus `fabrication_rate?`, `keyword_retention?`,
`cache_bands[]`, `metrics_ms`, and `total_ms`. It is mirrored field-for-field in the C# core with one
interop-gate check.

The Ledger's `renderChainFor` additionally fetches the metrics route and renders gist-precision,
detail-recall, and the fabricated-entity count beside the four existing counts; a metrics fetch failure
never hides the chain, since the metric is additive to the record, not part of it.

## The runner (`app\eval_runner.py`)

`app\scratch_db.py` holds `scratch_uri` plus `provision_scratch` and `drop_scratch` (CREATE, the
`db\migrate.py` subprocess, and drop; with a hard refusal when the resolved dbname is the product
`twicetold`). `app\eval_scenarios.py` is a pydantic scenario schema plus a JSONL loader (events: observe,
utterance, scene, correct, pin, as_of, context; `memory_ref` is an ordinal index into the scenario's
observes, resolved via `IngestResult.memory_id`), with `extra="forbid"` and tz-aware datetime validators
so an authoring mistake dies at load with a `path:line` context, never mid-run.

`python -m app.eval_runner` verbs:

- **`run`**: scratch database, then an agent, then events through `SessionRunner`, then queries, then the
  judge-free metrics plus structural expected-IDs checks, writing a run JSON under `data\eval\runs\`
  (gitignored) plus stdout tables. Exit 0 if checks green, 1 if any failed.
- **`drift-validate`**: real-embedding per-item drift versus `drift_budget_threshold`, reporting p50,
  p95, max, and the over-budget count. Exit 0 under budget, 1 over, 2 on a mode-gate refusal. The corpus
  is a subset of the scenario schema (observe and as_of only), so one loader serves both.
- **`agreement`**: raw percentage plus Cohen's kappa per category against a labeled gold set, with an
  `--kappa-bar` defaulting to 0.6; an undefined kappa (degenerate marginals) honestly fails the bar.
- **`compare`**: an A/B over two env overlays. A compare arm is a JSON file (`{"name", "env"}`) whose
  overlay may carry the six role vars, the thinking knob, and prices; mode, database, API keys, and the
  judge are refused, because an arm varies the system under test, never the instrument, and each arm
  carries its own dialogue prices. Prose is judged pairwise with a position-swap (disagreement gives a
  tie, per-arm scores averaged over both positions). The report is a Pareto table (accuracy versus
  `perceived_first_word` p50/p95 versus USD per 100 turns, non-dominated rows marked).
- **`emit-gold`**: emits gold candidates from a run (`--limit-per-category` defaults to 30), stripping
  verdicts so labels are blind (`item_id` joins back to the artifact) and skipping `judge_failed` items.
- **`judge-gold`**: judges gold-shaped rows fresh, rows authored with labels known by construction
  (perturbed tellings, premise-swallowing replies, and their faithful or correct counterparts,
  class-balanced by design), and writes an artifact-shaped JSON that `agreement` scores. This measures
  judge discrimination on known cases, which closes the degenerate-marginals gap when the system under
  test rarely fails. A present `label` is never shown to the judge.
- **`ablation`**: two arms on separate scratch databases (arm B's agent config carries the constraint
  knob at 0.0), capturing per-item drift and reporting paired `(memory_id, band, distance_on,
  distance_off)` plus arm summaries plus mean paired absolute delta beside gist-precision and fabrication
  per arm.

`app\reconstruction.py` carries the capture seam: a module attribute `drift_observer: Callable[[UUID,
float, bool], None] | None = None`, invoked per checked item at the distance computation, with a `None`
default giving byte-identical behavior. Its third argument is `refused` (`distance > threshold`, computed
where the serving decision is made; the blind embed-failure refusal path carries no distance and never
calls the observer).

## The judge layer (`app\eval_judge.py`)

Config: `ENV_MODEL_JUDGE`, `TWICETOLD_PRICE_JUDGE_IN/OUT`, and `Settings.model_judge` loaded in both
modes but absent from the real-mode required list. Providers: `FakeJudgeProvider` (deterministic hash
verdicts, plumbing only) and `RealJudgeProvider` (adaptive thinking, no sampling parameters, a bounded
`TWICETOLD_JUDGE_MAX_TOKENS` knob defaulting to 2048, `MalformedOutputError` with token accounting),
built through the standalone `build_judge_provider(settings)`.

The judge model is an Opus-class model rather than a sonnet-class one, so it grades neither arm's class
when comparing sonnet-class against haiku-class prose (a sonnet-class judge would self-grade the sonnet
arm). The Opus-class API rejects `temperature`, `top_p`, and `top_k` outright, so the judge call runs
adaptive thinking with no sampling parameters and the rubric's JSON-only output contract carries
determinism instead.

Rubric constants live in `RUBRICS` with `rubric_version` tags (sf-v1, abst-v1, rf-v1, pp-v1). The
prose-quality rubric scores naturalness, character-consistency, memory-grounding, and brevity, each 1 to
5, plus an overall a/b/tie preference, position-swapped. Faithfulness judges only memories whose
`live_write_cause` is `reconstruction` (anything else is counted `skipped_not_reconstructed`, never
silently judged) and sees all merged-span gist facts with no lemma-measurability filter (that filter is a
lexical-metric artifact; the judge does semantic support). Verdicts are pydantic-validated, with per-item
`judge_failed` degradation. `--judged` is refused in fake mode without `--plumbing`. Judged outcomes
never change `run` or `compare` exit codes (0 and 1 stay structural-checks-only; 2 is a gate refusal),
and judged numbers are quotable only past the agreement bar.

## The ablation

`SERVICE_DEFAULTS["reconstruction_gist_constraint"] = 1.0` is a kill-switch read via `agent_knob` inside
serve() (no signature change). When 0.0, gist is blanked on original-anchored items and
`assemble_reconstruction_prompt(..., include_gist_constraint=False)` drops the `"gist"` key and swaps
`_SYSTEM_TASK` for `_SYSTEM_TASK_NO_GIST`. Correction-anchored chains are excluded from ablation arms,
because their gist slot is the corrected head and blanking it would delete the correction, a different
experiment; at runtime a knob-0 correction-anchored miss still reconstructs normally, so serve()
partitions the call slots into a no-gist group and a normal group. The paired report keys on
`(scenario_id, memory_ref)`, since per-arm memory UUIDs differ across scratch databases. The knob is
deliberately not in `compose_cache_key` (arms live on separate scratch databases, and a live mid-process
flip could serve stale-keyed text), so it is flipped at provisioning boundaries, never mid-scene.

The ablation is the deciding data for whether the drift budget should also police facts. The empirical
finding is that the budget is blind to the constraint (per-item drift is near-identical with the
constraint in or out) while gist-precision drops materially when the constraint is removed. The
conclusion: the budget keeps its mechanism and threshold and is a topic guard, and fact-policing belongs
to gist-precision plus the judged faithfulness category.

## Verification

- Given a memory with gist spans and a live head, the route returns 200 with IDs, counts, and the three
  ratios, and 404 on an unknown memory id.
- Given fixed inputs, the metric arithmetic is exact: presence honors the threshold knob; empty
  denominators return `None`; correction-anchored chains score against the anchor and owe no detail; the
  band parser inverts `compose_cache_key`.
- A metrics read leaves the record unperturbed: `/chain` is byte-identical before and after, and zero
  rows are added to `memory_details` or `reconstruction_cache`.
- The Ledger renders the metric numbers beside the four counts on a real reconstructed chain, and a
  metrics failure does not hide the chain.
- The C# mirror deserializes the payload through the live interop gate.
- The suite is green, `verify_read_path.py` and `verify_reconstruction.py` re-run green, ruff is clean,
  and an independent verification passes.
