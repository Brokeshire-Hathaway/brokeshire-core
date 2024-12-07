from math import exp
from typing import Literal

from fireworks.client import Fireworks
from pydantic import BaseModel

from ember_agents.settings import SETTINGS

INTENT = Literal[
    "capabilities_query",
    "crypto_price_query",
    "convert_crypto_action",
    "transfer_crypto_action",
    "earn_crypto_action",
    "explanation_query",
    "advice_query",
    "market_news_query",
    "token_analysis_query",
    "terminate",
    "unclear",
    "out_of_scope",
]


class ClassifiedIntent(BaseModel):
    name: INTENT
    linear_probability: float


client = Fireworks(api_key=SETTINGS.fireworks_api_key)


descriptions: dict[INTENT, str] = {
    "capabilities_query": "Reply to any questions about me. Help the user understand what this assistant can do, it's features and functionalies, and how to use it. Its name is Brokeshire.",
    "crypto_price_query": "Get the price of a cryptocurrency or token",
    "convert_crypto_action": "Convert one cryptocurrency or token to another. Buy cryptocurrency, token or noun. This includes 'buy <noun>'. User can use any noun for this intent.",
    "transfer_crypto_action": "Send cryptocurrency or tokens to someone else. Someone else requests a cryptocurrency or token.",
    "earn_crypto_action": "Earn yield on your cryptocurrency or token by depositing it in a yield-generating strategy.",
    "explanation_query": "Describe a concept or term",
    "advice_query": "Provide general guidance on a decision not related to specific tokens or assets",
    "market_news_query": "Get the latest news on the crypto market",
    "token_analysis_query": "Provide an opinion, technical analysis or prediction on a token's performance. You either assess the specified token, or return a hidden gem if no token is specified.",
    "terminate": "End the current intent conversation",
    "unclear": "User message is gibberish, ambiguous or unclear",
    "out_of_scope": "Does not fit any of the other intents",
}

intent_strings = [f"{key} ({value})" for key, value in descriptions.items()]
possible_intents = "\n".join(intent_strings)
intent_grammar = f"""
root ::= intent
intent ::= "{'" | "'.join(INTENT.__args__)}"
"""
SYSTEM_PROMPT = f"""You are a natural language understanding expert that classifies a user utterance into an intent. Select one of following possible intents. Your response must be a single name.

# Possible Intents
{possible_intents}"""


def get_prompt(utterance: str) -> str:
    return f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

{SYSTEM_PROMPT}<|eot_id|><|start_header_id|>user<|end_header_id|>

Utterance: {utterance}<|eot_id|><|start_header_id|>assistant<|end_header_id|>

"""


async def classify_intent(utterance: str) -> ClassifiedIntent:
    """
    Classify the intent of an utterance
    """

    prompt = get_prompt(utterance)
    response = client.completion.create(
        model="accounts/fireworks/models/llama-v3-70b-instruct",
        response_format={"type": "grammar", "grammar": intent_grammar},
        prompt=prompt,
        temperature=0,
        logprobs=True,
        top_logprobs=3,
    )
    intent = response.choices[0].text
    token_logprob = response.choices[0].logprobs.content[0].top_logprobs[0]
    linear_probability = exp(token_logprob.logprob)

    return ClassifiedIntent(name=intent, linear_probability=linear_probability)
