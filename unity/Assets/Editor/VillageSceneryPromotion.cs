using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Twicetold.Village;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using Object = UnityEngine.Object;

/// <summary>One-time migration into editable scenery. Refuses to overwrite authored village content.</summary>
public static class VillageSceneryPromotion
{
    public const string Output = "Assets/Art/VillageProduction";
    private const string Audition = "Assets/Art/VillageAudition";
    private const string Models = "Assets/Art/ThirdParty/Quaternius/Village/Models";
    private static Material Timber => AssetDatabase.LoadAssetAtPath<Material>(Audition + "/Materials/Timber.mat");
    private static Material Stone => AssetDatabase.LoadAssetAtPath<Material>(Audition + "/Materials/RockTrim.mat");

    [MenuItem("Tools/Village/Open Playable Village")]
    public static void OpenVillage()
    {
        if (EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) EditorSceneManager.OpenScene("Assets/Scenes/VillageScene.unity");
    }

    public static void Run()
    {
        if (!Application.isBatchMode) throw new InvalidOperationException("Migration runs only in an isolated batch project.");
        try { Promote(); EditorApplication.Exit(0); }
        catch (Exception ex) { Debug.LogException(ex); EditorApplication.Exit(1); }
    }

    private static void Promote()
    {
        if (Directory.Exists(Output)) throw new InvalidOperationException("Production art already exists. Edit the saved prefabs; do not regenerate them.");
        var scene = EditorSceneManager.OpenScene("Assets/Scenes/VillageScene.unity");
        var bootstrap = Object.FindFirstObjectByType<VillageSceneBootstrap>();
        if (bootstrap == null || bootstrap.authoredScenery != null) throw new InvalidOperationException("Expected the untouched procedural VillageScene.");
        Directory.CreateDirectory(Output + "/Prefabs"); Directory.CreateDirectory(Output + "/Materials"); AssetDatabase.Refresh();
        var root = bootstrap.CreateSceneryForAuthoring();
        root.name = "Village Scenery - EDIT THESE PREFABS";
        var houses = new[] { "Ochre Roof Cottage", "Village Inn", "Riverside Home", "Green Roof Cottage", "North Lane House", "Riverwatch Cottage" };
        var scales = new[] { .91f, 1.08f, .91f, .89f, .86f, .85f };
        var oldScales = new[] { 1.08f, 1.42f, 1.08f, 1.04f, .98f, .92f };
        var roofs = new[] { new Color(1, .94f, .84f), new Color(.69f, .71f, .78f), new Color(.90f, .80f, .69f), new Color(.76f, .84f, .78f), new Color(.89f, .64f, .53f), new Color(.74f, .72f, .65f) };
        var plaster = new[] { Color.white, new Color(.95f, .88f, .76f), new Color(.87f, .91f, .83f), new Color(.83f, .90f, .83f), new Color(.97f, .90f, .81f), new Color(.89f, .91f, .91f) };
        for (var i = 0; i < houses.Length; i++)
        {
            var house = root.Find(houses[i]);
            foreach (Transform child in house.Cast<Transform>().ToArray())
                if (child.name != "Garden Fence") Object.DestroyImmediate(child.gameObject);
            var cottage = Instance(Audition + "/Prefabs/RiversideCottage.prefab", house);
            cottage.name = "Modular cottage exterior";
            cottage.transform.localScale = Vector3.one * scales[i];
            // Keep the previous frontage, porch, approach lane and actor landmark positions.
            cottage.transform.localPosition = new Vector3(0, 0, 4 * scales[i] - 2.7f * oldScales[i]);
            var roofMat = CloneMaterial("RoundTiles", "Roof " + i, roofs[i]);
            var wallMat = CloneMaterial("Plaster", "Plaster " + i, plaster[i]);
            foreach (var renderer in cottage.GetComponentsInChildren<Renderer>())
            {
                renderer.sharedMaterials = renderer.sharedMaterials.Select(m => m.name == "RoundTiles" ? roofMat : m.name == "Plaster" ? wallMat : m).ToArray();
                PrefabUtility.RecordPrefabInstancePropertyModifications(renderer);
            }
            if (i == 2) AddPorch(house);
            else
            {
                // Window boxes and doorstep props suggest residents without additional agents.
                for (var side = -1; side <= 1; side += 2)
                {
                    var planter = Crate(house, new Vector3(side * 1.82f * scales[i], .9f, -2.7f * oldScales[i] - .28f), new Vector3(.95f, .19f, .42f));
                    planter.name = "Window herb box";
                    AddHerbs(planter.transform);
                }
                Crate(house, new Vector3(3.3f * scales[i], 0, -2), Vector3.one * .62f);
            }
        }

        var market = bootstrap.authoredMarket;
        foreach (var child in market.Cast<Transform>().ToArray()) Object.DestroyImmediate(child.gameObject);
        var produce = Instance(Audition + "/Prefabs/OrchardStall.prefab", market);
        produce.name = "Henry's Orchard Stall"; produce.transform.localScale = new Vector3(1.45f, 1f, 1.35f);
        var goods = Instance(Audition + "/Prefabs/OrchardStall.prefab", market);
        goods.name = "Neighbouring Provision Stall"; goods.transform.localPosition = new Vector3(-.5f, 0, 6.2f); goods.transform.localRotation = Quaternion.Euler(0, 12, 0); goods.transform.localScale = new Vector3(1.35f, 1.05f, 1.3f);
        var blue = CloneMaterial("CanvasSage", "Provision Canvas Blue", new Color(.35f, .50f, .57f));
        foreach (var renderer in goods.GetComponentsInChildren<Renderer>())
        {
            if (renderer.sharedMaterial.name == "CanvasSage") { renderer.sharedMaterial = blue; PrefabUtility.RecordPrefabInstancePropertyModifications(renderer); }
        }
        // Dry goods instead of a second identical fruit display.
        foreach (var fruit in goods.GetComponentsInChildren<Transform>().Where(t => t.name == "Apple" || t.name == "Pear").ToArray()) fruit.gameObject.SetActive(false);
        for (var i = 0; i < 5; i++)
            Box("Wrapped provisions", market, new Vector3(-2.15f + i * .55f, 1.25f, 6.0f), new Vector3(.36f, .28f, .50f), AssetDatabase.LoadAssetAtPath<Material>(Audition + "/Materials/CanvasCream.mat"));

        foreach (var bench in root.Cast<Transform>().Where(t => t.name == "Village Bench").ToArray())
        {
            foreach (var child in bench.Cast<Transform>().ToArray()) Object.DestroyImmediate(child.gameObject);
            var furniture = Instance(Audition + "/Prefabs/TimberBench.prefab", bench);
            // A compact event bench leaves Joan's diagonal view of the bag clear.
            furniture.transform.localScale = new Vector3(bench == bootstrap.authoredEventBench ? 1f : 1.45f, 1.09f, 1.1f);
            bench.name = bench == bootstrap.authoredEventBench ? "Market Event Bench" : "Wayside Bench";
        }
        var oldCart = root.Find("Empty Village Cart");
        var wagon = Imported("Prop_Wagon", root); wagon.name = "Village Delivery Wagon";
        wagon.transform.SetPositionAndRotation(oldCart.position, oldCart.rotation);
        Object.DestroyImmediate(oldCart.gameObject);
        AddModelColliders(wagon);
        foreach (var stack in root.GetComponentsInChildren<Transform>().Where(t => t.name == "Crate Stack").ToArray())
        {
            foreach (var child in stack.Cast<Transform>().ToArray()) Object.DestroyImmediate(child.gameObject);
            Crate(stack, Vector3.zero, Vector3.one * .9f);
            Crate(stack, new Vector3(1, 0, .2f), Vector3.one * .7f);
            Crate(stack, new Vector3(.05f, .95f, 0), Vector3.one * .65f);
        }
        foreach (var hedge in root.GetComponentsInChildren<Transform>().Where(t => t.name == "Garden Hedge"))
        {
            var nearest = houses.Select(root.Find).OrderBy(h => Vector3.Distance(hedge.position, h.position)).First();
            var p = nearest.InverseTransformPoint(hedge.position); p.z = 6.6f;
            var world = nearest.TransformPoint(p); world.y = VillageSceneBootstrap.GroundHeight(world.x, world.z) + .48f; hedge.position = world;
        }
        // Cohesive timber across the saved docks, bridge, fences, lamp posts and barrel bodies.
        var timberNames = new HashSet<string> { "Dark Oak", "Sunlit Oak", "House Timber", "Weathered Dock Wood", "Barrel Wood", "Market Crates", "Crate Slats" };
        foreach (var renderer in root.GetComponentsInChildren<Renderer>())
        {
            if (renderer.sharedMaterials.Any(m => m != null && timberNames.Contains(m.name)))
                renderer.sharedMaterials = renderer.sharedMaterials.Select(m => timberNames.Contains(m.name) ? Timber : m).ToArray();
        }
        PersistResources(root);
        bootstrap.ReleaseAuthoringResources();
        // Save replacement landmarks as nested prefabs, then save the editable whole scenery.
        foreach (var name in houses) SaveLandmark(root.Find(name), name.Replace(" ", ""));
        SaveLandmark(market, "MarketSquare");
        SaveLandmark(bootstrap.authoredEventBench, "MarketEventBench");
        SaveLandmark(root.Find("Wayside Bench"), "WaysideBench");
        SaveLandmark(wagon.transform, "DeliveryWagon");
        PrefabUtility.SaveAsPrefabAssetAndConnect(root.gameObject, Output + "/Prefabs/VillageScenery.prefab", InteractionMode.AutomatedAction);
        EditorUtility.SetDirty(bootstrap);
        AssetDatabase.SaveAssets(); EditorSceneManager.SaveScene(scene);
        Debug.Log("PROMOTION COMPLETE: six modular homes, two stalls, two benches, delivery wagon, crates, coordinated timber; saved editable scenery with original NPC landmarks.");
    }

    private static GameObject Instance(string path, Transform parent)
    {
        var source = AssetDatabase.LoadAssetAtPath<GameObject>(path);
        if (source == null) throw new InvalidOperationException("Missing prefab " + path);
        var instance = (GameObject)PrefabUtility.InstantiatePrefab(source);
        instance.transform.SetParent(parent, false); instance.transform.localPosition = Vector3.zero; instance.transform.localRotation = Quaternion.identity;
        return instance;
    }

    private static Material CloneMaterial(string source, string name, Color tint)
    {
        var material = new Material(AssetDatabase.LoadAssetAtPath<Material>(Audition + "/Materials/" + source + ".mat")) { name = name, color = tint };
        AssetDatabase.CreateAsset(material, Output + "/Materials/" + name + ".mat"); return material;
    }

    private static GameObject Imported(string name, Transform parent)
    {
        var wrapper = new GameObject(name); wrapper.transform.SetParent(parent, false);
        var model = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(Models + "/" + name + ".fbx"));
        model.transform.SetParent(wrapper.transform, false);
        foreach (var renderer in model.GetComponentsInChildren<Renderer>())
        {
            renderer.sharedMaterials = renderer.sharedMaterials.Select(m => AssetDatabase.LoadAssetAtPath<Material>(Audition + "/Materials/" + m.name.Replace("MI_", "").Replace("_Wear", "") + ".mat")).ToArray();
            PrefabUtility.RecordPrefabInstancePropertyModifications(renderer);
        }
        return wrapper;
    }

    private static GameObject Crate(Transform parent, Vector3 position, Vector3 scale)
    {
        var crate = Imported("Prop_Crate", parent); crate.transform.localPosition = position; crate.transform.localScale = scale; AddModelColliders(crate); return crate;
    }

    private static void AddModelColliders(GameObject root)
    {
        foreach (var filter in root.GetComponentsInChildren<MeshFilter>())
        {
            var collider = filter.gameObject.AddComponent<BoxCollider>(); collider.center = filter.sharedMesh.bounds.center; collider.size = filter.sharedMesh.bounds.size;
        }
    }

    private static void Box(string name, Transform parent, Vector3 position, Vector3 size, Material material, bool collider = false)
    {
        var box = GameObject.CreatePrimitive(PrimitiveType.Cube); box.name = name; box.transform.SetParent(parent, false); box.transform.localPosition = position; box.transform.localScale = size;
        box.GetComponent<Renderer>().sharedMaterial = material;
        if (!collider) Object.DestroyImmediate(box.GetComponent<Collider>());
    }

    private static void AddPorch(Transform house)
    {
        var porch = new GameObject("Joan's Porch - reserved dialogue space").transform; porch.SetParent(house, false);
        Box("Porch Deck", porch, new Vector3(0, .50f, -3.9f), new Vector3(5.7f, .3f, 2.3f), Timber, true);
        porch.Find("Porch Deck").GetComponent<Renderer>().enabled = false;
        for (var i = 0; i < 10; i++) Box("Porch Deck Plank", porch, new Vector3(0, .62f, -4.935f + i * .23f), new Vector3(5.7f, .06f, .22f), Timber);
        Box("Porch Step", porch, new Vector3(0, .17f, -5.2f), new Vector3(2, .34f, .65f), Stone, true);
        Box("Porch Upper Step", porch, new Vector3(0, .33f, -4.95f), new Vector3(2, .32f, .55f), Stone, true);
        foreach (var x in new[] { -2.65f, 2.65f })
        {
            Box("Porch Post", porch, new Vector3(x, 1.8f, -4.85f), new Vector3(.14f, 3.6f, .14f), Timber, true);
            Box("Porch Side Rail", porch, new Vector3(x, 1, -3.9f), new Vector3(.12f, .1f, 1.8f), Timber);
        }
        var canopy = Instance(Audition + "/Prefabs/OrchardStall.prefab", porch);
        PrefabUtility.UnpackPrefabInstance(canopy, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
        foreach (var child in canopy.transform.Cast<Transform>().ToArray()) if (!child.name.StartsWith("Canvas")) Object.DestroyImmediate(child.gameObject);
        canopy.name = "Striped Porch Awning"; canopy.transform.localPosition = new Vector3(0, .72f, -3.88f); canopy.transform.localScale = new Vector3(1.56f, 1, 1.05f);
        Crate(porch, new Vector3(-2.05f, .65f, -3.2f), Vector3.one * .5f);
    }

    private static void AddHerbs(Transform planter)
    {
        var green = AssetDatabase.LoadAssetAtPath<Material>(Audition + "/Materials/Grass.mat");
        for (var i = 0; i < 5; i++)
        {
            var herb = GameObject.CreatePrimitive(PrimitiveType.Sphere); herb.name = "Kitchen Herbs"; herb.transform.SetParent(planter, false);
            herb.transform.localPosition = new Vector3(-.35f + .17f * i, 1.05f, 0); herb.transform.localScale = new Vector3(.25f, .9f, .6f); herb.GetComponent<Renderer>().sharedMaterial = green; Object.DestroyImmediate(herb.GetComponent<Collider>());
        }
    }

    private static void SaveLandmark(Transform root, string name)
    {
        var p = root.localPosition; var q = root.localRotation;
        root.localPosition = Vector3.zero; root.localRotation = Quaternion.identity;
        PrefabUtility.SaveAsPrefabAssetAndConnect(root.gameObject, Output + "/Prefabs/" + name + ".prefab", InteractionMode.AutomatedAction);
        root.localPosition = p; root.localRotation = q; PrefabUtility.RecordPrefabInstancePropertyModifications(root);
    }

    private static void PersistResources(Transform root)
    {
        var catalog = new Mesh { name = "Saved village geometry catalog" };
        AssetDatabase.CreateAsset(catalog, Output + "/VillageGeometry.asset");
        var meshes = root.GetComponentsInChildren<MeshFilter>().Select(f => f.sharedMesh)
            .Concat(root.GetComponentsInChildren<MeshCollider>().Select(c => c.sharedMesh)).Where(m => m != null).Distinct();
        foreach (var mesh in meshes) if (!EditorUtility.IsPersistent(mesh)) AssetDatabase.AddObjectToAsset(mesh, catalog);
        var materials = root.GetComponentsInChildren<Renderer>().SelectMany(r => r.sharedMaterials).Append(RenderSettings.skybox).Where(m => m != null).Distinct();
        var index = 0;
        foreach (var material in materials)
        {
            if (EditorUtility.IsPersistent(material)) continue;
            AssetDatabase.CreateAsset(material, Output + "/Materials/Scenery " + index++ + ".mat");
        }
        AssetDatabase.SaveAssets();
    }
}
