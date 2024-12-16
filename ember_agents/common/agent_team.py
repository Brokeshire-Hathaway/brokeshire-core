import asyncio
from abc import ABC, abstractmethod
from asyncio import Future, InvalidStateError, Queue
from collections.abc import Callable
from typing import Any, TypedDict, cast

import rich
from langchain_core.runnables.config import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Interrupt
from openai.types.chat import ChatCompletionMessageParam

from ember_agents.bg_tasks import add_bg_task


class SendResponse(TypedDict):
    message: str
    sign_url: str | None
    transaction_hash: str | None


class AgentTeam(ABC):
    # TODO: might update to be a queue in case of an API reconnection

    def __init__(self, on_complete: Callable[[], Any]):
        self._user_message_queue: Queue[dict[str, Any]] = Queue()
        self._is_initialized: bool = False
        self._on_activity: Callable[[str], None] | None = None
        self._on_complete = on_complete
        self._agent_team_response: Future[SendResponse] = Future()

    @abstractmethod
    async def _run_conversation(
        self, message: str, context: list[ChatCompletionMessageParam] | None = None
    ):
        """Executes a conversation with a user."""

    async def _run_graph(
        self,
        app: CompiledStateGraph,
        config: RunnableConfig,
        message: str,
        participants: list[str],
    ):
        async def stream_updates(graph_input: dict[str, Any] | Any):
            async for chunk in app.astream(graph_input, config, stream_mode="updates"):
                for key, item in chunk.items():
                    # rich.print(f"=== Stream Update ===")
                    # rich.print(f"{key}: {item}")
                    """rich.print(f"interrupt: {item[0]}")
                    rich.print(
                        f"is instance of Interrupt: {isinstance(item, Interrupt)}"
                    )
                    rich.print(
                        f"item.value: {(interrupt_value := item.get('value', None))}"
                    )"""
                    if (
                        key == "__interrupt__"
                        and (interrupt := next(iter(item), None))
                        and isinstance(interrupt, Interrupt)
                    ):
                        # rich.print(f"=== Interrupt ===")
                        # rich.print(interrupt.value)
                        raise Exception(interrupt.value)
                        # self._send_team_response(interrupt.value)

                    rich.print(
                        f"""
╭───┚ {key} ┖───
╧═╾ State Update ╼══
{item}
╤═╾
╰───"""
                    )

        try:
            intent_classification = "earn_token_action"
            graph_input = {
                "conversation": {
                    "history": [
                        {
                            "sender_name": "user",
                            "content": message,
                            "is_visible_to_user": True,
                        }
                    ],
                    "participants": participants,
                },
                "user_utterance": message,
                "intent_classification": intent_classification,
            }

            is_pending_interrupt = True
            while is_pending_interrupt:
                await stream_updates(graph_input)

                snapshot = app.get_state(config)

                """interrupt = None
                if snapshot.tasks and snapshot.tasks[0].interrupts:
                    interrupt = snapshot.tasks[0].interrupts[0]
                if interrupt is not None:
                    is_pending_interrupt = False
                    self._send_team_response(interrupt.value)
                    continue"""

                is_run_complete = snapshot.values.get("is_run_complete")
                response = snapshot.values["conversation"]["history"][-1]["content"]

                if is_run_complete:
                    rich.print("=== is_run_complete is True ===")
                    is_pending_interrupt = False
                    sign_url = snapshot.values.get("sign_url")
                    transaction_hash = snapshot.values.get("transaction_hash")
                    self._send_team_response(response, sign_url, transaction_hash)
                    continue

                rich.print("=== is_run_complete is False ===")

                user_message_future = asyncio.create_task(self._get_human_messages())

                if isinstance(response, str):
                    self._send_team_response(response)

                user_message = await user_message_future

                rich.print(f"=== user_message ===")
                rich.print(user_message)

                node_name = "ask_user"
                state_values = {
                    "conversation": {
                        "history": [
                            {
                                "sender_name": "user",
                                "content": user_message,
                                "is_visible_to_user": True,
                            }
                        ]
                    }
                }
                rich.print(f"=== update state ===")
                app.update_state(
                    config,
                    state_values,
                    as_node=node_name,
                )
                graph_input = None

        except Exception as error:
            rich.print("=== Exception as error ===")
            rich.print(error)
            self._send_team_response(str(error))

    def _send_team_response(
        self,
        message: str,
        sign_url: str | None = None,
        transaction_hash: str | None = None,
    ):
        try:
            self._agent_team_response.set_result(
                {
                    "message": message,
                    "sign_url": sign_url,
                    "transaction_hash": transaction_hash,
                }
            )
        except InvalidStateError as e:
            print(e, flush=True)
            raise e

    async def _on_team_response(self) -> SendResponse:
        try:
            await self._agent_team_response
        except Exception as e:
            print(e)
            raise e
        return self._agent_team_response.result()

    async def _get_human_messages(self) -> str:
        # human_reply: Callable[[], Awaitable[str]]
        # assistant_reply: Callable[[str], None]

        messages = []

        async def collect_from_queue():
            message = await self._user_message_queue.get()
            messages.append(message["message"])
            self._user_message_queue.task_done()

        # Collect all existing messages
        while not self._user_message_queue.empty():
            await collect_from_queue()

        # Wait for and collect a new message
        await collect_from_queue()

        return "\n\n".join(messages)

    def _init_conversation(
        self, message: str, context: list[ChatCompletionMessageParam] | None = None
    ):
        # NOTE: self._run_conversation does not return until the entire team conversation is complete

        # TODO: Probably should first have a setup method, then execute a run method
        async def task():
            await self._run_conversation(message, context=context)
            if self._on_complete is not None:
                self._on_complete()

        add_bg_task(asyncio.create_task(task()))
        self._is_initialized = True

    def _send_activity_update(self, message: str):
        if self._on_activity is not None:
            self._on_activity(message)

    def get_activity_updates(self, on_activity: Callable[[str], None]):
        self._on_activity = on_activity

    async def send(
        self, message: str, context: list[ChatCompletionMessageParam] | None = None
    ) -> SendResponse:
        # send message to human proxy agent
        # await and return response

        self._agent_team_response = Future()
        if not self._is_initialized:
            # asyncio.create_task(self._init_conversation(message))
            self._init_conversation(message, context=context)
        else:
            self._user_message_queue.put_nowait(
                {"message": message, "context": context}
            )

        return await self._on_team_response()
