# Assess the system before integrating it

Start with the [keyless Compose demo](first-run.md), then [connect an application](python-integration.md).
This bundle gives an evaluator inspectable results, commands to repeat them, and the limits of each
claim. The operating contract is in [deployment](deployment.md).

## What is demonstrated

| Evidence | What it establishes | What it does not establish |
| --- | --- | --- |
| [Current backend record](evidence/backend-2026-10-22.json) | Revision/configuration, 394 Python checks, both HTTP demos, migration rerun, real DB outage/recovery and restore rehearsal | Live-provider quality, production capacity or a human-evaluated benchmark |
| [Smoke evaluation](evidence/evaluation-2026-10-22.json) | Expected memory IDs under retrieval, correction, pins, age changes and context; fake providers, held-out case excluded | Semantic retrieval quality; fake prose/latency/cost are not real-model measurements |
| [Restore record](evidence/restore-2026-10-22.json) | All 17 public tables compare identically after a custom-format dump/restore, including historical tellings, vectors, binding and receipts | Recovery objectives at production data sizes; empty reflection/compiler tables are not populated-feature coverage |
| [October 19 real-provider walkthrough](verification/reference-real-2026-10-19.txt) | Successful observed/fresh/aged/pinned/cache/dialogue/correction lifecycle on revision `a4c2f02d2874e4e711803ffeaaeaecfb35183b8c` | A live recheck of later revisions or judged factual correctness |
| [September 28 rehearsal examples](evidence/rehearsals-2026-09-28.json) | Unedited target-memory timelines from one accepted and one rejected real-model take, with source, gist spans, IDs and qualitative notes | A random sample, a success rate, or an exactly reproducible benchmark: original Git/embedding configuration was not captured |

The clean run tested **`32f4dd156dfb4a186be470d02f723d4851726203`** with no working-tree changes.
The smoke scenario checks passed 6/6; all 394 tests passed with zero skips. Preserved console output:
[first-run demo](evidence/first-run-2026-10-22.txt),
[application integration](evidence/application-2026-10-22.txt), and
[resolved dependencies](evidence/dependencies-2026-10-22.txt).
The filename date uses America/Los_Angeles; machine timestamps are UTC. Inspector URLs in the
console transcripts belong to ephemeral containers; this verification project publishes no host port.

The current record identifies the implementation commit tested; its companion evidence commit only
publishes the results. The full verification directory also retains the dependency resolution,
image IDs, logs, pytest XML and demo dump. The committed JSON files are compact extracts; the
database backup and full logs remain local/CI artifacts. See [verification](verification.md) for
artifact retention and independent C# verification. No new paid-provider run accompanies this bundle.

## Success and failure side by side

In the accepted September take, Henry's day-180 telling interprets the abandoned gold with suspicion;
Joan's becomes shorter and expresses uncertainty and sadness. Both preserve the source record and
return identical text on repeat reads. Acceptance was a recorded qualitative prerecording decision,
not a calibrated accuracy score; the review file does not identify its author. Read the full timelines
in the JSON rather than inferring a population result from this selected pair.

In the rejected take (`20260928_192305_b858c69f`), the recorded reason was insufficient fading and
identity-conditioned interpretation. Henry's day-180 output also places the pouch **on the bench**,
whereas the observation places it **on the ground beside the bench**. That discrepancy is visible in
the archived text while its stored observation/gist spans remain intact. This is a concrete limit of
the current design: preservation of a source fact and faithful expression of that fact are separate.
The archive preserves existing capture replacement characters and marks its missing provenance.

Current failure-path evidence is reproducible without models: the Compose verifier stops its own
database, observes liveness 200/readiness 503, restores connectivity and observes readiness 200.
Tests also reject pending/newer migrations, incompatible embeddings, incomplete restoration and
changed observation replay payloads. These are infrastructure/contract failures, not model-quality grades.

## Repeat the checks

From the repo root with PowerShell 7 and Docker Desktop (Linux containers):

```powershell
pwsh -File scripts\verify-backend.ps1
```

This creates a new isolated project, uses `.env.example`, runs all checks above and removes only its
own containers/volume. It never reads your `.env` or calls a remote model. See the final printed
`artifacts\verification\<project>` directory. `run.json` records a failed status and step exit codes
when a run fails; missing Postgres or a skipped database suite cannot count as a successful run.
The first image build needs downloads; subsequent fake runtime work uses baked NLP assets.

For a separate smoke-evaluation run, after a configured host setup:

```powershell
$env:TWICETOLD_PROVIDER_MODE = 'fake'
python -m app.eval_runner run --scenarios data\eval\scenarios\smoke.jsonl --out artifacts\smoke.json
Remove-Item Env:TWICETOLD_PROVIDER_MODE
```

It provisions/drops a scratch database and needs database-creation privileges. `run` exit status
reflects structural ID checks; judged scores do not change it. To assess your providers, use
[the real-provider Compose path](first-run.md#real-providers-the-same-scenario-with-your-models)
with your own credentials. Real runs incur provider charges and send the authored demo data to
your configured endpoints; generated prose and usage vary.

For your own quality experiment, configure real mode plus `TWICETOLD_MODEL_JUDGE`, then use the
existing judged scenarios and ablation harness:

```powershell
python -m app.eval_runner run --scenarios data\eval\scenarios\judged.jsonl --judged --out artifacts\judged.json
python -m app.eval_runner ablation --corpus data\eval\corpora\ablation-fixture.jsonl --out artifacts\ablation.json
```

These are optional paid experiments, not part of keyless verification. Record `git rev-parse HEAD`,
`git status --short`, the model IDs/backend, embedding model/endpoint identity, changed knobs,
scenario files, dependency versions and time alongside the output, **excluding keys and `.env`**.
Use untouched held-out data and human review before generalizing quality to your product.

## How to read the metrics

The files under `data\eval\gold` keep their legacy CLI name. The natural and pairwise labels are
**single-model reference labels**, not human gold; their provenance documents say so explicitly.
Agreement measures concordance with that reference model. The pairwise reference report gives
kappa **0.3697**, below the project's 0.6 threshold, despite raw agreement 0.8333 (30 rows).
That result does not validate the pairwise quality scores. See the
[pairwise provenance](../data/eval/gold/pairwise-2026-08-12.provenance.md).
The [natural-reference provenance](../data/eval/gold/candidates-2026-08-07.provenance.md) reports
30 supported/0 unsupported faithfulness labels, so it provides no negative-case discrimination
evidence. The constructed set supplies authored positive/negative controls, not representative traffic.

Stored observation text and selected gist spans are immutable through ordinary retellings. Corrections
add new anchors/versions; explicit purge is the deletion exception. This protects an audit trail.
It does **not** make the input true or force an LLM to preserve every fact in generated prose.
The serving path has a gist prompt and an embedding-distance guard, not a semantic entailment gate.
`gist_precision` is lexical presence; `fabrication_rate` detects unmatched named entities, not every
invented claim. A low cosine distance can coexist with a factual contradiction. See
[the metric definitions](eval-harness.md).

The founder's remaining work is therefore explicit: evaluate their model/data combination, decide
which uses tolerate reconstructive recall, add authorization/rate and spending controls at the
application boundary, and establish backup/monitoring/load limits. A general factual-memory product
would also need a validated policy for accepting or rejecting retellings. This bundle demonstrates
an inspectable reconstructive-memory prototype and integration path, without claiming those product
decisions have already been solved.
