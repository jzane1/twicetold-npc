# Demo publication copy

## Title

Twicetold — NPCs reconstruct the same event into different memories

## Description

I built Twicetold, a persistent memory service for narrative agents, with a FastAPI backend,
PostgreSQL/pgvector storage, and a Unity C# client.

Henry and Joan witness one event. Later recalls reconstruct it through their identities,
with fixed gist, fading detail, and the previous telling as input. Each accepted telling
is saved; the original observation and earlier versions remain inspectable.

The demo also shows repeat-read cache reuse and a retrieval gate adding relevant history
to an ongoing conversation.

Code and setup: https://github.com/jzane1/twicetold-npc
Demo reproduction: https://github.com/jzane1/twicetold-npc/tree/main/data/demo

All memory and dialogue text shown is real model output. The memory timeline is one complete
selected run. The opening animation reenacts the canonical event for camera framing. The
dialogue overlay replays a recorded C# client stream at its original timing. Time jumps are
explicitly simulated; the recording did not run for six months.

## Chapters (review-cut timing; adjust after narration)

0:00 One shared event
0:15 Two witnesses
0:27 Gist and fading detail
0:39 Reconstruction over time
0:55 Different remembered meanings
1:12 Every version preserved
1:20 Reusing the cached memory
1:29 Live retrieval and streaming
1:46 Architecture and code

## Release handoff

- Add the recorded narration and align captions to the actual voice track.
- Export and review the final video before uploading it as unlisted on YouTube.
- Replace the README's village-demo text link with the video thumbnail link, keeping the
  reproduction guide nearby. Use the real published URL only after upload succeeds.
- Publish the code branch and verify the linked reproduction guide is available.
