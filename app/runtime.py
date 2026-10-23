"""Fail before NLP warm-up or provider work when the database is incompatible."""

import asyncio

from psycopg import Error as DatabaseError
from psycopg_pool import PoolTimeout

from app.config import ConfigError, Settings
from app.db import build_pool, check_runtime_database, ensure_embedding_space


async def open_runtime_pool(settings: Settings):
    pool = build_pool(settings.database_uri, max_size=settings.db_pool_max_size)
    try:
        await pool.open(wait=True, timeout=10)
        async with asyncio.timeout(10):
            await check_runtime_database(pool, settings, require_binding=False)
            await ensure_embedding_space(pool, settings)
        return pool
    except (DatabaseError, PoolTimeout, TimeoutError):
        await pool.close()
        raise ConfigError(
            "Database startup check failed. Check connectivity and apply pending "
            "migrations; run python -m app.doctor for diagnostics."
        ) from None
    except BaseException:
        await pool.close()
        raise
