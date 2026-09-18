using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Twicetold.Village;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using Object = UnityEngine.Object;

/// <summary>Explicit, edit-time asset authoring. Never runs in VillageScene or regenerates user edits on load.</summary>
public static class VillageAssetWorkflow
{
    public const string Output = "Assets/Art/VillageAudition";
    public const string ScenePath = "Assets/Scenes/VillageAssetAudition.unity";
    private const string Source = "Assets/Art/ThirdParty/Quaternius";
    private static readonly Dictionary<string, Material> Materials = new();

    [MenuItem("Tools/Village/Assets/Open Asset Audition")]
    public static void Open()
    {
        if (EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) EditorSceneManager.OpenScene(ScenePath);
    }

    [MenuItem("Tools/Village/Assets/Create Fresh Audition")]
    public static void CreateFresh()
    {
        if (AssetDatabase.LoadAssetAtPath<SceneAsset>(ScenePath) != null)
        {
            EditorUtility.DisplayDialog("Audition already exists", "Open the saved scene to edit its prefab instances. This command never overwrites an existing audition or your prefab changes.", "OK");
            return;
        }
        if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
        Build();
    }

    public static void BuildBatch()
    {
        if (!Application.isBatchMode) throw new InvalidOperationException("Batch entry point only.");
        try { Build(); EditorApplication.Exit(0); }
        catch (Exception ex) { Debug.LogException(ex); EditorApplication.Exit(1); }
    }

    private static void Build()
    {
        // Fail closed: artist-authored assets must never be silently regenerated.
        if (File.Exists(ScenePath) || Directory.Exists(Output)) throw new InvalidOperationException("Audition output already exists; edit it normally rather than regenerating it.");
        Directory.CreateDirectory(Output + "/Materials");
        Directory.CreateDirectory(Output + "/Prefabs");
        Directory.CreateDirectory(Output + "/Animation");
        AssetDatabase.Refresh();
        ConfigureImports();
        CreateMaterials();
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        var cottage = BuildCottage();
        SavePrefab(cottage, "RiversideCottage");
        cottage.transform.position = new Vector3(-5, 0, 5);
        var stall = BuildStall();
        SavePrefab(stall, "OrchardStall");
        stall.transform.position = new Vector3(3.5f, 0, 1.5f);
        stall.transform.rotation = Quaternion.Euler(0, -12, 0);
        var bench = BuildBench();
        SavePrefab(bench, "TimberBench");
        bench.transform.position = new Vector3(2.3f, 0, -3.5f);
        var actor = BuildCharacter();
        SavePrefab(actor, "HumanoidRetargetSample");
        actor.transform.position = new Vector3(7, 0, -4.5f);
        actor.transform.rotation = Quaternion.Euler(0, 180, 0);
        var home = new GameObject("Standing marker - no NPC identity").transform;
        home.SetPositionAndRotation(actor.transform.position, actor.transform.rotation);
        var seat = new GameObject("Seat marker - tune to animation").transform;
        seat.position = bench.transform.position;
        seat.rotation = Quaternion.Euler(0, 180, 0);

        var world = new GameObject("Review garden").transform;
        Box("Meadow", world, new Vector3(0, -.21f, 0), new Vector3(1000, .4f, 1000), Materials["Grass"], true);
        Box("Packed-earth lane", world, new Vector3(0, -.004f, -5), new Vector3(23, .025f, 3.5f), Materials["Path"], false);
        Box("Cottage approach", world, new Vector3(-5, .002f, -.8f), new Vector3(2.2f, .035f, 6), Materials["Path"], false);
        for (var i = 0; i < 5; i++)
        {
            var rock = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            rock.name = "Distant wooded ridge " + i;
            rock.transform.SetParent(world);
            rock.transform.position = new Vector3(-60 + 30 * i, -5, 78 + 8 * (i % 2));
            rock.transform.localScale = new Vector3(50, 23 + i * 3, 32);
            rock.GetComponent<Renderer>().sharedMaterial = Materials["Horizon"];
            Object.DestroyImmediate(rock.GetComponent<Collider>());
        }
        for (var i = 0; i < 7; i++)
        {
            var shrub = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            shrub.name = "Garden shrub";
            shrub.transform.SetParent(world);
            shrub.transform.position = new Vector3(-10 + i * 3.5f, .5f, 11 + (i % 2));
            shrub.transform.localScale = new Vector3(2.2f, 1.7f, 2.1f);
            shrub.GetComponent<Renderer>().sharedMaterial = Materials["Grass"];
            Object.DestroyImmediate(shrub.GetComponent<Collider>());
        }
        var wagon = Model("Prop_Wagon", world, new Vector3(-10, 0, 0), 25);
        var barrelCrate = Model("Prop_Crate", world, new Vector3(-9.4f, 0, -2.2f));
        AddBoundsCollider(barrelCrate);
        AddBoundsCollider(wagon);
        Lighting();
        var player = new GameObject("Asset Review Explorer");
        player.transform.position = new Vector3(1, .1f, -11);
        var controller = player.AddComponent<CharacterController>();
        controller.height = 1.8f; controller.radius = .3f; controller.center = Vector3.up * .9f; controller.stepOffset = .3f;
        var camera = new GameObject("Review Camera").AddComponent<Camera>();
        camera.tag = "MainCamera";
        camera.transform.SetParent(player.transform, false);
        camera.transform.localPosition = Vector3.up * 1.68f;
        camera.fieldOfView = 62; camera.farClipPlane = 800; camera.nearClipPlane = .06f;
        camera.allowHDR = true;
        camera.GetUniversalAdditionalCameraData().antialiasing = AntialiasingMode.SubpixelMorphologicalAntiAliasing;
        camera.GetUniversalAdditionalCameraData().antialiasingQuality = AntialiasingQuality.High;
        camera.GetUniversalAdditionalCameraData().renderPostProcessing = true;
        camera.gameObject.AddComponent<AudioListener>();
        var review = player.AddComponent<VillageAssetAudition>();
        review.reviewCamera = camera; review.character = actor.GetComponentInChildren<Animator>(); review.characterHome = home; review.seat = seat;
        AssetDatabase.SaveAssets();
        EditorSceneManager.SaveScene(scene, ScenePath);
        Debug.Log("ASSET AUDITION BUILT. VillageScene and build settings unchanged.");
    }

    private static void ConfigureImports()
    {
        foreach (var guid in AssetDatabase.FindAssets("t:Texture2D", new[] { Source }))
        {
            var importer = (TextureImporter)AssetImporter.GetAtPath(AssetDatabase.GUIDToAssetPath(guid));
            importer.maxTextureSize = 2048;
            importer.anisoLevel = 4;
            importer.mipmapEnabled = true;
            importer.textureType = importer.assetPath.Contains("_Normal") ? TextureImporterType.NormalMap : TextureImporterType.Default;
            importer.SaveAndReimport();
        }
        foreach (var path in new[] { Source + "/Character/Models/Superhero_Male_FullBody.fbx", Source + "/Animation/UAL1_Standard.fbx" })
        {
            var importer = (ModelImporter)AssetImporter.GetAtPath(path);
            importer.animationType = ModelImporterAnimationType.Human;
            importer.avatarSetup = ModelImporterAvatarSetup.CreateFromThisModel;
            importer.importCameras = importer.importLights = false;
            if (path.Contains("Animation/"))
            {
                var clips = importer.defaultClipAnimations;
                foreach (var clip in clips)
                {
                    clip.loopTime = clip.name.EndsWith("_Loop");
                    clip.lockRootRotation = true; clip.lockRootPositionXZ = true;
                    // Keep hip-height changes for sitting; the director will own world movement.
                    clip.lockRootHeightY = true; clip.keepOriginalPositionY = true;
                }
                importer.clipAnimations = clips;
            }
            importer.SaveAndReimport();
        }
    }

    private static Material MakeMaterial(string name, Color color, string texture = null, string normal = null)
    {
        var mat = new Material(Shader.Find("Universal Render Pipeline/Lit")) { name = name, color = color, enableInstancing = true };
        mat.SetFloat("_Smoothness", .16f);
        if (texture != null) mat.SetTexture("_BaseMap", AssetDatabase.LoadAssetAtPath<Texture2D>(texture));
        if (normal != null) { mat.SetTexture("_BumpMap", AssetDatabase.LoadAssetAtPath<Texture2D>(normal)); mat.SetFloat("_BumpScale", .6f); mat.EnableKeyword("_NORMALMAP"); }
        AssetDatabase.CreateAsset(mat, Output + "/Materials/" + name + ".mat");
        Materials[name] = mat;
        return mat;
    }

    private static void CreateMaterials()
    {
        Materials.Clear();
        foreach (var name in new[] { "WoodTrim", "Plaster", "UnevenBrick", "RoundTiles", "Brick", "RockTrim" })
        {
            var tint = name == "RoundTiles" ? new Color(.90f, .77f, .56f) : Color.white;
            MakeMaterial(name, tint, Source + "/Village/Textures/T_" + name + "_BaseColor.png", Source + "/Village/Textures/T_" + name + "_Normal.png");
        }
        MakeMaterial("WindowGlass", new Color(.36f, .55f, .59f));
        var timber = MakeMaterial("Timber", new Color(.84f, .83f, .76f), Source + "/Village/Textures/T_WoodTrim_BaseColor.png", Source + "/Village/Textures/T_WoodTrim_Normal.png");
        timber.SetTextureScale("_BaseMap", new Vector2(.85f, .18f)); timber.SetTextureOffset("_BaseMap", new Vector2(.05f, .73f));
        MakeMaterial("CanvasSage", new Color(.49f, .58f, .34f));
        MakeMaterial("CanvasCream", new Color(.86f, .79f, .57f));
        foreach (var name in new[] { "CanvasSage", "CanvasCream" }) { Materials[name].SetFloat("_Cull", 0); Materials[name].doubleSidedGI = true; }
        MakeMaterial("Apples", new Color(.65f, .12f, .07f));
        MakeMaterial("Pears", new Color(.68f, .67f, .16f));
        MakeMaterial("Grass", new Color(.32f, .47f, .22f));
        MakeMaterial("Path", new Color(.70f, .60f, .41f));
        MakeMaterial("Horizon", new Color(.33f, .46f, .43f));
        MakeMaterial("RigBody", Color.white, Source + "/Character/Textures/T_Superhero_Male_Ligh.png");
        MakeMaterial("RigEyes", Color.white, Source + "/Character/Textures/T_Eye_Brown.png");
        MakeMaterial("RigHair", new Color(.13f, .08f, .045f));
    }

    private static GameObject Model(string name, Transform parent, Vector3 position, float yaw = 0)
    {
        var source = AssetDatabase.LoadAssetAtPath<GameObject>(Source + "/Village/Models/" + name + ".fbx");
        if (source == null) throw new InvalidOperationException("Missing model " + name);
        // Place/scale a wrapper, preserving the FBX's original axis correction and scale.
        var wrapper = new GameObject(name);
        wrapper.transform.SetParent(parent, false);
        wrapper.transform.localPosition = position; wrapper.transform.localRotation = Quaternion.Euler(0, yaw, 0);
        var model = (GameObject)PrefabUtility.InstantiatePrefab(source);
        model.transform.SetParent(wrapper.transform, false);
        foreach (var renderer in model.GetComponentsInChildren<Renderer>())
            renderer.sharedMaterials = renderer.sharedMaterials.Select(m => Materials[m.name.Replace("MI_", "").Replace("_Wear", "")]).ToArray();
        return wrapper;
    }

    private static void Box(string name, Transform parent, Vector3 position, Vector3 scale, Material material, bool collider = false)
    {
        var box = GameObject.CreatePrimitive(PrimitiveType.Cube);
        box.name = name; box.transform.SetParent(parent, false); box.transform.localPosition = position; box.transform.localScale = scale;
        box.GetComponent<Renderer>().sharedMaterial = material.name == "WoodTrim" ? Materials["Timber"] : material;
        if (!collider) Object.DestroyImmediate(box.GetComponent<Collider>());
    }

    private static GameObject BuildCottage()
    {
        var house = new GameObject("Riverside cottage - modular FBX"); var root = house.transform;
        Box("Stone footing", root, new Vector3(0, .12f, 0), new Vector3(6.3f, .24f, 8.3f), Materials["RockTrim"], true);
        for (var x = -2; x <= 2; x += 2)
        {
            Model(x == 0 ? "Wall_Plaster_Door_Round" : "Wall_Plaster_Window_Wide_Flat", root, new Vector3(x, .24f, -4), 180);
            Model("Wall_Plaster_WoodGrid", root, new Vector3(x, .24f, 4));
            if (x != 0)
            {
                Model("Window_Wide_Flat1", root, new Vector3(x, .24f, -4), 180);
                Model("WindowShutters_Wide_Flat_Open", root, new Vector3(x, .24f, -4), 180);
            }
        }
        for (var z = -3; z <= 3; z += 2)
        {
            Model("Wall_Plaster_WoodGrid", root, new Vector3(-3, .24f, z), -90);
            Model("Wall_Plaster_Straight", root, new Vector3(3, .24f, z), 90);
        }
        Model("DoorFrame_Round_WoodDark", root, new Vector3(0, .24f, -4.03f), 180);
        Model("Door_1_Round", root, new Vector3(-.514f, .24f, -4.02f), 180);
        Model("Roof_RoundTiles_6x8", root, new Vector3(0, 3.24f, 0));
        Model("Roof_Front_Brick6", root, new Vector3(0, 3.24f, -4), 180);
        Model("Roof_Front_Brick6", root, new Vector3(0, 3.24f, 4));
        Model("Prop_Chimney", root, new Vector3(1.9f, 5.6f, 1.8f));
        Box("Entry step", root, new Vector3(0, .10f, -4.5f), new Vector3(1.8f, .2f, .85f), Materials["RockTrim"], true);
        // Intentionally closed exterior; simple collision does not depend on ornate mesh topology.
        var hull = root.gameObject.AddComponent<BoxCollider>(); hull.center = new Vector3(0, 1.7f, 0); hull.size = new Vector3(6, 3.4f, 8);
        return house;
    }

    private static GameObject BuildStall()
    {
        var stall = new GameObject("Orchard stall - textured timber and tailored canvas"); var root = stall.transform;
        foreach (var x in new[] { -1.65f, 1.65f }) foreach (var z in new[] { -.8f, .8f })
            Box("Oak post", root, new Vector3(x, 1.28f, z), new Vector3(.12f, 2.56f, .12f), Materials["WoodTrim"]);
        Box("Counter", root, new Vector3(0, .86f, 0), new Vector3(3.5f, .16f, 1.45f), Materials["WoodTrim"], true);
        Box("Front fascia", root, new Vector3(0, .68f, -.72f), new Vector3(3.5f, .28f, .08f), Materials["WoodTrim"]);
        foreach (var x in new[] { -1.6f, 1.6f })
            Box("Canopy stretcher", root, new Vector3(x, 2.5f, 0), new Vector3(.1f, .1f, 1.8f), Materials["WoodTrim"]);
        for (var stripe = 0; stripe < 8; stripe++)
        {
            var vertices = new List<Vector3>(); var triangles = new List<int>();
            for (var edge = 0; edge < 2; edge++) for (var j = 0; j <= 12; j++)
            {
                var z = -1.15f + j * 2.3f / 12;
                var y = 2.55f + .26f * Mathf.Cos(z / 1.15f * Mathf.PI / 2);
                if (j == 0) y -= .19f;
                vertices.Add(new Vector3(-1.85f + (stripe + edge) * 3.7f / 8, y, z));
            }
            for (var j = 0; j < 12; j++) { triangles.AddRange(new[] { j, j + 1, j + 13, j + 1, j + 14, j + 13 }); }
            var mesh = new Mesh { name = "Canvas stripe " + stripe }; mesh.SetVertices(vertices); mesh.SetTriangles(triangles, 0); mesh.RecalculateNormals(); mesh.RecalculateBounds();
            AssetDatabase.CreateAsset(mesh, Output + "/CanvasStripe" + stripe + ".asset");
            var cloth = new GameObject(mesh.name); cloth.transform.SetParent(root, false); cloth.AddComponent<MeshFilter>().sharedMesh = mesh; cloth.AddComponent<MeshRenderer>().sharedMaterial = Materials[stripe % 2 == 0 ? "CanvasSage" : "CanvasCream"];
        }
        for (var i = 0; i < 3; i++)
        {
            var crate = Model("Prop_Crate", root, new Vector3(-1.05f + i * 1.05f, .94f, 0)); crate.transform.localScale = new Vector3(.80f, .24f, .80f);
            for (var j = 0; j < 12; j++)
            {
                var fruit = GameObject.CreatePrimitive(PrimitiveType.Sphere); fruit.name = i == 1 ? "Pear" : "Apple";
                fruit.transform.SetParent(root, false); fruit.transform.localPosition = new Vector3(-1.05f + i * 1.05f + (j % 4 - 1.5f) * .17f, 1.20f, (j / 4 - 1) * .19f);
                fruit.transform.localScale = new Vector3(.16f, i == 1 ? .21f : .16f, .16f); fruit.GetComponent<Renderer>().sharedMaterial = Materials[i == 1 ? "Pears" : "Apples"];
                Object.DestroyImmediate(fruit.GetComponent<Collider>());
            }
        }
        Model("Prop_Crate", root, new Vector3(2.1f, 0, .5f)).transform.localScale = Vector3.one * .75f;
        Model("Prop_Crate", root, new Vector3(2.12f, .79f, .51f), 8).transform.localScale = Vector3.one * .65f;
        return stall;
    }

    private static GameObject BuildBench()
    {
        var bench = new GameObject("Timber bench");
        for (var i = 0; i < 3; i++) Box("Seat board", bench.transform, new Vector3(0, .40f, -.25f + i * .22f), new Vector3(2.2f, .08f, .2f), Materials["WoodTrim"], true);
        foreach (var x in new[] { -.8f, .8f })
        {
            Box("Bench leg", bench.transform, new Vector3(x, .19f, 0), new Vector3(.15f, .38f, .5f), Materials["WoodTrim"], true);
            Box("Back upright", bench.transform, new Vector3(x, .64f, .33f), new Vector3(.1f, .8f, .1f), Materials["WoodTrim"]);
        }
        Box("Back rail", bench.transform, new Vector3(0, .86f, .34f), new Vector3(2.2f, .28f, .08f), Materials["WoodTrim"]);
        return bench;
    }

    private static GameObject BuildCharacter()
    {
        var source = AssetDatabase.LoadAssetAtPath<GameObject>(Source + "/Character/Models/Superhero_Male_FullBody.fbx");
        var actor = (GameObject)PrefabUtility.InstantiatePrefab(source);
        actor.name = "Humanoid sample - not final villager art";
        actor.transform.localScale = Vector3.one * .94f;
        foreach (var renderer in actor.GetComponentsInChildren<Renderer>()) renderer.sharedMaterials = renderer.sharedMaterials.Select(m => Materials[m.name.Contains("Eyes") ? "RigEyes" : m.name.Contains("Hair") ? "RigHair" : "RigBody"]).ToArray();
        var animator = actor.GetComponent<Animator>();
        if (animator == null || animator.avatar == null || !animator.avatar.isHuman || !animator.avatar.isValid) throw new InvalidOperationException("Humanoid mapping failed.");
        var controller = AnimatorController.CreateAnimatorControllerAtPath(Output + "/Animation/Audition.controller");
        var clips = AssetDatabase.LoadAllAssetsAtPath(Source + "/Animation/UAL1_Standard.fbx").OfType<AnimationClip>().ToArray();
        foreach (var pair in new[] { ("Idle", "Idle_Loop"), ("Walk", "Walk_Loop"), ("Sit", "Sitting_Idle_Loop") })
        {
            var state = controller.layers[0].stateMachine.AddState(pair.Item1);
            state.motion = clips.Single(c => c.name == "Armature|" + pair.Item2); state.iKOnFeet = true;
            if (pair.Item1 == "Idle") controller.layers[0].stateMachine.defaultState = state;
        }
        animator.runtimeAnimatorController = controller; animator.applyRootMotion = false; animator.cullingMode = AnimatorCullingMode.AlwaysAnimate;
        return actor;
    }

    private static void SavePrefab(GameObject instance, string name)
    {
        PrefabUtility.SaveAsPrefabAssetAndConnect(instance, Output + "/Prefabs/" + name + ".prefab", InteractionMode.AutomatedAction);
    }

    private static void AddBoundsCollider(GameObject instance)
    {
        foreach (var filter in instance.GetComponentsInChildren<MeshFilter>())
        {
            var collider = filter.gameObject.AddComponent<BoxCollider>(); collider.center = filter.sharedMesh.bounds.center; collider.size = filter.sharedMesh.bounds.size;
        }
    }

    private static void Lighting()
    {
        RenderSettings.ambientMode = AmbientMode.Trilight;
        RenderSettings.ambientSkyColor = new Color(.64f, .77f, .91f); RenderSettings.ambientEquatorColor = new Color(.55f, .62f, .51f); RenderSettings.ambientGroundColor = new Color(.31f, .34f, .28f);
        RenderSettings.fog = true; RenderSettings.fogMode = FogMode.Linear; RenderSettings.fogStartDistance = 120; RenderSettings.fogEndDistance = 650; RenderSettings.fogColor = new Color(.64f, .76f, .86f);
        var sun = new GameObject("Review sunlight").AddComponent<Light>(); sun.type = LightType.Directional; sun.intensity = 1.35f; sun.color = new Color(1, .92f, .78f); sun.shadows = LightShadows.Soft; sun.transform.rotation = Quaternion.Euler(43, -32, 0); RenderSettings.sun = sun;
        var sky = new Material(Shader.Find("Skybox/Procedural")); sky.SetFloat("_AtmosphereThickness", .8f); sky.SetFloat("_Exposure", 1.15f); AssetDatabase.CreateAsset(sky, Output + "/Materials/ReviewSky.mat"); RenderSettings.skybox = sky;
        var profile = ScriptableObject.CreateInstance<VolumeProfile>(); profile.Add<Tonemapping>().mode.Override(TonemappingMode.Neutral); AssetDatabase.CreateAsset(profile, Output + "/ReviewVolume.asset");
        foreach (var component in profile.components) AssetDatabase.AddObjectToAsset(component, profile);
        var volume = new GameObject("Review tone mapping").AddComponent<Volume>(); volume.isGlobal = true; volume.sharedProfile = profile;
    }
}
