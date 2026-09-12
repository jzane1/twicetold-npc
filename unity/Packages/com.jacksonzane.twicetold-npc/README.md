# Twicetold NPC

The Unity client for twicetold-npc: NPCs with a long memory, served by a
self-hosted backend. This package carries the engine-agnostic core
(`NpcMemoryClient`, `NpcSession`, the wire models) and a thin MonoBehaviour
adapter (`NpcMemoryNpc`).

## Install

- Package Manager, Install package from git URL (once the repository is public;
  the `?path=` segment uses forward slashes):

  ```
  https://github.com/jzane1/twicetold-npc.git?path=unity/Packages/com.jacksonzane.twicetold-npc
  ```

- Or copy this folder into your project's `Packages` directory (an embedded
  package). Inside this repository it is already embedded.

Newtonsoft.Json arrives automatically as the `com.unity.nuget.newtonsoft-json`
dependency. Never add your own Newtonsoft DLL beside it.

## The four calls, in order

1. Create the agent and keep the UUID: it is the character.
2. `ObserveAndForget` from gameplay; dialogue never blocks on a write.
3. `SayStreamAsync` to talk; the result carries the memory IDs and scores.
4. `DrainObservesAsync`, then `SceneBoundaryAsync`, at the scene edge.

`docs/first-npc.md` in the repository is the full walk. The First NPC sample in
the Package Manager window mirrors it and ships the `link.xml` that IL2CPP
builds need.

## Requirements

- Declared minimum: Unity 2021.3 (the .NET Standard 2.1 profile). Developed and
  tested on Unity 6000.3 only.
- Desktop and mobile yes; WebGL no (no `System.Net` on the Web player).
- Every async call resumes on the Unity main thread. The client never blocks
  with `.Result` or `.Wait()`, and neither should you.

License: Apache-2.0 (the repository LICENSE).
