"""conftest.py — structural pytest suite fixtures (docs\\test-suite.md).

The suite is the CI-shaped regression net over the verified floors: offline,
keyless (fake providers pinned regardless of .env), deterministic, and
scratch-DB self-managing. It runs on `twicetold_suite_<pid>` — deliberately
distinct from the walkers' `twicetold_test`, so a run can never collide with a
walker loop, AND per-process so two suite runs never collide with EACH OTHER
(ruled 2026-07-20): the setup `DROP ... WITH (FORCE)` of a shared fixed-name
DB would force-kill a concurrently-running suite's live connections
(AdminShutdown). The Stop hook fires a run at every turn-end, so rapid
consecutive turns can overlap runs — the pid suffix makes each run own its
DB. The product `twicetold` is never connected to.

Stop-hook contract (ruled 2026-07-20): scenarios that CALL the write pass at
the service level (observe, or the correction verb with its NER merge) carry
the `nlp` marker — they trigger the lazy spaCy+fastcoref load (minutes, once
per process) — and the hook runs `-m "not nlp"`. Unmarked scenarios seed at
the db layer through the real `db.insert_observation` with the pure fake
embedding, so they never touch the loaders.

Postgres unreachable => every test SKIPS with a loud warning and the run
exits green (ruled 2026-07-20 — the Stop hook's existing
dormant-when-prerequisites-missing philosophy).

Per-scenario isolation: product tables on the scratch DB are truncated
before each test. That is test-harness reset of a disposable scratch store —
the non-destructive invariant governs the app's write surface on stored
memory content, not the fixture loop (the walkers drop whole scratch DBs).
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import psycopg
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # tests\ helpers

from psycopg.types.json import Jsonb
from scratch_uri import scratch_uri

from app import db
from app.config import Settings
from app.providers import (
    FakeEmbeddingProvider,
    FakeEscalationProvider,
    FakeProseProvider,
    FakeReconstructionProvider,
    FakeWriteProvider,
    Providers,
)
from app.schemas import DialogueTurnResult

# Per-process name: two overlapping runs (the Stop hook can fire one at every
# turn-end) never share a scratch DB, so no run's force-drop can kill another's
# connections. A hard-killed run leaks an empty `twicetold_suite_<pid>`; the next
# same-pid run drops it (DROP IF EXISTS), and it never collides with a live run.
SUITE_DB = f"twicetold_suite_{os.getpid()}"
NOW = datetime(2026, 7, 20, 12, 0, 0, tzinfo=timezone.utc)
SEED_PROSE = "The ford keeper, wary of strangers."

# --- per-set agent configs -------------------------------------------------
# decay_classes / decay_class_default are ordinary integrator config.
# reconstruction_theta = 0 and gate_enabled = 0 are FIXTURE-ONLY pins
# (production runs theta 0.5 and the gate active): each set knob-disables the
# stages it is NOT asserting, so failures have a single cause — the walker
# precedent (verify_read_path.py / verify_cli_harness.py pins).
BASE_CONFIG = {
    "decay_classes": {"episodic": 86400, "semantic": 604800},
    "decay_class_default": "episodic",
}
# Sets A/B + most degradation cases: v1 verbatim serving, no gate.
V1_CONFIG = {**BASE_CONFIG, "reconstruction_theta": 0.0, "gate_enabled": 0.0}
# Set C: reconstruction at the PRODUCTION default theta; gate pinned off.
RECON_CONFIG = {**BASE_CONFIG, "gate_enabled": 0.0}
# Set D: gate at PRODUCTION defaults; reconstruction pinned inert.
GATE_CONFIG = {**BASE_CONFIG, "reconstruction_theta": 0.0}

_EMBEDDER = FakeEmbeddingProvider()
_UNSET = object()


def embed_text(text: str) -> list[float]:
    """The pure locality-sensitive fake embedding of one text (a FIXTURE
    property — production uses real embeddings). Echo text => distance ~0."""
    return _EMBEDDER.embed([text]).vectors[0]


def _swap_db(uri: str, name: str) -> str:
    """Delegates to the shared, verified rewrite — see tests\\scratch_uri.py
    for why a path-only swap is not safe enough to sit in front of a
    per-test TRUNCATE."""
    return scratch_uri(uri, name)


def _base_uri() -> str | None:
    """DATABASE_URI without ever printing it: process env first (the CI
    shape), then the repo .env via load_env (which sys.exits when absent)."""
    if os.environ.get("DATABASE_URI"):
        return os.environ["DATABASE_URI"]
    try:
        from app.config import load_env

        return load_env()["DATABASE_URI"]
    except SystemExit:
        return None


@dataclass(frozen=True)
class SuiteEnv:
    database_uri: str
    settings: Settings


@pytest.fixture(scope="session")
def suite_env():
    """Create + migrate the scratch suite DB once; drop it at session end.
    Unreachable Postgres => loud warning + session-wide skip, exit green."""
    base = _base_uri()
    if base is None:
        warnings.warn(
            "STRUCTURAL SUITE SKIPPED: no DATABASE_URI (.env or process env)",
            stacklevel=1,
        )
        pytest.skip("postgres unreachable: no DATABASE_URI configured")
    admin_uri = _swap_db(base, "postgres")
    try:
        admin = psycopg.connect(admin_uri, connect_timeout=3, autocommit=True)
    except psycopg.OperationalError:
        warnings.warn(
            "STRUCTURAL SUITE SKIPPED: postgres unreachable — 0 scenarios ran "
            "(start the twicetold-pg container to run the suite)",
            stacklevel=1,
        )
        pytest.skip("postgres unreachable")
    with admin:
        admin.execute(f"DROP DATABASE IF EXISTS {SUITE_DB} WITH (FORCE)")
        admin.execute(f"CREATE DATABASE {SUITE_DB}")
    suite_uri = _swap_db(base, SUITE_DB)
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "db" / "migrate.py"),
            "--database-uri",
            suite_uri,
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    if proc.returncode != 0:
        # migrate.py never echoes the URI, so its output is safe to surface.
        pytest.fail(f"scratch migrate failed:\n{proc.stdout}\n{proc.stderr}")
    yield SuiteEnv(
        database_uri=suite_uri,
        settings=Settings(database_uri=suite_uri, provider_mode="fake"),
    )
    with psycopg.connect(admin_uri, connect_timeout=3, autocommit=True) as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {SUITE_DB} WITH (FORCE)")


@pytest.fixture()
def scene(suite_env: SuiteEnv) -> SuiteEnv:
    """A pristine scratch store per scenario (schema kept, rows gone)."""
    with psycopg.connect(suite_env.database_uri, autocommit=True) as conn:
        rows = conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
            "AND tablename <> 'schema_migrations'"
        ).fetchall()
        conn.execute(f"TRUNCATE {', '.join(r[0] for r in rows)} CASCADE")
    return suite_env


@dataclass
class Ctx:
    """Per-scenario context living inside one SelectorEventLoop: the open
    pool, the fake-mode settings, and the shared structural helpers."""

    pool: object
    settings: Settings

    # -- services -----------------------------------------------------------
    def providers(self, **overrides) -> Providers:
        return Providers(
            write=overrides.get("write", FakeWriteProvider()),
            escalation=overrides.get("escalation", FakeEscalationProvider()),
            embedding=overrides.get("embedding", FakeEmbeddingProvider()),
            # The streaming prose provider — the dialogue turn's only model
            # call since the A1 re-shape (2026-08-04) — overridable for the
            # degradation cases.
            dialogue=overrides.get("dialogue", FakeProseProvider()),
            reconstruction=overrides.get(
                "reconstruction", FakeReconstructionProvider()
            ),
        )

    def retrieval(self, **overrides):
        from app.retrieval import RetrievalService

        return RetrievalService(self.pool, self.providers(**overrides), self.settings)

    def ingest(self, **overrides):
        from app.ingest import IngestService

        return IngestService(self.pool, self.providers(**overrides), self.settings)

    def worker(self, *, defaults: dict | None = None, **overrides):
        """A deferred-write worker over this scenario's pool (Set K,
        deferred-writes.md). Never started — tests call `drain()` directly,
        the deterministic entry (no timers). `defaults` overrides service
        defaults (e.g. a pinned deferred_max_attempts) on a copied Settings."""
        from dataclasses import replace

        from app.deferred import DeferredWriteWorker

        settings = self.settings
        if defaults:
            settings = replace(settings, defaults={**settings.defaults, **defaults})
        return DeferredWriteWorker(self.pool, self.providers(**overrides), settings)

    def _settings_with(self, defaults: dict | None) -> Settings:
        from dataclasses import replace

        if not defaults:
            return self.settings
        return replace(self.settings, defaults={**self.settings.defaults, **defaults})

    def reflection(self, *, defaults: dict | None = None, provider=None, **overrides):
        """The reflect seam over this scenario's pool (Set L, reflection.md).
        `provider` injects a reflection-provider fake through the
        keyword-only build seam (ruled 2026-08-15); None means the lazy
        judge-shaped factory (fake mode => FakeReflectionProvider)."""
        from app.reflection import ReflectionService

        return ReflectionService(
            self.pool,
            self.providers(**overrides),
            self._settings_with(defaults),
            reflection_provider=provider,
        )

    def reflection_worker(
        self, *, defaults: dict | None = None, provider=None, **overrides
    ):
        """A reflection worker over this scenario's pool (Set L). Never
        started — tests call `sweep()` directly, the deterministic no-timer
        entry (the Set K drain() precedent)."""
        from app.reflection import ReflectionWorker

        return ReflectionWorker(
            self.pool,
            self.providers(**overrides),
            self._settings_with(defaults),
            reflection_provider=provider,
        )

    def compiler(self, *, defaults: dict | None = None, provider=None, **overrides):
        """The compile seam over this scenario's pool (Set M,
        parameter-compiler.md). `provider` injects a compiler-provider fake
        through the keyword-only build seam (the C2 precedent); None means
        the lazy judge-shaped factory (fake mode => FakeCompilerProvider)."""
        from app.compiler import CompilerService

        return CompilerService(
            self.pool,
            self.providers(**overrides),
            self._settings_with(defaults),
            compiler_provider=provider,
        )

    def compiler_worker(
        self, *, defaults: dict | None = None, provider=None, **overrides
    ):
        """A compiler worker over this scenario's pool (Set M). Never
        started — tests call `sweep()` directly, the deterministic no-timer
        entry (the Set K/L precedent)."""
        from app.compiler import CompilerWorker

        return CompilerWorker(
            self.pool,
            self.providers(**overrides),
            self._settings_with(defaults),
            compiler_provider=provider,
        )

    def dissonance(self, *, defaults: dict | None = None, **overrides):
        """The diegetic-correction seam (Set N, dissonance.md). No provider
        seam of its own: the retell rides the RECONSTRUCTION role (the C4
        ruling), so `reconstruction=` in overrides swaps it like any other
        role fake."""
        from app.dissonance import DissonanceService

        return DissonanceService(
            self.pool, self.providers(**overrides), self._settings_with(defaults)
        )

    # -- fixtures -----------------------------------------------------------
    async def make_agent(
        self,
        name: str,
        config: dict,
        components: tuple = (("Mara", ["the blacksmith"]),),
        seed_identity: str | None = SEED_PROSE,
    ) -> UUID:
        async with self.pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO agents (name, seed_identity, rigidity, "
                "diagnosticity_goal, config) "
                "VALUES (%s, %s, 1.0, %s, %s) RETURNING agent_id",
                (name, seed_identity, "what threatens the ford", Jsonb(dict(config))),
            )
            agent_id = (await cur.fetchone())[0]
            for canonical, aliases in components:
                await cur.execute(
                    "INSERT INTO identity_components (agent_id, canonical, "
                    "aliases, category) VALUES (%s, %s, %s, 'person')",
                    (agent_id, canonical, list(aliases)),
                )
        return agent_id

    async def seed(
        self,
        agent_id: UUID,
        text: str,
        valid_at: datetime,
        *,
        pinned: bool = False,
        decay_class: str = "episodic",
        importance: float = 0.5,
        typology: str = "observed",
        entities: list[str] | None = None,
        embedding=_UNSET,
        spans: tuple = (),
        component_spans: tuple = (),
        event_time: datetime | None = None,
        location_name: str | None = None,
    ) -> db.InsertOutcome:
        """Db-layer seed through the real atomic insert — no write-pass call,
        so unmarked scenarios never trigger the NLP loaders. Values are
        explicit fixture facts (importance chosen, not hash-derived;
        `typology` joined with Set N — the dissonance formula's memory-side
        evidence class is a fixture fact too). `embedding=None` seeds the
        embed-degradation row shape. `component_spans` (Set L, reflection.md
        trim fixtures): (start, end, component_id) triples — spans MATCHED to
        an existing component, the trim rule's evidence unit."""
        vec = embed_text(text) if embedding is _UNSET else embedding
        plan = db.InsertPlan(
            agent_id=agent_id,
            observation_text=text,
            rendered_content=f"[suite seed] {text}",
            valid_at=valid_at,
            importance_raw=importance,
            scoring_failed=False,
            typology=typology,
            typology_confidence=0.9,
            typology_source="declared",
            provenance="lived",
            pinned=pinned,
            decay_class=decay_class,
            decay_class_unknown=False,
            embedding=vec,
            entities=entities,
            spans=(
                [db.SpanPlan(s, e, None, "person") for (s, e) in spans]
                + [
                    db.SpanPlan(s, e, str(cid), "person")
                    for (s, e, cid) in component_spans
                ]
            ),
            event_time=event_time,
            location_name=location_name,
        )
        return await db.insert_observation(self.pool, plan)

    async def add_component(
        self,
        agent_id: UUID,
        canonical: str,
        aliases: tuple = (),
        category: str = "person",
    ) -> UUID:
        """One identity component, id returned — Set L's trim fixtures
        attach span evidence to it via seed(component_spans=...)."""
        async with self.pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO identity_components (agent_id, canonical, "
                "aliases, category) VALUES (%s, %s, %s, %s) "
                "RETURNING component_id",
                (agent_id, canonical, list(aliases), category),
            )
            return (await cur.fetchone())[0]

    async def seed_reflection(
        self,
        agent_id: UUID,
        content: str,
        valid_at: datetime,
        *,
        identity_relevant: bool = True,
        source_memory_ids: tuple = (),
        created_at: datetime | None = None,
        invalid_at: datetime | None = None,
    ) -> UUID:
        """Db-layer reflection seed (Set L, reflection.md — the seed_pending
        precedent): a prior belief row placed directly, so RRR-window,
        consolidation, and pressure fixtures control content, chronology
        (created_at is the RRR window's and the pressure gauge's order key),
        and liveness exactly — no service call, no model."""
        async with self.pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO reflections (agent_id, content, "
                "identity_relevant, source_memory_ids, valid_at, created_at, "
                "invalid_at) VALUES (%s, %s, %s, %s, %s, COALESCE(%s, now()), "
                "%s) RETURNING reflection_id",
                (
                    agent_id,
                    content,
                    identity_relevant,
                    list(source_memory_ids),
                    valid_at,
                    created_at,
                    invalid_at,
                ),
            )
            return (await cur.fetchone())[0]

    async def seed_bundle(
        self,
        agent_id: UUID,
        reflection_id: UUID,
        *,
        scene_type: str = "default",
        w_relevance: float = 1.0,
        w_recency: float = 1.0,
        w_importance: float = 1.0,
        passthrough: dict | None = None,
        created_at: datetime | None = None,
    ) -> UUID:
        """Db-layer compiled-bundle seed (Set M, parameter-compiler.md — the
        seed_reflection precedent): a bundle row placed directly so consume
        fixtures control multipliers, pair membership, and newest-per-pair
        ordering exactly — no service call, no model."""
        async with self.pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO compiled_bundles (agent_id, reflection_id, "
                "scene_type, w_relevance, w_recency, w_importance, "
                "passthrough, created_at) VALUES (%s, %s, %s, %s, %s, %s, "
                "%s, COALESCE(%s, now())) RETURNING bundle_id",
                (
                    agent_id,
                    reflection_id,
                    scene_type,
                    w_relevance,
                    w_recency,
                    w_importance,
                    Jsonb(passthrough or {}),
                    created_at,
                ),
            )
            return (await cur.fetchone())[0]

    async def seed_pending(
        self,
        agent_id: UUID,
        text: str,
        valid_at: datetime,
        *,
        declared_typology: str | None = None,
        declared_confidence: float | None = None,
        triggers: tuple = (),
        entities: list[str] | None = None,
        embedding=_UNSET,
        spans: tuple = (),
        pinned: bool = False,
        decay_class: str = "episodic",
    ) -> db.InsertOutcome:
        """A deferred-mode pending row seeded at the db layer (Set K,
        deferred-writes.md): the raw text IS the `original` head, the
        write-call scalars are NULL (a declared typology stores now — the
        one-shot COALESCE proof rides on it), `enrichment_pending` is set,
        and the persisted trigger names stand in for the NLP evaluation —
        so the worker path never touches the spaCy loaders and Set K stays
        unmarked."""
        vec = embed_text(text) if embedding is _UNSET else embedding
        plan = db.InsertPlan(
            agent_id=agent_id,
            observation_text=text,
            rendered_content=text,
            valid_at=valid_at,
            importance_raw=None,
            scoring_failed=False,
            typology=declared_typology,
            typology_confidence=(
                declared_confidence if declared_typology is not None else None
            ),
            typology_source=("declared" if declared_typology is not None else None),
            provenance="lived",
            pinned=pinned,
            decay_class=decay_class,
            decay_class_unknown=False,
            embedding=vec,
            entities=entities,
            spans=[db.SpanPlan(s, e, None, "person") for (s, e) in spans],
            enrichment_pending=True,
            enrichment_pending_triggers=list(triggers) or None,
        )
        return await db.insert_observation(self.pool, plan)

    # -- structural reads ---------------------------------------------------
    async def fetchall(self, sql: str, *params):
        async with self.pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(sql, params)
            return await cur.fetchall()

    async def fetchrow(self, sql: str, *params):
        rows = await self.fetchall(sql, *params)
        return rows[0] if rows else None

    async def execute(self, sql: str, *params) -> None:
        async with self.pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(sql, params)

    async def chain(self, memory_id: UUID):
        """(write_cause, content, valid_at, invalid_at, detail_id), oldest first."""
        return await self.fetchall(
            "SELECT write_cause, content, valid_at, invalid_at, detail_id "
            "FROM memory_details WHERE memory_id = %s ORDER BY created_at",
            memory_id,
        )

    async def fact_chain(self, memory_id: UUID):
        """(write_cause, basis_text, valid_at, invalid_at, fact_version_id,
        entities), oldest first."""
        return await self.fetchall(
            "SELECT write_cause, basis_text, valid_at, invalid_at, "
            "fact_version_id, entities FROM memory_fact_versions "
            "WHERE memory_id = %s ORDER BY created_at",
            memory_id,
        )

    async def cache_rows(self, memory_id: UUID) -> dict:
        return {
            row[0]: row[1]
            for row in await self.fetchall(
                "SELECT identity_version, rendered_text FROM reconstruction_cache "
                "WHERE memory_id = %s",
                memory_id,
            )
        }


def run_structural(env: SuiteEnv, scenario) -> None:
    """Run one async scenario against the scratch store on a fresh
    SelectorEventLoop (psycopg async cannot run on Windows' default
    ProactorEventLoop — the walker idiom)."""

    async def wrapper():
        pool = db.build_pool(env.database_uri)
        await pool.open()
        try:
            return await scenario(Ctx(pool=pool, settings=env.settings))
        finally:
            await pool.close()

    return asyncio.run(wrapper(), loop_factory=asyncio.SelectorEventLoop)


def by_id(result) -> dict:
    return {item.memory_id: item for item in result.items}


def item_ids(result) -> list:
    return [item.memory_id for item in result.items]


async def drain_turn(gen) -> tuple[str, DialogueTurnResult]:
    """Drain the split-brain seam's async generator (run_dialogue_turn) to
    (streamed_prose, terminal_result) — the non-streaming callers' shape.
    The seam always yields exactly one terminal DialogueTurnResult."""
    chunks: list[str] = []
    result: DialogueTurnResult | None = None
    async for item in gen:
        if isinstance(item, DialogueTurnResult):
            result = item
        else:
            chunks.append(item)
    assert result is not None, "seam yielded no terminal result"
    return "".join(chunks), result
