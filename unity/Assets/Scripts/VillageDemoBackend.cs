using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using NpcMemory;
using Twicetold.Village;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.SceneManagement;

/// <summary>Recording adapter over the village's stable callback seam.</summary>
public sealed class VillageDemoBackend : MonoBehaviour
{
    public string Status { get; private set; } = "Connecting witnesses…";
    public bool Busy => _pending > 0;
    public bool Aborted { get; private set; }
    public int Day { get; private set; }
    public string SelectedWitness { get; private set; } = "henry";
    public string Reply { get; private set; } = "";
    public string Diagnostics { get; private set; } = "";
    public bool ShowPanel;
    public bool ShowControls = true;
    public DialogueTurnResult LastTurn { get; private set; }

    private JObject _manifest;
    private string _manifestPath;
    private NpcMemoryClient _client;
    private readonly Dictionary<string, NpcSession> _sessions = new Dictionary<string, NpcSession>();
    private VillageNpcAnchor[] _anchors;
    private Task _initialization;
    private int _pending;
    private string _question = "What do you remember about the fisherman leaving his pouch of gold?";
    private GUIStyle _title, _body, _small, _button, _input;
    private Vector2 _scroll;

    private void Update()
    {
        var player = FindFirstObjectByType<VillagePlayerController>();
        if (ShowPanel && Keyboard.current != null && Keyboard.current.escapeKey.wasPressedThisFrame)
        {
            ShowPanel = false;
            if (player != null) player.enabled = true;
        }
        if (player != null && ShowPanel) player.enabled = false;
        if (ShowPanel) { Cursor.lockState = CursorLockMode.None; Cursor.visible = true; }
    }

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    private static void Attach()
    {
        if (SceneManager.GetActiveScene().name != "VillageScene") return;
        string path = Path.GetFullPath(Path.Combine(Application.dataPath, "../../data/demo/session.json"));
        if (File.Exists(path) && FindFirstObjectByType<VillageDemoBackend>() == null)
            new GameObject("Village demo backend").AddComponent<VillageDemoBackend>();
    }

    private void Start()
    {
        _manifestPath = Path.GetFullPath(Path.Combine(Application.dataPath, "../../data/demo/session.json"));
        _anchors = FindObjectsByType<VillageNpcAnchor>(FindObjectsSortMode.None).Where(a => a.IsDemoFocus).ToArray();
        foreach (var anchor in _anchors)
        {
            anchor.ObservationReported += Observe;
            anchor.DialogueRequested += OpenDialogue;
        }
        _initialization = Initialize();
    }

    private async Task Initialize()
    {
        _pending++;
        try
        {
            _manifest = JObject.Parse(File.ReadAllText(_manifestPath));
            if ((string)_manifest["status"] == "aborted" || _manifest["witnesses"].Any(w => (string)w["event_status"] == "in_flight"))
                throw new InvalidOperationException("Unresolved observation receipt; provision a new take.");
            _client = new NpcMemoryClient((string)_manifest["base_url"]);
            foreach (var witness in _manifest["witnesses"])
            {
                var session = new NpcSession(_client, Guid.Parse((string)witness["agent_id"]), "village-live");
                session.AsOf = DateTimeOffset.Parse((string)_manifest["world_time"]);
                await session.SceneBoundaryAsync();
                _sessions.Add((string)witness["stable_id"], session);
            }
            Day = (int)(DateTimeOffset.Parse((string)_manifest["world_time"]) - DateTimeOffset.Parse((string)_manifest["event"]["world_time"])).TotalDays;
            Status = "Two witnesses connected";
        }
        catch (Exception ex) { Abort(ex); }
        finally { _pending--; }
    }

    private JToken Witness(string stableId) => _manifest["witnesses"].Single(w => (string)w["stable_id"] == stableId);

    private void Persist()
    {
        string temporary = _manifestPath + ".tmp";
        File.WriteAllText(temporary, _manifest.ToString(Formatting.Indented));
        File.Replace(temporary, _manifestPath, null);
    }

    private void Abort(Exception ex)
    {
        Aborted = true;
        Status = "Take stopped: " + ex.GetType().Name + ". Check the saved receipt before starting a new take.";
        if (_manifest != null) { _manifest["status"] = "aborted"; Persist(); }
        Debug.LogError(Status);
    }

    private async void Observe(VillageNpcAnchor anchor, VillageObservation observation)
    {
        await _initialization;
        if (Aborted || observation.eventId != (string)_manifest["event"]["event_id"]) return;
        var witness = Witness(anchor.StableId);
        if ((string)witness["event_status"] != "not_observed") return;
        _pending++;
        try
        {
            witness["event_status"] = "in_flight";
            Persist();
            Status = "Remembering the event…";
            var result = await _sessions[anchor.StableId].ObserveAsync((string)_manifest["event"]["observation_text"]);
            witness["event_memory_id"] = result.MemoryId.ToString();
            witness["event_status"] = "observed";
            Persist();
            if (result.ScoringFailed || result.EmbeddingFailed || result.EnrichmentPending)
                throw new InvalidOperationException("Observation was saved in degraded form; use a fresh take.");
            Status = "Event saved to persistent memory";
        }
        catch (Exception ex) { Abort(ex); }
        finally { _pending--; }
    }

    private void OpenDialogue(VillageNpcAnchor anchor)
    {
        SelectedWitness = anchor.StableId;
        ShowPanel = true;
        Cursor.lockState = CursorLockMode.None;
        Cursor.visible = true;
    }

    public async Task AdvanceToDay(int day)
    {
        await _initialization;
        if (Aborted || Busy) return;
        if (day < Day) throw new InvalidOperationException("A take advances forward; use the Ledger to inspect past tellings.");
        if (_manifest["witnesses"].Any(w => (string)w["event_status"] != "observed")) return;
        _pending++;
        try
        {
            Status = "Opening a new scene…";
            var at = DateTimeOffset.Parse((string)_manifest["event"]["world_time"]).AddDays(day);
            foreach (var session in _sessions.Values)
            {
                session.AsOf = at;
                await session.SceneBoundaryAsync();
            }
            Day = day;
            _manifest["world_time"] = at.ToString("O");
            Persist();
            Reply = "";
            Diagnostics = "";
            Status = "Scene ready";
        }
        catch (Exception ex) { Abort(ex); }
        finally { _pending--; }
    }

    public async Task Ask(string stableId, string question)
    {
        await _initialization;
        if (Aborted || Busy || string.IsNullOrWhiteSpace(question)) return;
        _pending++;
        SelectedWitness = stableId;
        _question = question;
        Reply = "";
        Diagnostics = "";
        try
        {
            Status = "Recalling…";
            var session = _sessions[stableId];
            LastTurn = await session.SayStreamAsync(question, chunk => { Reply += chunk; Status = "Speaking…"; }, () => Status = "Reconstructing memory…", k: 3);
            var r = LastTurn.Instrumentation.Retrieval;
            Diagnostics = $"{session.LoadedMemoryIds.Count} memories loaded   ·   {r.CacheHits} cache hits   ·   {r.WriteBacks} new tellings   ·   gate: {(r.Gate.Fired ? "opened" : r.Gate.Evaluated ? "closed" : "initial load")}";
            Status = "Memory persists after the conversation";
            string directory = Path.Combine(Path.GetDirectoryName(_manifestPath), "runs", (string)_manifest["take_id"], "live");
            Directory.CreateDirectory(directory);
            File.WriteAllText(Path.Combine(directory, DateTime.UtcNow.ToString("yyyyMMdd_HHmmss_fff") + "_" + stableId + ".json"), JsonConvert.SerializeObject(LastTurn, Formatting.Indented));
        }
        catch (Exception ex) { Status = "Dialogue failed: " + ex.GetType().Name; }
        finally { _pending--; }
    }

    private void OnGUI()
    {
        if (!ShowPanel) return;
        if (_title == null)
        {
            _title = new GUIStyle(GUI.skin.label) { fontSize = 30, fontStyle = FontStyle.Bold, wordWrap = true };
            _body = new GUIStyle(GUI.skin.label) { fontSize = 24, wordWrap = true };
            _small = new GUIStyle(GUI.skin.label) { fontSize = 17, wordWrap = true };
            _button = new GUIStyle(GUI.skin.button) { fontSize = 19, padding = new RectOffset(14, 14, 10, 10) };
            _input = new GUIStyle(GUI.skin.textField) { fontSize = 21, wordWrap = true };
        }
        var oldMatrix = GUI.matrix;
        GUI.matrix = Matrix4x4.Scale(new Vector3(Screen.width / 1920f, Screen.height / 1080f, 1));
        var panel = new Rect(1040, 60, 820, 930);
        var oldColor = GUI.color;
        GUI.color = new Color(.06f, .08f, .1f, .97f);
        GUI.DrawTexture(panel, Texture2D.whiteTexture);
        GUI.color = oldColor;
        GUI.Box(panel, GUIContent.none);
        GUILayout.BeginArea(new Rect(panel.x + 30, panel.y + 22, panel.width - 60, panel.height - 44));
        GUILayout.Label("TWICETOLD  /  PERSISTENT NPC MEMORY", _small);
        GUILayout.Label(SelectedWitness.ToUpperInvariant() + "   ·   " + (Day == 0 ? "The day of the event" : Day + " days later"), _title);
        GUILayout.Space(14);
        GUILayout.Label(Status, _small);
        GUILayout.Space(18);
        GUILayout.Label(_question, _body);
        GUILayout.Space(14);
        _scroll = GUILayout.BeginScrollView(_scroll, GUILayout.Height(450));
        GUILayout.Label(Reply, _body);
        GUILayout.EndScrollView();
        GUILayout.Label(Diagnostics, _small);
        if (ShowControls)
        {
            GUI.enabled = !Busy && !Aborted;
            GUILayout.BeginHorizontal();
            foreach (var id in new[] { "henry", "joan" })
                if (GUILayout.Button(id.ToUpperInvariant(), _button)) { SelectedWitness = id; Reply = ""; }
            foreach (var day in new[] { 0, 60, 90, 180 })
                if (GUILayout.Button("+" + day + "d", _button) && day >= Day) _ = AdvanceToDay(day);
            GUILayout.EndHorizontal();
            _question = GUILayout.TextField(_question, _input, GUILayout.Height(70));
            if (GUILayout.Button("Ask", _button)) _ = Ask(SelectedWitness, _question);
            GUI.enabled = true;
        }
        GUILayout.EndArea();
        GUI.matrix = oldMatrix;
    }

    private void OnDestroy()
    {
        if (_anchors != null) foreach (var anchor in _anchors)
        {
            if (anchor == null) continue;
            anchor.ObservationReported -= Observe;
            anchor.DialogueRequested -= OpenDialogue;
        }
        _client?.Dispose();
    }
}
