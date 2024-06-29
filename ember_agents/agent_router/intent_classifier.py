import sys
from math import exp
from pprint import pprint
from typing import Literal

import numpy as np
from fireworks.client import Fireworks
from pydantic import BaseModel

from ember_agents.settings import SETTINGS

INTENT = Literal[
    "capabilities_query",
    "crypto_price_query",
    "swap_crypto_action",
    "transfer_crypto_action",
    "explanation_query",
    "advice_query",
    "market_news_query",
    "unclear",
    "out_of_scope",
]

descriptions: dict[INTENT, str] = {
    "capabilities_query": "Reply to any questions about me. Help the user understand what this assistant can do, it's features and functionalies, and how to use it. Its name is Ember.",
    "crypto_price_query": "Get the price of a cryptocurrency or token",
    "swap_crypto_action": "Convert one cryptocurrency or token to another",
    "transfer_crypto_action": "Send cryptocurrency or tokens to someone else",
    "explanation_query": "Describe a concept or term",
    "advice_query": "Provide guidance on a decision",
    "market_news_query": "Get the latest news on the crypto market",
    "unclear": "User message is gibberish, ambiguous or unclear",
    "out_of_scope": "Does not fit any of the other intents",
}


class ClassifiedIntent(BaseModel):
    intent: INTENT
    linear_probability: float


client = Fireworks(api_key=SETTINGS.fireworks_api_key)

# possible_intents = "\n".join(f'"{i}: {item}"' for i, item in enumerate(INTENT.__args__))

intent_strings = [f"{key} ({value})" for key, value in descriptions.items()]

possible_intents = "\n".join(intent_strings)

intent_grammar = f"""
root ::= intent
intent ::= "{'" | "'.join(INTENT.__args__)}"
"""

"""
root ::= intent
intent ::= {' | '.join(f'"{i}"' for i in range(len(INTENT.__args__)))}
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

    print(f"utterance: {utterance}")
    # print(f"possible_intents: {possible_intents}")
    # print(f"intent_grammar: {intent_grammar}")

    # sys.exit()

    prompt = get_prompt(utterance)
    # print(prompt)

    # number_of_intents = len(INTENT.__args__)
    response = client.completion.create(
        model="accounts/fireworks/models/llama-v3-70b-instruct",
        response_format={"type": "grammar", "grammar": intent_grammar},
        prompt=prompt,
        temperature=0,
        logprobs=True,
        top_logprobs=3,
    )

    # print(response.choices[0].logprobs.content[0].top_logprobs)

    """for content in response.choices[0].logprobs.content:
        # print("Content:", content)
        for token in content.top_logprobs:
            print("Token:", token.token)
            # print("Log prob:", token.logprob)
            print("Linear prob:", np.round(exp(token.logprob) * 100, 2), "%")
        break"""

    intent = response.choices[0].text

    # index = int(response.choices[0].text)
    # intent = INTENT.__args__[index]
    token_logprob = response.choices[0].logprobs.content[0].top_logprobs[0]
    linear_probability = exp(token_logprob.logprob)

    """for content in response.choices[0].logprobs.content:
        pprint(content.top_logprobs)"""
    return ClassifiedIntent(intent=intent, linear_probability=linear_probability)
