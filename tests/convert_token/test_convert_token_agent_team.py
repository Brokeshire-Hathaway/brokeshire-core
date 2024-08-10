import pytest
from pprint import pprint
from typing import Any, Literal

from ember_agents.convert_token.convert_token_agent_team import (
    ConvertTokenSchema,
    convert_token_agent_team,
)


@pytest.mark.parametrize(
    "user_utterance, user_responses",
    [
        (
            "swap 5 usdc for eth",
            ["from arbitrum to base"],
        ),
        (
            "swap wbtc",
            ["to usdt token", "polygon to arbitrum", "8.21 usdt"],
        ),
        (
            "Buy render",
            ["100 usdc", "from ethereum to optimism"],
        ),
        (
            "Buy cookie",
            ["with usdt", "linea to blast", "recieve 55"],
        ),
        (
            "change sol for arb",
            ["20 sol to 11 arb", "from solana to arbitrum", "11 arb"],
        ),
    ],
)
@pytest.mark.skip
async def test_convert_token_agent_team(user_utterance: str, user_responses: list[str]):
    print(f"\n--- {user_utterance}")

    next_user_response_index = 0

    async def get_user_response():
        nonlocal next_user_response_index
        next_user_response = user_responses[next_user_response_index]
        next_user_response_index += 1
        return next_user_response

    response = await convert_token_agent_team(user_utterance, get_user_response)

    print("RESPONSE:")
    pprint(response)


@pytest.mark.skip
async def test_convert_token_schema_validation():
    entities = {
        "from_token": {"value": "usdc", "confidence_percentage": 99.0},
        "from_network": {"value": "arbitrum", "confidence_percentage": 99.0},
        "to_network": {"value": "base", "confidence_percentage": 99.0},
    }
    schema = ConvertTokenSchema.model_validate(entities)
    print(f"schema: {schema}")
