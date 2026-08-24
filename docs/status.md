# longmem-npc — Status

**Last updated:** 2026-08-24
**Phase:** **Road to completion — Phases A–D DONE. Phase E (demo) PAUSED after the E3 first
attempt (recorded + QA'd 2026-08-24, master NOT cut). RE-SEQUENCED 2026-08-24 (the dated
entry): next is **F0** (whole-project audit/test/improve — latency, believability wording,
polish), then F1–F3; the demo endgame (redesign → re-record → publish) follows Phase F.**
**E3 first attempt 2026-08-24:** all four segments recorded through the new attach-mode rig
and every beat PASSED live QA (the per-segment receipts in the dated E3 entry; one nuance
carried to the captions — constancy binds the SERVED retelling, the streamed wrapper varies
by design). The cut was NOT made: footage QA found the Branwen nameplate MIRRORED in every
Unity frame plus lesser blemishes (the register: the beat script's E3 record) — **noted,
deliberately NOT fixed by ruling**: the presentation redesign owns them; the re-record runs
on a fresh provision (`--fresh` sanctioned). **The
2026-08-22 pinned state is SPENT** — a provision serves beat 1 exactly once (the correction
moves the fact chain and evicts the June caches). The E3 rig is provision-independent and
ready (driver `startAsOf`, committed scene-1 start state, OBS + ffmpeg, close card + run
sheet + raw takes under `C:\Users\jacks\Videos\longmem-demo\`); full record: the dated E3
entry + `demo-beat-script.md`'s E3 record.
**E2 landed 2026-08-19** (demo-scoped, no floors row): beat script + loader + Ledger live
feed + C# prewarm parity + the Branwen retarget; rehearsal executed 2026-08-22. The verbatim
block moved to `session-log.md`'s archive at the E3 wrap-up (size tripwire); full record in
`decisions.md`'s E2 entries.
**E1 landed 2026-08-19** (docs + data, no floor by ruling): `identity-authoring.md` +
Branwen, the drovers memory certified as the drift target — the roadmap bullet below; the
five authoring lessons in `decisions.md`'s E1 entry.
D1 (optimization, 2026-08-19, no new code): perceived-first-word **p50 938 ms**, believability
no regression (gist_precision 0.823), **model slate LOCKED** (Haiku latency-bound; Opus 4.8
batch roles in `.env.example`), workers OFF per-agent, prompt caching DEFERRED — the D1 entry.
The system is BUILT end to end on the final A1 seam — backend, C# client + console harness,
Unity adapter + gray-box scene, The Ledger, eval-harness stages 1–4, deferred writes,
reflection, the parameter compiler, the dissonance path, the agent-state read + async observes,
the purge endpoint, the concurrency cap + scene-boundary pre-warm (C7) — schema at
migrations 001–008.
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
on-screen numbers are judge-free).

**Recently closed** (pointers only): the E3 forks + the roadmap re-sequencing — ruled
2026-08-24 (the two dated entries); the E2 rehearsal blockers — cleared 2026-08-22; the
E2/E1/D1 fork batches — ruled at plan approvals 2026-08-19 (the dated entries); the C7/C6
forks — 2026-08-18. Full history lives in `decisions.md`'s index and the `session-log.md`
archive.

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
  floors row; rehearsal executed 2026-08-22 after the blockers cleared). Landed:
  `demo-beat-script.md` (correction-override lead → constancy-first drift on the certified
  drovers memory → the action-observe beat + the executed rehearsal record), the
  corpus→demo-DB loader, the Ledger live feed + identity pane + label sweep, the C#
  `PrewarmContext` mirror + harness beat [17], the `NpcMemoryNpc` passthroughs, the Branwen
  scene retarget + DLL refresh. The recording state is pinned (the header block above).
- **E3. Record + edit** — Unity + The Ledger split-screen in OBS; real providers only.
  FIRST ATTEMPT 2026-08-24: recorded + QA'd end to end, master not cut (the mirrored-nameplate
  scene flaw; the header block above). PAUSED — the demo endgame (below) now follows Phase F;
  the recording rig and cue flow are ready and provision-independent.

### Phase F — Release (~4 sessions; F0 added by the 2026-08-24 re-sequencing)

- **F0. Whole-project audit/test/improve pass** (NEW, ruled 2026-08-24) — the latency numbers
  the best they can be (inherits the deferred prompt-caching lever from C7/D1), the wording
  at its most believable, everything polished to Jack's liking. Scope settles at its own
  session spec.
- **F1. Full README build** — incl. the destructive-compression counter-example and the honest
  "what this is not" paragraph (no auth, no rate limiting; loopback-bound by default). Ships
  WITHOUT the video link (the video publishes last; the link lands in the publish step).
- **F2. Packaging** — the ruled end product: the Unity Package Manager package + the one-command
  backend spin-up (compose: Postgres/pgvector + API + migrations).
- **F3. Release hygiene + the public flip** — the Unity MCP pin fix + manifest/lockfile
  reconciliation, the committed-DLL staleness check, a sweep of the minor audit leftovers (F3
  check-8 teeth, CRLF renormalization, `~\.claude.json` duplicate keys, the Unity-gate
  session-ordering note — swept or consciously dropped), docs finalization, Apache-2.0 flip.

### The demo endgame (AFTER Phase F — re-sequenced 2026-08-24)

1. **The presentation redesign** — Jack's rulings at its own session; the E3 flaw register
   in `demo-beat-script.md` is its input.
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

- **The walkers (fifteen since C7-B) share a fixed-name scratch DB** (`longmem_test`) they neither
  create, migrate, nor drop, and some walker assertions are DB-global counts. The right fix —
  the suite's pid-scoped mechanism plus a `tests\run-walkers.ps1` runner — is a medium refactor
  of the verification apparatus itself, so it wants its own scoped task rather than riding an
  audit. THREE documented bites (the first two verbatim in the session-log archive, moved
  2026-08-17): 2026-08-12 (the DB found MISSING; psycopg_pool masked it as a 30 s
  `PoolTimeout`), 2026-08-17 (`verify_reflection` is non-re-runnable on the persistent
  scratch — a fresh pid-scoped scratch is that walker's documented precondition), and
  2026-08-17 again at the C4 landing (the elder correction walkers' DB-global
  corrections-emptiness asserts vs the re-opened `verify_reconstruction` — sweeps must run
  fresh + serial, elder walkers first; the C4 build record has the detail). *(The other
  2026-07-28 carried items — the auth honesty paragraph, the Unity MCP pin, the DLL
  staleness check — are scheduled: Phase F.)*
