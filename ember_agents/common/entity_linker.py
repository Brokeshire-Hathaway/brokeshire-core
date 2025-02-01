import json
from math import exp, log
from typing import Any, TypedDict

from openai.types.chat import ChatCompletionMessageParam
from rapidfuzz import fuzz, process, utils

from brokeshire_agents.common.ai_inference.openai import (
    Temperature,
    get_openai_response,
)

LOGPROBS_REQUIRED_ERROR = "Logprobs are required but were not provided."


class EntityMatch(TypedDict):
    entity: dict[str, Any]
    confidence_percentage: float


class LinkedEntityResults(TypedDict):
    named_entity: str
    fuzzy_matches: list[EntityMatch] | None
    llm_matches: list[EntityMatch] | None


def log_weighted_average(values):
    if not values:
        return 0
    weights = [exp(log(x)) if x > 0 else 0 for x in values]
    weighted_sum = sum(w * v for w, v in zip(weights, values, strict=False))
    sum_of_weights = sum(weights)
    return weighted_sum / sum_of_weights if sum_of_weights > 0 else 0


def fuzzy_entity_match(
    named_entity: str,
    entity_list: list[dict[str, Any]],
    keys_to_match: list[str],
    score_cutoff: float = 0.7,
    limit: int = 5,
) -> list[EntityMatch]:
    if len(keys_to_match) == 0:
        message = "At least one key must be provided to match entities."
        raise ValueError(message)

    # Create dictionaries of values for each key
    key_values = {
        key: {i: str(entity.get(key, "")) for i, entity in enumerate(entity_list)}
        for key in keys_to_match
    }

    # Calculate scores for each key using process.extract
    key_scores = {}
    for key, values in key_values.items():
        matches = process.extract(
            named_entity,
            values,
            scorer=fuzz.WRatio,
            processor=utils.default_process,
            limit=None,
        )
        key_scores[key] = {
            i: score if score > 0 else score + 1 for (_, score, i) in matches
        }

    # Calculate log weighted average scores
    avg_scores = {}
    for i in range(len(entity_list)):
        scores = [key_scores[key].get(i, 0) for key in keys_to_match]
        avg_scores[i] = log_weighted_average(scores)

    # Sort by average score, apply score cutoff, and then apply limit
    top_matches = sorted(
        [(i, score) for i, score in avg_scores.items() if score >= score_cutoff],
        key=lambda x: x[1],
        reverse=True,
    )[:limit]

    return [
        EntityMatch(entity=entity_list[i], confidence_percentage=score)
        for i, score in top_matches
    ]


# Use this if lower confidence is needed:
# "Select one of the unique entities that matches the named entity with low confidence."
#
# Otherwise use this in the following sentence:
# "If there isn't a clear match, show low confidence."
def get_system_prompt(unique_entities: dict[int, dict[str, Any]]):
    return f"""You are a natural language processing expert that links a named entity to a unique entity. Select one of the unique entities that best matches the named entity. If there isn't a clear match, show lower confidence. You must generate a response following the JSON schema below.

# JSON schema
{{
    "type": "object",
    "properties": {{
        "linked_entity_index": {{"type": "string"}},
    }},
    "required": ["linked_entity_index"]
}}

# Unique entities
{json.dumps(unique_entities, indent=2)}"""


def safe_int(s: str) -> int | None:
    try:
        return int(s)
    except ValueError:
        return None


async def llm_entity_match(
    named_entity: str,
    entity_list: list[dict[str, Any]],
    keys_to_match: list[str],
) -> list[EntityMatch]:
    if len(keys_to_match) == 0:
        message = "At least one key must be provided to match entities."
        raise ValueError(message)

    filtered_entity_keys = [
        {key: d[key] for key in keys_to_match if key in d} for d in entity_list
    ]
    indexed_entities = dict(enumerate(filtered_entity_keys))
    system_prompt = get_system_prompt(indexed_entities)
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Named entity: {named_entity}"},
    ]
    response = await get_openai_response(
        messages,
        "gpt-4o-2024-05-13",
        Temperature(value=0),
        response_format={"type": "json_object"},
        seed=42,
        logprobs=True,
        top_logprobs=3,
    )

    llm_match_token_index = 8
    choice = response.choices[0] if len(response.choices) >= 1 else None
    if choice is None or choice.logprobs is None or choice.logprobs.content is None:
        raise ValueError(LOGPROBS_REQUIRED_ERROR)

    llm_match_logprob = choice.logprobs.content[llm_match_token_index]
    return [
        EntityMatch(
            entity=entity_list[index],
            confidence_percentage=round(exp(top_logprob.logprob) * 100, 2),
        )
        for top_logprob in llm_match_logprob.top_logprobs
        if (index := safe_int(top_logprob.token)) is not None
        and 0 <= index < len(entity_list)
    ]


async def link_entity(
    named_entity: str,
    unique_entities: list[dict],
    fuzzy_keys: list[str] | None = None,
    llm_keys: list[str] | None = None,
) -> LinkedEntityResults:
    """
    Link a named entity to a unique entity from a list of unique entities
    """

    fuzzy_matches = (
        None
        if fuzzy_keys is None
        else fuzzy_entity_match(named_entity, unique_entities, fuzzy_keys)
    )
    llm_matches = None
    if llm_keys is not None:
        llm_entity_list = (
            [le["entity"] for le in fuzzy_matches] if fuzzy_matches else unique_entities
        )
        llm_matches = await llm_entity_match(named_entity, llm_entity_list, llm_keys)
    return LinkedEntityResults(
        named_entity=named_entity, fuzzy_matches=fuzzy_matches, llm_matches=llm_matches
    )
