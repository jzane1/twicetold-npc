# tests\ — structural-only discipline

These rules load whenever work touches this folder. Full spec: docs/test-suite.md — read it
before writing or changing any test.

## The one rule
Assert ONLY on structure: memory IDs, row types (write_cause, read_mode, typology), chain shape
(which rows are live vs invalidated), cache presence/absence, timestamps, and byte-identity of
returned text.

NEVER assert on generated prose: no substring matches, no regex over model output, no semantic
similarity checks. A model's wording is not a test surface.

## Mechanics
- Time travel = injected valid_at timestamps, plus the read path's `as_of` request override
  (adopted 2026-07-14). Tests never sleep() and never depend on wall clock.
- No fixture modes. Correction scenarios are verb-forked structural pairs keyed on write_cause.
- Deterministic: the suite must pass every run — offline, keyless, self-managing its scratch DB.
  `.github/workflows/verify.yml` runs the full suite with required database infrastructure;
  missing Postgres must fail in CI, never silently skip. The Stop hook remains the local subset.
- Judged or LLM-graded evals do not live in this folder — they belong to the separate eval story.

## When blocked
If an assertion seems to require checking prose, stop and report. The gap is usually in the
endpoint contract — IDs + scores for endpoints that RUN RETRIEVAL, IDs + structured fields for the
four unscored-by-contract reads (`/chain` and `/agents/{id}/memories`, ruled 2026-07-27;
`/memories/{id}/reconstruction-metrics`, the third member 2026-07-29; `/agents/{id}/state`, the
fourth, 2026-08-17). That is a design conversation, not a test workaround.
