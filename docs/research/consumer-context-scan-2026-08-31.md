# Consumer-context scan — 2026-08-31 → 09-01

**What this is.** A pre-release internet scan answering one question: does anything load-bearing
need changing, repositioning, or a prepared answer before the v1 public push (F1 README → F2
packaging → F3 flip → demo publish)? Five parallel research passes: (1) OSS agent-memory
projects and their reception, (2) commercial AI-NPC platforms and game-dev/player sentiment,
(3) research landscape + novelty stress test + name check, (4) release-hygiene norms (license
chain, no-auth norms, UPM packaging, erasure norms), (5) a cold consumer sub-agent — a
role-played Unity indie engineer evaluating the repo read-only with no project context. This
file is the synthesis; the load-bearing filter dropped style-level findings to the appendix.

**Method caveats.** Evidence links were gathered and dated by the research agents 2026-09-01;
spot-checked, not exhaustively re-verified. Reddit was fetch-blocked, so r/LocalLLaMA and
r/gamedev sentiment is triangulated via HN, GitHub issues, Unity Asset Store reviews, and
press rather than read directly. Single-source claims are flagged where they matter. This scan
complements the 2026-07-22 external-persona audit, which was simulated and demo-sequencing
focused; nothing here re-litigates it.

---

## The verdict, in five lines

1. **The novelty claim survives.** Nothing found — in games or out — does identity-conditioned
   reconstruction with versioned, compounding write-back over an immutable record. But the
   *slogan* "reconstructed, not replayed" was independently claimed twice in mid-2026 papers,
   and the bi-temporal substrate is established prior art (Zep/Graphiti). Cite and
   differentiate; never lead with the bare slogan.
2. **The license chain is clean.** Full dependency verification (including the two
   runtime-downloaded model artifacts) found nothing NC/SA/research-only. The Apache-2.0 flip
   is clear. One NOTICE micro-gap (f-coref weights).
3. **Two product gaps are category table stakes** and went to Jack as forks: an
   OpenAI-compatible/local-model provider path (the loudest demand in self-hosted AI infra,
   with an honest quality-floor counterargument), and a per-agent bulk erase verb (every
   comparator has one; graded on comparison sites).
4. **The stale README is doing real damage now** — the cold consumer nearly walked at the
   ~10x cost discrepancy between README and status ($0.92–0.94 vs $0.084 per 100 turns) and
   the "purge not built yet" line sitting beside `verify_purge` in tests. F1's priority rose.
5. **The demo's planned shape is on the right side of the evidence.** Every ridiculed AI-NPC
   showcase led with open-ended chat; every survivor led with mechanism and consequence. The
   correction-override lead + inspector split-screen is the surviving pattern. The framing
   traps are now enumerated (below) for the presentation-redesign session.

---

## Part 1 — The four forks surfaced to Jack (drafted neutral; rulings recorded in decisions.md)

### Fork 1 — Provider coupling: an OpenAI-compatible base-URL path
Today the six model roles are env vars but the implementations are Anthropic SDK + OpenAI
embeddings only. The market evidence: every surveyed comparator (Mem0, Zep/Graphiti, Letta,
Cognee, LangMem, Supermemory) ships a local/OpenAI-compatible path, and local-model breakage
is still their **dominant issue category** — the demand is that loud. HN dismissals of tools
without the knob ("vendor locked garbage with no Ollama support," Dec 2025), Home Assistant's
community calling the OpenAI-compatible shape the "lingua franca," and the game-side pattern
(Mantella's any-endpoint support; LLMUnity winning its Unity Asset Store reviews *on* offline
capability) all point the same way. The honest counterweight, documented by the same
comparators: small local models fail structured-output pipelines loudly (Graphiti's own docs
warn of it; Letta's tracker calls non-GPT use "pure torture"), and longmem-npc's write-path
typology/importance JSON and reconstruction drift enforcement are exactly the calls that
break first. Options: build a base-URL provider path pre-release (~1–2 sessions: new provider
implementation + config + tests + floor re-verify); or ship v1 with a "why these providers"
README section stating the measured-quality-floor rationale plus a roadmap line, and build the
knob as a scoped post-v1 task; or decline entirely (silence — reads as ignorance of the norm
per the evidence).

### Fork 2 — Per-agent bulk erase verb
Category norm verified in the comparators' own API docs: Mem0 `DELETE /v1/memories/` by
filter (marketed as GDPR erasure), Zep `DELETE /api/v2/users/{userId}` ("Right To Be
Forgotten... a single API call"), Letta agent delete; OpenMemory MCP's entire API is four
verbs and one is delete-all. Comparison sites grade the erasure path. longmem-npc has
per-memory `DELETE /v1/memories/{id}` only; full erasure composes via the enumeration read +
a loop, undocumented. Nuance in the project's favor: GDPR erasure targets a *player*, and
memories attach to NPC *agents* — a player's text can span many agents, so even a per-agent
verb is not a compliance button; the integrator owns the player-to-memory mapping under
either design. Options: build `DELETE /v1/agents/{id}/memories` as a thin transactional
extension of the existing C6 purge carve-out (small: endpoint + tests + walker extension +
purge-floor re-verify, under a session); or document the loop-over-purge pattern as the v1
answer.

### Fork 3 — The name
"longmem-npc" exact-match is clean everywhere (web, GitHub — zero collisions). The prefix is
crowded: Microsoft LongMem (NeurIPS 2023) owns the term academically; **longmem.dev is a live
product literally named "LongMem"** in the same category (privacy-first, self-hosted agent
memory) — the closest trademark-shaped item found, though no registered mark surfaced; PyPI
`longmem` is taken (Apr 2026, an unrelated tool); LongMemEval, CaviraOSS/LongMemory, and
LangChain's `langmem` crowd the rest. Search results for "longmem" are dominated by
Microsoft's paper and the benchmark. Risks: discoverability, implied kinship, and a possible
post-publicity objection from longmem.dev. Options: keep the name + one README disambiguation
line ("not affiliated with Microsoft's LongMem, LongMemEval, or longmem.dev") + never ship a
bare `longmem` package id (the UPM id and any future PyPI name carry the `-npc`); or rename
before the F3 flip — cheap now (repo rename, GitHub redirects, docs sweep; no package ids
shipped yet), roughly impossible after the video and package publish.

### Fork 4 — The Ledger's localhost exposure (DNS-rebinding class)
The API serves a browser page (The Ledger) on localhost with no Host/Origin validation
(grep-verified: no TrustedHost/CORS middleware anywhere in `app\`). Precedent: MCP Inspector
(CVE-2025-49596, CVSS 9.4, June 2025) — a localhost-only dev tool attacked from public web
pages via DNS-rebinding/CSRF; the fix was Host/Origin validation. Options: add FastAPI's
`TrustedHostMiddleware` with a localhost allowlist (a small standard mitigation + tests) in
the F3 sweep, plus a caveat line in the honesty section; or document the caveat only.

---

## Part 2 — Change-before-release items needing no ruling (routed into scheduled phases)

| Item | What | Where it lands |
|---|---|---|
| NOTICE gap | Add lines for the biu-nlp/f-coref weights (MIT, runtime-downloaded from HuggingFace — currently undocumented) and a one-line provenance note on the spaCy models (MIT; OntoNotes commercially licensed by Explosion, WordNet license, CC0 vectors) | F1 or F3, minutes |
| Compose Postgres exposure | `docker-compose.yml` publishes `"5432:5432"` on all host interfaces today; loopback-scope it (`127.0.0.1:5432:5432`) and keep the DB compose-internal in the F2 file | F2 (or an earlier one-liner) |
| One set of numbers | README $0.92–0.94/100 turns (2026-08-12 shape) vs status $0.084 (F0) — ~10x apart in public view; the demo close card's ~$0.12 is also stale. F1 ships one dated, defined, all-in cost table | F1 + presentation redesign |
| F2 compose shape | `build:` the API image from the repo (also avoids the LGPL-redistribution branch entirely — publishing a prebuilt image containing psycopg would create new obligations), pinned tags, healthcheck + `service_healthy`, migrations as an explicit one-shot service, loopback ports, no secrets | F2 spec |
| UPM conformance | Reverse-DNS id (with `-npc`, per Fork 3), exact-version dependency on `com.unity.nuget.newtonsoft-json` (never bundle the DLL — collision is the category's most common failure; note that package is Unity Companion License, one more reason to depend not bundle), `Samples~`, asmdefs, `Third Party Notices.md`, OpenUPM tag discipline, a shipped `link.xml` sample for IL2CPP | F2 spec |
| Platform matrix | Document: Editor/desktop/mobile yes (IL2CPP note + link.xml); **WebGL no** — Unity's own constraint (no System.Net on Web); netstandard2.1 is the right target, verified current | F1/F2 docs |

## Part 3 — F1 README input pack (content, framing, citations)

**Structural norms extracted from the top memory-infra READMEs** (Mem0/Graphiti/Letta, fetched
2026-09-01): measured numbers immediately after the fold; quickstart under ~15 lines with a
deployment-path table; an explicit providers section *including a local-LLM stance* (even
"not supported, here's why" beats silence); a comparison table against the obvious
alternative (here: destructive summarize-and-stuff compression — already planned); a
credibility block (license clarity, citations, no-telemetry statement).

**Content the scan says F1 must add** (beyond the planned rebuild):
- **The deployment-reality page** — the cold consumer's #1 blocker: an honest "to ship a game
  with this" section/page. Who hosts (the studio, behind auth it must add), who pays for keys,
  why player-local distribution is a non-starter (key distribution), the per-player cost math,
  and the Steam live-AI disclosure obligations a shipping game inherits (Valve's Jan 2026
  rules: live-generation checkbox, guardrail description, in-overlay reporting; disclosure
  correlates with a measured review/sales penalty; The Alters showed non-disclosure is worse).
  State plainly: no moderation layer is included; content safety is provider-side plus
  integrator-owned.
- **The integrator quickstart** ("your first NPC in ~30 lines") — the consumer's #3: exact
  `POST /v1/agents` request, a minimal MonoBehaviour showing the observe → turn →
  scene-boundary/drain order, "persist the agent UUID yourself" guidance, and the
  real-calendar-time-between-sessions / `AsOf` guidance. Everything is currently inferable
  from four files; inferable is not a pitch.
- **Position lines**: claim the empty slot (no self-hosted, engine-integrated NPC-memory
  comparable exists at any scale — verified by search); "no hosted version exists; this is
  the whole product" (the category's open-core retreats — Zep CE killed Apr 2025, Letta V1
  server archived, Mem0 cloud-first — make this a differentiator); platform-sunset risk as
  the argument for self-hosting (Inworld repositioned away from game NPCs, Replica shut down
  June 2025) stated without dunking on named vendors.
- **Framing constraints**: lead with correction-override ("retrieval follows the fix"), not
  "NPCs remember" — memory-as-marketing is commodity in 2026 (KRAFTON PUBG Ally, NVIDIA ACE);
  the wedge is what commodity memory lacks (ground truth vs telling, controlled drift,
  defend-vs-update, the inspector). Latency claims always carry "streamed text,
  time-to-first-word, no STT/TTS" — the voice-agent discourse rates 800 ms–1.2 s "poor," and
  an unqualified sub-second claim invites the wrong rubric; the honest favorable comparison
  is Convai's real-world 4–6 s text-to-speech loop. Cost claims carry a date, a definition of
  "turn," and a per-player-hour translation; the number decays within a model generation.
  The AI-pair paragraph stays and goes *human-judgment-first*: 2026 hiring/OSS discourse
  rewards disclosed AI use with a foregrounded verification loop and punishes undisclosed or
  unexplainable output (curl's bug-bounty shutdown under slop; GitLab's disclose-and-discuss
  policy); the register apparatus is exactly the rewarded artifact if the README frames it as
  the verification story within the first screen.
- **Prior-art citations to add**: MRAgent (ICML 2026, arXiv 2606.06036) and MemHarness (arXiv
  2607.28272) — both claimed "reconstructed, not replayed" framings in mid-2026 with different
  mechanisms (graph-path reconstruction; transient task-conditioned rewriting) — cite and
  differentiate on the four things neither has: identity conditioning, persisted compounding
  write-back, immutable bi-temporal ground truth, gist-pin + drift budget. Credit Zep/Graphiti
  (+ Engram, already cited) for the bi-temporal storage discipline — it is the floor, not the
  novelty. Optional strengtheners: modern serial-reproduction replications beside Bartlett
  (PNAS 2023; SciRep Dec 2023 — raw LLMs under-drift on retelling, which argues *for*
  induced, conditioned drift); "In Praise of Stubbornness" (2502.04390) and BeliefShift
  (2603.23848) near the dissonance section; Memory Contagion (2606.23195) as the
  uncontrolled-vs-controlled write-back contrast. Fix the Engram citation nuance (the paper's
  title is "Less Context, More Accuracy..."; Engram is the system name — cite with the full
  title once).

**Prepared answers to keep ready** (README FAQ or interview):
1. *Why no LoCoMo/LongMemEval numbers?* Three prongs: the signature behavior — deliberate,
   bounded paraphrase past a decay threshold — is scored as failure by verbatim-recall
   benchmarks (they measure what the system intentionally does not do); the judge-free
   harness + published agreement stats respond directly to the documented LoCoMo judge
   failure (Penfield audit: 6.4% of the answer key wrong, judge accepting up to 63% of
   intentionally wrong answers) and LongMemEval saturation (94–95% leaders; V2 pivoted to
   web-agent trajectories); the retrieval substrate underneath could run recall-style probes
   as future work. Plus one sentence on MemGround (2026's game-flavored memory benchmark)
   grading only accurate recall.
2. *Why Anthropic + OpenAI only?* (If Fork 1 rules defer.) A measured quality floor: the
   write call's structured typology/importance output and the drift-budgeted reconstruction
   are the call classes the comparators' own docs warn break on small local models; roles are
   env vars by design and an OpenAI-compatible provider is a scoped follow-up, not a
   philosophy.
3. *How do I erase a player?* Player-to-memory mapping is the integrator's (memories attach
   to NPC agents, not players); the mechanism is [per Fork 2's ruling: the bulk verb / the
   documented enumerate-and-purge loop].
4. *Why no WebGL?* Unity's platform constraint (no System.Net on Web), not a project defect.
5. The interview move for the process apparatus: walk one floors.md row end to end unaided.

## Part 4 — Demo presentation-redesign input pack (evidence for its own session)

The showcase post-mortem pattern is unanimous. Died: Ubisoft NEO NPC GDC 2024 ("stilted,"
"fans hate it"), Sony's leaked AI Aloy ("creepy... rancid"), PUBG Ally's chattiness ("an
encyclopedia with legs"), Fortnite's AI Vader jailbroken into slurs within ~40 minutes.
Survived: Whispers from the Star (AI as diegetic premise, 82% positive), Suck Up! (AI as a
short-form win/lose mechanic), Ubisoft Teammates (voice as command channel with game-state
consequences). The critique underneath: "infinite freedom is indistinguishable from lazy
design." Consequences for the redesign: the planned beats already sit on the surviving side
(mechanism + consequence + on-screen ground truth); the traps are register-level — no
"paradigm shift" promise language, no open-ended-chat invitation, short NPC lines, the
latency stopwatch defined on screen (text modality explicit), the close card's cost number
refreshed and dated. The "broken robots" critique (players mourn NPCs with no arc; the
Nemesis system locked behind patent until 2036 and still mourned) is free ammunition for the
constancy-and-drift beat: state it in the market's own vocabulary — characters that change
from what happens to them.

## Part 5 — The no-auth/security paragraph, evidence-backed (F1/F3 shape)

The credited pattern (from the Ollama exposure record — 1,000+ internet-facing instances
found by Wiz; 1,139 by Cisco/Shodan 2025 — the ComfyUI Pickai backdoor on ~700 exposed
servers, and ShadowRay's disclaimer-without-secure-defaults collapse) is secure-default PLUS
explicit trust-model statement PLUS a recipe: loopback bind by default (already true — keep
it stated); a paragraph saying anyone who reaches the port can read, write, and purge every
agent's memories, so treat it like a database socket; compose ports loopback-scoped; an
"if you must expose it" recipe (reverse proxy + auth + TLS), not a build-your-own-auth
promise; and the Fork-4 rebinding caveat/mitigation. ComfyUI's SECURITY.md is the positive
model to imitate.

## Part 6 — Novelty verdict detail + negative results (preserved as evidence)

Core verdict: after ~20 targeted searches, **no prior system combines identity-conditioned
retelling + persisted compounding write-back + an immutable bi-temporal record + gist/drift
constraints** — in games or out. Closest, each missing most of the stack: MemHarness
(transient, task-conditioned, unpersisted); "Human-Inspired Memory Architecture" (2605.08538
— reconsolidation-on-retrieval as an accuracy device, no identity, no immutability);
Mem0/Zep-style ADD/UPDATE consolidation (mutation-for-accuracy — the opposite philosophy);
Talk of the Town (real fallibility features, symbolic-era facet mutation, pre-LLM, already
cited — the lineage is unclaimed in LLM form; Kreminski's current line is drama management,
not memory distortion). The field literature frames read-time rewriting as a *hazard*
(security survey 2604.16548; Memory Contagion 2606.23195 studies write-back compounding as a
failure mode) — the controlled-vs-uncontrolled contrast is a positioning gift.

Negative results worth keeping (each searched, found empty of true precedent): Bartlett
operationalized in an agent system; confabulation-as-feature anywhere (treated exclusively as
failure); identity/persona-conditioned memory *transformation* (all persona-memory work
targets accurate persona-consistent recall); false-memory NPC design (MIT's line is about
human subjects); fuzzy-trace gist/verbatim used as a fidelity constraint on generative
retelling (used only for compression); unreliable-memory mechanics in the LLM modding scene
(all summarize-and-recall); a believability/distortion benchmark (none exists — MemGround,
MineNPC-Task, CloneMem all grade accurate recall); "longmem-npc" exact-name collisions
(zero); npm `longmem` (unclaimed); a shipped "reconstructive memory" repo with traction
(none). Also confirmed: all three 2026-era arXiv citations in the README resolve correctly
(2606.09900, 2606.22844, 2511.10277).

## Part 7 — The cold-consumer verdict (stream 5, summarized)

Verdict: **adopt for a one-day spike, prototype-only, with a pre-written exit** — the exit
being the absence of any shipped-game deployment story. What sold: the first sentence
matching the problem, the "What this is not" honesty, fake-mode keyless exploration, the
readable four-file C# client ("the layer I'd have to trust blind in most SDKs, and here I can
audit all of it in one sitting"), SETUP.md's expected-outputs-and-traps discipline, the
measured identity-authoring guide, and the debuggability story ("better than most commercial
SDKs"). Where it nearly walked: the README-vs-repo staleness and the ~10x cost discrepancy
("makes me distrust every number until I re-measure"). The walkthrough's status: 8 steps
CLEAR, several GUESSED (the exact `POST /v1/agents` body; drain-vs-boundary ordering at scene
edges; persist-the-UUID responsibility; real-calendar-time decay guidance; queueing behavior
at 5x oversubscription of the 8-slot gate), one BLOCKED (step 10: shipping to players'
machines — "not hard: undocumented and unaddressed"). Its top five missing things: (1) the
deployment/hosting page [→ F1], (2) the containerized backend [→ F2, confirms], (3) the
30-line integrator quickstart [→ F1], (4) a README matching the repo with one set of numbers
[→ F1, priority raised], (5) a concurrency characterization at 8/16/40 concurrent streams
[queued as an optional post-release measurement]. Honorable mention: internal codenames in
public code comments ("A1 re-shape," "C5, ruled 2026-08-17") read as lab-notebook static to
strangers — appendix-class; a short glossary in docs\README.md would neutralize it cheaply.

## Appendix — dropped one-liners and confirmations

Confirmations of already-scheduled work (priority signal only): README rebuild (F1) — the
consumer evidence upgrades it from scheduled to urgent; compose one-command backend (F2) —
it is also the category's absolution for install weight (the heavy spaCy/transformers
install is a scored liability bare-metal; lead with compose, demote bare-metal); the honesty
paragraph (F1) — now has an evidence-backed shape; CI absence — unremarked by any stream
beyond hygiene norms; walker scratch-DB refactor — untouched by external evidence.

Dropped (small/subjective, one line each): memory products now ship MCP servers as a standard
distribution surface (plausible interview question, not core); Graphiti's telemetry
disclosure pattern (copy only if telemetry is ever added); English-only NLP drew no complaint
anywhere on comparator trackers (not a launch blocker; already documented honestly);
Windows-first docs drew neither praise nor complaint (compose neutralizes); Python 3.14 floor
— documented friction pattern for pip installs, neutralized by the compose path; one honest
README sentence suffices ("developed and tested on 3.14 only; the compose path needs no host
Python"); LangMem's fate shows distribution beats polish (obscurity, not criticism, is the
default outcome — the video and package ARE the distribution plan); Bitpart/Artificial
Agency are pre-revenue-quiet competitor curiosities; "Deflanderization" and symbolic-scaffold
papers are citable related work if a related-work section ever grows; the load-driver could
one day emit the 8/16/40 oversubscription table (consumer #5) as a cheap credibility artifact.

---

## Postscript — rulings (2026-09-01)

Jack ruled all four forks at one batch (recorded in the dated decisions.md entry):
**Fork 1 — BUILD** the OpenAI-compatible provider path before release, shipped with the
documented small-model quality warning; **Fork 2 — BUILD** the per-agent purge verb;
**Fork 3 — RENAME** before the F3 flip (a short naming session precedes F1);
**Fork 4 — BUILD** the TrustedHost guard in F3. The queue consequence lives in status.md
(naming session → provider-path + per-agent-purge build → F1). Part 3's prepared answer #2
("why Anthropic + OpenAI only") is superseded by the Fork 1 ruling — the shipped answer
becomes the quality warning beside the knob.
