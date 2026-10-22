"""Run: python -m examples.chat --help. See docs/python-integration.md."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import httpx

from examples.memory_chat import (
    ChatCompletionsDialogue,
    Conversation,
    IntegrationError,
    MemoryAPI,
    endpoint,
    fake_dialogue,
    timestamp,
)


class LocalState:
    """One-process demo persistence; replace with your user/agent DB and outbox.

    Only the agent ID and one pending observation survive restarts. Chat history
    stays ephemeral. Bind the file to a service origin to prevent fake/real mixups.
    """

    def __init__(self, path: Path, api_url: str):
        self.path = path
        self.data = {
            "version": 1,
            "api_url": api_url,
            "agent_id": None,
            "pending": None,
        }
        if path.exists():
            try:
                saved = json.loads(path.read_text(encoding="utf-8"))
                if saved["version"] != 1 or saved["api_url"] != api_url:
                    raise ValueError
                UUID(saved["agent_id"])
                pending = saved["pending"]
                if pending is not None:
                    if (
                        pending["agent_id"] != saved["agent_id"]
                        or not pending["event_id"].strip()
                    ):
                        raise ValueError
                    timestamp(datetime.fromisoformat(pending["client_timestamp"]))
                self.data = saved
            except (ValueError, KeyError, TypeError, AttributeError):
                raise IntegrationError(
                    "State is invalid or belongs to another API. Use the matching --state file."
                ) from None

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent, delete=False
            ) as file:
                temporary = Path(file.name)
                json.dump(self.data, file, ensure_ascii=False, indent=2)
                file.flush()
                os.fsync(file.fileno())
            temporary.replace(self.path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()

    async def deliver(self, memory: MemoryAPI, payload: dict | None = None) -> dict:
        if payload is not None:
            if self.data["pending"] is not None:
                raise IntegrationError(
                    "A saved observation is pending. Use /retry before recording another."
                )
            if payload["agent_id"] != self.data["agent_id"]:
                raise IntegrationError("Observation belongs to a different agent.")
            self.data["pending"] = payload
            self.save()  # durable BEFORE the first network call
        if self.data["pending"] is None:
            raise IntegrationError("No saved observation to retry.")
        result = await memory.observe(self.data["pending"])
        self.data["pending"] = None
        self.save()  # a crash before this point just replays the receipt next time
        return result


HELP = """Type a message, or:
  /observe <event text>       Save and deliver one deliberate long-term observation
  /retry                     Redeliver the exact pending event (also after restart)
  /correct <memory UUID> <text>  Fix a memory using its current head as the CAS guard
  /scene [ISO-8601 time]      Start a new scene and clear recent conversation
  /help                      Show commands
  /quit                      Exit; agent and pending event stay in --state
"""


def show_reply(reply: dict):
    print(reply["content"])
    print(
        f"Recent messages sent: {reply['recent_messages_sent']}; retained turns: {reply['history_turns_retained']}"
    )
    for item in reply["items"]:
        used = item["memory_id"] in reply["used_memory_ids"]
        print(
            f"  {item['memory_id']} | {item['read_mode']} | score={item['score']:.4f} | sent_to_model={used}"
        )
    if reply["omitted_memory_ids"]:
        print(
            "Some whole memories did not fit --memory-chars; their IDs are listed above."
        )
    print(
        f"Retrieval {reply['retrieval_ms']:.0f}ms; dialogue {reply['dialogue_ms']:.0f}ms; model usage: {reply['model_usage']}"
    )


def show_receipt(receipt: dict):
    print(f"Recorded memory: {receipt['memory_id']} (detail: {receipt['detail_id']})")
    flags = [
        key
        for key in (
            "scoring_failed",
            "embedding_failed",
            "escalation_failed",
            "enrichment_pending",
            "decay_class_unknown",
        )
        if receipt.get(key)
    ]
    if flags:
        print(
            "Accepted with flags: "
            + ", ".join(flags)
            + ". Inspect current state; replaying does not repair a receipt."
        )


async def correct_current(chat: Conversation, memory_id: str, text: str, at: datetime):
    chain = await chat.memory.chain(memory_id)
    if chain["agent_id"] != chat.agent_id:
        raise IntegrationError("That memory belongs to another agent.")
    heads = [detail for detail in chain["details"] if detail["is_live"]]
    if len(heads) != 1:
        raise IntegrationError("Expected one live detail head; inspect the chain.")
    result = await chat.correct(memory_id, heads[0]["detail_id"], text, at)
    print(f"Corrected memory: {result['memory_id']}; recent conversation cleared.")
    return result


async def demo(chat: Conversation, state: LocalState, at: datetime):
    payload = chat.memory.observation(
        chat.agent_id, "The guest left a blue suitcase at the Waystone Inn.", at
    )
    receipt = await state.deliver(chat.memory, payload)
    show_receipt(receipt)
    replay = await chat.memory.observe(payload)
    if replay != receipt:
        raise IntegrationError(
            "Observation replay differed from the original acknowledgement."
        )
    first = await chat.say("What did the guest leave at the inn?", at)
    second = await chat.say("Where was it left?", at)
    show_reply(first)
    show_reply(second)
    if second["recent_messages_sent"] != 2:
        raise IntegrationError(
            "Demo history was not retained; raise --history-turns/--history-chars."
        )
    await correct_current(
        chat,
        receipt["memory_id"],
        "The guest left a green suitcase at the Waystone Inn.",
        at,
    )
    corrected = await chat.say("What did the guest leave at the inn?", at)
    show_reply(corrected)
    await chat.begin_scene(at)
    if chat.history or corrected["recent_messages_sent"]:
        raise IntegrationError("Recent conversation survived a reset.")
    print(
        "PASS application integration: replay, follow-up context, correction and scene reset."
    )


async def run(args, *, clock=lambda: datetime.now(timezone.utc)):
    state = LocalState(args.state, args.base_url)
    if args.agent_id:
        requested = str(UUID(args.agent_id))
        if state.data["agent_id"] not in {None, requested}:
            raise IntegrationError(
                "--agent-id conflicts with the saved agent. Choose another --state file."
            )
        state.data["agent_id"] = requested
        state.save()
    # Two clients: the dialogue key can never become a memory-service header.
    model_headers = {}
    if args.dialogue == "real" and os.environ.get("EXAMPLE_DIALOGUE_API_KEY"):
        model_headers["Authorization"] = (
            "Bearer " + os.environ["EXAMPLE_DIALOGUE_API_KEY"]
        )
    async with (
        httpx.AsyncClient(base_url=args.base_url, timeout=args.timeout) as memory_http,
        httpx.AsyncClient(
            base_url=(args.model_base_url or "http://localhost") + "/",
            headers=model_headers,
            timeout=args.timeout,
        ) as model_http,
    ):
        memory = MemoryAPI(memory_http, observe_attempts=args.observe_attempts)
        complete = (
            fake_dialogue
            if args.dialogue == "fake"
            else ChatCompletionsDialogue(
                model_http,
                args.model,
                max_output_tokens=args.max_output_tokens,
                token_limit_field=args.token_limit_field,
            )
        )
        if state.data["agent_id"] is None:
            state.data["agent_id"] = await memory.create_agent(args.name)
            print(
                f"Created agent: {state.data['agent_id']} (save this ID if local persistence fails)"
            )
            state.save()
        chat = Conversation(
            memory,
            state.data["agent_id"],
            complete,
            history_turns=args.history_turns,
            history_chars=args.history_chars,
            memory_chars=args.memory_chars,
            input_chars=args.input_chars,
            k=args.k,
        )
        at = clock()
        await chat.begin_scene(at)  # validates attachment and freezes the FIRST scene
        print(
            f"Agent: {chat.agent_id}\nInspector: {args.public_url or args.base_url}/ledger?agent={chat.agent_id}"
        )
        print(
            f"Application dialogue: {args.dialogue}. Memory-service provider mode is configured separately."
        )
        if args.dialogue == "fake":
            print("The dialogue stub proves message plumbing only, not answer quality.")
        if state.data["pending"] is not None:
            print(
                "A saved observation is pending. /retry reuses its original key, time and payload."
            )
        if args.demo:
            await demo(chat, state, at)
            return
        print(HELP)
        while True:
            try:
                line = (await asyncio.to_thread(input, "> ")).strip()
                if not line:
                    continue
                command, _, rest = line.partition(" ")
                if command == "/quit":
                    return
                if command == "/help":
                    print(HELP)
                elif command == "/observe":
                    show_receipt(
                        await state.deliver(
                            memory, memory.observation(chat.agent_id, rest, at)
                        )
                    )
                elif command == "/retry":
                    show_receipt(await state.deliver(memory))
                elif command == "/correct":
                    memory_id, _, content = rest.partition(" ")
                    await correct_current(chat, memory_id, content, at)
                elif command == "/scene":
                    next_time = datetime.fromisoformat(rest) if rest else clock()
                    await chat.begin_scene(next_time)
                    at = next_time
                    print("New scene; recent conversation cleared.")
                elif command.startswith("/"):
                    print(HELP)
                else:
                    show_reply(await chat.say(line, at))
            except EOFError:
                return
            except (IntegrationError, ValueError) as exc:
                print(f"ERROR: {exc}")


def cli_endpoint(value, *, allow_path=False):
    try:
        return endpoint(value, allow_path=allow_path)
    except ValueError as exc:
        # argparse's default ValueError handling echoes the rejected value,
        # which could contain a pasted credential or query-string API key.
        raise argparse.ArgumentTypeError(str(exc)) from None


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "--base-url", type=cli_endpoint, default="http://127.0.0.1:8001"
    )
    result.add_argument("--public-url", type=cli_endpoint)
    result.add_argument(
        "--state", type=Path, default=Path("data/integration-example/session.json")
    )
    result.add_argument("--agent-id")
    result.add_argument("--name", default="application-example")
    result.add_argument(
        "--demo",
        action="store_true",
        help="Exercise a fixed conversation without interactive input.",
    )
    result.add_argument("--dialogue", choices=["fake", "real"], default="fake")
    result.add_argument(
        "--model-base-url", type=lambda value: cli_endpoint(value, allow_path=True)
    )
    result.add_argument(
        "--model",
        help="Your application dialogue model name; required for real dialogue.",
    )
    result.add_argument(
        "--token-limit-field",
        choices=["max_tokens", "max_completion_tokens"],
        default="max_tokens",
    )
    result.add_argument("--max-output-tokens", type=int, default=512)
    result.add_argument("--timeout", type=float, default=180)
    result.add_argument("--observe-attempts", type=int, default=3)
    result.add_argument("--history-turns", type=int, default=4)
    result.add_argument("--history-chars", type=int, default=6000)
    result.add_argument("--memory-chars", type=int, default=12000)
    result.add_argument("--input-chars", type=int, default=4000)
    result.add_argument("--k", type=int, default=3)
    return result


def main(argv=None):
    cli = parser()
    args = cli.parse_args(argv)
    if args.dialogue == "real" and (
        not args.model_base_url or not args.model or not args.model.strip()
    ):
        cli.error(
            "Real dialogue requires --model-base-url and --model; set EXAMPLE_DIALOGUE_API_KEY if needed."
        )
    if (
        args.history_turns < 0
        or args.history_chars < 0
        or min(args.memory_chars, args.input_chars, args.k, args.max_output_tokens) < 1
    ):
        cli.error(
            "History limits must be nonnegative; other size limits must be positive."
        )
    if (
        not math.isfinite(args.timeout)
        or args.timeout <= 0
        or not 1 <= args.observe_attempts <= 10
    ):
        cli.error("Use a finite positive timeout and 1-10 observe attempts.")
    try:
        asyncio.run(run(args))
        return 0
    except (IntegrationError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1
    except OSError:
        print(
            "ERROR: Could not read/write application state. Keep its pending event and recover the printed agent ID."
        )
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
