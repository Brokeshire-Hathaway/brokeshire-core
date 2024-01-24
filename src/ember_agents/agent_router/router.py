import os

from semantic_router import Route
from semantic_router.encoders import CohereEncoder
from semantic_router.layer import RouteLayer

print("COHERE_API_KEY")
print(os.getenv("COHERE_API_KEY"))
encoder = CohereEncoder(cohere_api_key=os.getenv("COHERE_API_KEY"))

send = Route(
    name="send",
    utterances=[
        "give 5 bitcoin to alice",
        "send token",
        "send sol to bob",
        "transfer crypto",
        "1.25 eth to 0xC7F97cCC3b899fd0372134570A7c5404f6F887F8",
        "48.06 bob to mike",
        "22 usdc to 0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
    ],
)

market = Route(
    name="market",
    utterances=[
        "what's the price of bitcoin?",
        "current ethereum price",
        "how much is doge?",
        "market cap of cardano",
        "solana volume",
    ],
)

internal = Route(
    name="internal",
    utterances=[
        "how does bitcoin work?",
        "what is a blockchain?",
        "explain a smart contract",
        "tell me about yourself",
        "good morning",
        "what is the difference between chainlink and uniswap",
        "technology comparison of optimism and arbitrum",
    ],
)

routes = [send, market, internal]

decision_layer = RouteLayer(encoder=encoder, routes=routes)


def router(intent: str) -> str:
    """Route a user intent to the appropriate agent team."""

    # TODO: Track sessions using a user id and thread id.
    #       (A thread represents a private chat, public group, or chat thread)

    # TODO: Each time an agent team ends their session with the user, they should return
    #       a summary of their conversation with the user so that it can be included in
    #       the top level conversation for context.

    route = decision_layer(intent).name
    if route is None:
        return "internal"
    else:
        return route
