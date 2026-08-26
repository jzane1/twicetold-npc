"""scratch_uri.py — re-export shim (promoted 2026-08-05, eval-harness stage 2).

The verified rewrite now lives in `app\\scratch_db.py` so the eval runner can
share it. `conftest.py` and the walkers (fifteen since C7-B, 2026-08-18) import
from here byte-untouched; every importer inserts the repo root on sys.path
before importing this module, so the app import resolves without a path shim
here.
"""

from __future__ import annotations

from app.scratch_db import ScratchUriError, scratch_uri

__all__ = ["ScratchUriError", "scratch_uri"]
