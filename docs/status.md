# twicetold-npc — Status

**Last updated:** 2026-09-02
**Phase:** **Road to completion — Phases A–D DONE; Phase E PAUSED (E3 first attempt
recorded + QA'd, master not cut). F0 DONE 2026-08-26; the consumer-context scan DONE
2026-09-01. The rename (longmem-npc → twicetold-npc) DONE 2026-09-02 bar a carried
finalization; the local folder rename is dropped. Next: the rename finalization → the
provider + purge build → F1 → F2–F3; the demo endgame follows Phase F.**
**The rename → `twicetold-npc` (2026-09-02):** the in-repo sweep (243 replacements / 55 files)
and the operator swap both LANDED + verified — full suite **193**, all **15 walkers** on
`twicetold_test`, **C# harness 53**, real-mode `load_settings` on the `TWICETOLD_` keys; then
`.env` + GitHub renamed (Jack), Docker recreated to `twicetold-pg`/`twicetold-pgdata` (old
volume orphaned), migrations fresh-applied to `twicetold` + no-op, the `PRODUCT_DB`↔`.env`
lockstep proven, 178-subset green (commits `90f4c23`, `ec64ad8`). `git grep -i longmem`
returns only the ruled allowlist. The **local folder rename is DROPPED** (Windows lock +
Jack's ruling — local-only/invisible, so the folder and this session's memory-dir key stay
`longmem-npc`). **Carried (a future session, same folder):** the demo `--fresh` rebuild (real
spend) + hero-PNG re-capture + the DLL rebuild (exception-string refresh) + the independent
floor-verifier pass. Count 32. Full record: the dated `decisions.md` rename entry + the
`session-log.md` entry.
**Consumer-context scan landed 2026-09-01** (research-only; no floors row): novelty claim
SURVIVES, license chain CLEAN for the flip, README staleness is active trust damage; the
cold consumer's one BLOCKED step (the shipped-game deployment story) is F1's top addition.
Four rulings (the dated `decisions.md` entry): provider path pre-release, per-agent purge,
the rename, the Ledger F3 guard. Report + per-phase input packs:
`docs\research\consumer-context-scan-2026-08-31.md`.
**Earlier this phase** (F0 2026-08-26; E1–E3 + D1 2026-08-19/24; the consumer scan above):
the roadmap bullets below + the dated `decisions.md` entries + the `session-log.md` archive
carry the full records. Headline state that stays live: **$0.084/100 turns all-in**, perceived
p50 **826–917 ms**, believability no-regression, the model slate LOCKED, the demo rig ready
(E3 master not cut — the presentation redesign owns the flaws; the pinned state is SPENT,
`--fresh` sanctioned).
The system is BUILT end to end on the final A1 seam — backend, C# client + harness, Unity
adapter + gray-box scene, The Ledger, eval stages 1–4, deferred writes, reflection, the
compiler, the dissonance path, agent-state + async observes, purge, the concurrency cap +
pre-warm — schema at migrations 001–008.
What is proven lives in `docs\floors.md`, why in `decisions.md`, the narrative in
`session-log.md`; this file carries only what is live.

This is the *living* file — update it at the end of every working session. `architecture.md`
changes only when design changes; `decisions.md` is append-only. Size tripwire (ruled
2026-08-17): this file leaves every wrap-up at or under ~12 KB; anything past the line moves
verbatim into `session-log.md`'s archive — trimmed, never deleted.

## End products & framing (re-ruled 2026-08-04)

Three end products, nothing else: **the demo video**, **a Unity Package + one-command backend
spin-up**, and **the public GitHub repo** (Apache-2.0). The research track is scrapped — no
write-up, no submission. The mid-to-late-August demo date is **dropped by ruling**: quality
drives, and the demo lands after Phases A–D. Portfolio target unchanged: tier-1
embodied-agent / game-AI employers — the instrumentation table, the test suite, and the
on-screen eval numbers are what survive the interview. The demo records real-providers-only
(ruled 2026-07-22).

## Build discipline

- **Staged verification:** each layer verifies against a known-good layer beneath it, so failures
  have a single cause. Anything renamed or ported is re-verified before it counts as a floor.
- **Instrument at the seam:** when building a layer, its timing and token accounting land in the
  same task. Framework choices must survive the interview; ceremony scores below absence.
- Unity is the demo vehicle; the gray-box scene recorded is the fallback video. The CLI/REPL
  remains the debug product surface (memory IDs, scores, token counts exposed).

## Verified floors

The full table — layer, what it was verified against, and the date — lives in
**`docs\floors.md`** (moved there 2026-07-28 so this living file stays small enough to
auto-load). That file states the counting convention; cite it rather than a number in prose.

A row lands there only after an independent floor-verifier pass returns **pass**. Floors are
re-openable: re-verifying one is a step, never an argument against a design improvement.

## Open questions needing Jack's ruling

**Pending Jack (non-blocking):** (1) **ratify or redirect the dissonance-multiplier defaults**
— D1 found no objective metric to tune them against, so the principled ordering was kept
unchanged (an eyeball run available on request); (2) offline gold re-labeling if calibrated
judged-prose numbers are wanted on screen (kappa 0.37, unquotable; the on-screen numbers are
judge-free); (3) the `min_size` DB-pool sibling knob (the F0 entry). *(The orphaned
`longmem_eval_14188` scratch is now moot — it lived on the `longmem-pgdata` volume the
2026-09-02 rename orphaned; it vanishes when that volume is pruned.)*

**Recently closed** (pointers only): the four consumer-scan forks — ruled 2026-09-01 at one
batch (provider path pre-release, per-agent purge, the rename, the Ledger guard — the dated
entry); the F0 spec forks — 2026-08-26 (the dated F0 entry; README ruled wholly to F1); the
E3 forks + the re-sequencing — 2026-08-24; earlier batches — `decisions.md`'s index and the
`session-log.md` archive.

## The roadmap (re-planned 2026-08-04; ordering delegated to Claude on efficiency grounds)

Sizes are rough working-session counts, not dates — **~18–22 sessions to the finish line.**
Every build session keeps the standing discipline: settle forks at spec, build, walkers,
independent floor-verify, docs, commit. After each Phase C landing, a harness run checks
believability didn't regress (the point of doing Phase B first).

### Phases A + B — DONE

A1 (2026-08-04, floors rows 19/21) and B1–B3 (2026-08-05/07/12, floors rows 22–24). The
verbatim blocks moved to `session-log.md`'s archive at the E1 wrap-up (size tripwire).

### Phases C + D — DONE

C1–C7 (floors rows 25–32, each plan-to-floor) and D1 (2026-08-19, measure-only: 938 ms p50
confirmed, slate LOCKED, no floor). The verbatim blocks moved to `session-log.md`'s archive at
the E2 wrap-up (size tripwire); full records in `floors.md` + `decisions.md`.

### Phase E — Demo (E1–E2 DONE; the endgame re-sequenced AFTER Phase F, ruled 2026-08-24)

- **E1 + E2** ✅ DONE 2026-08-19 (identity guide + corpus; choreography + loader + Ledger feed
  + prewarm parity + the Branwen retarget; demo-scoped, no floors rows; rehearsal executed
  2026-08-22) — full records in the E1/E2 `decisions.md` entries + the session-log archive.
- **E3. Record + edit** (Unity + Ledger split-screen, real providers). FIRST ATTEMPT
  2026-08-24: recorded + QA'd, master not cut (the header block above). PAUSED — the demo
  endgame follows Phase F; the rig is ready and provision-independent.

### Phase F — Release (F0 + the scan DONE; ~5–6 sessions remain)

- **F0. Whole-project audit/test/improve pass.** ✅ DONE 2026-08-26 (spec-at-plan → build →
  independent floor-verify **pass**; no new floors row — the Re-verification entry). Header
  block above = the summary; the dated F0 `decisions.md` entry = the full record (rulings,
  measurements, the ceiling, forks, incident lessons).
- **The consumer-context scan.** ✅ DONE 2026-09-01 (research-only; the header block above;
  report: `docs\research\consumer-context-scan-2026-08-31.md`).
- **The naming session** (ruled 2026-09-01). ✅ DONE 2026-09-02 bar a carried finalization —
  name **twicetold-npc**, in-repo sweep + operator swap landed + verified, local folder rename
  dropped (the header block above; the dated `decisions.md` rename entry). Carried to a future
  session (same folder): the demo `--fresh` rebuild + hero-PNG re-capture + DLL rebuild + the
  independent floor-verifier pass.
- **The provider-path + per-agent-purge build** (NEW, ruled 2026-09-01): an
  OpenAI-compatible base-URL provider path for the model + embedding roles, shipped WITH
  the documented small-model quality warning (~1–2 sessions; floor re-verify), plus
  `DELETE /v1/agents/{id}/memories` as a thin extension of the C6 purge carve-out (may
  ride the same session).
- **F1. Full README build** — incl. the destructive-compression counter-example and the honest
  "what this is not" paragraph (no auth, no rate limiting; loopback-bound by default). Ships
  WITHOUT the video link (the video publishes last; the link lands in the publish step).
  Inherits the scan's F1 input pack (report Part 3 + the NOTICE f-coref line).
- **F2. Packaging** — the ruled end product: the Unity Package Manager package + the one-command
  backend spin-up (compose: Postgres/pgvector + API + migrations). Inherits the scan's
  compose + UPM conformance lists (report Part 2).
- **F3. Release hygiene + the public flip** — the Ledger TrustedHost guard (ruled
  2026-09-01), the Unity MCP pin fix + manifest/lockfile
  reconciliation, the committed-DLL staleness check, a sweep of the minor audit leftovers (F3
  check-8 teeth, CRLF renormalization, `~\.claude.json` duplicate keys, the Unity-gate
  session-ordering note — swept or consciously dropped), docs finalization, Apache-2.0 flip.

### The demo endgame (AFTER Phase F — re-sequenced 2026-08-24)

1. **The presentation redesign** (its own session) — inputs: the E3 flaw register in
   `demo-beat-script.md` + the scan's showcase post-mortem pack (report Part 4).
2. **The re-record** (E3 second attempt) — fresh provision + re-pin (`--fresh` sanctioned),
   record + edit on the proven rig.
3. **The video publish** — plus the small README video-link touch.

**The finish line: repo public + video published + package downloadable.**

### Phase G — Optional epilogue (time-permitting, explicitly droppable)

- **The personal-website embed** (REPLACED the real-game plug-in clip by the 2026-08-24
  re-sequencing): embed the project into Jack's personal website so people browsing it can
  interact with it somehow. Details deliberately deferred — decided only if this step is
  ever brought forward into a working session.

## Cut from scope (ruled 2026-08-04)

The full list (research track, split-brain behavior side, graph memory, the stretch list, the
August date) moved verbatim to `session-log.md`'s archive at the E1 wrap-up (size tripwire);
the ruling itself is `decisions.md` 2026-08-04. Nothing has been added back.

## Session log

In **`docs\session-log.md`** — append one entry per session there, at the end of the entry list
(before the archive section), in the honest landed/blocked/abandoned wording `/wrap-up` asks
for. The pre-2026-08-04 status narrative and superseded queues live in that file's archive.

## Repo conventions

Public GitHub (ruled 2026-08-13, the flip pulled ahead of Phase F — the interim-README entry
in `decisions.md`; the v1 *release* still exits through Phase F, purge included). Commit at
least weekly. Secrets in `.env` only
(`.env.example` is the tracked template). Always PowerShell, backslash paths.

Mechanically enforced since 2026-07-28: `ruff format` **and** `ruff check` on every edit (pinned
version, rules in `ruff.toml`); the `-m "not nlp"` suite subset at every turn end;
`.gitattributes` normalizing line endings to LF. Licensing is settled — `LICENSE` (Apache-2.0)
and `NOTICE` (the third-party inventory; psycopg is the one copyleft dependency, LGPL-3.0-only,
not vendored).

**Carried, not fixed** (deliberately unscheduled, awaiting its own ruling):

- **The walkers (fifteen since C7-B) share a fixed-name scratch DB** (`twicetold_test`) they
  neither create, migrate, nor drop; some assertions are DB-global counts, so sweeps run
  fresh + serial, elder walkers first. The right fix (the suite's pid-scoped mechanism + a
  `tests\run-walkers.ps1` runner) wants its own scoped task. THREE documented bites — the
  verbatim register is in the session-log archive (2026-09-01 tripwire move; the first two
  archived fuller 2026-08-17; the C4 build record has the third's detail). *(The other
  2026-07-28 carried items — the auth honesty paragraph, the Unity MCP pin, the DLL
  staleness check — are scheduled: Phase F.)*
