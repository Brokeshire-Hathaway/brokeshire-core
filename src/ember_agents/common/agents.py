import asyncio
from asyncio import Future, Queue
from typing import Callable, Protocol


class AgentTeam(Protocol):
    _is_initialized: bool = False
    _on_activity: Callable[[str], None] | None = None
    _user_message_queue: Queue[str] = Queue()
    # TODO: might update to be a queue in case of an API reconnection
    _agent_team_response: Future[str] = Future()
    on_complete: Callable[[str, str], None] | None = None
    sender_did: str
    thread_id: str

    def __init__(self, sender_did: str, thread_id: str):
        self.sender_did = sender_did
        self.thread_id = thread_id

    async def _run_conversation(self, message: str):
        ...
        # a_initiate_chat()
        # user_reply: Callable[[], Awaitable[str]]
        # assistant_reply: Callable[[str], None]

    def _send_team_response(self, message: str):
        # DEBUG
        print("===== _send_team_response =====")
        print(message)
        self._agent_team_response.set_result(message)

    def _prepare_team_response(self):
        self._agent_team_response: Future[str] = Future()

    async def _on_team_response(self) -> str:
        # DEBUG
        print("===== _on_team_response =====")
        print("===== self._agent_team_response: new Future created =====")
        await self._agent_team_response
        return self._agent_team_response.result()

    async def _get_human_messages(self) -> str:
        # human_reply: Callable[[], Awaitable[str]]
        # assistant_reply: Callable[[str], None]

        messages = []

        async def collect_from_queue():
            message = await self._user_message_queue.get()
            messages.append(message)
            self._user_message_queue.task_done()

        # Collect all existing messages
        while not self._user_message_queue.empty():
            await collect_from_queue()

        # Wait for and collect a new message
        await collect_from_queue()

        return "\n\n".join(messages)

    def _init_conversation(self, message: str):
        # NOTE: self._run_conversation does not return until the entire team conversation is complete

        # TODO: Probably should first have a setup method, then execute a run method
        async def task():
            await self._run_conversation(message)
            if self.on_complete is not None:
                # DEBUG
                print("===== _init_conversation: self.on_complete =====")
                self.on_complete(self.sender_did, self.thread_id)

        asyncio.create_task(task())

        self._is_initialized = True

    def _send_activity_update(self, message: str):
        if self._on_activity is not None:
            self._on_activity(message)

    def get_activity_updates(self, on_activity: Callable[[str], None]):
        self._on_activity = on_activity

    async def send(self, message: str):
        # send message to human proxy agent
        # await and return response

        self._prepare_team_response()

        if not self._is_initialized:
            # asyncio.create_task(self._init_conversation(message))
            self._init_conversation(message)
        else:
            self._user_message_queue.put_nowait(message)

        return await self._on_team_response()
