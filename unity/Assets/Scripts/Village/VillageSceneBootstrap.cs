using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.InputSystem;

namespace Twicetold.Village
{
    /// <summary>Builds a standalone, presentation-ready low-poly riverside village.</summary>
    public sealed class VillageSceneBootstrap : MonoBehaviour
    {
        [Header("Village")]
        public bool buildOnStart = true;

        private readonly Dictionary<string, Material> _materials = new();
        private readonly Dictionary<int, Mesh> _cylinderMeshes = new();
        private Transform _villageRoot;
        private Transform _riversideHome;
        private Transform _market;
        private Transform _eventBench;
        private Mesh _polySphereMesh;

        private enum VillagerStyle
        {
            Merchant,
            Homeowner,
            Fisherman,
            Baker,
            Worker,
        }

        private static readonly Vector3[] MainRoad =
        {
            new(0f, 0f, -49f), new(-1.5f, 0f, -36f), new(1.2f, 0f, -25f),
            new(-1.2f, 0f, -13f), new(1.4f, 0f, -1f), new(-0.8f, 0f, 12f),
            new(2.2f, 0f, 25f), new(0.5f, 0f, 38f), new(4f, 0f, 49f),
        };

        private static readonly Vector3[] HouseSites =
        {
            new(-16f, 0f, -20f), new(-15f, 0f, 7f), new(16f, 0f, 17f),
            new(17f, 0f, -16f), new(-11f, 0f, 31f), new(16f, 0f, 39f),
        };

        private void Awake()
        {
            Application.runInBackground = true;
            QualitySettings.antiAliasing = 4;
            QualitySettings.shadows = ShadowQuality.All;
            QualitySettings.shadowResolution = ShadowResolution.High;
            QualitySettings.shadowDistance = 95f;
            QualitySettings.shadowCascades = 4;
            if (buildOnStart) BuildVillage();
        }

        private void BuildVillage()
        {
            if (transform.Find("Generated Village") != null) return;
            _villageRoot = new GameObject("Generated Village").transform;
            _villageRoot.SetParent(transform, false);

            BuildLighting();
            BuildTerrainAndRiver();
            BuildRoads();
            BuildHomes();
            BuildMarketSquare();
            BuildRiverfront();
            BuildVegetation();
            BuildVillageDressing();
            BuildPlayer();
            BuildVillagersAndEvent();
        }

        private void BuildLighting()
        {
            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(0.61f, 0.76f, 0.91f);
            RenderSettings.ambientEquatorColor = new Color(0.60f, 0.68f, 0.57f);
            RenderSettings.ambientGroundColor = new Color(0.37f, 0.42f, 0.30f);
            RenderSettings.ambientIntensity = 1.18f;
            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.Linear;
            RenderSettings.fogColor = new Color(0.64f, 0.77f, 0.88f);
            RenderSettings.fogStartDistance = 85f;
            RenderSettings.fogEndDistance = 190f;

            var sun = new GameObject("Late Morning Sun").AddComponent<Light>();
            sun.transform.SetParent(_villageRoot, false);
            sun.type = LightType.Directional;
            sun.color = new Color(1f, 0.92f, 0.77f);
            sun.intensity = 1.18f;
            sun.shadows = LightShadows.Soft;
            sun.shadowStrength = 0.58f;
            sun.transform.rotation = Quaternion.Euler(46f, -38f, 0f);
            RenderSettings.sun = sun;

            var skyShader = Shader.Find("Skybox/Procedural");
            if (skyShader != null)
            {
                var sky = new Material(skyShader) { name = "Riverside Valley Sky" };
                sky.SetColor("_SkyTint", new Color(0.43f, 0.68f, 0.92f));
                sky.SetColor("_GroundColor", new Color(0.46f, 0.55f, 0.39f));
                sky.SetFloat("_AtmosphereThickness", 0.78f);
                sky.SetFloat("_SunSize", 0.035f);
                sky.SetFloat("_SunSizeConvergence", 4.5f);
                sky.SetFloat("_Exposure", 1.15f);
                RenderSettings.skybox = sky;
                _materials.Add("Riverside Valley Sky", sky);
            }
        }

        private void BuildTerrainAndRiver()
        {
            var distantMeadow = MaterialFor("Distant Meadow", new Color(0.28f, 0.50f, 0.23f), 0f);
            var distantFloor = Primitive("Distant Valley Floor", PrimitiveType.Cube, new Vector3(0f, -1.45f, 8f), new Vector3(290f, 1.5f, 290f), distantMeadow, _villageRoot, false);
            distantFloor.GetComponent<Renderer>().shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            distantFloor.GetComponent<Renderer>().receiveShadows = false;

            var meadow = MaterialFor("Meadow", new Color(0.36f, 0.64f, 0.24f), 0.03f);
            CreateMeshObject("Rolling Meadow", TerrainMesh(112f, 108f, 28, 27), Vector3.zero, Vector3.one, meadow, _villageRoot, true);

            var riverPoints = RiverPoints();
            var sand = MaterialFor("Warm River Sand", new Color(0.77f, 0.67f, 0.43f), 0.05f);
            CreateRibbon("River Sandbanks", riverPoints, 22f, -0.43f, sand, false, false);
            var water = MaterialFor("Clear River Water", new Color(0.13f, 0.48f, 0.71f, 0.86f), 0.82f, false, true);
            var river = CreateRibbon("Moving River", riverPoints, 16.5f, -0.38f, water, false, false);
            river.AddComponent<RiverSurfaceAnimator>().amplitude = 0.045f;

            var rock = MaterialFor("Mountain Slate", new Color(0.33f, 0.42f, 0.52f), 0.04f);
            var rockLight = MaterialFor("Mountain Sun Faces", new Color(0.47f, 0.56f, 0.64f), 0.04f);
            CreateMountainRange(new Vector3(-25f, 0f, 66f), 28f, 32f, rock, rockLight, 171);
            CreateMountainRange(new Vector3(-58f, 0f, 37f), 22f, 23f, rock, rockLight, 314);
            CreateMountainRange(new Vector3(64f, -0.2f, 40f), 21f, 29f, rock, rockLight, 903);
            var farGrass = MaterialFor("Far Hills", new Color(0.25f, 0.48f, 0.25f), 0f);
            CreateMountainRange(new Vector3(17f, -1f, 72f), 26f, 14f, farGrass, farGrass, 554);

            CreateHorizonBand("Distant Mountain Horizon", 165f, -24f, 28f, 27f, 56, 0.55f,
                UnlitMaterialFor("Distant Mountain Horizon", new Color(0.34f, 0.45f, 0.57f)));
            CreateHorizonBand("Distant Valley Rim", 112f, -8f, 7f, 8f, 48, 1.7f,
                UnlitMaterialFor("Distant Valley Rim", new Color(0.22f, 0.42f, 0.24f)));
        }

        private void BuildRoads()
        {
            var road = MaterialFor("Sunlit Packed Earth", new Color(0.84f, 0.72f, 0.48f), 0.02f);
            var lane = MaterialFor("Garden Lane", new Color(0.77f, 0.65f, 0.42f), 0.02f);
            CreateRibbon("Main Village Road", MainRoad, 5.7f, 0.09f, road, true, false);
            CreateRibbon("Miller Cottage Lane", new[] { new Vector3(0f, 0f, -24f), new Vector3(-8f, 0f, -22f), new Vector3(-15f, 0f, -23f) }, 3.2f, 0.075f, lane, true, false);
            CreateRibbon("East Cottage Lane", new[] { new Vector3(0f, 0f, -10f), new Vector3(9f, 0f, -12f), new Vector3(16f, 0f, -18f) }, 3.1f, 0.075f, lane, true, false);
            CreateRibbon("Inn Lane", new[] { new Vector3(0f, 0f, 5f), new Vector3(-8f, 0f, 5f), new Vector3(-14f, 0f, 4f) }, 3.5f, 0.075f, lane, true, false);
            CreateRibbon("River House Lane", new[] { new Vector3(0f, 0f, 17f), new Vector3(8f, 0f, 18f), new Vector3(15f, 0f, 15f) }, 3.1f, 0.075f, lane, true, false);
            CreateRibbon("North Homes Lane", new[] { new Vector3(1f, 0f, 33f), new Vector3(-5f, 0f, 34f), new Vector3(-11f, 0f, 29f) }, 3.1f, 0.075f, lane, true, false);

            var pebble = MaterialFor("Road Pebbles", new Color(0.48f, 0.48f, 0.42f), 0.03f);
            var random = new System.Random(207);
            for (var i = 0; i < 44; i++)
            {
                var z = -43f + i * 2f;
                var center = RoadCenterAt(z);
                var x = center + (i % 2 == 0 ? -3.1f : 3.1f) + ((float)random.NextDouble() - 0.5f) * 1.3f;
                CreateRock("Roadside Pebble", new Vector3(x, TerrainHeight(x, z) + 0.12f, z), new Vector3(0.22f, 0.11f, 0.34f) * (0.7f + (float)random.NextDouble() * 0.65f), pebble, false, i * 29f);
            }
        }

        private void BuildHomes()
        {
            CreateHouse("Ochre Roof Cottage", HouseSites[0], 1.08f, new Color(0.77f, 0.68f, 0.51f), new Color(0.78f, 0.49f, 0.14f), 0);
            CreateHouse("Village Inn", HouseSites[1], 1.42f, new Color(0.72f, 0.59f, 0.42f), new Color(0.88f, 0.61f, 0.16f), 1);
            _riversideHome = CreateHouse("Riverside Home", HouseSites[2], 1.08f, new Color(0.70f, 0.64f, 0.50f), new Color(0.42f, 0.26f, 0.15f), 2);
            CreateHouse("Green Roof Cottage", HouseSites[3], 1.04f, new Color(0.78f, 0.70f, 0.54f), new Color(0.39f, 0.51f, 0.18f), 3);
            CreateHouse("North Lane House", HouseSites[4], 0.98f, new Color(0.81f, 0.71f, 0.52f), new Color(0.64f, 0.39f, 0.13f), 4);
            CreateHouse("Riverwatch Cottage", HouseSites[5], 0.92f, new Color(0.74f, 0.66f, 0.50f), new Color(0.56f, 0.33f, 0.14f), 5);
        }

        private void BuildMarketSquare()
        {
            var wood = MaterialFor("Dark Oak", new Color(0.22f, 0.13f, 0.07f), 0.08f);
            var woodLight = MaterialFor("Sunlit Oak", new Color(0.45f, 0.27f, 0.11f), 0.07f);
            var canvasA = MaterialFor("Sage Market Canvas", new Color(0.60f, 0.68f, 0.39f), 0.03f);
            var canvasB = MaterialFor("Cream Market Canvas", new Color(0.84f, 0.75f, 0.52f), 0.03f);
            var crate = MaterialFor("Market Crates", new Color(0.49f, 0.31f, 0.13f), 0.04f);
            _market = new GameObject("Riverside Market Square").transform;
            _market.SetParent(_villageRoot, false);
            _market.localPosition = new Vector3(19f, TerrainHeight(19f, 3f), 3f);
            _market.localRotation = RotationFacingRoad(_market.localPosition);
            CreateMarketStall("Produce Stall", new Vector3(0f, 0f, 0f), 0f, canvasA, wood, crate, _market);
            CreateMarketStall("Dry Goods Stall", new Vector3(-0.5f, 0f, 6.2f), 12f, canvasB, wood, crate, _market);

            var red = MaterialFor("Red Produce", new Color(0.66f, 0.16f, 0.10f), 0.08f);
            var gold = MaterialFor("Golden Produce", new Color(0.90f, 0.57f, 0.13f), 0.08f);
            var green = MaterialFor("Green Produce", new Color(0.31f, 0.55f, 0.17f), 0.08f);
            for (var i = 0; i < 15; i++)
            {
                var row = i / 5;
                var column = i % 5;
                var material = i % 3 == 0 ? red : i % 3 == 1 ? gold : green;
                CreatePolyObject("Market Produce", new Vector3(-2f + column, 1.46f, -0.45f + row * 0.43f), Vector3.one * 0.24f, material, _market, false, i * 37f);
            }
            CreateBarrel(new Vector3(4.1f, 0.7f, 1.5f), 0.75f, _market);
            CreateCrateStack(new Vector3(-4.2f, 0f, 4.7f), _market, woodLight);
        }

        private void BuildRiverfront()
        {
            var wood = MaterialFor("Weathered Dock Wood", new Color(0.37f, 0.23f, 0.11f), 0.06f);
            var rope = MaterialFor("Hemp Rope", new Color(0.55f, 0.43f, 0.24f), 0.12f);
            var riverBlue = MaterialFor("Boat Paint", new Color(0.16f, 0.34f, 0.42f), 0.16f);
            var dock = new GameObject("River Dock").transform;
            dock.SetParent(_villageRoot, false);
            dock.localPosition = new Vector3(34f, TerrainHeight(34f, -7f) + 0.12f, -7f);
            for (var i = 0; i < 9; i++) Primitive("Dock Plank", PrimitiveType.Cube, new Vector3(i * 0.85f, 0.18f + i * -0.025f, 0f), new Vector3(0.78f, 0.18f, 3.1f), wood, dock, true);
            for (var i = 0; i < 4; i++)
            {
                var x = i < 2 ? 0f : 6.8f;
                var z = i % 2 == 0 ? -1.35f : 1.35f;
                CreateCylinder("Dock Post", new Vector3(x, -0.25f, z), new Vector3(0.18f, 1.45f, 0.18f), wood, dock, true, 8);
            }
            CreateRowboat(new Vector3(42f, -0.24f, -5.2f), -7f, riverBlue, wood);
            CreateCylinder("Mooring Rope", new Vector3(38.7f, -0.08f, -5.9f), new Vector3(0.045f, 2.5f, 0.045f), rope, _villageRoot, false, 6, Quaternion.Euler(0f, 0f, 79f));
            BuildBridge(new Vector3(RiverCenter(23f), 0f, 23f), wood);
        }

        private void BuildVegetation()
        {
            var random = new System.Random(117);
            for (var i = 0; i < 72; i++)
            {
                var x = (float)(random.NextDouble() * 101d - 50.5d);
                var z = (float)(random.NextDouble() * 99d - 49.5d);
                if (!TreePlacementIsClear(x, z)) continue;
                var scale = 0.76f + (float)random.NextDouble() * 0.72f;
                if (i % 5 == 0) CreatePine(new Vector3(x, TerrainHeight(x, z), z), scale);
                else CreateBroadleafTree(new Vector3(x, TerrainHeight(x, z), z), scale, i);
            }

            var featureTrees = new[]
            {
                new Vector3(-6.5f, 0f, -6f), new Vector3(-27f, 0f, -2f), new Vector3(-25f, 0f, 17f),
                new Vector3(27f, 0f, -7f), new Vector3(-25f, 0f, -35f), new Vector3(24f, 0f, 31f),
            };
            for (var i = 0; i < featureTrees.Length; i++)
            {
                var point = featureTrees[i];
                point.y = TerrainHeight(point.x, point.z);
                CreateBroadleafTree(point, 1.04f + i % 2 * 0.16f, 100 + i);
            }

            var hedgeDark = MaterialFor("Hedge Dark", new Color(0.16f, 0.39f, 0.14f), 0.02f);
            var hedgeLight = MaterialFor("Hedge Light", new Color(0.29f, 0.54f, 0.18f), 0.02f);
            foreach (var houseSite in HouseSites)
            {
                for (var i = -2; i <= 2; i++)
                {
                    var point = houseSite + new Vector3(i * 1.4f, 0f, -5.3f);
                    point.y = TerrainHeight(point.x, point.z) + 0.48f;
                    CreatePolyObject("Garden Hedge", point, new Vector3(0.86f, 0.68f, 0.75f), i % 2 == 0 ? hedgeLight : hedgeDark, _villageRoot, false, i * 29f);
                }
            }
            BuildGrassAndFlowers(random);
        }

        private void BuildVillageDressing()
        {
            var wood = MaterialFor("Dark Oak", new Color(0.22f, 0.13f, 0.07f), 0.08f);
            var warmWood = MaterialFor("Sunlit Oak", new Color(0.45f, 0.27f, 0.11f), 0.07f);
            var straw = MaterialFor("Dry Straw", new Color(0.82f, 0.64f, 0.25f), 0.02f);
            var glow = MaterialFor("Lantern Glass", new Color(1f, 0.68f, 0.23f), 0.35f, true);
            CreateLantern(new Vector3(3f, TerrainHeight(3f, -29f), -29f), wood, glow);
            CreateLantern(new Vector3(-3.5f, TerrainHeight(-3.5f, -4f), -4f), wood, glow);
            CreateLantern(new Vector3(3.7f, TerrainHeight(3.7f, 20f), 20f), wood, glow);
            CreateLantern(new Vector3(-2.8f, TerrainHeight(-2.8f, 39f), 39f), wood, glow);
            CreateBench(new Vector3(-5.6f, TerrainHeight(-5.6f, 13f), 13f), warmWood);
            _eventBench = CreateBench(new Vector3(7.4f, TerrainHeight(7.4f, 7.6f), 7.6f), warmWood);
            CreateCart(new Vector3(18f, TerrainHeight(18f, -31f), -31f), 18f, warmWood, wood);
            CreateHaystack(new Vector3(-23f, TerrainHeight(-23f, -16f), -16f), 1.15f, straw);
            CreateHaystack(new Vector3(-21f, TerrainHeight(-21f, -13.5f), -13.5f), 0.82f, straw);
            CreateCrateStack(new Vector3(26f, TerrainHeight(26f, 12f), 12f), _villageRoot, warmWood);
            CreateBarrel(new Vector3(-21f, TerrainHeight(-21f, 6f) + 0.65f, 6f), 0.72f, _villageRoot);
            CreateBarrel(new Vector3(-22.3f, TerrainHeight(-22.3f, 7.2f) + 0.58f, 7.2f), 0.62f, _villageRoot);

            var stone = MaterialFor("Village Stone", new Color(0.43f, 0.46f, 0.43f), 0.04f);
            foreach (var point in new[]
                     {
                         new Vector3(-30f, 0f, -7f), new Vector3(27f, 0f, 28f), new Vector3(-33f, 0f, 34f),
                         new Vector3(30f, 0f, -35f), new Vector3(-30f, 0f, -40f),
                     })
                CreateRockCluster(point, stone);
        }

        private void BuildPlayer()
        {
            var player = new GameObject("Village Explorer");
            player.transform.SetParent(_villageRoot, false);
            player.transform.localPosition = new Vector3(0f, TerrainHeight(0f, -45f) + 0.15f, -45f);
            var controller = player.AddComponent<CharacterController>();
            controller.height = 1.86f;
            controller.radius = 0.34f;
            controller.center = new Vector3(0f, 0.93f, 0f);
            controller.stepOffset = 0.38f;
            controller.slopeLimit = 48f;

            var cameraObject = new GameObject("Explorer Camera");
            cameraObject.transform.SetParent(player.transform, false);
            cameraObject.transform.localPosition = new Vector3(0f, 1.68f, 0f);
            var camera = cameraObject.AddComponent<Camera>();
            camera.fieldOfView = 64f;
            camera.nearClipPlane = 0.06f;
            camera.farClipPlane = 220f;
            camera.allowHDR = true;
            camera.allowMSAA = true;
            camera.clearFlags = CameraClearFlags.Skybox;
            camera.backgroundColor = new Color(0.56f, 0.75f, 0.92f);
            cameraObject.AddComponent<AudioListener>();
            var movement = player.AddComponent<VillagePlayerController>();
            movement.cameraTransform = cameraObject.transform;
            movement.playerCamera = camera;
            player.AddComponent<VillageHud>();
            var dialogue = player.AddComponent<VillageDialogueInteractor>();
            dialogue.playerCamera = camera;
        }

        private void BuildVillagersAndEvent()
        {
            var henryPosition = _market.TransformPoint(new Vector3(0f, 0f, 2.18f));
            var henry = CreateVillager(
                "NPC Henry — Market Merchant", "henry", "Henry", "produce merchant", true, true,
                henryPosition, _market.rotation, new Color(0.22f, 0.42f, 0.20f), new Color(0.30f, 0.20f, 0.12f),
                new Color(0.78f, 0.55f, 0.18f), new Color(0.22f, 0.12f, 0.07f), VillagerStyle.Merchant);

            var joanPosition = _riversideHome.TransformPoint(new Vector3(1.22f, 0.62f, -3.55f));
            var joan = CreateVillager(
                "NPC Joan — Riverside Resident", "joan", "Joan", "riverside resident", true, true,
                joanPosition, _riversideHome.rotation, new Color(0.25f, 0.39f, 0.62f), new Color(0.20f, 0.29f, 0.48f),
                new Color(0.83f, 0.72f, 0.52f), new Color(0.43f, 0.20f, 0.10f), VillagerStyle.Homeowner);

            var approachRoute = new[]
            {
                GroundPoint(RoadCenterAt(-17f) + 0.45f, -17f),
                GroundPoint(RoadCenterAt(-9f) + 0.25f, -9f),
                GroundPoint(RoadCenterAt(1f) + 0.55f, 1f),
                GroundPoint(3.7f, 5.2f),
                GroundPoint(6.8f, 7.25f),
            };
            var fishermanFacing = Quaternion.LookRotation(-(approachRoute[1] - approachRoute[0]).normalized, Vector3.up);
            var fisherman = CreateVillager(
                "NPC Fisherman — Gold Event Actor", "fisherman", "Fisherman", "river fisherman", false, false,
                approachRoute[0], fishermanFacing, new Color(0.16f, 0.43f, 0.46f), new Color(0.29f, 0.30f, 0.24f),
                new Color(0.58f, 0.43f, 0.21f), new Color(0.29f, 0.20f, 0.13f), VillagerStyle.Fisherman);
            CreateFishingGear(fisherman);
            var goldBag = CreateGoldBag(fisherman.LeftHand, out var coinSpill);

            var maraRoute = new[]
            {
                GroundPoint(-22f, 3.5f), GroundPoint(-16.5f, 4.8f),
                GroundPoint(-9.5f, 5.1f), GroundPoint(-15f, 1.5f),
            };
            var mara = CreateVillager(
                "NPC Mara — Baker", "mara", "Mara", "village baker", false, false,
                maraRoute[0], Quaternion.LookRotation(-(maraRoute[1] - maraRoute[0]).normalized),
                new Color(0.63f, 0.28f, 0.19f), new Color(0.46f, 0.19f, 0.16f),
                new Color(0.88f, 0.76f, 0.56f), new Color(0.18f, 0.12f, 0.07f), VillagerStyle.Baker);
            var maraWalker = mara.gameObject.AddComponent<VillageAmbientWalker>();
            maraWalker.Configure(mara.Motion, maraRoute, 1.05f, 2.2f);

            var rowanRoute = new[]
            {
                GroundPoint(-3f, 29f), GroundPoint(-9.5f, 31f),
                GroundPoint(-8f, 38f), GroundPoint(0.5f, 37f),
            };
            var rowan = CreateVillager(
                "NPC Rowan — Woodworker", "rowan", "Rowan", "village woodworker", false, false,
                rowanRoute[0], Quaternion.LookRotation(-(rowanRoute[1] - rowanRoute[0]).normalized),
                new Color(0.54f, 0.43f, 0.25f), new Color(0.25f, 0.35f, 0.18f),
                new Color(0.39f, 0.27f, 0.14f), new Color(0.12f, 0.08f, 0.05f), VillagerStyle.Worker);
            var rowanWalker = rowan.gameObject.AddComponent<VillageAmbientWalker>();
            rowanWalker.Configure(rowan.Motion, rowanRoute, 0.92f, 3f);

            var exitRoute = new[]
            {
                GroundPoint(7.4f, 7.6f), GroundPoint(3.2f, 10.4f),
                GroundPoint(RoadCenterAt(15f), 15f), GroundPoint(RoadCenterAt(25f), 25f),
                GroundPoint(RoadCenterAt(35f), 35f),
            };
            var eventObject = new GameObject("EVENT — Forgotten Gold at the Market Bench");
            eventObject.transform.SetParent(_villageRoot, false);
            var director = eventObject.AddComponent<VillageGoldEventDirector>();
            director.Configure(fisherman, henry, joan, _eventBench, goldBag, coinSpill, approachRoute, exitRoute);
        }

        private VillageNpcAnchor CreateVillager(
            string objectName,
            string stableId,
            string displayName,
            string role,
            bool demoFocus,
            bool dialogueEnabled,
            Vector3 position,
            Quaternion rotation,
            Color tunicColor,
            Color lowerColor,
            Color accentColor,
            Color hairColor,
            VillagerStyle style)
        {
            var root = new GameObject(objectName);
            root.transform.SetParent(_villageRoot, false);
            root.transform.position = position;
            root.transform.rotation = rotation;

            var collider = root.AddComponent<CapsuleCollider>();
            collider.radius = 0.38f;
            collider.height = 2.08f;
            collider.center = new Vector3(0f, 1.04f, 0f);
            var body = root.AddComponent<Rigidbody>();
            body.isKinematic = true;
            body.useGravity = false;
            body.interpolation = RigidbodyInterpolation.Interpolate;

            var visual = new GameObject("Animated Low-Poly Body").transform;
            visual.SetParent(root.transform, false);
            var attachmentPoint = new GameObject("Backend Attachment Point [" + stableId + "]").transform;
            attachmentPoint.SetParent(root.transform, false);
            attachmentPoint.localPosition = new Vector3(0f, 1.35f, 0.18f);

            var skin = MaterialFor("Villager Skin", new Color(0.72f, 0.50f, 0.34f), 0.04f);
            var tunic = MaterialFor(displayName + " Tunic", tunicColor, 0.025f);
            var lower = MaterialFor(displayName + " Lower Clothing", lowerColor, 0.02f);
            var accent = MaterialFor(displayName + " Accent", accentColor, 0.03f);
            var hair = MaterialFor(displayName + " Hair", hairColor, 0.02f);
            var boot = MaterialFor("Villager Boots", new Color(0.17f, 0.105f, 0.055f), 0.05f);
            var eye = MaterialFor("Villager Eyes", new Color(0.06f, 0.055f, 0.045f), 0.12f);

            var leftLeg = new GameObject("Left Leg Pivot").transform;
            leftLeg.SetParent(visual, false);
            leftLeg.localPosition = new Vector3(-0.20f, 0.91f, 0f);
            var rightLeg = new GameObject("Right Leg Pivot").transform;
            rightLeg.SetParent(visual, false);
            rightLeg.localPosition = new Vector3(0.20f, 0.91f, 0f);
            Primitive("Left Trouser Leg", PrimitiveType.Cube, new Vector3(0f, -0.40f, 0f), new Vector3(0.27f, 0.80f, 0.29f), lower, leftLeg, false);
            Primitive("Right Trouser Leg", PrimitiveType.Cube, new Vector3(0f, -0.40f, 0f), new Vector3(0.27f, 0.80f, 0.29f), lower, rightLeg, false);
            Primitive("Left Boot", PrimitiveType.Cube, new Vector3(0f, -0.83f, -0.07f), new Vector3(0.30f, 0.18f, 0.42f), boot, leftLeg, false);
            Primitive("Right Boot", PrimitiveType.Cube, new Vector3(0f, -0.83f, -0.07f), new Vector3(0.30f, 0.18f, 0.42f), boot, rightLeg, false);

            var wearsSkirt = style == VillagerStyle.Homeowner || style == VillagerStyle.Baker;
            if (wearsSkirt) CreateCone("Low-Poly Skirt", new Vector3(0f, 0.73f, 0f), 0.53f, 0.92f, 10, lower, visual);
            Primitive("Tunic", PrimitiveType.Cube, new Vector3(0f, 1.28f, 0f), new Vector3(0.82f, 0.88f, 0.47f), tunic, visual, false);
            Primitive("Belt", PrimitiveType.Cube, new Vector3(0f, 0.94f, -0.01f), new Vector3(0.88f, 0.12f, 0.51f), accent, visual, false);

            if (style == VillagerStyle.Merchant || style == VillagerStyle.Homeowner || style == VillagerStyle.Baker)
            {
                Primitive("Work Apron", PrimitiveType.Cube, new Vector3(0f, 1.17f, -0.255f), new Vector3(0.58f, 0.72f, 0.055f), accent, visual, false);
                Primitive("Apron Tie", PrimitiveType.Cube, new Vector3(0f, 1.48f, -0.285f), new Vector3(0.72f, 0.09f, 0.06f), accent, visual, false);
            }

            var leftArm = CreateArm("Left", -0.54f, skin, tunic, visual);
            var rightArm = CreateArm("Right", 0.54f, skin, tunic, visual);
            var leftHand = leftArm.Find("Left Hand Grip");
            var rightHand = rightArm.Find("Right Hand Grip");

            var headPivot = new GameObject("Head Pivot").transform;
            headPivot.SetParent(visual, false);
            headPivot.localPosition = new Vector3(0f, 1.92f, 0f);
            CreatePolyObject("Head", Vector3.zero, new Vector3(0.34f, 0.38f, 0.33f), skin, headPivot, false, 0f);
            CreatePolyObject("Nose", new Vector3(0f, -0.01f, -0.325f), new Vector3(0.075f, 0.09f, 0.08f), skin, headPivot, false, 0f);
            foreach (var x in new[] { -0.12f, 0.12f }) CreatePolyObject("Eye", new Vector3(x, 0.07f, -0.315f), Vector3.one * 0.035f, eye, headPivot, false, 0f);
            CreatePolyObject("Hair", new Vector3(0f, 0.20f, 0.035f), new Vector3(0.36f, 0.21f, 0.34f), hair, headPivot, false, 17f);

            if (style == VillagerStyle.Homeowner)
            {
                CreatePolyObject("Hair Bun", new Vector3(0f, 0.12f, 0.33f), Vector3.one * 0.19f, hair, headPivot, false, 41f);
                Primitive("Shoulder Shawl", PrimitiveType.Cube, new Vector3(0f, 1.55f, 0.02f), new Vector3(1.08f, 0.20f, 0.52f), accent, visual, false);
            }
            else if (style == VillagerStyle.Baker)
            {
                CreateCone("Baker Head Scarf", new Vector3(0f, 0.21f, 0f), 0.39f, 0.30f, 9, accent, headPivot);
            }
            else
            {
                Primitive("Cap Brim", PrimitiveType.Cube, new Vector3(0f, 0.25f, -0.13f), new Vector3(0.62f, 0.07f, 0.46f), accent, headPivot, false);
                CreateCylinder("Cap Crown", new Vector3(0f, 0.36f, 0.01f), new Vector3(0.31f, 0.13f, 0.31f), accent, headPivot, false, 9);
            }

            if (style == VillagerStyle.Fisherman)
            {
                CreatePolyObject("Short Beard", new Vector3(0f, -0.20f, -0.275f), new Vector3(0.24f, 0.18f, 0.10f), hair, headPivot, false, 9f);
            }

            var motion = root.AddComponent<VillageNpcMotion>();
            motion.Configure(visual, headPivot, leftArm, rightArm, leftLeg, rightLeg);
            var anchor = root.AddComponent<VillageNpcAnchor>();
            anchor.Configure(stableId, displayName, role, demoFocus, dialogueEnabled, attachmentPoint, leftHand, rightHand, motion);
            return anchor;
        }

        private Transform CreateArm(string sideName, float x, Material skin, Material sleeve, Transform parent)
        {
            var arm = new GameObject(sideName + " Arm Pivot").transform;
            arm.SetParent(parent, false);
            arm.localPosition = new Vector3(x, 1.58f, 0f);
            Primitive(sideName + " Sleeve", PrimitiveType.Cube, new Vector3(0f, -0.22f, 0f), new Vector3(0.25f, 0.48f, 0.28f), sleeve, arm, false);
            Primitive(sideName + " Forearm", PrimitiveType.Cube, new Vector3(0f, -0.59f, 0f), new Vector3(0.20f, 0.42f, 0.22f), skin, arm, false);
            var hand = new GameObject(sideName + " Hand Grip").transform;
            hand.SetParent(arm, false);
            hand.localPosition = new Vector3(0f, -0.84f, 0f);
            CreatePolyObject(sideName + " Hand", Vector3.zero, Vector3.one * 0.14f, skin, hand, false, 0f);
            return arm;
        }

        private void CreateFishingGear(VillageNpcAnchor fisherman)
        {
            var rod = MaterialFor("Fishing Rod", new Color(0.28f, 0.16f, 0.07f), 0.04f);
            var line = MaterialFor("Fishing Line", new Color(0.72f, 0.76f, 0.68f), 0.16f);
            var tackle = MaterialFor("Tackle Box", new Color(0.39f, 0.24f, 0.10f), 0.06f);
            var metal = MaterialFor("Tackle Metal", new Color(0.22f, 0.24f, 0.22f), 0.42f);
            CreateCylinder("Fishing Rod", new Vector3(0f, 0.92f, 0f), new Vector3(0.035f, 1.28f, 0.035f), rod, fisherman.RightHand, false, 8, Quaternion.Euler(0f, 0f, -8f));
            Primitive("Fishing Line", PrimitiveType.Cube, new Vector3(-0.10f, 1.82f, -0.46f), new Vector3(0.012f, 1.05f, 0.012f), line, fisherman.RightHand, false, Quaternion.Euler(24f, 0f, 0f));
            Primitive("Tackle Box", PrimitiveType.Cube, new Vector3(0f, 0.72f, 0.43f), new Vector3(0.72f, 0.52f, 0.34f), tackle, fisherman.transform, false);
            Primitive("Tackle Latch", PrimitiveType.Cube, new Vector3(0f, 0.76f, 0.245f), new Vector3(0.15f, 0.14f, 0.035f), metal, fisherman.transform, false);
        }

        private Transform CreateGoldBag(Transform parent, out GameObject coinSpill)
        {
            var bagCloth = MaterialFor("Gold Bag Cloth", new Color(0.62f, 0.39f, 0.10f), 0.04f);
            var tie = MaterialFor("Gold Bag Tie", new Color(0.27f, 0.15f, 0.06f), 0.05f);
            var gold = MaterialFor("Gold Coins", new Color(1f, 0.66f, 0.08f), 0.58f, true);
            var bag = new GameObject("Forgotten Gold Coin Bag").transform;
            bag.SetParent(parent, false);
            CreatePolyObject("Coin Bag", Vector3.zero, new Vector3(0.38f, 0.44f, 0.31f), bagCloth, bag, false, 13f);
            CreateCylinder("Drawstring", new Vector3(0f, 0.33f, 0f), new Vector3(0.22f, 0.055f, 0.22f), tie, bag, false, 10);
            CreateCylinder("Gold Coin Mark", new Vector3(0f, 0.03f, -0.30f), new Vector3(0.14f, 0.035f, 0.14f), gold, bag, false, 12, Quaternion.Euler(90f, 0f, 0f));

            coinSpill = new GameObject("Visible Gold Coin Spill");
            coinSpill.transform.SetParent(bag, false);
            var coinPositions = new[]
            {
                new Vector3(0.42f, -0.42f, -0.12f), new Vector3(0.62f, -0.41f, 0.03f),
                new Vector3(0.50f, -0.37f, 0.22f), new Vector3(-0.42f, -0.42f, 0.04f),
                new Vector3(-0.56f, -0.39f, -0.18f),
            };
            for (var i = 0; i < coinPositions.Length; i++)
                CreateCylinder("Loose Gold Coin", coinPositions[i], new Vector3(0.13f, 0.025f, 0.13f), gold, coinSpill.transform, false, 12, Quaternion.Euler(0f, i * 19f, i % 2 == 0 ? 0f : 7f));
            coinSpill.SetActive(false);
            return bag;
        }

        private static Vector3 GroundPoint(float x, float z) => new(x, TerrainHeight(x, z), z);

        private Transform CreateHouse(string name, Vector3 position, float scale, Color wallColor, Color roofColor, int variant)
        {
            var house = new GameObject(name).transform;
            house.SetParent(_villageRoot, false);
            house.localPosition = new Vector3(position.x, TerrainHeight(position.x, position.z), position.z);
            house.localRotation = RotationFacingRoad(house.localPosition);
            var plaster = MaterialFor(name + " Plaster", wallColor, 0.03f);
            var roof = MaterialFor(name + " Roof", roofColor, 0.02f);
            var beam = MaterialFor("House Timber", new Color(0.23f, 0.13f, 0.065f), 0.07f);
            var stone = MaterialFor("Foundation Stone", new Color(0.43f, 0.44f, 0.39f), 0.03f);
            var glass = MaterialFor("Warm Window Glass", new Color(1f, 0.67f, 0.23f), 0.28f, true);
            var flowerRed = MaterialFor("Window Flowers", new Color(0.72f, 0.18f, 0.14f), 0.05f);

            Primitive("Stone Foundation", PrimitiveType.Cube, new Vector3(0f, 0.32f * scale, 0f), new Vector3(6.8f * scale, 0.64f * scale, 5.9f * scale), stone, house, true);
            Primitive("Plaster Walls", PrimitiveType.Cube, new Vector3(0f, 2.05f * scale, 0f), new Vector3(6.25f * scale, 3.55f * scale, 5.4f * scale), plaster, house, true);
            CreateGabledRoof(house, new Vector3(0f, 3.72f * scale, 0f), 7.35f * scale, 6.55f * scale, 2.55f * scale, roof);
            Primitive("Ridge Beam", PrimitiveType.Cube, new Vector3(0f, 6.25f * scale, 0f), new Vector3(0.19f * scale, 0.22f * scale, 6.8f * scale), beam, house, false);
            Primitive("Front Door", PrimitiveType.Cube, new Vector3(0f, 1.36f * scale, -2.76f * scale), new Vector3(1.18f * scale, 2.35f * scale, 0.18f * scale), beam, house, true);
            Primitive("Door Header", PrimitiveType.Cube, new Vector3(0f, 2.62f * scale, -2.87f * scale), new Vector3(1.55f * scale, 0.18f * scale, 0.18f * scale), beam, house, false);
            for (var side = -1; side <= 1; side += 2)
                Primitive("Door Frame", PrimitiveType.Cube, new Vector3(side * 0.68f * scale, 1.38f * scale, -2.87f * scale), new Vector3(0.16f * scale, 2.55f * scale, 0.18f * scale), beam, house, false);
            CreatePolyObject("Door Handle", new Vector3(0.37f * scale, 1.38f * scale, -2.9f * scale), Vector3.one * 0.10f * scale, MaterialFor("Brass", new Color(0.72f, 0.52f, 0.15f), 0.55f), house, false, 0f);
            var windowXs = variant == 1 ? new[] { -2.05f, 2.05f } : new[] { -1.95f, 1.95f };
            foreach (var x in windowXs) CreateWindow(new Vector3(x * scale, 2.13f * scale, -2.79f * scale), scale, glass, beam, flowerRed, house);
            for (var x = -2; x <= 2; x += 2)
                Primitive("Vertical Timber", PrimitiveType.Cube, new Vector3(x * scale, 2.05f * scale, -2.86f * scale), new Vector3(0.17f * scale, 3.65f * scale, 0.15f * scale), beam, house, false);
            Primitive("Cross Timber", PrimitiveType.Cube, new Vector3(0f, 3.03f * scale, -2.87f * scale), new Vector3(6.2f * scale, 0.15f * scale, 0.15f * scale), beam, house, false);
            var chimneyX = variant % 2 == 0 ? 1.9f : -1.9f;
            Primitive("Stone Chimney", PrimitiveType.Cube, new Vector3(chimneyX * scale, 5.15f * scale, 0.62f * scale), new Vector3(0.72f * scale, 2.45f * scale, 0.72f * scale), stone, house, true);
            Primitive("Chimney Cap", PrimitiveType.Cube, new Vector3(chimneyX * scale, 6.35f * scale, 0.62f * scale), new Vector3(0.92f * scale, 0.18f * scale, 0.92f * scale), stone, house, false);
            Primitive("Front Step", PrimitiveType.Cube, new Vector3(0f, 0.18f * scale, -3.35f * scale), new Vector3(2.15f * scale, 0.28f * scale, 1.1f * scale), stone, house, true);
            if (variant == 2) CreateHousePorch(house, scale, beam, roof, stone);
            else
            {
                CreateFence(house, new Vector3(-4.8f * scale, 0f, -4.35f * scale), new Vector3(-1.5f * scale, 0f, -4.35f * scale), beam);
                CreateFence(house, new Vector3(1.5f * scale, 0f, -4.35f * scale), new Vector3(4.8f * scale, 0f, -4.35f * scale), beam);
            }
            return house;
        }

        private void CreateHousePorch(Transform house, float scale, Material wood, Material roof, Material stone)
        {
            Primitive("Porch Deck", PrimitiveType.Cube, new Vector3(0f, 0.47f * scale, -3.62f * scale), new Vector3(5.25f * scale, 0.26f * scale, 1.95f * scale), wood, house, true);
            Primitive("Porch Step", PrimitiveType.Cube, new Vector3(0f, 0.18f * scale, -4.78f * scale), new Vector3(2.15f * scale, 0.28f * scale, 0.72f * scale), stone, house, true);
            foreach (var x in new[] { -2.28f, 2.28f })
            {
                CreateCylinder("Porch Post", new Vector3(x * scale, 1.85f * scale, -4.28f * scale), new Vector3(0.12f * scale, 1.45f * scale, 0.12f * scale), wood, house, true, 8);
                Primitive("Porch Side Rail", PrimitiveType.Cube, new Vector3(x * scale, 1.0f * scale, -3.62f * scale), new Vector3(0.12f * scale, 0.12f * scale, 1.28f * scale), wood, house, false);
            }
            CreateGabledRoof(house, new Vector3(0f, 3.32f * scale, -3.65f * scale), 5.85f * scale, 2.45f * scale, 0.78f * scale, roof, false);
        }

        private void CreateWindow(Vector3 position, float scale, Material glass, Material frame, Material flowers, Transform parent)
        {
            Primitive("Window Glass", PrimitiveType.Cube, position, new Vector3(0.92f, 0.94f, 0.10f) * scale, glass, parent, false);
            foreach (var x in new[] { -0.52f, 0.52f }) Primitive("Window Frame", PrimitiveType.Cube, position + new Vector3(x * scale, 0f, -0.08f * scale), new Vector3(0.11f, 1.16f, 0.13f) * scale, frame, parent, false);
            foreach (var y in new[] { -0.54f, 0.54f }) Primitive("Window Frame", PrimitiveType.Cube, position + new Vector3(0f, y * scale, -0.08f * scale), new Vector3(1.15f, 0.11f, 0.13f) * scale, frame, parent, false);
            Primitive("Window Mullion", PrimitiveType.Cube, position + new Vector3(0f, 0f, -0.09f * scale), new Vector3(0.08f, 1.02f, 0.13f) * scale, frame, parent, false);
            Primitive("Flower Box", PrimitiveType.Cube, position + new Vector3(0f, -0.68f * scale, -0.25f * scale), new Vector3(1.22f, 0.25f, 0.42f) * scale, frame, parent, false);
            for (var i = -2; i <= 2; i++) CreatePolyObject("Window Flowers", position + new Vector3(i * 0.21f * scale, -0.47f * scale, -0.33f * scale), Vector3.one * 0.12f * scale, flowers, parent, false, i * 42f);
        }

        private void CreateMarketStall(string name, Vector3 position, float yaw, Material canvas, Material wood, Material crate, Transform parent)
        {
            var stall = new GameObject(name).transform;
            stall.SetParent(parent, false);
            stall.localPosition = position;
            stall.localRotation = Quaternion.Euler(0f, yaw, 0f);
            Primitive("Market Tabletop", PrimitiveType.Cube, new Vector3(0f, 1.18f, 0f), new Vector3(6f, 0.22f, 2.15f), crate, stall, true);
            Primitive("Market Display Rim", PrimitiveType.Cube, new Vector3(0f, 1.33f, 0f), new Vector3(6.35f, 0.10f, 2.4f), wood, stall, false);
            Primitive("Lower Shelf", PrimitiveType.Cube, new Vector3(0f, 0.38f, 0f), new Vector3(5.15f, 0.14f, 1.45f), crate, stall, false);
            for (var i = 0; i < 4; i++)
            {
                var x = i < 2 ? -2.55f : 2.55f;
                var z = i % 2 == 0 ? -0.78f : 0.78f;
                Primitive("Table Leg", PrimitiveType.Cube, new Vector3(x, 0.57f, z), new Vector3(0.20f, 1.14f, 0.20f), wood, stall, true);
            }
            for (var i = 0; i < 4; i++)
            {
                var x = i < 2 ? -3.05f : 3.05f;
                var z = i % 2 == 0 ? -1.65f : 1.65f;
                CreateCylinder("Canopy Pole", new Vector3(x, 2.35f, z), new Vector3(0.12f, 2.35f, 0.12f), wood, stall, true, 8);
            }
            CreateGabledRoof(stall, new Vector3(0f, 4.62f, 0f), 7.35f, 4.25f, 1.25f, canvas, false);
            Primitive("Canopy Ridge", PrimitiveType.Cube, new Vector3(0f, 5.86f, 0f), new Vector3(0.16f, 0.16f, 4.5f), wood, stall, false);
        }

        private void BuildBridge(Vector3 center, Material wood)
        {
            const float bridgeLength = 20.5f;
            const int plankCount = 23;
            var leftBank = TerrainHeight(center.x - bridgeLength * 0.5f, center.z);
            var rightBank = TerrainHeight(center.x + bridgeLength * 0.5f, center.z);
            var bankSlope = Mathf.Atan2(rightBank - leftBank, bridgeLength) * Mathf.Rad2Deg;
            var bridge = new GameObject("Timber Footbridge").transform;
            bridge.SetParent(_villageRoot, false);
            bridge.localPosition = new Vector3(center.x, 0f, center.z);
            for (var i = 0; i < plankCount; i++)
            {
                var progress = i / (float)(plankCount - 1);
                var x = -bridgeLength * 0.5f + progress * bridgeLength;
                var deckHeight = Mathf.Lerp(leftBank, rightBank, progress) + 0.10f + Mathf.Sin(progress * Mathf.PI) * 0.58f;
                var archSlope = Mathf.Cos(progress * Mathf.PI) * 4.2f;
                Primitive("Bridge Plank", PrimitiveType.Cube, new Vector3(x, deckHeight, 0f), new Vector3(0.86f, 0.19f, 3.3f), wood, bridge, true, Quaternion.Euler(0f, 0f, bankSlope + archSlope));
            }
            for (var side = -1; side <= 1; side += 2)
            {
                for (var i = 0; i < 7; i++)
                {
                    var progress = i / 6f;
                    var x = -9.6f + i * 3.2f;
                    var deckHeight = Mathf.Lerp(leftBank, rightBank, progress) + 0.10f + Mathf.Sin(progress * Mathf.PI) * 0.58f;
                    CreateCylinder("Bridge Rail Post", new Vector3(x, deckHeight + 0.72f, side * 1.55f), new Vector3(0.10f, 0.75f, 0.10f), wood, bridge, true, 8);
                }
                Primitive("Bridge Handrail", PrimitiveType.Cube, new Vector3(0f, (leftBank + rightBank) * 0.5f + 1.77f, side * 1.55f), new Vector3(19.9f, 0.13f, 0.13f), wood, bridge, false, Quaternion.Euler(0f, 0f, bankSlope));
            }
        }

        private void CreateRowboat(Vector3 position, float yaw, Material hull, Material wood)
        {
            var boat = new GameObject("Moored Rowboat").transform;
            boat.SetParent(_villageRoot, false);
            boat.localPosition = position;
            boat.localRotation = Quaternion.Euler(0f, yaw, 2f);
            Primitive("Port Hull", PrimitiveType.Cube, new Vector3(-0.8f, 0f, 0f), new Vector3(0.35f, 0.65f, 4.6f), hull, boat, true, Quaternion.Euler(0f, 0f, -18f));
            Primitive("Starboard Hull", PrimitiveType.Cube, new Vector3(0.8f, 0f, 0f), new Vector3(0.35f, 0.65f, 4.6f), hull, boat, true, Quaternion.Euler(0f, 0f, 18f));
            for (var z = -1.4f; z <= 1.4f; z += 1.4f) Primitive("Boat Seat", PrimitiveType.Cube, new Vector3(0f, 0.38f, z), new Vector3(1.65f, 0.13f, 0.38f), wood, boat, false);
            Primitive("Oar", PrimitiveType.Cube, new Vector3(0.2f, 0.72f, 0.2f), new Vector3(3.7f, 0.10f, 0.18f), wood, boat, false, Quaternion.Euler(0f, 28f, -7f));
        }

        private void CreateBroadleafTree(Vector3 position, float scale, int seed)
        {
            var tree = new GameObject("Broadleaf Tree").transform;
            tree.SetParent(_villageRoot, false);
            tree.localPosition = position;
            tree.localRotation = Quaternion.Euler(0f, seed * 19f % 360f, 0f);
            var trunk = MaterialFor("Tree Trunks", new Color(0.25f, 0.14f, 0.065f), 0.03f);
            var foliage = MaterialFor("Leaf Green", new Color(0.14f, 0.42f, 0.13f), 0.01f);
            var foliageLight = MaterialFor("Sunlit Leaf Green", new Color(0.32f, 0.59f, 0.18f), 0.01f);
            var foliageWarm = MaterialFor("Warm Leaf Green", new Color(0.25f, 0.51f, 0.13f), 0.01f);
            CreateCylinder("Trunk", new Vector3(0f, 1.85f * scale, 0f), new Vector3(0.34f * scale, 1.85f * scale, 0.34f * scale), trunk, tree, true, 8);
            CreateCylinder("Left Branch", new Vector3(-0.48f * scale, 3.05f * scale, 0f), new Vector3(0.17f * scale, 1.1f * scale, 0.17f * scale), trunk, tree, false, 7, Quaternion.Euler(0f, 0f, -31f));
            CreateCylinder("Right Branch", new Vector3(0.52f * scale, 3.18f * scale, 0.18f * scale), new Vector3(0.16f * scale, 1.05f * scale, 0.16f * scale), trunk, tree, false, 7, Quaternion.Euler(12f, 0f, 34f));
            CreatePolyObject("Lower Crown", new Vector3(0f, 4.35f * scale, 0f), new Vector3(2.25f, 1.65f, 2.05f) * scale, foliage, tree, false, seed);
            CreatePolyObject("Left Crown", new Vector3(-1.28f * scale, 4.82f * scale, 0.18f * scale), new Vector3(1.48f, 1.32f, 1.42f) * scale, foliageWarm, tree, false, seed + 41);
            CreatePolyObject("Right Crown", new Vector3(1.27f * scale, 4.95f * scale, -0.14f * scale), new Vector3(1.55f, 1.38f, 1.48f) * scale, foliage, tree, false, seed + 83);
            CreatePolyObject("Top Crown", new Vector3(0.05f, 6.0f * scale, 0f), new Vector3(1.6f, 1.45f, 1.55f) * scale, foliageLight, tree, false, seed + 137);
        }

        private void CreatePine(Vector3 position, float scale)
        {
            var pine = new GameObject("Pine Tree").transform;
            pine.SetParent(_villageRoot, false);
            pine.localPosition = position;
            var trunk = MaterialFor("Tree Trunks", new Color(0.25f, 0.14f, 0.065f), 0.03f);
            var needles = MaterialFor("Pine Needles", new Color(0.10f, 0.32f, 0.17f), 0.01f);
            var needlesLight = MaterialFor("Pine Tips", new Color(0.20f, 0.46f, 0.19f), 0.01f);
            CreateCylinder("Pine Trunk", new Vector3(0f, 2.1f * scale, 0f), new Vector3(0.25f * scale, 2.1f * scale, 0.25f * scale), trunk, pine, true, 8);
            CreateCone("Lower Boughs", new Vector3(0f, 1.5f * scale, 0f), 2.3f * scale, 3.7f * scale, 9, needles, pine);
            CreateCone("Middle Boughs", new Vector3(0f, 3.0f * scale, 0f), 1.82f * scale, 3.45f * scale, 9, needlesLight, pine);
            CreateCone("Top Boughs", new Vector3(0f, 4.55f * scale, 0f), 1.22f * scale, 2.8f * scale, 9, needles, pine);
        }

        private void BuildGrassAndFlowers(System.Random random)
        {
            var grassA = MaterialFor("Meadow Grass", new Color(0.24f, 0.51f, 0.15f), 0f);
            var grassB = MaterialFor("Golden Grass", new Color(0.55f, 0.64f, 0.21f), 0f);
            var flowerWhite = MaterialFor("White Wildflowers", new Color(0.94f, 0.89f, 0.68f), 0.03f);
            var flowerBlue = MaterialFor("Blue Wildflowers", new Color(0.31f, 0.45f, 0.78f), 0.03f);
            for (var i = 0; i < 140; i++)
            {
                var x = (float)(random.NextDouble() * 80d - 40d);
                var z = (float)(random.NextDouble() * 92d - 46d);
                if (Mathf.Abs(x - RoadCenterAt(z)) < 3.4f || Mathf.Abs(x - RiverCenter(z)) < 11f) continue;
                var root = new GameObject("Meadow Detail").transform;
                root.SetParent(_villageRoot, false);
                root.localPosition = new Vector3(x, TerrainHeight(x, z), z);
                root.localRotation = Quaternion.Euler(0f, (float)random.NextDouble() * 180f, 0f);
                var material = i % 4 == 0 ? grassB : grassA;
                for (var blade = -1; blade <= 1; blade++)
                    Primitive("Grass Blade", PrimitiveType.Cube, new Vector3(blade * 0.13f, 0.22f + Mathf.Abs(blade) * 0.04f, 0f), new Vector3(0.055f, 0.44f + blade * 0.05f, 0.055f), material, root, false, Quaternion.Euler(0f, 0f, blade * 10f));
                if (i % 7 == 0)
                {
                    var flower = i % 14 == 0 ? flowerBlue : flowerWhite;
                    CreatePolyObject("Wildflower", new Vector3(0.05f, 0.52f, 0.05f), Vector3.one * 0.12f, flower, root, false, i * 17f);
                }
            }
        }

        private void CreateLantern(Vector3 position, Material wood, Material glow)
        {
            var post = new GameObject("Road Lantern").transform;
            post.SetParent(_villageRoot, false);
            post.localPosition = position;
            CreateCylinder("Lantern Post", new Vector3(0f, 2.15f, 0f), new Vector3(0.11f, 2.15f, 0.11f), wood, post, true, 8);
            Primitive("Lamp Hook", PrimitiveType.Cube, new Vector3(0.3f, 4.05f, 0f), new Vector3(0.65f, 0.09f, 0.09f), wood, post, false);
            var lantern = CreatePolyObject("Lantern Glass", new Vector3(0.58f, 3.72f, 0f), new Vector3(0.28f, 0.36f, 0.28f), glow, post, false, 0f);
            var light = lantern.AddComponent<Light>();
            light.type = LightType.Point;
            light.range = 6.5f;
            light.intensity = 0.75f;
            light.color = new Color(1f, 0.65f, 0.25f);
            light.shadows = LightShadows.None;
        }

        private Transform CreateBench(Vector3 position, Material material)
        {
            var bench = new GameObject("Village Bench").transform;
            bench.SetParent(_villageRoot, false);
            bench.localPosition = position;
            bench.localRotation = RotationFacingRoad(position);
            Primitive("Seat", PrimitiveType.Cube, new Vector3(0f, 0.72f, 0f), new Vector3(3.2f, 0.18f, 0.72f), material, bench, true);
            Primitive("Back", PrimitiveType.Cube, new Vector3(0f, 1.3f, 0.31f), new Vector3(3.2f, 0.72f, 0.14f), material, bench, true, Quaternion.Euler(-8f, 0f, 0f));
            foreach (var x in new[] { -1.2f, 1.2f }) Primitive("Bench Leg", PrimitiveType.Cube, new Vector3(x, 0.36f, 0f), new Vector3(0.18f, 0.72f, 0.6f), material, bench, true);
            return bench;
        }

        private void CreateCart(Vector3 position, float yaw, Material wood, Material darkWood)
        {
            var cart = new GameObject("Empty Village Cart").transform;
            cart.SetParent(_villageRoot, false);
            cart.localPosition = position;
            cart.localRotation = Quaternion.Euler(0f, yaw, 0f);
            Primitive("Cart Bed", PrimitiveType.Cube, new Vector3(0f, 1.2f, 0f), new Vector3(3.8f, 0.35f, 2.5f), wood, cart, true);
            Primitive("Cart Front", PrimitiveType.Cube, new Vector3(1.75f, 1.85f, 0f), new Vector3(0.22f, 1.3f, 2.5f), wood, cart, true);
            foreach (var z in new[] { -1.28f, 1.28f })
            {
                CreateCylinder("Cart Wheel", new Vector3(0f, 0.9f, z), new Vector3(1f, 0.14f, 1f), darkWood, cart, true, 12, Quaternion.Euler(90f, 0f, 0f));
                CreateCylinder("Wheel Hub", new Vector3(0f, 0.9f, z * 1.05f), new Vector3(0.19f, 0.22f, 0.19f), wood, cart, false, 8, Quaternion.Euler(90f, 0f, 0f));
            }
            foreach (var z in new[] { -0.72f, 0.72f }) Primitive("Cart Shaft", PrimitiveType.Cube, new Vector3(-3.5f, 0.7f, z), new Vector3(4.8f, 0.14f, 0.14f), darkWood, cart, false);
        }

        private void CreateHaystack(Vector3 position, float scale, Material straw)
        {
            var hay = new GameObject("Haystack").transform;
            hay.SetParent(_villageRoot, false);
            hay.localPosition = position;
            CreatePolyObject("Hay Mound", new Vector3(0f, 0.95f * scale, 0f), new Vector3(1.6f, 1.25f, 1.45f) * scale, straw, hay, true, position.GetHashCode());
            CreateCone("Hay Cap", new Vector3(0f, 1.65f * scale, 0f), 1.35f * scale, 1.5f * scale, 11, straw, hay);
        }

        private void CreateBarrel(Vector3 position, float scale, Transform parent)
        {
            var barrelWood = MaterialFor("Barrel Wood", new Color(0.40f, 0.24f, 0.10f), 0.07f);
            var iron = MaterialFor("Dark Iron", new Color(0.12f, 0.13f, 0.12f), 0.36f);
            var barrel = new GameObject("Barrel").transform;
            barrel.SetParent(parent, false);
            barrel.localPosition = position;
            CreateCylinder("Barrel Body", Vector3.zero, new Vector3(scale, scale, scale), barrelWood, barrel, true, 12);
            foreach (var y in new[] { -0.68f, 0f, 0.68f }) CreateCylinder("Iron Band", new Vector3(0f, y * scale, 0f), new Vector3(scale * 1.035f, scale * 0.055f, scale * 1.035f), iron, barrel, false, 12);
        }

        private void CreateCrateStack(Vector3 position, Transform parent, Material wood)
        {
            var stack = new GameObject("Crate Stack").transform;
            stack.SetParent(parent, false);
            stack.localPosition = position;
            CreateCrate(new Vector3(0f, 0.55f, 0f), 1.05f, wood, stack);
            CreateCrate(new Vector3(1.15f, 0.42f, 0.25f), 0.82f, wood, stack);
            CreateCrate(new Vector3(0.25f, 1.58f, 0.05f), 0.76f, wood, stack);
        }

        private void CreateCrate(Vector3 position, float scale, Material wood, Transform parent)
        {
            Primitive("Crate", PrimitiveType.Cube, position, Vector3.one * scale, wood, parent, true);
            var dark = MaterialFor("Crate Slats", new Color(0.30f, 0.17f, 0.07f), 0.04f);
            foreach (var y in new[] { -0.42f, 0.42f }) Primitive("Crate Slat", PrimitiveType.Cube, position + new Vector3(0f, y * scale, -0.53f * scale), new Vector3(1.08f, 0.09f, 0.08f) * scale, dark, parent, false);
            foreach (var x in new[] { -0.42f, 0.42f }) Primitive("Crate Slat", PrimitiveType.Cube, position + new Vector3(x * scale, 0f, -0.54f * scale), new Vector3(0.09f, 1.08f, 0.08f) * scale, dark, parent, false);
        }

        private void CreateRockCluster(Vector3 center, Material stone)
        {
            center.y = TerrainHeight(center.x, center.z);
            CreateRock("Boulder", center + new Vector3(0f, 0.65f, 0f), new Vector3(1.5f, 0.95f, 1.2f), stone, true, 17f);
            CreateRock("Boulder", center + new Vector3(1.25f, 0.32f, 0.45f), new Vector3(0.75f, 0.48f, 0.68f), stone, true, 83f);
            CreateRock("Boulder", center + new Vector3(-1f, 0.25f, 0.65f), new Vector3(0.55f, 0.36f, 0.63f), stone, true, 147f);
        }

        private void CreateMountainRange(Vector3 position, float radius, float height, Material stone, Material highlight, int seed)
        {
            var mountain = CreateMeshObject("Faceted Mountain", MountainMesh(radius, height, 11, seed), position, Vector3.one, stone, _villageRoot, false);
            mountain.transform.localRotation = Quaternion.Euler(0f, seed % 360, 0f);
            mountain.GetComponent<MeshRenderer>().shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            var cap = CreateMeshObject("Mountain Sun Cap", MountainMesh(radius * 0.43f, height * 0.38f, 9, seed + 51), position + new Vector3(-radius * 0.04f, height * 0.62f, 0f), Vector3.one, highlight, _villageRoot, false);
            cap.GetComponent<MeshRenderer>().shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        }

        private void CreateHorizonBand(string name, float radius, float bottom, float height, float amplitude, int segments, float phase, Material material)
        {
            var band = CreateMeshObject(name, HorizonBandMesh(radius, bottom, height, amplitude, segments, phase), Vector3.zero, Vector3.one, material, _villageRoot, false);
            var renderer = band.GetComponent<MeshRenderer>();
            renderer.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            renderer.receiveShadows = false;
        }

        private void CreateFence(Transform parent, Vector3 start, Vector3 end, Material material)
        {
            var direction = end - start;
            var length = direction.magnitude;
            var fence = new GameObject("Garden Fence").transform;
            fence.SetParent(parent, false);
            fence.localPosition = start;
            fence.localRotation = Quaternion.LookRotation(direction.normalized);
            Primitive("Fence Rail", PrimitiveType.Cube, new Vector3(0f, 0.62f, length * 0.5f), new Vector3(0.13f, 0.13f, length), material, fence, false);
            Primitive("Fence Rail", PrimitiveType.Cube, new Vector3(0f, 1.12f, length * 0.5f), new Vector3(0.13f, 0.11f, length), material, fence, false);
            for (var z = 0f; z <= length; z += 1.15f) CreateCylinder("Fence Post", new Vector3(0f, 0.76f, z), new Vector3(0.09f, 0.76f, 0.09f), material, fence, true, 7);
        }

        private GameObject CreateRibbon(string name, IReadOnlyList<Vector3> points, float width, float yOffset, Material material, bool followTerrain, bool collider)
        {
            var vertices = new Vector3[points.Count * 2];
            var uvs = new Vector2[vertices.Length];
            var triangles = new int[(points.Count - 1) * 6];
            for (var i = 0; i < points.Count; i++)
            {
                var previous = points[Mathf.Max(0, i - 1)];
                var next = points[Mathf.Min(points.Count - 1, i + 1)];
                var tangent = (next - previous).normalized;
                var side = new Vector3(-tangent.z, 0f, tangent.x);
                for (var edge = 0; edge < 2; edge++)
                {
                    var position = points[i] + side * (edge == 0 ? -width * 0.5f : width * 0.5f);
                    position.y = followTerrain ? TerrainHeight(position.x, position.z) + yOffset : yOffset;
                    vertices[i * 2 + edge] = position;
                    uvs[i * 2 + edge] = new Vector2(edge, i * 0.35f);
                }
                if (i == points.Count - 1) continue;
                var triangle = i * 6;
                var vertex = i * 2;
                triangles[triangle] = vertex;
                triangles[triangle + 1] = vertex + 1;
                triangles[triangle + 2] = vertex + 2;
                triangles[triangle + 3] = vertex + 1;
                triangles[triangle + 4] = vertex + 3;
                triangles[triangle + 5] = vertex + 2;
            }
            var mesh = new Mesh { name = name + " Mesh", vertices = vertices, triangles = triangles, uv = uvs };
            mesh.RecalculateNormals();
            mesh.RecalculateBounds();
            var ribbon = CreateMeshObject(name, mesh, Vector3.zero, Vector3.one, material, _villageRoot, collider);
            ribbon.GetComponent<MeshRenderer>().shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            return ribbon;
        }

        private GameObject CreateMeshObject(string name, Mesh mesh, Vector3 position, Vector3 scale, Material material, Transform parent, bool collider)
        {
            var instance = new GameObject(name);
            instance.transform.SetParent(parent, false);
            instance.transform.localPosition = position;
            instance.transform.localScale = scale;
            var filter = instance.AddComponent<MeshFilter>();
            filter.sharedMesh = mesh;
            var renderer = instance.AddComponent<MeshRenderer>();
            renderer.sharedMaterial = material;
            renderer.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.On;
            renderer.receiveShadows = true;
            if (collider) instance.AddComponent<MeshCollider>().sharedMesh = mesh;
            return instance;
        }

        private GameObject Primitive(string name, PrimitiveType type, Vector3 position, Vector3 scale, Material material, Transform parent, bool keepCollider, Quaternion? rotation = null)
        {
            var instance = GameObject.CreatePrimitive(type);
            instance.name = name;
            instance.transform.SetParent(parent, false);
            instance.transform.localPosition = position;
            instance.transform.localRotation = rotation ?? Quaternion.identity;
            instance.transform.localScale = scale;
            instance.GetComponent<Renderer>().sharedMaterial = material;
            if (!keepCollider)
            {
                var primitiveCollider = instance.GetComponent<Collider>();
                if (primitiveCollider != null) Destroy(primitiveCollider);
            }
            return instance;
        }

        private GameObject CreateCylinder(string name, Vector3 position, Vector3 scale, Material material, Transform parent, bool collider, int sides, Quaternion? rotation = null)
        {
            if (!_cylinderMeshes.TryGetValue(sides, out var mesh))
            {
                mesh = CylinderMesh(sides);
                _cylinderMeshes.Add(sides, mesh);
            }
            var cylinder = CreateMeshObject(name, mesh, position, scale, material, parent, collider);
            cylinder.transform.localRotation = rotation ?? Quaternion.identity;
            return cylinder;
        }

        private GameObject CreatePolyObject(string name, Vector3 position, Vector3 scale, Material material, Transform parent, bool collider, float yaw)
        {
            _polySphereMesh ??= PolySphereMesh();
            var poly = CreateMeshObject(name, _polySphereMesh, position, scale, material, parent, collider);
            poly.transform.localRotation = Quaternion.Euler(yaw * 0.17f, yaw, yaw * 0.11f);
            return poly;
        }

        private GameObject CreateRock(string name, Vector3 position, Vector3 scale, Material material, bool collider, float yaw)
            => CreatePolyObject(name, position, scale, material, _villageRoot, collider, yaw);

        private void CreateCone(string name, Vector3 position, float radius, float height, int sides, Material material, Transform parent)
            => CreateMeshObject(name, ConeMesh(radius, height, sides), position, Vector3.one, material, parent, false);

        private void CreateGabledRoof(Transform parent, Vector3 position, float width, float depth, float height, Material material, bool collider = true)
            => CreateMeshObject("Gabled Roof", GabledRoofMesh(width, depth, height), position, Vector3.one, material, parent, collider);

        private Material MaterialFor(string name, Color color, float smoothness = 0f, bool emission = false, bool transparent = false)
        {
            if (_materials.TryGetValue(name, out var existing)) return existing;
            var shader = Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard");
            var material = new Material(shader) { name = name, color = color };
            if (material.HasProperty("_BaseColor")) material.SetColor("_BaseColor", color);
            if (material.HasProperty("_Smoothness")) material.SetFloat("_Smoothness", smoothness);
            if (material.HasProperty("_Metallic")) material.SetFloat("_Metallic", 0f);
            if (emission && material.HasProperty("_EmissionColor"))
            {
                material.EnableKeyword("_EMISSION");
                material.SetColor("_EmissionColor", color * 1.25f);
            }
            if (transparent)
            {
                material.SetFloat("_Surface", 1f);
                material.SetFloat("_Blend", 0f);
                material.SetFloat("_SrcBlend", (float)UnityEngine.Rendering.BlendMode.SrcAlpha);
                material.SetFloat("_DstBlend", (float)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
                material.SetFloat("_ZWrite", 0f);
                material.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
                material.renderQueue = 3000;
            }
            _materials.Add(name, material);
            return material;
        }

        private Material UnlitMaterialFor(string name, Color color)
        {
            if (_materials.TryGetValue(name, out var existing)) return existing;
            var shader = Shader.Find("Universal Render Pipeline/Unlit") ?? Shader.Find("Unlit/Color");
            var material = new Material(shader) { name = name, color = color };
            if (material.HasProperty("_BaseColor")) material.SetColor("_BaseColor", color);
            _materials.Add(name, material);
            return material;
        }

        private static Quaternion RotationFacingRoad(Vector3 position)
        {
            var roadPosition = new Vector3(RoadCenterAt(position.z), position.y, position.z);
            var directionToRoad = roadPosition - position;
            if (directionToRoad.sqrMagnitude < 0.01f) directionToRoad = Vector3.back;
            return Quaternion.LookRotation(-directionToRoad.normalized, Vector3.up);
        }

        private bool TreePlacementIsClear(float x, float z)
        {
            if (Mathf.Abs(x - RoadCenterAt(z)) < 8f) return false;
            if (Mathf.Abs(x - RiverCenter(z)) < 13f) return false;
            foreach (var site in HouseSites)
                if (Vector2.Distance(new Vector2(x, z), new Vector2(site.x, site.z)) < 10f) return false;
            return true;
        }

        private static float RoadCenterAt(float z)
        {
            for (var i = 0; i < MainRoad.Length - 1; i++)
            {
                var a = MainRoad[i];
                var b = MainRoad[i + 1];
                if (z < Mathf.Min(a.z, b.z) || z > Mathf.Max(a.z, b.z)) continue;
                return Mathf.Lerp(a.x, b.x, Mathf.InverseLerp(a.z, b.z, z));
            }
            return 0f;
        }

        private static float RiverCenter(float z) => 43f + Mathf.Sin(z * 0.075f) * 2.1f + Mathf.Sin(z * 0.031f + 1.2f) * 1.2f;

        private static Vector3[] RiverPoints()
        {
            var points = new Vector3[13];
            for (var i = 0; i < points.Length; i++)
            {
                var z = -60f + i * 10f;
                points[i] = new Vector3(RiverCenter(z), 0f, z);
            }
            return points;
        }

        private static float TerrainHeight(float x, float z)
        {
            var centerMask = Mathf.Lerp(0.24f, 1f, Mathf.Clamp01((Mathf.Abs(x) - 22f) / 27f));
            var rolling = (Mathf.Sin(x * 0.105f) * Mathf.Cos(z * 0.082f) * 0.34f + Mathf.Sin((x + z) * 0.055f) * 0.18f) * centerMask;
            var riverDistance = Mathf.Abs(x - RiverCenter(z));
            var riverCarve = riverDistance < 12f ? Mathf.Pow(1f - riverDistance / 12f, 1.35f) * 1.35f : 0f;
            return rolling - riverCarve;
        }

        private static Mesh HorizonBandMesh(float radius, float bottom, float height, float amplitude, int segments, float phase)
        {
            var vertices = new Vector3[(segments + 1) * 2];
            var triangles = new int[segments * 6];
            for (var i = 0; i <= segments; i++)
            {
                var angle = i / (float)segments * Mathf.PI * 2f;
                var profile = Mathf.Pow(Mathf.Abs(Mathf.Sin(angle * 2f + phase)), 3.2f) * amplitude;
                profile += Mathf.Sin(angle * 5f + phase * 0.7f) * amplitude * 0.13f;
                var x = Mathf.Cos(angle) * radius;
                var z = Mathf.Sin(angle) * radius;
                vertices[i * 2] = new Vector3(x, bottom, z);
                vertices[i * 2 + 1] = new Vector3(x, height + profile, z);
                if (i == segments) continue;
                var vertex = i * 2;
                var triangle = i * 6;
                triangles[triangle] = vertex;
                triangles[triangle + 1] = vertex + 2;
                triangles[triangle + 2] = vertex + 1;
                triangles[triangle + 3] = vertex + 2;
                triangles[triangle + 4] = vertex + 3;
                triangles[triangle + 5] = vertex + 1;
            }
            var mesh = new Mesh { name = "Low Cost Horizon Band", vertices = vertices, triangles = triangles };
            mesh.RecalculateNormals();
            mesh.RecalculateBounds();
            return mesh;
        }

        private static Mesh TerrainMesh(float width, float depth, int xSegments, int zSegments)
        {
            var vertices = new Vector3[(xSegments + 1) * (zSegments + 1)];
            var uvs = new Vector2[vertices.Length];
            var triangles = new int[xSegments * zSegments * 6];
            for (var z = 0; z <= zSegments; z++)
            for (var x = 0; x <= xSegments; x++)
            {
                var worldX = -width * 0.5f + width * x / xSegments;
                var worldZ = -depth * 0.5f + depth * z / zSegments;
                var index = z * (xSegments + 1) + x;
                vertices[index] = new Vector3(worldX, TerrainHeight(worldX, worldZ), worldZ);
                uvs[index] = new Vector2(x / (float)xSegments, z / (float)zSegments);
            }
            var triangle = 0;
            for (var z = 0; z < zSegments; z++)
            for (var x = 0; x < xSegments; x++)
            {
                var a = z * (xSegments + 1) + x;
                var b = a + 1;
                var c = a + xSegments + 1;
                var d = c + 1;
                triangles[triangle++] = a;
                triangles[triangle++] = c;
                triangles[triangle++] = b;
                triangles[triangle++] = b;
                triangles[triangle++] = c;
                triangles[triangle++] = d;
            }
            var mesh = new Mesh { name = "Rolling Meadow Mesh", vertices = vertices, triangles = triangles, uv = uvs };
            mesh.RecalculateNormals();
            mesh.RecalculateBounds();
            return mesh;
        }

        private static Mesh GabledRoofMesh(float width, float depth, float height)
        {
            var w = width * 0.5f;
            var d = depth * 0.5f;
            var vertices = new[]
            {
                new Vector3(-w, 0f, -d), new Vector3(w, 0f, -d), new Vector3(0f, height, -d),
                new Vector3(-w, 0f, d), new Vector3(w, 0f, d), new Vector3(0f, height, d),
            };
            var triangles = new[] { 0, 2, 1, 3, 4, 5, 0, 3, 5, 0, 5, 2, 1, 2, 5, 1, 5, 4, 0, 1, 4, 0, 4, 3 };
            return FlatMesh("Low Poly Gabled Roof", vertices, triangles);
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
            return FlatMesh("Low Poly Cone", vertices.ToArray(), triangles.ToArray());
        }

        private static Mesh CylinderMesh(int sides)
        {
            var vertices = new List<Vector3>();
            var triangles = new List<int>();
            for (var i = 0; i < sides; i++)
            {
                var angle = i / (float)sides * Mathf.PI * 2f;
                vertices.Add(new Vector3(Mathf.Cos(angle), -1f, Mathf.Sin(angle)));
                vertices.Add(new Vector3(Mathf.Cos(angle), 1f, Mathf.Sin(angle)));
            }
            vertices.Add(new Vector3(0f, -1f, 0f));
            vertices.Add(new Vector3(0f, 1f, 0f));
            var bottomCenter = sides * 2;
            var topCenter = bottomCenter + 1;
            for (var i = 0; i < sides; i++)
            {
                var next = (i + 1) % sides;
                triangles.AddRange(new[] { i * 2, next * 2 + 1, i * 2 + 1, i * 2, next * 2, next * 2 + 1 });
                triangles.AddRange(new[] { bottomCenter, next * 2, i * 2, topCenter, i * 2 + 1, next * 2 + 1 });
            }
            return FlatMesh("Low Poly Cylinder " + sides, vertices.ToArray(), triangles.ToArray());
        }

        private static Mesh PolySphereMesh()
        {
            var t = (1f + Mathf.Sqrt(5f)) * 0.5f;
            var vertices = new[]
            {
                new Vector3(-1, t, 0), new Vector3(1, t, 0), new Vector3(-1, -t, 0), new Vector3(1, -t, 0),
                new Vector3(0, -1, t), new Vector3(0, 1, t), new Vector3(0, -1, -t), new Vector3(0, 1, -t),
                new Vector3(t, 0, -1), new Vector3(t, 0, 1), new Vector3(-t, 0, -1), new Vector3(-t, 0, 1),
            };
            for (var i = 0; i < vertices.Length; i++) vertices[i] = vertices[i].normalized;
            var triangles = new[]
            {
                0,11,5, 0,5,1, 0,1,7, 0,7,10, 0,10,11,
                1,5,9, 5,11,4, 11,10,2, 10,7,6, 7,1,8,
                3,9,4, 3,4,2, 3,2,6, 3,6,8, 3,8,9,
                4,9,5, 2,4,11, 6,2,10, 8,6,7, 9,8,1,
            };
            return FlatMesh("Faceted Poly Sphere", vertices, triangles);
        }

        private static Mesh MountainMesh(float radius, float height, int sides, int seed)
        {
            var random = new System.Random(seed);
            const int rings = 4;
            var vertices = new List<Vector3>();
            for (var ring = 0; ring < rings; ring++)
            {
                var level = ring / (float)(rings - 1);
                var ringRadius = Mathf.Pow(1f - level, 0.72f) * radius;
                if (ring == rings - 1) ringRadius = radius * 0.04f;
                for (var side = 0; side < sides; side++)
                {
                    var angle = side / (float)sides * Mathf.PI * 2f;
                    var variance = 0.82f + (float)random.NextDouble() * 0.31f;
                    vertices.Add(new Vector3(Mathf.Cos(angle) * ringRadius * variance, height * level, Mathf.Sin(angle) * ringRadius * variance));
                }
            }
            var triangles = new List<int>();
            for (var ring = 0; ring < rings - 1; ring++)
            for (var side = 0; side < sides; side++)
            {
                var next = (side + 1) % sides;
                var a = ring * sides + side;
                var b = ring * sides + next;
                var c = (ring + 1) * sides + side;
                var d = (ring + 1) * sides + next;
                triangles.AddRange(new[] { a, c, b, b, c, d });
            }
            return FlatMesh("Faceted Mountain Mesh", vertices.ToArray(), triangles.ToArray());
        }

        private static Mesh FlatMesh(string name, IReadOnlyList<Vector3> sourceVertices, IReadOnlyList<int> sourceTriangles)
        {
            var vertices = new Vector3[sourceTriangles.Count];
            var triangles = new int[sourceTriangles.Count];
            for (var i = 0; i < sourceTriangles.Count; i++)
            {
                vertices[i] = sourceVertices[sourceTriangles[i]];
                triangles[i] = i;
            }
            var mesh = new Mesh { name = name, vertices = vertices, triangles = triangles };
            mesh.RecalculateNormals();
            mesh.RecalculateBounds();
            return mesh;
        }
    }

    [RequireComponent(typeof(CharacterController))]
    public sealed class VillagePlayerController : MonoBehaviour
    {
        [HideInInspector] public Transform cameraTransform;
        [HideInInspector] public Camera playerCamera;
        public float walkSpeed = 4.7f;
        public float sprintSpeed = 7.3f;
        public float lookSensitivity = 0.075f;
        private CharacterController _controller;
        private float _verticalVelocity;
        private float _pitch;
        private float _bobTime;
        private Vector3 _cameraRestPosition;

        private void Awake() => _controller = GetComponent<CharacterController>();

        private void Start()
        {
            _cameraRestPosition = cameraTransform.localPosition;
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
            var sprinting = keyboard != null && keyboard.leftShiftKey.isPressed && move.sqrMagnitude > 0.1f;
            var speed = sprinting ? sprintSpeed : walkSpeed;
            _verticalVelocity = _controller.isGrounded ? -1.3f : _verticalVelocity + Physics.gravity.y * Time.deltaTime;
            var worldMove = transform.TransformDirection(move) * speed;
            worldMove.y = _verticalVelocity;
            _controller.Move(worldMove * Time.deltaTime);

            playerCamera.fieldOfView = Mathf.Lerp(playerCamera.fieldOfView, sprinting ? 68f : 64f, Time.deltaTime * 5f);
            if (move.sqrMagnitude > 0.05f && _controller.isGrounded)
            {
                _bobTime += Time.deltaTime * (sprinting ? 11f : 8f);
                cameraTransform.localPosition = _cameraRestPosition + new Vector3(Mathf.Sin(_bobTime * 0.5f) * 0.018f, Mathf.Sin(_bobTime) * 0.028f, 0f);
            }
            else cameraTransform.localPosition = Vector3.Lerp(cameraTransform.localPosition, _cameraRestPosition, Time.deltaTime * 8f);

            if (mouse == null) return;
            var look = mouse.delta.ReadValue() * lookSensitivity;
            _pitch = Mathf.Clamp(_pitch - look.y, -78f, 78f);
            transform.Rotate(0f, look.x, 0f);
            cameraTransform.localRotation = Quaternion.Euler(_pitch, 0f, 0f);
        }
    }

    public sealed class VillageHud : MonoBehaviour
    {
        private void OnGUI()
        {
            if (Time.time > 9f) return;
            var alpha = Time.time < 7f ? 1f : Mathf.InverseLerp(9f, 7f, Time.time);
            var titleStyle = new GUIStyle(GUI.skin.label)
            {
                fontSize = 19,
                fontStyle = FontStyle.Bold,
                normal = { textColor = new Color(1f, 0.94f, 0.78f, alpha) },
            };
            var helpStyle = new GUIStyle(titleStyle)
            {
                fontSize = 14,
                fontStyle = FontStyle.Normal,
                normal = { textColor = new Color(0.94f, 0.93f, 0.85f, alpha) },
            };
            GUI.Label(new Rect(22f, 18f, 420f, 28f), "RIVERSIDE VILLAGE", titleStyle);
            GUI.Label(new Rect(22f, 45f, 820f, 26f), "WASD move   •   mouse look   •   Shift sprint   •   E talk   •   R replay event   •   Esc release cursor", helpStyle);
        }
    }

    public sealed class RiverSurfaceAnimator : MonoBehaviour
    {
        public float amplitude = 0.04f;
        private Mesh _mesh;
        private Vector3[] _baseVertices;
        private Vector3[] _vertices;

        private void Start()
        {
            var filter = GetComponent<MeshFilter>();
            _mesh = Instantiate(filter.sharedMesh);
            _mesh.name = filter.sharedMesh.name + " Animated";
            filter.sharedMesh = _mesh;
            _baseVertices = _mesh.vertices;
            _vertices = new Vector3[_baseVertices.Length];
        }

        private void Update()
        {
            if (_mesh == null) return;
            for (var i = 0; i < _baseVertices.Length; i++)
            {
                var vertex = _baseVertices[i];
                vertex.y += Mathf.Sin(Time.time * 1.15f + vertex.z * 0.24f + vertex.x * 0.12f) * amplitude;
                _vertices[i] = vertex;
            }
            _mesh.vertices = _vertices;
            _mesh.RecalculateNormals();
        }
    }
}
