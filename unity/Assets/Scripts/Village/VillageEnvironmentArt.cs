using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace Twicetold.Village
{
    public sealed partial class VillageSceneBootstrap
    {
        private readonly HashSet<Mesh> _ownedMeshes = new();
        private RenderPipelineAsset _previousPipeline;
        private UniversalRenderPipelineAsset _presentationPipeline;
        private VolumeProfile _presentationVolume;
        public int CombinedSourceRenderers { get; private set; }
        public int SceneryBatches { get; private set; }

        private Material CreateRiverMaterial()
        {
            var shader = Resources.Load<Shader>("VillageRiver");
            if (shader == null) return MaterialFor("River Fallback", new Color(.1f, .40f, .49f), .6f);
            var material = new Material(shader) { name = "Flowing Valley Water" };
            _materials.Add(material.name, material);
            return material;
        }

        private void ConfigurePresentationCamera(Camera camera)
        {
            // This scene's overrides are runtime-only; other scenes retain their project settings.
            var source = GraphicsSettings.currentRenderPipeline as UniversalRenderPipelineAsset;
            if (source != null)
            {
                _previousPipeline = QualitySettings.renderPipeline;
                _presentationPipeline = Instantiate(source);
                _presentationPipeline.name = "Village Presentation Pipeline (runtime)";
                _presentationPipeline.shadowDistance = 110f;
                _presentationPipeline.shadowCascadeCount = 4;
                _presentationPipeline.renderScale = 1f;
                QualitySettings.renderPipeline = _presentationPipeline;
            }
            var data = camera.GetUniversalAdditionalCameraData();
            data.antialiasing = AntialiasingMode.SubpixelMorphologicalAntiAliasing;
            data.antialiasingQuality = AntialiasingQuality.High;
            data.renderPostProcessing = true;
            var volume = new GameObject("Village Colour Grade").AddComponent<Volume>();
            volume.transform.SetParent(_villageRoot, false);
            volume.isGlobal = true;
            _presentationVolume = ScriptableObject.CreateInstance<VolumeProfile>();
            volume.sharedProfile = _presentationVolume;
            _presentationVolume.Add<Tonemapping>().mode.Override(TonemappingMode.Neutral);
            var grade = _presentationVolume.Add<ColorAdjustments>();
            grade.contrast.Override(8f);
            grade.saturation.Override(-5f);
        }

        private void BuildDistantLandscape()
        {
            // Three real depth layers, not a wall immediately behind the last house.
            BuildRidge("Far Blue Peaks", 600f, 83f, 120f, 119, new Color(.40f, .53f, .65f));
            BuildRidge("Middle Slate Range", 355f, 30f, 77f, 321, new Color(.34f, .47f, .53f));
            BuildRidge("Rolling Forest Foothills", 195f, 3f, 29f, 507, new Color(.29f, .43f, .31f));
            var cloud = UnlitMaterialFor("High Cloud Ivory", new Color(.86f, .89f, .88f));
            var random = new System.Random(631);
            for (var i = 0; i < 11; i++)
            {
                var angle = i * Mathf.PI * 2 / 11;
                var center = new Vector3(Mathf.Cos(angle) * 380f, 115f + (float)random.NextDouble() * 50, Mathf.Sin(angle) * 380f);
                for (var j = 0; j < 4; j++)
                {
                    var part = Ellipsoid("High Summer Cloud", _villageRoot, center + new Vector3(j * 19f, j % 2 * 4, 0),
                        new Vector3(28f, 5 + j % 3 * 2, 16f), cloud);
                    part.GetComponent<Renderer>().shadowCastingMode = ShadowCastingMode.Off;
                }
            }
            var field = MaterialFor("Valley Field Gold", new Color(.50f, .50f, .26f));
            var distantGreen = MaterialFor("Valley Field Green", new Color(.31f, .45f, .24f));
            for (var i = 0; i < 7; i++)
            {
                var x = -73f + i * 24f;
                Primitive("Distant Cultivated Field", PrimitiveType.Cube, new Vector3(x, -.61f, 110 + i % 3 * 17),
                    new Vector3(20f, .10f, 34f), i % 2 == 0 ? field : distantGreen, _villageRoot, false, Quaternion.Euler(0, -14, 0));
            }
        }

        private void BuildRidge(string name, float radius, float baseHeight, float relief, int seed, Color color)
        {
            const int segments = 72;
            var random = new System.Random(seed);
            var crest = new float[segments];
            for (var i = 0; i < segments; i++)
                crest[i] = baseHeight + relief * (.3f + .38f * Mathf.Sin(i * .51f + seed) + .32f * (float)random.NextDouble());
            var vertices = new List<Vector3>(); var triangles = new List<int>();
            for (var i = 0; i < segments; i++)
            {
                var next = (i + 1) % segments;
                var a = i * Mathf.PI * 2 / segments; var b = (i + 1) * Mathf.PI * 2 / segments;
                var va = new Vector3(Mathf.Sin(a), 0, Mathf.Cos(a)); var vb = new Vector3(Mathf.Sin(b), 0, Mathf.Cos(b));
                var lowA = va * (radius - relief * 2.1f) + Vector3.down * 6;
                var lowB = vb * (radius - relief * 2.1f) + Vector3.down * 6;
                var highA = va * radius + Vector3.up * crest[i];
                var highB = vb * radius + Vector3.up * crest[next];
                var midpoint = (lowA + lowB + highA + highB) * .25f - va * (relief * .06f);
                AddFacet(vertices, triangles, lowA, highA, midpoint);
                AddFacet(vertices, triangles, highA, highB, midpoint);
                AddFacet(vertices, triangles, highB, lowB, midpoint);
                AddFacet(vertices, triangles, lowB, lowA, midpoint);
            }
            var mesh = new Mesh { name = name };
            mesh.SetVertices(vertices); mesh.SetTriangles(triangles, 0); mesh.RecalculateNormals(); mesh.RecalculateBounds();
            var obj = CreateMeshObject(name, mesh, Vector3.zero, Vector3.one, MaterialFor(name, color), _villageRoot, false);
            obj.GetComponent<Renderer>().shadowCastingMode = ShadowCastingMode.Off;
        }

        private static void AddFacet(List<Vector3> vertices, List<int> triangles, Vector3 a, Vector3 b, Vector3 c)
        {
            var index = vertices.Count; vertices.AddRange(new[] { a, b, c }); triangles.AddRange(new[] { index, index + 1, index + 2 });
        }

        private void AddHouseCraft(Transform house, float scale, Color roofColor, Material timber, Material stone)
        {
            var details = Joint("Architectural Joinery", house, Vector3.zero);
            details.localScale = Vector3.one * scale;
            var roofShade = MaterialFor(house.name + " Roof Courses", roofColor * .84f);
            var shutter = MaterialFor("Painted Sage Shutters", new Color(.28f, .38f, .26f));
            var glass = MaterialFor("Daylight Window", new Color(.30f, .43f, .43f), .5f);
            // Roof courses follow both pitched planes, with end grain visible at the eaves.
            for (var side = -1; side <= 1; side += 2)
            {
                for (var row = 1; row < 9; row++)
                {
                    var t = row / 9f;
                    Primitive("Overlapping Roof Course", PrimitiveType.Cube, new Vector3(side * 3.675f * t, 6.27f - 2.55f * t + .025f, 0),
                        new Vector3(.075f, .055f, 6.6f), row % 3 == 0 ? timber : roofShade, details, false, Quaternion.Euler(0, 0, -side * 34.8f));
                }
                BeamBetween("Gable Fascia", details, new Vector3(0, 6.28f, -3.32f), new Vector3(side * 3.73f, 3.70f, -3.32f), .15f, timber);
                BeamBetween("Rear Gable Fascia", details, new Vector3(0, 6.28f, 3.32f), new Vector3(side * 3.73f, 3.70f, 3.32f), .15f, timber);
                for (var z = -2; z <= 2; z += 2)
                    Primitive("Side Wall Post", PrimitiveType.Cube, new Vector3(side * 3.15f, 2.04f, z), new Vector3(.13f, 3.48f, .14f), timber, details, false);
                foreach (var y in new[] { .70f, 3.05f, 3.7f })
                    Primitive("Side Wall Rail", PrimitiveType.Cube, new Vector3(side * 3.16f, y, 0), new Vector3(.14f, .13f, 5.45f), timber, details, false);
                var window = Joint("Side Casement", details, new Vector3(side * 3.19f, 2.15f, .8f));
                window.localRotation = Quaternion.Euler(0, -side * 90, 0);
                CreateWindow(Vector3.zero, .80f, glass, timber, shutter, window);
                foreach (var x in new[] { -1.95f, 1.95f })
                {
                    Primitive("Open Window Shutter", PrimitiveType.Cube, new Vector3(x + side * .75f, 2.13f, -2.91f),
                        new Vector3(.35f, 1.03f, .085f), shutter, details, false, Quaternion.Euler(0, side * 12, 0));
                    for (var r = 0; r < 4; r++)
                        Primitive("Shutter Slat", PrimitiveType.Cube, new Vector3(x + side * .75f, 1.82f + r * .20f, -2.963f), new Vector3(.32f, .025f, .025f), timber, details, false);
                }
                BeamBetween("Front Diagonal Brace", details, new Vector3(side * 2.9f, 3.07f, -2.91f), new Vector3(side * 2.22f, 3.70f, -2.91f), .10f, timber);
            }
            for (var i = -2; i <= 2; i++)
                Primitive("Door Plank Seam", PrimitiveType.Cube, new Vector3(i * .2f, 1.36f, -2.86f), new Vector3(.012f, 2.25f, .013f), roofShade, details, false);
            for (var x = -3; x <= 3; x++)
                Primitive("Foundation Block", PrimitiveType.Cube, new Vector3(x * .94f, .34f, -3.0f), new Vector3(.87f, .40f, .12f), stone, details, false);
            var lane = MaterialFor("Sunlit Packed Earth", new Color(.84f, .72f, .48f));
            var entrance = house.TransformPoint(new Vector3(0, 0, -5.5f * scale));
            CreateRibbon("Doorway Approach", new[] { new Vector3(RoadCenterAt(entrance.z), 0, entrance.z), entrance }, 2.8f, .115f, lane, true, false);
        }

        private void BeamBetween(string name, Transform parent, Vector3 a, Vector3 b, float width, Material material)
        {
            var beam = Primitive(name, PrimitiveType.Cube, (a + b) * .5f, new Vector3(width, (b - a).magnitude, width), material, parent, false);
            beam.transform.localRotation = Quaternion.FromToRotation(Vector3.up, b - a);
        }

        private void BuildLandscapeDetails()
        {
            var distantLeaf = MaterialFor("Distant Forest Canopy", new Color(.25f, .40f, .27f));
            var distantPine = MaterialFor("Distant Forest Pine", new Color(.20f, .34f, .26f));
            for (var i = 0; i < 110; i++)
            {
                var angle = i * 2.4f;
                var radius = 78 + i % 5 * 11;
                var p = new Vector3(Mathf.Sin(angle) * radius, -.65f, Mathf.Cos(angle) * radius);
                if (Mathf.Abs(p.x - RiverCenter(p.z)) < 14 || Mathf.Abs(p.x - 12) < 9) continue;
                var height = 5f + i % 7 * .8f;
                CreateCone("Distant Forest Tree", p, 2.3f + i % 3 * .35f, height, 7, i % 2 == 0 ? distantLeaf : distantPine, _villageRoot);
            }
            CreateRibbon("Road Beyond the Village", new[] { new Vector3(4, 0, 48), new Vector3(8, 0, 65), new Vector3(12, 0, 88), new Vector3(18, 0, 115), new Vector3(3, 0, 140) },
                4.8f, -.60f, MaterialFor("Sunlit Packed Earth", new Color(.84f, .72f, .48f)), false, false);
            var reed = MaterialFor("River Reed", new Color(.38f, .46f, .19f));
            var tips = MaterialFor("Reed Seed Heads", new Color(.32f, .21f, .10f));
            var random = new System.Random(2609);
            for (var i = 0; i < 48; i++)
            {
                var z = -48f + i * 2;
                var x = RiverCenter(z) + (i % 2 == 0 ? -9.5f : 9.5f);
                var y = TerrainHeight(x, z);
                if (Mathf.Abs(z + 7f) < 4) continue;
                for (var j = 0; j < 3; j++)
                {
                    var p = new Vector3(x + j * .18f, y, z + (float)random.NextDouble() * .4f);
                    var height = .6f + (float)random.NextDouble() * .55f;
                    BeamBetween("Waterside Reed", _villageRoot, p, p + new Vector3(.1f, height, .03f), .025f, reed);
                    Ellipsoid("Reed Head", _villageRoot, p + new Vector3(.1f, height, .03f), new Vector3(.04f, .14f, .04f), tips);
                }
            }
            var stem = MaterialFor("Market Fruit Stem", new Color(.27f, .18f, .08f));
            var apple = MaterialFor("Orchard Apple", new Color(.69f, .17f, .10f), .18f);
            var pear = MaterialFor("Orchard Pear", new Color(.61f, .66f, .22f), .15f);
            var tray = MaterialFor("Market Basket", new Color(.49f, .32f, .14f));
            for (var row = 0; row < 3; row++)
            {
                var basket = Joint("Woven Produce Tray", _market, new Vector3(-1.8f + row * 1.8f, 1.04f, 0));
                Profile("Basket Rim", basket, Vector3.zero, tray, new Vector3(0, .65f, .48f), new Vector3(.10f, .69f, .51f));
                for (var j = 0; j < 12; j++)
                {
                    var p = new Vector3((j % 4 - 1.5f) * .25f, .13f, (j / 4 - 1) * .25f);
                    Ellipsoid("Fresh Orchard Fruit", basket, p, new Vector3(.11f, row % 2 == 0 ? .11f : .14f, .11f), row % 2 == 0 ? apple : pear);
                    BeamBetween("Fruit Stem", basket, p + Vector3.up * .10f, p + new Vector3(.012f, .16f, 0), .015f, stem);
                }
            }
        }

        private void CombineStaticScenery()
        {
            // Small spatial batches retain useful culling. Colliders/landmarks stay in the hierarchy.
            var groups = new Dictionary<(Material, int, int, ShadowCastingMode), List<MeshFilter>>();
            foreach (var filter in _villageRoot.GetComponentsInChildren<MeshFilter>())
            {
                var renderer = filter.GetComponent<MeshRenderer>();
                if (renderer == null || !renderer.enabled || filter.GetComponent<RiverSurfaceAnimator>() != null || renderer.bounds.size.magnitude > 65f) continue;
                var p = renderer.bounds.center;
                var key = (renderer.sharedMaterial, Mathf.FloorToInt(p.x / 16), Mathf.FloorToInt(p.z / 16), renderer.shadowCastingMode);
                if (!groups.TryGetValue(key, out var list)) groups[key] = list = new List<MeshFilter>();
                list.Add(filter);
            }
            foreach (var group in groups)
            {
                if (group.Value.Count < 3) continue;
                var instances = new List<CombineInstance>();
                foreach (var filter in group.Value)
                    instances.Add(new CombineInstance { mesh = filter.sharedMesh, transform = _villageRoot.worldToLocalMatrix * filter.transform.localToWorldMatrix });
                var mesh = new Mesh { name = "Village Spatial Batch", indexFormat = IndexFormat.UInt32 };
                mesh.CombineMeshes(instances.ToArray(), true, true);
                var obj = CreateMeshObject("Scenery Batch " + SceneryBatches++, mesh, Vector3.zero, Vector3.one, group.Key.Item1, _villageRoot, false);
                obj.GetComponent<Renderer>().shadowCastingMode = group.Key.Item4;
                foreach (var filter in group.Value) filter.GetComponent<MeshRenderer>().enabled = false;
                CombinedSourceRenderers += group.Value.Count;
            }
        }

        private void OnDestroy()
        {
            if (_presentationPipeline != null)
            {
                if (QualitySettings.renderPipeline == _presentationPipeline) QualitySettings.renderPipeline = _previousPipeline;
                Destroy(_presentationPipeline);
            }
            if (_presentationVolume != null)
            {
                foreach (var component in _presentationVolume.components) Destroy(component);
                Destroy(_presentationVolume);
            }
            foreach (var material in _materials.Values) if (material != null) Destroy(material);
            foreach (var mesh in _ownedMeshes) if (mesh != null) Destroy(mesh);
        }
    }
}
