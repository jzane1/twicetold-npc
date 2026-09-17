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

        public void LookAtFor(Vector3 worldPosition, float seconds) => motion.BeginLookAt(worldPosition, seconds);
    }

    public sealed class VillageNpcMotion : MonoBehaviour
    {
        private Transform _visualRoot;
        private Transform _headPivot;
        private Transform _leftArm;
        private Transform _rightArm;
        private Transform _leftLeg;
        private Transform _rightLeg;
        private Vector3 _visualRestPosition;
        private Quaternion _headRestRotation;
        private bool _walking;
        private bool _sitting;
        private bool _inspecting;
        private bool _happy;
        private bool _looking;
        private float _lookEndsAt;
        private Quaternion _lookStartRotation;
        private Quaternion _lookTargetRotation;

        public void Configure(
            Transform visualRoot,
            Transform headPivot,
            Transform leftArm,
            Transform rightArm,
            Transform leftLeg,
            Transform rightLeg)
        {
            _visualRoot = visualRoot;
            _headPivot = headPivot;
            _leftArm = leftArm;
            _rightArm = rightArm;
            _leftLeg = leftLeg;
            _rightLeg = rightLeg;
            _visualRestPosition = visualRoot.localPosition;
            _headRestRotation = headPivot.localRotation;
        }

        public void SetWalking(bool walking, bool happy = false)
        {
            _walking = walking;
            _happy = happy;
        }

        public void SetSitting(bool sitting) => _sitting = sitting;
        public void SetInspecting(bool inspecting) => _inspecting = inspecting;

        public void BeginLookAt(Vector3 worldPosition, float seconds)
        {
            var flatDirection = worldPosition - transform.position;
            flatDirection.y = 0f;
            if (flatDirection.sqrMagnitude < 0.01f) return;
            _lookStartRotation = transform.rotation;
            _lookTargetRotation = Quaternion.LookRotation(-flatDirection.normalized, Vector3.up);
            _lookEndsAt = Time.time + Mathf.Max(0.5f, seconds);
            _looking = true;
        }

        public void ResetMotion()
        {
            _walking = false;
            _sitting = false;
            _inspecting = false;
            _happy = false;
            _looking = false;
            if (_visualRoot != null) _visualRoot.localPosition = _visualRestPosition;
            if (_headPivot != null) _headPivot.localRotation = _headRestRotation;
            if (_leftArm != null) _leftArm.localRotation = Quaternion.identity;
            if (_rightArm != null) _rightArm.localRotation = Quaternion.identity;
            if (_leftLeg != null) _leftLeg.localRotation = Quaternion.identity;
            if (_rightLeg != null) _rightLeg.localRotation = Quaternion.identity;
        }

        private void Update()
        {
            if (_visualRoot == null) return;

            var pace = _happy ? 9.2f : 7.2f;
            var stride = _walking ? Mathf.Sin(Time.time * pace) : 0f;
            var armSwing = _walking ? stride * (_happy ? 34f : 27f) : 0f;
            var legSwing = _walking ? stride * (_happy ? 31f : 24f) : 0f;
            if (_sitting)
            {
                armSwing = _inspecting ? -38f : 8f;
                legSwing = -63f;
            }

            _leftArm.localRotation = Quaternion.Slerp(_leftArm.localRotation, Quaternion.Euler(armSwing, 0f, _inspecting ? -10f : 0f), Time.deltaTime * 9f);
            _rightArm.localRotation = Quaternion.Slerp(_rightArm.localRotation, Quaternion.Euler(-armSwing - (_inspecting ? 24f : 0f), 0f, _inspecting ? 13f : 0f), Time.deltaTime * 9f);
            _leftLeg.localRotation = Quaternion.Slerp(_leftLeg.localRotation, Quaternion.Euler(legSwing, 0f, 0f), Time.deltaTime * 10f);
            _rightLeg.localRotation = Quaternion.Slerp(_rightLeg.localRotation, Quaternion.Euler(_sitting ? legSwing : -legSwing, 0f, 0f), Time.deltaTime * 10f);

            var bob = _walking ? Mathf.Abs(Mathf.Sin(Time.time * pace)) * (_happy ? 0.075f : 0.045f) : Mathf.Sin(Time.time * 1.7f) * 0.012f;
            var poseOffset = _sitting ? -0.27f : 0f;
            _visualRoot.localPosition = Vector3.Lerp(_visualRoot.localPosition, _visualRestPosition + Vector3.up * (poseOffset + bob), Time.deltaTime * 10f);
            var headTarget = _inspecting ? Quaternion.Euler(24f, 0f, 0f) : _headRestRotation;
            _headPivot.localRotation = Quaternion.Slerp(_headPivot.localRotation, headTarget, Time.deltaTime * 7f);

            if (!_looking) return;
            var remaining = _lookEndsAt - Time.time;
            if (remaining <= 0f)
            {
                transform.rotation = Quaternion.Slerp(transform.rotation, _lookStartRotation, Time.deltaTime * 12f);
                if (Quaternion.Angle(transform.rotation, _lookStartRotation) < 0.8f)
                {
                    transform.rotation = _lookStartRotation;
                    _looking = false;
                }
                return;
            }
            transform.rotation = Quaternion.Slerp(transform.rotation, _lookTargetRotation, Time.deltaTime * 4.5f);
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

            _motion.SetWalking(true);
            transform.position = Vector3.MoveTowards(transform.position, target, _speed * Time.deltaTime);
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
            _bagGroundPosition = bench.TransformPoint(new Vector3(2.05f, 0.46f, -0.02f));
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
            _goldBag.localPosition = new Vector3(0f, -0.08f, -0.05f);
            _goldBag.localRotation = Quaternion.Euler(0f, 0f, -8f);
            _coinSpill.SetActive(false);
            _routeIndex = 1;
            _observationsSent = false;
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
            if (State == VillageGoldEventState.Complete && Keyboard.current != null && Keyboard.current.rKey.wasPressedThisFrame)
            {
                ResetEvent();
                BeginEvent();
                return;
            }

            switch (State)
            {
                case VillageGoldEventState.WaitingForPlayer:
                    if (_player != null && Vector3.Distance(_player.position, _bench.position) < 29f) BeginEvent();
                    break;
                case VillageGoldEventState.WalkingToBench:
                    if (WalkRoute(_approachRoute, 1.65f, false))
                    {
                        _fisherman.transform.position = _seatPosition;
                        _fisherman.transform.rotation = _bench.rotation;
                        _fisherman.Motion.SetWalking(false);
                        _fisherman.Motion.SetSitting(true);
                        SetState(VillageGoldEventState.SittingDown);
                    }
                    break;
                case VillageGoldEventState.SittingDown:
                    if (StateAge > 1.35f)
                    {
                        _bagPlacementStart = _goldBag.position;
                        _goldBag.SetParent(transform, true);
                        SetState(VillageGoldEventState.PlacingGold);
                    }
                    break;
                case VillageGoldEventState.PlacingGold:
                    var placement = Mathf.Clamp01(StateAge / 1.15f);
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
                    if (StateAge > 3.1f)
                    {
                        _fisherman.Motion.SetInspecting(false);
                        _fisherman.Motion.SetSitting(false);
                        SetState(VillageGoldEventState.StandingUp);
                    }
                    break;
                case VillageGoldEventState.StandingUp:
                    if (StateAge > 1.15f)
                    {
                        _routeIndex = 1;
                        _fisherman.Motion.SetWalking(true, true);
                        SetState(VillageGoldEventState.WalkingAway);
                    }
                    break;
                case VillageGoldEventState.WalkingAway:
                    if (WalkRoute(_exitRoute, 1.85f, true))
                    {
                        _fisherman.Motion.SetWalking(false);
                        NotifyWitnesses();
                        SetState(VillageGoldEventState.WitnessesNotice);
                    }
                    break;
                case VillageGoldEventState.WitnessesNotice:
                    if (StateAge > 3.6f) SetState(VillageGoldEventState.Complete);
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

            _fisherman.Motion.SetWalking(true, happy);
            _fisherman.transform.position = Vector3.MoveTowards(_fisherman.transform.position, target, speed * Time.deltaTime);
            var facing = Quaternion.LookRotation(-direction.normalized, Vector3.up);
            _fisherman.transform.rotation = Quaternion.Slerp(_fisherman.transform.rotation, facing, Time.deltaTime * 7f);
            return false;
        }

        private void NotifyWitnesses()
        {
            if (_observationsSent) return;
            _observationsSent = true;
            _henry.LookAtFor(_goldBag.position, 2.9f);
            _joan.LookAtFor(_goldBag.position, 2.9f);
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
            _statusMessage = $"Dialogue requested with {_target.DisplayName}. Backend attachment hook fired.";
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
