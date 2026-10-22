# Connect your application to memory

This example puts an application-owned conversation in front of the memory service. It uses
only public HTTP routes and `httpx`; it does not import the backend, load NLP models, or connect
to Postgres. Your application chooses what to remember and supplies its own dialogue model.

## Try it with Docker only

From the repository root in PowerShell, with Docker Desktop running:

```powershell
docker compose -f compose.demo.yml run --build --rm demo python -m examples.chat --base-url http://api:8000 --public-url http://127.0.0.1:8001 --state /tmp/chat-session.json --demo
```

This starts the isolated, keyless memory service, records an observation, replays its event key,
asks two related questions, corrects the memory, asks again, and starts a new scene. It prints
memory IDs, retrieval scores, read modes, timings, an inspector link, and:

```text
PASS application integration: replay, follow-up context, correction and scene reset.
```

The second answer receives two recent messages; the answer after correction receives none.
Both the memory providers and the application dialogue are deterministic fakes in this command.
It proves the wiring, not answer quality. Use the [first-run walkthrough](first-run.md) to explore
aging, reconstruction and cache reuse, or to configure real memory providers.

The container's `/tmp` state disappears on exit; each invocation creates another agent. Its
memories remain in the demo database and are reachable through the printed inspector link.
The following host-based path retains the agent ID and pending observations across restarts.

## Use the interactive application

Keep the demo service running. With Python installed, these are the only client dependencies;
the backend requirements are unnecessary for this client:

```powershell
python -m pip install -r examples\requirements.txt
python -m examples.chat
```

Run from the repository root. The default endpoint is `http://127.0.0.1:8001`. Try:

```text
/observe The guest left a blue suitcase at the Waystone Inn.
What did the guest leave at the inn?
Where was it left?
/help
/quit
```

Restart with the same command to attach to the saved agent. Recent chat starts empty; durable
memories remain. `python -m examples.chat --demo` runs the same fixed scenario on the host.
The private state file defaults to `data\integration-example\session.json`, which Git ignores.
Use `--agent-id` to attach an existing UUID with a new `--state` file. Use one state file per agent
and API origin; mixing the host URL, container URL, fake stack or real stack is rejected.
Agent names are display labels, not lookup keys. If the service database is reset, choose a new
state file rather than attempting to attach the old UUID.

| Command | Application action |
| --- | --- |
| Plain text | Retrieve memories, combine them with bounded recent chat, call your dialogue model. |
| `/observe <event>` | Save a deliberate observation to the local outbox, then deliver it. |
| `/retry` | Redeliver the exact pending observation, including after a restart. |
| `/correct <memory UUID> <text>` | Read the live detail head and submit an authorial correction with that head as the conflict guard. |
| `/scene [ISO-8601 time]` | Freeze a new scene basis and clear recent chat after acknowledgement. |
| `/quit` | Exit, retaining the agent and any pending observation. |

The terminal uses a simple game clock: it holds the current scene's time fixed until `/scene`.
Without a timestamp, `/scene` uses current UTC; an explicit time must include an offset, for
example `/scene 2026-10-22T12:00:00+00:00`. The service's `as_of` controls aging and scoring;
it does not retrieve historical knowledge. A real application can advance its read clock every
turn while holding `identity_version` and `scene_started_at` fixed until its next scene boundary.

## Connect a real dialogue model

The application dialogue provider is independent of the memory service's providers. To use an
already running OpenAI-compatible model server on your host, replace the model name below with
one served by that endpoint:

```powershell
python -m examples.chat --dialogue real --model-base-url http://127.0.0.1:11434/v1 --model "your-model-name"
```

For an authenticated endpoint, set `EXAMPLE_DIALOGUE_API_KEY` in the process environment using
your normal secret management. The example does not read the backend's `.env` or reuse its keys.
Two separate HTTP clients ensure the model key is sent only to the dialogue server. Do not put
keys in URLs, command arguments, or state files.

The optional adapter posts non-streaming text messages to `chat/completions` under the supplied
base URL. It accepts a complete text answer and reports the returned usage. Its default output
limit field is `max_tokens` for local-server compatibility; use `--token-limit-field
max_completion_tokens` when required by your model, and adjust `--max-output-tokens` (default
512). The latter may also budget reasoning tokens. Model-specific roles, tools and streaming
belong in your own callback; this adapter uses a system message and ordinary text chat.
See the [official Chat Completions reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)
for the request and response fields. A length-limited or tool-only response is reported as an
error instead of silently adding an incomplete answer to history.

To run the same adapter inside Docker, pass `-e EXAMPLE_DIALOGUE_API_KEY` to `docker compose run`
if needed and use `http://host.docker.internal:11434/v1` for a model served by your host. Keep
`--state /tmp/chat-session.json` for disposable runs. To make memory providers real as well,
first follow [the real-provider setup](first-run.md#real-providers-the-same-scenario-with-your-models), then point the host
client at port 8002 with a separate state file:

```powershell
python -m examples.chat --base-url http://127.0.0.1:8002 --state data\integration-example\real.json --dialogue real --model-base-url http://127.0.0.1:11434/v1 --model "your-model-name"
```

Real providers may incur charges. Fake memory plus real dialogue is useful for checking your
application's plumbing, but it does not demonstrate real memory extraction or reconstruction.

## Replace the terminal with your application

The reusable part is [examples/memory_chat.py](../examples/memory_chat.py).
[examples/chat.py](../examples/chat.py) supplies the terminal, local persistence and executable
scenario. Keep one `Conversation` per application session and call it sequentially. For example,
inside an existing application's async session handler:

```python
from datetime import datetime, timezone
import httpx
from examples.memory_chat import Completion, Conversation, MemoryAPI

async def complete(messages):
    # Your application's existing dialogue client; adapt its return value here.
    response = await your_dialogue_model(messages)
    return Completion(response.text, response.usage)

async def handle_session(saved_agent_id, incoming_messages, send_reply):
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8001", timeout=180) as http:
        memory = MemoryAPI(http)
        conversation = Conversation(memory, saved_agent_id, complete)
        await conversation.begin_scene(datetime.now(timezone.utc))
        async for user_text in incoming_messages:
            result = await conversation.say(user_text, datetime.now(timezone.utc))
            await send_reply(result)
```

Replace `your_dialogue_model`, the input iterator and the output function with your application
interfaces. Provision an agent once with `MemoryAPI.create_agent`, persist its returned UUID in
your user/character record, and pass that UUID to later sessions. Make observations separately:
`MemoryAPI.observation(agent_id, text, at)` prepares a stable event; persist the entire result
before calling `await memory.observe(payload)`. The CLI's `LocalState.deliver` demonstrates this
ordering. Plain dialogue never automatically becomes a long-term observation.

| Responsibility | Owner and HTTP operation |
| --- | --- |
| User/character-to-agent mapping | Application persists the UUID from `POST /v1/agents`. |
| What happened and when | Application selects observations; `POST /v1/events/observe` stores them. |
| Memory storage, retrieval, decay and reconstruction | Service, through `POST /v1/dialogue/init` for this example. |
| Recent conversation and dialogue model | Application; neither is stored in the memory service by this example. |
| Scene boundaries and clock | Application calls `POST /v1/events/scene-boundary` and retains the returned identity version. |
| Corrections | Application reads `/v1/memories/{id}/chain`, then posts `/correction` with `expected_detail_id`. |
| Delivery, errors and retries | Application persists pending events, shows errors and chooses whether to retry other operations. |

Each turn retrieves a fresh top-k, then sends the current question, selected memory records and
recent user/assistant pairs to the model. The default retrieval query includes recent conversation
so a follow-up such as “Where was it left?” has context. Supply `retrieval_query=` to `say()` if
your application already produces a better search query. This example uses neither the optional
mid-dialogue gate nor an accumulating loaded set. The service's `/v1/dialogue/turn` is an alternate
dialogue path, not a requirement when you already own a model client.

Defaults are four completed turns, 6,000 history characters, 4,000 input characters, three recalled
memories, and 12,000 characters of serialized memory records. CLI flags expose every limit.
Oldest whole conversation pairs are evicted; an oversized pair is not retained. Whole memory
records that do not fit are omitted, with their IDs reported. These are character budgets, not
token counts; choose budgets that fit your model. The model output limit is separate. Memory
records are labeled as remembered accounts and passed as data; this is not a prompt-injection
security boundary.

## Handle failures deliberately

- Only keyed observations retry automatically: connection errors, timeouts, HTTP 408/429 and
  500/502/503/504. The default is three total attempts with exponential backoff. Every attempt
  uses identical event key, timestamp and payload. A lost acknowledgement after commit replays
  the original receipt. HTTP 409/422 and authorization failures stop immediately.
- Exhausted or rejected delivery leaves the event in the outbox. `/retry` after a restart uses
  the same payload. A second observation cannot replace it. An accepted receipt with degradation
  or enrichment flags is still accepted; replay is not a repair operation. Inspect the memory
  state and the [retry contract](first-npc.md#7-retrying-an-observation-safely).
- Provisioning, corrections, scene changes and dialogue calls are not automatically retried.
  A timed-out write may have committed: inspect the agent or memory chain before repeating it.
  Provisioning has no idempotency key. A correction conflict requires rereading the head and
  deciding whether the correction still applies.
- Failed/cancelled model calls do not append a partial turn. Degraded retrieval fails visibly
  before the model call. Successful corrections and scene boundaries clear recent chat so old
  answers do not compete with the new memory account. If another client corrects a memory, your
  application must invalidate affected chat context too; this sample has no push subscription.
- `LocalState` is a single-process example with one pending event and atomic file replacement.
  In a multi-user application, use your own durable agent mapping and outbox, serialize turns
  within each session, and coordinate concurrent writers. Stop queued retries before purging
  memories, because purge removes their idempotency receipts. Keep state files private.

This is a local integration path. Network deployment still needs the authentication and access
controls described in [setup](SETUP.md); the service does not enforce application user isolation.
The [Unity first-NPC sample](first-npc.md) remains the game-client path, including readiness,
first-scene initialization, cancellation and visible failures.

Focused offline verification lives in `tests\test_python_integration.py`: bounded context,
follow-ups, resets, failure/cancellation, durable retry recovery, provider request/response shape,
and the entire CLI scenario over real API routes with a lost acknowledgement after commit.
These tests assert structure and byte identity, not model answer quality.
