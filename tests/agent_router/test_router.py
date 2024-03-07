import uuid

import pytest
from ember_agents.agent_router.router import AgentTeamSessionManager, Router

"""
@pytest.mark.parametrize(
    "intent, expected",
    [
        ("What is DeFi?", "internal"),
        ("Send 5 Bitcoin to Alice", "send"),
        ("What is the price of Bitcoin?", "market"),
        ("tell me a joke", "internal"),
        ("compare ethereum and cardano", "market"),
        ("compare the technology of ethereum and cardano", "internal"),
        ("differences between dogecoin and bitcoin", "internal"),
        ("0.0001 link to joe", "send"),
        ("ada performance", "market"),
    ],
)
def test_default_route(intent: str, expected: str):
    assert router(intent) == expected
"""


@pytest.mark.parametrize(
    "message",
    [
        ("Send 5 uni to Alice"),
    ],
)
@pytest.mark.skip
async def test_send_route(message: str):
    agent_team_sessions = AgentTeamSessionManager()
    router = Router(agent_team_sessions)
    sender_did = str(uuid.uuid4())
    thread_id = str(uuid.uuid4())
    response = await router.send(sender_did, thread_id, message)
    print(response)
    new_message = "0xc6A9f8f20d79Ae0F1ADf448A0C460178dB6655Cf is Alice's address. Use whatever you have for uni."
    response = await router.send(sender_did, thread_id, new_message)
    print(response)
    new_message = "execute"
    response = await router.send(sender_did, thread_id, new_message)
    print(response)
