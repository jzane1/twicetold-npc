using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading.Channels;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace NpcMemory.Tests;

// Real HTTP on an ephemeral loopback port. Tests choose exactly when headers/body
// arrive, including a body that stalls until cancellation. No provider traffic.
internal sealed class LoopbackServer : IAsyncDisposable
{
    private readonly TcpListener _listener = new(IPAddress.Loopback, 0);
    private readonly CancellationTokenSource _stop = new();
    private readonly Channel<Request> _requests = Channel.CreateUnbounded<Request>();
    private readonly List<Task> _connections = new();
    private readonly Task _accept;
    public string Url { get; }

    public LoopbackServer()
    {
        _listener.Start();
        Url = $"http://127.0.0.1:{((IPEndPoint)_listener.LocalEndpoint).Port}";
        _accept = Accept();
    }

    public async Task<Request> Next() =>
        await _requests.Reader.ReadAsync().AsTask().WaitAsync(TimeSpan.FromSeconds(5));

    private async Task Accept()
    {
        try
        {
            while (!_stop.IsCancellationRequested)
                _connections.Add(Handle(await _listener.AcceptTcpClientAsync(_stop.Token)));
        }
        catch (OperationCanceledException) { }
    }

    private async Task Handle(TcpClient client)
    {
        using (client)
        {
            try
            {
                using var stream = client.GetStream();
                using var reader = new StreamReader(stream, Encoding.UTF8, leaveOpen: true);
                var start = await reader.ReadLineAsync(_stop.Token);
                int length = 0;
                string line;
                while (!string.IsNullOrEmpty(line = await reader.ReadLineAsync(_stop.Token)))
                    if (line.StartsWith("Content-Length:", StringComparison.OrdinalIgnoreCase))
                        length = int.Parse(line.Split(':')[1]);
                // Fixture requests are ASCII, so byte and character counts agree.
                var body = new char[length];
                int read = 0;
                while (read < length)
                {
                    int count = await reader.ReadAsync(body.AsMemory(read), _stop.Token);
                    if (count == 0) throw new EndOfStreamException();
                    read += count;
                }
                using var json = new JsonTextReader(new StringReader(new string(body)))
                { DateParseHandling = DateParseHandling.DateTimeOffset };
                var request = new Request(start.Split(' ')[1], JObject.Load(json), stream);
                await _requests.Writer.WriteAsync(request, _stop.Token);
                await request.Closed.Task.WaitAsync(_stop.Token);
            }
            catch (OperationCanceledException) when (_stop.IsCancellationRequested) { }
        }
    }

    public async ValueTask DisposeAsync()
    {
        _stop.Cancel();
        _listener.Stop();
        await _accept;
        await Task.WhenAll(_connections);
        _stop.Dispose();
    }

    internal sealed class Request(string path, JObject body, NetworkStream stream)
    {
        public string Path { get; } = path;
        public JObject Body { get; } = body;
        public TaskCompletionSource<bool> Closed { get; } = new(TaskCreationOptions.RunContinuationsAsynchronously);

        public async Task Write(string bytes)
        {
            await stream.WriteAsync(Encoding.UTF8.GetBytes(bytes));
            await stream.FlushAsync();
        }

        public async Task Reply(string json, int status = 200)
        {
            await Write($"HTTP/1.1 {status} Test\r\nContent-Type: application/json\r\nContent-Length: {Encoding.UTF8.GetByteCount(json)}\r\nConnection: close\r\n\r\n{json}");
            Closed.TrySetResult(true);
        }

        public Task Stream(string initial = "", int status = 200) =>
            Write($"HTTP/1.1 {status} Test\r\nContent-Type: text/event-stream\r\nConnection: close\r\n\r\n{initial}");
    }
}
