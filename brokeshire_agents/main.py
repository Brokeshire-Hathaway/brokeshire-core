import asyncio
from asyncio import Queue
from typing import Any, Literal, cast

from fastapi import FastAPI, Request
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel
from rich import print
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from brokeshire_agents.agent_router.intent_classifier import INTENT
from brokeshire_agents.agent_router.router import AgentTeamSessionManager, Router
from brokeshire_agents.bg_tasks import add_bg_task, delete_task
from brokeshire_agents.common.agent_team import ExpressionSuggestion
from brokeshire_agents.common.types import MessageType
from brokeshire_agents.education.education import upload_doc_memory

app = FastAPI()


class MessageContext(BaseModel):
    is_response: bool
    message: str


class RequestMessage(BaseModel):
    user_chat_id: str
    client_id: int
    message: str
    message_type: MessageType
    context: list[MessageContext]
    store_transaction: Any
    requested_routes: list[INTENT] | None = None
    user_address: str | None = None
    required_route: INTENT | None = None


def context_to_messages(
    context: list[MessageContext],
):
    return [
        cast(
            ChatCompletionMessageParam,
            {"role": "assistant" if m.is_response else "user", "content": m.message},
        )
        for m in context
    ]


ResponseStatus = Literal["done", "processing", "error"]


class Response(BaseModel):
    status: ResponseStatus
    message: str
    intent_suggestions: list[str] | None = None
    expression_suggestions: list[ExpressionSuggestion] | None = None
    sign_tx_url: str | None = None
    transaction_hash: str | None = None
    reroute_recommendations: list | None = None


@app.get("/")
def read_root():
    return {"message": "Hello World"}


agent_team_session_manager = AgentTeamSessionManager()
add_bg_task(asyncio.create_task(upload_doc_memory()))

ONE_MINUTE_TIMEOUT = 60


def event_router(
    thread_id: str,
    body: RequestMessage,
    request: Request,
    routes: list[INTENT] | None = None,
):
    """Default event router for the threads API."""

    message_queue: Queue[Response] = Queue()

    # ===================================================
    # Returning Response with reroute recommendations
    # ===================================================

    def on_activity(activity: str):
        response = Response(status="processing", message=activity)
        message_queue.put_nowait(response)

    session_id = agent_team_session_manager.get_session_id(
        body.user_chat_id, thread_id, body.client_id
    )
    print(f"Session ID: {session_id}")
    print(f"thread_id: {thread_id}")
    print(f"body.user_chat_id: {body.user_chat_id}")
    print(f"body.client_id: {body.client_id}")
    print(f"body.message: {body.message}")
    print(f"body.context: {body.context}")
    print(f"body.store_transaction: {body.store_transaction}")
    print(f"request: {request}")
    print(f"body.required_route: {body.required_route}")

    async def send_message():
        router = Router(agent_team_session_manager, routes, body.requested_routes)
        try:
            response_message = await router.send(
                body.user_chat_id,
                body.store_transaction,
                session_id,
                body.message,
                body.message_type,
                on_activity,
                context=context_to_messages(body.context),
                user_address=body.user_address,
                required_route=body.required_route,
            )
            response = Response(
                status="done",
                message=response_message["message"],
                intent_suggestions=response_message["intent_suggestions"],
                expression_suggestions=response_message["expression_suggestions"],
                sign_tx_url=response_message["sign_url"],
                transaction_hash=response_message["transaction_hash"],
                reroute_recommendations=response_message["route_recommendations"],
            )
        except Exception as e:
            response = Response(status="error", message=str(e))
        message_queue.put_nowait(response)

    async def event_generator():
        task = asyncio.create_task(send_message())
        add_bg_task(task)
        while True:
            if await request.is_disconnected():
                break

            try:
                async with asyncio.timeout(ONE_MINUTE_TIMEOUT):
                    response = await message_queue.get()
            except TimeoutError:
                delete_task(task)
                agent_team_session_manager.remove_session(session_id)
                yield ServerSentEvent(
                    {"message": "Operation aborted due to timeout"}, event="error"
                )
                return

            json = response.model_dump_json()
            match response.status:
                case "done":
                    yield ServerSentEvent(json, event="done")
                    break
                case "processing":
                    yield ServerSentEvent(json, event="activity")
                case "error":
                    yield ServerSentEvent(json, event="error")
                    break

    # Select route for thread
    # Route to proper agent team
    # send activiy updates from agent team
    # Wait for agent team to reply
    # send post response
    # close connection

    # Repeat

    return EventSourceResponse(event_generator())


@app.post("/v1/threads/{thread_id}/private")
async def create_message(thread_id: str, body: RequestMessage, request: Request):
    return event_router(thread_id, body, request)


@app.post("/v1/threads/{thread_id}/group")
async def create_message_group(thread_id: str, body: RequestMessage, request: Request):
    return event_router(
        thread_id,
        body,
        request,
        routes=[
            "crypto_price_query",
            "market_news_query",
            "explanation_query",
            "capabilities_query",
            "advice_query",
            "unclear",
            "out_of_scope",
            "terminate",
        ],
    )
