# Verify a clean checkout

The [GitHub Actions workflow](../.github/workflows/verify.yml) runs on pushes, pull requests and
manual dispatch. It requires no repository secrets and makes no paid model calls. The backend
job uses Ubuntu 24.04 and the repository's Dockerfile; independent C# jobs use Ubuntu 24.04 and
Windows 2022 with .NET SDK 8.0.423. Actions are pinned to commit hashes and the workflow requests
read-only repository access. See [GitHub's workflow reference](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
for the trigger and permissions semantics.

## Run the backend check locally

Prerequisites: Docker Desktop with Linux containers, Compose 2.24.4 or newer, and PowerShell 7.
From the repository root:

```powershell
pwsh -File scripts\verify-backend.ps1
```

This is the same script CI runs. It:

1. Builds the actual service image, including its Python dependencies and NLP models.
2. Runs Ruff lint and formatting checks against the service, examples and tests.
3. Creates a unique Compose project and a new Postgres/pgvector volume, applies every migration,
   and waits for the API. A second migration invocation must exit successfully with nothing pending.
4. Runs the full Python suite, including NLP/write scenarios, with `--require-db`.
5. Runs the documented first-run walkthrough and the application-owned chat demo over HTTP.
6. Runs the smoke evaluation on its own scratch database; scores structural ID checks only.
7. Stops the disposable database and verifies HTTP 503 readiness with HTTP 200 liveness, then
   restarts it and verifies readiness recovers.
8. Stops the API, dumps the demo database, restores into a new empty database and compares every
   public table's complete rows, including vectors, history and receipts. Checks doctor/runtime startup.
9. Saves logs, image IDs, resolved Python dependency versions and pytest XML under
   `artifacts\verification\<project>`, then removes that project's containers, network and volume.

The output folder is an evidence bundle: `run.json` records revision, working-tree changes,
configuration, step exit codes and final status; `evaluation.json` preserves scenario results;
`restore.json` records table counts/hashes; `demo.dump` is the disposable demo backup. Ready/outage/
recovery JSON lives in the corresponding step logs. Failed runs retain their available artifacts
and an unsuccessful status. Compare the [committed example bundle](evidence.md) and
[deployment procedure](deployment.md). Local runs with changes are explicitly marked; a source
archive without Git metadata is labeled as such, never attributed to an invented commit.

The script uses `.env.example`, never your `.env`. It publishes no host ports, so it can run beside
the ordinary demo without touching its database. Test inputs mount read-only; the application and
dependencies come from the built image. It uses the same `compose.demo.yml` as the introductory
walkthrough, with [a verification overlay](../compose.verify.yml) for isolation and the test runner.
The first build needs package/model download access. Tests and fake demonstrations use no remote
model services; NLP assets are baked into the image and runtime downloads are disabled. Docker
image/build caches remain available for later runs. GitHub retains diagnostic artifacts for 14 days,
including after a failed job. The script exits nonzero when a required step or cleanup fails.

CI begins from a fresh checkout. Running locally checks your working files; use a fresh clone when
you want the same clean-source guarantee. No prebuilt service image is published by this workflow.
Dependencies are not a complete lockfile: the saved resolution and image ID identify what a given
run tested, while future clean builds may resolve different transitive dependencies.

## Database tests cannot silently pass without Postgres

For a host Python installation with the backend requirements and a test-capable Postgres role:

```powershell
python -m pytest tests --require-db -q
```

The fixture creates and migrates its own `twicetold_suite_<pid>` database, then drops it even if
migration fails. It needs database-creation privileges; it never runs product-table tests against
the database named in your `DATABASE_URI`. Missing configuration or an unreachable database is a
failure in required mode. `CI=true` enables that mode automatically, and the Compose test runner
also passes the flag explicitly. Migration failures and timeouts fail the run rather than skip it.

For local development only, omitting `--require-db` outside CI preserves the warning/skip behavior
when Postgres is unavailable. Such a result verifies only the checks that actually ran; it is not a
passing backend verification. Pure infrastructure regressions can run without a database:

```powershell
python -m pytest tests\test_infrastructure.py -q
```

Those checks cover required versus optional database availability, CI defaults, safe diagnostics,
and scratch cleanup on successful setup, failed migration and timeout.

## Check the C# integration separately

With .NET SDK 8.0.423 installed (`global.json` pins it for the repository's client tools):

```powershell
dotnet restore client\NpcMemory.Tests\NpcMemory.Tests.csproj
dotnet build client\NpcMemory.Tests\NpcMemory.Tests.csproj --no-restore --configuration Release
dotnet run --project client\NpcMemory.Tests --no-build --configuration Release
```

The runner compiles the shipped core, Unity adapter and starter sample and exercises their HTTP,
readiness, scene and cancellation contracts. Expected result: `47 contract checks passed`.
It uses Unity type stubs, not the Unity Editor or Play Mode. CI runs this independently on both
operating systems; a passing backend job alone does not establish client compatibility.

## Recorded real-provider reference

The latest recorded paid-provider verification is **2026-10-19 (America/Los_Angeles)**, at service
revision **`a4c2f02d2874e4e711803ffeaaeaecfb35183b8c`**. This is historical evidence, not a claim
that every later revision has been rechecked against live providers. The current automated checks
use fake providers and mock HTTP contracts.

| Setting | Verified value |
| --- | --- |
| Recipe | `compose.demo.yml` plus `compose.demo-real.yml`, separate real-provider database |
| Provider mode / text backend | `real` / `anthropic` |
| Importance, render, typology, dialogue, reconstruction | `claude-haiku-4-5-20251001` for all five roles |
| Embeddings | OpenAI `text-embedding-3-small`, 1536 dimensions, default hosted endpoint |
| Result | First-run walkthrough passed ingestion, fresh/aged recall, pins, cached text stability, dialogue, correction and preserved history |
| Agent | `dad67a38-e9ae-411f-a3e7-81421138535f` |
| Corrected memory | `97e5fbfd-d2b3-4869-9479-2efde7049896` |

The [recorded walkthrough output](verification/reference-real-2026-10-19.txt) contains the IDs,
returned tellings, checks and usage from that run. Build chatter is omitted; walkthrough output is
preserved. Reported tokens were 845 input / 260 output for writes, 1,063 / 190 for reconstruction,
191 / 110 for dialogue, and 221 embedding plus 216 reconstruction drift-check tokens. The report's
legacy `sonnet_*` fields describe dialogue usage; the configured dialogue model was Haiku.

To recheck a current revision, follow [the real-provider setup](first-run.md#real-providers-the-same-scenario-with-your-models)
with your own credentials and run:

```powershell
docker compose -f compose.demo.yml -f compose.demo-real.yml run --build --rm demo
```

This makes paid calls. Keep the date, revision, model configuration and output with the result;
do not store keys or `.env` in CI artifacts. Generated wording and usage can vary. The walkthrough
checks structural behavior and persistence, not factual faithfulness or model quality. Broader
evaluation evidence and deployment guarantees are separate from this integration check.
