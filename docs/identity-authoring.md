# Authoring an NPC: identity, memories, and the authoring-time checks

Written 2026-08-19 (Phase E1). This is the integrator-facing guide to authoring a twicetold-npc
agent: the identity fields, the memory prose, the config knobs an author owns, and the two
validation commands that catch a bad authoring decision before it reaches a live game or a
recording. It was proven by authoring the demo NPC (Branwen of the Waystone Inn) with it;
section 8 is that worked example with its real validation numbers. The demo corpus lives at
`data\eval\corpora\demo-waystone.jsonl`, its held-out probes at
`data\eval\scenarios\demo-waystone.jsonl`.

Everything here uses PowerShell syntax and repo-relative backslash paths, run from the repo root.

---

## 1. What an agent is made of

An agent row has five author-owned fields (created via `POST /v1/agents`, or the `agent` block
of an eval scenario):

| Field | What it is | Where it feeds |
|---|---|---|
| `name` | unique handle | bookkeeping only, never prompts |
| `seed_identity` | free prose, no template | the rendered identity document (below) |
| `diagnosticity_goal` | one line: what this character finds significant | the importance prompt, verbatim, and through it both retrieval weight and memory durability; the escalation stage reads the same signal when it extracts gist |
| `rigidity` | 0.5 to 2.0 | the dissonance path's defend-vs-update resistance |
| `config` | JSON knob overrides | every agent-scoped knob (section 4) |

The **rendered identity document** is the seed plus the agent's current identity-relevant
reflections, joined by blank lines; with zero reflections it is the seed verbatim. Its hash is
`identity_version`. There is deliberately no template (a template would be a hidden authorial
artifact). The document is pasted into the dialogue prompt's `[identity]` block and into the
reconstruction prompt, so the seed's exact wording is what the character speaks from and
remembers through.

One consequence worth designing for: the fabrication metric whitelists every entity that appears
in the observation text, the anchor, or the **identity document**. A name in the seed can never
be counted as fabricated. Put the NPC's stable world in the seed: the place, the landmark
regulars, the things the character would name in any conversation.

## 2. Writing `seed_identity`

Two shapes are proven:

- **The one-liner** (all eval fixtures): name, role and place, one or two contrasting traits.
  Example from the fixtures: "Hedda, who keeps the inn by the mill road and hears every debt
  settled or dodged at her long table."
- **The short paragraph** (the demo NPC, section 8): four to six sentences in first person,
  naming the place and two or three stable world entities. Richer on camera, and a richer
  fabrication whitelist.

Rules that held up in practice:

- **Pick one grammatical person and keep it.** The document is pasted verbatim into prompts;
  a seed that drifts between "I" and the character's name reads as two speakers.
- **Write character, not instructions.** It is identity prose, not a system prompt. "I forgive
  an unpaid debt slower still" beats "always remember debts".
- **Write a stable core.** Reflections will append below the seed over the agent's life; the
  seed should still read true a hundred scenes later. No news, no current events.

## 3. Writing `diagnosticity_goal`

One line, phrased as what the character finds significant: "what threatens the house, who owes
it, and what news the road brings". The importance model consumes it verbatim when scoring every
new memory, and importance drives two things at once: retrieval weight (the served score
multiplies relevance, recency, and normalized importance) and durability
(`tau_eff = tau_base x (1 + decay_k_importance x importance_raw)`).

Two hard-won lessons:

- **The goal must cover what your scenes need the NPC to care about.** The demo NPC's first
  goal was "who owes the house and what news the road brings"; a house fire then scored 0.32
  importance and lost retrieval to fresher gossip. Adding "what threatens the house" moved the
  same memory to 0.72. If a beat depends on a memory surfacing, the goal must make that memory
  matter.
- **The goal also shapes gist.** The escalation stage extracts the diagnostic spans of each
  observation as fixed gist, and gist is exactly what a reconstruction may never change. So the
  goal decides not only which memories are durable but which parts of them are frozen. See
  section 5 for why that matters.

## 4. The config knobs an author owns

Set these in `agents.config` (or the scenario `agent.config`). Fixture discipline: state every
value an assertion or a beat depends on explicitly; never lean on service defaults.

- **`decay_classes`** maps class labels to base time constants in seconds, and
  **`decay_class_default`** names the class used when an observe carries none. The demo corpus
  uses `{"episodic": 864000.0, "semantic": 15552000.0}` (10 and 180 days) with default
  `episodic`. Two honest notes: the eval scenario schema's `observe` step carries text only, so
  **every corpus-replayed memory takes the default class**; the live API's observe event does
  accept a per-event `decay_class`, so a game can classify at write time.
- **The decay math in one line:** `strength = exp(-age / tau_eff)` with
  `tau_eff = tau_base x (1 + decay_k_importance x importance_raw)`; a served memory reconstructs
  when `strength < reconstruction_theta` (default 0.5) at the scene-frozen basis. Pinned
  memories never reconstruct.
- **Reconstruction knobs:** `reconstruction_theta` 0.5, `reconstruction_band_quantum` 0.25 (the
  thinning band; deeper bands thin harder), `drift_budget_threshold` 0.35, and
  `reconstruction_gist_constraint`, which stays 1.0 in production. The drift budget is a topic
  guard, not a fact guard: it refuses a retelling whose embedding left the anchor's
  neighborhood. Factual faithfulness is policed by the gist constraint and the gist-precision
  metric, never by that threshold.
- **`rigidity`** (0.5 to 2.0): how hard the character defends a challenged memory in the
  dissonance path.
- **Worker opt-ins**, all OFF by default and enabled per agent:
  `reflection_worker_enabled`, `compiler_worker_enabled`, `deferred_writes_enabled`. Eval
  corpora leave them out (the runner needs deterministic replay); a live deployment enables
  them on the agent it provisions. The demo agent's corpus config and its provisioned live
  config therefore intentionally diverge on exactly these flags and nothing else.
- **Eval-only neutralization convention:** a scenario whose assertion is a tight top-k
  membership cut sets `importance_norm_floor: 1.0` and `decay_k_importance: 0.0` so the cut
  rides pure similarity. Drift corpora deliberately do NOT neutralize; decay is the thing under
  test.

## 5. Memory-prose register

Memories are authored as observation events: what the game says happened. The register rules
are measured, not stylistic preferences.

**Write shipped-game prose, not driver prose.** The write path's escalation stage fired on 79%
of realistic prose versus 0% of synthetic load-driver prose in the 2026-07-21 measurement
(roughly 95% on realistic corpora at current defaults). Synthetic filler silently starves the
write path's construct, and everything downstream of it. Concrete: in-world sensory detail,
named minor characters, quantities, consequences.

**Entity discipline.** Every proper noun in a memory should be established by that observation,
the seed, or an earlier memory. The fabrication metric counts unexplained entities in the
NPC's speech; prose that invents casual names inflates it.

**Author the NPC's own actions in first person.** The render model narrates observations from
the character's point of view, and it defaults to witness voice: an observe reading "Branwen
turned two drovers away" rendered as "I watched Branwen turn away those two drovers", which on
an inspector close-up reads as a bug (she IS Branwen). Passive phrasing did not fix it (still
"I watched as..."). First person did: "I turned away two drovers at the door" renders owned.
Third person is right for what the character witnessed; first person for what the character did.
Game-side action observes (the fire-and-forget observe path) should follow the same rule.

**Texture that must drift has to be goal-orthogonal.** This is the subtle one. A reconstruction
may thin and reshape only what is NOT gist, and gist extraction follows the diagnosticity goal.
The demo's chimney-fire memory was written as maximal drama, and escalation dutifully froze
two thirds of it as gist (11 spans over a 477-character observe); the leftover "detail" was
punctuation fragments, and on that degenerate input the retelling model was unreliable (some
calls returned no usable retelling at all; the serve path soft-degrades such an item to its
live head, honestly but invisibly). Even after a rewrite, house-flavored texture kept getting
promoted to gist because the goal says the house matters. If you need a memory to visibly
drift, give it texture the goal does not care about: weather, light, incidental sensation, in
sentences free of names and numbers. And know that a memory whose every clause matters will
hold nearly still. That is the system working.

## 6. The authoring-time drift check

`drift-validate` replays a corpus, ages the session past its last authored moment, re-freezes
the scene basis, probes once, and reports the per-memory cosine distance between each new
retelling and its anchor. It exists so an undemonstrable memory is caught at authoring time,
not at recording or shipping time.

**Corpus shape:** JSONL, one scenario per line, events restricted to `observe` and `as_of`.
The loader is strict (`extra="forbid"`); any authoring typo fails at load with file and line.

**Dry-run the mechanics first (free, fake mode):**

```powershell
$env:TWICETOLD_PROVIDER_MODE = "fake"
python -m app.eval_runner drift-validate --corpus data\eval\corpora\demo-waystone.jsonl --age-days 60 --plumbing
Remove-Item Env:\TWICETOLD_PROVIDER_MODE
```

The report is labeled `plumbing_only`; ignore its distances.

**Then validate on real embeddings** (the tool refuses real signal in fake mode; exit 2):

```powershell
$env:TWICETOLD_PROVIDER_MODE = "real"
python -m app.eval_runner drift-validate --corpus data\eval\corpora\demo-waystone.jsonl --age-days 60 --out data\eval\runs\demo-drift-60d.json
Remove-Item Env:\TWICETOLD_PROVIDER_MODE
```

Exit 0 means every retelling stayed under the drift budget; exit 1 means at least one was
refused. Read the report beyond the exit code:

- **`items_checked` versus `observes`.** A memory missing from the items list did not get
  drift-checked: it was pinned, still above theta at the aged basis, outside the probe's k, or
  its retelling call returned nothing for it (the soft-degrade path; the memory serves its
  prior head). For a demo or test corpus you want these equal; investigate any gap.
- **The ranked items list** (distance descending) is the pick-your-on-camera-memory tool.
- **Both extremes fail a demo.** Distance near 0 means the retelling is the anchor, so there
  is nothing to show; distance above the threshold means the write-back was refused and the
  audience sees the old text. The useful window in practice is roughly 0.05 to 0.30 against
  the 0.35 default.
- **`--keep-db`** keeps the scratch database for forensics (inspect renders, spans, and
  importance with SQL); drop it afterward via `app.scratch_db.drop_scratch`.

**Validate in the beat's own condition too.** The default probe covers the whole corpus at
k = corpus size, which retells every memory in one batched call. A live scene retells only the
top-k of one utterance. Both membership and retell behavior differ between those conditions,
so certify the target memory with the actual question and k:

```powershell
python -m app.eval_runner drift-validate --corpus data\eval\corpora\demo-waystone.jsonl --age-days 60 --probe "Do you remember the two drovers you turned away at the door in June?" --max-items 3
```

**What is deterministic and what is a dice roll.** Three write-time and read-time judgments are
model calls and vary between provisionings: importance scoring (retrieval membership at small
k), gist-span extraction (how much of a memory is frozen), and the first aged retelling itself,
which on some calls edits richly and on some calls returns the telling verbatim (echo). All
three FREEZE once rolled: importance and spans at write time, and the retelling on its first
aged read, after which the cache serves it byte-identical (the constancy invariant). For a
recording or a test, that means: provision, inspect what actually rolled (the kept scratch or
the live inspector reads), and re-provision or re-roll the scene if the roll was bad. A good
take, once landed, is stable.

## 7. The held-out arm

Full scenarios (utterances, expected-ID cuts, corrections, judged specs) marked
`"held_out": true` are excluded from `run` and `compare` by default; the artifact records them
under `excluded_held_out`. This is the construct-validity guard: material used to grade the
system never participates in tuning it. Author the demo or acceptance scenarios held out, keep
them in their own file, and include them explicitly when you want them measured:

```powershell
python -m app.eval_runner run --scenarios data\eval\scenarios\demo-waystone.jsonl --include-held-out
```

Judge-free by default; the exit code is the expected-ID checks. Scenario authoring notes that
came out of building the demo probes:

- A scenario asserting a tight k-cut should put all its observes at ONE `as_of` timestamp (the
  judged-fixture convention) and use the neutralization config (section 4), or recency will
  quietly decide the cut for you.
- `memory_ref` ordinals are the scenario's observe order, 0-based; the loader rejects forward
  or out-of-range references at load.
- Give every scenario a globally unique `scenario_id`; files are concatenated in some verbs.

## 8. Worked example: the demo NPC

Branwen keeps the Waystone Inn. Seed (first person, five sentences; every stable entity in it
is fabrication-whitelisted):

> I am Branwen, and I keep the Waystone Inn where the north road crosses the drove way below
> Harrowmere. My mother kept it before me, and her mother before that, and the long cellar
> under the taproom has never flooded on my watch. I know every regular by their knock, old
> Fenn the carter loudest of all, and I know what each one owes the house to the farthing.
> Travelers' news is half my trade; ale and a dry bed are the other half. I forget a face
> slower than the road forgets a wheel rut, and I forgive an unpaid debt slower still.

Goal: "what threatens the house, who owes it, and what news the road brings". Rigidity 1.0.
Config: episodic 10 days, semantic 180 days, default episodic, decay live.

Nine memories over three June weeks, each with a job: a crisp correctable debt fact (Halvard's
eleven shillings, the correction beat's target), a first-person action memory that drifts
reliably (the turned-away drovers, the drift beat's target), a deliberate knowledge gap (the
nameless lodger, the abstention probe's target), road news, house texture, and a vivid closing
incident (the chimney fire, which escalation freezes almost whole, exactly as section 5
predicts).

Validation, 2026-08-19, real providers (Haiku write/escalation/reconstruction, OpenAI
embeddings), age 60 days:

- **Coverage run** (k = 9): 9 of 9 memories reconstructed and checked, 0 over budget against
  threshold 0.35, distances p50 0.06 / p95 0.11 / max 0.121, drift-refusal self-check matched.
- **Beat condition** (drovers probe, `--max-items 3`): the target memory was served in the
  top 3 on every roll and landed distance 0.082 on a retell-mode roll (echo rolls occur; see
  section 6, the dice-and-freeze note).
- **Held-out run** (judge-free, real): 2 of 2 expected-ID checks passed, fabricated entities 0,
  fabrication rate 0.000, keyword retention 0.979, gist precision 0.720, detail recall 0.664.

The corpus took five authored revisions to pass all three. The failures, in order: the fire
memory silently failed to retell (gist saturation, section 5); the correction probe's k-cut
was decided by recency, not relevance (single-timestamp convention, section 7); the render
witness-voiced the NPC's own actions (first-person rule, section 5); the fire lost retrieval
membership to fresher gossip (goal coverage, section 3); and house-flavored texture kept
freezing into gist (goal-orthogonal texture, section 5). Every one was visible in a
drift-validate report or a kept scratch database before any of it reached a recording.
