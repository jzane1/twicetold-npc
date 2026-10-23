# Run a private memory service

The supported starting topology is **one application server → one private memory API process
→ one PostgreSQL 16/pgvector database and the configured model providers**. Run the application
server on the same host as the ordinary Compose stack. It calls `http://127.0.0.1:8000`;
the API reaches Postgres as `db:5432` on the Compose network. Players and browsers talk to
your application server. Provider credentials stay with the memory service.

Start with [the executable trial](first-run.md), then [the application example](python-integration.md).
The [evidence guide](evidence.md) separates demonstrated behavior from quality claims. This page
defines the deployment boundary; it is not a claim of production scale or high availability.

## Start, inspect, upgrade

Follow [setup](SETUP.md) to create `.env`, choose providers and set database credentials.
Use the ordinary stack for a persistent application; the demo credentials are disposable.

```powershell
docker compose up -d --build --wait --wait-timeout 360
docker compose ps
Invoke-RestMethod http://127.0.0.1:8000/health/ready
```

Both published ports in `docker-compose.yml` bind loopback. Do not publish them on a public
interface. The API has **no authentication, tenant authorization or rate limiting**: anyone
with access can inspect, alter and purge any agent. The Ledger, API docs and health routes share
this boundary. `TWICETOLD_ALLOWED_HOSTS` validates Host headers, but is not authentication.
For a remote application server, supplying a private network plus authenticated TLS ingress,
firewall rules and application-level agent ownership is the integrator's responsibility.

Before an upgrade, stop application traffic, stop all memory writers, and take the backup below.
Apply migrations once, then start one matching API version. Startup refuses a missing, pending
or newer migration ledger, or an incompatible embedding binding, before NLP/model construction.
Migrations are forward-only: rollback means restoring the prior database backup with its prior
code/configuration. Do not run old and new API versions against the same database during migration.
Changing chat models is allowed; changing embedding mode/model/endpoint requires a new database
or explicit re-embedding work, which this repository does not supply.

## Health has a defined meaning

| Probe | Success means | Failure behavior |
| --- | --- | --- |
| `GET /health/live` | The HTTP process can answer | No database or provider request |
| `GET /health/ready` | Startup finished, a pooled DB connection works, pgvector exists, the migration ledger matches this revision, the embedding binding matches, all three worker tasks are alive | HTTP 503 and fixed status fields; whole DB check bounded to two seconds, including pool wait |
| `python -m app.doctor` | Configuration/schema/embedding diagnostics | Nonzero on failure; no paid calls |

Compose uses `/health/ready`. A database outage makes the API unready while liveness can stay
200; readiness recovers when connectivity returns. Responses are not cached and expose no DSNs,
keys, raw exceptions or model responses. The check reads metadata only: it neither binds an
empty store nor modifies memory rows. A 200 does not verify every table/index or data checksum.

Readiness makes **no provider requests**. It does not establish provider availability, credentials,
model quality, sufficient capacity, or successful background work. Workers catch individual job
failures and continue; inspect enrichment/reflection/compiler run records and service logs.
Optional reflection/compiler model configuration is validated at first use, not by readiness.
Use the explicitly billable `python -m app.doctor --probe-providers` when you want connectivity
checks, then a real-provider first-run scenario for behavior. Monitor response degradation flags
as well as HTTP status: an accepted observation may carry `scoring_failed` or `embedding_failed`.

Docker marks a running container unhealthy without automatically restarting it. See
[Compose healthcheck semantics](https://docs.docker.com/reference/compose-file/services/#healthcheck).
Set your own alerts and recovery policy; restarting continuously during a database outage is not
a substitute for repairing the dependency.

## One process per database; bounded calls, not bounded traffic

Use the shipped `python -m app.serve` process. Do not add `uvicorn --workers`, multiple API replicas,
or a concurrent REPL/load driver against the same store. Each runtime starts deferred enrichment,
reflection and compiler workers. Reflection/compiler sweeps have no distributed leader lease;
multiple runtimes can duplicate provider work and race logical updates. Deferred claims use row
locks and attempt accounting, but are not a deployment-wide exactly-once scheduler. Crash recovery
can retry work and incur provider cost. This limit is documented, not enforced by a database lease.

`TWICETOLD_MAX_CONCURRENT_MODEL_CALLS=8` and `TWICETOLD_DB_POOL_MAX_SIZE=8` are the defaults.
The former caps in-flight provider calls **per process**, including workers and streams; it does
not cap requests, waiting tasks, CPU NLP work, global tokens/minute or spend. Increasing replicas
multiplies it. The database pool can also saturate, making readiness fail until demand subsides.
Load-test your own workload before increasing either setting. There is no advertised requests/sec
capacity, tenant isolation, admission queue limit, global rate limiter or availability SLA.

Reflection and compilation auto-pulls are off by default and opt in per agent. Configure their
models and budgets before enabling them. Deferred enrichment always drains pending work, even
after new-write deferral is switched off. Reflection/compilation failures can be retried each poll;
there is no global billing ceiling. The Ledger's recent-turn feed is process-local and disappears
on restart. Durable memory chains, observation receipts and reconstruction caches live in Postgres.

## Back up and restore

Keep a database dump **and** the service revision/image, configuration and embedding model/endpoint
identity together. Keep secrets separately in your secret store. Backups contain observations,
identity, past versions and receipts; keep them private, encrypted off-host and subject to your own
retention policy. A database backup is not a backup of application-owned user/agent mapping or chat
state. Back those up too. This is a manual recovery procedure, not continuous recovery or failover.

The commands below use the default database user/name `twicetold`; set these two non-secret
variables to your configured values. Run in PowerShell from the repo root. First pause your
application's traffic and stop every other writer, including REPL/load processes.

```powershell
$dbUser = 'twicetold'
$sourceDb = 'twicetold'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupDir = Join-Path (Get-Location) "artifacts/backups/$stamp"
New-Item -ItemType Directory -Path $backupDir -ErrorAction Stop | Out-Null
$containerDump = "/tmp/twicetold-$stamp.dump"
docker compose stop api
if ($LASTEXITCODE -ne 0) { throw 'Could not stop API' }
docker compose exec -T db pg_dump -U $dbUser -d $sourceDb --format=custom --file=$containerDump
if ($LASTEXITCODE -ne 0) { throw 'Backup failed; keep traffic paused' }
docker compose cp "db:$containerDump" (Join-Path $backupDir 'database.dump')
if ($LASTEXITCODE -ne 0) { throw 'Backup copy failed; keep traffic paused' }
Get-FileHash (Join-Path $backupDir 'database.dump') -Algorithm SHA256
```

The custom archive is written inside the container and copied as a file, avoiding binary shell
redirection. PostgreSQL provides a consistent snapshot even with concurrent writers; quiescing here
also makes the application cutover explicit. This follows [PostgreSQL's dump guidance](https://www.postgresql.org/docs/16/backup-dump.html).
Copy the archive off-host; `artifacts/` is ignored by Git. Do not delete the volume to “test” a backup.

Restore into a **new empty database** on PostgreSQL 16 with pgvector available, using the matching
service revision and configuration. This example restores on the same instance and refuses a name
collision. It keeps the source database intact; do not add `--clean` or drop the original database.

```powershell
$restoreDb = 'twicetold_restore_' + (Get-Date -Format 'yyyyMMddHHmmss')
docker compose cp (Join-Path $backupDir 'database.dump') "db:$containerDump"
if ($LASTEXITCODE -ne 0) { throw 'Archive copy failed' }
docker compose exec -T db createdb -U $dbUser --template=template0 $restoreDb
if ($LASTEXITCODE -ne 0) { throw 'Destination creation failed' }
docker compose exec -T db pg_restore -U $dbUser -d $restoreDb --exit-on-error --single-transaction --no-owner --no-privileges $containerDump
if ($LASTEXITCODE -ne 0) { throw 'Restore failed; do not switch traffic' }
docker compose exec -T db psql -X -U $dbUser -d $restoreDb -v ON_ERROR_STOP=1 -c 'SELECT count(*) FROM schema_migrations; SELECT count(*) FROM memories; SELECT count(*) FROM observation_receipts;'
if ($LASTEXITCODE -ne 0) { throw 'Restored database check failed' }
```

`--no-owner --no-privileges` restores under the restore role; it does not preserve a custom role/grant
layout. Recreate any deployment-specific roles/grants separately. See [pg_restore options](https://www.postgresql.org/docs/16/app-pgrestore.html).
The whole dump includes the migration ledger, embedding binding, chains and vector values.

While traffic remains paused, point `POSTGRES_DB` and `DATABASE_URI` in `.env` at the restored
database (preserve the original values for rollback). Then:

```powershell
docker compose run --rm --no-deps api python -m app.doctor
if ($LASTEXITCODE -ne 0) { throw 'Restored configuration is incompatible' }
docker compose up -d --wait --wait-timeout 360 api
if ($LASTEXITCODE -ne 0) { throw 'Restored service is not ready' }
Invoke-RestMethod http://127.0.0.1:8000/health/ready
```

Check known agent IDs, original/corrected chains, a pinned memory and an exact observation replay
through your application before resuming traffic. Preserve the old store until you accept the result.
Never resume both stores as active writers. Reads can reconstruct/write back, so an end-to-end
acceptance check belongs on the restored candidate, not an immutable backup.

The [verification script](verification.md) rehearses this dump/create/restore sequence with disposable
demo data. It verifies every public table's row count and complete-row hash (including vectors,
historical versions and receipts), runs the doctor and opens the normal runtime pool on the restored
copy. It also tests HTTP readiness during an actual DB stop and recovery. The rehearsal does not
measure recovery time for your data volume or replace periodic restore drills with off-host backups.
