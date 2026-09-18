using UnityEngine;
using UnityEngine.InputSystem;

namespace Twicetold.Village
{
    /// <summary>Local-only controls for the asset review scene. Never provisions or impersonates a demo NPC.</summary>
    public sealed class VillageAssetAudition : MonoBehaviour
    {
        public Camera reviewCamera;
        public Animator character;
        public Transform characterHome;
        public Transform seat;
        private CharacterController _controller;
        private float _pitch;
        private float _fallSpeed;
        private int _pose;
        private bool _showHelp = true;

        private void Start()
        {
            _controller = GetComponent<CharacterController>();
            Cursor.lockState = CursorLockMode.Locked;
            Cursor.visible = false;
            SetPose(0);
        }

        public void SetPose(int pose)
        {
            _pose = Mathf.Clamp(pose, 0, 2);
            var marker = _pose == 2 ? seat : characterHome;
            character.transform.SetPositionAndRotation(marker.position, marker.rotation);
            character.CrossFadeInFixedTime(new[] { "Idle", "Walk", "Sit" }[_pose], .18f);
        }

        private void Update()
        {
            var keyboard = Keyboard.current;
            if (keyboard == null) return;
            if (keyboard.escapeKey.wasPressedThisFrame) { Cursor.lockState = CursorLockMode.None; Cursor.visible = true; }
            if (Mouse.current != null && Mouse.current.leftButton.wasPressedThisFrame) { Cursor.lockState = CursorLockMode.Locked; Cursor.visible = false; }
            if (keyboard.hKey.wasPressedThisFrame) _showHelp = !_showHelp;
            if (keyboard.digit1Key.wasPressedThisFrame) SetPose(0);
            if (keyboard.digit2Key.wasPressedThisFrame) SetPose(1);
            if (keyboard.digit3Key.wasPressedThisFrame) SetPose(2);
            if (Cursor.lockState != CursorLockMode.Locked) return;
            if (Mouse.current != null)
            {
                var delta = Mouse.current.delta.ReadValue() * .09f;
                transform.Rotate(0, delta.x, 0);
                _pitch = Mathf.Clamp(_pitch - delta.y, -75, 75);
                reviewCamera.transform.localRotation = Quaternion.Euler(_pitch, 0, 0);
            }
            var input = new Vector2((keyboard.dKey.isPressed ? 1 : 0) - (keyboard.aKey.isPressed ? 1 : 0), (keyboard.wKey.isPressed ? 1 : 0) - (keyboard.sKey.isPressed ? 1 : 0));
            var direction = transform.TransformDirection(new Vector3(input.x, 0, input.y).normalized);
            _fallSpeed = _controller.isGrounded ? -2 : _fallSpeed - 20 * Time.deltaTime;
            _controller.Move((direction * (keyboard.leftShiftKey.isPressed ? 6 : 3.5f) + Vector3.up * _fallSpeed) * Time.deltaTime);
        }

        private void OnGUI()
        {
            if (!_showHelp) return;
            GUI.Box(new Rect(18, 18, 510, 115), "ASSET AUDITION  /  separate from the demo village");
            GUI.Label(new Rect(34, 47, 480, 80), "WASD + mouse: explore     Shift: faster     Esc: release mouse\n1: idle     2: walk in place     3: seated     H: hide this panel\nRig is a technical sample, NOT Henry or Joan's final appearance.\nHouse and stall are editable prefab instances in this scene.");
        }

        private void OnDestroy() { Cursor.lockState = CursorLockMode.None; Cursor.visible = true; }
    }
}
