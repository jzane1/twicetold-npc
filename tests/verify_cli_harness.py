"""verify_cli_harness.py — structural done-when walker for the dialogue-turn
seam (docs\\cli-harness.md 2026-07-15; RE-OPENED by the split-brain build
2026-07-21, the HTTP turn-route build 2026-07-23, the SSE build 2026-07-27,
and REWRITTEN for the A1 re-shape 2026-08-04 — the behavior call, the action
directive, the reputation system, and the recent-actions block were removed
by ruling, and `weight_overrides` moved onto the prose view).

The seam is an ASYNC GENERATOR: `run_dialogue_turn` yields prose chunks, then
the terminal DialogueTurnResult. One retrieval, one streaming prose call, one
weight-ranked view: `items` is the raw retrieval echo; `dialogue_view` is the
SAME served set re-scored with the resolved per-call weights and re-ranked —
at all-1.0 weights it equals the (id, score) projection of `items` (the
parity contract), and the prose prompt's [memories] block renders in the
weight-ranked order (weights-on-speech: the NPC's words shaped by weights it
is unaware of). A dialogue turn persists nothing.

This walker asserts: the streaming happy path + the shrunk wire contract,
prose-prompt assembly, the weights contract (parity / re-rank / exponent
form / resolution order / clamp / prompt render order), runner passthrough +
zero-persistence, determinism, the prose degradation ladder, the debug view,
cost, the load driver aggregates, the stateless HTTP route pass-through, and
the SSE stream framing.

Structural-only per tests\\CLAUDE.md: assertions touch IDs, flags, score
components, byte-identity, and prompt block structure, never generated prose
content.

Prerequisite (PowerShell):
    python db\\migrate.py --database-uri <scratch-uri>
Run:
    python tests\\verify_cli_harness.py [--database-uri <scratch-uri>]
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # tests\ helpers

from psycopg.types.json import Jsonb

from scratch_uri import scratch_uri

from app.cli import render_debug
from app.config import Settings
from app.db import build_pool
from app.dialogue import (
    DialogueService,
    assemble_prose_prompt,
    rank_dialogue_view,
    resolve_dialogue_weights,
    weighted_score,
)
from app.ingest import IngestService, UnknownAgentError
from app.load_driver import run_driver
from app.providers import (
    FailingProseProvider,
    FakeEmbeddingProvider,
    FakeEscalationProvider,
    FakeProseProvider,
    FakeWriteProvider,
    MidStreamDropProseProvider,
    Providers,
)
from app.retrieval import RetrievalService
from app.schemas import (
    DialogueTurnRequest,
    DialogueTurnResult,
    ObserveEvent,
    RetrievedMemory,
    WeightOverrides,
)
from app.session import SessionRunner

NOW = datetime(2026, 7, 15, 12, 0, 0, tzinfo=timezone.utc)

FALLBACK_LINE = "[fallback] The smith stares into the coals."

AGENT_CONFIG = {
    "decay_classes": {"episodic": 86400, "semantic": 604800},
    "decay_class_default": "episodic",
    "dialogue_fallback_line": FALLBACK_LINE,
    # theta = 0 knob-disables the reconstruction serving stage; gate_enabled = 0
    # knob-disables the mid-dialogue gate — this walker keeps the v1
    # every-turn-retrieves / verbatim-serving contract (their swapped behaviors
    # are verify_reconstruction.py / verify_gate.py floors). FIXTURE-ONLY.
    "reconstruction_theta": 0.0,
    "gate_enabled": 0.0,
}

T_FORGE = "Mara sharpened my blade at the forge while John watched."
T_ROAD = "I overheard talk of bandits on the north road."
T_TAX = "The baron doubled the tax on iron."
UTTERANCE = "Tell me about the forge."

PASSED: list[str] = []

# Turn-result fields the A1 re-shape removed from the wire — asserted absent.
DEAD_RESULT_FIELDS = (
    "directive",
    "directive_dropped",
    "directive_dropped_reason",
    "reputation_snapshot",
    "reputation_prev",
    "reputation_delta",
    "reputation_delta_source",
    "reputation_sensitivity",
    "reputation_after",
    "behavior_view",
)
DEAD_INSTRUMENTATION_FIELDS = (
    "apply_ms",
    "behavior_ms",
    "behavior_input_tokens",
    "behavior_output_tokens",
)
DEAD_REQUEST_FIELDS = (
    "reputation_snapshot",
    "reputation_delta_override",
    "action_vocabulary",
    "recent_actions",
)


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

    return scratch_uri(load_env()["DATABASE_URI"], "longmem_test")


class RecordingProseProvider:
    """FakeProseProvider that keeps the last system prompt so the [memories]
    render order is assertable (IDs only, never prose)."""

    def __init__(self):
        self._inner = FakeProseProvider()
        self.last_system_prompt: str | None = None

    def stream_prose(self, *, system_prompt: str, utterance: str):
        self.last_system_prompt = system_prompt
        return self._inner.stream_prose(
            system_prompt=system_prompt, utterance=utterance
        )


def bundle(dialogue=None) -> Providers:
    return Providers(
        write=FakeWriteProvider(),
        escalation=FakeEscalationProvider(),
        embedding=FakeEmbeddingProvider(),
        dialogue=dialogue if dialogue is not None else FakeProseProvider(),
    )


async def run_turn(gen) -> tuple[str, DialogueTurnResult]:
    """Drain the async-generator seam to (streamed_prose, terminal_result)."""
    chunks: list[str] = []
    result: DialogueTurnResult | None = None
    async for item in gen:
        if isinstance(item, DialogueTurnResult):
            result = item
        else:
            chunks.append(item)
    if result is None:
        raise AssertionError("seam yielded no terminal result")
    return "".join(chunks), result


async def make_agent(pool, name: str, config: dict):
    # The reputation / reputation_sensitivity columns are deliberately absent
    # (A1 re-shape 2026-08-04): the columns stay in the schema, never written.
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO agents (name, seed_identity, rigidity, "
            "diagnosticity_goal, config) "
            "VALUES (%s, %s, 1.0, %s, %s) RETURNING agent_id",
            (
                name,
                "A verification NPC who tends the forge.",
                "what threatens the forge",
                Jsonb(config),
            ),
        )
        return (await cur.fetchone())[0]


async def fetchval(pool, sql: str, *params):
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(sql, params)
        return (await cur.fetchone())[0]


async def seed(ingest: IngestService, agent_id, text: str, valid_at):
    result = await ingest.ingest_observation(
        ObserveEvent(
            agent_id=agent_id,
            observation_text=text,
            phase_tag="walker",
            client_timestamp=valid_at,
            provenance="lived",
        )
    )
    return result.memory_id


def request(agent_id, **overrides) -> DialogueTurnRequest:
    base = dict(agent_id=agent_id, utterance=UTTERANCE, as_of=NOW)
    base.update(overrides)
    return DialogueTurnRequest(**base)


def prompt_memory_lines(prompt: str) -> list[str]:
    """The [memories] block's rendered line texts, in order — a structural
    extract of fixture-authored content, never model output (the in-prompt
    id left the line at F0, 2026-08-26)."""
    return re.findall(r"^- (.+)$", prompt, flags=re.MULTILINE)


def crafted_item(memory_id, score, relevance, recency, importance_norm):
    """A synthetic served item for the pure re-rank tests (score is consistent
    with rel*rec*imp so parity is exact)."""
    return RetrievedMemory(
        memory_id=memory_id,
        detail_id=uuid4(),
        content="x",
        read_mode="verbatim",
        pinned=False,
        score=score,
        relevance=relevance,
        recency=recency,
        importance_norm=importance_norm,
        importance_raw=importance_norm,
    )


async def main(database_uri: str) -> None:
    settings = Settings(database_uri=database_uri, provider_mode="fake")
    pool = build_pool(database_uri)
    await pool.open()
    recording = RecordingProseProvider()
    providers = bundle(dialogue=recording)
    ingest = IngestService(pool, providers, settings)
    retrieval = RetrievalService(pool, providers, settings)
    dialogue = DialogueService(pool, providers, settings, retrieval)

    def service_with(dialogue_provider) -> DialogueService:
        return DialogueService(pool, bundle(dialogue_provider), settings, retrieval)

    print(f"walker: scratch DB = {urlsplit(database_uri).path.lstrip('/')}")

    agent_a = await make_agent(pool, "cli-walker-npc-a", AGENT_CONFIG)
    await seed(ingest, agent_a, T_FORGE, NOW - timedelta(hours=1))
    await seed(ingest, agent_a, T_ROAD, NOW - timedelta(hours=3))
    await seed(ingest, agent_a, T_TAX, NOW - timedelta(hours=26))

    # ------------------------------------------------------------------ #
    print("\n[1] Turn happy path (streaming seam, fake providers)")
    prose1, r1 = await run_turn(dialogue.run_dialogue_turn(request(agent_a)))
    check(
        bool(prose1) and r1.content == prose1, "seam streams prose; content == chunks"
    )
    check(
        len(r1.items) == 3
        and all(
            item.memory_id and item.score is not None and item.recency is not None
            for item in r1.items
        ),
        "retrieval echo: memory_ids + score components ride in the result",
    )
    dump = r1.model_dump()
    check(
        all(field not in dump for field in DEAD_RESULT_FIELDS),
        "wire shrink: no directive/reputation/behavior_view fields on the result",
    )
    ins = r1.instrumentation
    ins_dump = ins.model_dump()
    check(
        all(field not in ins_dump for field in DEAD_INSTRUMENTATION_FIELDS),
        "wire shrink: no apply/behavior terms in the instrumentation",
    )
    check(
        all(
            field not in DialogueTurnRequest.model_fields
            for field in DEAD_REQUEST_FIELDS
        ),
        "wire shrink: the dead request fields are gone from DialogueTurnRequest",
    )
    for name in (
        "sonnet_ms",
        "sonnet_first_token_ms",
        "first_word_ms",
        "perceived_first_word_ms",
        "prose_stream_ms",
        "total_ms",
    ):
        if getattr(ins, name) is None or getattr(ins, name) < 0:
            fail("turn instrumentation", f"{name} = {getattr(ins, name)}")
    check(
        ins.first_word_ms == ins.sonnet_first_token_ms
        and ins.prose_stream_ms == ins.sonnet_ms,
        "first_word_ms == prose TTFT; prose_stream_ms == prose total",
    )
    # Turn-route build 2026-07-23: the honest metric clocks from turn start,
    # so it strictly contains agent fetch + retrieval that first_word_ms skips.
    check(
        ins.perceived_first_word_ms > ins.first_word_ms > 0.0,
        "perceived_first_word_ms is retrieval-inclusive: > first_word_ms > 0",
        f"perceived={ins.perceived_first_word_ms} first_word={ins.first_word_ms}",
    )
    check(
        ins.retrieval.total_ms >= 0
        and ins.sonnet_input_tokens > 0
        and ins.sonnet_output_tokens > 0
        and ins.degraded is False,
        "instrumentation non-null: retrieval + prose timings + tokens",
    )
    check(ins.cost_usd is None, "cost_usd null when no LONGMEM_PRICE_* configured")
    try:
        await run_turn(dialogue.run_dialogue_turn(request(uuid4())))
        fail("unknown agent", "no exception raised")
    except UnknownAgentError:
        ok("unknown agent_id raises UnknownAgentError")

    # ------------------------------------------------------------------ #
    print("\n[2] Prose prompt assembly (the turn's only prompt)")
    p1 = assemble_prose_prompt("Seed prose.", list(r1.items))
    p2 = assemble_prose_prompt("Seed prose.", list(r1.items))
    check(p1 == p2, "identical inputs assemble byte-identical prose prompts")
    order = [p1.index(b) for b in ("[identity]", "[memories]", "[output]")]
    check(order == sorted(order), "prose prompt blocks ride in spec order")
    check(
        all(item.content in p1 for item in r1.items)
        and not any(str(item.memory_id) in p1 for item in r1.items),
        "retrieved memory content rides the prose prompt; the id does not "
        "(stripped from the character-facing block at F0, 2026-08-26)",
    )
    check(
        "reputation" not in p1
        and "directive" not in p1
        and "[recent actions]" not in p1,
        "prose prompt is pure-prose: no JSON contract, no reputation, no "
        "recent-actions block (A1 re-shape)",
    )

    # ------------------------------------------------------------------ #
    print("\n[3] Weights on speech: parity, re-rank, resolution, prompt order")
    # Parity (service level): at default all-1.0 weights, dialogue_view is
    # byte-identical to the (id, score) projection of the served ranking.
    check(
        [v.memory_id for v in r1.dialogue_view] == [i.memory_id for i in r1.items]
        and [v.score for v in r1.dialogue_view] == [i.score for i in r1.items],
        "parity at default weights: dialogue_view == items (id, score) projection",
    )
    content_by_id = {i.memory_id: i.content for i in r1.items}
    check(
        prompt_memory_lines(recording.last_system_prompt or "")
        == [content_by_id[v.memory_id] for v in r1.dialogue_view],
        "prose prompt [memories] renders the weight-ranked (== served) order",
    )
    # Re-rank (service level): an override re-scores the SAME served set; the
    # seam's view equals a recomputation through the pure functions, and the
    # prompt renders in that order (weights shape the words).
    over = WeightOverrides(relevance=0.0)
    _p, rw = await run_turn(
        dialogue.run_dialogue_turn(request(agent_a, weight_overrides=over))
    )
    check(
        {v.memory_id for v in rw.dialogue_view} == {i.memory_id for i in rw.items}
        and [v.score for v in rw.dialogue_view] != [i.score for i in rw.items],
        "override: same served set, re-scored (items stays the raw echo)",
    )
    weights = resolve_dialogue_weights(AGENT_CONFIG, over, settings)
    expected = rank_dialogue_view(list(rw.items), weights)
    check(
        [v.memory_id for v in rw.dialogue_view]
        == [item.memory_id for _s, item in expected]
        and [v.score for v in rw.dialogue_view] == [s for s, _i in expected],
        "override: dialogue_view == the pure-function re-rank of the served set",
    )
    check(
        prompt_memory_lines(recording.last_system_prompt or "")
        == [content_by_id[v.memory_id] for v in rw.dialogue_view],
        "override: the prose prompt renders in the re-ranked order",
    )
    # Pure re-rank proof on crafted items (deterministic, no model call):
    id_hi, id_lo = uuid4(), uuid4()
    # A: score 0.5 (rel .5, rec 1.0);  B: score 0.6 (rel .9, rec .6667).
    item_a = crafted_item(id_lo, 0.5, 0.5, 1.0, 1.0)
    item_b = crafted_item(id_hi, 0.6, 0.9, 2.0 / 3.0, 1.0)
    parity = rank_dialogue_view([item_b, item_a], (1.0, 1.0, 1.0))
    check(
        [it.memory_id for _s, it in parity] == [id_hi, id_lo],
        "parity: weights (1,1,1) keep the served score order",
    )
    # w_rel = 0 removes relevance emphasis => A (0.5/0.5=1.0) outranks B (0.6/0.9):
    reranked = rank_dialogue_view([item_b, item_a], (0.0, 1.0, 1.0))
    check(
        [it.memory_id for _s, it in reranked] == [id_lo, id_hi],
        "re-rank: a relevance-de-emphasis weight flips the prose view order",
    )
    check(
        abs(weighted_score(item_a, 0.0, 1.0, 1.0) - 1.0) < 1e-9
        and abs(weighted_score(item_a, 1.0, 1.0, 1.0) - 0.5) < 1e-9,
        "weighted_score is exponent-form: 1.0 reproduces the score, else re-weights",
    )
    check(
        resolve_dialogue_weights({}, None, settings) == (1.0, 1.0, 1.0)
        and resolve_dialogue_weights(
            {"weight_relevance": 2.0}, WeightOverrides(relevance=3.0), settings
        )
        == (3.0, 1.0, 1.0)
        and resolve_dialogue_weights({"weight_recency": 0.5}, None, settings)
        == (1.0, 0.5, 1.0)
        and resolve_dialogue_weights(
            {}, WeightOverrides(relevance=99.0, recency=-5.0), settings
        )
        == (4.0, 0.0, 1.0),
        "weight resolution: request wins over config wins over 1.0; clamp [0, 4]",
    )

    # ------------------------------------------------------------------ #
    print("\n[4] SessionRunner passthrough + a turn persists nothing")
    mem_before = await fetchval(
        pool, "SELECT count(*) FROM memories WHERE agent_id = %s", agent_a
    )
    runner = await SessionRunner.create(
        agent_a, settings=settings, providers=providers, pool=pool, phase_tag="walker"
    )
    runner.as_of = NOW
    t1 = await runner.utterance(UTTERANCE, weight_overrides=over)
    check(
        [v.score for v in t1.dialogue_view] != [i.score for i in t1.items],
        "runner passes weight_overrides through to the seam",
    )
    t2 = await runner.utterance(UTTERANCE)
    check(
        [v.score for v in t2.dialogue_view] == [i.score for i in t2.items],
        "runner without overrides: parity again (per-call, nothing sticks)",
    )
    mem_after = await fetchval(
        pool, "SELECT count(*) FROM memories WHERE agent_id = %s", agent_a
    )
    rep_row = await fetchval(
        pool, "SELECT reputation FROM agents WHERE agent_id = %s", agent_a
    )
    check(
        int(mem_before) == int(mem_after) and rep_row is None,
        "a dialogue turn persists NOTHING: no memory rows, agents.reputation "
        "stays NULL (the A1 zero-write contract)",
    )
    scene_result = await runner.scene()
    check(
        scene_result.accepted and runner.loaded_memory_ids is None,
        "scene boundary accepted; caller-held loaded set resets",
    )

    # ------------------------------------------------------------------ #
    print("\n[5] Deterministic fake: byte-identical turns")
    p_d1, d1 = await run_turn(dialogue.run_dialogue_turn(request(agent_a)))
    p_d2, d2 = await run_turn(dialogue.run_dialogue_turn(request(agent_a)))
    check(
        p_d1 == p_d2 and d1.content == d2.content,
        "two identical turns: byte-identical prose",
    )
    check(
        [v.memory_id for v in d1.dialogue_view]
        == [v.memory_id for v in d2.dialogue_view]
        and [v.score for v in d1.dialogue_view] == [v.score for v in d2.dialogue_view],
        "two identical turns: identical weight-ranked views",
    )
    check(
        [i.memory_id for i in d1.items] == [i.memory_id for i in d2.items]
        and [i.content for i in d1.items] == [i.content for i in d2.items],
        "repeated reads byte-identical within the scene (served items)",
    )

    # ------------------------------------------------------------------ #
    print("\n[6] Never-blank ladder: the prose degradation rows")
    # row 1: prose fails BEFORE the first chunk -> fallback line + degraded;
    # retrieval is unaffected, so the served view still rides the result.
    _p, r_pf = await run_turn(
        service_with(FailingProseProvider()).run_dialogue_turn(request(agent_a))
    )
    check(
        r_pf.content == FALLBACK_LINE
        and r_pf.instrumentation.degraded
        and "prose call failed" in r_pf.instrumentation.degraded_reason
        and [i.memory_id for i in r_pf.items]
        and [v.memory_id for v in r_pf.dialogue_view],
        "prose fails pre-chunk: fallback line; served view still on the result",
    )
    check(
        r_pf.instrumentation.first_word_ms == 0.0
        and r_pf.instrumentation.perceived_first_word_ms == 0.0,
        "no chunk ever arrived: both TTFT fields stay 0.0 (the honest zero)",
    )
    # row 2: prose drops mid-stream -> keep the partial (ruled 2026-07-21).
    prose_md, r_md = await run_turn(
        service_with(MidStreamDropProseProvider()).run_dialogue_turn(request(agent_a))
    )
    check(
        prose_md == "partial prose"
        and r_md.content == prose_md
        and r_md.content != FALLBACK_LINE
        and r_md.instrumentation.degraded
        and "mid-stream" in r_md.instrumentation.degraded_reason,
        "prose drops mid-stream: the partial is kept + degraded flag",
    )

    # ------------------------------------------------------------------ #
    print("\n[7] Debug view surfaces IDs, scores, the weight-ranked view")
    view = render_debug(r1)
    check(
        all(str(item.memory_id) in view for item in r1.items),
        "debug view carries every retrieved memory_id",
    )
    check(
        f"score={r1.items[0].score:.4f}" in view
        and f"first_word={r1.instrumentation.first_word_ms}" in view
        and "dialogue view (weight-ranked)" in view
        and str(r1.dialogue_view[0].memory_id)[:8] in view,
        "debug view carries scores, first_word, and the weight-ranked view",
    )
    check(
        "reputation" not in view and "behavior" not in view,
        "debug view carries no reputation/behavior lines (A1 re-shape)",
    )

    # ------------------------------------------------------------------ #
    print("\n[8] Per-turn cost populated when prices are configured")
    priced = Settings(
        database_uri=database_uri,
        provider_mode="fake",
        prices={"dialogue_in": 3.0, "dialogue_out": 15.0, "embedding": 0.02},
    )
    _p, r_priced = await run_turn(
        DialogueService(
            pool, providers, priced, RetrievalService(pool, providers, priced)
        ).run_dialogue_turn(request(agent_a))
    )
    check(
        r_priced.instrumentation.cost_usd is not None
        and r_priced.instrumentation.cost_usd > 0,
        "cost_usd computed from configured prose + embedding prices",
        f"${r_priced.instrumentation.cost_usd}",
    )

    # ------------------------------------------------------------------ #
    print("\n[9] Load driver: scripted sessions offline, §11 aggregates")
    report = await run_driver(settings, sessions=2, turns=3, seed=1)
    check(
        report["sessions"] == 2 and report["turns"] == 6,
        "scripted N-session run completed offline and keyless",
        f"{report['turns']} turns, {report['observes']} observes",
    )
    for series in (
        "retrieval_sql",
        "query_embed",
        "first_word",
        "perceived_first_word",
        "pre_prose",
        "dialogue_total",
        "turn_total",
    ):
        row = report["latency_ms"].get(series)
        if row is None or row["p50"] < 0 or row["p95"] < row["p50"]:
            fail("latency aggregates", f"{series}: {row}")
    ok(
        "latency p50/p95 emitted for every §11 series incl. first_word + "
        "perceived_first_word (the gate term is in verify_gate.py)"
    )
    check(
        "behavior" not in report["latency_ms"]
        and "behavior" not in report["per_100_turns"],
        "no behavior series or cost row anywhere in the report (A1 re-shape)",
    )
    check(
        report["per_100_turns"]["dialogue"]["input_tokens_per_100_turns"] > 0
        and report["per_100_turns"]["dialogue"]["usd_per_100_turns"] is None
        and report["degraded_turns"] == 0,
        "per-100-turn table itemized; USD unpriced -> null",
    )

    # ------------------------------------------------------------------ #
    print("\n[10] HTTP turn route: stateless pass-through (the Unity front door)")
    # Turn-route build 2026-07-23: POST /v1/dialogue/turn drains the SAME
    # async-generator seam to its terminal result — route JSON == the seam
    # result's serialization (the pass-through ruling), scene state entirely
    # caller-held on the request (stateless by construction).
    import json

    import httpx

    import app.api as api_module

    class CapturingDialogue:
        def __init__(self, inner: DialogueService):
            self._inner = inner
            self.last: DialogueTurnResult | None = None
            self.chunks = 0

        async def run_dialogue_turn(self, req, *, on_reconstruct=None):
            async for item in self._inner.run_dialogue_turn(
                req, on_reconstruct=on_reconstruct
            ):
                if isinstance(item, DialogueTurnResult):
                    self.last = item
                else:
                    self.chunks += 1
                yield item

    capturing = CapturingDialogue(dialogue)
    api_module.app.state.dialogue = capturing
    transport = httpx.ASGITransport(app=api_module.app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://walker"
    ) as client:
        payload = json.loads(request(agent_a).model_dump_json())
        response = await client.post("/v1/dialogue/turn", json=payload)
        r_missing = await client.post(
            "/v1/dialogue/turn",
            json=json.loads(request(uuid4()).model_dump_json()),
        )
        r_badver = await client.post(
            "/v1/dialogue/turn",
            json=json.loads(
                request(agent_a, identity_version="no-such-version").model_dump_json()
            ),
        )
    check(response.status_code == 200, "route returned 200")
    check(
        capturing.chunks > 0
        and response.json() == json.loads(capturing.last.model_dump_json()),
        "route JSON is exactly the drained seam DialogueTurnResult (pass-through)",
        f"{capturing.chunks} chunks drained server-side",
    )
    body = response.json()
    check(
        all(item["memory_id"] and item["score"] is not None for item in body["items"])
        and body["dialogue_view"]
        and all(field not in body for field in DEAD_RESULT_FIELDS)
        and body["instrumentation"]["perceived_first_word_ms"]
        > body["instrumentation"]["first_word_ms"]
        > 0.0,
        "wire contract: IDs + scores + dialogue_view + both TTFT fields, and "
        "no dead fields, over HTTP",
    )
    check(
        r_missing.status_code == 404,
        "unknown agent_id -> 404 over the route",
    )
    check(
        r_badver.status_code == 422,
        "unknown identity_version -> 422 over the route (the init-route precedent)",
    )

    # ------------------------------------------------------------------ #
    print("\n[11] SSE turn stream: the same seam over text/event-stream")
    # unity-client.md fork 1 (ruled 2026-07-27): POST /v1/dialogue/turn/stream
    # iterates the SAME async generator via a queue-bridged pump task. The
    # `reconstructing` event rides the same queue off the pre-serve callback;
    # its firing condition (a blocked mid-scene retelling) is fixture-pinned
    # off here (reconstruction_theta = 0) and proven at the reconstruction
    # floor — this section proves the stream framing contract.
    capturing_sse = CapturingDialogue(dialogue)
    api_module.app.state.dialogue = capturing_sse
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api_module.app), base_url="http://walker"
    ) as client:
        s_ok = await client.post(
            "/v1/dialogue/turn/stream",
            json=json.loads(request(agent_a).model_dump_json()),
        )
        s_missing = await client.post(
            "/v1/dialogue/turn/stream",
            json=json.loads(request(uuid4()).model_dump_json()),
        )
    check(
        s_ok.status_code == 200
        and s_ok.headers["content-type"].startswith("text/event-stream"),
        "stream route returned 200 text/event-stream",
    )
    sse_events = []
    for block in s_ok.text.split("\n\n"):
        if block.strip():
            fields = dict(
                line.split(": ", 1) for line in block.split("\n") if ": " in line
            )
            sse_events.append((fields["event"], fields["data"]))
    stream_chunks = [json.loads(d) for k, d in sse_events if k == "chunk"]
    stream_result = json.loads(sse_events[-1][1])
    check(
        sse_events[-1][0] == "result"
        and len(stream_chunks) == capturing_sse.chunks > 0,
        "chunk events streamed (count == the seam's chunk count); result terminal",
        f"{len(stream_chunks)} chunks over SSE",
    )
    check(
        "".join(stream_chunks) == stream_result["content"],
        "chunks concatenate byte-identically to the result's content",
    )
    check(
        stream_result == json.loads(capturing_sse.last.model_dump_json()),
        "result event JSON is exactly the seam result's serialization",
    )
    check(
        s_missing.status_code == 404,
        "unknown agent_id -> 404 on the stream route (pre-stream mapping)",
    )

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
