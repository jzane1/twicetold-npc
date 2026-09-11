# twicetold-npc — Status

**Last updated:** 2026-09-11
**Phase:** **Road to completion — Phases A–D DONE; Phase E PAUSED (E3 first attempt
recorded + QA'd, master not cut). F0 DONE 2026-08-26; the consumer-context scan DONE
2026-09-01; the rename DONE 2026-09-02; the provider-path + per-agent-purge build DONE
2026-09-02 (floors row 33); F1 DONE 2026-09-03, hero rebuilt 2026-09-11 (no floor by design).
Next: Jack's README deep review + the deferred agent-framing/loop copy reframe, then the
token-limit knob (half a session) → F2–F3; the demo endgame follows Phase F.**
**F1 DONE 2026-09-03, hero rebuilt 2026-09-11** (the `decisions.md` F1 entry + Review round 1/2
are the full record; Jack's deep review is the gate before any push): README first-person and
short, `docs\first-npc.md` + `docs\shipping.md`, NOTICE + docs index touched. The hero is
`docs\media\showcase-hero.png`, a static capture of a NEW display-only Ledger showcase view
(`?view=showcase` in `ledger\index.html`, additive) built after the motion GIF read as
undecipherable; its before/after of the Aldous memory (`readme-shot.jsonl`) holds 11/11 facts,
detail 0.647, 0 fabricated. One code touch beyond the CLI banner (the showcase view); no
migration, no floor; counts unchanged (226 / 211, 16 walkers, 33). DEFERRED: the approved
agent-framing/loop copy reframe.
**Earlier this phase** (provider path + rename 2026-09-02; consumer scan 2026-09-01; F0
2026-08-26; E1–E3 + D1 2026-08-19/24): the roadmap bullets + the dated `decisions.md` entries +
the `session-log.md` archive hold the full records. Live headline: **$0.084/100 turns all-in**
(Anthropic slate), perceived p50 **826–917 ms**, believability no-regression, the model slate
LOCKED, the demo rig ready (E3 master not cut, `--fresh` sanctioned).
The system is BUILT end to end on the final A1 seam (two model backends, the C# client +
harness, the Unity gray-box scene, The Ledger, eval stages 1–4, the C-phase workers +
dissonance path, agent-state + async observes, the two purge verbs, the concurrency cap +
pre-warm; migrations 001–008). What is proven lives in `docs\floors.md`, why in `decisions.md`,
the narrative in `session-log.md`; this file carries only what is live.

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
judge-free); (3) the `min_size` DB-pool sibling knob (the F0 entry). *(The former item 4, the
token-limit-field knob, was RULED 2026-09-03 at the F1 batch: documented now, built as its
own target — the roadmap bullet below. The orphaned `longmem_eval_14188` scratch is moot — it
lived on the volume the rename orphaned.)*

**Recently closed** (full list in `decisions.md`'s index): the F1 forks + Review round 1/2
(2026-09-03/11), the provider-path and consumer-scan forks (2026-09-02/01), F0 (2026-08-26),
the E3 forks + re-sequencing (2026-08-24), and earlier batches.

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

### Phase F — Release (F0 → the provider-path build DONE; ~3–4 sessions remain)

- **F0. Whole-project audit/test/improve pass.** ✅ DONE 2026-08-26 (spec-at-plan → build →
  independent floor-verify **pass**; no new floors row — the Re-verification entry). The dated
  F0 `decisions.md` entry = the full record (rulings, measurements, the ceiling, forks,
  incident lessons).
- **The consumer-context scan.** ✅ DONE 2026-09-01 (research-only; report:
  `docs\research\consumer-context-scan-2026-08-31.md`; four rulings in the dated entry).
- **The naming session.** ✅ DONE + independently re-verified 2026-09-02 — name
  **twicetold-npc**; in-repo sweep + operator swap + DLL rebuild + the floor-verifier pass; the
  local folder rename dropped (the dated rename entry + the floors.md re-verification entry).
  Folded onward: the hero PNG → F1, the Unity Editor re-check → F3.
- **The provider-path + per-agent-purge build.** ✅ DONE 2026-09-02 (plan-to-floor; the header
  block above; the dated `decisions.md` entry; floors row 33). Folded onward: the F1
  providers-section pointer and pending item 4.
- **F1. Full README build.** ✅ DONE 2026-09-03; **hero rebuilt 2026-09-11** (the dated
  `decisions.md` entry + Review round 1/2 = the full record). Ships WITHOUT the video link (it
  lands in the publish step). The scan's input pack, the NOTICE f-coref line, the hero
  re-capture, and the providers section all landed; the deferred agent-framing/loop copy
  reframe (recruiter-audience lens) is the standing follow-on.
- **The token-limit-field knob** (ruled 2026-09-03: its own half-session target) —
  `TWICETOLD_MODEL_TOKEN_LIMIT_FIELD` = `max_tokens` | `max_completion_tokens`, default the
  former (~10 lines + a config row + two scenarios + a walker criterion + the provider-path
  floor re-verified), **plus the one-line README touch** Jack asked for when it lands.
- **F2. Packaging** — the ruled end product: the Unity Package Manager package + the one-command
  backend spin-up (compose: Postgres/pgvector + API + migrations). Inherits the scan's
  compose + UPM conformance lists (report Part 2).
- **F3. Release hygiene + the public flip** — the Ledger TrustedHost guard (ruled
  2026-09-01), the Unity MCP pin fix + manifest/lockfile reconciliation, the Unity Editor
  re-check, the committed-DLL staleness check, a sweep of the minor audit leftovers (F3
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

- **The walkers (sixteen since the provider path) share a fixed-name scratch DB**
  (`twicetold_test`) they neither create, migrate, nor drop; some assertions are DB-global
  counts, so sweeps run fresh + serial, elder walkers first. The right fix (the suite's
  pid-scoped mechanism + a `tests\run-walkers.ps1` runner) wants its own scoped task. THREE
  documented bites — the verbatim register is in the session-log archive. *(The other
  2026-07-28 carried items — the auth honesty paragraph, the Unity MCP pin, the DLL staleness
  check — are scheduled: Phase F.)*
