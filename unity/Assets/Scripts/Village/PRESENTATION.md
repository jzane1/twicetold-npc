# Village presentation

VillageScene loads `Assets/Art/VillageRefinement/VillageScenery.prefab`: saved,
editable scenery with nested modular architecture, sculpted landscape meshes,
textured nature, and spline paths. The bootstrap adds the player, five stable NPC
anchors with assigned skinned visual prefabs, event choreography, and runtime
presentation/batching. No backend transport or SampleScene content is used.

## Artwork and editing

- Five dressed Humanoid characters replace the primitive-built production cast.
  Faces, hair, beards, skin, peasant/ranger clothes and imported animations come
  from the licensed Quaternius sources listed in ThirdParty/Quaternius/PROVENANCE.md.
  The naked anatomical sample is not used as production art.
- Six modular cottages, market stalls, benches, wagon and textured timber remain
  editable nested prefabs. Henry stays behind his stall; Joan stays on her porch.
- The old horizon walls, primitive tree canopies and sparse stick grass are replaced
  by a continuous low-poly heightfield, wooded hills, textured trees, clustered
  meadow grass, ferns, flowers, shrubs, rocks and pebbled riverbanks.
- Packed-earth paths have world-space surface variation, feathered sides and end
  fades. Their intersections alpha-blend without writing competing depth.
  Select a VillageLandscapePath, move Scene-view handles, and explicitly rebuild
  its saved mesh in the Inspector. See ASSET_WORKFLOW.md for shared-asset cautions.
- Reusable, correctly coloured planting prefabs are in VillageRefinement/Nature.
  Decorative ground cover has no collision. Keep event sightlines/routes clear.
- Depth-coloured river water, restrained moving ripples and shallow-water foam;
  a locally authored gradient/cloud sky; height-based rock tint and distant haze.
  These are code-authored shaders, not AI-generated textures or paid pack shaders.

Use **Tools > Village > Open Playable Village**. Edit in stopped Edit Mode.
The old production prefab and separate asset audition are retained; they are not
the scenery referenced by VillageScene. Never regenerate over authored work.

## Rendering

The camera retains its 950-metre far plane, full render scale, high-quality SMAA,
neutral tonemapping and runtime-only URP override. Haze runs from 150 to 900 metres;
the terrain and continuing road provide real depth instead of a nearby horizon wall.
Camera depth is enabled for the water shader. Original project pipeline assets are
not modified.

Readable single-material geometry is spatially combined at Play startup.
Multi-material imported models and LOD-controlled trees are excluded, preserving
material slots and distance culling. Source renderers remain editable before Play.
The validation run reports source/batch counts; these are not an FPS benchmark.

## Choreography

VillageRigPresentation adapts the existing motion interface to imported Humanoid
idle, walk, sitting entry/idle/exit and seated hand gestures. Animator root motion
is off: the director owns world movement and roughly 13-second pacing. Animation
speed follows walking speed. Hair/clothing share the body rig; props follow hand
sockets, and the tackle box follows the hip when sitting. Eye landmarks follow
the head. Skinned art is isolated below the stable backend attachment root.

Exactly five IDs remain, and only Henry/Joan expose dialogue/observation callbacks.
The gold event emits one callback per witness per replay. Ambient walking uses
collision sweeps, not automatic rerouting. See NPC_INTEGRATION.md for the unchanged
integration contract.

## Verification

In an isolated Unity 6000.3.17f1 project, with graphics and Animation enabled:

    -batchmode -force-d3d11 -projectPath "<isolated project>" -executeMethod VillagePresentationValidation.Run -logFile "<log path>"

Do not add -quit or launch a second editor against an already open project.
The verifier tests path-knot/width rebuilding, five skinned rigs and valid bones,
visual facing, two dialogue callbacks and real targeting, all event states,
two replays, one observation each, witness sightlines, walking knees/feet,
bench-height seating and collision-free ambient routes over 42 simulated seconds.
It writes ValidationArtifacts/validation.txt and full-resolution scene/character
screenshots. This is presentation regression evidence, not a backend floor.

The isolated editor can emit its pre-existing UnityEditor.Search startup exception
and Unity JobTempAlloc shutdown warnings. Record those separately from the
presentation verifier result; do not describe the entire editor log as warning-free.
