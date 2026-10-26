# Village demo

[All guides](../../docs/README.md) | [First-run demo](../../docs/first-run.md) | [Python integration](../../docs/python-integration.md)

This is the optional Unity recording workflow with real providers. To evaluate the backend first,
use [the keyless Compose walkthrough](../../docs/first-run.md); it needs no Unity or host Python.

The recording uses real model output, two authored identities, and one shared event.
The canonical event is `village-event.json`; both village corpora end with that exact text.

## Reproduce

With the normal Python dependencies, configured real providers, and PostgreSQL running:

```powershell
python -m app.village_demo rehearse --takes 3
python -m app.village_demo provision
python -m app.village_demo serve
```

Every provision creates a new `twicetold_video_*` database. Existing takes are retained.
Five backstories are loaded for each witness. The final shared event is left for the Unity
callback. Reflection, parameter compilation, and deferred writes are off for these agents.

Open `unity\Assets\Scenes\VillageScene.unity` and enter Play mode. When
`data\demo\session.json` exists, `VillageDemoBackend` attaches to Henry and Joan by stable ID.
Their callbacks ingest the canonical event. The manifest records an in-flight marker before
each request and a memory ID after success. Replaying the animation never repeats a completed
observation. A leftover in-flight marker stops the take, since the server may already have
committed it. Provision a new take instead of clearing that marker and retrying.

The adapter offers streaming dialogue and forward scene ages (0, 60, 90, 180 days).
The Ledger's `?view=demo&henry=<agent>&hm=<memory>&joan=<agent>&jm=<memory>` view
reads stored histories; its age buttons do not mutate memory or run retrieval.

## Evidence and selection

`runs\<take>\rehearsal.json` preserves initial writes, all age steps, retrieval counters,
repeat reads, and complete version chains. A manual review requires the core event to survive,
the observer to remain distinct from the actor, meaningful loss of incidental detail, and
different stored interpretations consistent with the two identities. Review full pairs and
retain failures. Never splice different runs into a single memory's timeline.

The video uses the first complete pair that passes review. Scene animation may be replayed
for camera framing after the event has been recorded; this is a visual reenactment of the same
canonical input. The Ledger and live dialogue use the selected pair's actual database. Text
is never rewritten for the edit. A displayed memory is distinguished from generated dialogue.

Local manifests, review reports, raw captures, and database identifiers are ignored by Git.
The editor-only `VillageDemoCapture` writes a camera render to H.264 at 1920×1080, 30 fps.
Its capture does not include desktop windows or the adapter's immediate-mode GUI.

## Recording result (2026-09-28)

The first three rehearsals exposed excessive retention in the previous telling. After
adjusting the reconstruction prompt to apply retention to that text as well, two of three
new independent pairs passed manual review. The first passing complete pair was selected.
The third failed because an initial telling moved the pouch from the ground to the bench.
This is a selected demonstration, not a measured success-rate claim or a guarantee that
every model run preserves every fact.

The selected six-month accounts show Henry questioning who really owns the gold and why
it was left where he could see it; Joan wonders whether the fisherman intended to leave it
or forgot, and finds something sad in it. These interpretations are stored reconstructions.
The later spoken response about Rowan is dialogue and does not itself persist a memory.

Two repeated C# recalls returned byte-identical memory text with three cache hits, zero
write-backs, and zero reconstruction output tokens. Changing the topic to Rowan fired the
novelty gate and added three memories to the loaded set (three to six). The film replays
the recorded C# stream at its original chunk timings in an editorial overlay.

Backend verification: 232 tests passed, the affected write/reconstruction/deferred/provider
walkers passed, and the C# harness passed all 53 checks. Model prose was reviewed separately.

Those are the September recording results. See [current verification](../../docs/verification.md)
and [the evidence bundle](../../docs/evidence.md) for the later integration and deployment checks.

## Build the review cut

Install Pillow for the editing script and make ffmpeg available. The script uses Windows
Segoe UI fonts. With the selected run's portraits, Ledger captures, and stream trace saved,
replace the three path placeholders below:

```powershell
python data\demo\build_video.py --take "data\demo\runs\<selected-take>" --event-video "<event-capture.mp4>" --ffmpeg "<ffmpeg.exe>"
```

It writes a 116-second 1080p review cut, SRT/ASS captions, and a provenance manifest under
`data\demo\output`. The review cut has silent audio until the [narration](narration.md) is
recorded. Raw takes and output media stay local; they are not needed to run the service.
