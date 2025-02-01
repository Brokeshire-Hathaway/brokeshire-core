import pytest
from typing import Literal, TypedDict
from rich.console import Console

from brokeshire_agents.common.agents.entity_extractor import (
    ClassifiedEntities,
    extract_entities,
    flatten_classified_entities,
)
from brokeshire_agents.common.conversation import ContextMessage


console = Console()

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

test_cases = [
    pytest.param(
        "Convert USDT from the Linea network to receive 55 cookie on the Blast network.",
        swapEntityCategories,
        additionalContextSwap,
        [
            {
                "from_token": {"named_entity": "USDT", "confidence_level": "high"},
                "from_network": {"named_entity": "Linea", "confidence_level": "high"},
                "to_amount": {"named_entity": "55", "confidence_level": "high"},
                "to_token": {"named_entity": "cookie", "confidence_level": "normal"},
                "to_network": {"named_entity": "Blast", "confidence_level": "high"},
            },
            {
                "from_token": {"named_entity": "USDT", "confidence_level": "high"},
                "from_network": {"named_entity": "Linea", "confidence_level": "high"},
                "to_amount": {"named_entity": "55", "confidence_level": "high"},
                "to_token": {"named_entity": "cookie", "confidence_level": "high"},
                "to_network": {"named_entity": "Blast", "confidence_level": "high"},
            },
        ],
        id="convert_usdt_to_cookie_blast",
        # marks=pytest.mark.skip(reason="Temporarily disabled"),
    ),
    pytest.param(
        "Swap WBTC from Polygon network to receive 8.21 USDT on the Arbitrum network.",
        swapEntityCategories,
        additionalContextSwap,
        [
            {
                "from_token": {"named_entity": "WBTC", "confidence_level": "high"},
                "from_network": {"named_entity": "Polygon", "confidence_level": "high"},
                "to_amount": {"named_entity": "8.21", "confidence_level": "high"},
                "to_token": {"named_entity": "USDT", "confidence_level": "high"},
                "to_network": {"named_entity": "Arbitrum", "confidence_level": "high"},
            },
        ],
        id="swap_wbtc_to_usdt_arbitrum",
        # marks=pytest.mark.skip(reason="Temporarily disabled"),
    ),
    pytest.param(
        "swap op",
        swapEntityCategories,
        additionalContextSwap,
        [
            {},
            {
                "to_token": {
                    "named_entity": "op",
                    "confidence_level": "low",
                }
            },
            {
                "from_token": {
                    "named_entity": "op",
                    "confidence_level": "low",
                }
            },
        ],
        id="swap_op_simple",
        # marks=pytest.mark.skip(reason="Temporarily disabled"),
    ),
    pytest.param(
        "Swap 5 USDC for ETH from the Arbitrum network to the Base network",
        swapEntityCategories,
        additionalContextSwap,
        [
            {
                "from_amount": {"named_entity": "5", "confidence_level": "high"},
                "from_token": {"named_entity": "USDC", "confidence_level": "high"},
                "from_network": {
                    "named_entity": "Arbitrum",
                    "confidence_level": "high",
                },
                "to_token": {"named_entity": "ETH", "confidence_level": "high"},
                "to_network": {"named_entity": "Base", "confidence_level": "high"},
            }
        ],
        id="swap_usdc_to_eth_arb_base",
        # marks=pytest.mark.skip(reason="Temporarily disabled"),
    ),
    pytest.param(
        "I want cookies",
        swapEntityCategories,
        additionalContextSwap,
        [
            {
                "to_token": {"named_entity": "cookies", "confidence_level": "low"},
            },
            {
                "from_token": {"named_entity": "cookies", "confidence_level": "low"},
            },
            {
                "from_token": {"named_entity": "cookies", "confidence_level": "normal"},
            },
        ],
        id="want_cookies_simple",
        # marks=pytest.mark.skip(reason="Temporarily disabled")
    ),
    pytest.param(
        "I want puppy",
        swapEntityCategories,
        additionalContextSwap,
        [
            {
                "to_token": {"named_entity": "puppy", "confidence_level": "low"},
            },
            {
                "to_token": {"named_entity": "puppy", "confidence_level": "high"},
            },
            {
                "from_token": {"named_entity": "puppy", "confidence_level": "low"},
            },
            {
                "to_token": {
                    "named_entity": "puppy",
                    "confidence_level": "normal",
                }
            },
        ],
        id="want_puppy_simple",
        # marks=pytest.mark.skip(reason="Temporarily disabled"),
    ),
    pytest.param(
        "Buy cookies",
        swapEntityCategories,
        additionalContextSwap,
        [
            {
                "to_token": {"named_entity": "cookies", "confidence_level": "low"},
                "to_token": {"named_entity": "cookies", "confidence_level": "high"},
            }
        ],
        id="buy_cookies_simple",
        # marks=pytest.mark.skip(reason="Temporarily disabled"),
    ),
    pytest.param(
        "bitcoin",
        swapEntityCategories,
        additionalContextSwap,
        [
            {
                "from_token": {"named_entity": "bitcoin", "confidence_level": "high"},
            },
            {
                "from_token": {"named_entity": "bitcoin", "confidence_level": "normal"},
            },
            {
                "from_token": {
                    "named_entity": "bitcoin",
                    "confidence_level": "low",
                }
            },
        ],
        id="bitcoin_single_token",
        # marks=pytest.mark.skip(reason="Temporarily disabled"),
    ),
    pytest.param(
        "swap 5 usdc for eth",
        swapEntityCategories,
        additionalContextSwap,
        [
            {
                "from_amount": {"named_entity": "5", "confidence_level": "high"},
                "from_token": {"named_entity": "usdc", "confidence_level": "high"},
                "to_token": {"named_entity": "eth", "confidence_level": "high"},
            },
        ],
        id="swap_usdc_to_eth_simple",
        # marks=pytest.mark.skip(reason="Temporarily disabled"),
    ),
    pytest.param(
        "buy render",
        swapEntityCategories,
        additionalContextSwap,
        [
            {
                "to_token": {"named_entity": "render", "confidence_level": "high"},
            },
        ],
        id="buy_render_simple",
        # marks=pytest.mark.skip(reason="Temporarily disabled"),
    ),
    pytest.param(
        "give me bitcoin",
        swapEntityCategories,
        additionalContextSwap,
        [
            {
                "to_token": {"named_entity": "bitcoin", "confidence_level": "high"},
            },
        ],
        id="give_bitcoin_simple",
        # marks=pytest.mark.skip(reason="Temporarily disabled"),
    ),
    pytest.param(
        "give eth to friend",
        sendEntityCategories,
        sendEntityCategories,
        [
            {
                "token": {"named_entity": "eth", "confidence_level": "high"},
                "recipient": {"named_entity": "friend", "confidence_level": "high"},
            },
            {
                "token": {"named_entity": "eth", "confidence_level": "high"},
                "recipient": {"named_entity": "friend", "confidence_level": "normal"},
            },
        ],
        id="send_eth_to_friend",
        # marks=pytest.mark.skip(reason="Temporarily disabled"),
    ),
    pytest.param(
        "change sol for arb",
        swapEntityCategories,
        additionalContextSwap,
        [
            {
                "from_token": {"named_entity": "sol", "confidence_level": "high"},
                "to_token": {"named_entity": "arb", "confidence_level": "high"},
            },
            {
                "from_token": {"named_entity": "sol", "confidence_level": "normal"},
                "to_token": {"named_entity": "arb", "confidence_level": "normal"},
            },
        ],
        id="swap_sol_to_arb",
        # marks=pytest.mark.skip(reason="Temporarily disabled")
    ),
    pytest.param(
        "my friend wants some eth",
        sendEntityCategories,
        sendEntityCategories,
        [
            {
                "amount": None,
                "token": {"named_entity": "eth", "confidence_level": "high"},
                "network": None,
                "recipient": {"named_entity": "my friend", "confidence_level": "high"},
            },
            {
                "recipient": {
                    "named_entity": "my friend",
                    "confidence_level": "normal",
                },
                "token": {"named_entity": "eth", "confidence_level": "high"},
            },
            {
                "token": {"named_entity": "eth", "confidence_level": "high"},
                "amount": {"named_entity": "some", "confidence_level": "low"},
            },
        ],
        id="friend_wants_eth",
        # marks=pytest.mark.skip(reason="Temporarily disabled"),
    ),
]


@pytest.mark.parametrize(
    "text, entity_categories, additional_context, expected", test_cases
)
@pytest.mark.skip
async def test_extract_entities(
    text: str,
    entity_categories: EntityCategories,
    additional_context: str,
    expected: list[ClassifiedEntities],
):
    print(f"\n--- {text}")

    message_history: list[ContextMessage] = [
        {
            "role": "user",
            "content": f"<sender_name>user</sender_name>\n<message>{text}</message>",
        }
    ]
    (results, reasoning) = await extract_entities(
        text, entity_categories, additional_context, message_history
    )

    console.print(f"[purple] reasoning: {reasoning} [/purple]")

    classified_entities = flatten_classified_entities(results)

    assert any(
        classified_entities == expected_classified_entities
        for expected_classified_entities in expected
    ), (
        f"[{text}] No match found between classified_entities and any expected_classified_entities\n\n"
        f"classified_entities: {classified_entities}\nexpected: {expected}"
    )
