from typing import NamedTuple

import pytest
from ember_agents.agent_router.router import Router


@pytest.mark.parametrize(
    "message, expected",
    [
        ("Send 5 Bitcoin to Alice", ""),
    ],
)
async def test_create_message(message: str, expected: str):
    """
    ## DESIGN PATTERN OPTIONS
    # Build
    response_message = await router.send(thread_id, message, activity_callback)
    # Tear down


    # Build
    class Response(NamedTuple):
        reply_message: str | None
        activity_message: str | None
        state: str
    def response_callback(response: Response):
        print(response_message)
    router.send(thread_id, message, response_callback)
    # Tear down


    # Build
    agent_team = await router.get_active_agent_team(thread_id, message)
    response_message = await agent_team.send(message, activity_callback)
    # Tear down


    # Build
    agent_team = await router.get_active_agent_team(thread_id, message)
    agent_team.get_activity_updates(activity_callback)
    response_message = await agent_team.send(message)
    # Tear down
    """
