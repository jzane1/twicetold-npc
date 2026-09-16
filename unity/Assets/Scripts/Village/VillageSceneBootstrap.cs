using System;
using System.Collections.Generic;
using NpcMemory.Unity;
using UnityEngine;
using UnityEngine.InputSystem;

namespace Twicetold.Village
{
    /// <summary>Creates the playable village at runtime while SampleScene remains the bridge harness.</summary>
    public sealed class VillageSceneBootstrap : MonoBehaviour
    {
        [Header("Village")]
        public bool buildOnStart = true;

        [Header("Optional live NPC bridge")]
        [Tooltip("Requires an existing backend agent UUID. The village never auto-provisions agents.")]
        public bool enableLiveNpcBridge;
        public string npcServiceUrl = "http://127.0.0.1:8000";
        public string npcAgentId = "";

        private readonly Dictionary<string, Material> _materials = new();
        private Transform _villageRoot;
        private VillageHud _hud;

        private void Awake()
        {
            Application.runInBackground = true;
            if (buildOnStart) BuildVillage();
        }

        private void BuildVillage()
        {
            if (transform.Find("Generated Village") != null) return;
            _villageRoot = new GameObject("Generated Village").transform;
            _villageRoot.SetParent(transform, false);
            BuildLighting();
            BuildLandscape();
            BuildRoadAndLandmarks();
            BuildHomes();
            BuildMarket();
            BuildVillageGreenery();
            BuildKeeper();
            BuildPlayer();
        }

        private void BuildLighting()
        {
            RenderSettings.ambientLight = new Color(0.72f, 0.80f, 0.88f);
            RenderSettings.fog = true;
            RenderSettings.fogColor = new Color(0.63f, 0.75f, 0.87f);
            RenderSettings.fogDensity = 0.0035f;
            var sun = new GameObject("Village Sun").AddComponent<Light>();
            sun.transform.SetParent(_villageRoot, false);
            sun.type = LightType.Directional;
            sun.color = new Color(1f, 0.91f, 0.72f);
            sun.intensity = 1.25f;
            sun.transform.rotation = Quaternion.Euler(48f, -33f, 0f);
        }

        private void BuildLandscape()
        {
            var grass = MaterialFor("Grass", new Color(0.31f, 0.62f, 0.22f));
            var grassLight = MaterialFor("Grass Light", new Color(0.42f, 0.73f, 0.28f));
            var sand = MaterialFor("River Sand", new Color(0.86f, 0.77f, 0.52f));
            var water = MaterialFor("River Water", new Color(0.19f, 0.55f, 0.82f));
            var mountain = MaterialFor("Distant Mountains", new Color(0.37f, 0.48f, 0.62f));
            var mountainLight = MaterialFor("Mountain Highlights", new Color(0.55f, 0.65f, 0.73f));

            Primitive("Meadow", PrimitiveType.Cube, new Vector3(0f, -0.35f, 0f), new Vector3(100f, 0.7f, 92f), grass, _villageRoot, true);
            Primitive("River", PrimitiveType.Cube, new Vector3(51f, -0.12f, 4f), new Vector3(26f, 0.18f, 96f), water, _villageRoot, false);
            Primitive("Riverbank", PrimitiveType.Cube, new Vector3(38.5f, -0.06f, 4f), new Vector3(4f, 0.14f, 96f), sand, _villageRoot, false);
            CreateCone("North Mountain", new Vector3(-18f, 0f, 48f), 23f, 30f, 7, mountain, _villageRoot);
            CreateCone("North Mountain Peak", new Vector3(-18f, 22f, 48f), 10f, 13f, 7, mountainLight, _villageRoot);
            CreateCone("West Ridge", new Vector3(-47f, 0f, 28f), 19f, 19f, 6, mountain, _villageRoot);
            CreateCone("East Cliff", new Vector3(43f, 1f, 31f), 13f, 22f, 6, mountain, _villageRoot);

            var random = new System.Random(117);
            for (var i = 0; i < 48; i++)
            {
                var x = (float)(random.NextDouble() * 88d - 44d);
                var z = (float)(random.NextDouble() * 82d - 41d);
                if (Mathf.Abs(x) < 12f && z > -38f && z < 39f) continue;
                var blade = Primitive("Grass Tuft", PrimitiveType.Cube, new Vector3(x, 0.17f, z), new Vector3(0.12f, 0.35f + (float)random.NextDouble() * 0.25f, 0.12f), grassLight, _villageRoot, false);
                blade.transform.localRotation = Quaternion.Euler((float)random.NextDouble() * 12f, (float)random.NextDouble() * 180f, (float)random.NextDouble() * 12f);
            }
        }

        private void BuildRoadAndLandmarks()
        {
            var path = MaterialFor("Village Path", new Color(0.83f, 0.72f, 0.48f));
            var stone = MaterialFor("Stone", new Color(0.38f, 0.43f, 0.46f));
            var stoneLight = MaterialFor("Stone Light", new Color(0.57f, 0.62f, 0.61f));
            var wood = MaterialFor("Dark Wood", new Color(0.22f, 0.13f, 0.075f));
            var lampGlow = MaterialFor("Lantern Glow", new Color(1f, 0.77f, 0.29f), true);
            var route = new[]
            {
                new Vector3(0f, 0.04f, -42f), new Vector3(-1f, 0.04f, -27f), new Vector3(1.5f, 0.04f, -13f),
                new Vector3(-1f, 0.04f, 0f), new Vector3(2.2f, 0.04f, 14f), new Vector3(0.5f, 0.04f, 28f), new Vector3(4f, 0.04f, 43f),
            };
            for (var i = 0; i < route.Length - 1; i++) CreateRoadSegment(route[i], route[i + 1], 5.2f, path);
            CreateStoneCircle(new Vector3(-1f, 0.08f, 1.5f), stone, stoneLight);
            CreateWell(new Vector3(-1f, 0f, 1.5f), wood, lampGlow);
            CreateSignpost(new Vector3(-3.8f, 0f, -14f), wood, path);
            CreateLantern(new Vector3(2.8f, 0f, -20f), wood, lampGlow);
            CreateLantern(new Vector3(-2.7f, 0f, 10f), wood, lampGlow);
            CreateLantern(new Vector3(3.8f, 0f, 24f), wood, lampGlow);
            CreateWorldInteraction("Village Noticeboard", new Vector3(-3.8f, 0f, -14f), 3f, "Read the noticeboard", "The posted notices mention a missing cart, a market day, and a road washed out beyond the north pass.");
            CreateWorldInteraction("Old Well", new Vector3(-1f, 0f, 1.5f), 3.2f, "Look into the old well", "Cool water catches the sunlight. Someone has tied a small bronze charm to the crank.");
        }

        private void BuildHomes()
        {
            CreateHouse("Miller's Cottage", new Vector3(-15f, 0f, -17f), 12f, 1.15f, new Color(0.82f, 0.68f, 0.46f), new Color(0.78f, 0.53f, 0.18f));
            CreateHouse("Waystone Inn", new Vector3(-14f, 0f, 7f), -9f, 1.45f, new Color(0.72f, 0.55f, 0.33f), new Color(0.92f, 0.68f, 0.22f));
            CreateHouse("River House", new Vector3(16f, 0f, 17f), 22f, 1.1f, new Color(0.70f, 0.61f, 0.43f), new Color(0.52f, 0.30f, 0.16f));
            CreateHouse("Greenroof Cottage", new Vector3(16f, 0f, -14f), -24f, 1.05f, new Color(0.76f, 0.66f, 0.47f), new Color(0.46f, 0.57f, 0.18f));
            CreateHouse("North Road Home", new Vector3(-10f, 0f, 28f), 18f, 0.92f, new Color(0.86f, 0.73f, 0.51f), new Color(0.62f, 0.39f, 0.16f));
        }

        private void BuildMarket()
        {
            var wood = MaterialFor("Dark Wood", new Color(0.22f, 0.13f, 0.075f));
            var canvas = MaterialFor("Market Canvas", new Color(0.72f, 0.81f, 0.52f));
            var berry = MaterialFor("Market Berries", new Color(0.62f, 0.17f, 0.12f));
            var crate = MaterialFor("Crates", new Color(0.45f, 0.28f, 0.12f));
            var market = new GameObject("Riverside Market").transform;
            market.SetParent(_villageRoot, false);
            market.localPosition = new Vector3(18f, 0f, 3f);
            Primitive("Counter", PrimitiveType.Cube, new Vector3(0f, 1.1f, 0f), new Vector3(6f, 1.5f, 2.1f), crate, market, true);
            for (var i = 0; i < 4; i++)
            {
                var x = i < 2 ? -3f : 3f;
                var z = i % 2 == 0 ? -1.6f : 1.6f;
                Primitive("Canopy Pole", PrimitiveType.Cylinder, new Vector3(x, 3.1f, z), new Vector3(0.13f, 2.1f, 0.13f), wood, market, false);
            }
            Primitive("Canopy", PrimitiveType.Cube, new Vector3(0f, 5.05f, 0f), new Vector3(7.2f, 0.25f, 4.2f), canvas, market, false);
            for (var i = 0; i < 6; i++)
            {
                var fruit = Primitive("Produce", PrimitiveType.Sphere, new Vector3(-2.2f + i * 0.85f, 2.03f, -0.2f + (i % 2) * 0.65f), Vector3.one * 0.35f, berry, market, false);
                fruit.transform.localRotation = Quaternion.Euler(i * 31f, i * 49f, 0f);
            }
            CreateWorldInteraction("Market Stall", new Vector3(18f, 0f, 3f), 4.2f, "Browse the market stall", "Fresh berries, river fish, and cedar candles are laid out beneath the shade cloth.");
        }

        private void BuildVillageGreenery()
        {
            var treePositions = new[]
            {
                new Vector3(-28f, 0f, -28f), new Vector3(-32f, 0f, -6f), new Vector3(-26f, 0f, 20f), new Vector3(-24f, 0f, 34f),
                new Vector3(28f, 0f, -28f), new Vector3(31f, 0f, -8f), new Vector3(27f, 0f, 19f), new Vector3(32f, 0f, 29f),
                new Vector3(36f, 0f, 40f), new Vector3(-39f, 0f, 7f), new Vector3(12f, 0f, 38f), new Vector3(-6f, 0f, 39f),
            };
            for (var i = 0; i < treePositions.Length; i++) CreateTree(treePositions[i], 0.8f + (i % 3) * 0.18f);
            var random = new System.Random(291);
            var rock = MaterialFor("Rocks", new Color(0.33f, 0.38f, 0.41f));
            for (var i = 0; i < 25; i++)
            {
                var x = (float)(random.NextDouble() * 76d - 38d);
                var z = (float)(random.NextDouble() * 78d - 35d);
                if (Mathf.Abs(x) < 9f && z > -37f && z < 37f) continue;
                var scale = 0.35f + (float)random.NextDouble() * 0.8f;
                var boulder = Primitive("Low Poly Rock", PrimitiveType.Sphere, new Vector3(x, scale * 0.38f, z), new Vector3(scale * 1.25f, scale * 0.7f, scale), rock, _villageRoot, false);
                boulder.transform.localRotation = Quaternion.Euler((float)random.NextDouble() * 40f, (float)random.NextDouble() * 180f, (float)random.NextDouble() * 40f);
            }
        }

        private void BuildKeeper()
        {
            var keeper = new GameObject("Village Keeper").transform;
            keeper.SetParent(_villageRoot, false);
            keeper.localPosition = new Vector3(3.1f, 0f, 8.5f);
            keeper.localRotation = Quaternion.Euler(0f, 180f, 0f);
            var coat = MaterialFor("Keeper Coat", new Color(0.18f, 0.30f, 0.54f));
            var skin = MaterialFor("Keeper Skin", new Color(0.72f, 0.46f, 0.29f));
            var hair = MaterialFor("Keeper Hair", new Color(0.17f, 0.09f, 0.035f));
            var glow = MaterialFor("Keeper Lantern", new Color(1f, 0.76f, 0.30f), true);
            Primitive("Keeper Body", PrimitiveType.Capsule, new Vector3(0f, 1.02f, 0f), new Vector3(0.8f, 1.02f, 0.8f), coat, keeper, true);
            Primitive("Keeper Head", PrimitiveType.Sphere, new Vector3(0f, 2.25f, 0f), new Vector3(0.62f, 0.66f, 0.62f), skin, keeper, false);
            Primitive("Keeper Hair", PrimitiveType.Sphere, new Vector3(0f, 2.55f, 0f), new Vector3(0.66f, 0.31f, 0.66f), hair, keeper, false);
            var lantern = Primitive("Keeper Lantern", PrimitiveType.Sphere, new Vector3(0.55f, 1.15f, 0.15f), Vector3.one * 0.22f, glow, keeper, false);
            var light = lantern.AddComponent<Light>();
            light.type = LightType.Point;
            light.range = 6f;
            light.intensity = 1.1f;
            light.color = new Color(1f, 0.65f, 0.25f);
            var interaction = keeper.gameObject.AddComponent<VillageNpcInteraction>();
            interaction.Configure(enableLiveNpcBridge, npcServiceUrl, npcAgentId);
        }

        private void BuildPlayer()
        {
            var player = new GameObject("Village Player");
            player.transform.SetParent(_villageRoot, false);
            player.transform.SetPositionAndRotation(new Vector3(0f, 0.05f, -36f), Quaternion.identity);
            var controller = player.AddComponent<CharacterController>();
            controller.height = 1.8f;
            controller.radius = 0.32f;
            controller.center = new Vector3(0f, 0.9f, 0f);
            controller.stepOffset = 0.28f;
            var cameraRoot = new GameObject("Player Camera").transform;
            cameraRoot.SetParent(player.transform, false);
            cameraRoot.localPosition = new Vector3(0f, 1.62f, 0f);
            var camera = cameraRoot.gameObject.AddComponent<Camera>();
            camera.tag = "MainCamera";
            camera.fieldOfView = 66f;
            camera.nearClipPlane = 0.03f;
            camera.farClipPlane = 220f;
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = new Color(0.46f, 0.69f, 0.88f);
            var playerController = player.AddComponent<VillagePlayerController>();
            playerController.cameraTransform = cameraRoot;
            _hud = gameObject.AddComponent<VillageHud>();
            playerController.hud = _hud;
        }

        private void CreateHouse(string name, Vector3 position, float yaw, float scale, Color wallColor, Color roofColor)
        {
            var house = new GameObject(name).transform;
            house.SetParent(_villageRoot, false);
            house.localPosition = position;
            house.localRotation = Quaternion.Euler(0f, yaw, 0f);
            var walls = MaterialFor($"{name} Walls", wallColor);
            var roof = MaterialFor($"{name} Roof", roofColor);
            var wood = MaterialFor("Dark Wood", new Color(0.22f, 0.13f, 0.075f));
            var window = MaterialFor("Warm Windows", new Color(1f, 0.71f, 0.27f), true);
            Primitive("Walls", PrimitiveType.Cube, new Vector3(0f, 1.85f * scale, 0f), new Vector3(6.2f * scale, 3.7f * scale, 5.4f * scale), walls, house, true);
            CreateGabledRoof(house, new Vector3(0f, 3.65f * scale, 0f), 7.1f * scale, 6.5f * scale, 2.6f * scale, roof);
            Primitive("Door", PrimitiveType.Cube, new Vector3(0f, 1.05f * scale, -2.74f * scale), new Vector3(1.15f * scale, 2.1f * scale, 0.15f), wood, house, true);
            Primitive("Porch", PrimitiveType.Cube, new Vector3(0f, 0.17f * scale, -3.25f * scale), new Vector3(2.3f * scale, 0.26f * scale, 1.15f * scale), wood, house, true);
            foreach (var x in new[] { -1.95f, 1.95f }) Primitive("Window", PrimitiveType.Cube, new Vector3(x * scale, 2.08f * scale, -2.76f * scale), new Vector3(0.78f * scale, 0.82f * scale, 0.1f), window, house, false);
            for (var i = -2; i <= 2; i += 2) Primitive("Timber Beam", PrimitiveType.Cube, new Vector3(i * scale, 1.85f * scale, -2.79f * scale), new Vector3(0.16f * scale, 3.6f * scale, 0.13f), wood, house, false);
            Primitive("Chimney", PrimitiveType.Cube, new Vector3(1.85f * scale, 5.15f * scale, 0.55f * scale), new Vector3(0.65f * scale, 2.3f * scale, 0.65f), wood, house, true);
            CreateFence(house, new Vector3(-4.9f * scale, 0f, -4.2f * scale), new Vector3(4.9f * scale, 0f, -4.2f * scale), wood);
        }

        private void CreateTree(Vector3 position, float scale)
        {
            var tree = new GameObject("Low Poly Tree").transform;
            tree.SetParent(_villageRoot, false);
            tree.localPosition = position;
            var trunk = MaterialFor("Tree Trunks", new Color(0.27f, 0.15f, 0.075f));
            var foliage = MaterialFor("Tree Foliage", new Color(0.15f, 0.46f, 0.16f));
            var foliageLight = MaterialFor("Tree Foliage Light", new Color(0.31f, 0.62f, 0.20f));
            Primitive("Trunk", PrimitiveType.Cylinder, new Vector3(0f, 1.7f * scale, 0f), new Vector3(0.32f * scale, 1.7f * scale, 0.32f * scale), trunk, tree, true);
            Primitive("Lower Canopy", PrimitiveType.Sphere, new Vector3(0f, 4.05f * scale, 0f), new Vector3(2.4f * scale, 2.1f * scale, 2.2f * scale), foliage, tree, false);
            Primitive("Upper Canopy", PrimitiveType.Sphere, new Vector3(-0.25f * scale, 5.45f * scale, 0.1f), new Vector3(1.85f * scale, 1.7f * scale, 1.75f * scale), foliageLight, tree, false);
        }

        private void CreateRoadSegment(Vector3 start, Vector3 end, float width, Material material)
        {
            var delta = end - start;
            var segment = Primitive("Winding Path", PrimitiveType.Cube, (start + end) * 0.5f, new Vector3(width, 0.11f, delta.magnitude), material, _villageRoot, false);
            segment.transform.rotation = Quaternion.LookRotation(new Vector3(delta.x, 0f, delta.z));
        }

        private void CreateStoneCircle(Vector3 center, Material stone, Material stoneLight)
        {
            for (var i = 0; i < 9; i++)
            {
                var angle = i / 9f * Mathf.PI * 2f;
                var block = Primitive("Well Stone", PrimitiveType.Cube, center + new Vector3(Mathf.Cos(angle), 0.16f, Mathf.Sin(angle)) * 2.2f, new Vector3(0.72f, 0.35f, 0.52f), i % 2 == 0 ? stone : stoneLight, _villageRoot, true);
                block.transform.rotation = Quaternion.Euler(0f, -angle * Mathf.Rad2Deg, 0f);
            }
        }

        private void CreateWell(Vector3 position, Material wood, Material glow)
        {
            var well = new GameObject("Village Well").transform;
            well.SetParent(_villageRoot, false);
            well.localPosition = position;
            Primitive("Well Water", PrimitiveType.Cylinder, new Vector3(0f, 0.3f, 0f), new Vector3(1.55f, 0.08f, 1.55f), MaterialFor("Well Water", new Color(0.16f, 0.48f, 0.65f)), well, false);
            for (var side = -1; side <= 1; side += 2) Primitive("Well Post", PrimitiveType.Cylinder, new Vector3(side * 1.75f, 2f, 0f), new Vector3(0.13f, 2f, 0.13f), wood, well, true);
            var beam = Primitive("Well Beam", PrimitiveType.Cylinder, new Vector3(0f, 3.35f, 0f), new Vector3(0.13f, 1.9f, 0.13f), wood, well, false);
            beam.transform.localRotation = Quaternion.Euler(0f, 0f, 90f);
            Primitive("Well Lantern", PrimitiveType.Sphere, new Vector3(0f, 2.35f, 0f), Vector3.one * 0.23f, glow, well, false);
        }

        private void CreateSignpost(Vector3 position, Material wood, Material path)
        {
            var sign = new GameObject("Village Noticeboard").transform;
            sign.SetParent(_villageRoot, false);
            sign.localPosition = position;
            Primitive("Post", PrimitiveType.Cylinder, new Vector3(0f, 1.8f, 0f), new Vector3(0.14f, 1.8f, 0.14f), wood, sign, true);
            Primitive("Board", PrimitiveType.Cube, new Vector3(0f, 2.6f, 0f), new Vector3(2.25f, 1.25f, 0.17f), path, sign, true);
        }

        private void CreateLantern(Vector3 position, Material wood, Material glow)
        {
            var post = new GameObject("Road Lantern").transform;
            post.SetParent(_villageRoot, false);
            post.localPosition = position;
            Primitive("Lantern Post", PrimitiveType.Cylinder, new Vector3(0f, 2.15f, 0f), new Vector3(0.11f, 2.15f, 0.11f), wood, post, false);
            var lamp = Primitive("Lantern", PrimitiveType.Sphere, new Vector3(0f, 4.1f, 0f), Vector3.one * 0.27f, glow, post, false);
            var light = lamp.AddComponent<Light>();
            light.type = LightType.Point;
            light.range = 6f;
            light.intensity = 1.2f;
            light.color = new Color(1f, 0.67f, 0.27f);
        }

        private void CreateFence(Transform parent, Vector3 start, Vector3 end, Material material)
        {
            var direction = end - start;
            var length = direction.magnitude;
            var fence = new GameObject("Garden Fence").transform;
            fence.SetParent(parent, false);
            fence.localPosition = start;
            fence.localRotation = Quaternion.LookRotation(direction.normalized);
            Primitive("Fence Rail", PrimitiveType.Cube, new Vector3(0f, 0.75f, length * 0.5f), new Vector3(0.13f, 0.12f, length), material, fence, false);
            for (var z = 0f; z <= length; z += 1.25f) Primitive("Fence Post", PrimitiveType.Cylinder, new Vector3(0f, 0.78f, z), new Vector3(0.08f, 0.78f, 0.08f), material, fence, true);
        }

        private void CreateWorldInteraction(string name, Vector3 position, float radius, string prompt, string message)
        {
            var target = new GameObject(name).AddComponent<VillageWorldInteraction>();
            target.transform.SetParent(_villageRoot, false);
            target.transform.localPosition = position;
            target.interactionRadius = radius;
            target.prompt = prompt;
            target.message = message;
        }

        private void CreateGabledRoof(Transform parent, Vector3 position, float width, float depth, float height, Material material)
        {
            var roof = new GameObject("Gabled Roof");
            roof.transform.SetParent(parent, false);
            roof.transform.localPosition = position;
            var filter = roof.AddComponent<MeshFilter>();
            filter.sharedMesh = GabledRoofMesh(width, depth, height);
            roof.AddComponent<MeshRenderer>().sharedMaterial = material;
            roof.AddComponent<MeshCollider>().sharedMesh = filter.sharedMesh;
        }

        private void CreateCone(string name, Vector3 position, float radius, float height, int sides, Material material, Transform parent)
        {
            var cone = new GameObject(name);
            cone.transform.SetParent(parent, false);
            cone.transform.localPosition = position;
            var filter = cone.AddComponent<MeshFilter>();
            filter.sharedMesh = ConeMesh(radius, height, sides);
            cone.AddComponent<MeshRenderer>().sharedMaterial = material;
        }

        private GameObject Primitive(string name, PrimitiveType type, Vector3 position, Vector3 scale, Material material, Transform parent, bool keepCollider)
        {
            var instance = GameObject.CreatePrimitive(type);
            instance.name = name;
            instance.transform.SetParent(parent, false);
            instance.transform.localPosition = position;
            instance.transform.localScale = scale;
            instance.GetComponent<Renderer>().sharedMaterial = material;
            if (!keepCollider)
            {
                var collider = instance.GetComponent<Collider>();
                if (collider != null) Destroy(collider);
            }
            return instance;
        }

        private Material MaterialFor(string name, Color color, bool emission = false)
        {
            if (_materials.TryGetValue(name, out var material)) return material;
            var shader = Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard");
            material = new Material(shader) { name = name, color = color };
            if (material.HasProperty("_Smoothness")) material.SetFloat("_Smoothness", 0f);
            if (emission && material.HasProperty("_EmissionColor"))
            {
                material.EnableKeyword("_EMISSION");
                material.SetColor("_EmissionColor", color * 1.35f);
            }
            _materials.Add(name, material);
            return material;
        }

        private static Mesh GabledRoofMesh(float width, float depth, float height)
        {
            var w = width * 0.5f;
            var d = depth * 0.5f;
            var mesh = new Mesh { name = "Low Poly Gabled Roof" };
            mesh.vertices = new[]
            {
                new Vector3(-w, 0f, -d), new Vector3(w, 0f, -d), new Vector3(0f, height, -d),
                new Vector3(-w, 0f, d), new Vector3(w, 0f, d), new Vector3(0f, height, d),
            };
            mesh.triangles = new[] { 0, 2, 1, 3, 4, 5, 0, 3, 5, 0, 5, 2, 1, 2, 5, 1, 5, 4, 0, 1, 4, 0, 4, 3 };
            mesh.RecalculateNormals();
            return mesh;
        }

        private static Mesh ConeMesh(float radius, float height, int sides)
        {
            var vertices = new List<Vector3> { new(0f, height, 0f), Vector3.zero };
            for (var i = 0; i < sides; i++)
            {
                var angle = i / (float)sides * Mathf.PI * 2f;
                vertices.Add(new Vector3(Mathf.Cos(angle) * radius, 0f, Mathf.Sin(angle) * radius));
            }
            var triangles = new List<int>();
            for (var i = 0; i < sides; i++)
            {
                var next = (i + 1) % sides;
                triangles.AddRange(new[] { 0, i + 2, next + 2, 1, next + 2, i + 2 });
            }
            var mesh = new Mesh { name = "Low Poly Cone" };
            mesh.SetVertices(vertices);
            mesh.SetTriangles(triangles, 0);
            mesh.RecalculateNormals();
            return mesh;
        }
    }

    public abstract class VillageInteractable : MonoBehaviour
    {
        [HideInInspector] public float interactionRadius = 3f;
        [HideInInspector] public string prompt = "Interact";
        public bool IsInRange(Vector3 playerPosition) => Vector3.Distance(playerPosition, transform.position) <= interactionRadius;
        public abstract void Interact(VillageHud hud);
    }

    public sealed class VillageWorldInteraction : VillageInteractable
    {
        [HideInInspector] public string message = "";
        public override void Interact(VillageHud hud) => hud.ShowDialogue("Village", message);
    }

    public sealed class VillageNpcInteraction : VillageInteractable
    {
        private const string FallbackDialogue = "Welcome to Waystone. The river is kind today, but the north road has stories enough for a long evening.";
        private NpcMemoryNpc _liveNpc;
        private bool _busy;

        private void Awake()
        {
            interactionRadius = 3.1f;
            prompt = "Talk to Branwen, the Waystone Keeper";
        }

        public void Configure(bool enableLiveBridge, string serviceUrl, string agentId)
        {
            if (!enableLiveBridge) return;
            if (!Guid.TryParse(agentId, out _))
            {
                Debug.LogWarning("[village] Live NPC bridge is enabled but npcAgentId is not a UUID. Using local dialogue.", this);
                return;
            }
            _liveNpc = gameObject.AddComponent<NpcMemoryNpc>();
            _liveNpc.baseUrl = serviceUrl;
            _liveNpc.autoProvision = false;
            _liveNpc.agentIdOverride = agentId;
            _liveNpc.phaseTag = "village";
        }

        public override void Interact(VillageHud hud)
        {
            if (_busy) return;
            if (_liveNpc == null)
            {
                hud.ShowDialogue("Branwen", FallbackDialogue);
                return;
            }
            if (!_liveNpc.Ready)
            {
                hud.ShowDialogue("Branwen", "One moment, traveler. I am gathering my thoughts.");
                return;
            }
            StartDialogue(hud);
        }

        private async void StartDialogue(VillageHud hud)
        {
            _busy = true;
            hud.BeginDialogue("Branwen");
            try
            {
                await _liveNpc.SayStreamAsync("A traveler has approached you in the Waystone village. Offer a short in-character greeting and invite one question.", hud.AppendDialogue, () => hud.SetThinking(true));
                hud.SetThinking(false);
            }
            catch (Exception exception)
            {
                Debug.LogException(exception, this);
                hud.ShowDialogue("Branwen", FallbackDialogue + " (The village's memory service is resting.)");
            }
            finally { _busy = false; }
        }
    }

    [RequireComponent(typeof(CharacterController))]
    public sealed class VillagePlayerController : MonoBehaviour
    {
        [HideInInspector] public Transform cameraTransform;
        [HideInInspector] public VillageHud hud;
        private CharacterController _controller;
        private float _verticalVelocity;
        private float _pitch;
        private VillageInteractable _nearest;

        private void Awake() => _controller = GetComponent<CharacterController>();

        private void Start()
        {
            Cursor.lockState = CursorLockMode.Locked;
            Cursor.visible = false;
        }

        private void Update()
        {
            var keyboard = Keyboard.current;
            var mouse = Mouse.current;
            if (keyboard != null && keyboard.escapeKey.wasPressedThisFrame)
            {
                Cursor.lockState = CursorLockMode.None;
                Cursor.visible = true;
            }
            if (mouse != null && mouse.leftButton.wasPressedThisFrame && Cursor.lockState != CursorLockMode.Locked)
            {
                Cursor.lockState = CursorLockMode.Locked;
                Cursor.visible = false;
            }
            FindNearestInteractable();
            if (keyboard != null && keyboard.eKey.wasPressedThisFrame && _nearest != null) _nearest.Interact(hud);
            if (Cursor.lockState != CursorLockMode.Locked) return;

            var move = Vector3.zero;
            if (keyboard != null)
            {
                if (keyboard.wKey.isPressed) move += Vector3.forward;
                if (keyboard.sKey.isPressed) move += Vector3.back;
                if (keyboard.aKey.isPressed) move += Vector3.left;
                if (keyboard.dKey.isPressed) move += Vector3.right;
            }
            if (move.sqrMagnitude > 1f) move.Normalize();
            var speed = keyboard != null && keyboard.leftShiftKey.isPressed ? 7.2f : 4.6f;
            _verticalVelocity = _controller.isGrounded ? -1.3f : _verticalVelocity + Physics.gravity.y * Time.deltaTime;
            var worldMove = transform.TransformDirection(move) * speed;
            worldMove.y = _verticalVelocity;
            _controller.Move(worldMove * Time.deltaTime);
            if (mouse == null) return;
            var look = mouse.delta.ReadValue() * 0.08f;
            _pitch = Mathf.Clamp(_pitch - look.y, -76f, 76f);
            transform.Rotate(0f, look.x, 0f);
            cameraTransform.localRotation = Quaternion.Euler(_pitch, 0f, 0f);
        }

        private void FindNearestInteractable()
        {
            _nearest = null;
            var nearestDistance = float.MaxValue;
            foreach (var interactable in FindObjectsByType<VillageInteractable>(FindObjectsSortMode.None))
            {
                var distance = Vector3.Distance(transform.position, interactable.transform.position);
                if (distance > interactable.interactionRadius || distance >= nearestDistance) continue;
                _nearest = interactable;
                nearestDistance = distance;
            }
            hud.SetPrompt(_nearest == null ? "" : $"[E] {_nearest.prompt}");
        }
    }

    public sealed class VillageHud : MonoBehaviour
    {
        private string _prompt = "";
        private string _speaker = "";
        private string _dialogue = "";
        private bool _thinking;
        private float _visibleUntil;

        public void SetPrompt(string prompt) => _prompt = prompt;
        public void BeginDialogue(string speaker)
        {
            _speaker = speaker;
            _dialogue = "";
            _thinking = false;
            _visibleUntil = float.PositiveInfinity;
        }
        public void AppendDialogue(string chunk)
        {
            _dialogue += chunk;
            _visibleUntil = float.PositiveInfinity;
        }
        public void SetThinking(bool value) => _thinking = value;
        public void ShowDialogue(string speaker, string dialogue)
        {
            _speaker = speaker;
            _dialogue = dialogue;
            _thinking = false;
            _visibleUntil = Time.time + 8f;
        }

        private void OnGUI()
        {
            var helpStyle = new GUIStyle(GUI.skin.label) { fontSize = 15, normal = { textColor = new Color(0.95f, 0.92f, 0.78f) } };
            GUI.Label(new Rect(18f, 16f, 420f, 28f), "WAYSTONE VILLAGE", helpStyle);
            GUI.Label(new Rect(18f, 40f, 520f, 28f), "WASD move  •  mouse look  •  E interact  •  Shift sprint", helpStyle);
            if (!string.IsNullOrEmpty(_prompt))
            {
                var promptStyle = new GUIStyle(helpStyle) { alignment = TextAnchor.MiddleCenter, fontSize = 17 };
                GUI.Box(new Rect(Screen.width * 0.5f - 180f, Screen.height - 95f, 360f, 42f), GUIContent.none);
                GUI.Label(new Rect(Screen.width * 0.5f - 175f, Screen.height - 88f, 350f, 28f), _prompt, promptStyle);
            }
            if (!string.IsNullOrEmpty(_dialogue) && Time.time <= _visibleUntil)
            {
                var panel = new Rect(28f, Screen.height - 244f, Mathf.Min(610f, Screen.width - 56f), 125f);
                GUI.Box(panel, GUIContent.none);
                var titleStyle = new GUIStyle(helpStyle) { fontSize = 18, fontStyle = FontStyle.Bold };
                var bodyStyle = new GUIStyle(helpStyle) { wordWrap = true, fontSize = 16 };
                GUI.Label(new Rect(panel.x + 16f, panel.y + 12f, panel.width - 32f, 25f), _speaker, titleStyle);
                GUI.Label(new Rect(panel.x + 16f, panel.y + 42f, panel.width - 32f, 70f), _dialogue + (_thinking ? "\n(thinking…)" : ""), bodyStyle);
            }
            var crosshairStyle = new GUIStyle(helpStyle) { alignment = TextAnchor.MiddleCenter, fontSize = 22 };
            GUI.Label(new Rect(Screen.width * 0.5f - 12f, Screen.height * 0.5f - 15f, 24f, 30f), "+", crosshairStyle);
        }
    }
}
