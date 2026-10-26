# twicetold-npc — setup

[All guides](README.md) | [First-run demo](first-run.md) | [Python integration](python-integration.md)

This page covers a persistent backend, provider configuration, diagnostics, and host development.
Commands use **PowerShell**; Docker runs Linux containers. Choose the path that matches your goal:

| Goal | Start with | Prerequisites |
| --- | --- | --- |
| Try the complete lifecycle | [First-run Compose demo](first-run.md) | Docker; no host Python, Unity, or keys for the fake path |
| Connect your application | [Python integration](python-integration.md) | Docker for its demo; Python and `httpx` for the interactive host client |
| Add the Unity client | [Your first NPC](first-npc.md) | A running backend and Unity |
| Operate a persistent service | [Deployment](deployment.md) and the Compose setup below | Docker and application-owned access controls |
| Check a checkout | [Verification](verification.md) | Docker and PowerShell 7; the pinned .NET SDK for separate C# checks |

After the demo, [the evidence guide](evidence.md) explains what the checks and model examples prove.
The host installation sections are for backend development; the Python client does not need the
backend's NLP dependencies.

## Which service to connect to

| Stack | Compose files | API URL from your host | Configuration |
| --- | --- | --- | --- |
| Keyless first-run / application demo | `compose.demo.yml` | `http://127.0.0.1:8001` | `.env.example`, forced fake mode, isolated demo database |
| Real-provider first-run demo | `compose.demo.yml` + `compose.demo-real.yml` | `http://127.0.0.1:8002` | `.env` providers, forced real mode, separate demo database |
| Persistent backend | `docker-compose.yml` | `http://127.0.0.1:8000` | `.env`, your chosen provider mode and database |

These are separate stores: an agent UUID from one will not exist in another. The Python client
defaults to port 8001; [connecting to the persistent backend](python-integration.md#use-the-interactive-application)
requires `--base-url http://127.0.0.1:8000` and a separate state file. Inside a demo container,
use `http://api:8000` for that project's API instead of a host URL. Keep state files tied to
one agent and API origin. Fake and real embeddings cannot share a bound database; see
[changing providers safely](#changing-providers-safely).

## The one-command backend (compose)

Use this stack for a persistent service with your own configuration. For an automatically
populated trial, use [the first-run demo](first-run.md) instead. Both paths need Docker only:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# Edit .env for this database, or keep the fake-mode defaults for a new store.
docker compose up -d --build
```

This builds the API image, starts Postgres with pgvector, runs migrations 001 through 011 as a
one-shot `migrate` service, and starts the API, in dependency order. `docker compose ps` shows
progress; the `api` service reports `healthy` after its pipelines warm and database/schema/embedding
and worker readiness checks pass. The first build downloads large Python/NLP dependencies and
model weights; allow several minutes and several GB of disk space. Later builds reuse cached
layers. NLP assets are baked into the image, so runtime NLP needs no downloads.
Then open [The Ledger](http://127.0.0.1:8000/ledger) or [the API docs](http://127.0.0.1:8000/docs). Both
published ports, Postgres 5432 and the API 8000, bind `127.0.0.1` only.

This starts an empty service. Provision an agent through [the Python client](python-integration.md#use-the-interactive-application)
or [the Unity guide](first-npc.md) before expecting memories in the Ledger.

If `up` fails at once on the `api` mount, you skipped `Copy-Item .env.example .env`: the API
reads `.env` from a read-only bind mount and compose refuses to invent it. Provider mode, real
keys, and the OpenAI-compatible backend are all configured through that same `.env`, exactly as
in the numbered sections below. Teardown is under [Teardown](#teardown) at the end.

**Sections 0–5 below describe the host development path** (Python running the backend directly).
Provider settings apply to both paths; [section 4b](#4b-self-hosted--openai-compatible-servers-the-provider-path-2026-09-02) includes the Compose-specific
host address. For host development, `docker compose up -d db`
brings up just the database and you run `python -m app.serve` on the host beside it. Do not run
the full compose stack and a host `python -m app.serve` at once: they both bind port 8000 and
both drive the same database.

## Check setup before making observations

After the image has built and migrations have run, use a one-off container. This also works when
the API cannot start, and does not load the NLP pipelines:

```powershell
docker compose run --rm --no-deps api python -m app.doctor
```

For a host Python installation, run `python -m app.doctor` instead. The default command is
read-only: it reports the effective provider mode, required model names in real mode, database
connectivity, pending migrations, and embedding-configuration compatibility. It makes **no model
calls** and does not record a database binding. Exit 0 means these checks passed, not that a live
model has been contacted. `--json` provides machine-readable checks; exit 1 means a check failed.

To explicitly test provider connectivity too:

```powershell
docker compose run --rm --no-deps api python -m app.doctor --probe-providers
# Host Python equivalent:
# python -m app.doctor --probe-providers
```

Real mode sends one small JSON request to each distinct required chat model and one embedding
request. These may incur provider charges. Fake mode only checks the deterministic fake embedding;
it does not test any configured remote server. Probes use no automatic retries and a 10-second
request timeout (`--timeout 30` changes it). Database failures prevent provider probes. Credentials,
connection strings and remote error bodies are omitted from diagnostic output. The embedding probe
checks the fitted 1536-dimension output and rejects empty, zero or non-finite vectors. A passing
probe establishes basic connectivity and response shape, not memory quality or streaming support.
Optional judge, reflection and compiler models are not probed.

## Changing providers safely

Migration 010 adds a database-wide embedding binding. Before NLP warm-up or worker startup, the
API and command-line runners check it. A database without vectors is bound automatically on first
runtime startup. The binding covers fake versus real mode, the embedding model, endpoint identity,
dimension and fitting version. API keys and chat-model choices are excluded, so rotating keys or
changing dialogue models does not invalidate embeddings. Endpoint identity is stored as a hash.
An endpoint alias or model alias is conservatively treated as a different configuration; use the
same connection topology consistently. A model server changing weights behind an unchanged model
name cannot be detected, so use stable model versions.

**To switch a fake trial to real providers, create a separate database.** Preserve the old one;
do not delete the volume or relabel its binding. With the unchanged template database user:

```powershell
docker compose stop api
docker compose exec db psql -U twicetold -d postgres -c 'CREATE DATABASE twicetold_real;'
```

Use your configured `POSTGRES_USER` if it differs. In `.env`, change `POSTGRES_DB` to
`twicetold_real`, change the database name at the end of `DATABASE_URI` to the same name, and set
`TWICETOLD_PROVIDER_MODE=real` plus the chosen provider settings. Keep the existing database user
and password. Then run:

```powershell
docker compose up -d --build
docker compose run --rm --no-deps api python -m app.doctor --probe-providers
```

The migration service initializes the new database. The old database remains in the volume; its
agents and memories do not appear in the new database. On the host path, create a new database in
the same way, point `DATABASE_URI` at it, run `python db\migrate.py`, then run the doctor and server.
There is no re-embedding tool in v1; retained memories must be replayed into a new database using
their original observations if a different embedding model is required.

**Upgrading an existing store:** stop every API, REPL, worker and evaluation process using it
before applying migration 010. The migration never guesses the provenance of existing vectors.
If vectors exist without a binding, startup refuses them. Verify that `.env` describes the
**original** embedding mode, model and endpoint, then explicitly attest to that configuration:

```powershell
# Compose: rebuild first, then migrate while the API is stopped.
docker compose build
docker compose run --rm migrate
docker compose run --rm --no-deps api python -m app.doctor --adopt-existing-embeddings
docker compose up -d api
# Host equivalent after python db\migrate.py:
# python -m app.doctor --adopt-existing-embeddings
```

Adoption only fills a missing binding; it cannot override an existing one and never changes
vectors. It is an operator attestation, not a verification of historical model provenance. If
provenance is unknown or mixed, use a new database. Historical and location vectors also count;
purging live memories is not a supported way to change the binding.

## Agent configuration errors

`POST /v1/agents` validates `config` before provisioning and returns HTTP 422 for unknown keys,
invalid types, non-finite numbers and unsafe ranges. The Python provisioning and configuration
merge helpers use the same validation; a failed merge leaves the stored configuration unchanged.
Valid configurations stay sparse: defaults are not copied into the stored object.

For example, `{"decay_classes":{"episodic":86400},"decay_class_default":"episodic"}` is
valid; a zero duration, an unresolved default label, or `retrieval_top_kk` is rejected. Numbers
must be JSON numbers, not strings or booleans. Numeric `null` overrides retain their existing
use-the-default meaning. Switches accept 0 or 1; count knobs require whole numbers. Zero remains
valid for supported disable switches such as `gate_enabled`, `reconstruction_theta` and
`lexical_fetch_k`. Decay durations, time scales and the reconstruction band quantum must be
positive. Process-only worker poll/batch settings cannot be overridden per agent. Retired
escalation keys remain accepted for corpus compatibility but have no effect. Existing stored
configurations are not rewritten by this upgrade; validate them before updating them. Custom
`text_search_config` names must also exist in Postgres.

---

## 0. Prerequisites

The compose path above needs only a running Docker Desktop. The list below is for the
bare-metal dev path and the C# and Unity clients:

| Thing | Version | Notes |
|---|---|---|
| Python | 3.14, on PATH | global install, not a venv — the project assumes this |
| Docker Desktop | current | must be *running*, not just installed |
| .NET SDK | 8.0.423 | pinned by [global.json](../global.json); only for the C# tools and checks |
| Unity | 6.x | only for the demo scene |

Check:

```powershell
python --version; docker --version; dotnet --version
```

---

## 1. Python dependencies

```powershell
python -m pip install -r requirements.txt
```

This includes the two spaCy models as direct wheel URLs. **Do not** use
`python -m spacy download` — spaCy's downloader shells out to `uv` on this machine (uv is
installed for the Postgres MCP) and fails outside a venv. `en_core_web_lg` is the write pass;
`en_core_web_sm` is fastcoref's internal tokenizer and is required even though nothing calls it
directly.

The API warms spaCy and fastcoref during startup, before readiness succeeds. The host REPL and
some direct service tests load them on first use instead; those tests carry the `nlp` marker.
Initial model loading can take several minutes.

---

## 2. Environment file

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Then edit `.env`. The template documents every key. A few things that have actually caused
failures:

- **One `KEY=VALUE` per line.** No inline comments after a value, no wrapped lines. A
  consolidated multi-line price note once crashed `load_settings` on every run that read prices.
- **`DATABASE_URI` must name the product database** (`twicetold`). Scratch databases are created
  and dropped by the fixtures; never point this at one.
- **Use `127.0.0.1` in `DATABASE_URI`, not `localhost`.** The db container publishes IPv4
  loopback only (`127.0.0.1:5432`); on Windows/macOS `localhost` can resolve to IPv6 (`::1`)
  first and stall roughly 20 seconds per connection before falling back, which makes the suite
  and the CLI crawl.

Verify without printing anything:

```powershell
python -c "from app.config import load_settings; load_settings(); print('config ok')"
```

`.env` is gitignored and must stay that way. `TWICETOLD_PROVIDER_MODE=fake` (the template default)
runs offline and keyless — everything below works without an API key. Real mode runs on the
Anthropic backend by default; `TWICETOLD_MODEL_BACKEND=openai` plus a base URL points every LLM
role at any OpenAI-compatible server instead (§4b below), and the embedding role has its own
base URL and model knobs.

---

## 3. Database

```powershell
docker compose up -d db
docker ps --filter name=twicetold-pg --format "{{.Names}} {{.Status}}"
```

`up -d db` starts only the database. Plain `docker compose up -d` now starts the whole stack
(database, the one-shot migration, and the containerized API); on the bare-metal path you want
the database alone, because you run the API on the host in the next step. Wait for `(healthy)`.
Compose reads the same `.env`, so `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` must
agree with `DATABASE_URI`.

Apply the schema:

```powershell
python db\migrate.py
```

First run applies migrations 001–011 and records each in `schema_migrations` **in the same
transaction as its DDL** — a half-applied migration can never be logged complete. Re-running is a
clean no-op:

```
Up to date: 11 migration(s) applied, 0 pending.
```

Point it elsewhere with `--database-uri <uri>` (this is how the fixtures migrate scratch
databases).

---

## 4. Run the service

```powershell
python -m app.serve
```

**Not** `uvicorn app.api:app` — psycopg's async pool needs a `SelectorEventLoop` on Windows, and
`app\serve.py` is what sets it. The API listens on `http://127.0.0.1:8000`.

Useful once it is up:

- [API docs](http://127.0.0.1:8000/docs): the generated OpenAPI surface, including health checks.
  `/ledger` and `/v1/ledger/turns` are deliberately excluded from that schema.
- [The Ledger](http://127.0.0.1:8000/ledger): paste an agent UUID to
  see its memories, and click one to see the immutable observation beside both version chains
  with superseded rows greyed but present.

---

## 4b. Self-hosted / OpenAI-compatible servers (the provider path, 2026-09-02)

Every LLM role can run on any server that speaks the OpenAI chat-completions API — OpenAI
itself, Ollama, vLLM, LM Studio, llama.cpp server, OpenRouter, LiteLLM — through one explicit
selector. The Ollama shape, end to end:

```powershell
winget install --id Ollama.Ollama
ollama pull llama3.1:8b            # any chat model; the five role vars name it
ollama pull qwen3-embedding:4b     # Matryoshka: emits exactly 1536 via dimensions=
$env:OLLAMA_CONTEXT_LENGTH = "16384"   # or a Modelfile num_ctx — see the warning below
```

Then in `.env` (one `KEY=VALUE` per line):

```
TWICETOLD_PROVIDER_MODE=real
TWICETOLD_MODEL_BACKEND=openai
TWICETOLD_MODEL_BASE_URL=http://127.0.0.1:11434/v1
TWICETOLD_MODEL_IMPORTANCE=llama3.1:8b
TWICETOLD_MODEL_RENDER=llama3.1:8b
TWICETOLD_MODEL_TYPOLOGY=llama3.1:8b
TWICETOLD_MODEL_DIALOGUE=llama3.1:8b
TWICETOLD_MODEL_RECONSTRUCTION=llama3.1:8b
TWICETOLD_EMBEDDING_BASE_URL=http://127.0.0.1:11434/v1
TWICETOLD_EMBEDDING_MODEL=qwen3-embedding:4b
```

The URLs above are for **host Python**. For the API in **Docker Desktop Compose**, use
`http://host.docker.internal:11434/v1` for both base URLs: `127.0.0.1` inside the API container
refers to that container. Ollama must listen on an interface reachable from Docker. Quit any
already-running Ollama tray/server instance, then start it in a separate PowerShell window:

```powershell
$env:OLLAMA_HOST = "0.0.0.0:11434"
$env:OLLAMA_CONTEXT_LENGTH = "16384"
ollama serve
```

This listens beyond loopback; restrict inbound port 11434 with the host firewall to the intended
local/Docker clients. Keep this window open. For host Python only, use the same start procedure
with `$env:OLLAMA_HOST = "127.0.0.1:11434"` so the context setting reaches the server process.
After changing `.env`, restart the API (`docker compose restart api` or restart the host process),
then run the doctor with `--probe-providers`. If the database is already bound to fake mode,
follow [Changing providers safely](#changing-providers-safely) first. Startup rejects a mismatched
binding instead of silently mixing the vectors.

No API key is needed for a local server (a placeholder is sent; `TWICETOLD_MODEL_API_KEY` /
`TWICETOLD_EMBEDDING_API_KEY` exist for hosted servers such as `https://api.openai.com/v1`).
`load_settings` is loud about the misconfigurations: a base URL under the anthropic backend, a
missing base URL under openai, `TWICETOLD_DIALOGUE_THINKING` under openai (an Anthropic
request knob), and `TWICETOLD_MODEL_TOKEN_LIMIT_FIELD=max_completion_tokens` under anthropic
(whose wire field is always `max_tokens`). Fake mode reads none of this.

**The embedding width contract.** The vector column is locked at 1536 dimensions. Every
embedding call sends `dimensions=1536`, so a Matryoshka-trained model (`qwen3-embedding`)
emits exactly 1536; a narrower model (`nomic-embed-text` at 768, `bge`/`mxbai` at 1024) is
zero-padded to 1536 at the seam — cosine, L2, and inner-product distances between padded
vectors equal those of the originals, so retrieval is unchanged — with one warning per
process; a wider model is refused loudly (client-side truncation is unsound for non-Matryoshka
models). The embedding model is a per-database choice: startup rejects a change to an existing
binding, and there is no re-embed tooling in v1. Use a new database as described above.

**Wire notes.** The token-limit FIELD is a knob (ruled 2026-09-03, built 2026-09-11):
requests use `max_tokens` (the default; the field local servers document) unless
`TWICETOLD_MODEL_TOKEN_LIMIT_FIELD=max_completion_tokens` (the field hosted OpenAI's
reasoning-class models — the gpt-5 family — demand); the values each role sends are unchanged
either way. Beyond that, `response_format=json_object` on every structured call, and
`stream_options.include_usage` on the dialogue stream (a server that rejects it fails the turn
before the first chunk, loudly; a server that omits usage is counted as 0 tokens with one
warning, and the cost table then reads zero).

**The small-model quality warning** (ruled with the path, 2026-09-01). Every measured number in
this repo — cost per 100 turns, perceived-first-word p50, the believability no-regression —
was taken on the locked Anthropic slate and does not transfer. Small local models break the
structured-output contract first: the write call's JSON (rendered telling + importance +
typology) and the drift-budgeted batched reconstruction. The failures are loud and degrade by
the ruled ladder, never a rejected request: `scoring_failed` writes at neutral importance,
failed enrichment runs, retellings falling back to their live heads, `MalformedOutputError` in
the log. Ollama's default context window (4096 tokens) silently truncates the batched
reconstruction prompt from the front, which is the single likeliest "it returns garbage"
report — raise `OLLAMA_CONTEXT_LENGTH` (or a Modelfile `num_ctx`) to 16384 or more. The judge's
calibration and its adaptive thinking are Anthropic-only; the judge-shaped roles (judge,
reflection, compiler) are the most exposed to a weak model.

---

## 5. Drive it from the REPL

Provision an agent (`POST /v1/agents`), then replace the UUID placeholder below:

```powershell
python -m app.cli --agent "<agent-uuid>" --debug
```

`--debug` is the point: it prints retrieved memory IDs, scores, `read_mode`, gate decisions,
token counts, and both TTFT fields. Meta-commands include `:observe`, `:correct`, `:scene`,
`:as-of`, `:context`, and `:help`.

Synthetic load, aggregates, and the per-100-turn cost table:

```powershell
python -m app.load_driver
```

---

## 6. Tests

For the complete Docker-based check, use [clean-checkout verification](verification.md). It runs
the build, migrations, full suite, both examples, smoke evaluation, and recovery/restore checks.

**The host suite** creates and drops its own scratch database. It needs the backend dependencies
and a Postgres role with database-creation privileges. Use required-database mode:

```powershell
python -m pytest tests --require-db -q
python -m pytest tests --require-db -q -m "not nlp"   # faster structural subset
```

Missing Postgres fails these commands; `CI=true` also enables required-database mode. Outside CI,
omitting `--require-db` allows unavailable database cases to warn and skip. Such a run is not a
passing backend verification. [The suite guide](test-suite.md) has the current coverage/counts;
[verification](verification.md#database-tests-cannot-silently-pass-without-postgres) explains the policy.

**The walkers** (sixteen structural done-when scripts) need a scratch DB you create yourself:

```powershell
$scratch = "postgresql://twicetold:change-me@127.0.0.1:5432/twicetold_test"
docker exec twicetold-pg psql -U twicetold -d postgres -c "CREATE DATABASE twicetold_test"
python db\migrate.py --database-uri $scratch
python tests\verify_write_path.py --database-uri $scratch
# ... verify_provider_path (the provider path, 2026-09-02 — offline; only its served
#     beat touches the scratch), verify_prewarm (C7-B, 2026-08-18),
#     verify_concurrency (C7-A, 2026-08-18),
#     verify_purge (C6, 2026-08-18; section H = the per-agent verb, 2026-09-02),
#     verify_agent_state (C5, 2026-08-17),
#     verify_dissonance (C4, 2026-08-17), verify_compiler (C3, 2026-08-17),
#     verify_reflection (C2, 2026-08-15), verify_deferred_writes (C1, 2026-08-12),
#     verify_read_path, verify_cli_harness, verify_gate, verify_reconstruction,
#     verify_authorial_correction, verify_fact_correction
docker exec twicetold-pg psql -U twicetold -d postgres -c "DROP DATABASE twicetold_test WITH (FORCE)"
```

Run them serially on a FRESH scratch, elder walkers before `verify_dissonance` (the five
newest — agent_state, purge, concurrency, prewarm, provider_path — are id-scoped and
re-runnable, so their position is free) — two of the
correction walkers assert the corrections table is empty of diegetic rows, which is true in
sweep order on a fresh scratch and false after a dissonance run (a known shared-scratch
fragility, carried; `verify_reflection` additionally requires
a fresh scratch for its own re-run).

Each prints `ALL CHECKS PASSED (N assertions)` and exits non-zero on the first failure. Assertion
counts grow whenever a layer is re-opened, so there is no single "current" number: the count
your own run prints is the current truth for your tree.

**Lint and format** are gated mechanically on every edit, but run by hand any time:

```powershell
python -m ruff format .
python -m ruff check .
```

---

## 7. The C# client

Use the SDK pinned in [global.json](../global.json). Start with the independent
[C# contract checks](verification.md#check-the-c-integration-separately) to compile the core,
adapter, and starter sample and exercise loopback HTTP without a running backend.
For the live-backend harness, build:

```powershell
dotnet build client\NpcMemory.Core\NpcMemory.Core.csproj -c Release
dotnet build client\NpcMemory.Harness\NpcMemory.Harness.csproj
```

The console harness plays every demo beat headless against a running server — this is the
interop gate. With the service up on a scratch database:

```powershell
dotnet run --project client\NpcMemory.Harness -- --base-url http://127.0.0.1:8000
```

It provisions its own agent and ends with `ALL HARNESS BEATS PASSED (N checks)`.
Use a scratch database: this harness writes observations and corrections.

### The Unity client is source, not a DLL

Since F2 (2026-09-12) the core is not a committed DLL. Its source lives in the embedded UPM
package at `unity\Packages\com.jacksonzane.twicetold-npc\Runtime\Core\`, which Unity compiles
directly, and `client\NpcMemory.Core\NpcMemory.Core.csproj` compiles the very same files for the
console harness (an `EnableDefaultCompileItems=false` glob points at the package path). So a
change under `Runtime\Core\` reaches both hosts with no copy step: rebuild the harness (above)
to gate it on the dotnet side, and re-open Unity so it recompiles.

---

## 8. Unity

Open `unity\` with Unity 6. On first open it resolves packages. The client itself is the
embedded package at `unity\Packages\com.jacksonzane.twicetold-npc`
(asmdefs `NpcMemory.Core`, the engine-agnostic core, and `NpcMemory.Unity`, the adapter); Unity
compiles it in place, and its `com.unity.nuget.newtonsoft-json` dependency is what pulls in
Newtonsoft.Json.

`Assets/Scenes/VillageScene.unity` is the only scene in player Build Settings. It is the
playable low-poly village presentation: five dressed skinned Humanoids, the replayable
forgotten-gold event, and stable dialogue/observation anchors for Henry and Joan. Open that
scene for presentation work. For its real-provider recording, follow [the village reproduction
guide](../data/demo/README.md). `VillageDemoBackend` attaches when that guide's local session
manifest exists and connects the scene callbacks to the provisioned witnesses. The underlying
[scene integration seam](../unity/Assets/Scripts/Village/NPC_INTEGRATION.md) defines stable IDs,
callbacks, and hand/socket anchors. This Unity workflow is optional for backend or Python use.

`SampleScene` remains on disk only as the old adapter/dev-tool rig. It is not a source of
VillageScene content and is not in Build Settings. If the embedded client package needs a
live-backend smoke test, use its `NpcMemoryNpc` / `NpcDemoDriver` rig in attach mode
(`autoProvision` off): load the demo database first (`python -m app.demo_loader --fresh` — it
prints the agent id), paste that id into `agentIdOverride`, and set `baseUrl` to the running
service. To run its scripted Play-mode verification beats instead, temporarily flip
`autoProvision` AND `autoRun` on against a fake-mode serve on a scratch DB. Do that gate
before pasting a demo agent id: autoRun replays scripted observes into whichever agent the
adapter holds.

---

## 9. Optional: MCP servers

A read-only Postgres MCP runs on the development machine as a convenience for inspecting the
database. Nothing in the service depends on it.

---

## Teardown

```powershell
docker compose down          # stops the stack, keeps the volume and the image
docker compose down -v       # also deletes the database volume (the memories)
docker image rm twicetold-api    # reclaim the built API image when you no longer need it
```

`down -v` removes the volume but never the image; the image rebuilds from cache in seconds on
the next `up -d --build`.
