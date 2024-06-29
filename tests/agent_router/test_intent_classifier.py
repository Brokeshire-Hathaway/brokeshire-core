import pytest

from ember_agents.agent_router.intent_classifier import INTENT, classify_intent


@pytest.mark.parametrize(
    "utterance, expected_intent, expected_is_confident",
    [
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
            False,
        ),
        (
            "jeo boden",
            "unclear",
            True,
        ),
        ("tell me about arweave", "explanation_query", True),
        ("how much is doge?", "crypto_price_query", True),
        ("poocoin convert price point news outlet", "unclear", True),
        ("change a tire", "out_of_scope", True),
        ("the metal is soft because grass is green", "unclear", True),
        ("What can you do?", "capabilities_query", True),
        ("wif price", "crypto_price_query", True),
        ("cost of link", "crypto_price_query", True),
        ("swap op", "swap_crypto_action", True),
        ("give eth to friend", "transfer_crypto_action", True),
        ("change sol for arb", "swap_crypto_action", True),
        ("give me bitcoin", "crypto_price_query", True),
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
# @pytest.mark.skip
async def test_classify_intent(
    utterance: str, expected_intent: INTENT, expected_is_confident: bool
):
    classified_intent = await classify_intent(utterance)
    assert classified_intent.intent == expected_intent
    assert (classified_intent.linear_probability >= 0.8) is expected_is_confident
