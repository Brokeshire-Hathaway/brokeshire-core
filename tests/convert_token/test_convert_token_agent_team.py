import pytest
from rich import print
from typing import Any, Literal

from ember_agents.convert_token.convert_token_agent_team import (
    ConvertTokenAgentTeam,
    ConvertTokenSchema,
)


"""
        
"""


@pytest.mark.parametrize(
    "user_messages",
    [
        ["Buy cookie", "with usdt", "from linea to blast", "recieve 55", "yes"],
        ["swap 5 usdc for eth", "from arbitrum to base", "yes ETH"],
        ["change sol for arb", "20 sol to 11 arb", "from solana to arbitrum", "11 arb"],
        [
            "swap wbtc",
            "to usdt token",
            "polygon to arbitrum",
            "8.21 usdt",
            "yes, from wbtc",
        ],
        ["Buy render", "100 usdc", "from ethereum to optimism"],
    ],
)
# @pytest.mark.skip
async def test_convert_token_agent_team(user_messages: list[str]):
    print(f"\n--- {user_messages[0]}")

    next_user_message_index = 0

    def get_user_message():
        nonlocal next_user_message_index
        next_user_message = user_messages[next_user_message_index]
        next_user_message_index += 1
        return next_user_message

    is_complete = False

    def on_complete():
        print("COMPLETE")
        nonlocal is_complete
        is_complete = True

    store_transaction_info = {
        "authorization_header": "",
        "endpoint": "/public/telegram/transaction",
        "method": "POST",
    }
    convert_token_agent_team = ConvertTokenAgentTeam(
        on_complete=on_complete,
        store_transaction_info=store_transaction_info,
        user_chat_id="1129320042",
    )

    while not is_complete:
        user_message = get_user_message()
        response = await convert_token_agent_team.send(user_message)

        print("RESPONSE: ")
        print(response)


@pytest.mark.skip
async def test_convert_token_schema_validation():
    entities = {
        "from_amount": {"value": "5", "confidence_level": "high"},
        "from_token": {"value": "usdc", "confidence_level": "high"},
        "from_network": {"value": "arbitrum", "confidence_level": "high"},
        "to_token": {"value": "eth", "confidence_level": "high"},
        "to_network": {"value": "base", "confidence_level": "high"},
    }
    schema = ConvertTokenSchema.model_validate(entities)
    print(f"schema: {schema}")
