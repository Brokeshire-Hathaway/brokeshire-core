import pytest
from rich import print
from typing import Any, Literal
from ember_agents.common.agents.entity_extractor import (
    ExtractedEntities,
    ExtractedEntity,
)

from ember_agents.common.conversation import ContextMessage, Conversation, Message
from ember_agents.earn.earn_agent_team import (
    AgentState,
    Participant,
    EarnAgentTeam,
    EarnSchema,
)


"""@pytest.mark.parametrize(
    "user_messages",
    [
        [
            "Earn eth"
        ],
        ["get yield on arb"],
        ["deposit 100 op on beefy"],
        ["earn on superform"],
        [
            "get yield on beefy"
        ],
        ["find highest yield on bnb"],
        ["deposit into vault 0x5A47993216fa6ACaf93418f9830cee485e82d0ba"],
    ],
)
@pytest.mark.skip
async def test_earn_token_agent_team(user_messages: list[str]):
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
    earn_token_agent_team = EarnTokenAgentTeam(
        on_complete=on_complete,
        store_transaction_info=store_transaction_info,
        user_chat_id="1129320042",
    )

    while not is_complete:
        user_message = get_user_message()
        response = await earn_token_agent_team.send(user_message)

        print("RESPONSE: ")
        print(response)
"""


@pytest.mark.skip
async def test_earn_token_schema_validation():
    entities = {
        "deposit_token": {"named_entity": "usdc", "confidence_level": "high"},
        "deposit_chain": {"named_entity": "arbitrum", "confidence_level": "high"},
        "amount": {"named_entity": "100", "confidence_level": "high"},
    }
    schema = EarnSchema.model_validate(entities)


@pytest.mark.parametrize(
    "user_message",
    [
        "get yield",
    ],
)
@pytest.mark.skip
async def test_schema_validator_action(user_message: str):
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
    earn_token_agent_team = EarnAgentTeam(
        on_complete=on_complete,
        store_transaction_info=store_transaction_info,
        user_chat_id="1129320042",
    )

    message1: Message = {
        "sender_name": "user",
        "content": user_message,
        "is_visible_to_user": True,
    }

    context_message1: ContextMessage = {
        "role": "user",
        "content": f"<sender_name>user</sender_name>\n<message>{user_message}</message>",
    }

    conversation: Conversation[Participant] = {
        "history": [message1],
        "contexts": {
            "user": [context_message1],
        },
        "participants": [
            "user",
            "entity_extractor",
            "schema_validator",
            "clarifier",
            "transactor",
        ],
    }

    state = AgentState(
        conversation=conversation,
        user_utterance=user_message,
        intent_classification="earn_token_action",
    )
    try:
        result = await earn_token_agent_team._schema_validator_action(state)
        print(f"result: {result}")
    except Exception as e:
        print(f"error: {e}")
