using System.Collections.Generic;
using UnityEngine;

namespace Twicetold.Village
{
    public sealed partial class VillageSceneBootstrap
    {
        // Character dimensions are in metres. Art lives below the motion root; backend anchors do not.
        private Mesh _characterSphere;

        private VillageNpcAnchor CreateVillager(string objectName, string stableId, string displayName,
            string role, bool demoFocus, bool dialogueEnabled, Vector3 position, Quaternion rotation,
            Color tunicColor, Color lowerColor, Color accentColor, Color hairColor, VillagerStyle style)
        {
            var root = Joint(objectName, _villageRoot, position);
            root.rotation = rotation;
            var collider = root.gameObject.AddComponent<CapsuleCollider>();
            collider.radius = 0.25f;
            collider.height = 1.78f;
            collider.center = Vector3.up * 0.89f;
            var body = root.gameObject.AddComponent<Rigidbody>();
            body.isKinematic = true;
            body.useGravity = false;
            var visual = Joint("Tailored Character Rig", root, Vector3.zero);
            var attachment = Joint("Backend Attachment Point [" + stableId + "]", root, new Vector3(0, 1.3f, 0.15f));
            var female = style == VillagerStyle.Homeowner || style == VillagerStyle.Baker;
            var skin = MaterialFor(displayName + " Skin", style == VillagerStyle.Worker
                ? new Color(.53f, .32f, .20f) : new Color(.78f, .55f, .38f), .16f);
            var cloth = MaterialFor(displayName + " Woven Cloth", tunicColor, .06f);
            var lower = MaterialFor(displayName + " Garment", lowerColor, .04f);
            var accent = MaterialFor(displayName + " Trim", accentColor, .06f);
            var hair = MaterialFor(displayName + " Hair", hairColor, .09f);
            var linen = MaterialFor("Natural Linen", new Color(.84f, .79f, .64f), .03f);
            var leather = MaterialFor("Oiled Leather", new Color(.16f, .09f, .045f), .18f);
            var eye = MaterialFor("Character Eyes", new Color(.06f, .045f, .035f), .25f);
            var lips = MaterialFor("Character Lips", new Color(.46f, .24f, .18f), .03f);
            var brass = MaterialFor("Tailoring Brass", new Color(.73f, .51f, .20f), .45f);

            var hips = Profile("Hips", visual, new Vector3(0, .88f, 0), lower,
                new Vector3(0, .21f, .13f), new Vector3(.17f, .23f, .14f), new Vector3(.23f, .20f, .12f));
            Profile("Fitted Tunic", visual, new Vector3(0, .99f, 0), cloth,
                new Vector3(0, .22f, .14f), new Vector3(.10f, .205f, .13f),
                new Vector3(.29f, female ? .235f : .27f, .15f), new Vector3(.40f, .27f, .13f),
                new Vector3(.45f, .19f, .105f), new Vector3(.47f, .10f, .08f));
            Profile("Leather Waist Belt", visual, new Vector3(0, 1.04f, 0), leather,
                new Vector3(0, .222f, .145f), new Vector3(.055f, .217f, .142f));
            Ellipsoid("Belt Clasp", visual, new Vector3(0, 1.066f, -.151f), new Vector3(.045f, .032f, .012f), brass);
            var leftLeg = MakeLeg("Left", visual, -.12f, lower, leather);
            var rightLeg = MakeLeg("Right", visual, .12f, lower, leather);
            if (female)
            {
                Profile("Pleated Skirt", hips, new Vector3(0, -.55f, 0), lower,
                    new Vector3(0, .35f, .235f), new Vector3(.08f, .34f, .23f),
                    new Vector3(.35f, .28f, .18f), new Vector3(.66f, .215f, .14f));
                Profile("Skirt Hem", hips, new Vector3(0, -.55f, 0), accent,
                    new Vector3(0, .354f, .239f), new Vector3(.035f, .35f, .236f));
            }
            var leftArm = MakeArm("Left", visual, -.285f, cloth, linen, skin, out var leftHand);
            var rightArm = MakeArm("Right", visual, .285f, cloth, linen, skin, out var rightHand);
            Ellipsoid("Neck", visual, new Vector3(0, 1.48f, 0), new Vector3(.082f, .11f, .082f), skin);
            var head = Joint("Head Pivot", visual, new Vector3(0, 1.50f, 0));
            Ellipsoid("Sculpted Face", head, new Vector3(0, .14f, -.016f), new Vector3(.145f, .215f, .132f), skin);
            Ellipsoid("Jaw", head, new Vector3(0, .028f, -.04f), new Vector3(female ? .089f : .103f, .089f, .10f), skin);
            Ellipsoid("Nose Bridge", head, new Vector3(0, .12f, -.146f), new Vector3(.028f, .048f, .032f), skin);
            Ellipsoid("Nose Tip", head, new Vector3(0, .099f, -.162f), new Vector3(.037f, .022f, .025f), skin);
            Ellipsoid("Mouth", head, new Vector3(0, .046f, -.132f), new Vector3(.043f, .009f, .006f), lips);
            foreach (var side in new[] { -1f, 1f })
            {
                Ellipsoid("Ear", head, new Vector3(side * .144f, .12f, .005f), new Vector3(.026f, .046f, .022f), skin);
                Ellipsoid("Eye", head, new Vector3(side * .055f, .157f, -.136f), new Vector3(.023f, .012f, .009f), eye);
                Ellipsoid("Brow", head, new Vector3(side * .054f, .189f, -.129f), new Vector3(.034f, female ? .005f : .008f, .01f), hair);
                Ellipsoid("Cheek", head, new Vector3(side * .080f, .10f, -.094f), new Vector3(.047f, .040f, .025f), skin);
            }
            Ellipsoid("Swept Hair", head, new Vector3(0, .282f, .012f), new Vector3(.153f, .098f, .133f), hair);
            Ellipsoid("Side Part", head, new Vector3(-.06f, .255f, -.076f), new Vector3(.09f, .057f, .095f), hair);
            if (female)
            {
                Ellipsoid("Gathered Hair", head, new Vector3(0, .17f, .099f), new Vector3(.14f, .17f, .078f), hair);
                Ellipsoid("Braided Bun", head, new Vector3(0, .205f, .185f), new Vector3(.085f, .087f, .067f), hair);
                foreach (var side in new[] { -1f, 1f })
                    Ellipsoid("Tucked Hair Strand", head, new Vector3(side * .133f, .149f, .034f), new Vector3(.035f, .147f, .075f), hair);
                Profile("Linen Collar", visual, new Vector3(0, 1.40f, 0), linen,
                    new Vector3(0, .18f, .113f), new Vector3(.035f, .12f, .084f));
                // A soft apron and a small brooch read as clothing, not a rectangular body block.
                ClothApron(visual, 1.045f, .53f, .155f, .24f, accent);
                Ellipsoid("Brooch", visual, new Vector3(0, 1.386f, -.143f), new Vector3(.021f, .024f, .014f), brass);
            }
            else
            {
                foreach (var side in new[] { -1f, 1f })
                    Ellipsoid("Waistcoat Panel", visual, new Vector3(side * .137f, 1.285f, -.128f), new Vector3(.10f, .20f, .048f), lower);
                for (var i = 0; i < 4; i++)
                    Ellipsoid("Tunic Button", visual, new Vector3(.022f, 1.16f + i * .068f, -.172f), Vector3.one * .011f, brass);
            }
            if (style == VillagerStyle.Merchant)
            {
                ClothApron(visual, 1.05f, .59f, .17f, .23f, accent);
                Ellipsoid("Apron Bib", visual, new Vector3(0, 1.20f, -.166f), new Vector3(.125f, .16f, .022f), accent);
                Ellipsoid("Apron Pocket", visual, new Vector3(0, .94f, -.197f), new Vector3(.12f, .065f, .013f), lower);
                Ellipsoid("Moustache", head, new Vector3(0, .069f, -.145f), new Vector3(.052f, .016f, .012f), hair);
            }
            if (style == VillagerStyle.Fisherman || style == VillagerStyle.Worker)
            {
                Ellipsoid("Soft Cap", head, new Vector3(0, .309f, .015f), new Vector3(.167f, .087f, .155f), accent);
                Ellipsoid("Cap Peak", head, new Vector3(0, .271f, -.126f), new Vector3(.158f, .018f, .105f), accent);
                Ellipsoid("Short Beard", head, new Vector3(0, .006f, -.054f), new Vector3(.102f, .061f, .091f), hair);
            }
            if (style == VillagerStyle.Baker)
                Ellipsoid("Linen Headscarf", head, new Vector3(0, .29f, .025f), new Vector3(.16f, .096f, .145f), linen);

            var motion = root.gameObject.AddComponent<VillageNpcMotion>();
            motion.Configure(visual, head, leftArm, rightArm, leftLeg, rightLeg);
            var anchor = root.gameObject.AddComponent<VillageNpcAnchor>();
            anchor.Configure(stableId, displayName, role, demoFocus, dialogueEnabled, attachment, leftHand, rightHand, motion);
            return anchor;
        }

        private Transform MakeLeg(string side, Transform visual, float x, Material trousers, Material boots)
        {
            var hip = Joint(side + " Hip", visual, new Vector3(x, .90f, 0));
            Ellipsoid("Trouser Thigh", hip, new Vector3(0, -.205f, 0), new Vector3(.106f, .235f, .113f), trousers);
            var knee = Joint("Knee", hip, new Vector3(0, -.41f, 0));
            Ellipsoid("Trouser Calf", knee, new Vector3(0, -.17f, 0), new Vector3(.082f, .195f, .087f), trousers);
            Ellipsoid("Boot Upper", knee, new Vector3(0, -.31f, 0), new Vector3(.09f, .115f, .105f), boots);
            var ankle = Joint("Ankle", knee, new Vector3(0, -.41f, 0));
            Ellipsoid("Leather Shoe", ankle, new Vector3(0, -.004f, -.044f), new Vector3(.098f, .071f, .155f), boots);
            return hip;
        }

        private void ClothApron(Transform parent, float top, float bottom, float topWidth, float bottomWidth, Material material)
        {
            var vertices = new List<Vector3>(); var indices = new List<int>();
            for (var row = 0; row < 3; row++)
            for (var column = 0; column < 5; column++)
            {
                var t = row / 2f; var across = (column - 2) / 2f;
                vertices.Add(new Vector3(across * Mathf.Lerp(topWidth, bottomWidth, t), Mathf.Lerp(top, bottom, t) + across * across * .015f,
                    -.16f - t * .09f + across * across * .018f));
            }
            for (var row = 0; row < 2; row++)
            for (var column = 0; column < 4; column++)
            {
                var i = row * 5 + column;
                indices.AddRange(new[] { i, i + 1, i + 5, i + 1, i + 6, i + 5 });
            }
            var mesh = new Mesh { name = "Tailored Cloth Apron" };
            mesh.SetVertices(vertices); mesh.SetTriangles(indices, 0); mesh.RecalculateNormals(); mesh.RecalculateBounds();
            CreateMeshObject("Cloth Apron", mesh, Vector3.zero, Vector3.one, material, parent, false);
        }

        private Transform MakeArm(string side, Transform visual, float x, Material cloth, Material cuff, Material skin, out Transform hand)
        {
            var shoulder = Joint(side + " Shoulder", visual, new Vector3(x, 1.38f, 0));
            Ellipsoid("Gathered Sleeve", shoulder, new Vector3(0, -.13f, 0), new Vector3(.10f, .18f, .10f), cloth);
            var elbow = Joint("Elbow", shoulder, new Vector3(0, -.28f, 0));
            Ellipsoid("Rolled Cuff", elbow, new Vector3(0, -.02f, 0), new Vector3(.073f, .05f, .074f), cuff);
            Ellipsoid("Forearm", elbow, new Vector3(0, -.122f, 0), new Vector3(.057f, .125f, .06f), skin);
            hand = Joint(side + " Hand", elbow, new Vector3(0, -.255f, -.009f));
            Ellipsoid("Hand", hand, Vector3.zero, new Vector3(.056f, .082f, .04f), skin);
            Ellipsoid("Thumb", hand, new Vector3(-Mathf.Sign(x) * .04f, .016f, -.025f), new Vector3(.023f, .044f, .023f), skin);
            return shoulder;
        }

        private static Transform Joint(string name, Transform parent, Vector3 position)
        {
            var joint = new GameObject(name).transform;
            joint.SetParent(parent, false);
            joint.localPosition = position;
            return joint;
        }

        private Transform Ellipsoid(string name, Transform parent, Vector3 position, Vector3 radii, Material material)
        {
            _characterSphere ??= SoftSphereMesh();
            return CreateMeshObject(name, _characterSphere, position, radii, material, parent, false).transform;
        }

        private static Mesh SoftSphereMesh()
        {
            const int sides = 12, rings = 8;
            var vertices = new List<Vector3>(); var triangles = new List<int>();
            for (var y = 0; y <= rings; y++)
            for (var x = 0; x <= sides; x++)
            {
                var phi = y * Mathf.PI / rings; var theta = x * Mathf.PI * 2 / sides;
                vertices.Add(new Vector3(Mathf.Sin(phi) * Mathf.Cos(theta), Mathf.Cos(phi), Mathf.Sin(phi) * Mathf.Sin(theta)));
            }
            for (var y = 0; y < rings; y++)
            for (var x = 0; x < sides; x++)
            {
                var a = y * (sides + 1) + x; var b = a + sides + 1;
                triangles.AddRange(new[] { a, a + 1, b, a + 1, b + 1, b });
            }
            var mesh = new Mesh { name = "Shared twelve-sided character sculpt" };
            mesh.SetVertices(vertices); mesh.SetTriangles(triangles, 0);
            mesh.SetNormals(vertices); mesh.RecalculateBounds();
            return mesh;
        }

        // Each profile ring is (height, x radius, z radius); restrained faceting keeps the village aesthetic.
        private Transform Profile(string name, Transform parent, Vector3 position, Material material, params Vector3[] rings)
        {
            const int sides = 14;
            var vertices = new List<Vector3>(); var triangles = new List<int>();
            for (var r = 0; r < rings.Length; r++)
            for (var i = 0; i < sides; i++)
            {
                var angle = i * Mathf.PI * 2 / sides;
                vertices.Add(new Vector3(Mathf.Cos(angle) * rings[r].y, rings[r].x, Mathf.Sin(angle) * rings[r].z));
            }
            for (var r = 0; r < rings.Length - 1; r++)
            for (var i = 0; i < sides; i++)
            {
                var a = r * sides + i; var b = r * sides + (i + 1) % sides;
                triangles.AddRange(new[] { a, a + sides, b, b, a + sides, b + sides });
            }
            var mesh = new Mesh { name = name + " tailored profile" };
            mesh.SetVertices(vertices); mesh.SetTriangles(triangles, 0); mesh.RecalculateNormals(); mesh.RecalculateBounds();
            return CreateMeshObject(name, mesh, position, Vector3.one, material, parent, false).transform;
        }
    }
}
