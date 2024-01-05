import pytest
from ember_agents.agent_router.router import router


@pytest.mark.parametrize(
    "intent, expected",
    [
        ("What is DeFi?", "default"),
        ("Send 5 Bitcoin to Alice", "send"),
        ("What is the price of Bitcoin?", "market"),
    ],
)
def test_default_route(intent: str, expected: str):
    assert router(intent) == expected
