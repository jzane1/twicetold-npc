# Documentation and reading order

Start with **[the first-run demo](first-run.md)**, then **[connect a Python application](python-integration.md)**.
The trial needs Docker with Linux containers; no host Python, Unity, or provider keys are required.
Use [the evidence guide](evidence.md) to assess the results and [deployment](deployment.md) when
you are ready to run a persistent private service. Commands in these guides use PowerShell.

## Start here

| Goal | Guide | What you get |
| --- | --- | --- |
| Try the memory lifecycle | [First-run Compose demo](first-run.md) | One keyless command, a populated Ledger, and a separate real-provider path |
| Connect your own application and dialogue model | [Python integration](python-integration.md) | A Docker-only example, an interactive client, and reusable HTTP code with only `httpx` as a client dependency |
| Assess behavior and limitations | [Evidence](evidence.md) | Reproducible structural checks, dated real-model examples, and quality caveats |
| Run a persistent backend or configure providers | [Setup](SETUP.md) | Ordinary Compose, host development, diagnostics, and safe provider changes |
| Operate the service | [Deployment](deployment.md) | The single-process boundary, readiness, upgrades, and backup/restore |
| Repeat the automated checks | [Verification](verification.md) | Isolated backend verification and separate C# contract checks |
| Add memory to a Unity game | [Your first NPC](first-npc.md) | Provisioning, readiness, observations, dialogue, and scene boundaries |
| Design a character | [Identity authoring](identity-authoring.md) | Identity, memory prose, and per-agent settings |
| Plan a game release | [Shipping](shipping.md) | Hosting, keys, historical cost measurements, platforms, and retention responsibilities |

The fake demo, real demo, and ordinary Compose service use separate databases and ports.
See [which service to connect to](SETUP.md#which-service-to-connect-to) before attaching a client.
For the optional Unity recording, use [the village reproduction guide](../data/demo/README.md).

## Design and API reference

[Architecture](architecture.md) explains the data model and the write, retrieval, reconstruction,
correction, dialogue, reflection, and instrumentation paths. Read the sections relevant to the
behavior you want to adapt. [The Unity client reference](unity-client.md) covers C# verbs,
timeouts, errors, and scene-state handling. The running service also exposes OpenAPI at `/docs`.

| Reference | Scope |
| --- | --- |
| [Foundational schema](migration-01.md) | Migration 001 only, with pointers to later schema changes |
| [Mid-dialogue gate](mid-dialogue-gate.md) | Conditional retrieval and the caller-held loaded set |
| [Deferred writes](deferred-writes.md) | Pending observations, enrichment, and completion behavior |
| [Reflection](reflection.md) | Evidence-cited beliefs and the optional worker |
| [Parameter compiler](parameter-compiler.md) | Beliefs compiled into per-scene retrieval weights |
| [Evaluation harness](eval-harness.md) | Metrics, model-reference agreement, judged scenarios, and ablation |
| [Test suite](test-suite.md) | Structural-test discipline, coverage, and failure contracts |

The current schema is defined by [migrations 001 through 011](../db/migrations/), applied by
[the migration runner](../db/migrate.py). Migration 010 binds the database to an embedding
configuration; migration 011 adds observation retry receipts. The foundational schema page is
not a complete description of the current database.

## The repository, folder by folder

| Path | Contents |
| --- | --- |
| [app](../app/) | Service routes, providers, memory processing, diagnostics, demos, and evaluation runners |
| [examples](../examples/) | The application-owned Python chat client and its small dependency list |
| [db](../db/) | Numbered migrations and the transactional runner |
| [tests](../tests/) | Pytest scenarios, layer walkers, and deployment-verification helpers |
| [scripts](../scripts/) | The isolated backend verification entry point |
| [GitHub Actions](../.github/workflows/verify.yml) | Backend and C# verification on a fresh checkout |
| [client](../client/) | C# core project, live-backend harness, and loopback contract tests |
| [unity](../unity/) | The embedded client package, starter sample, and optional playable village |
| [ledger](../ledger/) | The memory inspector served by the API at `/ledger` |
| [data](../data/) | Authored demo/evaluation inputs, model-generated reference labels, and the affect lexicon |
| [evidence records](evidence/) | Dated verification outputs and selected real-model examples |

## Verification vocabulary

- **Suite:** pytest cases that assert IDs, versions, cache behavior, failures, and other structural
  contracts. Database checks require a disposable scratch database; use `--require-db` so unavailable
  infrastructure fails the run. See [verification](verification.md#database-tests-cannot-silently-pass-without-postgres).
- **Walker:** a layer-specific `tests/verify_*.py` script used for deeper checks against a scratch
  database. The [setup guide](SETUP.md#6-tests) explains their ordering and database ownership.
- **Floor:** a layer whose behavior was independently verified. The historical floor ledger,
  decision register, and session log are maintained locally; the public [evidence](evidence.md)
  and [verification](verification.md) guides describe what an evaluator can inspect and repeat.
