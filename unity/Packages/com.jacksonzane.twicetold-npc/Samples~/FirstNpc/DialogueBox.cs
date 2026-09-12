using UnityEngine;

/// <summary>
/// The smallest possible sink for streamed dialogue, so the sample compiles and
/// runs as-is. Replace it with your game's dialogue UI.
/// </summary>
public sealed class DialogueBox : MonoBehaviour
{
    private string _text = "";

    public void Append(string chunk) => _text += chunk;

    public void ShowThinking() => _text += "\n[thinking...]\n";

    private void OnGUI() =>
        GUI.Label(new Rect(12, 12, Screen.width - 24, Screen.height - 24), _text);
}
