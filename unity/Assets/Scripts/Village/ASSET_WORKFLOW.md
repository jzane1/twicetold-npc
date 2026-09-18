# Village asset workflow

## Playable village: the audition style is now promoted

Open **Tools > Village > Open Playable Village**. The production scene now uses
`Assets/Art/VillageRefinement/VillageScenery.prefab`, with nested prefabs for
six houses, the market, two benches and the wagon. This is saved Edit Mode scenery,
not geometry recreated on every Play. Production material variations live alongside
it; the original audition remains available for comparison.

Move/place objects in Edit Mode, and apply intentional prefab overrides. Do not edit
the runtime `Scenery Batch` objects: those are rebuilt from the saved source geometry
at the next Play. Imported FBXs retain their own material slots and axis-correction
wrappers. Preserve all `.meta` files when moving assets.

The bootstrap's authored scenery/market/home/bench references and five visual prefabs are required. These
landmarks preserve Henry, Joan, the bench event and the gold-bag coordinates. If you
move the event area, retest dialogue sightlines and routes. Ambient routes and terrain
height sampling still live in code; arbitrary terrain sculpting requires updating
those, not only moving the terrain mesh. Scenery editing does not grant backend writes.

The promotion tool is a one-time migration and refuses existing output. The saved
prefabs and scene, not that migration recipe, are now the production source of truth.

## Open and review

Use **Tools > Village > Assets > Open Asset Audition**, or open
`Assets/Scenes/VillageAssetAudition.unity`. This is a separate, saved, walkable review
scene. It is intentionally NOT added to player build settings. `VillageScene` remains
the working demonstration with its original five actors, dialogue hooks, and gold event.

In Play Mode: WASD/mouse to explore, Shift to move faster, Escape to release the
cursor. Press 1 for idle, 2 for walking in place, 3 for sitting, H to hide the help.
The character is a technical retargeting sample, not a new NPC and not final Henry art.

## Edit normally, without rewriting a scene generator

The cottage, orchard stall, bench, and rig are prefab instances under
`Assets/Art/VillageAudition/Prefabs`. They exist in Edit Mode. Move them with Unity's
normal transform tools; open a prefab to edit shared construction, or make a prefab
variant for a distinct house/stall. Apply only intentional instance overrides.

The cottage uses imported 2-metre wall modules, separate shutters/door/gables, and a
tiled roof. Keep a 2-metre grid for wall construction. Its front faces local -Z;
the stall and bench also face local -Z. World units are metres. The cottage is a
closed exterior, with a simple collision hull, not an accessible interior.

The stall combines imported crates with textured timber and a saved curved canvas
mesh. The existing produce-table idea is retained. Simple shapes remain useful for
collision and minor props; they no longer have to carry every architectural detail.

Shared URP materials are in `Assets/Art/VillageAudition/Materials`. Tune the palette
there, not in imported FBX material sub-assets. Source textures retain their original
pixels; import limits are 2048 with mipmaps and 4x anisotropic filtering. Normal maps
use the publisher's Unity/Godot orientation. Canvas is double-sided.

`VillageAssetWorkflow.cs` is the explicit initial authoring recipe, not a runtime
generator. **Create Fresh Audition refuses to overwrite existing output.** The saved
prefabs and scene are the editable source of truth after creation; changing the
builder does not silently replace artist edits. No third-party editor scripts or
package dependencies are installed.

## Source ownership and animation

Imported originals and publisher licenses live in `Assets/Art/ThirdParty/Quaternius`.
Keep that directory separate from our materials, prefabs, and controller. Preserve
`.meta` files and GUIDs when copying or updating any assets.

The character and animation file each use a valid Humanoid avatar. The controller
retargets `Idle_Loop`, `Walk_Loop`, and `Sitting_Idle_Loop` onto the character, loops
the clips, and disables root motion. The library also includes sitting entry/exit
clips for a later choreography integration. The current audition deliberately tests
the seated loop, not a finished sit-down/stand-up transition.

The free base-character edition supplies superhero-proportioned bodies, not dressed
villagers. This proves the skeletal-animation workflow but does not settle costumes,
faces, or the final five-character art direction. Do not promote that body to Henry
or Joan solely because its rig works.

## Production villagers and landscape (2026-09-18 refinement)

All five production characters now use dressed Humanoid prefabs in
`Assets/Art/VillageRefinement/Characters`. These combine peasant/ranger clothing,
extracted male/female faces, hair and beards on a shared skeleton. The anatomical
audition body is not visible in production. Edit clothing materials, hair, and scale
in these prefabs, not in the backend anchor. Their Animator controller uses imported
idle, walk, sitting entry/idle/exit and seated hand-gesture clips. World root motion
is disabled; the local event director owns positions and pacing. Hand sockets and
eye landmarks follow bones. The tackle box follows the hip through sitting.

The production scenery contains a LANDSCAPE group. Select a `VillageLandscapePath`
object, move its Scene-view handles, and click **Rebuild saved path mesh** in the
Inspector. Both knot movement and rebuilding support Undo. This explicitly updates
the saved mesh; Play does not rebuild paths. End fades and blended margins avoid
hard rectangular ends and coplanar road-intersection artifacts. If duplicating a
path, duplicate its mesh and material assets too before editing, to avoid changing
the original's shared assets.

Ready-coloured tree, grass, flower, shrub and fern prefabs live in
`Assets/Art/VillageRefinement/Nature`. Drag these into the scene for manual planting;
their materials are already mapped to URP. Distant trees have distance culling.
Keep the market/bench/porch witness triangle and the two ambient walking corridors
clear. Decorative ground cover has no collision. Do not add tall planting where it
hides the coins or the two focus characters.

The landscape uses saved heightfield meshes and the locally authored ground, water,
and sky shaders. It is not a Unity Terrain asset, and does not require Terrain Tools,
ProBuilder, a paid foliage shader, or a live MCP connection. The path tool samples
`VillageLandscapeProfile.Height`; change that profile along with any deliberate
terrain-height redesign, then revalidate actor grounding and routes. This pass keeps
the original core village heights to preserve the proven choreography.

The old VillageProduction prefab and separate audition are retained as references;
VillageScene points to the refined prefab. Never regenerate over artist edits.
No SampleScene content or backend code is part of this workflow.

## Verification

In an isolated Unity 6000.3.17f1 project with the Animation built-in module enabled:

    -batchmode -force-d3d11 -projectPath "<isolated project>" -executeMethod VillageAssetAuditionValidation.Run -logFile "<log>"

Do not add `-quit`; the checker exits after actual Play Mode updates. It checks
Humanoid validity, materials, missing scripts, saved prefabs, the absence of backend
identities, three animation states, changing walking knees, and the seated pose.
It captures seven PNGs under `ValidationArtifacts/AssetAudition`. This is not a
frame-rate benchmark. The existing `VillagePresentationValidation.Run` remains the
demo regression check, including callbacks, replay, timing, and ambient routes.
