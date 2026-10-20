using System.Reflection;
using Newtonsoft.Json.Linq;
using NpcMemory.Unity;

namespace NpcMemory.Tests;

internal static class Program
{
    private const string Scene = "{\"accepted\":true,\"identity_version\":\"identity-1\"}";
    private const string Turn = "{\"content\":\"fixture\",\"items\":[],\"instrumentation\":{\"retrieval\":{\"gate\":{\"evaluated\":false}}}}";
    private static readonly DateTimeOffset Clock = DateTimeOffset.Parse("2026-07-27T12:00:00Z");
    private static int _checks;

    private static void Check(bool condition, string description)
    {
        if (!condition) throw new Exception(description);
        _checks++;
        Console.WriteLine($"PASS {description}");
    }

    private static async Task Throws<T>(Task task, string description) where T : Exception
    {
        try { await task.WaitAsync(TimeSpan.FromSeconds(5)); }
        catch (T) { Check(true, description); return; }
        throw new Exception($"Expected {typeof(T).Name}: {description}");
    }

    private static void Destroy(NpcMemoryNpc npc) =>
        typeof(NpcMemoryNpc).GetMethod("OnDestroy", BindingFlags.NonPublic | BindingFlags.Instance).Invoke(npc, null);

    private static async Task FirstScene(bool stream)
    {
        await using var server = new LoopbackServer();
        using var client = new NpcMemoryClient(server.Url);
        var session = new NpcSession(client, Guid.NewGuid()) { AsOf = Clock, ContextLocation = "ford" };
        Task<DialogueTurnResult> Speak() => stream ? session.SayStreamAsync("Hello", _ => { }) : session.SayAsync("Hello");
        async Task Answer(LoopbackServer.Request req)
        {
            if (stream) await req.Stream($"event: result\ndata: {Turn}\n\n");
            else await req.Reply(Turn);
        }
        var first = Speak();
        var boundary = await server.Next();
        Check(boundary.Path == "/v1/events/scene-boundary", "first turn awaits boundary before dialogue");
        Check(boundary.Body.Value<DateTimeOffset>("client_timestamp") == Clock, "initial boundary uses injected clock");
        await boundary.Reply(Scene);
        var turn = await server.Next();
        Check(turn.Path.EndsWith(stream ? "/stream" : "/turn"), "correct turn route follows initialization");
        Check(turn.Body.Value<string>("identity_version") == "identity-1" && turn.Body.Value<DateTimeOffset>("scene_started_at") == Clock, "first turn has frozen identity and basis");
        Check(turn.Body.Value<string>("location_name") == "ford" && turn.Body["loaded_memory_ids"].Type == JTokenType.Null, "first turn retains caller context and null loader set");
        await Answer(turn);
        await first.WaitAsync(TimeSpan.FromSeconds(5));
        session.AsOf = Clock.AddDays(1);
        var second = Speak();
        var next = await server.Next();
        Check(next.Path == turn.Path && next.Body.Value<DateTimeOffset>("scene_started_at") == Clock, "second turn reuses frozen first scene");
        Check(next.Body["loaded_memory_ids"] is JArray { Count: 0 }, "empty loaded scene stays distinct from null");
        await Answer(next);
        await second.WaitAsync(TimeSpan.FromSeconds(5));
        var edge = session.SceneBoundaryAsync("tavern");
        var edgeRequest = await server.Next();
        session.AsOf = Clock.AddDays(2); // clock changes while request is pending
        await edgeRequest.Reply(Scene.Replace("identity-1", "identity-2"));
        await edge;
        Check(session.SceneStartedAt == Clock.AddDays(1) && session.IdentityVersion == "identity-2", "boundary response preserves request-time basis");
        Check(session.LoadedMemoryIds == null && session.ContextLocation == null && session.SceneType == "tavern", "explicit boundary resets scene state");
        await session.InitializeAsync(); // must not emit another boundary
    }

    private static async Task InitializationFailuresAndSharing()
    {
        await using var server = new LoopbackServer();
        using var client = new NpcMemoryClient(server.Url);
        var session = new NpcSession(client, Guid.NewGuid()) { AsOf = Clock };
        var failed = session.SayAsync("hello");
        await (await server.Next()).Reply("{}", 503);
        await Throws<NpcMemoryApiException>(failed, "failed initialization propagates before turn");
        Check(session.IdentityVersion == null && session.SceneStartedAt == null, "failure leaves session uninitialized");
        var pending = Enumerable.Range(0, 5).Select(_ => session.InitializeAsync()).ToArray();
        await (await server.Next()).Reply(Scene);
        await Task.WhenAll(pending).WaitAsync(TimeSpan.FromSeconds(5));
        Check(session.IdentityVersion == "identity-1", "concurrent initialization shares one boundary and explicit retry succeeds");
        var invalid = session.SceneBoundaryAsync();
        await (await server.Next()).Reply("{\"accepted\":false}");
        await Throws<NpcMemoryApiException>(invalid, "unaccepted boundary cannot replace scene state");
        Check(session.SceneStartedAt == Clock && session.IdentityVersion == "identity-1", "failed replacement keeps previous scene");
    }

    private static async Task StreamCancellation(bool errorBody)
    {
        await using var server = new LoopbackServer();
        using var client = new NpcMemoryClient(server.Url);
        using var cancel = new CancellationTokenSource();
        var chunk = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
        var task = client.DialogueTurnStreamAsync(new DialogueTurnRequest { AgentId = Guid.NewGuid(), Utterance = "hello" }, _ => chunk.TrySetResult(true), ct: cancel.Token);
        var request = await server.Next();
        await request.Stream(errorBody ? "partial error" : "event: chunk\ndata: \"fixture\"\n\n", errorBody ? 500 : 200);
        if (!errorBody) await chunk.Task.WaitAsync(TimeSpan.FromSeconds(5));
        cancel.Cancel();
        await Throws<OperationCanceledException>(task, $"cancellation interrupts stalled {(errorBody ? "HTTP error" : "SSE")} body");
    }

    private static async Task RouteTimeouts()
    {
        await using var server = new LoopbackServer();
        using var client = new NpcMemoryClient(server.Url) { DefaultTimeout = TimeSpan.FromMilliseconds(500), InitTimeout = TimeSpan.FromSeconds(5), TurnTimeout = TimeSpan.FromMilliseconds(500) };
        var plain = client.SceneBoundaryAsync(new SceneBoundaryEvent());
        await server.Next();
        var warm = client.SceneBoundaryAsync(new SceneBoundaryEvent { PrewarmContext = "ford" });
        var request = await server.Next();
        var whitespaceWarm = client.SceneBoundaryAsync(new SceneBoundaryEvent { PrewarmContext = " " });
        var whitespaceRequest = await server.Next();
        await Throws<OperationCanceledException>(plain, "plain boundary uses default timeout");
        Check(!warm.IsCompleted, "prewarm uses longer init timeout");
        Check(!whitespaceWarm.IsCompleted, "whitespace probe matches server nonempty prewarm condition");
        await request.Reply(Scene);
        await whitespaceRequest.Reply(Scene);
        await warm;
        await whitespaceWarm;
        var stream = client.DialogueTurnStreamAsync(new DialogueTurnRequest(), _ => { });
        await (await server.Next()).Stream();
        await Throws<OperationCanceledException>(stream, "TurnTimeout cancels a body stalled after headers");
    }

    private static async Task StreamTerminals()
    {
        await using var server = new LoopbackServer();
        using var client = new NpcMemoryClient(server.Url);
        var success = client.DialogueTurnStreamAsync(new DialogueTurnRequest(), _ => { });
        await (await server.Next()).Stream($"event: result\ndata: {Turn}\n\n");
        Check((await success.WaitAsync(TimeSpan.FromSeconds(5))).Items.Count == 0, "terminal result completes without waiting for EOF");
        foreach (var body in new[] { "event: error\ndata: \"fixture error\"\n\n", "" })
        {
            var failed = client.DialogueTurnStreamAsync(new DialogueTurnRequest(), _ => { });
            var request = await server.Next();
            await request.Stream(body);
            request.Closed.TrySetResult(true);
            await Throws<NpcMemoryApiException>(failed, "error event or missing result is a typed failure");
        }
    }

    private static async Task AdapterReadiness()
    {
        await using var server = new LoopbackServer();
        var npc = new NpcMemoryNpc { baseUrl = server.Url };
        try
        {
            npc.SetAsOf(Clock);
            try { npc.ObserveAndForget("early"); throw new Exception("early event was accepted"); }
            catch (InvalidOperationException) { Check(true, "early fire-and-forget fails with readiness contract"); }
            var ready = npc.ReadyTask;
            Check(ReferenceEquals(ready, npc.ReadyTask), "readiness is a shared task");
            using var cancel = new CancellationTokenSource();
            var earlyTurn = npc.SayAsync("cancelled waiter", cancel.Token);
            cancel.Cancel();
            await Throws<OperationCanceledException>(earlyTurn, "one cancelled waiter does not cancel shared initialization");
            var provision = await server.Next();
            Check(provision.Path == "/v1/agents", "adapter provisions once");
            var id = Guid.NewGuid();
            await provision.Reply($"{{\"agent_id\":\"{id}\"}}");
            var boundary = await server.Next();
            Check(!npc.Ready && boundary.Path == "/v1/events/scene-boundary", "ready waits for first scene, not just provisioning");
            var observe = npc.ObserveAsync("early awaited event");
            await boundary.Reply(Scene);
            await ready.WaitAsync(TimeSpan.FromSeconds(5));
            Check(npc.Ready && npc.AgentId == id && npc.Session.SceneStartedAt == Clock, "readiness initializes agent and game-time scene");
            var observation = await server.Next();
            Check(observation.Path == "/v1/events/observe", "early async operation waits until ready");
            await observation.Reply("{}");
            await observe;
        }
        finally { Destroy(npc); }
        Check(!npc.Ready, "destroy clears ready state");
        await Throws<ObjectDisposedException>(npc.SayAsync("after destroy"), "destroyed adapter rejects new work");
    }

    private static async Task AdapterFailureAndDestroy()
    {
        await using var server = new LoopbackServer();
        var npc = new NpcMemoryNpc { baseUrl = server.Url };
        var ready = npc.ReadyTask;
        await (await server.Next()).Reply("{}", 503);
        await Throws<NpcMemoryApiException>(ready, "adapter readiness exposes provisioning failure");
        Check(ReferenceEquals(ready, npc.ReadyTask) && !npc.Ready, "failed readiness stays failed without reprovisioning");
        await Throws<NpcMemoryApiException>(npc.SayAsync("hello"), "early callers observe same failure");
        Destroy(npc);
        var attached = new NpcMemoryNpc { baseUrl = server.Url, autoProvision = false, agentIdOverride = Guid.NewGuid().ToString() };
        var pending = attached.ReadyTask;
        var boundary = await server.Next();
        Check(boundary.Path == "/v1/events/scene-boundary", "saved agent attachment skips provisioning");
        Destroy(attached);
        await Throws<OperationCanceledException>(pending, "destroy cancels in-flight initialization");
        Check(!attached.Ready, "cancelled initialization cannot mark destroyed adapter ready");
    }

    public static async Task Main()
    {
        await FirstScene(false);
        await FirstScene(true);
        await InitializationFailuresAndSharing();
        await StreamCancellation(false);
        await StreamCancellation(true);
        await RouteTimeouts();
        await StreamTerminals();
        await AdapterReadiness();
        await AdapterFailureAndDestroy();
        Console.WriteLine($"{_checks} contract checks passed (loopback HTTP; Unity type stubs, not Play Mode).");
    }
}
