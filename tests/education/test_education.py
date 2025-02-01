from pprint import pprint

import pytest
from brokeshire_agents.education.education import education


@pytest.mark.parametrize(
    "user_request",
    [
        # ("how does chainlink work?"),
        # ("what is a smart contract?"),
        ("tell me about yourself"),
    ],
)
@pytest.mark.skip
async def test_education(user_request: str):
    print(f"User request: {user_request}", flush=True)
    response = await education(user_request)

    pprint(response)
