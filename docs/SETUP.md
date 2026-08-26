# longmem-npc — setup

From a fresh clone to a running system. **Windows 11 / PowerShell**; every command below is
PowerShell with backslash paths (a project rule, not a preference — see `CLAUDE.md`).

Written 2026-07-28. Before it existed, the bring-up path lived only inside `requirements.txt`'s
header comment and scattered session-log entries, and `docker compose up` appeared in no document
at all. If you change how the project starts, change it here.

---

## 0. Prerequisites

| Thing | Version | Notes |
|---|---|---|
| Python | 3.14, on PATH | global install, not a venv — the project assumes this |
| Docker Desktop | current | must be *running*, not just installed |
| .NET SDK | 8.0+ | only for the C# client and console harness |
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

The first observe in a process pays a multi-minute lazy load of spaCy + fastcoref. That is
expected, and it is why the test suite marks those scenarios `nlp` and the turn-end hook skips
them.

---

## 2. Environment file

```powershell
Copy-Item .env.example .env
```

Then edit `.env`. The template documents every key. Two things that have actually caused
failures:

- **One `KEY=VALUE` per line.** No inline comments after a value, no wrapped lines. A
  consolidated multi-line price note once crashed `load_settings` on every run that read prices.
- **`DATABASE_URI` must name the product database** (`longmem`). Scratch databases are created
  and dropped by the fixtures; never point this at one.

Verify without printing anything:

```powershell
python -c "from app.config import load_settings; load_settings(); print('config ok')"
```

`.env` is gitignored and must stay that way. `LONGMEM_PROVIDER_MODE=fake` (the template default)
runs offline and keyless — everything below works without an API key.

---

## 3. Database

```powershell
docker compose up -d
docker ps --filter name=longmem-pg --format "{{.Names}} {{.Status}}"
```

Wait for `(healthy)`. Compose reads the same `.env`, so `POSTGRES_USER` / `POSTGRES_PASSWORD` /
`POSTGRES_DB` must agree with `DATABASE_URI`.

Apply the schema:

```powershell
python db\migrate.py
```

First run applies migrations 001–008 and records each in `schema_migrations` **in the same
transaction as its DDL** — a half-applied migration can never be logged complete. Re-running is a
clean no-op:

```
Up to date: 8 migration(s) applied, 0 pending.
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

- `http://127.0.0.1:8000/docs` — the generated OpenAPI surface (fifteen routes; `/ledger` and
  `/v1/ledger/turns` are deliberately `include_in_schema=False`)
- `http://127.0.0.1:8000/ledger` — **The Ledger**, the browser inspector. Paste an agent UUID to
  see its memories, and click one to see the immutable observation beside both version chains
  with superseded rows greyed but present.

---

## 5. Drive it from the REPL

Provision an agent (`POST /v1/agents`), then:

```powershell
python -m app.cli --agent <agent-uuid> --debug
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

Two systems, deliberately distinct — see `docs\README.md` for what each is for.

**The suite** (193 scenarios, self-managing scratch DB, no arguments needed):

```powershell
python -m pytest tests -q
python -m pytest tests -q -m "not nlp"   # 178, the turn-end subset — seconds, not minutes
```

Postgres unreachable ⇒ every scenario skips loudly and the run exits green, by ruling.

**The walkers** (fifteen structural done-when scripts) need a scratch DB you create yourself:

```powershell
$scratch = "postgresql://longmem:change-me@localhost:5432/longmem_test"
docker exec longmem-pg psql -U longmem -d postgres -c "CREATE DATABASE longmem_test"
python db\migrate.py --database-uri $scratch
python tests\verify_write_path.py --database-uri $scratch
# ... verify_prewarm (C7-B, 2026-08-18), verify_concurrency (C7-A, 2026-08-18),
#     verify_purge (C6, 2026-08-18), verify_agent_state (C5, 2026-08-17),
#     verify_dissonance (C4, 2026-08-17), verify_compiler (C3, 2026-08-17),
#     verify_reflection (C2, 2026-08-15), verify_deferred_writes (C1, 2026-08-12),
#     verify_read_path, verify_cli_harness, verify_gate, verify_reconstruction,
#     verify_authorial_correction, verify_fact_correction
docker exec longmem-pg psql -U longmem -d postgres -c "DROP DATABASE longmem_test WITH (FORCE)"
```

Run them serially on a FRESH scratch, elder walkers before `verify_dissonance` (the four
newest — agent_state, purge, concurrency, prewarm — are id-scoped and re-runnable, so their
position is free) — two of the
correction walkers assert the corrections table is empty of diegetic rows, which is true in
sweep order on a fresh scratch and false after a dissonance run (the shared-scratch
fragility recorded in `status.md`'s carried item; `verify_reflection` additionally requires
a fresh scratch for its own re-run).

Each prints `ALL CHECKS PASSED (N assertions)` and exits non-zero on the first failure. Assertion
counts grow whenever a layer is re-opened, so there is no single "current" number: each
`docs\floors.md` row records the count at the time that layer was verified, and the newest run is
in the latest `docs\session-log.md` entry.

**Lint and format** are gated mechanically on every edit, but run by hand any time:

```powershell
python -m ruff format .
python -m ruff check .
```

---

## 7. The C# client

```powershell
dotnet build client\NpcMemory.Core\NpcMemory.Core.csproj -c Release
dotnet build client\NpcMemory.Harness\NpcMemory.Harness.csproj
```

The console harness plays every demo beat headless against a running server — this is the
interop gate. With the service up on a scratch database:

```powershell
dotnet run --project client\NpcMemory.Harness -- --base-url http://127.0.0.1:8000
```

It provisions its own agent and ends with `ALL HARNESS BEATS PASSED (N checks)` — the count
grows with each client build, so trust the line, not a number here (this sentence pinned "32"
while the gate stood at 36, its second rot; reworded 2026-08-17). Point it
at a scratch DB, not the product one — it writes.

### Refreshing the Unity plugin DLL

Unity consumes the core as a committed DLL because there is no package path to it. **Any change
under `client\NpcMemory.Core\` requires this copy, or Unity silently runs the old code:**

```powershell
dotnet build client\NpcMemory.Core\NpcMemory.Core.csproj -c Release
Copy-Item client\NpcMemory.Core\bin\Release\netstandard2.1\NpcMemory.Core.dll `
          unity\Assets\Plugins\NpcMemory\NpcMemory.Core.dll -Force
```

Then re-run the harness (proves the built core still passes) and re-open Unity so it reimports.

---

## 8. Unity

Open `unity\` with Unity 6. On first open it resolves packages, including the MCP for Unity
bridge from the git URL in `unity\Packages\manifest.json` (the resolved copy is gitignored).
Newtonsoft.Json comes from `com.unity.nuget.newtonsoft-json`.

The gray-box scene holds the Branwen capsule (nameplate `Branwen` since E2, 2026-08-19) with
`NpcMemoryNpc` (the adapter) and `NpcDemoDriver` (the IMGUI dev-tool overlay). The committed
scene is attach-mode (`autoProvision` off): load the demo database first
(`python -m app.demo_loader --fresh` — it prints the agent id), paste that id into the
adapter's `agentIdOverride`, and set `baseUrl` to the running service. To play the scripted
Play-mode verification beats instead, temporarily flip `autoProvision` AND `autoRun` on
against a fake-mode serve on a scratch DB — the beats provision their own agent and log
`[npc-demo]` receipts to the console. Do that gate BEFORE pasting a demo agent id: autoRun
replays scripted observes into whatever agent the adapter holds
(`docs\demo-beat-script.md` has the full rehearsal ordering).

Scene-manipulation calls through the MCP bridge fail while the Editor is in Play mode — stop
play first.

---

## 9. Optional: MCP servers

`docs\mcp-setup.md` is the reproduction runbook for the read-only Postgres MCP and the Unity
bridge. Both are development conveniences; nothing in the service depends on them.

---

## Teardown

```powershell
docker compose down          # keeps the volume
docker compose down -v       # deletes the database volume too
```
