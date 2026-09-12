using Newtonsoft.Json;
using Newtonsoft.Json.Serialization;

namespace NpcMemory
{
    /// <summary>
    /// The ONE serializer configuration both hosts use (unity-client.md fork 4,
    /// ruled 2026-07-27: Newtonsoft everywhere — one serializer, one behavior).
    ///
    /// The null-vs-absent contract is load-bearing: on DialogueTurnRequest,
    /// loaded_memory_ids = null means LOADER TURN while [] means "an empty
    /// loaded set the gate still evaluates". NullValueHandling stays Include
    /// (the Newtonsoft default) so a null list serializes as an explicit null
    /// — never silently omitted — and an empty List serializes as []. Nothing
    /// here may ever collapse one into the other.
    ///
    /// Timestamps are DateTimeOffset end to end (the service requires
    /// timezone-aware ISO-8601). DateParseHandling is None so free-form JSON
    /// payloads (directive params, agent config) never have date-looking
    /// strings mangled; typed DateTimeOffset properties still parse.
    /// </summary>
    public static class NpcJson
    {
        public static readonly JsonSerializerSettings Settings = new JsonSerializerSettings
        {
            ContractResolver = new DefaultContractResolver
            {
                NamingStrategy = new SnakeCaseNamingStrategy(),
            },
            NullValueHandling = NullValueHandling.Include,
            DateParseHandling = DateParseHandling.None,
            DateFormatHandling = DateFormatHandling.IsoDateFormat,
        };

        public static string Serialize(object value) =>
            JsonConvert.SerializeObject(value, Settings);

        public static T Deserialize<T>(string json) =>
            JsonConvert.DeserializeObject<T>(json, Settings)
            ?? throw new NpcMemoryApiException(0, "response deserialized to null");
    }
}
