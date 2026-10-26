# Run the complete Compose demo

[All guides](README.md) | [Next: Python integration](python-integration.md)

From the repository root in PowerShell, with Docker Desktop running (Linux containers).
No host Python, Unity, manual database setup, or downloaded scenario files are needed.
Compose 2.24.4 or newer is required for the real-provider overlay (`docker compose version`).

After the walkthrough, [connect your application](python-integration.md), use
[the evidence bundle](evidence.md) to assess behavior, and follow [deployment](deployment.md)
for a persistent private service. [Setup's connection table](SETUP.md#which-service-to-connect-to)
distinguishes the demo endpoints from the ordinary backend.

## Fake providers: one command, no keys

```powershell
docker compose -f compose.demo.yml run --build --rm demo
```

The command builds the image, creates a dedicated Postgres/pgvector database, applies every
migration, waits for the API and NLP pipelines to be ready, and runs the HTTP walkthrough.
The first build downloads large Python/NLP dependencies and model weights; allow several minutes
and several GB of disk space. Later builds reuse those layers. Runtime NLP is offline.

This path mounts **`.env.example`**, explicitly selects fake providers, and never mounts your
`.env` or calls a model service. Fake prose and token counts are synthetic: this verifies the
integration mechanics, not memory quality. The isolated Compose project is `twicetold-demo-fake`;
its API is at `http://127.0.0.1:8001`, and its database has no host port. Your regular Compose
stack and database are separate.

The walkthrough creates an innkeeper, records two observations about Mara (one pinned), and:

1. Retrieves fresh stored tellings with memory IDs and scores.
2. Advances the simulated clock seven days and persists a reconstruction of the unpinned memory.
3. Repeats the same scene and checks identical text, IDs and read modes plus a cache hit.
4. Generates a dialogue turn using those memories.
5. Corrects where Mara found the lost ledger, using `expected_detail_id` for conflict detection.
6. Retrieves again and checks the corrected fact head, new served telling, and preserved history.
7. Prints a link to that agent and memory in the Ledger, plus token counts.

Expected final result: **`PASS first-run demo (fake)`** (exit code 0). Open the printed inspector
link to compare the immutable observation, original telling, reconstruction, correction, and
subsequent telling. UUIDs, timestamps, scores, and retelling markers vary by run. `read_mode`
changes from `verbatim` to `reconstructed` for the unpinned memory; the pinned one stays verbatim.
Scores can vary slightly across real embedding calls; the same-scene guarantee covers stored
tellings and versions, not query scores or ranking order.

## Real providers: the same scenario with your models

Create `.env` only if you do not already have one:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Edit `.env`: for the template's Anthropic chat + OpenAI embedding configuration, fill in
`ANTHROPIC_API_KEY` and `OPENAI_API_KEY` and choose model names your account can access.
`TWICETOLD_MODEL_IMPORTANCE`, `TWICETOLD_MODEL_RENDER`, and `TWICETOLD_MODEL_TYPOLOGY` must match;
also configure `TWICETOLD_MODEL_DIALOGUE` and `TWICETOLD_MODEL_RECONSTRUCTION`.
For a local/OpenAI-compatible provider, use [the provider recipes in SETUP](SETUP.md).
Host services must be reachable from Docker (`host.docker.internal` on Docker Desktop,
not container-local `127.0.0.1`). No judge, reflection or compiler model is used here.

```powershell
docker compose -f compose.demo.yml -f compose.demo-real.yml run --build --rm demo
```

The overlay explicitly selects **real** mode even if `.env` still says fake. It uses the
separate `twicetold-demo-real` project/volume and port **8002**, so fake and real vectors cannot
mix and both inspectors can remain open. Database connection values come from the demo Compose
file; your `.env` database URI is not used. Only the API and demo runner mount `.env`, read-only;
it is never copied into the image.

This makes live calls to your configured providers. A successful run normally needs **two write
calls, two reconstruction calls, one dialogue call**, and embedding requests for writes, queries,
drift checks and the correction (about a dozen small embedding requests). Budget for a few thousand
input tokens and hundreds to low thousands of output tokens; actual usage is printed per role.
The providers can retry transient failures internally. Dollar cost depends on your models and
rates; no price estimate is baked into this example. There is no paid judge.

Expected outcome is `PASS first-run demo (real)`. The checks verify successful provider paths,
persisted chains, cache behavior and correction mechanics. They do not grade generated prose.
Read the Ledger to assess whether your model's retelling is good. The default drift budget is
preserved: if it refuses an aged retelling, the demo reports failure with an explanation rather
than claiming reconstruction worked or weakening the guard.

## Run again, inspect, diagnose, stop

Rerun the same command to create another agent. Earlier agents and their histories remain.
No writes are automatically retried by the demo's HTTP client: after a timeout, check the printed
agent link before rerunning, since the server may have completed the request. The API remains
running after the one-shot demo container exits.

```powershell
docker compose -f compose.demo.yml ps -a
docker compose -f compose.demo.yml logs --tail 80 api migrate
docker compose -f compose.demo.yml run --rm --no-deps demo python -m app.doctor
# Real-provider connectivity check (small paid calls; also works if the API cannot start):
docker compose -f compose.demo.yml -f compose.demo-real.yml run --rm --no-deps demo python -m app.doctor --probe-providers
```

Use both `-f` arguments for all real-stack commands. A missing `.env` fails the real mount;
missing keys or inconsistent model names fail configuration; provider failures or degraded
responses fail the walkthrough. If a port is occupied, stop its owner before starting the demo.
If you change the real embedding model/endpoint, use a new project name (`-p my-new-real-demo`)
after stopping the old API to free port 8002; its existing volume remains bound to the old model.

For machine-readable output on an already healthy stack:

```powershell
docker compose -f compose.demo.yml run --rm --no-deps demo python -m app.first_run --mode fake --base-url http://api:8000 --public-url http://127.0.0.1:8001 --json
```

The JSON report includes each recall, dialogue, correction, chain, checks, and token usage.
Exit 1 means a check failed. `--timeout 300` raises the default 180-second timeout per HTTP
request for a slower local model. Keep the demo runner and API on the same configuration; its
mode check reads that shared configuration, not remote server metadata.

Stop and remove demo containers/networks while preserving the recorded data:

```powershell
docker compose -f compose.demo.yml down
docker compose -f compose.demo.yml -f compose.demo-real.yml down
```

Adding `--volumes` deletes only the selected demo project's recorded agents and histories.
Use it only when you want to discard that demo data.

## Adapt the HTTP example

[`app/first_run.py`](../app/first_run.py) contains the entire scenario and request bodies. It uses
`httpx` against public routes, never internal database helpers. Copy its provision → observe →
scene boundary → recall sequence into your integration. It keeps the scene's returned
`identity_version` and `scene_started_at` fixed across repeated reads and dialogue, and advances
them explicitly at the next boundary. `as_of` controls decay/scoring; it is **not** a historical
snapshot API. The demo advances world time without waiting seven real days.

Each observation includes an agent-scoped `event_id`. For retryable delivery, save the whole
payload and resend it unchanged after a transport failure; the receipt prevents a second
committed memory. The walkthrough itself does not retry automatically. See the
[retry contract](first-npc.md#7-retrying-an-observation-safely) for conflicts and purge behavior.

The only agent tuning is an explicitly named one-day episodic decay class. Reconstruction,
drift checking and all other thresholds retain service defaults. The authorial correction is
stored verbatim as the new fact basis; a later aged recall can reconstruct its telling again.
The original observation and superseded versions remain available through `/chain`.

## Put it behind your application

The [standalone Python integration](python-integration.md) adds the application layer: bounded
recent conversation, your own dialogue model, a saved agent UUID, and durable observation retries.
It includes an interactive terminal and a second executable Compose scenario, with only `httpx`
required on the client. Use it to replace the sample input/output with your application's UI.

The [verification workflow](verification.md) executes both examples against a fresh database in CI.
That guide also records the dated Haiku/OpenAI reference run and explains what it proves.
