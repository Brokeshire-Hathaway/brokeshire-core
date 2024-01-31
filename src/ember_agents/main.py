import asyncio
from typing import Union

from fastapi import FastAPI, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from ember_agents.agent_router.router import AgentTeamSessionManager, Router

app = FastAPI()


class Message(BaseModel):
    message: str


@app.get("/")
def read_root():
    return {"message": "Hello World"}


# POST /v1/dids/{did}/threads
# POST /v1/threads/{thread_id}/messages

agent_team_session_manager = AgentTeamSessionManager()


@app.post("/v1/threads/{thread_id}/messages")
async def create_message(thread_id: str, message: Message, request: Request):
    async def event_generator():
        count = 0
        while True:
            if await request.is_disconnected():
                break

            await asyncio.sleep(1)
            count += 1
            yield {
                "id": count,
                "data": f"Message {count}",
            }

    # Select route for thread
    # Route to proper agent team
    # send activiy updates from agent team
    # Wait for agent team to reply
    # send post response
    # close connection

    # Repeat

    # router = Router(agent_team_session_manager)
    # agent_team = router.get_active_agent_team(thread_id, message.message)
    # agent_team.get_activity_updates(lambda activity: None)
    # response = await agent_team.send(message.message)

    return EventSourceResponse(event_generator())
