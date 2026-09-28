# Twicetold demo narration

Read naturally, at about 125–135 words per minute. The timestamps guide the edit;
you do not need to hit them precisely. Leave a short pause between paragraphs.
Record in a quiet room, with a few seconds of silence before and after. WAV,
M4A, or MP3 is fine. No music is needed in the recording.

## 0:00–0:15 — The event

I built Twicetold, a persistent memory service for narrative agents.

Here, a fisherman leaves a pouch of gold behind. Henry and Joan witness the same event.

## 0:15–0:27 — The witnesses

Henry is a merchant who learned to distrust easy money.

Joan tries to see the best in people.

## 0:27–0:39 — The memory

The original observation is stored unchanged. A few essential spans become fixed gist.
The rest is detail that can fade.

## 0:39–0:55 — Reconstruction

Sixty days later, recall reconstructs the memory using the character's identity,
surviving details, and the previous telling.

Each accepted reconstruction becomes the starting point for the next.

## 0:55–1:12 — Divergence

At six months, Henry suspects somebody has a reason for leaving that gold.

Joan is left wondering what happened to the fisherman. The event survives;
its remembered meaning diverges.

## 1:12–1:29 — Inspectability and caching

These are stored memories, not just different dialogue. Every earlier version remains
inspectable beside the original.

Repeating recall reuses the same memory text. Here, all three reads hit the cache,
and no new telling is written.

## 1:29–1:46 — Live retrieval

Change the subject to Rowan, and the retrieval gate loads relevant history into
the ongoing conversation.

This is the real streamed response through the Unity C-sharp client.

## 1:46–1:56 — Close

Twicetold runs on FastAPI and Postgres, with versioned memory, retrieval instrumentation,
and a Unity package. Code and reproduction steps are on GitHub.
