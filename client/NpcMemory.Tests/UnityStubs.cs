// Minimal host for lifecycle contract tests. No Unity runtime behavior is emulated.
namespace UnityEngine;

public class MonoBehaviour { }
public sealed class HeaderAttribute : Attribute { public HeaderAttribute(string text) { } }
public sealed class TooltipAttribute : Attribute { public TooltipAttribute(string text) { } }
public sealed class TextAreaAttribute : Attribute { }
public sealed class SerializeField : Attribute { }
public static class Debug
{
    public static void Log(object message) { }
    public static void LogException(Exception exception, object context = null) { }
}
public readonly struct Rect
{
    public Rect(float x, float y, float width, float height) { }
}
public static class Screen
{
    public static int width => 800;
    public static int height => 600;
}
public static class GUI
{
    public static void Label(Rect rect, string text) { }
}
