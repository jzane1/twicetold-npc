# Shipping a game with this

This is the page I'd have wanted before adopting anything like this: who hosts it, who pays,
what it costs per player, what Steam asks, and what is deliberately not included. None of it
is hidden in the code; all of it was inferable from four files, and inferable isn't a plan.

## The shape

The service runs on a machine you control, with Postgres beside it. Your game talks HTTP to
it, and it talks to whatever model provider you configured. One service serves as many
agents as you like; the agent UUID is the unit, so shard by game, region or shard key when
you need to. The Unity client is one DLL (`NpcMemory.Core`, netstandard2.1) plus a
MonoBehaviour adapter; `first-npc.md` is the thirty lines.

## Who pays, and how much

The measured figure is **$0.084 per 100 turns, all-in, on 2026-08-26**, on the Anthropic slate
(Claude Haiku 4.5 on every turn-path role, `text-embedding-3-small` for embeddings), where a
turn is one dialogue line on the 60-turn load driver with its observes, and the write,
escalation, dialogue and embedding calls are priced from the token counts every payload
carries. The arithmetic from there, with the assumptions in the open:

| Assumption | Cost |
|---|---|
| One turn | $0.00084 |
| A player who speaks to NPCs 20 times an hour | about $0.017 per player-hour |
| A talkative player, 60 turns an hour | about $0.05 per player-hour |
| A monthly active player at 10 hours a month, 20 turns an hour | about $0.17 a month |

Two honest caveats. First, that number decays within a model generation: re-measure it with
the load driver against your own turn mix (`python -m app.load_driver` prints the per-100-turn
cost table from token counts; set `TWICETOLD_PRICE_*` to your rates) before you budget.
Second, none of it transfers to a different backend or a smaller model, and a local model
changes the quality floor as well as the price: `SETUP.md` §4b has the warning.

## Why it doesn't run on the player's machine

Three reasons, in order of how fast they'd bite:

1. **Keys.** A player-local build ships your provider keys inside the binary. There is no way
   to hand a player a key you don't mind them keeping.
2. **The install.** The service is Python 3.14 with spaCy, fastcoref and transformers on top of
   a Postgres with pgvector. That's a server's footprint, not a game's.
3. **The record.** The memories are the character's state across every player and session.
   A record on a player's disk is a record the player edits.

The one honest exception is a fully local stack: an OpenAI-compatible server on the player's
machine (Ollama, LM Studio) behind `TWICETOLD_MODEL_BACKEND=openai`, with Postgres alongside.
It works, it's keyless, and it's under the small-model warning: every number in this repo was
measured on the hosted slate, and small models break the structured write call first.

## The trust model

The service has no authentication and no rate limiting. It binds `127.0.0.1:8000` by default,
and anyone who can reach that port can read, write and purge every agent's memories. Treat it
exactly like a database socket:

- **Players never talk to it.** Players talk to your game server, and your game server talks
  to the memory service. The client library is for that server-side integration, or for a
  single-player build where the service is on the same machine.
- **If you must expose it,** put a reverse proxy in front (nginx or Caddy) that terminates
  TLS and enforces auth: mutual TLS between your game server and the proxy, or a shared secret
  that only your game server holds. This is a recipe, not a promise to build auth into the
  service; the service stays loopback-bound and dumb.
- **Keep the database on loopback too.** The shipped compose file publishes 5432; the
  packaging pass scopes it to `127.0.0.1`. Until then, don't run it on a machine with a public
  interface without a firewall rule.
- **The Ledger is a designer tool.** It's served by the API at `/ledger` and reads the record
  in full. Don't expose it to players. A Host-header guard for the inspector page (the
  DNS-rebinding class of attack against localhost tools) lands in the release-hygiene pass
  and is not in place today.

## What Steam asks

If a shipped game generates character lines live, Steam's content survey asks whether the
game contains live-generated AI content and what guardrails are in place to keep it from
producing illegal content, and the answers appear on the store page. Players can report
live-generated content from the Steam overlay, a system Valve added in January 2024 alongside
the disclosure rules, and Valve says it won't ship live-generated Adult Only sexual content
at all. Declare it. The public cases where a studio was found not to have declared went
worse than any declaration did.

The primary sources: the Steamworks content survey documentation
(`partner.steamgames.com/doc/gettingstarted/contentsurvey`) and Valve's "AI Content on Steam"
post of 9 January 2024. The survey wording was updated in January 2026 to say it's about
content players consume, not about AI tools used in development; read the current page.

## Content safety

No moderation layer is included. The gist constraint and the drift budget bound what the
character says about her own record; they do nothing about what a player can talk her into
saying. Content safety is the provider's filters plus whatever you build: a filter on the
streamed prose before it reaches the screen, a filter on player lines before they reach the
service, or both. The dialogue role streams pure prose and persists nothing, so a filtered
line is simply never shown; nothing has to be unwritten.

## Platforms

| Target | Status | Note |
|---|---|---|
| Unity Editor, Windows, macOS, Linux | yes | the DLL targets netstandard2.1, Unity 6's compatibility profile |
| iOS, Android (IL2CPP) | yes, with a `link.xml` | the client serializes with Newtonsoft.Json (`com.unity.nuget.newtonsoft-json`); preserve `NpcMemory.Core` and `Newtonsoft.Json` from stripping |
| WebGL | no | Unity's constraint: no `System.Net` on the Web player, so an HTTP client library cannot run there |

The Unity project in `unity\` is a gray-box reference scene, not a package yet; the Unity
Package Manager package and the one-command backend spin-up are the packaging pass.

## Erasing a player

Memories attach to NPC agents, not to players, so the map from a player to the memories they
caused is yours to keep (the agent UUIDs of the characters that are private to that player,
or the memory IDs your game observed on their behalf). With that map, the erase flow is two
verbs:

- `DELETE /v1/agents/{id}/memories` erases every memory of one agent, in one transaction
  across seven tables, and returns the counts. Use it for a character that belongs to one
  player.
- `DELETE /v1/memories/{id}` erases one memory the same way. Use it for a shared character
  that remembers many players.

Both are honest about what survives: the agent row, its identity, its reflections (which may
now cite memories that no longer exist), its compiled bundles and its run logs. Those are the
character's, not the player's, and erasing them would erase the character. There is no
scheduler; erasure happens when you call it.

## The latency budget

The measured p50 is **826–917 ms to the first streamed word** (2026-08-26, five runs), with no
speech in the loop: a text line in, text chunks out. Speech recognition and synthesis sit on
top of that in your pipeline, not inside this number, and the pre-prose part of it is mostly
the query embedding (roughly a quarter of the median). Two things keep it down in practice:
pre-warm at scene boundaries so the first line of a scene is a cache hit, and stay under the
model-call cap (`TWICETOLD_MAX_CONCURRENT_MODEL_CALLS`, default 8) so turns don't queue.

## Before you ship

- The service and Postgres on a machine you control, loopback-bound, behind your game server.
- Keys in the server's `.env` only; never in a build.
- A player-to-memory map, and the erase flow tested against it.
- Your own content filter on the streamed prose, if your rating needs one.
- The Steam content survey answered honestly.
- A re-measured cost table from the load driver against your turn mix.
- `AsOf` set every session if your game keeps its own clock.
