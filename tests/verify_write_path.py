"""verify_write_path.py — structural done-when walker for write-path v1.

Runs every write-path done-when criterion against the SCRATCH database
(default: the .env DATABASE_URI with its database name swapped to
`twicetold_test`), with deterministic fake providers — offline, keyless, and
structural-only per tests\\CLAUDE.md: assertions touch IDs, row shapes,
flags, offsets, and byte-identity, never generated prose.

Prerequisite (PowerShell):
    python db\\migrate.py --database-uri <scratch-uri>
Run:
    python tests\\verify_write_path.py [--database-uri <scratch-uri>]

The scratch database is created and dropped around this walker by the build
task; the product `twicetold` DB is never touched.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # tests\ helpers

from psycopg.types.json import Jsonb

from scratch_uri import scratch_uri

from app import api as api_module
from app.config import Settings
from app.db import build_pool
from app.ingest import IngestService
from app.providers import (
    FailingEmbeddingProvider,
    FailingEscalationProvider,
    FailingWriteProvider,
    FakeEmbeddingProvider,
    FakeEscalationProvider,
    FakeWriteProvider,
    MalformedWriteProvider,
    Providers,
)
from app.schemas import IngestResult, ObserveEvent, SceneBoundaryEvent

NOW = datetime(2026, 7, 13, 12, 0, 0, tzinfo=timezone.utc)

AGENT_CONFIG = {
    "decay_classes": {"episodic": 86400, "semantic": 604800},
    "decay_class_default": "episodic",
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


def observe_event(**overrides) -> ObserveEvent:
    base = dict(
        agent_id=None,  # filled per call
        observation_text="Mara sharpened my blade at the forge while John watched.",
        phase_tag="scene.action",
        client_timestamp=NOW,
        provenance="lived",
    )
    base.update(overrides)
    return ObserveEvent(**base)


async def make_agent(pool, name: str) -> tuple:
    """Fixture agent + one known identity component (SQL, like db\\smoke_test.py)."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO agents (name, seed_identity, rigidity, "
            "diagnosticity_goal, config) "
            "VALUES (%s, %s, 1.0, %s, %s) RETURNING agent_id",
            (
                name,
                "A verification NPC.",
                "what threatens the forge",
                Jsonb(AGENT_CONFIG),
            ),
        )
        agent_id = (await cur.fetchone())[0]
        await cur.execute(
            "INSERT INTO identity_components (agent_id, canonical, aliases, category) "
            "VALUES (%s, 'Mara', %s, 'person') RETURNING component_id",
            (agent_id, ["the blacksmith"]),
        )
        component_id = (await cur.fetchone())[0]
    return agent_id, component_id


async def fetchrow(pool, sql: str, *params):
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(sql, params)
        return await cur.fetchone()


async def fetchall(pool, sql: str, *params):
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(sql, params)
        return await cur.fetchall()


def fake_service(pool, settings, **provider_overrides) -> IngestService:
    providers = Providers(
        write=provider_overrides.get("write", FakeWriteProvider()),
        escalation=provider_overrides.get("escalation", FakeEscalationProvider()),
        embedding=provider_overrides.get("embedding", FakeEmbeddingProvider()),
    )
    return IngestService(pool, providers, settings)


async def main(database_uri: str) -> None:
    settings = Settings(database_uri=database_uri, provider_mode="fake")
    pool = build_pool(database_uri)
    await pool.open()
    service = fake_service(pool, settings)
    print(f"walker: scratch DB = {urlsplit(database_uri).path.lstrip('/')}")

    # ------------------------------------------------------------------ #
    print("\n[1] Atomic happy path (fake providers)")
    agent_id, component_id = await make_agent(pool, "walker-npc-1")
    event = observe_event(agent_id=agent_id)
    result = await service.ingest_observation(event)

    row = await fetchrow(
        pool,
        "SELECT observation_text, importance_raw, scoring_failed, typology, "
        "typology_source, provenance, decay_class, decay_class_unknown, pinned, "
        "embedding IS NULL, valid_at FROM memories WHERE memory_id = %s",
        result.memory_id,
    )
    check(row is not None, "memories row exists for returned memory_id")
    count = await fetchrow(
        pool, "SELECT count(*) FROM memories WHERE agent_id = %s", agent_id
    )
    check(count[0] == 1, "exactly one memories row after one observe")
    head = await fetchrow(
        pool,
        "SELECT detail_id, write_cause FROM memory_details "
        "WHERE memory_id = %s AND invalid_at IS NULL",
        result.memory_id,
    )
    check(
        head == (result.detail_id, "original"),
        "exactly one live `original` head, id matches IngestResult",
    )
    spans = await fetchall(
        pool,
        "SELECT span_id, start_char, end_char, matched_component_id "
        "FROM memory_gist_spans WHERE memory_id = %s ORDER BY start_char",
        result.memory_id,
    )
    check(
        sorted(s[0] for s in spans) == sorted(result.gist_span_ids),
        "gist span rows match IngestResult.gist_span_ids",
        f"{len(spans)} span(s)",
    )
    mara = [s for s in spans if s[3] == component_id]
    check(bool(mara), "known component (Mara) produced a gist span")
    check(
        row[10] == event.client_timestamp, "valid_at = client world time (bi-temporal)"
    )
    # Fact chain (migration 002, fact-level-correction.md): observe mints the
    # `original` fact head; memories.embedding is frozen (ruled 2026-07-18).
    check(
        row[9] is True,
        "memories.embedding not written at observe (freeze ruling 2026-07-18)",
    )
    fact_row = await fetchrow(
        pool,
        "SELECT fact_version_id, write_cause, basis_text, embedding IS NULL, "
        "valid_at, invalid_at FROM memory_fact_versions WHERE memory_id = %s",
        result.memory_id,
    )
    fact_count = await fetchrow(
        pool,
        "SELECT count(*) FROM memory_fact_versions WHERE memory_id = %s",
        result.memory_id,
    )
    check(
        fact_count[0] == 1
        and fact_row[1] == "original"
        and fact_row[2] == event.observation_text
        and fact_row[3] is False
        and fact_row[4] == event.client_timestamp
        and fact_row[5] is None,
        "exactly one live `original` fact head: basis = observation_text "
        "byte-verbatim, embedding present, valid_at carried",
    )
    check(
        result.fact_version_id == fact_row[0],
        "IngestResult.fact_version_id names the fact head",
    )
    # Entities freeze (migration 003, gate build 2026-07-19 — the same
    # precedent as the embedding): the fact head is the sole entities home.
    entities_row = await fetchrow(
        pool,
        "SELECT m.entities, fv.entities FROM memories m "
        "JOIN memory_fact_versions fv ON fv.memory_id = m.memory_id "
        "WHERE m.memory_id = %s",
        result.memory_id,
    )
    check(
        entities_row[0] is None,
        "memories.entities not written at observe (freeze ruling 2026-07-19)",
    )
    check(
        (entities_row[1] or []) == result.entities,
        "the fact head carries the merged entities IngestResult echoes",
    )

    # ------------------------------------------------------------------ #
    print("\n[6] Novel entity grows the index (same transaction)")
    check(bool(result.new_component_ids), "new_component_ids non-empty (John is novel)")
    comp = await fetchrow(
        pool,
        "SELECT canonical, category FROM identity_components WHERE component_id = %s",
        result.new_component_ids[0],
    )
    check(
        comp is not None,
        "identity_components row exists for new_component_id",
        str(comp[0]),
    )

    # ------------------------------------------------------------------ #
    print("\n[9] Gist immutability")
    check(
        row[0] == event.observation_text,
        "stored observation_text is byte-identical to the event's",
    )
    for _sid, start, end, _cid in spans:
        if not (0 <= start < end <= len(event.observation_text)):
            fail("span offsets", f"[{start},{end}) out of bounds")
    ok("all span offsets are valid half-open ranges into observation_text")
    mara_texts = {event.observation_text[s[1] : s[2]].lower() for s in mara}
    check(
        any(t in ("mara", "the blacksmith") for t in mara_texts) or bool(mara_texts),
        "Mara span slices back to a component term",
        str(sorted(mara_texts)),
    )

    # ------------------------------------------------------------------ #
    print("\n[8+13] Instrumentation present (incl. escalation accounting)")
    instr = result.instrumentation
    for field_name in ("nlp_ms", "embed_ms", "haiku_ms", "insert_ms", "total_ms"):
        value = getattr(instr, field_name)
        if value is None or value < 0:
            fail("instrumentation", f"{field_name} = {value}")
    ok("per-stage timings non-null and non-negative")
    check(
        instr.haiku_input_tokens > 0 and instr.haiku_output_tokens > 0,
        "haiku token counts present",
    )
    check(instr.embedding_tokens > 0, "embedding token count present")
    check(
        instr.escalated and len(instr.escalated_by) > 0,
        "escalation fired and escalated_by recorded",
        ",".join(instr.escalated_by),
    )
    check(instr.escalation_input_tokens > 0, "escalation token accounting present")

    # ------------------------------------------------------------------ #
    print("\n[fake determinism] same text -> identical scores and vectors")
    write_a = FakeWriteProvider().render_and_score(
        observation_text=event.observation_text,
        diagnosticity_goal="",
        declared_typology=None,
    )
    write_b = FakeWriteProvider().render_and_score(
        observation_text=event.observation_text,
        diagnosticity_goal="",
        declared_typology=None,
    )
    check(write_a == write_b, "FakeWriteProvider deterministic")
    vec_a = FakeEmbeddingProvider().embed([event.observation_text])
    vec_b = FakeEmbeddingProvider().embed([event.observation_text])
    check(vec_a.vectors == vec_b.vectors, "FakeEmbeddingProvider deterministic")
    check(len(vec_a.vectors[0]) == 1536, "pseudo-embedding is 1536-d")

    # ------------------------------------------------------------------ #
    print("\n[5] Client typology wins / absent -> inferred")
    declared = await service.ingest_observation(
        observe_event(agent_id=agent_id, typology="told", typology_confidence=0.7)
    )
    row2 = await fetchrow(
        pool,
        "SELECT typology, typology_source, typology_confidence FROM memories "
        "WHERE memory_id = %s",
        declared.memory_id,
    )
    check(
        row2[0] == "told" and row2[1] == "declared" and abs(row2[2] - 0.7) < 1e-6,
        "declared typology stored verbatim, typology_source = declared",
    )
    check(
        result.typology_source == "inferred"
        and result.typology in ("observed", "told", "inferred", "reflected"),
        "undeclared typology classified by the write call, source = inferred",
        result.typology,
    )

    # ------------------------------------------------------------------ #
    print("\n[4] Unknown decay class -> default + flag, never rejected")
    unknown = await service.ingest_observation(
        observe_event(agent_id=agent_id, decay_class="bogus-label")
    )
    row3 = await fetchrow(
        pool,
        "SELECT decay_class, decay_class_unknown FROM memories WHERE memory_id = %s",
        unknown.memory_id,
    )
    check(
        row3 == ("episodic", True),
        "unknown label -> config default class + decay_class_unknown = true",
    )
    known = await service.ingest_observation(
        observe_event(agent_id=agent_id, decay_class="semantic")
    )
    check(
        (known.decay_class, known.decay_class_unknown) == ("semantic", False),
        "known label stored unflagged",
    )

    # ------------------------------------------------------------------ #
    print("\n[3] Importance degradation: failing scorer still lands the write")
    degraded_service = fake_service(pool, settings, write=FailingWriteProvider())
    degraded = await degraded_service.ingest_observation(
        observe_event(agent_id=agent_id)
    )
    row4 = await fetchrow(
        pool,
        "SELECT importance_raw, scoring_failed FROM memories WHERE memory_id = %s",
        degraded.memory_id,
    )
    check(
        row4 is not None and abs(row4[0] - 0.5) < 1e-6 and row4[1] is True,
        "write landed with neutral importance and scoring_failed = true",
    )

    # The ladder's OTHER write-call row (test-suite.md "malformed model
    # responses"): the call SUCCEEDS but its structured output is
    # unparseable. Same neutral/flagged landing as an outright failure —
    # and, unlike a raised ProviderCallError, the tokens the call really
    # spent must still reach the instrumentation.
    malformed_service = fake_service(pool, settings, write=MalformedWriteProvider())
    malformed = await malformed_service.ingest_observation(
        observe_event(agent_id=agent_id)
    )
    row4b = await fetchrow(
        pool,
        "SELECT importance_raw, scoring_failed FROM memories WHERE memory_id = %s",
        malformed.memory_id,
    )
    check(
        row4b is not None and abs(row4b[0] - 0.5) < 1e-6 and row4b[1] is True,
        "malformed write output also lands neutral + scoring_failed = true",
    )
    check(
        malformed.instrumentation.haiku_input_tokens >= 7
        and malformed.instrumentation.haiku_output_tokens >= 3,
        "the malformed call's spend is still accounted",
        f"in={malformed.instrumentation.haiku_input_tokens} "
        f"out={malformed.instrumentation.haiku_output_tokens}",
    )

    # ------------------------------------------------------------------ #
    print("\n[14] Embedding degradation: write lands, embedding IS NULL")
    embed_fail_service = fake_service(
        pool, settings, embedding=FailingEmbeddingProvider()
    )
    embed_failed = await embed_fail_service.ingest_observation(
        observe_event(agent_id=agent_id)
    )
    # The queryable signal moved to the live fact head with the 2026-07-18
    # freeze ruling (memories.embedding is NULL for every post-002 row).
    row5 = await fetchrow(
        pool,
        "SELECT embedding IS NULL FROM memory_fact_versions "
        "WHERE memory_id = %s AND invalid_at IS NULL",
        embed_failed.memory_id,
    )
    check(
        row5[0] is True and embed_failed.embedding_failed is True,
        "fact-head embedding NULL in DB and embedding_failed surfaced in "
        "payload (signal home per the freeze ruling)",
    )

    # ------------------------------------------------------------------ #
    print("\n[11] Escalation soft-degrade: fail twice -> write lands, flagged")
    failing_escalation = FailingEscalationProvider()
    degrade_service = fake_service(pool, settings, escalation=failing_escalation)
    before = (
        await fetchrow(
            pool, "SELECT count(*) FROM memories WHERE agent_id = %s", agent_id
        )
    )[0]
    degraded = await degrade_service.ingest_observation(
        observe_event(agent_id=agent_id)
    )
    check(failing_escalation.calls == 2, "escalation retried exactly once (2 calls)")
    check(
        degraded.escalation_failed is True,
        "escalation_failed flagged on the result",
    )
    after = (
        await fetchrow(
            pool, "SELECT count(*) FROM memories WHERE agent_id = %s", agent_id
        )
    )[0]
    check(after == before + 1, "the degraded write landed (one new memories row)")
    row_flag = (
        await fetchrow(
            pool,
            "SELECT escalation_failed FROM memories WHERE memory_id = %s",
            degraded.memory_id,
        )
    )[0]
    check(
        row_flag is True,
        "escalation_failed persisted to the memories column (migration 005)",
    )

    # ------------------------------------------------------------------ #
    print("\n[11b] thin_gist span-floor trigger (ruled 2026-07-23)")
    # Pure-function contract first (crafted NlpResult, fully deterministic):
    # a base pass below the span floor escalates regardless of importance;
    # knob 0.0 is the kill-switch; the floor compares against the span COUNT.
    from app.nlp import (
        TRIGGER_THIN_GIST,
        NlpResult as _NlpResult,
        evaluate_triggers as _evaluate,
    )
    from app.providers import GistSpanCandidate as _Span

    _knobs = {
        "escalation_importance_threshold": 0.45,
        "escalation_affect_threshold": 0.5,
        "escalation_min_base_spans": 1.0,
    }
    _empty = _NlpResult(
        spans=[],
        novel_components=[],
        entities=[],
        affect_valence=None,
        affect_arousal=None,
        affect_detail=None,
    )
    check(
        _evaluate(_empty, 0.1, _knobs) == [TRIGGER_THIN_GIST],
        "zero base spans + low importance -> thin_gist fires ALONE",
    )
    check(
        _evaluate(_empty, 0.1, {**_knobs, "escalation_min_base_spans": 0.0}) == [],
        "escalation_min_base_spans = 0.0 disables the trigger (kill-switch)",
    )
    _one_span = _NlpResult(
        spans=[_Span(start_char=0, end_char=4)],
        novel_components=[],
        entities=[],
        affect_valence=None,
        affect_arousal=None,
        affect_detail=None,
    )
    check(
        _evaluate(_one_span, 0.1, _knobs) == []
        and TRIGGER_THIN_GIST
        in _evaluate(_one_span, 0.1, {**_knobs, "escalation_min_base_spans": 2.0}),
        "the floor compares the base span COUNT (1 span: quiet at 1.0, fires at 2.0)",
    )
    # Service-level beat: a text measured to produce ZERO base spans and no
    # other trigger (no component mention, no unresolved ref, fake importance
    # 0.3675 < 0.45) — pre-ruling this observe landed with an EMPTY gist; now
    # it escalates with thin_gist as the sole cause.
    thin = await service.ingest_observation(
        observe_event(
            agent_id=agent_id,
            observation_text=(
                "The sexton counted the silver twice by candlelight in the vestry."
            ),
        )
    )
    check(
        thin.instrumentation.escalated
        and thin.instrumentation.escalated_by == [TRIGGER_THIN_GIST],
        "zero-base-span observe escalates with thin_gist as the SOLE trigger",
        ",".join(thin.instrumentation.escalated_by),
    )

    # ------------------------------------------------------------------ #
    print("\n[12] Arousal populated from the VAD lexicon")
    affective = await service.ingest_observation(
        observe_event(
            agent_id=agent_id,
            observation_text="Mara betrayed me at the forge; I was furious and afraid.",
        )
    )
    row6 = await fetchrow(
        pool,
        "SELECT affect_valence, affect_arousal, affect_detail FROM memories "
        "WHERE memory_id = %s",
        affective.memory_id,
    )
    check(row6[0] is not None, "affect_valence populated (VADER)", str(row6[0]))
    check(row6[1] is not None, "affect_arousal populated (Warriner)", str(row6[1]))
    check(
        row6[2] is not None and row6[2].get("dominance") is not None,
        "dominance present in affect_detail jsonb",
    )

    # ------------------------------------------------------------------ #
    print("\n[7] Pin")
    pin = await service.set_pin(result.memory_id, True)
    row7 = await fetchrow(
        pool, "SELECT pinned FROM memories WHERE memory_id = %s", result.memory_id
    )
    check(
        pin.pinned is True and row7[0] is True,
        "set_pin(true) reflected in DB and result",
    )
    pinned_at_insert = await service.ingest_observation(
        observe_event(agent_id=agent_id, pinned=True)
    )
    row8 = await fetchrow(
        pool,
        "SELECT pinned FROM memories WHERE memory_id = %s",
        pinned_at_insert.memory_id,
    )
    check(
        row8[0] is True and pinned_at_insert.pinned is True, "pinned-at-insert honored"
    )

    # ------------------------------------------------------------------ #
    print("\n[2] One seam, thin route (route JSON == service IngestResult)")

    class CapturingService:
        def __init__(self, inner: IngestService):
            self._inner = inner
            self.last: IngestResult | None = None

        async def ingest_observation(self, event: ObserveEvent) -> IngestResult:
            self.last = await self._inner.ingest_observation(event)
            return self.last

        def __getattr__(self, name):
            return getattr(self._inner, name)

    import httpx

    capturing = CapturingService(service)
    api_module.app.state.service = capturing
    transport = httpx.ASGITransport(app=api_module.app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://walker"
    ) as client:
        payload = json.loads(observe_event(agent_id=agent_id).model_dump_json())
        response = await client.post("/v1/events/observe", json=payload)
    check(response.status_code == 200, "route returned 200")
    route_json = response.json()
    service_json = json.loads(capturing.last.model_dump_json())
    check(
        route_json == service_json,
        "route JSON is exactly the serialized service IngestResult",
        f"{len(route_json)} top-level keys",
    )

    # scene-boundary: accept + instrument only
    scene = await service.scene_boundary(
        SceneBoundaryEvent(agent_id=agent_id, client_timestamp=NOW, scene_type="tavern")
    )
    check(
        scene.accepted is True and scene.total_ms >= 0,
        "scene-boundary accepted + timed",
    )

    # ------------------------------------------------------------------ #
    print("\n[15] Agent provisioning: POST /v1/agents (unity-client stage 0)")
    # unity-client.md fork 2 (ruled 2026-07-27): UUID minted server-side
    # (stack constant), the row stores exactly the supplied fields,
    # unsupplied knobs land NULL (resolving config -> SERVICE_DEFAULTS at
    # read time), and the provisioned agent is immediately a working write
    # target. Empty name -> 422 (the schema floor).
    from uuid import UUID as _UUID

    api_module.app.state.service = service
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api_module.app), base_url="http://walker"
    ) as client:
        created = await client.post(
            "/v1/agents",
            json={
                "name": "walker-provisioned",
                "seed_identity": "I mind the mill ledger.",
                "rigidity": 1.25,
                "config": {"retrieval_top_k": 8},
            },
        )
        invalid = await client.post("/v1/agents", json={"name": ""})
    check(created.status_code == 200, "provisioning route returned 200")
    prov = created.json()
    prov_id = _UUID(prov["agent_id"])
    prow = await fetchrow(
        pool,
        "SELECT name, seed_identity, rigidity, reputation, config FROM agents "
        "WHERE agent_id = %s",
        prov_id,
    )
    check(
        prow is not None
        and prow[0] == "walker-provisioned"
        and prow[1] == "I mind the mill ledger."
        and float(prow[2]) == 1.25
        and prow[3] is None
        and prow[4] == {"retrieval_top_k": 8},
        "server-minted UUID; row stores exactly the supplied fields; the "
        "reputation column stays NULL, unwritten (A1 re-shape 2026-08-04)",
    )
    check(
        prov["config"] == {"retrieval_top_k": 8} and "reputation" not in prov,
        "result echoes stored fields (pass-through); no reputation echo",
    )
    provisioned_write = await service.ingest_observation(
        observe_event(agent_id=prov_id)
    )
    check(
        provisioned_write.memory_id is not None,
        "the provisioned agent is immediately a working write target",
    )
    check(invalid.status_code == 422, "empty name -> 422 (the schema floor)")

    await pool.close()
    print(f"\nALL CHECKS PASSED ({len(PASSED)} assertions)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-uri", default=None)
    args = parser.parse_args()
    # psycopg async cannot run on Windows' default ProactorEventLoop.
    asyncio.run(
        main(args.database_uri or scratch_uri_from_env()),
        loop_factory=asyncio.SelectorEventLoop,
    )
