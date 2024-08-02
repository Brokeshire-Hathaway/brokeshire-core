from unicodedata import category
import pytest
from pprint import pprint
from typing import Any, Literal

from ember_agents.common.agents.entity_extractor import (
    extract_entities,
    ClassifiedEntity,
)
from ember_agents.common.ai_inference.openai import add_confidence_to_json_values

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


"""

"""

"""

"""

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
                "from_amount": [{"value": "5", "confidence_threshold": 99}],
                "from_token": [{"value": "usdc", "confidence_threshold": 99}],
                "from_network": [],
                "to_amount": [],
                "to_token": [{"value": "eth", "confidence_threshold": 99}],
                "to_network": [],
            },
        ),
        (
            "swap op",
            swapEntityCategories,
            additionalContextSwap,
            {
                "from_amount": [],
                "from_token": [{"value": "op", "confidence_threshold": 90}],
                "from_network": [],
                "to_amount": [],
                "to_token": [{"value": "op", "confidence_threshold": 90}],
                "to_network": [],
            },
        ),
        (
            "I want puppy",
            swapEntityCategories,
            additionalContextSwap,
            {
                "from_amount": [],
                "from_token": [],
                "from_network": [],
                "to_amount": [],
                "to_token": [{"value": "puppy", "confidence_threshold": 40}],
                "to_network": [],
            },
        ),
        (
            "Buy cookies",
            swapEntityCategories,
            additionalContextSwap,
            {
                "from_amount": [],
                "from_token": [],
                "from_network": [],
                "to_amount": [],
                "to_token": [{"value": "cookies", "confidence_threshold": 85}],
                "to_network": [],
            },
        ),
        (
            "buy render",
            swapEntityCategories,
            additionalContextSwap,
            {
                "from_amount": [],
                "from_token": [],
                "from_network": [],
                "to_amount": [],
                "to_token": [{"value": "render", "confidence_threshold": 99}],
                "to_network": [],
            },
        ),
        (
            "give me bitcoin",
            swapEntityCategories,
            additionalContextSwap,
            {
                "from_amount": [],
                "from_token": [],
                "from_network": [],
                "to_amount": [],
                "to_token": [{"value": "bitcoin", "confidence_threshold": 65}],
                "to_network": [],
            },
        ),
        (
            "bitcoin",
            swapEntityCategories,
            additionalContextSwap,
            {
                "from_amount": [],
                "from_token": [{"value": "bitcoin", "confidence_threshold": 99}],
                "from_network": [],
                "to_amount": [],
                "to_token": [],
                "to_network": [],
            },
        ),
        (
            "I want cookies",
            swapEntityCategories,
            additionalContextSwap,
            {
                "from_amount": [],
                "from_token": [],
                "from_network": [],
                "to_amount": [],
                "to_token": [{"value": "cookies", "confidence_threshold": 90}],
                "to_network": [],
            },
        ),
        (
            "give eth to friend",
            sendEntityCategories,
            sendEntityCategories,
            {
                "amount": [],
                "token": [{"value": "eth", "confidence_threshold": 99}],
                "network": [],
                "recipient": [{"value": "friend", "confidence_threshold": 99}],
            },
        ),
        (
            "change sol for arb",
            swapEntityCategories,
            additionalContextSwap,
            {
                "from_amount": [],
                "from_token": [{"value": "sol", "confidence_threshold": 99}],
                "from_network": [],
                "to_amount": [],
                "to_token": [{"value": "arb", "confidence_threshold": 99}],
                "to_network": [],
            },
        ),
        (
            "my friend wants some eth",
            sendEntityCategories,
            sendEntityCategories,
            {
                "amount": [],
                "token": [{"value": "eth", "confidence_threshold": 99}],
                "network": [],
                "recipient": [{"value": "my friend", "confidence_threshold": 99}],
            },
        ),
    ],
)
@pytest.mark.skip
async def test_extract_entities(
    text: str,
    entity_categories: EntityCategories,
    additional_context: str,
    expected_extracted_entities: dict[
        str, list[dict[Literal["value", "confidence_threshold"], Any]]
    ],
):
    print(f"\n--- {text}")

    results = await extract_entities(text, entity_categories, additional_context)

    print("EXPECTED_EXTRACTED_ENTITIES:")
    pprint(expected_extracted_entities)
    print("RESULTS:")
    pprint(results)

    for _, classified_entity in enumerate(results["classified_entities"]):
        category = classified_entity["category"]
        named_entity = classified_entity["named_entity"]
        found_named_entity = False
        for _, expected_entity in enumerate(
            expected_extracted_entities[category["value"]]
        ):
            if expected_entity["value"] != named_entity["value"]:
                continue
            found_named_entity = True
            assert (
                category["confidence_percentage"]
                >= expected_entity["confidence_threshold"]
            )
            break
        assert found_named_entity == True

    """for entity_category, expected_entities in expected_extracted_entities.items():
        assert len(expected_entities) == len(results[entity_category])

        for i, expected_entity in enumerate(expected_entities):
            named_entity = results[entity_category][i]["named_entity"]
            assert named_entity["value"] == expected_entity["value"]
            assert (
                named_entity["confidence_percentage"]
                >= expected_entity["confidence_threshold"]
            )"""
