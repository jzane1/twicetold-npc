using UnityEngine;

namespace Twicetold.Village
{
    /// <summary>Art-only animation adapter. Root movement and all event/identity ownership remain outside the rig.</summary>
    public sealed class VillageRigPresentation : MonoBehaviour
    {
        public Animator animator;
        public Transform leftGrip, rightGrip;
        public Transform leftEye, rightEye;
        [Tooltip("Small visual correction only; never moves the collision or backend anchor.")]
        public float seatedHeightOffset;
        private Transform _actor;
        private string _state;
        private bool _seated;
        private float _transitionEnds, _height;
        private Vector3 _previous;

        public void Initialize(Transform actor)
        {
            _actor = actor; _previous = actor.position;
            animator.applyRootMotion = false;
            animator.cullingMode = AnimatorCullingMode.AlwaysAnimate;
            ResetPose();
        }

        public void ResetPose()
        {
            _seated = false; _transitionEnds = 0; _height = 0;
            transform.localPosition = Vector3.zero;
            _state = "Idle"; animator.speed = 1;
            animator.Play(_state, 0, 0); animator.Update(0);
            if (_actor != null) _previous = _actor.position;
        }

        public void Tick(bool walking, bool sitting, bool inspecting, bool happy, Vector3? lookPoint)
        {
            var speed = Vector3.Distance(_actor.position, _previous) / Mathf.Max(.001f, Time.deltaTime);
            _previous = _actor.position;
            if (sitting != _seated)
            {
                _seated = sitting; _transitionEnds = Time.time + (sitting ? .70f : .65f);
                Play(sitting ? "SitEnter" : "SitExit", .12f);
            }
            if (Time.time >= _transitionEnds)
                Play(sitting ? (inspecting ? "Inspect" : "SitIdle") : walking && speed > .05f ? "Walk" : "Idle", .16f);
            animator.speed = _state == "SitEnter" ? 1.85f : _state == "SitExit" ? 1.6f :
                _state == "Walk" ? Mathf.Clamp(speed / 1.4f, .65f, 1.9f) : 1;
            _height = Mathf.MoveTowards(_height, sitting ? seatedHeightOffset : 0, Time.deltaTime * .5f);
            transform.localPosition = Vector3.up * _height;
            // Hand bones use anatomical axes. Keep presentation prop sockets upright while following the hands.
            leftGrip.rotation = rightGrip.rotation = _actor.rotation;
            if (lookPoint.HasValue)
            {
                var head = animator.GetBoneTransform(HumanBodyBones.Head);
                var direction = lookPoint.Value - head.position;
                var pitch = Mathf.Clamp(Mathf.Atan2(direction.y, new Vector2(direction.x, direction.z).magnitude) * Mathf.Rad2Deg, -27, 12);
                head.rotation = Quaternion.AngleAxis(pitch, _actor.right) * head.rotation;
            }
        }

        private void Play(string state, float blend)
        {
            if (_state == state) return;
            _state = state; animator.CrossFadeInFixedTime(state, blend, 0);
        }
    }

    public sealed partial class VillageSceneBootstrap
    {
        private VillageNpcAnchor CreateRiggedVillager(string objectName, string stableId, string displayName,
            string role, bool focus, bool dialogue, Vector3 position, Quaternion rotation, GameObject visualPrefab)
        {
            var root = Joint(objectName, _villageRoot, position); root.rotation = rotation;
            var collider = root.gameObject.AddComponent<CapsuleCollider>();
            collider.height = 1.78f; collider.radius = .25f; collider.center = Vector3.up * .89f;
            var body = root.gameObject.AddComponent<Rigidbody>(); body.isKinematic = true; body.useGravity = false;
            var visual = Instantiate(visualPrefab, root, false);
            var rig = visual.GetComponent<VillageRigPresentation>();
            if (rig == null) throw new System.InvalidOperationException("Villager visual needs a VillageRigPresentation: " + visualPrefab.name);
            rig.Initialize(root);
            var motion = root.gameObject.AddComponent<VillageNpcMotion>(); motion.ConfigureRig(rig);
            var attachment = Joint("Backend Attachment Point [" + stableId + "]", root, new Vector3(0, 1.3f, .15f));
            var anchor = root.gameObject.AddComponent<VillageNpcAnchor>();
            anchor.Configure(stableId, displayName, role, focus, dialogue, attachment, rig.leftGrip, rig.rightGrip, motion);
            return anchor;
        }
    }
}
