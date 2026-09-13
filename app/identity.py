"""identity.py — the rendered identity document (architecture §4.3, item 2).

The render is seed prose plus the agent's live identity-relevant reflection
contents in stable chronology, joined by blank lines — no template
(a template would be a hidden hardcoded authorial artifact). With zero
reflections the render is the seed VERBATIM — the parity contract every
pre-C2 hash, cache key, prompt, and floor stands on. identity_version =
sha256 hex of the rendered text, exactly as before.

Plumbing (spec-time ruling 2026-07-17, the caller-frozen-scene-state
precedent):
the scene-boundary handler recompiles server-side via ensure_identity_document
and returns identity_version; the caller freezes it as scene state and passes
it on each read request. A read arriving without a version lazy-bootstraps
through the same ensure. A NULL seed renders as the empty string (hashed like
any document); the reconstruction prompt omits the identity block for it.
Since the C2 build the dialogue prompt rides this document too (the
raw-seed asymmetry closed by ruling, 2026-08-15).
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from uuid import UUID

from psycopg_pool import AsyncConnectionPool

from app import db


def render_identity_document(
    seed_identity: str | None,
    reflection_contents: Sequence[str] = (),
) -> tuple[str, str]:
    """(rendered_text, identity_version) — pure, so the walker asserts the
    hash contract without a database. The literal formula (reflection.md):
    seed prose then each live identity-relevant reflection's content, joined
    "\\n\\n". Zero reflections => the seed verbatim (a NULL seed is the
    empty string), byte-for-byte the pre-C2 render."""
    seed = seed_identity if seed_identity is not None else ""
    rendered = "\n\n".join([seed, *reflection_contents])
    version = hashlib.sha256(rendered.encode()).hexdigest()
    return rendered, version


async def ensure_identity_document(
    pool: AsyncConnectionPool, agent_id: UUID, seed_identity: str | None
) -> tuple[str, str, bool]:
    """Render, hash, and upsert the current document. Returns
    (identity_version, rendered_text, created) — created is False when this
    exact version already existed (recompiling unchanged inputs is a no-op
    row-wise; the version is stable because the content hash is). Fetches
    the live identity-relevant reflection contents itself (C2 ruling: both
    pre-existing call sites keep their shape; an empty reflections table
    reproduces the pre-C2 render exactly)."""
    rows = await db.fetch_live_identity_reflections(pool, agent_id)
    rendered, version = render_identity_document(
        seed_identity, [row.content for row in rows]
    )
    created = await db.upsert_identity_document(pool, agent_id, rendered, version)
    return version, rendered, created
