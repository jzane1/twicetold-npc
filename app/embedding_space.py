"""Database embedding identity, shared by runtime startup and setup diagnostics.

The binding is immutable through application code. Keys are never included;
the endpoint is hashed so credentials cannot enter the metadata or diagnostics.
"""

from __future__ import annotations

import hashlib
from urllib.parse import urlsplit, urlunsplit

from app.config import EMBEDDING_DIM, OPENAI_HOSTED_BASE_URL, ConfigError, Settings

MISMATCH = (
    "Embedding configuration does not match this database. Restore its original "
    "provider mode, embedding model and endpoint, or use a new database. "
    "Changing chat models is safe; changing embedding spaces is not. "
    "See docs/SETUP.md: Changing providers safely."
)
LEGACY = (
    "This database has vectors but no recorded embedding configuration. "
    "Stop its writers and verify the ORIGINAL embedding mode/model/endpoint, "
    "then run python -m app.doctor --adopt-existing-embeddings with that configuration. "
    "If provenance is unknown or mixed, use a new database; adoption does not re-embed."
)


class EmbeddingSpaceError(ConfigError):
    """The database's vector provenance needs operator attention."""


def embedding_configuration(settings: Settings) -> dict:
    if settings.provider_mode == "fake":
        return {
            "version": 1,
            "mode": "fake",
            "model": "sha256-trigrams-v1",
            "dimensions": EMBEDDING_DIM,
        }
    url = urlsplit(settings.embedding_base_url or OPENAI_HOSTED_BASE_URL)
    host = (url.hostname or "").lower()
    if ":" in host:
        host = f"[{host}]"
    port = url.port
    if port and (url.scheme.lower(), port) not in {("https", 443), ("http", 80)}:
        host += f":{port}"
    endpoint = urlunsplit((url.scheme.lower(), host, url.path.rstrip("/"), "", ""))
    return {
        "version": 1,
        "mode": "real",
        "model": settings.embedding_model,
        "dimensions": EMBEDDING_DIM,
        "fit": "zero-pad-v1",
        "endpoint_sha256": hashlib.sha256(endpoint.encode()).hexdigest(),
    }


def binding_status(stored: dict | None, requested: dict, has_vectors: bool) -> str:
    if stored is not None:
        if stored != requested:
            raise EmbeddingSpaceError(MISMATCH)
        return "matched"
    return "legacy" if has_vectors else "unbound"
