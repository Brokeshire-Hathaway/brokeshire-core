import pytest
from ember_agents.agent_router.router import router

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
