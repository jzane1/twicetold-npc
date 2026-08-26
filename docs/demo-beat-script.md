# The demo beat script (E2, 2026-08-19)

The final choreography for the E3 recording: three beats + a close, ~75 seconds, split-screen
(Unity gray-box left, The Ledger right in a browser, composited in OBS). Beat order is ruled
(the 2026-07-22 audit's R4): **correction-override leads** — studios buy NPCs that remember
correctly before they buy controlled drift. The drift beat is framed constancy-first (gist
holds, texture drifts, on a budget, on purpose). The old beat 3 (split-brain divergence) is
dead (scrapped 2026-08-04); its slot is the game-authored action-observe beat.

Everything here runs on the demo DB (`longmem_demo`), real providers only (ruled 2026-07-22),
agent **Branwen of the Waystone Inn** (`data\eval\corpora\demo-waystone.jsonl`, authored and
validated in E1 — `identity-authoring.md` §8). On-screen text obeys the em-dash ban
(2026-08-13).

## The rig

- Backend: `.env` pointing `DATABASE_URI` at `longmem_demo`, `LONGMEM_PROVIDER_MODE=real`,
  the six live roles per the D1 slate (Haiku latency-bound) **plus the two batch roles synced
  to Opus 4.8 — the demo agent's workers are ON, so the pending-Jack `.env` sync binds here**
  (C3's first real compile is the worker's; a missing `LONGMEM_MODEL_COMPILER` lands a
  `failed` run row on camera).
- `python -m app.serve`, then The Ledger at `http://127.0.0.1:8000/ledger?agent=<agent-id>`
  with **poll ON** (the 2 s poll drives the index, the chain view, the identity pane, and the
  live turn feed).
- Unity: `SampleScene` — the adapter is committed attach-mode (`autoProvision` off);
  paste the loader's printed agent id into `agentIdOverride` before Play. The driver's
  inspector carries the beat controls: `correctionMemoryId` (paste ref 0's memory id),
  `correctionText` (below), `prewarmContext` (committed as the beat-1 Halvard question —
  the scene-1 start state; flipped to the drovers question at the scene-2 cut), `sayK`
  (see the k rule below), `jumpDays = 60`, and **`startAsOf`** (E3, 2026-08-24: applied
  via `SetAsOf` once the adapter attaches, so Play alone lands the June-25 basis — attach
  mode previously had NO operator surface for the starting clock and would have run at
  real now, re-rolling the pinned June layer).
- **The k rule (a 2026-08-22 rehearsal finding): beat-1 asks run at k=9, beat-2 at k=3.**
  At the June-25 basis under the real corpus config, 23 days of episodic decay (tau 10 d)
  buried the June-2 Halvard memory below k=3 — the E1 correction probe had only certified
  k=3 under the neutralized eval config, not the live condition. k = corpus size makes
  beat-1 membership roll-proof. Choreography: `sayK = 9` through scene 1, flip the
  inspector field to `3` at the scene-2 cut (beat 2 keeps its certified condition).
  Scene 1's boundary also carries a prewarm probe (the beat-1 question), so the June-basis
  retells roll during the cut, not inside the first on-camera ask.
- OBS frame (0–8 s): left "what the character says", right "what they actually remember,
  and how". The Ledger's identity pane shows Branwen's seed identity on camera (E1 ruling).

## Timeline

The corpus's June runs 2026-06-02 → 2026-06-24T21:00Z (nine observes). The demo session:

| Step | Session as_of |
|---|---|
| Scene 1 (beats 0–1) | 2026-06-25T19:00Z |
| Scene 2 (beat 2) | +60 days = 2026-08-24T19:00Z |
| Scene 3 (beat 3 recall) | same evening, after the beat-3 boundary |

## BEAT 1 — Correction-override (~8–30 s, the lead)

The wrong belief is authored: ref 0 has Halvard settling his account **in full** (eleven
shillings, a round for the room). The designer knows he only paid six.

1. Set as_of to 2026-06-25T19:00Z (SetAsOf before the boundary), **Scene boundary** with
   `prewarmContext` = the beat-1 question (freezes the June basis; the June retells are
   already pinned from rehearsal, so the prewarm reports cache hits).
2. Say (k=9): **"Did Halvard settle his account before he rode north?"** → Branwen answers
   from the wrong belief (rehearsed answer: "Aye, he did — counted out every farthing...
   eleven shillings"). Ledger turn panel: ref 0 served with its score on screen
   (`read_mode` reconstructed — the June basis is already past theta for a June-2 memory;
   the retelling faithfully carries the wrong belief, which is the point).
3. **Correct** (the driver button; `correctionMemoryId` = ref 0's id) with the probe-certified
   override text:
   > Halvard paid only six of the eleven shillings before riding north; the other five stand
   > as debt against his return.
4. Ledger chain view on ref 0 (a scene cut can deep-link `&memory=<id>`): the original
   telling **greyed but present**, the `authorial_correction` head live — superseded, never
   deleted.
5. Say (k=9): **"How much does Halvard still owe the house?"** → the corrected answer
   (rehearsed shape: "Five shillings, and I've marked it plain in my ledger against his
   name"). Retrieval follows the fix (the fact chain moved with the correction), and the
   correction evicted the memory's reconstruction cache (a sanctioned cause), so this ask
   visibly re-forms the telling around the fix — a beat, not a bug. Retake lever: if that
   re-formed retell rolls badly, re-fire the same Correct (a fresh head + a fresh eviction
   re-rolls the retell without touching the drovers take).

Guard: SATISFIED at the 2026-08-22 rehearsal — on the dry-run provision the served
relevance of ref 0 moved up across the fix, and the post-correction money answer carried
the five-shillings debt.

## BEAT 2 — Constancy-first drift (~30–55 s)

The certified target: ref 3, the turned-away drovers — her OWN action, first person, drifted
on 6 of 7 E1 rolls, certified in the beat's own condition (k=3, 60 days, distance 0.082,
inside the 0.05–0.30 useful window). The chimney fire stays the fallback take only.

1. **+60 days** → 2026-08-24T19:00Z. **Scene boundary** — the boundary carries
   `prewarm_context` = the beat utterance (C7-B), so the retellings roll during the scene
   cut, off the turn's latency. (The old off-camera warm-init trick is retired.)
2. Say (k=3): **"Do you remember the two drovers you turned away at the door in June?"**
   → the retelling. Ledger: `read_mode` flips to `reconstructed` (amber), gist precision
   green at the top ("the NPC is never wrong about what matters"), the chain view shows the
   retold telling beside the immutable observation, gist spans marked.
3. The line: not a hallucination — the record underneath is intact; the telling drifted, on
   a budget, on purpose.
4. Say the same question again → **byte-identical text** (the constancy invariant; the cache
   serves the pinned take).

## BEAT 3 — The game authors her actions (~55–72 s)

The action-observe contract (2026-08-04): the NPC's own deeds arrive as ordinary observes,
first person (the E1 render-voice rule — first person renders owned; third person renders
witnessed). Fire-and-forget, so gameplay never blocks on the write path; the drain is the
explicit join at the scene edge (no verb auto-drains, by ruling).

1. On-camera action beats (typed into the driver input, or scripted):
   - **Observe (async):** "I put old Fenn's cart under the lean-to when the rain came, and
     stabled his gray mare with a feed of oats."
   - **Observe (async):** "I chalked the well rope onto the repair slate myself, so Piers
     cannot claim he was never told."
   The overlay's `pending observes: 2` readout is the fire-and-forget proof on screen.
2. **Drain** at the scene edge, then **Scene boundary**.
3. Say (k=3): **"What did you do for Fenn when the rain came?"** → owned, first-person
   recall of an action the game authored moments ago. Ledger index (live poll) already shows
   the two new memories.

(Both observe texts follow `identity-authoring.md` §5: first person, existing cast only —
Fenn, Piers, the well rope are corpus entities — no new proper nouns.)

## CLOSE (~72–75 s)

The instrumentation close, all judge-free numbers already earned:

- perceived-first-word **p50 938 ms / p95 1516 ms** (D1, on this slate)
- **~$0.12 per 100 turns** all-in
- believability: gist_precision **0.823**, fabrication_rate 0.043 (D1 run); held-out demo
  corpus: fabricated entities **0**, keyword retention **0.979** (E1)
- the tagline: self-hostable — your Postgres, your models.

## Rehearsal record (2026-08-22): EXECUTED — the recording state is pinned

The checklist below ran end to end on 2026-08-22 (both blockers cleared: the `.env` batch
roles verified at `claude-opus-4-8` and proven on live calls — a real reflect wrote 3
reflections and the compiler worker auto-ran `completed`, 3 bundles, 0 failed; the Unity
play-mode gate ran GREEN through the live editor, 8 checks). Two provisions: a full dry-run
(all beats + the correction guard, then discarded), then the final provision whose state is
**pinned and live in `longmem_demo` — do not run the loader again before recording**:

- agent `3f7355f1-fd90-4fce-8d8d-c7e652e33af9` (also pasted into the committed scene's
  `agentIdOverride`, with ref 0's id in `correctionMemoryId`)
- ref 0 Halvard `f28784f7-…` (importance 0.620, correction VIRGIN) · ref 3 drovers
  `9b43a8be-…` (importance 0.720, 4 spans)
- the June layer pinned (scene-1 prewarm + both beat-1 asks at k=9, wrong-belief answers
  on the nose); the beat-2 take pinned (a real edit, not an echo: gist_precision **1.00**,
  detail_recall 0.58, 0 fabrications, constancy byte-identical on the re-ask); beat 3
  virgin; no failed worker runs; the Ledger verified camera-ready on this exact state.

What remains for E3 is performance, not validation: drive the same beats through the Unity
driver + OBS.

## Rehearsal checklist (the E2 guard; re-run only if the state is ever re-provisioned)

0. `.env`: batch roles synced to Opus 4.8 (Jack's pending action — binds now), real mode,
   `DATABASE_URI` → `longmem_demo`.
1. **Play-mode gate BEFORE any retarget/paste** (ordering: after the agent id is pasted,
   autoRun would replay scripted observes INTO the pinned demo agent): fake-mode serve on a
   scratch DB, `autoProvision` temporarily ON + `autoRun` ON → `[npc-demo] ALL PLAY-MODE
   BEATS PASSED` in the console → flip both back.
2. `python -m app.demo_loader --fresh` (real providers). The printed roll is the guard's
   input:
   - ref 3 (drovers): importance high enough for k=3 membership on the beat question, gist
     spans low (a saturated roll is un-driftable — E1 lesson 1);
   - ref 0 (Halvard) present with sane importance;
   - no `scoring_failed` / `escalation_failed` / `embedding_failed` flags anywhere.
   Re-run `--fresh` until the roll is good. **After a good take is pinned, never run the
   loader again** — `--fresh` is the only destructive path and it is deliberate.
3. Paste the printed agent id into the Unity inspector (`agentIdOverride`) and the Ledger
   deep link; paste ref 0's memory id into `correctionMemoryId`.
4. Start the real serve; workers settle (the demo agent's reflection/compiler flags are ON —
   let any auto-reflection land BEFORE rolling the beat-2 take: a reflect evicts affected
   reconstruction caches, the fourth sanctioned text-change cause, and would re-roll a
   pinned take).
5. Dry-run the beats in order. Beat-1 guard: ref 0's served score/rank moves across the
   correction. Beat-2 guard: the retelling is a real retell (visibly edited, not an echo)
   and not a refusal (the chain shows a new `reconstruction` head, not the prior text) —
   if it echoed or refused, re-provision (step 2) and re-roll. The take then pins by
   constancy: repeat reads are byte-identical.
6. Record timings per beat for the E3 edit; confirm the Ledger turn feed rendered every
   turn live (poll ON) and the identity pane shows the seed identity.

## E3 first attempt (2026-08-24): recorded + QA'd, master NOT cut — findings for the next version

All four segments were recorded through the attach-mode rig (Jack on the overlay + OBS,
Claude cueing and QA'ing live) and every beat guard PASSED; the cut was abandoned after
footage QA and Jack ruled a demo-presentation redesign session of his own before a fresh
provision + full re-record (the dated E3 entry in `decisions.md`; the same day's
re-sequencing entry then moved the whole demo endgame — redesign → re-record → publish —
to AFTER Phase F). What the next version inherits:

1. **A provision serves beat 1 exactly once.** The correction moves ref 0's fact chain and
   evicts the June caches — the wrong-belief answer is unreproducible afterwards. Plan every
   recording attempt as fresh-provision + re-pin (the `rehearse.py --take-only` shape —
   session-scratch tooling from the E2 rehearsal, never committed to the repo; rebuild or
   improvise it at the re-record); the 2026-08-22 provision is SPENT.
2. **Flaws found on camera, noted NOT fixed by ruling** (may not survive the redesign): the
   Branwen nameplate renders MIRRORED (TextMesh rotY 180, faces away from the camera —
   invisible to every API-level gate; visual QA needs extracted frames), the browser tab/URL
   bar and the Game-view toolbar strip are in frame, and the overlay input's default text
   still names the ford (pre-Branwen). A pre-record visual frame check belongs in the next
   rehearsal checklist.
3. **The constancy camera line is loose.** The invariant binds the STORED/SERVED retelling
   (byte-identical across the re-ask, verified) — the streamed dialogue wrapper varies per
   turn by design. The beat-2 caption must claim exactly that; the two asks will not sound
   identical.
4. The re-ask's retrieval gate fired (`entity_tripwire`) and served 6 rows vs the first
   ask's 3 — designed behavior, visible on the Ledger.
5. The post-ask chain leaves the correction head superseded by the re-formed retell; the
   chain close-up's ruled frame (amber correction LIVE) is restored by re-firing the same
   correction before the shot — the documented lever, exercised and verified.
6. Timing reality: ~215 s of raw across the four segments against the ~75 s target. Streams
   play at natural speed (speeding them up would misrepresent the latency claims), so an
   honest cut lands nearer 100 s; the next choreography pass should budget for it.

## What E2 built for this script (pointers)

The corpus→demo-DB loader (`app\demo_loader.py`, `--fresh`-guarded, prints the provisioned
roll + hand-off ids, merges the two worker flags after replay); the Ledger live turn feed
(`GET /v1/ledger/turns`, an in-memory tee at the two dialogue routes — the E2 ruling) + the
identity/state pane + the em-dash label sweep; C# `SceneBoundaryEvent.PrewarmContext` /
`SceneResult.Prewarm` (+ the 13-field `ScenePrewarmInstrumentation` DTO) and the
`NpcMemoryNpc` ObserveAndForget / DrainObservesAsync / PendingObserves passthroughs; the
driver beat controls; the Unity scene retarget to Branwen. Verification: the 17-beat console
harness (the new prewarm beat mirrors `tests\verify_prewarm.py` A/B/C), the suite's
`test_ledger_feed.py` + `test_demo_loader.py`, and this checklist's rehearsal.
