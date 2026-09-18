using UnityEngine;

namespace Twicetold.Village
{
    /// <summary>Authoring height profile for saved landscape/path meshes. Preserves the demo's core ground heights.</summary>
    public static class VillageLandscapeProfile
    {
        public static float Height(float x, float z)
        {
            var ground = VillageSceneBootstrap.GroundHeight(x, z);
            var mask = Mathf.SmoothStep(0, 1, Mathf.InverseLerp(57, 125, new Vector2(x, z * .8f).magnitude));
            float Hill(float cx, float cz, float h, float rx, float rz) => h * Mathf.Exp(-Mathf.Pow((x - cx) / rx, 2) - Mathf.Pow((z - cz) / rz, 2));
            var hills = Hill(-145, 80, 27, 85, 110) + Hill(160, 190, 32, 90, 110) + Hill(-115, 275, 69, 115, 100)
                + Hill(95, 410, 104, 170, 120) + Hill(-320, 390, 125, 125, 160) + Hill(360, 345, 99, 135, 140)
                + Hill(-220, -260, 63, 110, 125) + Hill(180, -330, 90, 160, 130) + Hill(-400, -20, 90, 140, 180);
            hills += (Mathf.PerlinNoise(x * .016f + 17, z * .016f + 31) - .48f) * 13 + (Mathf.PerlinNoise(x * .043f + 12, z * .043f + 46) - .5f) * 3;
            // Keep a visible river valley all the way into the landscape.
            var valleyWidth = 24 + Mathf.Max(0, Mathf.Abs(z) - 70) * .16f;
            var river = 1 - Mathf.Exp(-Mathf.Pow((x - River(x, z)) / valleyWidth, 2));
            return Mathf.Lerp(ground, Mathf.Max(-.8f, hills * .82f) * river - .4f * (1 - river), mask);
        }
        private static float River(float x, float z) => 43 + Mathf.Sin(z * .075f) * 2.1f + Mathf.Sin(z * .031f + 1.2f) * 1.2f;
    }
}
