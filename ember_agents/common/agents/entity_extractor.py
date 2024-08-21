import json
from typing import Sequence, TypedDict, TypeVar

from openai.types.chat import (
    ChatCompletionMessageParam,
)

from ember_agents.common.ai_inference.openai import (
    Temperature,
    add_confidence_to_json_values,
    get_openai_response,
)

T = TypeVar("T", bound=str)


class ValueWithConfidence(TypedDict):
    value: str
    confidence_percentage: float


class ClassifiedEntity(TypedDict):
    named_entity: ValueWithConfidence
    category: ValueWithConfidence


class ExtractedEntities(TypedDict):
    classified_entities: list[ClassifiedEntity]


SYSTEM_PROMPT = """You are a Named-entity recognition (NER) processor. Your task is to identify entities from a given utterance and classify them according to the provided JSON schema."""


"""

"""


def get_instructions_prompt(
    utterance: str, categories: Sequence[str], additional_context: str | None
):
    schema = {
        "properties": {
            "classified_entities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "named_entity": {"type": "string"},
                    },
                    "required": [
                        "category",
                        "named_entity",
                    ],
                },
            },
        },
        "required": ["classified_entities"],
    }

    return f"""Here is the utterance to analyze:
<utterance>
{utterance}
</utterance>

Here is some additional context that may help you identify and classify potential entities in the utterance:
<additional_context>
{additional_context}
</additional_context>

Here are the categories to use for classification:
<categories>
{json.dumps(categories, indent=2)}
</categories>

Here is the JSON schema to use for your output:
<json_schema>
{json.dumps(schema, indent=2)}
</json_schema>

<instructions>
1. Carefully read through the utterance and identify any words or phrases that represent entities associated with the categories. Pay attention to context and potential variations in how entities might be expressed.

2. For any word or phrase that is not clearly an identified entity, show less confidence.

3. For each identified entity:
    a. Determine any potential match from categories in no particular order
    b. Extract the exact text of the entity from the utterance
    c. When presented with a phrase, identify and focus only on the first element.
        - Ignore any subsequent elements in your named entity response unless they are necessary to fully identify the entity.
        - When dealing with number + unit expressions, treat the number as the focus, even if it doesn't make semantic sense on its own.
    d. If the category classification is not clear, show less confidence

4. Construct a JSON object that follows the structure of the provided schema, populating it with all of the entities you've extracted. Ensure that your output is valid JSON and matches the schema structure exactly.
</instructions>

Now, analyze the utterance and provide your output as instructed."""


# If there is no match, do not include the entity in the output.
async def extract_entities(
    text: str, categories: Sequence[str], additional_context: str
) -> ExtractedEntities:
    instructions_prompt = get_instructions_prompt(text, categories, additional_context)
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": instructions_prompt},
    ]
    response = await get_openai_response(
        messages,
        "gpt-4o-2024-05-13",
        Temperature(value=0),
        response_format={"type": "json_object"},
        seed=42,
        logprobs=True,
    )

    logprobs = response.choices[0].logprobs

    if logprobs is None or logprobs.content is None:
        msg = "No logprobs found in response"
        raise ValueError(msg)

    json_with_confidence = add_confidence_to_json_values(logprobs.content)

    return json_with_confidence
