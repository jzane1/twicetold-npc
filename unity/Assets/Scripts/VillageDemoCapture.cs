#if UNITY_EDITOR
using System;
using System.Collections;
using System.IO;
using UnityEditor;
using UnityEditor.Media;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

/// <summary>Editor-only, camera-native capture; does not record the desktop.</summary>
public sealed class VillageDemoCapture : MonoBehaviour
{
    public bool Recording { get; private set; }
    public int Frames { get; private set; }
    public string Output { get; private set; }
    public string Error { get; private set; }
    private MediaEncoder _encoder;
    private RenderTexture _target;
    private Texture2D _pixels;
    private Camera _camera;
    private int _limit;
    private int _previousCaptureRate;

    public void Begin(string path, Camera camera, int seconds = 20)
    {
        if (Recording) throw new InvalidOperationException("Already recording");
        Output = Path.GetFullPath(path);
        if (File.Exists(Output)) throw new IOException("Capture exists; choose a new filename");
        Directory.CreateDirectory(Path.GetDirectoryName(Output));
        _camera = camera;
        _limit = seconds * 30;
        _target = new RenderTexture(1920, 1080, 24, RenderTextureFormat.ARGB32);
        _pixels = new Texture2D(1920, 1080, TextureFormat.RGBA32, false);
        _encoder = new MediaEncoder(Output, new VideoTrackAttributes {
            frameRate = new MediaRational(30), width = 1920, height = 1080,
            includeAlpha = false, bitRateMode = VideoBitrateMode.High
        });
        Frames = 0;
        Error = null;
        _previousCaptureRate = Time.captureFramerate;
        Time.captureFramerate = 30;
        Recording = true;
        StartCoroutine(Capture());
    }

    private IEnumerator Capture()
    {
        while (Recording && Frames < _limit)
        {
            yield return new WaitForEndOfFrame();
            var previousTarget = _camera.targetTexture;
            var previousActive = RenderTexture.active;
            try
            {
                _camera.targetTexture = _target;
                RenderPipeline.SubmitRenderRequest(_camera, new UniversalRenderPipeline.SingleCameraRequest { destination = _target });
                RenderTexture.active = _target;
                _pixels.ReadPixels(new Rect(0, 0, 1920, 1080), 0, 0);
                _pixels.Apply();
                if (!_encoder.AddFrame(_pixels)) throw new IOException("Unity encoder refused a frame");
                Frames++;
            }
            catch (Exception ex) { Error = ex.ToString(); Recording = false; }
            finally { RenderTexture.active = previousActive; _camera.targetTexture = previousTarget; }
        }
        Finish();
    }

    public void Finish()
    {
        if (_encoder == null) return;
        Recording = false;
        _encoder.Dispose();
        _encoder = null;
        Time.captureFramerate = _previousCaptureRate;
        if (_target != null) Destroy(_target);
        if (_pixels != null) Destroy(_pixels);
    }

    private void OnDestroy() => Finish();
}
#endif
