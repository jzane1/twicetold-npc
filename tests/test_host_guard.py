"""The Ledger host guard (docs\\architecture.md): TrustedHostMiddleware rejects
any request whose Host header is not in the allowlist, closing the
DNS-rebinding / CSRF class that bites localhost-only inspector tools.

Route-level, unmarked: /openapi.json needs no DB or lifespan, so the module app
is driven directly over ASGI transport. The allowlist is bound at import from
load_allowed_hosts(); with the knob unset the shipped default (loopback only)
is what these assertions exercise.
"""

from __future__ import annotations

from app.config import ALLOWED_HOSTS_DEFAULT, load_allowed_hosts


def test_allowed_hosts_knob_parses_and_defaults():
    """The knob is a real, integrator-tunable allowlist: comma-separated,
    trimmed, empties dropped; unset or blank falls back to loopback."""
    assert ALLOWED_HOSTS_DEFAULT == ("localhost", "127.0.0.1")
    assert load_allowed_hosts() == ALLOWED_HOSTS_DEFAULT
    assert load_allowed_hosts(
        {"TWICETOLD_ALLOWED_HOSTS": "a.example, b.example ,"}
    ) == (
        "a.example",
        "b.example",
    )
    assert (
        load_allowed_hosts({"TWICETOLD_ALLOWED_HOSTS": "   "}) == ALLOWED_HOSTS_DEFAULT
    )


def test_host_guard_allows_loopback_and_rejects_foreign():
    """Requests carrying a loopback Host pass the middleware; a foreign Host is
    rejected 400 before reaching any route."""
    import asyncio

    import httpx

    import app.api as api_module

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=api_module.app)
        for host in ("localhost", "127.0.0.1"):
            async with httpx.AsyncClient(
                transport=transport, base_url=f"http://{host}"
            ) as client:
                allowed = await client.get("/openapi.json")
                assert allowed.status_code == 200, host
        async with httpx.AsyncClient(
            transport=transport, base_url="http://evil.example"
        ) as client:
            rejected = await client.get("/openapi.json")
            assert rejected.status_code == 400
            assert "host" in rejected.text.lower()

    asyncio.run(scenario())
