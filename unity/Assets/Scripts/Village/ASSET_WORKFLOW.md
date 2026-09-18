# Village asset workflow

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

## Promotion into the demo

First judge the cottage/stall in this scene at player-eye height. A wholesale bake
or art swap is not automatic: current village geometry is spatially combined at
runtime, so moving its disabled source renderers cannot update those baked batches.
The next conversion should make scenery an authored scene/prefab layer and retain
the gameplay roots as a separate layer, with explicitly serialized landmark refs.

Replace only the visual child of each eventual NPC prefab; keep stable identity,
colliders, hand sockets, attachment point, and dialogue/observation callbacks. Adapt
the choreography's motion interface to Animator rather than moving memory logic into
Unity. Retest the gold bag, hands, bench alignment, gaze, timings, and both witnesses.
Do not copy anything from SampleScene or modify the external backend.

## Verification

In an isolated Unity 6000.3.17f1 project with the Animation built-in module enabled:

    -batchmode -force-d3d11 -projectPath "<isolated project>" -executeMethod VillageAssetAuditionValidation.Run -logFile "<log>"

Do not add `-quit`; the checker exits after actual Play Mode updates. It checks
Humanoid validity, materials, missing scripts, saved prefabs, the absence of backend
identities, three animation states, changing walking knees, and the seated pose.
It captures seven PNGs under `ValidationArtifacts/AssetAudition`. This is not a
frame-rate benchmark. The existing `VillagePresentationValidation.Run` remains the
demo regression check, including callbacks, replay, timing, and ambient routes.
