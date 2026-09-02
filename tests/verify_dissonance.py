"""verify_dissonance.py — structural done-when walker for the dissonance
path + diegetic-correction event (Phase C4; dissonance.md, the eight rulings
dated 2026-08-17; NO migration — the corrections table and both verb enum
values have sat in the schema since 001, ruled this target's scope fact).

Runs the C4 done-when criteria against the SCRATCH database (default: the
.env DATABASE_URI with its database name swapped to `twicetold_test`), with
deterministic fake providers — offline, keyless, and structural-only per
tests\\CLAUDE.md. The event is exercised through `DissonanceService.confront`
(the seam behind POST /v1/events/diegetic-correction and the REPL's
:confront) and once through the session runner (the :confront core). The
write-path and read-path walkers staying byte-identical at their pre-C4
criteria are the zero-retrieval-change evidence; verify_reconstruction owns
the ruling-4 constraint branch (its [13] section, added with C4); THIS
walker owns the mechanism: the schema-in-waiting shape (corrections columns,
CHECK teeth, the fact chain REJECTING the diegetic verbs), the mechanical
verb ladder with hand math, the chain-preserving transaction (corrections
record, coherent timeline, eviction), anchor semantics, the read-path
effect, pin outranked-and-inherited, and the CAS/error ladder with rollback
proof.

Persistent-scratch rule (the verify_compiler precedent, adapted): C4 has no
worker and no kill-switch, so re-runnability rides on scoping instead —
every agent name carries a per-run suffix and every assertion is scoped to
this run's agent/memory ids (never a DB-global count), so prior green runs
on the persistent scratch cannot perturb this one.

Prerequisite (PowerShell):
    python db\\migrate.py --database-uri <scratch-uri>
Run:
    python tests\\verify_dissonance.py [--database-uri <scratch-uri>]

The product `twicetold` DB is never touched.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # tests\ helpers

import psycopg.errors
from psycopg.types.json import Jsonb

from scratch_uri import scratch_uri

from app import db
from app.config import SERVICE_DEFAULTS, Settings
from app.db import build_pool
from app.dissonance import (
    DissonanceCallError,
    DissonanceService,
    decide_dissonance,
    typology_mult,
)
from app.ingest import (
    TYPOLOGY_FALLBACK,
    CorrectionConflictError,
    UnknownAgentError,
    UnknownMemoryError,
)
from app.providers import (
    FailingReconstructionProvider,
    FakeEmbeddingProvider,
    FakeEscalationProvider,
    FakeProseProvider,
    FakeReconstructionProvider,
    FakeWriteProvider,
    MalformedReconstructionProvider,
    Providers,
)
from app.retrieval import RetrievalService
from app.schemas import DialogueInitRequest, DiegeticCorrectionEvent

NOW = datetime(2026, 8, 17, 12, 0, 0, tzinfo=timezone.utc)
T_E = NOW + timedelta(hours=1)
SEED = "A verification NPC, keeper of the crossing ledger."
RUN = uuid4().hex[:8]  # per-run fixture scoping (persistent-scratch rule)

M_EVENT = (
    "Marta stole the silver chalice from the chapel during the harvest "
    "festival and left by the north door."
)
CHALLENGE = (
    "The chalice was misplaced in the crypt by the sexton himself; Marta "
    "was never in the chapel that night."
)

AGENT_CONFIG = {
    "decay_classes": {"episodic": 86400, "semantic": 604800},
    "decay_class_default": "episodic",
    "reconstruction_theta": 0.0,
    "gate_enabled": 0.0,
}

PASSED: list[str] = []


def ok(criterion: str, detail: str = "") -> None:
    PASSED.append(criterion)
    print(f"  PASS  {criterion}" + (f"  ({detail})" if detail else ""))


def fail(criterion: str, detail: str) -> None:
    print(f"  FAIL  {criterion}: {detail}")
    sys.exit(1)


def check(condition: bool, criterion: str, detail: str = "") -> None:
    if not condition:
        fail(criterion, detail or "condition false")
    ok(criterion, detail)


def scratch_uri_from_env() -> str:
    from app.config import load_env

    return scratch_uri(load_env()["DATABASE_URI"], "twicetold_test")


def fake_providers(**overrides) -> Providers:
    return Providers(
        write=overrides.get("write", FakeWriteProvider()),
        escalation=overrides.get("escalation", FakeEscalationProvider()),
        embedding=overrides.get("embedding", FakeEmbeddingProvider()),
        dialogue=overrides.get("dialogue", FakeProseProvider()),
        reconstruction=overrides.get("reconstruction", FakeReconstructionProvider()),
    )


async def make_agent(pool, tag: str, config: dict, *, rigidity: float | None = 1.0):
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO agents (name, seed_identity, rigidity, "
            "diagnosticity_goal, config) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING agent_id",
            (
                f"dissonance-walker-{RUN}-{tag}",
                SEED,
                rigidity,
                "what threatens the crossing",
                Jsonb(config),
            ),
        )
        return (await cur.fetchone())[0]


async def seed_memory(
    pool,
    agent_id,
    text: str,
    valid_at,
    *,
    importance=0.5,
    typology="observed",
    pinned=False,
    spans: tuple = (),
    decay_class="episodic",
):
    """A completed memory at the db layer — the verify_compiler seed shape:
    explicit fixture facts, the pure fake embedding, no NLP pass."""
    vec = FakeEmbeddingProvider().embed([text]).vectors[0]
    plan = db.InsertPlan(
        agent_id=agent_id,
        observation_text=text,
        rendered_content=f"[walker seed] {text}",
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
        entities=None,
        spans=[db.SpanPlan(s, e, None, "person") for (s, e) in spans],
        event_time=None,
        location_name=None,
    )
    outcome = await db.insert_observation(pool, plan)
    return outcome.memory_id


async def fetchall(pool, sql: str, *params):
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(sql, params)
        return await cur.fetchall()


async def fetchrow(pool, sql: str, *params):
    rows = await fetchall(pool, sql, *params)
    return rows[0] if rows else None


async def chain(pool, memory_id):
    """(write_cause, content, valid_at, invalid_at, detail_id), oldest first."""
    return await fetchall(
        pool,
        "SELECT write_cause, content, valid_at, invalid_at, detail_id "
        "FROM memory_details WHERE memory_id = %s ORDER BY created_at",
        memory_id,
    )


def event(agent_id, memory_id, **overrides) -> DiegeticCorrectionEvent:
    base = dict(
        agent_id=agent_id,
        memory_id=memory_id,
        challenge_text=CHALLENGE,
        challenge_typology="observed",
        client_timestamp=T_E,
    )
    base.update(overrides)
    return DiegeticCorrectionEvent(**base)


async def run(uri: str) -> None:
    from urllib.parse import urlsplit

    settings = Settings(database_uri=uri, provider_mode="fake")
    pool = build_pool(uri)
    await pool.open()
    print(f"walker: scratch DB = {urlsplit(uri).path.lstrip('/')}")
    try:
        svc = DissonanceService(pool, fake_providers(), settings)

        # ------------------------------------------------------------------ #
        print("\n-- A. the schema in waiting (001 shape; no migration by ruling)")
        cols = await fetchall(
            pool,
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'corrections'",
        )
        check(
            {c[0] for c in cols}
            == {
                "correction_id",
                "memory_id",
                "detail_id",
                "verb",
                "source_event",
                "created_at",
                "valid_at",
            },
            "A1 corrections carries exactly the 001 columns",
        )
        idx = await fetchrow(
            pool,
            "SELECT indexname FROM pg_indexes "
            "WHERE indexname = 'corrections_memory_id_idx'",
        )
        check(idx is not None, "A2 corrections_memory_id_idx exists")
        agent_a = await make_agent(pool, "schema", AGENT_CONFIG)
        m_probe = await seed_memory(pool, agent_a, M_EVENT, NOW - timedelta(days=2))
        head_probe = (await chain(pool, m_probe))[-1]
        try:
            async with pool.connection() as conn:
                await conn.execute(
                    "INSERT INTO corrections (memory_id, detail_id, verb, "
                    "valid_at) VALUES (%s, %s, 'junk', %s)",
                    (m_probe, head_probe[4], T_E),
                )
            fail("A3 corrections verb CHECK has teeth", "junk verb accepted")
        except psycopg.errors.CheckViolation:
            ok("A3 corrections verb CHECK has teeth (junk verb -> violation)")

        class _Rollback(Exception):
            pass

        for verb in ("rationalization", "update_with_resentment"):
            try:
                async with pool.connection() as conn:
                    async with conn.transaction():
                        # invalid_at set: a dead row dodges the one-live-head
                        # partial index; the write_cause CHECK still fires.
                        await conn.execute(
                            "INSERT INTO memory_details (memory_id, content, "
                            "write_cause, valid_at, invalid_at) "
                            "VALUES (%s, 'probe', %s, %s, %s)",
                            (m_probe, verb, T_E, T_E),
                        )
                        raise _Rollback
            except _Rollback:
                pass
        ok("A4 the telling-chain CHECK admits both diegetic verbs (since 001)")
        for verb in ("rationalization", "update_with_resentment"):
            try:
                async with pool.connection() as conn:
                    await conn.execute(
                        "INSERT INTO memory_fact_versions (memory_id, "
                        "basis_text, write_cause, valid_at, invalid_at) "
                        "VALUES (%s, 'probe', %s, %s, %s)",
                        (m_probe, verb, T_E, T_E),
                    )
                fail(
                    "A5 the fact-chain CHECK rejects the diegetic verbs",
                    f"{verb} accepted — tellings-only ruling violated",
                )
            except psycopg.errors.CheckViolation:
                pass
        ok("A5 the fact-chain CHECK rejects both diegetic verbs (tellings-only)")
        ledger = await fetchall(
            pool, "SELECT version FROM schema_migrations ORDER BY version"
        )
        check(
            len(ledger) == 8 and ledger[-1][0] == "008_parameter_compiler.sql",
            "A6 the ledger records 001-008 — C4 ships NO migration (ruled)",
        )

        # ------------------------------------------------------------------ #
        print("\n-- B. the verb ladder (mechanical, hand math)")
        cfg: dict = {}
        d = decide_dissonance(
            importance_raw=0.5,
            memory_typology="observed",
            rigidity=1.0,
            challenge_typology="observed",
            challenge_weight=None,
            config=cfg,
            settings=settings,
        )
        check(
            d.verb == "update_with_resentment"
            and abs(d.resistance - 0.5) < 1e-9
            and abs(d.challenge - 1.0) < 1e-9,
            "B1 challenge wins: 0.5x1.0x1.0 resistance vs 1.0x1.0 challenge",
        )
        d = decide_dissonance(
            importance_raw=0.9,
            memory_typology="observed",
            rigidity=2.0,
            challenge_typology="told",
            challenge_weight=None,
            config=cfg,
            settings=settings,
        )
        check(
            d.verb == "rationalization"
            and abs(d.resistance - 1.8) < 1e-9
            and abs(d.challenge - 0.6) < 1e-9,
            "B2 memory holds: the zealot end resists hearsay",
        )
        d = decide_dissonance(
            importance_raw=1.0,
            memory_typology="told",
            rigidity=1.0,
            challenge_typology="told",
            challenge_weight=None,
            config=cfg,
            settings=settings,
        )
        check(
            d.resistance == d.challenge and d.verb == "rationalization",
            "B3 the exact tie defends (strict >)",
        )
        d = decide_dissonance(
            importance_raw=None,
            memory_typology=None,
            rigidity=None,
            challenge_typology="observed",
            challenge_weight=None,
            config=cfg,
            settings=settings,
        )
        check(
            abs(d.importance_norm - SERVICE_DEFAULTS["importance_neutral"]) < 1e-9
            and abs(
                d.rigidity_effective - SERVICE_DEFAULTS["dissonance_rigidity_default"]
            )
            < 1e-9
            and abs(
                d.typology_mult_memory
                - SERVICE_DEFAULTS[f"dissonance_typology_{TYPOLOGY_FALLBACK}"]
            )
            < 1e-9,
            "B4 NULLs resolve: neutral importance, default rigidity, fallback typology",
        )
        d = decide_dissonance(
            importance_raw=0.01,
            memory_typology="observed",
            rigidity=9.0,
            challenge_typology="observed",
            challenge_weight=2.5,
            config=cfg,
            settings=settings,
        )
        check(
            abs(d.importance_norm - SERVICE_DEFAULTS["importance_norm_floor"]) < 1e-9
            and abs(d.rigidity_effective - 2.0) < 1e-9
            and abs(d.challenge_weight_effective - 1.0) < 1e-9,
            "B5 every clamp mirrors its existing bound (floor, CHECK band, [0,1])",
        )
        check(
            abs(typology_mult("told", {"dissonance_typology_told": 0.0}, settings))
            < 1e-9,
            "B6 a 0.0 multiplier is the per-side kill-switch shape",
        )
        agent_b = await make_agent(pool, "ladder", AGENT_CONFIG)
        m_up = await seed_memory(
            pool,
            agent_b,
            M_EVENT,
            NOW - timedelta(days=2),
            importance=0.2,
            typology="told",
        )
        res_up = await svc.confront(event(agent_b, m_up))
        check(
            res_up.verb == "update_with_resentment"
            and abs(res_up.resistance - 0.2 * 0.6 * 1.0) < 1e-9
            and abs(res_up.challenge - 1.0) < 1e-9
            and abs(res_up.importance_norm - 0.2) < 1e-9
            and abs(res_up.rigidity_effective - 1.0) < 1e-9,
            "B7 the seam echoes every resolved input; update end to end",
            f"challenge {res_up.challenge:.3f} vs {res_up.resistance:.3f}",
        )
        m_def = await seed_memory(
            pool, agent_b, M_EVENT + " (b)", NOW - timedelta(days=2), importance=0.9
        )
        res_def = await svc.confront(event(agent_b, m_def, challenge_typology="told"))
        check(
            res_def.verb == "rationalization"
            and abs(res_def.resistance - 0.9) < 1e-9
            and abs(res_def.challenge - 0.6) < 1e-9,
            "B8 rationalization end to end (the memory holds)",
        )
        agent_flip = await make_agent(
            pool, "flip", {**AGENT_CONFIG, "dissonance_typology_told": 2.0}
        )
        m_flip = await seed_memory(
            pool, agent_flip, M_EVENT, NOW - timedelta(days=2), importance=0.9
        )
        res_flip = await svc.confront(
            event(agent_flip, m_flip, challenge_typology="told")
        )
        check(
            res_flip.verb == "update_with_resentment"
            and abs(res_flip.challenge - 2.0) < 1e-9,
            "B9 a per-agent knob override flips the same fixture's verdict",
        )
        check(
            res_up.retell_input_tokens > 0
            and res_up.retell_output_tokens > 0
            and res_up.total_ms >= res_up.retell_ms >= 0.0,
            "B10 honest instrumentation: retell tokens counted, timings nested",
        )

        # ------------------------------------------------------------------ #
        print("\n-- C. chain preserved, correction recorded, cache evicted")
        agent_c = await make_agent(pool, "chain", AGENT_CONFIG)
        m_c = await seed_memory(
            pool, agent_c, M_EVENT, NOW - timedelta(days=2), spans=((0, 25),)
        )
        await db.insert_cache_row(pool, m_c, "vhash|b1", "cached one")
        await db.insert_cache_row(pool, m_c, "vhash|b2", "cached two")
        obs_before = await fetchrow(
            pool, "SELECT observation_text FROM memories WHERE memory_id = %s", m_c
        )
        facts_before = await fetchall(
            pool,
            "SELECT fact_version_id, basis_text, write_cause, invalid_at "
            "FROM memory_fact_versions WHERE memory_id = %s ORDER BY created_at",
            m_c,
        )
        payload = {"scene": "tavern", "speaker": "Bram", "beat": 3}
        res_c = await svc.confront(event(agent_c, m_c, source_event=payload))
        chain_c = await chain(pool, m_c)
        check(
            len(chain_c) == 2
            and chain_c[0][0] == "original"
            and chain_c[0][3] == T_E
            and chain_c[-1][0] == "update_with_resentment"
            and chain_c[-1][3] is None
            and chain_c[-1][1] == res_c.content
            and res_c.superseded_detail_id == chain_c[0][4],
            "C1 the chain EXTENDS: prior telling superseded, kept, queryable",
        )
        check(
            (
                await fetchrow(
                    pool,
                    "SELECT observation_text FROM memories WHERE memory_id = %s",
                    m_c,
                )
            )
            == obs_before
            and (
                await fetchall(
                    pool,
                    "SELECT fact_version_id, basis_text, write_cause, invalid_at "
                    "FROM memory_fact_versions WHERE memory_id = %s "
                    "ORDER BY created_at",
                    m_c,
                )
            )
            == facts_before,
            "C2 observation + fact chain byte-untouched (tellings-only ruling)",
        )
        corr = await fetchrow(
            pool,
            "SELECT verb, detail_id, source_event, valid_at, created_at "
            "FROM corrections WHERE memory_id = %s",
            m_c,
        )
        check(
            corr[0] == "update_with_resentment"
            and corr[1] == res_c.detail_id
            and corr[2] == payload
            and corr[3] == T_E,
            "C3 the correction record: verb + new head + source_event verbatim",
        )
        check(
            res_c.evicted_cache_rows == 2
            and await fetchall(
                pool,
                "SELECT 1 FROM reconstruction_cache WHERE memory_id = %s",
                m_c,
            )
            == [],
            "C4 every cache row for the memory evicted, count honest",
        )
        windowed = await fetchall(
            pool,
            "SELECT content FROM memory_details WHERE memory_id = %s "
            "AND valid_at <= %s AND (invalid_at IS NULL OR invalid_at > %s)",
            m_c,
            T_E - timedelta(seconds=1),
            T_E - timedelta(seconds=1),
        )
        check(
            [w[0] for w in windowed] == [f"[walker seed] {M_EVENT}"]
            and chain_c[0][3] == chain_c[-1][2] == corr[3],
            "C5 coherent timeline: windowed SQL re-derives the pre-event "
            "telling; one instant, no gap or overlap",
        )
        sources = await db.fetch_reconstruction_sources(pool, [m_c, m_def])
        check(
            sources[m_c].anchor_cause == "update_with_resentment"
            and sources[m_c].anchor_content == res_c.content,
            "C6 update_with_resentment re-anchors (the accepted account)",
        )
        check(
            sources[m_def].anchor_cause == "original",
            "C7 rationalization never re-anchors ('the story has set')",
        )
        res_c2 = await svc.confront(
            event(
                agent_c,
                m_c,
                challenge_text="No — it was the reeve who moved it, actually.",
                challenge_typology="told",
                client_timestamp=T_E + timedelta(hours=1),
            )
        )
        chain_c2 = await chain(pool, m_c)
        verbs = await fetchall(
            pool,
            "SELECT verb FROM corrections WHERE memory_id = %s ORDER BY valid_at",
            m_c,
        )
        check(
            [r[0] for r in chain_c2]
            == ["original", "update_with_resentment", res_c2.verb]
            and len([r for r in chain_c2 if r[3] is None]) == 1
            and len(verbs) == 2,
            "C8 confrontation over confrontation: heads and records stack",
        )
        check(
            res_c.content != f"[walker seed] {M_EVENT}" and len(res_c.content) > 0,
            "C9 the retell moved the text with NO drift refusal possible — "
            "the event path contains no budget code (exempt by design)",
        )

        # ------------------------------------------------------------------ #
        print("\n-- D. the read-path effect")
        retrieval = RetrievalService(pool, fake_providers(), settings)

        def req(agent_id, text, as_of):
            return DialogueInitRequest(
                agent_id=agent_id,
                query_text=text,
                as_of=as_of,
                scene_started_at=as_of,
            )

        agent_d = await make_agent(pool, "read", AGENT_CONFIG)
        m_d = await seed_memory(pool, agent_d, M_EVENT, NOW - timedelta(days=2))
        before = await retrieval.retrieve_dialogue_init(req(agent_d, M_EVENT, NOW))
        item_before = {i.memory_id: i for i in before.items}[m_d]
        res_d = await svc.confront(event(agent_d, m_d))
        after1 = await retrieval.retrieve_dialogue_init(req(agent_d, M_EVENT, T_E))
        after2 = await retrieval.retrieve_dialogue_init(req(agent_d, M_EVENT, T_E))
        item1 = {i.memory_id: i for i in after1.items}[m_d]
        item2 = {i.memory_id: i for i in after2.items}[m_d]
        check(
            item_before.content == f"[walker seed] {M_EVENT}"
            and item1.content == res_d.content
            and item1.detail_id == res_d.detail_id,
            "D1 the sanctioned mid-scene change: reads serve the new head",
        )
        check(
            item1.content == item2.content and item1.read_mode == "verbatim",
            "D2 stability restored: repeated reads byte-identical (theta-0 "
            "serves the live head verbatim)",
        )
        agent_e = await make_agent(
            pool, "retell", {**AGENT_CONFIG, "reconstruction_theta": 1.1}
        )
        m_e = await seed_memory(
            pool, agent_e, M_EVENT, NOW - timedelta(days=2), spans=((0, 25),)
        )
        await svc.confront(event(agent_e, m_e))
        read_e = await retrieval.retrieve_dialogue_init(req(agent_e, M_EVENT, T_E))
        item_e = {i.memory_id: i for i in read_e.items}[m_e]
        head_e = (await chain(pool, m_e))[-1]
        check(
            item_e.read_mode == "reconstructed"
            and head_e[0] == "reconstruction"
            and item_e.content == head_e[1],
            "D3 past theta the evicted memory retells FROM the accepted "
            "anchor (verify_reconstruction [13] owns the constraint shape)",
        )
        agent_p = await make_agent(pool, "pin", AGENT_CONFIG)
        m_p = await seed_memory(
            pool,
            agent_p,
            M_EVENT,
            NOW - timedelta(days=30),
            pinned=True,
            decay_class="episodic",
        )
        res_p = await svc.confront(event(agent_p, m_p))
        pinned_row = await fetchrow(
            pool, "SELECT pinned FROM memories WHERE memory_id = %s", m_p
        )
        read_p = await retrieval.retrieve_dialogue_init(req(agent_p, M_EVENT, T_E))
        item_p = {i.memory_id: i for i in read_p.items}[m_p]
        check(
            pinned_row == (True,)
            and res_p.pinned is True
            and item_p.read_mode == "verbatim"
            and item_p.content == res_p.content,
            "D4 pin outranked and inherited: the event proceeds, the new head "
            "is the frozen head, served verbatim past any age",
        )
        chain_p = await chain(pool, m_p)
        check(
            [r[0] for r in chain_p] == ["original", "update_with_resentment"],
            "D5 no reconstruction rows ever grow on the pinned chain",
        )
        from app.session import SessionRunner

        runner = await SessionRunner.create(
            agent_d, settings=settings, providers=fake_providers(), pool=pool
        )
        try:
            runner.as_of = T_E + timedelta(hours=2)
            res_r = await runner.confront(
                m_d, "The runner heard otherwise.", challenge_typology="told"
            )
            check(
                res_r.verb in ("rationalization", "update_with_resentment")
                and (await chain(pool, m_d))[-1][2] == T_E + timedelta(hours=2),
                "D6 the session runner's :confront core stamps the session's "
                "effective time (time travel)",
            )
        finally:
            await runner.close()

        # ------------------------------------------------------------------ #
        print("\n-- E. pin/CAS/error ladder (rollback proven)")
        agent_f = await make_agent(pool, "ladder2", AGENT_CONFIG)
        m_f = await seed_memory(pool, agent_f, M_EVENT, NOW - timedelta(days=2))
        await db.insert_cache_row(pool, m_f, "vhash|b1", "cached one")
        try:
            await svc.confront(event(agent_f, m_f, expected_detail_id=uuid4()))
            fail("E1 stale CAS refuses", "no exception")
        except CorrectionConflictError:
            ok("E1 stale expected_detail_id -> the 409 shape")
        check(
            len(await chain(pool, m_f)) == 1
            and await fetchall(
                pool, "SELECT 1 FROM corrections WHERE memory_id = %s", m_f
            )
            == []
            and len(
                await fetchall(
                    pool,
                    "SELECT 1 FROM reconstruction_cache WHERE memory_id = %s",
                    m_f,
                )
            )
            == 1,
            "E2 the CAS rollback left NOTHING: no head, no record, cache intact",
        )
        try:
            await svc.confront(event(agent_f, uuid4()))
            fail("E3 unknown memory refuses", "no exception")
        except UnknownMemoryError:
            ok("E3 unknown memory -> the 404 shape")
        try:
            await svc.confront(event(uuid4(), m_f))
            fail("E4 unknown agent refuses", "no exception")
        except UnknownAgentError:
            ok("E4 unknown agent -> the 404 shape")
        agent_g = await make_agent(pool, "foreign", AGENT_CONFIG)
        try:
            await svc.confront(event(agent_g, m_f))
            fail("E5 foreign memory refuses", "no exception")
        except UnknownMemoryError:
            ok("E5 a foreign memory 404s: from this agent's world it does not exist")
        for provider, label in (
            (FailingReconstructionProvider(), "failing"),
            (MalformedReconstructionProvider(), "malformed"),
        ):
            broken = DissonanceService(
                pool, fake_providers(reconstruction=provider), settings
            )
            try:
                await broken.confront(event(agent_f, m_f))
                fail(f"E6 {label} retell refuses", "no exception")
            except DissonanceCallError:
                pass
        check(
            len(await chain(pool, m_f)) == 1
            and await fetchall(
                pool, "SELECT 1 FROM corrections WHERE memory_id = %s", m_f
            )
            == [],
            "E6 failing AND malformed retells: 502 shape, nothing written "
            "(all-or-nothing, the authorial precedent)",
        )
        rigid_null = await make_agent(pool, "nullrig", AGENT_CONFIG, rigidity=None)
        m_n = await seed_memory(pool, rigid_null, M_EVENT, NOW - timedelta(days=2))
        res_n = await svc.confront(event(rigid_null, m_n))
        check(
            abs(
                res_n.rigidity_effective
                - SERVICE_DEFAULTS["dissonance_rigidity_default"]
            )
            < 1e-9,
            "E7 a NULL-rigidity agent resolves through the default knob "
            "end to end (the column has no default by design)",
        )
    finally:
        await pool.close()
    print(f"\nALL CHECKS PASSED ({len(PASSED)} assertions)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--database-uri", default=None)
    args = parser.parse_args()
    uri = args.database_uri or scratch_uri_from_env()
    asyncio.run(run(uri), loop_factory=asyncio.SelectorEventLoop)


if __name__ == "__main__":
    main()
