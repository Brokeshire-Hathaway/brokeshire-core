import asyncio
from asyncio import Queue
from typing import Literal

from fastapi import FastAPI, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from ember_agents.agent_router.router import AgentTeamSessionManager, Router
from ember_agents.education.education import upload_doc_memory

app = FastAPI()


class Message(BaseModel):
    sender_uid: str
    message: str


ResponseStatus = Literal["done", "processing", "error"]


class Response(BaseModel):
    status: ResponseStatus
    message: str


@app.get("/")
def read_root():
    return {"message": "Hello World"}


# POST /v1/dids/{did}/threads
# POST /v1/threads/{thread_id}/messages

agent_team_session_manager = AgentTeamSessionManager()


asyncio.create_task(upload_doc_memory())


@app.post("/v1/threads/{thread_id}/messages")
async def create_message(thread_id: str, body: Message, request: Request):
    # DEBUG
    print(f"[/v1/threads/{thread_id}/messages] Received message: {body}", flush=True)
    message_queue: Queue[Response] = Queue()

    def on_activity(activity: str):
        response = Response(status="processing", message=activity)
        message_queue.put_nowait(response)

    async def send_message():
        print(f"Session manager: {agent_team_session_manager}", flush=True)
        print({str(agent_team_session_manager._sessions)})
        router = Router(agent_team_session_manager)
        sender_did = body.sender_uid
        try:
            response_message = await router.send(
                sender_did, thread_id, body.message, on_activity
            )
            response = Response(status="done", message=response_message)
        except Exception as e:
            response = Response(status="error", message=str(e))
        message_queue.put_nowait(response)

    async def event_generator():
        asyncio.create_task(send_message())
        while True:
            if await request.is_disconnected():
                print(
                    f"[/v1/threads/{thread_id}/messages] Client disconnected",
                    flush=True,
                )
                break
            response = await message_queue.get()
            json = response.json()
            print(
                f"[/v1/threads/{thread_id}/messages] Sending response: {json}",
                flush=True,
            )
            print(type(json))
            print(json)
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
