# Judged eval harness v1 — build target (specced 2026-07-29)

The measurement instrument for the demo and the paper: a judge-free metric layer feeding The
Ledger's on-screen numbers, an eval runner driving Insert/Query scenarios over the existing
session-runner loop, an LLM-judge layer with a hand-labeled gold set, and the fixed-gist ON/OFF
ablation that produces R7's deciding data. Pulled pre-demo by the 2026-07-22 ruling ("the
demo-legibility artifact and the faithfulness eval are the same artifact"); the judge surface
designed in from v1 by the 2026-07-20 ruling (structural-first-judge-later rejected).

**Build stages (one session, one floor each):** stage 1 = this spec + the judge-free metric
layer + the Ledger metrics route. Stage 2 = the eval runner core + scratch provisioning + drift
capture + `drift-validate`. Stage 3 = the judge layer + rubrics + gold emission + A/B-Pareto.
Stage 4 = the ablation rig + meta-eval closure. Later-stage sections here are contract, not yet
build receipts; each stage gains its own dated BUILT banner.

**BUILT (stage 1) — 2026-07-29.** The judge-free metric layer + the reconstruction-metrics
route + The Ledger binding landed and floor-verified the same day this spec was written
(plan-as-spec session). See the Done-when for what was proven.

**BUILT (stage 2) — 2026-08-05.** The runner core landed to the stage-2 contract paragraph
verbatim and floor-verified (the twenty-second `floors.md` row; session rulings + build
latitude in the dated `decisions.md` entry): `app\scratch_db.py` (the promoted
`scratch_uri` + pid-scoped `provision_scratch`/`drop_scratch`), `app\eval_scenarios.py`
(strict schema + the one loader), `app\eval_runner.py` (`run` + `drift-validate`), the
`drift_observer` seam, fixtures under `data\eval\`, suite Set H. The ruled single real-mode
`drift-validate` on the fixture corpus (7 authored observes, aged 30 days, threshold 0.35):
**7/7 items checked, 0 over budget — distance p50 0.030 / p95 0.100 / max 0.120**,
`drift_refusals` self-check exact. Fake-mode e2e: 6/6 expected-IDs checks, byte-identical
across runs.

**BUILT (stage 3) — 2026-08-07.** The judge layer landed to the stage-3 contract paragraph
with one dated API-forced correction (adaptive thinking / no sampling parameters in place of
the unimplementable "temperature 0" — see the contract paragraph) and floor-verified (the
twenty-third `floors.md` row; the four plan-approval rulings — **Opus 4.8 judge**, the
thinking knob built now, the smoke+gold sequencing, the three spec knobs as recommended —
plus build latitude in the dated 2026-08-07 `decisions.md` entry). The ruled single real
judged smoke (`run --judged` over `smoke.jsonl` + `judged.jsonl`: 12 scenarios, 62 turns,
44 observes, 0 degraded, 6/6 structural checks, total spend **≈ $0.58** of the $2 budget,
judge $0.398 at 36,784/8,574 tokens): **0 `judge_failed` across all 78 verdict items** —
selective-forgetting 18/24 pass, abstention 23/24, reconstruction-faithfulness 88/89 facts
supported with **63 fabricated-claim flags** (7 never-reconstructed memories honestly
skipped). *These judged readings are pre-agreement — quotable only once Jack's gold labels
clear the kappa ≥ 0.6 bar (fork 5); the structural and cost numbers are quotable now.* The
instrument's reason-to-exist showed up in its first run: strict-lexical gist-precision read
**0.765** where the judge's semantic support read **0.9888** (the paraphrase-slack gap the
spec predicted), and the judge flagged 63 embellishment claims where the lexical
entity-detector saw 2. Gold candidates emitted blind to
`data\eval\gold\candidates-2026-08-07.jsonl` (78 rows: 24/24/30, fact candidates capped at
30 of 89); `agreement` + the first real `compare` (haiku vs sonnet-5 ± thinking-off, the
queued 2026-07-29 deferral) open the next session once labels exist.

## The ruled shape

1. **Judge model role from v1** (ruled 2026-07-20): `TWICETOLD_MODEL_JUDGE` + judged categories
   beside the structural scenarios; judged signal is only meaningful in real provider mode, and
   the reports make that mechanical (`plumbing_only` labels under fake mode).
2. **Judge role is eval-runner-only** (ruled 2026-07-29 at plan approval): the server/REPL
   real-mode required list is untouched — `load_settings` does NOT require the judge var; the
   eval runner validates it itself when a judged run starts. The judge provider is deliberately
   NOT a field on the frozen `Providers` bundle. *(Corrected in place 2026-08-07: this entry
   originally said "stays seven-role" — written before the A1 re-shape removed the `behavior`
   role on 2026-08-04. Real mode requires SIX roles; the ruling's substance — judge never among
   them — is unchanged. The Set I config regression test asserts exactly that.)*
3. **v1 judged categories = core 3 + prose quality** (ruled 2026-07-29): selective-forgetting
   (single/multi-hop, MemoryAgentBench 2507.05257 shape), abstention/false-premise
   (LongMemEval 2410.10813 / LME-V2 2605.12493 premise-awareness rubric), reconstruction-
   faithfulness (LoCoMo 2402.17753 FactScore **retargeted**: gist-precision expected ~100%,
   detail-recall allowed to decay), plus a **prose-quality pairwise rubric** — the deferred
   instrument for the sonnet-5-vs-haiku and B2 thinking-off re-assessments (ruled 2026-07-29;
   **discharged 2026-08-12** — both compares ran and Jack re-ruled HAIKU on latency, the
   dated entry in `decisions.md`).
   FAMA stale-leakage and the MemTrace trajectory probe are deferred (scope boundary).
4. **Judge-free metric layer** (ruled 2026-07-22): gist-precision / detail-recall from existing
   gist spans + spaCy lemmas — no judge call; binned by decay band via the reconstruction
   cache's composed key; fabrication rate (retelling entities absent from every ground text);
   keyword retention (2511.10277). These feed The Ledger's on-screen numbers.
5. **Ledger binding = a new small read route** (ruled 2026-07-29):
   `GET /v1/memories/{id}/reconstruction-metrics`, computed server-side (lemmas need spaCy).
   The two existing inspector reads' unscored-by-contract wording is untouched. The new route
   runs no retrieval, so the IDs-and-scores invariant does not bind; it returns IDs + numbers
   and performs **zero writes**.
6. **Hand-labeled gold set** (ruled 2026-07-22): the runner emits gold candidates from a run,
   Jack labels a small set, the runner reports judge-agreement (raw % + Cohen's kappa) —
   judged numbers are quotable only past the agreement bar (fork 5).
7. **Fixed-gist ON/OFF ablation** (ruled 2026-07-22) — R7's deciding data: same seeded set /
   bands / model / drift budget with the gist constraint IN vs REMOVED; gist-precision +
   fabrication rate per arm, with per-item cosine drift shown near-identical in both arms (the
   budget-is-blind proof). Any drift-metric/threshold change waits on this data (R7 stays open
   until then).
8. **No new migration** (ruled 2026-07-29, the explicit per-target scope fact): scenarios, gold
   sets, and corpora are repo files under `data\eval\`; run artifacts are JSON files; nothing
   eval-related persists in Postgres. Runs use disposable pid-scoped scratch DBs and never
   connect to the product `twicetold`.
9. **Harness shape** (queue item 3): Insert/Query over the existing `SessionRunner` loop;
   accuracy-vs-latency Pareto reporting; plus the early-runnable real-embedding
   **drift-validation verb** (audit addition iv) so the demo-corpus validation is a command,
   not a build, when the choreography task lands.

## Principles this build honors

- **One metric implementation, three consumers.** The metrics are pure functions in
  `app\eval_metrics.py`, consumed by the API route (The Ledger), the eval runner (stage 2+),
  and the suite. No divergent second computation anywhere.
- **Judged evals stay out of `tests\`** (test-suite.md). Pure metric *arithmetic* over fixed
  inputs is structural and does live in the suite; anything judged or LLM-graded lives in the
  runner and its artifacts.
- **Instrument at the seam.** The metrics route reports `metrics_ms` (the spaCy + arithmetic
  block) inside `total_ms`; the runner (stage 2+) accounts judge tokens and USD per run with
  the prices-optional → `None` pattern.
- **Nothing integrator-configurable is hardcoded.** The gist match rule is the
  `metric_gist_match_threshold` knob (agent_knob contract); rubric texts carry
  `rubric_version` tags; paths and caps are CLI arguments.
- **Honest denominators.** Every ratio returns `None` on an empty denominator — a memory with
  zero measurable gist facts reports `gist_precision: null`, never a flattering 1.0 (the
  thin-gist lesson, 2026-07-23).

## Scope boundary — do NOT build

- No NLI model on gist sentences (explicitly deferred to the research phase by the audit
  solutions doc); the presence + chain-diff floor is v1.
- No FAMA stale-leakage or MemTrace trajectory categories in v1 (ruled 2026-07-29) — they queue
  behind the core four.
- No reflection, no migration, no DB-persisted eval state, no CI workflow changes.
- No pre-warm build and no metric check at cache-write time (R8 rides the post-demo pre-warm).
- The demo corpus itself arrives with the choreography task; stage 2 ships `drift-validate`
  proven against a fixture corpus, and held-out scenarios (`"held_out": true`) are excluded
  from tuning/compare runs by default.

## Mechanism — stage 1 (BUILT)

### The judge-free metrics (`app\eval_metrics.py`)

Definitions (the exact rules; all pure, walker/suite-assertable without a database):

- **Gist facts.** One fact per **merged** gist span (`reconstruction.merge_spans` — the same
  merge reconstruction's constraint uses), sliced from the immutable `observation_text`. On an
  `authorial_correction`-anchored chain the anchor content **is** the fixed facts (mirroring
  `build_reconstruction_item`): the corrected head, sentence-split by the same deterministic
  splitter reconstruction thins with. A fact whose content-lemma set is empty (e.g. a bare
  pronoun coref span) is **unmeasurable** — excluded from both numerator and denominator,
  flagged `None` in the per-fact presence list.
- **Gist-precision** = measurable facts whose content lemmas appear in the live telling's lemma
  set (per-fact: `|fact ∩ telling| / |fact| >= metric_gist_match_threshold`, default 1.0 —
  strict lexical; paraphrase slack belongs to the judged faithfulness category) ÷ measurable
  facts. `None` at zero measurable facts.
- **Detail-recall** = `|detail ∩ telling| / |detail|` where detail = the content lemmas of the
  between-span remainders (`reconstruction.split_gist_detail`) **minus** the gist lemma union
  (detail never gets credit for words the gist already carries). Empty (`None`) on
  correction-anchored chains — no observation detail was re-injected, so none is owed.
- **Content lemmas** = `nlp.lemma_content_set(text)`: lowercased `token.lemma_` for tokens that
  are not stop/punct/space — byte-for-byte the write pass's Warriner token filter, promoted
  public (the `extract_entities` precedent).
- **Fabrication** = telling entities (`nlp.extract_entities`, the write pass's NER mirror)
  found in **none** of: the observation text, the rendered identity document, the anchor
  content (`nlp.find_term_spans` — the same whole-word matcher the gate's tripwire uses).
  `fabrication_rate = fabricated / telling entities`, `None` at zero telling entities.
- **Keyword retention** (2511.10277) = fraction of the observation's NER entities still present
  (whole-word) in the live telling. `None` at zero observation entities.
- **Band binning** = `band_from_composed_key` parses the `|b<N>` tail of the reconstruction
  cache's composed key (`compose_cache_key`) — the ruled binning source; the route reports the
  bands observed in this memory's cache rows, no decay math re-run.

### The route

`GET /v1/memories/{memory_id}/reconstruction-metrics` → `ReconstructionMetricsResult`
(pass-through by ruling; 404 unknown memory, the `/chain` shape). The service method lives
beside the inspector reads (`RetrievalService.reconstruction_metrics`): `fetch_memory_chain` +
`fetch_reconstruction_sources` (the anchor) + `fetch_agent` → `render_identity_document`
(**pure render — never the `ensure_` upsert**) + the new read-only `db.fetch_cache_keys`.
spaCy work runs in a worker thread (the serve() pattern). Scoring target is the **live telling
head only** (fork 6); a chain with no live head reports counts with every ratio `None`
(the degraded-path precedent). **Zero writes** — proven by the suite's non-perturbation pair.

Payload: `memory_id`, `agent_id`, `live_detail_id?`, `live_write_cause?`, `anchor_cause?`,
`gist_facts_total/present` + `gist_precision?`, `detail_lemmas_total/present` +
`detail_recall?`, `telling_entities[]`, `fabricated_entities[]` + `fabrication_rate?`,
`keyword_retention?`, `cache_bands[]`, `metrics_ms`, `total_ms`. Mirrored field-for-field in
`client\NpcMemory.Core\Models.cs` (fork 1: mirror — 31 → 32 wire models) with one
interop-gate check.

### The Ledger

`renderChainFor` additionally fetches the metrics route and renders gist-precision,
detail-recall, and the fabricated-entity count beside the four existing counts; a metrics
fetch failure never hides the chain (the metric is additive to the record, not part of it).
Footer updated: the binding promise is now the binding.

## Mechanism — stages 2–4 (contract)

- **Stage 2 — runner core. BUILT 2026-08-05** (banner above; built to this paragraph
  verbatim). `app\scratch_db.py` promotes `tests\scratch_uri.py` (re-export
  shim keeps conftest + all seven walkers byte-untouched) and adds `provision_scratch` /
  `drop_scratch` (CREATE + `db\migrate.py` subprocess + drop; hard refusal when the resolved
  dbname is the product `twicetold`). `app\eval_scenarios.py` = pydantic scenario schema + JSONL
  loader (events: observe / utterance / scene / correct / pin / as_of / context; `memory_ref`
  = ordinal index into the scenario's observes, resolved via `IngestResult.memory_id`).
  `app\eval_runner.py` (`python -m app.eval_runner`) verbs: `run` (scratch DB → agent →
  events through `SessionRunner` → queries → judge-free metrics + structural expected-IDs
  checks → run JSON under `data\eval\runs\` (gitignored) + stdout tables) and `drift-validate`
  (real-embedding per-item drift vs `drift_budget_threshold`: p50/p95/max + over-budget count).
  `app\reconstruction.py` gains the capture seam only: module attribute
  `drift_observer: Callable[[UUID, float, bool], None] | None = None` invoked per checked item
  at the distance computation; `None` default ⇒ byte-identical behavior (the `on_reconstruct`
  shape). Scenario fixtures are authored realistic prose (the 79%-vs-0% escalation
  construct-validity lesson).
- **Stage 3 — judge layer. BUILT 2026-08-07** (banner above; built to this paragraph with the
  one dated correction below). Config: `ENV_MODEL_JUDGE`, `TWICETOLD_PRICE_JUDGE_IN/OUT`
  (`judge_in`/`judge_out`), `Settings.model_judge` loaded in both modes but absent from the
  real-mode required list (the ruling as a regression test). Providers: `FakeJudgeProvider`
  (deterministic hash verdicts, plumbing only), `RealJudgeProvider` (adaptive thinking, no
  sampling parameters, bounded max_tokens knob, `MalformedOutputError` with token accounting),
  standalone `build_judge_provider(settings)`. Runner: per-category rubric constants with
  `rubric_version` tags; pydantic-validated verdicts; per-item `judge_failed` degradation;
  `--judged` refused in fake mode without `--plumbing`; `emit-gold`; `agreement` (raw % +
  kappa per category); `compare` (A/B over two env overlays; prose judged pairwise with
  position-swap, disagreement ⇒ tie); the Pareto table (accuracy vs `perceived_first_word`
  p50/p95 vs USD/100 turns, non-dominated rows marked). *(Corrected in place 2026-08-07: this
  contract originally specced the real judge at "temperature 0" — unimplementable on the ruled
  Opus-4.8-class judge, whose 4.7+ API rejects `temperature`/`top_p`/`top_k` outright. The
  judge call runs adaptive thinking with no sampling parameters; the rubric's JSON-only output
  contract carries determinism instead.)*
- **Stage 4 — ablation rig.** `SERVICE_DEFAULTS["reconstruction_gist_constraint"] = 1.0` (the
  `gate_enabled` kill-switch shape, read via `agent_knob` inside serve() — no signature
  change); when 0.0, gist is blanked on **original-anchored** items and
  `assemble_reconstruction_prompt(..., include_gist_constraint=False)` drops the `"gist"` key
  and swaps `_SYSTEM_TASK` for `_SYSTEM_TASK_NO_GIST`. Correction-anchored chains are excluded
  from ablation arms (fork 11 — their gist slot IS the corrected head; blanking it deletes the
  correction, a different experiment). The `ablation` verb runs two arms on separate scratch
  DBs (arm B's agent config carries the 0 knob), captures per-item drift via `drift_observer`,
  and reports paired `(memory_id, band, distance_on, distance_off)` + arm summaries + mean
  paired |Δ| beside gist-precision and fabrication per arm. Real-mode for signal; the
  fake-mode run is the plumbing gate only.

  **BUILT 2026-08-12** (the dated workaround + build entries in `decisions.md`; the
  twenty-fourth `floors.md` row — independent floor-verifier pass, 7/7). As specced, with
  three recorded physical shapes: at runtime with the knob at 0, a correction-anchored miss
  still reconstructs normally — serve() partitions the call slots into a no-gist group and a
  normal group (fork 11's ruling applied to the runtime path, not only arm composition); the
  paired report keys on `(scenario_id, memory_ref)` — per-arm memory UUIDs differ across
  scratch DBs, so both are carried as provenance and the contract's `memory_id` wording reads
  through the ref; and the knob is deliberately NOT in `compose_cache_key` — arms live on
  separate scratch DBs, and a live mid-process flip could serve stale-keyed text (the
  kill-switch caveat: flip it at provisioning boundaries, never mid-scene). The corpus is
  `data\eval\corpora\ablation-fixture.jsonl` (3 scenarios × 8 observes, observe/as_of only,
  both decay classes pinned equal + `decay_k_importance` 0.0 so bands are deterministic and
  identical across arms). **The first real run (R7's deciding data):** 24/24
  paired and drift-checked, 0 band mismatches, drift p50/p95/max ON 0.05/0.16/0.1748 vs OFF
  0.04/0.15/0.1594, **0 over-budget in either arm**, mean paired |Δ| 0.056 — the budget is
  blind to the constraint — while **gist-precision drops 0.8335 → 0.7036** with the
  constraint removed (lexical fabrication 0.0 both arms; that detector's known bluntness is
  the stage-3 63-vs-2 finding). **R7 resolved 2026-08-12 on this data** (the dated entry in
  `decisions.md`): the budget keeps its mechanism and threshold and is re-scoped as a topic
  guard; fact-policing belongs to gist-precision + the judged faithfulness category. No
  tuning follow-up — the ruling changes documentation, not the metric.

## Settle-at-build forks

Ruled at stage-1 plan approval or settled at build as authorized; later-stage forks stay open
until their stage builds.

| # | Fork | State |
|---|---|---|
| 1 | C# mirror vs dated exemption for the new wire model | **Mirror** (built, stage 1) — keeps the field-for-field attestation true; verified no mechanical parity gate exists either way |
| 2 | `metric_gist_match_threshold` default | **1.0 strict** (built, stage 1) — paraphrase slack belongs to the judged category |
| 3 | Judge model class | **Opus 4.8** (`claude-opus-4-8`, ruled 2026-08-07) — the sonnet-class recommendation collided with the first real use (judging haiku vs sonnet-5 prose would self-grade the sonnet arm); an Opus judge grades neither arm's class. Env value in `.env`; verdicts are short, so absolute cost stays small |
| 4 | Rubric text home | **Module constants with `rubric_version` tags** (built, stage 3) — `app\eval_judge.py` `RUBRICS`, versions sf-v1 / abst-v1 / rf-v1 / pp-v1 |
| 5 | Judge-agreement acceptance bar | **Kappa ≥ 0.6 per category** (ruled 2026-08-07) — shipped as `agreement --kappa-bar` defaulting to 0.6; an undefined kappa (degenerate marginals) honestly fails the bar |
| 6 | Metrics-route scoring target | **Live head only** (built, stage 1) — the Ledger shows the live telling; the runner walks chains itself |
| 7 | Milestone run artifacts | **Gitignored runs + numbers quoted into dated doc entries** (built, stage 2) — `.gitignore` carries `data/eval/runs/`; the stage-2 banner quotes the real drift numbers |
| 8 | conftest adoption of `provision_scratch` | **Deferred** (ruled at stage-2 build) — the suite's fixture spine stays byte-untouched; the shim keeps conftest + all seven walkers unmodified |
| 9 | Prose-quality rubric dimensions | **Naturalness / character-consistency / memory-grounding / brevity, each 1–5** (ruled 2026-08-07; built as pp-v1) — plus an overall a/b/tie preference, position-swapped |
| 10 | `drift-validate` corpus schema | **Subset of the scenario schema — one loader** (built, stage 2): observe/as_of only, `assert_corpus_shape` states the restriction |
| 11 | Ablation OFF semantics on correction-anchored chains | **Exclude from ablation arms** (ruled 2026-08-12, built stage 4) — the corpus is observe/as_of-only by construction, and at runtime a knob-0 correction-anchored miss still reconstructs normally (blanking its gist would delete the correction). Rejected: a third arm measuring exactly that (~+50% runtime for a question R7 doesn't need); skipping those misses when OFF (correction chains would never reconstruct while the knob is 0) |
| 12 | Gold-set size | **~20–30 items/category** (ruled 2026-08-07) — `emit-gold --limit-per-category` defaults to 30; candidates emitted from the stage-3 real smoke, prose-pairwise gold arrives with the first real compare |

Stage-1 physical shapes settled at build (the [SETTLE-AT-BUILD] latitude): the wire payload
carries no `identity_version` (the identity document is a metric *input*, not an output; the
chain route does not echo it either); unmeasurable gist facts are excluded from both sides of
the ratio and flagged `None` in the per-fact list; the observation's keyword-retention entity
set is recomputed via `extract_entities` (measures the definition, not the stored write-time
merge).

Stage-2 physical shapes settled at build (same latitude; the dated 2026-08-05 `decisions.md`
entry records them with rationale): argparse subparsers for verb dispatch; `extra="forbid"` +
tz-aware datetime validators on every scenario model (an authoring mistake dies at load with
`path:line`, never mid-run); `drift_observer`'s third argument is `refused`
(`distance > threshold`, computed exactly where the serving decision is made — the blind
embed-failure refusal path carries no distance and never calls the observer); one scratch DB
per invocation, fresh agent per scenario; exit codes (`run`: 0 checks green / 1 any failed;
`drift-validate`: 0 under budget / 1 over / 2 mode-gate refusal); defaults `--age-days 30` +
a plain coverage probe (coverage rides k, not wording); fixture scoring pinned by explicit
config facts (`importance_norm_floor: 1.0` + `decay_k_importance: 0.0` neutralize
hash-derived fake importance so expected-IDs cut on pure fake-embedding similarity).

Stage-3 physical shapes settled at build (same latitude; the dated 2026-08-07 `decisions.md`
entry records them with rationale): prose capture is **judged-runs-only** — the plain `run`
artifact stays byte-untouched (the only all-runs addition is the `models` provenance block:
resolved role names + the thinking knob, without which two compare arms are indistinguishable
after the fact); faithfulness judges only memories whose `live_write_cause` is
`reconstruction` (anything else is counted `skipped_not_reconstructed`, never silently judged)
and sees **all** merged-span gist facts — no lemma-measurability filter (that filter is a
lexical-metric artifact; the judge does semantic support); `TWICETOLD_JUDGE_MAX_TOKENS` is a
Settings/env knob (default 2048), not an `agent_knob` — service-scoped eval config, not
per-agent policy; the `TWICETOLD_DIALOGUE_THINKING` knob (`""` omits the thinking parameter —
the pre-B2 request byte-for-byte; `"disabled"` sends thinking off) lands in the real prose
provider now by ruling, so the queued thinking-off variant is expressible as a pure env
overlay; a compare arm is a JSON file (`{"name", "env"}`) whose overlay may carry the six role
vars, the thinking knob, and prices — mode, database, API keys, and the judge are refused (an
arm varies the system under test, never the instrument), and each arm carries its own dialogue
prices (the 2026-07-29 cross-model USD caveat honored by construction); judged outcomes never
change `run`/`compare` exit codes (0/1 stays structural-checks-only; 2 = gate refusal), and
judged numbers are quotable only past the agreement bar; `emit-gold` strips verdicts (labels
are blind; `item_id` joins back to the artifact) and skips `judge_failed` items; pairwise
prose is two calls per pair — true order plus position-swapped — combined with disagreement ⇒
tie and per-arm scores averaged over both positions, `degraded_either` flagged.

**Stage-3 addendum — the `judge-gold` verb (BUILT 2026-08-12, the dated workaround entry in
`decisions.md`).** The first `agreement` run exposed a structural gap no labeler could fix:
when the system under test rarely fails, the natural gold set's judge-side marginals go
degenerate (rf 30/30 `supported`) and Cohen's kappa is undefined-or-zero by arithmetic — the
"rebalance the gold set" case named in `cohen_kappa`'s docstring. The sixth verb closes it:
`judge-gold --gold-in <constructed.jsonl> [--out] [--plumbing]` judges **gold-shaped rows
fresh** — rows authored with labels known by construction (perturbed tellings, premise-
swallowing replies, and their faithful/correct counterparts, class-balanced by design) — and
writes an artifact-shaped JSON that `agreement` scores; that kappa measures judge
**discrimination on known cases**. A present `label` is never shown to the judge (`_judge_one`
receives display-field kwargs only). prose_pairwise rows are refused (pairwise needs the
position-swap protocol only `compare` provides); faithfulness rows must be single-fact
(`...:fact0` item_ids — the artifact item carries the base id, so the agreement fan-out
re-derives the row's id); duplicate ids, rubric-version mismatches, and missing display fields
refuse the whole run (exit 2) before any judge spend. Same real-mode gate as `run --judged`;
providers yes, database no. Judge accounting rides the artifact
(`judged.judge_tokens` + USD when priced).

## Done-when (stage 1 — the build's floor)

- Given a memory with gist spans and a live head, `GET /v1/memories/{id}/reconstruction-metrics`
  returns 200 with IDs + counts + the three ratios, and 404 on an unknown memory id.
- Given the metric functions fixed inputs, the arithmetic is exact: presence honors the
  threshold knob; empty denominators return `None` (never 1.0); correction-anchored chains
  score against the anchor and owe no detail; the band parser inverts `compose_cache_key`.
- Given a metrics read, the record is unperturbed: `/chain` is byte-identical before and after,
  and zero rows are added to `memory_details` / `reconstruction_cache` (the suite's
  non-perturbation pair).
- The Ledger renders the metric numbers beside the four counts on a real reconstructed chain
  (live serve beat), and a metrics failure does not hide the chain.
- The C# mirror deserializes the payload through the live interop gate (one new check).
- Suite green (new tests included), `verify_read_path.py` + `verify_reconstruction.py` re-run
  green, ruff clean at the pin, and an independent floor-verifier pass.
