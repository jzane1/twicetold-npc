# twicetold-npc — Status

**Last updated:** 2026-09-02
**Phase:** **Road to completion — Phases A–D DONE; Phase E PAUSED (E3 first attempt
recorded + QA'd, master not cut). F0 DONE 2026-08-26; the consumer-context scan DONE
2026-09-01. The naming session (longmem-npc → twicetold-npc) IN PROGRESS 2026-09-02 —
in-repo half landed + self-verified; operator swap pending Jack. Next: finish the rename →
the provider + purge build → F1 → F2–F3; the demo endgame follows Phase F.**
**The rename → `twicetold-npc` (2026-09-02):** the in-repo half is LANDED and self-verified
— 243 replacements across 55 files, full suite **193 passed**, all **15 walkers** green
fresh+serial on `twicetold_test`, C# harness **53 checks** green, real-mode `load_settings`
boots on the `TWICETOLD_` keys; `git grep -i longmem` returns only the ruled allowlist. The
dated `decisions.md` entry carries the pick, the collision check, the four scope rulings, the
allowlist, and the `PRODUCT_DB`↔`.env` lockstep note. **Operator swap LANDED + verified
2026-09-02:** `.env` renamed (Jack), GitHub repo renamed + remote re-pointed (Jack), Docker
volume recreated (old `longmem-pgdata` orphaned, fresh `twicetold-pgdata`), migrations
fresh-applied to `twicetold` + no-op idempotency, the `PRODUCT_DB`↔`.env` lockstep proven
(guard now refuses the real product DB), 178-subset green on the recreated container.
**Still pending:** the local folder rename + Claude project-state copy (Jack, next); then in
the renamed folder — the demo-DB `--fresh` rebuild (real spend) + hero-PNG re-capture + the
DLL rebuild/copy + the independent floor-verifier pass (commit-2). Count stays 32.
**Consumer-context scan landed 2026-09-01** (research-only; no floors row): five streams —
OSS-memory reception, game-dev/platform sentiment, novelty stress test + name check,
release-hygiene norms, a cold consumer agent (verdict: adopt-for-a-spike; its one BLOCKED
step, the shipped-game deployment story, is F1's top addition). The novelty claim
SURVIVES; the license chain is CLEAN for the flip; README staleness is active trust
damage. Four rulings (the dated `decisions.md` entry): the OpenAI-compatible provider
path builds PRE-release; the per-agent purge verb builds; the project RENAMES before the
flip; the Ledger host guard lands in F3. Report + per-phase input packs:
`docs\research\consumer-context-scan-2026-08-31.md`.
**F0 landed 2026-08-26** — registers reconciled (suite **193/178**; floors rows 28–32
restored), the overlap + pool knob, the gated prompt pair (**dialogue input −51%; all-in
$0.084/100 turns**; NO regression); p50 826–917 ms; the D1 attribution CLOSED. The
floors.md Re-verification entry + the dated F0 entry; the verbatim block is in the
session-log archive (2026-09-01 tripwire move).
**E3 first attempt 2026-08-24:** recorded + QA'd, master NOT cut (mirrored nameplate —
the presentation redesign owns it); **the 2026-08-22 pinned state is SPENT** (`--fresh`
sanctioned); the rig is ready. The dated E3 entry + `demo-beat-script.md`'s E3 record.
E2/E1/D1 (all 2026-08-19): choreography + corpus + the slate-lock pass — archived at the
F0 wrap-up; the roadmap bullets + dated entries carry the records.
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

**Pending Jack (from the D1 landing, non-blocking):** (1) **ratify or redirect the
dissonance-multiplier defaults** — D1 found no objective metric to tune them against, so the
principled ordering was kept unchanged (an eyeball run of the defend/update beat is available on
request); (2) offline gold re-labeling if
calibrated judged-prose numbers are wanted on screen (kappa 0.37, unquotable — non-blocking; the
on-screen numbers are judge-free). Plus two F0 micro-calls (non-blocking, the F0 entry): drop
the orphaned `longmem_eval_14188` scratch DB; the `min_size` sibling knob.

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

- **E1. Identity authoring guide + demo corpus.** ✅ DONE 2026-08-19 (docs + data only; no
  floors row by ruling) — the header pointer above; the E1 `decisions.md` entry has the
  five authoring lessons.
- **E2. Choreography + rehearsal.** ✅ DONE (built 2026-08-19, demo-scoped by ruling — no
  floors row; rehearsal executed 2026-08-22). `demo-beat-script.md` + the loader + the
  Ledger live feed + C# prewarm parity + the Branwen retarget; the verbatim bullet is in
  the session-log archive (2026-09-01 tripwire move); full record: the E2 entries.
- **E3. Record + edit** — Unity + Ledger split-screen in OBS; real providers only. FIRST
  ATTEMPT 2026-08-24: recorded + QA'd, master not cut (the header block above). PAUSED —
  the demo endgame follows Phase F; the rig is ready and provision-independent.

### Phase F — Release (F0 + the scan DONE; ~5–6 sessions remain)

- **F0. Whole-project audit/test/improve pass.** ✅ DONE 2026-08-26 (spec-at-plan → build →
  independent floor-verify **pass**; no new floors row — the Re-verification entry). Header
  block above = the summary; the dated F0 `decisions.md` entry = the full record (rulings,
  measurements, the ceiling, forks, incident lessons).
- **The consumer-context scan.** ✅ DONE 2026-09-01 (research-only; the header block above;
  report: `docs\research\consumer-context-scan-2026-08-31.md`).
- **The naming session** (ruled 2026-09-01 — rename before the flip). IN PROGRESS 2026-09-02:
  name = **twicetold-npc**; the in-repo sweep (code + docs + tests + env prefix + DB names)
  is landed and self-verified (the header block above + the dated `decisions.md` entry). The
  operator swap (`.env`, Docker volume, demo rebuild, DLL rebuild, hero PNG, GitHub rename,
  folder rename, independent floor-verify) is the remaining checklist, handed to Jack.
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

1. **The presentation redesign** — Jack's rulings at its own session; the E3 flaw register
   in `demo-beat-script.md` is its input, and the scan's showcase post-mortem pack (report
   Part 4) is its second input.
2. **The re-record** (the E3 second attempt) — fresh provision + re-pin (`--fresh`
   sanctioned; a provision serves beat 1 exactly once), record + edit on the proven rig.
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
