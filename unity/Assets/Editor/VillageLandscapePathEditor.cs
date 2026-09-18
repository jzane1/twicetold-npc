using System.Collections.Generic;
using Twicetold.Village;
using UnityEditor;
using UnityEngine;

[CustomEditor(typeof(VillageLandscapePath))]
public sealed class VillageLandscapePathEditor : Editor
{
    public override void OnInspectorGUI()
    {
        DrawDefaultInspector();
        EditorGUILayout.HelpBox("Move spline handles in Scene view, then rebuild. The saved mesh is edited explicitly; Play never regenerates it. Width includes the walkable earth, not the feathered verge.", MessageType.Info);
        if (GUILayout.Button("Rebuild saved path mesh")) Rebuild((VillageLandscapePath)target);
    }
    private void OnSceneGUI()
    {
        var path = (VillageLandscapePath)target; if (path.points == null) return;
        for (var i = 0; i < path.points.Length; i++)
        {
            EditorGUI.BeginChangeCheck(); var p = Handles.PositionHandle(path.transform.TransformPoint(path.points[i]), Quaternion.identity);
            if (EditorGUI.EndChangeCheck()) { Undo.RecordObject(path, "Move village path knot"); path.points[i] = path.transform.InverseTransformPoint(p); EditorUtility.SetDirty(path); PrefabUtility.RecordPrefabInstancePropertyModifications(path); }
            Handles.Label(p + Vector3.up * .4f, "Path " + i);
        }
    }
    public static Vector3 Sample(Vector3[] p, int segment, float t)
    {
        var a = p[Mathf.Max(0, segment - 1)]; var b = p[segment]; var c = p[segment + 1]; var d = p[Mathf.Min(p.Length - 1, segment + 2)];
        return .5f * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t * t + (-a + 3 * b - 3 * c + d) * t * t * t);
    }
    public static void Rebuild(VillageLandscapePath path)
    {
        if (path.points == null || path.points.Length < 2) return;
        var samples = new List<Vector3>();
        for (var s = 0; s < path.points.Length - 1; s++)
        {
            var steps = Mathf.Max(2, Mathf.CeilToInt(Vector3.Distance(path.points[s], path.points[s + 1]) / .7f));
            for (var j = 0; j < steps; j++) samples.Add(Sample(path.points, s, j / (float)steps));
        }
        samples.Add(path.points[path.points.Length - 1]);
        var vertices = new List<Vector3>(); var uv = new List<Vector2>(); var triangles = new List<int>(); float length = 0;
        const int cross = 8;
        for (var i = 0; i < samples.Count; i++)
        {
            var tangent = (samples[Mathf.Min(samples.Count - 1, i + 1)] - samples[Mathf.Max(0, i - 1)]).normalized;
            var side = new Vector3(-tangent.z, 0, tangent.x);
            if (i > 0) length += Vector3.Distance(samples[i], samples[i - 1]);
            for (var j = 0; j <= cross; j++)
            {
                var p = samples[i] + side * ((j / (float)cross - .5f) * (path.width + 1.4f));
                var world = path.transform.TransformPoint(p); world.y = VillageLandscapeProfile.Height(world.x, world.z) + path.surfaceOffset;
                vertices.Add(path.transform.InverseTransformPoint(world)); uv.Add(new Vector2(j / (float)cross, length));
                if (i == samples.Count - 1 || j == cross) continue;
                var k = i * (cross + 1) + j; triangles.AddRange(new[] { k, k + 1, k + cross + 1, k + 1, k + cross + 2, k + cross + 1 });
            }
        }
        if (!path.authoredMesh) path.authoredMesh = new Mesh { name = path.name + " spline mesh" };
        Undo.RecordObject(path.authoredMesh, "Rebuild village path");
        path.authoredMesh.Clear(); path.authoredMesh.SetVertices(vertices); path.authoredMesh.SetUVs(0, uv); path.authoredMesh.SetTriangles(triangles, 0); path.authoredMesh.RecalculateNormals(); path.authoredMesh.RecalculateBounds();
        path.GetComponent<MeshFilter>().sharedMesh = path.authoredMesh;
        var mat = path.GetComponent<Renderer>().sharedMaterial;
        if (mat) { Undo.RecordObject(mat, "Path fringe width"); mat.SetFloat("_PathWidth", path.width + 1.4f); mat.SetFloat("_PathLength", length); EditorUtility.SetDirty(mat); }
        EditorUtility.SetDirty(path); EditorUtility.SetDirty(path.authoredMesh);
        PrefabUtility.RecordPrefabInstancePropertyModifications(path);
    }
}
