using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using Twicetold.Village;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering.Universal;
using Object = UnityEngine.Object;

/// <summary>Run in an isolated project with -batchmode -executeMethod VillagePresentationValidation.Run.</summary>
[InitializeOnLoad]
public static class VillagePresentationValidation
{
    private const string Key = "VillagePresentationValidation.Active";
    private static VillageGoldEventDirector _director;
    private static VillageNpcAnchor[] _actors;
    private static readonly List<string> Results = new();
    private static readonly HashSet<string> Failures = new();
    private static readonly Dictionary<string, int> Observations = new();
    private static readonly Dictionary<string, Vector3> InitialPositions = new();
    private static readonly Dictionary<string, Vector3> LastPositions = new();
    private static readonly Dictionary<string, float> Distances = new();
    private static readonly HashSet<VillageGoldEventState> States = new();
    private static double _deadline;
    private static float _started, _cycleStarted;
    private static bool _initialized, _secondCycle, _sittingCaptured;
    private static float _phaseStarted, _minimumKnee = 360, _maximumKnee;
    private static int _walkingCaptures;
    private static float _maximumSupportGap;
    private static Camera _camera;
    private static string Output => Path.GetFullPath("ValidationArtifacts");

    static VillagePresentationValidation()
    {
        if (!SessionState.GetBool(Key, false)) return;
        _deadline = EditorApplication.timeSinceStartup + 120;
        EditorApplication.update += Tick;
    }

    public static void Run()
    {
        if (!Application.isBatchMode) throw new InvalidOperationException("Run this verifier only in an isolated batch-mode Unity project.");
        SessionState.SetBool(Key, true);
        EditorSceneManager.OpenScene("Assets/Scenes/VillageScene.unity", OpenSceneMode.Single);
        ValidatePathAuthoring();
        _deadline = EditorApplication.timeSinceStartup + 120;
        EditorApplication.update -= Tick;
        EditorApplication.update += Tick;
        EditorApplication.isPlaying = true;
    }

    private static void Tick()
    {
        try
        {
            if (EditorApplication.timeSinceStartup > _deadline) { Failures.Add("Play-mode validation timed out"); Finish(); return; }
            if (!EditorApplication.isPlaying || EditorApplication.isCompiling) return;
            if (!_initialized)
            {
                _director = Object.FindFirstObjectByType<VillageGoldEventDirector>();
                if (_director == null) return;
                _initialized = true;
                Directory.CreateDirectory(Output);
                _actors = Object.FindObjectsByType<VillageNpcAnchor>(FindObjectsSortMode.None);
                Check(_actors.Length == 5, "Exactly five stable characters");
                Check(_actors.Select(a => a.StableId).Distinct().Count() == 5, "Unique stable IDs");
                Check(_actors.Count(a => a.DialogueEnabled) == 2, "Only Henry and Joan offer dialogue");
                foreach (var actor in _actors)
                {
                    Observations[actor.StableId] = 0;
                    InitialPositions[actor.StableId] = actor.transform.position;
                    LastPositions[actor.StableId] = actor.transform.position;
                    Distances[actor.StableId] = 0;
                    actor.ObservationReported += (a, o) => {
                        Observations[a.StableId]++;
                        Check(o.eventId == "forgotten-gold-at-market-bench", "Stable observation contract");
                    };
                    Check(actor.GetComponent<CapsuleCollider>().height < 1.9f, actor.StableId + " human scale");
                    var rig=actor.GetComponentInChildren<VillageRigPresentation>();
                    Check(rig!=null && rig.animator.avatar.isValid && rig.animator.avatar.isHuman,actor.StableId+" uses a valid skinned Humanoid");
                    Check(actor.GetComponentsInChildren<SkinnedMeshRenderer>().Length>=6,actor.StableId+" uses authored face, hair and clothing meshes");
                    Check(actor.GetComponentsInChildren<SkinnedMeshRenderer>().All(r=>r.bones.All(b=>b!=null)),actor.StableId+" clothing and hair share valid bone references");
                    var eyesForward=Vector3.ProjectOnPlane((rig.leftEye.position+rig.rightEye.position)*.5f-rig.animator.GetBoneTransform(HumanBodyBones.Head).position,Vector3.up);
                    Check(Vector3.Dot(eyesForward.normalized,-actor.transform.forward)>.75f,actor.StableId+" visual faces the actor's travel/interaction direction");
                    if (actor.IsDemoFocus)
                    {
                        var called = false;
                        actor.DialogueRequested += a => called = true;
                        actor.RequestDialogue();
                        Check(called, actor.StableId + " dialogue callback");
                    }
                }
                var player = Object.FindFirstObjectByType<VillagePlayerController>();
                player.enabled = false;
                player.GetComponent<CharacterController>().enabled = false;
                player.transform.position = new Vector3(1, 1, -5);
                _camera = player.playerCamera;
                _started = _cycleStarted = Time.time;
                _director.StateChanged += state => { _phaseStarted = Time.time; States.Add(state); Results.Add("STATE " + state + " @ " + (Time.time - _cycleStarted).ToString("F2") + "s"); };
                States.Add(_director.State);
                _director.BeginEvent();
                var builder = Object.FindFirstObjectByType<VillageSceneBootstrap>();
                Check(builder.authoredScenery != null, "Playable village uses saved, editable scenery");
                Check(builder.authoredScenery.GetComponentsInChildren<Transform>().Count(t => t.name == "Modular cottage exterior") == 6, "All six homes use the imported modular exterior");
                Check(builder.authoredRiversideHome.GetComponentsInChildren<Transform>().First(t => t.name == "Striped Porch Awning").childCount == 8, "Joan's porch awning preserves all eight canvas panels");
                Check(builder.authoredMarket != null && builder.authoredRiversideHome != null && builder.authoredEventBench != null, "All choreography landmark references survived serialization");
                Check(builder.authoredScenery.GetComponentsInChildren<Transform>().All(t => GameObjectUtility.GetMonoBehavioursWithMissingScriptCount(t.gameObject) == 0), "Authored scenery has no missing scripts");
                Check(builder.authoredScenery.GetComponentsInChildren<MeshFilter>().All(f => f.sharedMesh != null), "All saved scenery meshes reload");
                Check(builder.authoredScenery.GetComponentsInChildren<Renderer>().All(r => r.sharedMaterials.All(m => m != null && m.shader != null && m.shader.name != "Hidden/InternalErrorShader")), "Authored scenery has valid materials");
                Check(builder.authoredScenery.GetComponentsInChildren<MeshFilter>().Where(f => f.sharedMesh.subMeshCount > 1).All(f => f.GetComponent<Renderer>().enabled && f.GetComponent<Renderer>().sharedMaterials.Length == f.sharedMesh.subMeshCount), "Imported multi-material submeshes remain intact after runtime batching");
                Results.Add("BATCHES " + builder.CombinedSourceRenderers + " source renderers -> " + builder.SceneryBatches + " spatial batches");
                Check(_camera.farClipPlane >= 900, "Long-range camera");
                Check(_camera.GetUniversalAdditionalCameraData().antialiasing == AntialiasingMode.SubpixelMorphologicalAntiAliasing, "SMAA enabled");
                Capture("00-arrival", new Vector3(0, 1.85f, -40), new Vector3(-2, 2, -18));
                Capture("01-village", new Vector3(-9, 11, -10), new Vector3(8, 1.5f, 12));
                Capture("02-horizon", new Vector3(0, 3, -25), new Vector3(0, 14, 130));
                var henry = _actors.First(a => a.StableId == "henry");
                Capture("03-henry", henry.transform.position + new Vector3(-4.6f, 1.7f, -.5f), henry.transform.position + Vector3.up * 1.35f);
                var joan = _actors.First(a => a.StableId == "joan");
                Capture("04-joan", joan.transform.position + new Vector3(-3.5f, 1.4f, -1), joan.transform.position + Vector3.up);
                Capture("07-market-street", new Vector3(-1.8f, 2, 2), new Vector3(15, 1.6f, 10));
                Capture("08-river-bridge", new Vector3(32, 2.3f, 17), new Vector3(41, 1.1f, 25));
                TestDialogueTarget(player.GetComponent<VillageDialogueInteractor>(), henry);
                TestDialogueTarget(player.GetComponent<VillageDialogueInteractor>(), joan);
            }
            foreach (var actor in _actors.Where(a => a.StableId == "mara" || a.StableId == "rowan"))
            {
                var p = actor.transform.position;
                Distances[actor.StableId] += Vector3.Distance(p, LastPositions[actor.StableId]);
                LastPositions[actor.StableId] = p;
                foreach (var hit in Physics.OverlapCapsule(p + Vector3.up * .4f, p + Vector3.up * 1.45f, .22f))
                    if (!hit.transform.IsChildOf(actor.transform) && !hit.isTrigger && hit.bounds.max.y > p.y + .5f) Failures.Add(actor.StableId + " intersects scenery: " + hit.name);
            }
            if (_director.State == VillageGoldEventState.WalkingToBench)
            {
                var fisher = _actors.First(a => a.StableId == "fisherman");
                var animator=fisher.GetComponentInChildren<Animator>();
                var angle = KneeAngle(animator);
                _minimumKnee = Mathf.Min(_minimumKnee, angle); _maximumKnee = Mathf.Max(_maximumKnee, angle);
                var soles = new[]{HumanBodyBones.LeftToes,HumanBodyBones.RightToes}.Select(b=>animator.GetBoneTransform(b).position.y-.015f).ToArray();
                var ground = VillageSceneBootstrap.GroundHeight(fisher.transform.position.x, fisher.transform.position.z);
                _maximumSupportGap = Mathf.Max(_maximumSupportGap, soles.Min() - ground);
                if (!_secondCycle && _walkingCaptures < 3 && Time.time - _cycleStarted > 2.5f + _walkingCaptures * .22f)
                {
                    Capture("walk-" + _walkingCaptures++, fisher.transform.position + new Vector3(-2.8f, 1.4f, 2), fisher.transform.position + Vector3.up * .95f);
                }
            }
            if (_director.State == VillageGoldEventState.CheckingTackle && Time.time - _phaseStarted > .75f && !_sittingCaptured)
            {
                _sittingCaptured = true;
                var fisher = _actors.First(a => a.StableId == "fisherman");
                Capture("05-seated-tackle", fisher.transform.position + new Vector3(-3.5f, 1.7f, -2.5f), fisher.transform.position + Vector3.up * .8f);
                Check(KneeAngle(fisher.GetComponentInChildren<Animator>()) > 65, "Sitting has bent knees");
                Results.Add("SEATED HIP "+fisher.GetComponentInChildren<Animator>().GetBoneTransform(HumanBodyBones.Hips).position);
                var seatHeight=Object.FindFirstObjectByType<VillageSceneBootstrap>().authoredEventBench.position.y+.53f;
                Check(Mathf.Abs(fisher.GetComponentInChildren<Animator>().GetBoneTransform(HumanBodyBones.Hips).position.y-seatHeight)<.16f,"Seated pelvis aligns with the bench support");
            }
            if (_director.State == VillageGoldEventState.Complete && !_secondCycle)
            {
                Results.Add("EVENT_DURATION " + (Time.time - _cycleStarted).ToString("F2") + " seconds");
                Check(Time.time - _cycleStarted < 18, "Event completes in under 18 seconds");
                Check(Observations["henry"] == 1 && Observations["joan"] == 1, "One observation per focus character");
                foreach (var witness in _actors.Where(a => a.IsDemoFocus))
                {
                    var eyes = witness.GetComponentsInChildren<Transform>().Where(t => t.name == "Eye").ToArray();
                    Check(eyes.Length == 2, witness.StableId + " has two authored eye landmarks");
                    var start = eyes.Aggregate(Vector3.zero, (sum, eye) => sum + eye.position) / Mathf.Max(1, eyes.Length);
                    var vector = witness.LastObservation.worldPosition - start;
                    var blocked = Physics.RaycastAll(start, vector.normalized, vector.magnitude, ~0, QueryTriggerInteraction.Ignore)
                        .Any(hit => hit.collider.GetComponentInParent<VillageNpcAnchor>() == null);
                    Check(!blocked, witness.StableId + " has an unobstructed view of the forgotten gold");
                }
                Capture("06-gold-left-behind", new Vector3(2, 2.8f, 3), new Vector3(12, 1.1f, 10));
                _secondCycle = true;
                _director.ResetEvent();
                Check(_actors.Where(a => a.IsDemoFocus).All(a => a.LastObservation == null), "Replay clears presentation observations");
                _cycleStarted = Time.time;
                _director.BeginEvent();
            }
            if (Time.time - _started > 42)
            {
                Check(_director.State == VillageGoldEventState.Complete, "Replay completes");
                Check(Observations["henry"] == 2 && Observations["joan"] == 2, "Replay emits exactly one callback each");
                Check(Observations["mara"] == 0 && Observations["rowan"] == 0, "Ambient characters never report focus event");
                Check(States.Count == 9, "Every event state exercised");
                Check(_maximumKnee - _minimumKnee > 30, "Walking articulates the knee through a full gait cycle");
                Results.Add("Maximum walking support-foot ground gap: " + _maximumSupportGap.ToString("F3") + "m (road surface is 0.09m above terrain)");
                Check(_maximumSupportGap < .145f, "Support foot stays grounded while walking");
                foreach (var id in new[] { "mara", "rowan" })
                {
                    Results.Add(id + " distance travelled: " + Distances[id].ToString("F2") + " metres");
                    Check(Distances[id] > 25f, id + " keeps moving around its route");
                }
                Finish();
            }
        }
        catch (Exception exception) { Failures.Add(exception.ToString()); Finish(); }
    }

    private static void Check(bool condition, string message)
    {
        if (condition) Results.Add("PASS " + message); else Failures.Add(message);
    }

    private static void TestDialogueTarget(VillageDialogueInteractor interactor, VillageNpcAnchor target)
    {
        var position = _camera.transform.position; var rotation = _camera.transform.rotation;
        _camera.transform.position = target.transform.position + new Vector3(-4.5f, 1.68f, 0);
        _camera.transform.LookAt(target.transform.position + Vector3.up * 1.45f);
        Physics.SyncTransforms();
        var method = typeof(VillageDialogueInteractor).GetMethod("FindBestTarget", BindingFlags.NonPublic | BindingFlags.Instance);
        Check(ReferenceEquals(method.Invoke(interactor, null), target), target.StableId + " reachable through actual interaction targeting");
        _camera.transform.SetPositionAndRotation(position, rotation);
    }

    private static float KneeAngle(Animator animator)
    {
        var hip=animator.GetBoneTransform(HumanBodyBones.LeftUpperLeg).position;
        var knee=animator.GetBoneTransform(HumanBodyBones.LeftLowerLeg).position;
        var foot=animator.GetBoneTransform(HumanBodyBones.LeftFoot).position;
        return Vector3.Angle(knee-hip,foot-knee);
    }

    private static void ValidatePathAuthoring()
    {
        var go=new GameObject("Temporary path authoring test");go.AddComponent<MeshFilter>();
        var mat=new Material(Shader.Find("Twicetold/Painterly Village Ground"));go.AddComponent<MeshRenderer>().sharedMaterial=mat;
        var path=go.AddComponent<VillageLandscapePath>();path.points=new[]{new Vector3(-2,0,-30),new Vector3(1,0,-20),new Vector3(0,0,-10)};
        VillageLandscapePathEditor.Rebuild(path);var before=path.authoredMesh.bounds;
        path.width=8;path.points[1]+=Vector3.right*2;VillageLandscapePathEditor.Rebuild(path);
        if(path.authoredMesh.bounds.size.x<=before.size.x || path.authoredMesh.vertexCount<100 || path.authoredMesh.normals.Any(n=>n.y<.95f))
            throw new InvalidOperationException("Editable spline path rebuilding failed.");
        Debug.Log("PATH AUTHORING PASS: knot/width changes rebuild a valid upward-facing mesh.");
        Object.DestroyImmediate(path.authoredMesh);Object.DestroyImmediate(mat);Object.DestroyImmediate(go);
    }

    private static void Capture(string name, Vector3 position, Vector3 target)
    {
        var previousPosition = _camera.transform.position; var previousRotation = _camera.transform.rotation;
        _camera.transform.position = position; _camera.transform.LookAt(target);
        var texture = new RenderTexture(1440, 900, 24, RenderTextureFormat.ARGB32);
        _camera.targetTexture = texture;
        Results.Add("CAPTURE " + name + " position=" + position + " target=" + target);
        UnityEngine.Rendering.RenderPipeline.SubmitRenderRequest(_camera, new UniversalRenderPipeline.SingleCameraRequest { destination = texture });
        var previous = RenderTexture.active; RenderTexture.active = texture;
        var image = new Texture2D(1440, 900, TextureFormat.RGB24, false);
        image.ReadPixels(new Rect(0, 0, 1440, 900), 0, 0); image.Apply();
        File.WriteAllBytes(Path.Combine(Output, name + ".png"), image.EncodeToPNG());
        RenderTexture.active = previous; _camera.targetTexture = null;
        Object.DestroyImmediate(image); Object.DestroyImmediate(texture);
        _camera.transform.SetPositionAndRotation(previousPosition, previousRotation);
    }

    private static void Finish()
    {
        SessionState.SetBool(Key, false);
        EditorApplication.update -= Tick;
        Directory.CreateDirectory(Output);
        Results.AddRange(Failures.Select(f => "FAIL " + f));
        Results.Add(Failures.Count == 0 ? "VALIDATION PASS" : "VALIDATION FAILED");
        File.WriteAllLines(Path.Combine(Output, "validation.txt"), Results);
        Debug.Log(string.Join("\n", Results));
        EditorApplication.Exit(Failures.Count == 0 ? 0 : 1);
    }
}
