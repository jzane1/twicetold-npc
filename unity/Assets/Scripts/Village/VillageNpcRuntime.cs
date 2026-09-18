using System;
using UnityEngine;
using UnityEngine.InputSystem;

namespace Twicetold.Village
{
    [Serializable]
    public sealed class VillageObservation
    {
        public string eventId;
        public string summary;
        public Vector3 worldPosition;
        public float sceneTime;

        public VillageObservation(string eventId, string summary, Vector3 worldPosition)
        {
            this.eventId = eventId;
            this.summary = summary;
            this.worldPosition = worldPosition;
            sceneTime = Time.time;
        }
    }

    /// <summary>
    /// Stable Unity-only attachment seam for an NPC backend. External code can discover an anchor by
    /// StableId, subscribe to DialogueRequested and ObservationReported, and mount components below
    /// BackendAttachmentPoint without depending on the procedural character model.
    /// </summary>
    public sealed class VillageNpcAnchor : MonoBehaviour
    {
        [SerializeField] private string stableId;
        [SerializeField] private string displayName;
        [SerializeField] private string villageRole;
        [SerializeField] private bool demoFocus;
        [SerializeField] private bool dialogueEnabled;
        [SerializeField] private Transform backendAttachmentPoint;
        [SerializeField] private Transform leftHand;
        [SerializeField] private Transform rightHand;
        [SerializeField] private VillageNpcMotion motion;

        public string StableId => stableId;
        public string DisplayName => displayName;
        public string VillageRole => villageRole;
        public bool IsDemoFocus => demoFocus;
        public bool DialogueEnabled => dialogueEnabled;
        public Transform BackendAttachmentPoint => backendAttachmentPoint;
        public Transform LeftHand => leftHand;
        public Transform RightHand => rightHand;
        public VillageNpcMotion Motion => motion;
        public VillageObservation LastObservation { get; private set; }
        public int DialogueRequestCount { get; private set; }

        public event Action<VillageNpcAnchor> DialogueRequested;
        public event Action<VillageNpcAnchor, VillageObservation> ObservationReported;

        public void Configure(
            string id,
            string characterName,
            string role,
            bool isDemoFocus,
            bool canTalk,
            Transform attachmentPoint,
            Transform characterLeftHand,
            Transform characterRightHand,
            VillageNpcMotion characterMotion)
        {
            stableId = id;
            displayName = characterName;
            villageRole = role;
            demoFocus = isDemoFocus;
            dialogueEnabled = canTalk;
            backendAttachmentPoint = attachmentPoint;
            leftHand = characterLeftHand;
            rightHand = characterRightHand;
            motion = characterMotion;
        }

        public void RequestDialogue()
        {
            if (!dialogueEnabled) return;
            DialogueRequestCount++;
            DialogueRequested?.Invoke(this);
        }

        public void ReportObservation(VillageObservation observation)
        {
            LastObservation = observation;
            ObservationReported?.Invoke(this, observation);
        }

        public void ClearPresentationObservation() => LastObservation = null;

        public void LookAtFor(Vector3 worldPosition, float seconds) => motion.BeginLookAt(worldPosition, seconds);
    }

    public sealed class VillageNpcMotion : MonoBehaviour
    {
        private VillageRigPresentation _rig;
        public void ConfigureRig(VillageRigPresentation rig) { _rig = rig; _lastPosition = transform.position; }
        private Transform _visualRoot, _headPivot, _leftArm, _rightArm, _leftLeg, _rightLeg;
        private Transform _leftElbow, _rightElbow, _leftKnee, _rightKnee;
        private Transform _leftAnkle, _rightAnkle;
        private Vector3 _lastPosition, _lookPoint;
        private Quaternion _lookStartRotation;
        private bool _walking, _sitting, _inspecting, _happy, _looking;
        private float _phase, _walkBlend, _sitBlend, _lookEndsAt;
        public bool IsInspecting => _inspecting;

        public void Configure(Transform visualRoot, Transform headPivot, Transform leftArm,
            Transform rightArm, Transform leftLeg, Transform rightLeg)
        {
            _visualRoot = visualRoot; _headPivot = headPivot;
            _leftArm = leftArm; _rightArm = rightArm; _leftLeg = leftLeg; _rightLeg = rightLeg;
            _leftElbow = leftArm.Find("Elbow"); _rightElbow = rightArm.Find("Elbow");
            _leftKnee = leftLeg.Find("Knee"); _rightKnee = rightLeg.Find("Knee");
            _leftAnkle = _leftKnee.Find("Ankle"); _rightAnkle = _rightKnee.Find("Ankle");
            _lastPosition = transform.position;
        }

        public void SetWalking(bool walking, bool happy = false) { _walking = walking; _happy = happy; }
        public void SetSitting(bool sitting) => _sitting = sitting;
        public void SetInspecting(bool inspecting) => _inspecting = inspecting;
        public void BeginLookAt(Vector3 worldPosition, float seconds)
        {
            if (!_looking) _lookStartRotation = transform.rotation;
            _lookPoint = worldPosition;
            _lookEndsAt = Time.time + Mathf.Max(.5f, seconds);
            _looking = true;
        }

        public void ResetMotion()
        {
            _walking = _sitting = _inspecting = _happy = false;
            if (_looking) transform.rotation = _lookStartRotation;
            _looking = false; _phase = _walkBlend = _sitBlend = 0;
            _lastPosition = transform.position;
            if (_rig != null) { _rig.ResetPose(); return; }
            if (_visualRoot == null) return;
            _visualRoot.localPosition = Vector3.zero;
            _visualRoot.localRotation = Quaternion.identity;
            foreach (var joint in new[] { _headPivot, _leftArm, _rightArm, _leftLeg, _rightLeg, _leftElbow, _rightElbow, _leftKnee, _rightKnee, _leftAnkle, _rightAnkle })
                if (joint != null) joint.localRotation = Quaternion.identity;
        }

        private void LateUpdate()
        {
            if (_rig != null)
            {
                Vector3? look = null;
                if (_looking)
                {
                    var flat = _lookPoint - transform.position; flat.y = 0;
                    var active = Time.time < _lookEndsAt;
                    var target = active && flat.sqrMagnitude > .01f ? Quaternion.LookRotation(-flat.normalized) : _lookStartRotation;
                    transform.rotation = Quaternion.Slerp(transform.rotation, target, 1 - Mathf.Exp(-Time.deltaTime * 5));
                    if (active) look = _lookPoint;
                    else if (Quaternion.Angle(transform.rotation, _lookStartRotation) < .5f) _looking = false;
                }
                _rig.Tick(_walking, _sitting, _inspecting, _happy, look);
                return;
            }
            if (_visualRoot == null) return;
            var dt = Time.deltaTime;
            var travel = transform.position - _lastPosition; travel.y = 0;
            _lastPosition = transform.position;
            // Cadence follows distance travelled, not an unrelated wall-clock oscillator.
            _phase += Mathf.Min(travel.magnitude, .2f) * 5.8f;
            _walkBlend = Mathf.MoveTowards(_walkBlend, _walking && travel.sqrMagnitude > .000001f ? 1 : 0, dt * 7);
            _sitBlend = Mathf.MoveTowards(_sitBlend, _sitting ? 1 : 0, dt * 2.6f);
            var left = Mathf.Sin(_phase); var right = -left;
            Pose(_leftLeg, Mathf.Lerp(left * 31 * _walkBlend, 87, _sitBlend), 0, 0, dt);
            Pose(_rightLeg, Mathf.Lerp(right * 31 * _walkBlend, 84, _sitBlend), 0, 0, dt);
            Pose(_leftKnee, Mathf.Lerp(-Mathf.Max(0, left) * 53 * _walkBlend, -88, _sitBlend), 0, 0, dt);
            Pose(_rightKnee, Mathf.Lerp(-Mathf.Max(0, right) * 53 * _walkBlend, -87, _sitBlend), 0, 0, dt);
            // Keep soles level and lower the pelvis onto the support leg, rather than floating
            // both feet whenever the legs rotate. The other leg retains its swing clearance.
            if (_leftAnkle != null) _leftAnkle.localRotation = Quaternion.Inverse(_leftLeg.localRotation * _leftKnee.localRotation);
            if (_rightAnkle != null) _rightAnkle.localRotation = Quaternion.Inverse(_rightLeg.localRotation * _rightKnee.localRotation);
            var leftSole = _leftLeg.localPosition + _leftLeg.localRotation * (Vector3.down * .41f + _leftKnee.localRotation * Vector3.down * .41f);
            var rightSole = _rightLeg.localPosition + _rightLeg.localRotation * (Vector3.down * .41f + _rightKnee.localRotation * Vector3.down * .41f);
            var supportOffset = -(Mathf.Min(leftSole.y, rightSole.y) - .075f);
            var inspect = _inspecting ? 1f : 0f;
            Pose(_leftArm, -left * 22 * _walkBlend + _sitBlend * 22 + inspect * 18, inspect * 15, -5 - inspect * 8, dt);
            Pose(_rightArm, -right * 22 * _walkBlend + _sitBlend * 18 + inspect * 12, -inspect * 12, 5 + inspect * 8, dt);
            Pose(_leftElbow, 12 + inspect * 58 + (_happy ? 8 : 0), 0, 0, dt);
            Pose(_rightElbow, 16 + inspect * 54, 0, 0, dt);
            var breathing = Mathf.Sin(Time.time * 1.8f + transform.position.x) * .003f;
            _visualRoot.localPosition = Vector3.up * (breathing + Mathf.Lerp(supportOffset, -.335f, _sitBlend));
            _visualRoot.localRotation = Quaternion.Euler(-_sitBlend * 5, 0, left * 1.5f * _walkBlend);
            var headPitch = _inspecting ? -25f : 0;
            if (_looking)
            {
                var direction = _lookPoint - (transform.position + Vector3.up * 1.55f);
                var flat = direction; flat.y = 0;
                var target = Time.time < _lookEndsAt && flat.sqrMagnitude > .01f
                    ? Quaternion.LookRotation(-flat.normalized) : _lookStartRotation;
                transform.rotation = Quaternion.Slerp(transform.rotation, target, 1 - Mathf.Exp(-dt * 5));
                if (Time.time < _lookEndsAt) headPitch = Mathf.Clamp(Mathf.Atan2(direction.y, flat.magnitude) * Mathf.Rad2Deg, -32, 20);
                else if (Quaternion.Angle(transform.rotation, _lookStartRotation) < .5f) _looking = false;
            }
            Pose(_headPivot, headPitch, 0, _happy && _walking ? -3 : 0, dt);
        }

        private static void Pose(Transform joint, float x, float y, float z, float dt)
        {
            if (joint != null) joint.localRotation = Quaternion.Slerp(joint.localRotation, Quaternion.Euler(x, y, z), 1 - Mathf.Exp(-dt * 15));
        }
    }

    [DefaultExecutionOrder(100)]
    public sealed class VillageHeldFishingRod : MonoBehaviour
    {
        private VillageNpcMotion _motion;
        private Transform _actor;
        public void Configure(VillageNpcMotion motion, Transform actor) { _motion = motion; _actor = actor; }
        private void LateUpdate()
        {
            if (_actor == null) return;
            var target = _actor.rotation * Quaternion.Euler(_motion.IsInspecting ? -52 : -12, 0, -6);
            transform.rotation = Quaternion.Slerp(transform.rotation, target, 1 - Mathf.Exp(-Time.deltaTime * 8));
        }
    }

    internal static class VillageNpcNavigation
    {
        private static readonly RaycastHit[] Hits = new RaycastHit[24];

        public static bool Step(Transform actor, Vector3 target, float distance)
        {
            var next = Vector3.MoveTowards(actor.position, target, distance);
            var delta = next - actor.position; delta.y = 0;
            if (delta.sqrMagnitude < .000001f) return false;
            var count = Physics.CapsuleCastNonAlloc(actor.position + Vector3.up * .38f,
                actor.position + Vector3.up * 1.48f, .23f, delta.normalized, Hits,
                delta.magnitude + .035f, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore);
            for (var i = 0; i < count; i++)
            {
                if (Hits[i].transform.IsChildOf(actor)) continue;
                return false;
            }
            next.y = VillageSceneBootstrap.GroundHeight(next.x, next.z) + .10f;
            actor.position = next;
            return true;
        }
    }

    public sealed class VillageAmbientWalker : MonoBehaviour
    {
        private VillageNpcMotion _motion;
        private Vector3[] _waypoints;
        private float _speed;
        private float _pauseSeconds;
        private float _pauseUntil;
        private int _targetIndex;

        public void Configure(VillageNpcMotion motion, Vector3[] waypoints, float speed, float pauseSeconds)
        {
            _motion = motion;
            _waypoints = waypoints;
            _speed = speed;
            _pauseSeconds = pauseSeconds;
            _targetIndex = waypoints.Length > 1 ? 1 : 0;
        }

        private void Update()
        {
            if (_waypoints == null || _waypoints.Length < 2) return;
            if (Time.time < _pauseUntil)
            {
                _motion.SetWalking(false);
                return;
            }

            var target = _waypoints[_targetIndex];
            var direction = target - transform.position;
            direction.y = 0f;
            if (direction.sqrMagnitude < 0.08f)
            {
                transform.position = target;
                _targetIndex = (_targetIndex + 1) % _waypoints.Length;
                _pauseUntil = Time.time + _pauseSeconds;
                _motion.SetWalking(false);
                return;
            }

            _motion.SetWalking(VillageNpcNavigation.Step(transform, target, _speed * Time.deltaTime));
            var facing = Quaternion.LookRotation(-direction.normalized, Vector3.up);
            transform.rotation = Quaternion.Slerp(transform.rotation, facing, Time.deltaTime * 7f);
        }
    }

    public enum VillageGoldEventState
    {
        WaitingForPlayer,
        WalkingToBench,
        SittingDown,
        PlacingGold,
        CheckingTackle,
        StandingUp,
        WalkingAway,
        WitnessesNotice,
        Complete,
    }

    public sealed class VillageGoldEventDirector : MonoBehaviour
    {
        private const string EventId = "forgotten-gold-at-market-bench";
        private VillageNpcAnchor _fisherman;
        private VillageNpcAnchor _henry;
        private VillageNpcAnchor _joan;
        private Transform _bench;
        private Transform _goldBag;
        private GameObject _coinSpill;
        private Vector3[] _approachRoute;
        private Vector3[] _exitRoute;
        private Vector3 _seatPosition;
        private Vector3 _bagGroundPosition;
        private Transform _player;
        private int _routeIndex;
        private float _stateStartedAt;
        private Vector3 _bagPlacementStart;
        private Vector3 _sitStartPosition;
        private bool _departureFinished;
        private bool _observationsSent;

        public VillageGoldEventState State { get; private set; } = VillageGoldEventState.WaitingForPlayer;
        public event Action<VillageGoldEventState> StateChanged;

        public void Configure(
            VillageNpcAnchor fisherman,
            VillageNpcAnchor henry,
            VillageNpcAnchor joan,
            Transform bench,
            Transform goldBag,
            GameObject coinSpill,
            Vector3[] approachRoute,
            Vector3[] exitRoute)
        {
            _fisherman = fisherman;
            _henry = henry;
            _joan = joan;
            _bench = bench;
            _goldBag = goldBag;
            _coinSpill = coinSpill;
            _approachRoute = approachRoute;
            _exitRoute = exitRoute;
            _seatPosition = bench.TransformPoint(new Vector3(0.35f, 0f, -0.08f));
            _bagGroundPosition = bench.TransformPoint(new Vector3(1.92f, 0.35f, -0.30f));
            ResetEvent();
        }

        public void BeginEvent()
        {
            if (State != VillageGoldEventState.WaitingForPlayer) return;
            SetState(VillageGoldEventState.WalkingToBench);
            _fisherman.Motion.SetWalking(true);
        }

        public void ResetEvent()
        {
            if (_fisherman == null || _approachRoute == null || _approachRoute.Length < 2) return;
            _fisherman.transform.position = _approachRoute[0];
            _fisherman.transform.rotation = Quaternion.LookRotation(-(_approachRoute[1] - _approachRoute[0]).normalized, Vector3.up);
            _fisherman.Motion.ResetMotion();
            _goldBag.SetParent(_fisherman.LeftHand, false);
            _goldBag.localPosition = new Vector3(0f, -0.27f, -0.05f);
            _goldBag.localRotation = Quaternion.Euler(0f, 0f, -8f);
            _coinSpill.SetActive(false);
            _routeIndex = 1;
            _observationsSent = false;
            _departureFinished = false;
            _henry.Motion.ResetMotion();
            _joan.Motion.ResetMotion();
            _henry.ClearPresentationObservation();
            _joan.ClearPresentationObservation();
            SetState(VillageGoldEventState.WaitingForPlayer);
        }

        private void Start()
        {
            var controller = FindFirstObjectByType<VillagePlayerController>();
            if (controller != null) _player = controller.transform;
        }

        private void Update()
        {
            if (_fisherman == null) return;
            if ((State == VillageGoldEventState.WitnessesNotice || State == VillageGoldEventState.Complete) && !_departureFinished)
            {
                _departureFinished = WalkRoute(_exitRoute, 2.7f, true);
                if (_departureFinished) _fisherman.Motion.SetWalking(false);
            }
            if (State == VillageGoldEventState.Complete && Keyboard.current != null && Keyboard.current.rKey.wasPressedThisFrame)
            {
                ResetEvent();
                BeginEvent();
                return;
            }

            switch (State)
            {
                case VillageGoldEventState.WaitingForPlayer:
                    if (_player != null && Vector3.Distance(_player.position, _bench.position) < 17f) BeginEvent();
                    break;
                case VillageGoldEventState.WalkingToBench:
                    if (WalkRoute(_approachRoute, 2.35f, false))
                    {
                        _sitStartPosition = _fisherman.transform.position;
                        _fisherman.transform.rotation = _bench.rotation;
                        _fisherman.Motion.SetWalking(false);
                        _fisherman.Motion.SetSitting(true);
                        SetState(VillageGoldEventState.SittingDown);
                    }
                    break;
                case VillageGoldEventState.SittingDown:
                    _fisherman.transform.position = Vector3.Lerp(_sitStartPosition, _seatPosition, Mathf.SmoothStep(0, 1, StateAge / .65f));
                    if (StateAge > .7f)
                    {
                        _bagPlacementStart = _goldBag.position;
                        _goldBag.SetParent(transform, true);
                        SetState(VillageGoldEventState.PlacingGold);
                    }
                    break;
                case VillageGoldEventState.PlacingGold:
                    var placement = Mathf.Clamp01(StateAge / .7f);
                    var arc = Mathf.Sin(placement * Mathf.PI) * 0.28f;
                    _goldBag.position = Vector3.Lerp(_bagPlacementStart, _bagGroundPosition, Mathf.SmoothStep(0f, 1f, placement)) + Vector3.up * arc;
                    _goldBag.rotation = Quaternion.Slerp(_goldBag.rotation, _bench.rotation, Time.deltaTime * 5f);
                    if (placement >= 1f)
                    {
                        _goldBag.position = _bagGroundPosition;
                        _coinSpill.SetActive(true);
                        _fisherman.Motion.SetInspecting(true);
                        SetState(VillageGoldEventState.CheckingTackle);
                    }
                    break;
                case VillageGoldEventState.CheckingTackle:
                    if (StateAge > 1.65f)
                    {
                        _fisherman.Motion.SetInspecting(false);
                        _fisherman.Motion.SetSitting(false);
                        SetState(VillageGoldEventState.StandingUp);
                    }
                    break;
                case VillageGoldEventState.StandingUp:
                    _fisherman.transform.position = Vector3.Lerp(_seatPosition, _sitStartPosition, Mathf.SmoothStep(0, 1, StateAge / .6f));
                    if (StateAge > .65f)
                    {
                        _routeIndex = 1;
                        _fisherman.Motion.SetWalking(true, true);
                        SetState(VillageGoldEventState.WalkingAway);
                    }
                    break;
                case VillageGoldEventState.WalkingAway:
                    if (WalkRoute(_exitRoute, 2.7f, true) || Vector3.Distance(_fisherman.transform.position, _bench.position) > 4.5f)
                    {
                        _henry.LookAtFor(_goldBag.position, 2.2f);
                        _joan.LookAtFor(_goldBag.position, 2.2f);
                        SetState(VillageGoldEventState.WitnessesNotice);
                    }
                    break;
                case VillageGoldEventState.WitnessesNotice:
                    if (StateAge > .35f) NotifyWitnesses();
                    if (StateAge > 2.2f) SetState(VillageGoldEventState.Complete);
                    break;
            }
        }

        private float StateAge => Time.time - _stateStartedAt;

        private bool WalkRoute(Vector3[] route, float speed, bool happy)
        {
            if (route == null || route.Length == 0 || _routeIndex >= route.Length) return true;
            var target = route[_routeIndex];
            var direction = target - _fisherman.transform.position;
            direction.y = 0f;
            if (direction.sqrMagnitude < 0.08f)
            {
                _fisherman.transform.position = target;
                _routeIndex++;
                return _routeIndex >= route.Length;
            }

            _fisherman.Motion.SetWalking(VillageNpcNavigation.Step(_fisherman.transform, target, speed * Time.deltaTime), happy);
            var facing = Quaternion.LookRotation(-direction.normalized, Vector3.up);
            _fisherman.transform.rotation = Quaternion.Slerp(_fisherman.transform.rotation, facing, Time.deltaTime * 7f);
            return false;
        }

        private void NotifyWitnesses()
        {
            if (_observationsSent) return;
            _observationsSent = true;
            _henry.ReportObservation(new VillageObservation(
                EventId,
                "Henry saw the fisherman leave the market bench and forget a bag of gold coins beside it.",
                _goldBag.position));
            _joan.ReportObservation(new VillageObservation(
                EventId,
                "Joan saw the fisherman leave the market bench and forget a bag of gold coins beside it.",
                _goldBag.position));
        }

        private void SetState(VillageGoldEventState state)
        {
            State = state;
            _stateStartedAt = Time.time;
            StateChanged?.Invoke(state);
        }
    }

    public sealed class VillageDialogueInteractor : MonoBehaviour
    {
        public Camera playerCamera;
        public float interactionDistance = 5.4f;
        private VillageNpcAnchor[] _targets;
        private VillageNpcAnchor _target;
        private string _statusMessage;
        private float _statusEndsAt;

        private void Start() => _targets = FindObjectsByType<VillageNpcAnchor>(FindObjectsSortMode.None);

        private void Update()
        {
            if (playerCamera == null) return;
            _target = FindBestTarget();
            if (_target == null || Keyboard.current == null || !Keyboard.current.eKey.wasPressedThisFrame) return;
            _target.RequestDialogue();
            _statusMessage = $"{_target.DisplayName} is ready to talk.";
            _statusEndsAt = Time.unscaledTime + 3.2f;
        }

        private VillageNpcAnchor FindBestTarget()
        {
            VillageNpcAnchor best = null;
            var bestScore = float.MaxValue;
            if (_targets == null || _targets.Length == 0) _targets = FindObjectsByType<VillageNpcAnchor>(FindObjectsSortMode.None);
            foreach (var candidate in _targets)
            {
                if (!candidate.DialogueEnabled) continue;
                var targetPoint = candidate.transform.position + Vector3.up * 1.45f;
                var offset = targetPoint - playerCamera.transform.position;
                var distance = offset.magnitude;
                if (distance > interactionDistance) continue;
                var angle = Vector3.Angle(playerCamera.transform.forward, offset);
                if (angle > 36f) continue;
                if (Physics.Raycast(playerCamera.transform.position, offset.normalized, out var hit, distance,
                    Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore) && !hit.transform.IsChildOf(candidate.transform)) continue;
                var score = distance + angle * 0.075f;
                if (score >= bestScore) continue;
                best = candidate;
                bestScore = score;
            }
            return best;
        }

        private void OnGUI()
        {
            var centerX = Screen.width * 0.5f;
            var centerY = Screen.height * 0.5f;
            var crosshair = new GUIStyle(GUI.skin.label)
            {
                alignment = TextAnchor.MiddleCenter,
                fontSize = 18,
                normal = { textColor = new Color(1f, 0.96f, 0.78f, 0.8f) },
            };
            GUI.Label(new Rect(centerX - 12f, centerY - 14f, 24f, 28f), "+", crosshair);

            if (_target != null)
            {
                var prompt = new GUIStyle(GUI.skin.box)
                {
                    alignment = TextAnchor.MiddleCenter,
                    fontSize = 17,
                    fontStyle = FontStyle.Bold,
                    normal = { textColor = new Color(1f, 0.95f, 0.74f) },
                };
                GUI.Box(new Rect(centerX - 170f, Screen.height - 104f, 340f, 42f), $"E   Talk to {_target.DisplayName}", prompt);
            }

            if (Time.unscaledTime < _statusEndsAt)
            {
                var status = new GUIStyle(GUI.skin.box)
                {
                    alignment = TextAnchor.MiddleCenter,
                    fontSize = 14,
                    normal = { textColor = Color.white },
                };
                GUI.Box(new Rect(centerX - 260f, Screen.height - 54f, 520f, 32f), _statusMessage, status);
            }
        }
    }
}
