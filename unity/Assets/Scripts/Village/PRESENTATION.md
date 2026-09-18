# Village presentation

The standalone VillageScene loads saved scenery from
`Assets/Art/VillageProduction/Prefabs/VillageScenery.prefab`. The scene is visible and
editable before pressing Play. VillageSceneBootstrap now adds only the player, five
characters, event, presentation settings and runtime scenery batches to that authored
world. Its procedural construction remains an explicit migration/reference path, not
the shipped scene's source of truth. No SampleScene content or backend transport is used.
VillageCharacterArt and VillageEnvironmentArt are partial implementation files, not
extra scene components.

## Authored replacement

All six homes use the approved Quaternius modular cottage kit, with restrained roof and
plaster variations. Frontages still face the road. Joan's home has a dedicated 0.65-metre
porch deck, steps and striped awning; her original landmark and dialogue position stay
intact. The market has a produce stall and a blue provision stall, plus imported crates.
Both benches use the approved timber design, scaled to preserve the original seating and
gold-bag staging. The delivery cart uses the imported wagon model. Bridge, dock, fences,
lamp posts and barrel bodies share the textured timber material. Terrain, water, vegetation,
valley silhouette and the five clothed characters retain their established art.

Use **Tools > Village > Open Playable Village**. Edit the scenery prefab or its nested
house/market/furniture prefabs in Edit Mode. Preserve the bootstrap's four authored
references: scenery, market, riverside home and event bench. The migration refuses to
overwrite authored output. `VillageAssetAudition` remains a separate art/animation test.

## Rendering and environment

- 950-metre camera range; layered ridges at 195, 355, and 600 metres, with linear haze
  from 145 to 680 metres. Distant fields, a tree line, and a continuing road/river extend
  the composition without adding a second playable village.
- Runtime-only URP pipeline clone with a 110-metre shadow range, full render scale,
  high-quality SMAA, neutral tonemapping, and a restrained colour grade. The original
  pipeline asset is restored when the scene is destroyed; no shared pipeline asset is edited.
- Timber joinery, shutters, roof courses, side casements, shaped foliage, reed beds,
  orchard produce trays, and correctly outward-facing cylinder/cone surfaces.
- Readable, single-material static meshes are merged by material and 16-metre spatial
  cell at startup, using the current saved transforms. Imported multi-material or
  non-readable FBXs bypass that combiner, preserving every submesh and material slot.
  The editable source renderers are disabled only during Play Mode; colliders and
  landmarks stay intact. Characters and large horizon meshes are not merged.
- VillageRiver.shader is loaded from Resources so player builds include it. Ripples,
  glints, and bank highlights run on the GPU, without per-frame CPU mesh deformation.

## Choreography and interaction

Five stable IDs and the two focus-NPC callbacks are documented in NPC_INTEGRATION.md.
Characters use shared sculpted geometry, tailored garments, and distance-driven gait cycles.
Sitting bends knees, lowers the hips to the bench, and smoothly backs into/out of the seat.
The fishing rod maintains a deliberate grip orientation during tackle inspection.

The two ambient routes are authored in open space. Capsule sweeps stop an actor before a
new obstruction; this is deliberately not a general-purpose pathfinding system. If furniture
is moved into a route, adjust its waypoints rather than expecting the walker to reroute.
Dialogue targeting checks line of sight so characters cannot be addressed through a wall.

## Regression check

Assets/Editor/VillagePresentationValidation.cs is an isolated-project batch verifier. Never
run a second editor against an already open project. Copy the Unity source and settings to
a disposable project, then launch Unity with graphics enabled and these arguments:

    -batchmode -force-d3d11 -projectPath "<isolated project>" -executeMethod VillagePresentationValidation.Run -logFile "<log path>"

Do not pass -quit: the verifier exits itself after actual play-mode updates. It checks the
five IDs, both dialogue callbacks and targeting, event states/timing, one observation per
witness per replay, knee articulation, and two ambient routes over 42 simulated seconds.
It writes ValidationArtifacts/validation.txt and full-resolution PNGs of the village,
horizon, characters, walking poses, seating, and the abandoned gold.

The measured event length is about 13.1 seconds. Static-batch counts are reported by each
run. These are renderer reductions, not a claim about a measured frame-rate improvement.
