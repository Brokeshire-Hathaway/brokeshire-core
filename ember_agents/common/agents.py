import asyncio
from abc import ABC, abstractmethod
from asyncio import Future, InvalidStateError, Queue
from collections.abc import Callable
from typing import Any

from openai.types.chat import ChatCompletionMessageParam

from ember_agents.bg_tasks import add_bg_task


class AgentTeam(ABC):
    # TODO: might update to be a queue in case of an API reconnection

    def __init__(self, on_complete: Callable[[], Any]):
        self._user_message_queue: Queue[dict[str, Any]] = Queue()
        self._is_initialized: bool = False
        self._on_activity: Callable[[str], None] | None = None
        self._agent_team_response: Future[str] = Future()
        self._on_complete = on_complete
        self.sign_url: str | None = None

    @abstractmethod
    async def _run_conversation(
        self, message: str, context: list[ChatCompletionMessageParam] | None = None
    ):
        """Executes a conversation with a user."""

    def _send_team_response(self, message: str):
        try:
            self._agent_team_response.set_result(message)
        except InvalidStateError as e:
            print(e, flush=True)
            raise e

    async def _on_team_response(self) -> str:
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
    ):
        # send message to human proxy agent
        # await and return response

        if not self._is_initialized:
            # asyncio.create_task(self._init_conversation(message))
            self._init_conversation(message, context=context)
        else:
            self._user_message_queue.put_nowait(
                {"message": message, "context": context}
            )

        return await self._on_team_response()
