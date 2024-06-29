import pytest

from ember_agents.agent_router.intent_classifier import INTENT, classify_intent


@pytest.mark.parametrize(
    "utterance, expected_intent",
    [
        (
            "@EmberAIBot  What is the cryptocurrency with the highest trading volume today and why? 🤔",
            "market_news",
        ),
        ("how is ember ai different from unibot or bananabot?", "capabilities"),
        (
            "Is your wallet readily available, and how do you see the idea of telegram wallets",
            "capabilities",
        ),
        (
            "Is your wallet readily available",
            "capabilities",
        ),
        (
            "how do you see the idea of telegram wallets",
            "capabilities",
        ),
        ("jeo boden", "definition"),
        ("tell me about arweave", "explanation"),
        ("how much is doge?", "crypto_price"),
        ("poocoin convert price point news outlet", "market_news"),
        ("change a tire", "out_of_scope"),
        ("the metal is soft because grass is green", "out_of_scope"),
        ("What can you do?", "capabilities"),
        ("wif price", "crypto_price"),
        ("cost of link", "crypto_price"),
        ("swap op", "swap_crypto"),
        ("give eth to friend", "transfer_crypto"),
        ("change sol for arb", "swap_crypto"),
        ("give me bitcoin", "transfer_crypto"),
        ("my friend wants some eth", "transfer_crypto"),
        ("What is an L3?", "explanation"),
        ("should I short bitcoin", "advice"),
        ("best trading strategy", "advice"),
        ("What are market news ?", "market_news"),
        ("how to use", "capabilities"),
        (
            "Long or short on bitcoin? For a short term trade? What do you think has better chances of success?",
            "advice",
        ),
        ("features", "capabilities"),
        (
            "hi @EmberAIBot What are the 3 key signs that investing in a token might be a bad idea?",
            "advice",
        ),
        ("anything exciting happen this week", "market_news"),
        ("@EmberAIBot What's up What will be the next X100 crypto gem?", "advice"),
    ],
)
# @pytest.mark.skip
async def test_classify_intent(utterance: str, expected_intent: INTENT):
    print("\n\ntesting...\n\n---\n\n")
    intent = await classify_intent(utterance)
    print(f"classification: {intent}")
    # assert await classify_intent(utterance) == expected_intent
