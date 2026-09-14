"""The Ledger's live turn feed (E2, ruled 2026-08-19; docs\\test-suite.md).

Route-level, unmarked: db-layer seeding + ASGI transport, no NLP pass. The
feed is a module-global ring buffer in app.api (deliberately not app.state —
this file drives the app without lifespan, the set-D route-contract
convention), so every scenario resets it first.
"""

from __future__ import annotations

from datetime import timedelta

from conftest import NOW, V1_CONFIG, run_structural


def _parse_sse(body: str) -> list[tuple[str, str]]:
    """(event, data) pairs from a text/event-stream body — framing only."""
    events = []
    for block in body.split("\n\n"):
        if not block.strip():
            continue
        fields = dict(line.split(": ", 1) for line in block.split("\n") if ": " in line)
        events.append((fields["event"], fields["data"]))
    return events


def test_ledger_turn_feed_contract(scene):
    """The turn feed (E2 ruling, 2026-08-19): both dialogue routes tee their
    terminal result into GET /v1/ledger/turns — each entry's `result` is the
    route response's serialization byte-identical (the pass-through carve-out
    records, never alters); seq is monotone from 1 after a process start;
    `after` filters to strictly-newer entries with `last_seq` as the next
    cursor even when nothing newer exists; and the buffer holds exactly the
    newest _TURN_FEED_CAP entries."""

    async def scenario(ctx):
        import json

        import httpx

        import app.api as api_module
        from app.dialogue import DialogueService
        from app.schemas import DialogueTurnRequest

        # Module-global state: start this scenario from an empty feed.
        api_module._turn_feed.clear()
        api_module._turn_seq = 0

        agent = await ctx.make_agent("ledger-feed", V1_CONFIG)
        await ctx.seed(
            agent,
            "The miller raised his toll at the bridge and the carters "
            "grumbled about the price of crossing all week.",
            NOW - timedelta(hours=1),
        )
        api_module.app.state.dialogue = DialogueService(
            ctx.pool, ctx.providers(), ctx.settings, ctx.retrieval()
        )
        transport = httpx.ASGITransport(app=api_module.app)

        def payload():
            return json.loads(
                DialogueTurnRequest(
                    agent_id=agent,
                    utterance="What happened at the bridge?",
                    as_of=NOW,
                ).model_dump_json()
            )

        async with httpx.AsyncClient(
            transport=transport, base_url="http://localhost"
        ) as client:
            # Empty feed: no entries, cursor 0.
            empty = await client.get("/v1/ledger/turns")
            assert empty.status_code == 200
            assert empty.json() == {"entries": [], "last_seq": 0}

            # The non-streaming route tees its response byte-identically.
            turn = await client.post("/v1/dialogue/turn", json=payload())
            assert turn.status_code == 200
            feed1 = (await client.get("/v1/ledger/turns")).json()
            assert [e["seq"] for e in feed1["entries"]] == [1]
            assert feed1["last_seq"] == 1
            assert feed1["entries"][0]["result"] == turn.json()

            # The SSE route tees the SAME terminal result it streams.
            stream = await client.post("/v1/dialogue/turn/stream", json=payload())
            assert stream.status_code == 200
            events = _parse_sse(stream.text)
            assert events[-1][0] == "result"
            stream_result = json.loads(events[-1][1])
            feed2 = (await client.get("/v1/ledger/turns?after=1")).json()
            assert [e["seq"] for e in feed2["entries"]] == [2]
            assert feed2["last_seq"] == 2
            assert feed2["entries"][0]["result"] == stream_result

            # `after` beyond the newest entry: empty, cursor unchanged.
            drained = (await client.get("/v1/ledger/turns?after=2")).json()
            assert drained == {"entries": [], "last_seq": 2}

            # The cap: the buffer keeps exactly the newest _TURN_FEED_CAP
            # entries (tee the already-validated result object directly —
            # the cap is buffer mechanics, not turn mechanics).
            cap = api_module._TURN_FEED_CAP
            assert api_module._turn_feed.maxlen == cap
            last = api_module._turn_feed[-1].result
            for _ in range(cap + 40):
                api_module._tee_turn(last)
            capped = (await client.get("/v1/ledger/turns")).json()
            seqs = [e["seq"] for e in capped["entries"]]
            assert len(seqs) == cap
            assert seqs == list(range(2 + 40 + 1, 2 + cap + 40 + 1))
            assert capped["last_seq"] == seqs[-1]

        # Leave the module-global feed empty for whatever runs next.
        api_module._turn_feed.clear()
        api_module._turn_seq = 0

    run_structural(scene, scenario)
