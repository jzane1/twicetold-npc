using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Twicetold.Village;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using Object = UnityEngine.Object;

[InitializeOnLoad]
public static class VillageAssetAuditionValidation
{
    private const string Key = "Village.AssetAuditionValidation";
    private static readonly List<string> Results = new();
    private static VillageAssetAudition _review;
    private static double _deadline;
    private static float _start;
    private static int _phase;
    private static Quaternion _knee;
    private static float _poseStarted, _maximumKneeAngle;
    private static int _errors;
    private const string Output = "ValidationArtifacts/AssetAudition";

    static VillageAssetAuditionValidation()
    {
        if (SessionState.GetBool(Key, false)) { _deadline = EditorApplication.timeSinceStartup + 120; EditorApplication.update += Tick; }
    }

    public static void Run()
    {
        if (!Application.isBatchMode) throw new InvalidOperationException("Run only in an isolated batch project.");
        EditorSceneManager.OpenScene(VillageAssetWorkflow.ScenePath);
        SessionState.SetBool(Key, true);
        _deadline = EditorApplication.timeSinceStartup + 120;
        EditorApplication.update -= Tick; EditorApplication.update += Tick;
        EditorApplication.isPlaying = true;
    }

    private static void Check(bool pass, string description)
    {
        Results.Add((pass ? "PASS " : "FAIL ") + description); if (!pass) _errors++;
    }

    private static void Tick()
    {
        try
        {
            if (EditorApplication.timeSinceStartup > _deadline) throw new TimeoutException();
            if (!EditorApplication.isPlaying || EditorApplication.isCompiling) return;
            if (_review == null)
            {
                _review = Object.FindFirstObjectByType<VillageAssetAudition>(); if (_review == null) return;
                _review.enabled = false;
                Directory.CreateDirectory(Output);
                _start = Time.time;
                Check(_review.character.avatar.isValid && _review.character.avatar.isHuman, "Retargeted character has a valid Humanoid avatar");
                Check(!_review.character.applyRootMotion, "Choreography retains ownership of world movement");
                Check(Object.FindObjectsByType<VillageNpcAnchor>(FindObjectsSortMode.None).Length == 0, "Audition creates no backend NPC identities");
                Check(Object.FindObjectsByType<VillageSceneBootstrap>(FindObjectsSortMode.None).Length == 0, "Saved review scene has no runtime village generator");
                var renderers = Object.FindObjectsByType<Renderer>(FindObjectsSortMode.None);
                Check(renderers.All(r => r.sharedMaterials.All(m => m != null && m.shader != null && m.shader.name != "Hidden/InternalErrorShader")), "All renderers have valid materials/shaders");
                var missing = Object.FindObjectsByType<Transform>(FindObjectsSortMode.None).Sum(t => GameObjectUtility.GetMonoBehavioursWithMissingScriptCount(t.gameObject));
                Check(missing == 0, "No missing scripts in saved scene");
                Results.Add("Scene renderers: " + renderers.Length);
                foreach (var path in AssetDatabase.FindAssets("t:Prefab", new[] { VillageAssetWorkflow.Output + "/Prefabs" }).Select(AssetDatabase.GUIDToAssetPath))
                    Check(AssetDatabase.LoadAssetAtPath<GameObject>(path) != null, "Saved prefab " + Path.GetFileName(path));
                _review.SetPose(0);
            }
            var elapsed = Time.time - _start;
            if (_phase == 0 && elapsed > 1)
            {
                Capture("01-cottage-and-market", new Vector3(13, 8, -15), new Vector3(-2, 2.2f, 3));
                Capture("02-cottage-front", new Vector3(-11, 3.6f, -8), new Vector3(-5, 3, 3));
                Capture("03-market-stall", new Vector3(7.3f, 2.3f, -3.7f), new Vector3(3.5f, 1.4f, 1.5f));
                Capture("04-rig-idle", _review.character.transform.position + new Vector3(1.7f, 1.1f, -3), _review.character.transform.position + Vector3.up * .95f);
                Check(_review.character.GetCurrentAnimatorStateInfo(0).IsName("Idle"), "Idle is playing in actual Play Mode");
                _review.SetPose(1); _poseStarted = Time.time; _phase++;
            }
            if (_phase == 1 && Time.time - _poseStarted > .4f)
            {
                _knee = _review.character.GetBoneTransform(HumanBodyBones.LeftLowerLeg).localRotation;
                Capture("05-rig-walk-a", _review.character.transform.position + new Vector3(2.5f, 1, -2.1f), _review.character.transform.position + Vector3.up * .95f);
                _phase++;
            }
            if (_phase == 2)
                _maximumKneeAngle = Mathf.Max(_maximumKneeAngle, Quaternion.Angle(_knee, _review.character.GetBoneTransform(HumanBodyBones.LeftLowerLeg).localRotation));
            if (_phase == 2 && Time.time - _poseStarted > 1.8f)
            {
                Check(_review.character.GetCurrentAnimatorStateInfo(0).IsName("Walk"), "Walk is playing in actual Play Mode");
                Results.Add("Maximum walking knee excursion=" + _maximumKneeAngle.ToString("F1") + " degrees");
                Check(_maximumKneeAngle > 10, "Retargeted walking changes the knee joint across a full gait cycle");
                Check(Vector3.Distance(_review.character.transform.position, _review.characterHome.position) < .001f, "Walk-in-place does not drift away from the marker");
                Capture("06-rig-walk-b", _review.character.transform.position + new Vector3(2.5f, 1, -2.1f), _review.character.transform.position + Vector3.up * .95f);
                _review.SetPose(2); _poseStarted = Time.time; _phase++;
            }
            if (_phase == 3 && Time.time - _poseStarted > .9f)
            {
                Check(_review.character.GetCurrentAnimatorStateInfo(0).IsName("Sit"), "Seated loop is playing in actual Play Mode");
                var hip = _review.character.GetBoneTransform(HumanBodyBones.Hips).position;
                var knee = _review.character.GetBoneTransform(HumanBodyBones.LeftLowerLeg).position;
                var ankle = _review.character.GetBoneTransform(HumanBodyBones.LeftFoot).position;
                var seatTop = GameObject.Find("Timber bench").GetComponentsInChildren<BoxCollider>().Where(c => c.name == "Seat board").Max(c => c.bounds.max.y);
                Results.Add("Seated hip=" + hip + " knee=" + knee + " ankle=" + ankle);
                Check(Mathf.Abs(hip.y - knee.y) < .25f && knee.y - ankle.y > .22f, "Seated thighs are approximately horizontal, shins vertical");
                Check(hip.y - seatTop > .06f && hip.y - seatTop < .18f, "Seated pelvis clears the bench surface");
                Capture("07-rig-seated", _review.character.transform.position + new Vector3(3, 1.5f, -2), _review.character.transform.position + Vector3.up * .65f);
                Finish();
            }
        }
        catch (Exception ex) { Check(false, ex.ToString()); Finish(); }
    }

    private static void Capture(string name, Vector3 position, Vector3 target)
    {
        var camera = _review.reviewCamera; camera.transform.position = position; camera.transform.LookAt(target);
        var rt = new RenderTexture(1440, 900, 24, RenderTextureFormat.ARGB32);
        RenderPipeline.SubmitRenderRequest(camera, new UniversalRenderPipeline.SingleCameraRequest { destination = rt });
        var previous = RenderTexture.active; RenderTexture.active = rt;
        var image = new Texture2D(1440, 900, TextureFormat.RGB24, false); image.ReadPixels(new Rect(0, 0, 1440, 900), 0, 0); image.Apply();
        File.WriteAllBytes(Path.Combine(Output, name + ".png"), image.EncodeToPNG());
        RenderTexture.active = previous; Object.DestroyImmediate(image); Object.DestroyImmediate(rt);
    }

    private static void Finish()
    {
        SessionState.SetBool(Key, false); EditorApplication.update -= Tick;
        Directory.CreateDirectory(Output); Results.Add(_errors == 0 ? "VALIDATION PASS" : "VALIDATION FAILED");
        File.WriteAllLines(Output + "/validation.txt", Results); Debug.Log(string.Join("\n", Results));
        EditorApplication.Exit(_errors == 0 ? 0 : 1);
    }
}
