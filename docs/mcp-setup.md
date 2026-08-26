# MCP setup runbook

MCP (Model Context Protocol) servers expose external systems — the live Postgres database, the
running Unity Editor — as tools Claude Code can call. Tools appear as `mcp__<server>__<tool>` and
obey normal permission rules. Check connection status any time with `/mcp` inside a session, or
`claude mcp list` from the shell.

Scopes: `claude mcp add` defaults to **local** scope (private to this machine + project; nothing
committed — right for anything holding credentials). `--scope project` writes a committed
`.mcp.json` (never put credentials in it). `--scope user` applies across all projects.

> **Both servers are LIVE** *(status corrected 2026-07-28 — this runbook still read as forward-
> looking after both had gone live)*. Postgres went live 2026-07-13 with the migration-01
> container; MCP for Unity went live 2026-07-27 with the Unity project (verified by a read probe
> plus a cube round-trip). `claude mcp list` should show both `✓ Connected`. What follows is now
> a **reproduction runbook** — for a fresh machine, or when a connection breaks — not a schedule.

Each section records the go-live moment it was tied to in the build order, which is why the
prerequisites read the way they do.

---

## 1. Postgres — go-live: the moment the migration-01 container exists

**Server:** Postgres MCP Pro (`crystaldba/postgres-mcp`), run in **restricted mode**, which wraps
every call in a `READ ONLY` transaction — write protection enforced by Postgres itself.

**Never use** `@modelcontextprotocol/server-postgres`: deprecated and archived in May 2025 after a
SQL-injection disclosure that bypassed its read-only mode. Old tutorials still recommend it.

**One-time tooling** (uv also serves the Unity server later):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
# restart the terminal so uv is on PATH, then:
uv tool install postgres-mcp --python 3.13
```

> **Why `--python 3.13`** (deviation recorded in `decisions.md`, 2026-07-13): postgres-mcp's
> `pglast` dependency has no Python 3.14 wheel and won't build from source on Windows, so the MCP
> runs in an isolated uv-managed 3.13 venv. The project itself stays on Python 3.14 — the MCP is a
> standalone server process, never imported by project code. Drop the flag once `pglast` ships a
> 3.14 wheel.

**Register with Claude Code** (local scope; connection string must match `.env`):

```powershell
claude mcp add postgres --env DATABASE_URI=postgresql://USER:PASSWORD@localhost:5432/DBNAME -- postgres-mcp --access-mode=restricted
```

Restart Claude Code, then verify with `/mcp` (postgres should show connected) and a live prompt:
*"Using the postgres MCP tools, list the tables and describe the memories table"* — the answer
should match `docs\migration-01.md` column for column, **plus everything migrations 002–008 added
on top of it** *(pointer corrected 2026-07-28, extended at F0 2026-08-26: migration-01.md
documents only the foundational schema, so it is no longer the whole truth —
`memory_fact_versions` and its indexes came with 002, `memory_fact_versions.entities` with 003,
the lexical FTS GIN with 004, `memories.escalation_failed` with 005, the deferred-write columns +
`memory_enrichment_runs` with 006, `reflection_runs` with 007, and `compiled_bundles` +
`compiler_runs` with 008. Read `db\migrations\*.sql` for the current shape; `schema_migrations`
should list exactly 001–008.)*

**Tools exposed:** schema listing (`list_schemas`, `list_objects`), object detail
(`get_object_details` — columns, constraints, indexes), read-only `execute_sql`, `explain_query`,
and database health checks.

**Follow-up edit — give the verifier eyes.** `.claude/agents/floor-verifier.md` restricts its
tools, which also excludes MCP. At go-live, **two** frontmatter changes are required (proven live
2026-07-13 — the `mcpServers` line alone is NOT sufficient):

```yaml
tools: Read, Grep, Glob, Bash, mcp__postgres   # the mcp__postgres pattern is load-bearing
mcpServers: postgres
```

An explicit `tools:` allowlist filters out every `mcp__postgres__*` tool unless the `mcp__postgres`
pattern is in it; `mcpServers:` only authorizes the server connection. Also add one line to the
agent body: "Prefer the postgres MCP tools over psql for schema and row-state checks." Agent
definitions load at Claude Code startup — restart before expecting the tools to appear. From then
on, verification asserts against live rows and constraints, not against what the migration script
says it did.

**Defense in depth, later:** restricted mode is fine for the local dev database. If this server
ever points at anything shared, also connect through a dedicated SELECT-only Postgres role — the
database role is the backstop no server bug can bypass.

---

## 2. Unity — go-live: the moment the Unity project is created (after the CLI slice)

**Server:** MCP for Unity (`CoplayDev/unity-mcp`). Requirements: Unity 2021.3 LTS → 6.x (we are
on Unity 6) and Python 3.10+ via uv (installed above).

**Install, inside the Unity Editor:**

1. Window → Package Manager → **+** → *Add package from git URL...* →
   `https://github.com/CoplayDev/unity-mcp.git?path=/MCPForUnity#main`
   (pin a release tag instead of `#main` if reproducibility matters that week).
2. A setup wizard opens automatically on import: it verifies Python and uv (and guides the
   install if either is missing), then lists the MCP clients detected on the machine. Select
   Claude Code → **Configure Selected**.
3. The panel lives at Window → MCP for Unity: start/stop the bridge, switch transport
   (HTTP vs stdio), reconfigure clients. Status should read **Connected**.
4. Restart Claude Code so it picks up the new server, then verify with `/mcp` and a live prompt:
   *"List the objects in the current scene"* or *"Create a cube at the origin."*

**What it enables:** creating and modifying GameObjects, components, prefabs, and scenes; editing
and attaching scripts; reading the scene hierarchy; and reading the Unity console — so a compile
or runtime error is something Claude sees and fixes itself, not something to copy-paste.

**Known gotchas:**
- Switching transport (HTTP ↔ stdio) in the MCP for Unity window requires restarting Claude Code.
- Some operations (scene manipulation, prefab editing) fail while Play mode is active — stop the
  game before scene-building commands.
- Do not install Unity's own AI Assistant package alongside: known
  System.Collections.Immutable assembly conflict on recent Unity versions.
- With multiple Unity projects open, tell Claude explicitly which project root to target.

---

## Hygiene

- Credentials never enter a committed file: local scope for the Postgres server, `.env` as the
  single source for the connection string. If a `.mcp.json` ever appears in this repo, it must
  contain no secrets.
- Review any MCP server before trusting it — it runs with your permissions, same as a hook.
- Removal: `claude mcp remove <name>`.
