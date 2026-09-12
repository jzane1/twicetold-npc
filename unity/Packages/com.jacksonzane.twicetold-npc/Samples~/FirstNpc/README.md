# First NPC sample

The thirty-line integration from docs/first-npc.md in the repository, plus the
smallest possible DialogueBox so it compiles out of the box.

- `TavernScene.cs` is verbatim from docs/first-npc.md. That page is the
  contract; keep the two in step.
- `DialogueBox.cs` is a minimal IMGUI sink for streamed prose. Replace it with
  your own dialogue UI.
- `link.xml` preserves `NpcMemory.Core` and `Newtonsoft.Json` from IL2CPP
  managed code stripping. Importing this sample copies it under `Assets/Samples`,
  where Unity honors it. Keep it in any IL2CPP build, even if you delete the
  sample scripts.

Setup: put `NpcMemoryNpc` and `DialogueBox` on GameObjects, wire both into
`TavernScene`, and set `baseUrl` on `NpcMemoryNpc` to your running twicetold-npc
service.
