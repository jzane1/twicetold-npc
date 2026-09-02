"""serve.py — Windows-safe uvicorn runner for the ingestion API.

psycopg's async pool cannot run on Windows' default ProactorEventLoop, and
uvicorn 0.51 serves on Proactor there — so this runner starts uvicorn on a
SelectorEventLoop explicitly. Use this, not bare `uvicorn app.api:app`.

    PowerShell:  python -m app.serve [--host 127.0.0.1] [--port 8000]
"""

from __future__ import annotations

import argparse
import asyncio

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="twicetold-npc ingestion API server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--log-level", default="info")
    args = parser.parse_args()

    config = uvicorn.Config(
        "app.api:app", host=args.host, port=args.port, log_level=args.log_level
    )
    server = uvicorn.Server(config)
    asyncio.run(server.serve(), loop_factory=asyncio.SelectorEventLoop)


if __name__ == "__main__":
    main()
