from operator import is_
import pytest

from ember_agents.agent_router.intent_classifier import INTENT, classify_intent


@pytest.mark.parametrize(
    "utterance, expected_intent, expected_is_confident",
    [
        ("I want cookies", "swap_crypto_action", True),
        ("Buy cookies", "swap_crypto_action", True),
        ("I want puppy", "swap_crypto_action", True),
        ("buy render", "swap_crypto_action", True),
        ("change a tire", "out_of_scope", True),
        (
            "@EmberAIBot  What is the cryptocurrency with the highest trading volume today and why? 🤔",
            "market_news_query",
            True,
        ),
        (
            "how is ember ai different from unibot or bananabot?",
            "capabilities_query",
            True,
        ),
        (
            "Is your wallet readily available, and how do you see the idea of telegram wallets",
            "capabilities_query",
            True,
        ),
        (
            "Is your wallet readily available",
            "capabilities_query",
            True,
        ),
        (
            "how do you see the idea of telegram wallets",
            "explanation_query",
            True,
        ),
        (
            "jeo boden",
            "unclear",
            True,
        ),
        ("tell me about arweave", "explanation_query", True),
        ("how much is doge?", "crypto_price_query", True),
        ("poocoin convert price point news outlet", "unclear", False),
        ("the metal is soft because grass is green", "unclear", True),
        ("What can you do?", "capabilities_query", True),
        ("wif price", "crypto_price_query", True),
        ("cost of link", "crypto_price_query", True),
        ("swap op", "swap_crypto_action", True),
        ("give eth to friend", "transfer_crypto_action", True),
        ("change sol for arb", "swap_crypto_action", True),
        ("give me bitcoin", "swap_crypto_action", True),
        ("my friend wants some eth", "transfer_crypto_action", True),
        ("What is an L3?", "explanation_query", True),
        ("should I short bitcoin", "advice_query", True),
        ("best trading strategy", "advice_query", True),
        ("What are market news ?", "market_news_query", True),
        ("how to use", "capabilities_query", True),
        (
            "Long or short on bitcoin? For a short term trade? What do you think has better chances of success?",
            "advice_query",
            True,
        ),
        ("features", "capabilities_query", True),
        (
            "hi @EmberAIBot What are the 3 key signs that investing in a token might be a bad idea?",
            "advice_query",
            True,
        ),
        ("anything exciting happen this week", "market_news_query", True),
        (
            "@EmberAIBot What's up What will be the next X100 crypto gem?",
            "advice_query",
            True,
        ),
    ],
)
@pytest.mark.skip
async def test_classify_intent(
    utterance: str, expected_intent: INTENT, expected_is_confident: bool
):
    classified_intent = await classify_intent(utterance)

    print(f"\n\n---\n\nUtterance: {utterance}")
    print(f"Classified Intent: {classified_intent.name}")
    print(f"Confidence: {classified_intent.linear_probability}")

    is_confident = classified_intent.linear_probability >= 0.8

    assert is_confident is expected_is_confident

    if is_confident:
        assert classified_intent.name == expected_intent
