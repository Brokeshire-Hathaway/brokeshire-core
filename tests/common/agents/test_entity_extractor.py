import pytest
from typing import Literal, TypedDict

from ember_agents.common.agents.entity_extractor import (
    extract_entities,
)


class ExpectedNamedEntity(TypedDict):
    value: str
    confidence_threshold: float


class ExpectedClassification(TypedDict):
    named_entity: list[ExpectedNamedEntity]
    confidence_threshold: float


SwapEntityCategories = list[
    Literal[
        "from_amount",
        "from_token",
        "from_network",
        "to_amount",
        "to_token",
        "to_network",
    ]
]


SendEntityCategories = list[
    Literal[
        "amount",
        "token",
        "network",
        "recipient",
    ]
]


EntityCategories = SwapEntityCategories | SendEntityCategories


swapEntityCategories = [
    "from_amount",
    "from_token",
    "from_network",
    "to_amount",
    "to_token",
    "to_network",
]


sendEntityCategories = [
    "amount",
    "token",
    "network",
    "recipient",
]

additionalContextSwap = "User Intent: convert_token_action"
additionalContextSend = "User Intent: send_token_action"


@pytest.mark.parametrize(
    "text, entity_categories, additional_context, expected_extracted_entities",
    [
        (
            "swap 5 usdc for eth",
            swapEntityCategories,
            additionalContextSwap,
            {
                "from_amount": {
                    "named_entity": [{"value": "5", "confidence_threshold": 99}],
                    "confidence_threshold": 99,
                },
                "from_token": {
                    "named_entity": [{"value": "usdc", "confidence_threshold": 99}],
                    "confidence_threshold": 99,
                },
                "from_network": None,
                "to_amount": None,
                "to_token": {
                    "named_entity": [{"value": "eth", "confidence_threshold": 99}],
                    "confidence_threshold": 99,
                },
                "to_network": None,
            },
        ),
        (
            "swap op",
            swapEntityCategories,
            additionalContextSwap,
            {
                "from_amount": None,
                "from_token": {
                    "named_entity": [{"value": "op", "confidence_threshold": 90}],
                    "confidence_threshold": 99,
                },
                "from_network": None,
                "to_amount": None,
                "to_token": {
                    "named_entity": [{"value": "op", "confidence_threshold": 90}],
                    "confidence_threshold": 99,
                },
                "to_network": None,
            },
        ),
        (
            "I want puppy",
            swapEntityCategories,
            additionalContextSwap,
            {
                "from_amount": None,
                "from_token": None,
                "from_network": None,
                "to_amount": None,
                "to_token": {
                    "named_entity": [{"value": "puppy", "confidence_threshold": 40}],
                    "confidence_threshold": 95,
                },
                "to_network": None,
            },
        ),
        (
            "Buy cookies",
            swapEntityCategories,
            additionalContextSwap,
            {
                "from_amount": None,
                "from_token": None,
                "from_network": None,
                "to_amount": None,
                "to_token": {
                    "named_entity": [{"value": "cookies", "confidence_threshold": 85}],
                    "confidence_threshold": 95,
                },
                "to_network": None,
            },
        ),
        (
            "buy render",
            swapEntityCategories,
            additionalContextSwap,
            {
                "from_amount": None,
                "from_token": None,
                "from_network": None,
                "to_amount": None,
                "to_token": {
                    "named_entity": [{"value": "render", "confidence_threshold": 99}],
                    "confidence_threshold": 95,
                },
                "to_network": None,
            },
        ),
        (
            "give me bitcoin",
            swapEntityCategories,
            additionalContextSwap,
            {
                "from_amount": None,
                "from_token": None,
                "from_network": None,
                "to_amount": None,
                "to_token": {
                    "named_entity": [{"value": "bitcoin", "confidence_threshold": 65}],
                    "confidence_threshold": 99,
                },
                "to_network": None,
            },
        ),
        (
            "bitcoin",
            swapEntityCategories,
            additionalContextSwap,
            {
                "from_amount": None,
                "from_token": {
                    "named_entity": [{"value": "bitcoin", "confidence_threshold": 99}],
                    "confidence_threshold": 99,
                },
                "from_network": None,
                "to_amount": None,
                "to_token": None,
                "to_network": None,
            },
        ),
        (
            "I want cookies",
            swapEntityCategories,
            additionalContextSwap,
            {
                "from_amount": None,
                "from_token": None,
                "from_network": None,
                "to_amount": None,
                "to_token": {
                    "named_entity": [{"value": "cookies", "confidence_threshold": 90}],
                    "confidence_threshold": 99,
                },
                "to_network": None,
            },
        ),
        (
            "give eth to friend",
            sendEntityCategories,
            sendEntityCategories,
            {
                "amount": None,
                "token": {
                    "named_entity": [{"value": "eth", "confidence_threshold": 99}],
                    "confidence_threshold": 99,
                },
                "network": None,
                "recipient": {
                    "named_entity": [{"value": "friend", "confidence_threshold": 99}],
                    "confidence_threshold": 99,
                },
            },
        ),
        (
            "change sol for arb",
            swapEntityCategories,
            additionalContextSwap,
            {
                "from_amount": None,
                "from_token": {
                    "named_entity": [{"value": "sol", "confidence_threshold": 99}],
                    "confidence_threshold": 99,
                },
                "from_network": None,
                "to_amount": None,
                "to_token": {
                    "named_entity": [{"value": "arb", "confidence_threshold": 99}],
                    "confidence_threshold": 99,
                },
                "to_network": None,
            },
        ),
        (
            "my friend wants some eth",
            sendEntityCategories,
            sendEntityCategories,
            {
                "amount": None,
                "token": {
                    "named_entity": [{"value": "eth", "confidence_threshold": 99}],
                    "confidence_threshold": 99,
                },
                "network": None,
                "recipient": {
                    "named_entity": [
                        {"value": "my friend", "confidence_threshold": 99}
                    ],
                    "confidence_threshold": 55,
                },
            },
        ),
        (
            "Swap WBTC from Polygon network to receive 8.21 USDT on the Arbitrum network.",
            swapEntityCategories,
            additionalContextSwap,
            {
                "from_amount": None,
                "from_token": {
                    "named_entity": [{"value": "WBTC", "confidence_threshold": 99}],
                    "confidence_threshold": 99,
                },
                "from_network": {
                    "named_entity": [{"value": "Polygon", "confidence_threshold": 99}],
                    "confidence_threshold": 99,
                },
                "to_amount": {
                    "named_entity": [{"value": "8.21", "confidence_threshold": 99}],
                    "confidence_threshold": 99,
                },
                "to_token": {
                    "named_entity": [{"value": "USDT", "confidence_threshold": 99}],
                    "confidence_threshold": 99,
                },
                "to_network": {
                    "named_entity": [{"value": "Arbitrum", "confidence_threshold": 99}],
                    "confidence_threshold": 99,
                },
            },
        ),
    ],
)
@pytest.mark.skip
async def test_extract_entities(
    text: str,
    entity_categories: EntityCategories,
    additional_context: str,
    expected_extracted_entities: dict[str, ExpectedClassification],
):
    print(f"\n--- {text}")

    results = await extract_entities(text, entity_categories, additional_context)

    for _, classified_entity in enumerate(results["classified_entities"]):
        classified_category = classified_entity["category"]
        expected_category = expected_extracted_entities[classified_category["value"]]

        assert (
            classified_category["confidence_percentage"]
            >= expected_category["confidence_threshold"]
        )

        classified_named_entity = classified_entity["named_entity"]

        found_named_entity = False
        for _, expected_named_entity in enumerate(expected_category["named_entity"]):
            if expected_named_entity["value"] != classified_named_entity["value"]:
                continue
            found_named_entity = True
            assert (
                classified_named_entity["confidence_percentage"]
                >= expected_named_entity["confidence_threshold"]
            )
            break
        assert found_named_entity == True
