import asyncio
from typing import Literal, Union

from fastapi import FastAPI, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from ember_agents.agent_router.router import AgentTeamSessionManager, Router

app = FastAPI()


class Message(BaseModel):
    sender_did: str
    message: str


ResponseState = Literal["done", "processing", "error"]


class Response(BaseModel):
    state: ResponseState
    message: str


@app.get("/")
def read_root():
    return {"message": "Hello World"}


# POST /v1/dids/{did}/threads
# POST /v1/threads/{thread_id}/messages

agent_team_session_manager = AgentTeamSessionManager()


@app.post("/v1/threads/{thread_id}/messages")
async def create_message(thread_id: str, message: Message, request: Request):
    message_queue = asyncio.Queue()

    def on_activity(activity: str):
        response = Response(state="processing", message=activity)
        message_queue.put_nowait(response)

    async def send_message():
        router = Router(agent_team_session_manager)
        sender_did = message.sender_did
        try:
            response_message = await router.send(
                sender_did, thread_id, message.message, on_activity
            )
            response = Response(state="done", message=response_message)
        except Exception as e:
            response = Response(state="error", message=str(e))
        message_queue.put_nowait(response)

    async def event_generator():
        asyncio.create_task(send_message())
        while True:
            if await request.is_disconnected():
                print(f"[/v1/threads/{thread_id}/messages] Client disconnected")
                break
            response = await message_queue.get()
            print(f"[/v1/threads/{thread_id}/messages] Sending response: {response}")
            yield response
            if response.state == "done" or response.state == "error":
                break

    # Select route for thread
    # Route to proper agent team
    # send activiy updates from agent team
    # Wait for agent team to reply
    # send post response
    # close connection

    # Repeat

    return EventSourceResponse(event_generator())
