using UnityEngine;

namespace Twicetold.Village
{
    /// <summary>Edit-time spline metadata. Geometry is saved; no per-frame rebuilding or package dependency.</summary>
    [DisallowMultipleComponent]
    public sealed class VillageLandscapePath : MonoBehaviour
    {
        public Vector3[] points;
        [Range(1, 12)] public float width = 5.7f;
        [Range(.01f, .15f)] public float surfaceOffset = .085f;
        [HideInInspector] public Mesh authoredMesh;
    }
}
