import json
from pprint import pprint
from typing import Generic, Sequence, TypedDict, TypeVar

from openai.types.chat import (
    ChatCompletionMessageParam,
)
from pydantic import BaseModel

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


ExtractedEntities = dict[str, list[ClassifiedEntity]]

SYSTEM_PROMPT = """You are a Na
med-entity recognition (NER) processor. Your task is to identify entities from a given utterance and classify them according to the provided JSON schema."""


"""
Carefully read through the user utterance and identify any words or phrases that correspond to the entity categories defined in the JSON schema.

5. If no entities of a particular type are found in the utterance, include that type in the JSON output with an empty array as its value.

4. Explain the reasoning for why you chose each entity type and why you didn't choose another type.

{{
  "vacation_requester": [
    {{
      "named_entity": "John Doe",
    }}
  ],
  "employer": [
    {{
      "named_entity": "Acme Corp",
    }}
  ],
  "location": []
}}

Here are the categories to use for classification:
<categories>
{json.dumps(categories, indent=2)}
</categories>

properties = {
        key: {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"named_entity": {"type": "string"}},
                "required": ["named_entity"],
            },
        }
        for key in categories
    }
    schema = {"type": "object", "properties": properties, "required": categories}

properties = {
        key: {
            "type": "string",
        }
        for key in categories
    }
    # print("PROPERTIES")
    # pprint(properties)
    schema = {"type": "object", "properties": properties, "required": categories}
    # print("SCHEMA")
    # print(json.dumps(schema, indent=2))


2. Include any words or phrases that might be entities related to the categories, even if they're not clear, but show low confidence.

3. Remember to include all entities, but respond with low confidence for unclear entities.

    example_output = {
        "identified_entities": [
            "John Doe",
            "Acme Corp",
            "space ship",
        ],
        "classified_entities": [
            {
                "category": "pto_requester",
                "named_entity": "John Doe",
            },
            {
                "category": "employer",
                "named_entity": "Acme Corp",
            },
        ],
    }

Here's an example of how your output should be structured (adjust according to the actual schema provided):
<example_json_output>
{json.dumps(example_output, indent=2)}
</example_json_output>
"""


def get_instructions_prompt(
    utterance: str, categories: Sequence[str], additional_context: str | None
):
    schema = {
        "properties": {
            "identified_entities": {
                "type": "array",
                "items": {"type": "string"},
            },
            "classified_entities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "named_entity": {"type": "string"},
                    },
                    "required": ["category", "named_entity"],
                },
            },
        },
        "required": ["identified_entities", "classified_entities"],
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
1. Carefully read through the utterance and identify any words or phrases that represent entities. Pay attention to context and potential variations in how entities might be expressed.

2. For any word or phrase that is not clearly an identified entity, show low confidence.

3. For each identified entity:
    a. Determine the appropriate category from categories.
    b. For any category classification that is not clear, show low confidence.
    c. Extract the exact text of the entity from the utterance.

4. Construct a JSON object that follows the structure of the provided schema, populating it with all of the entities you've extracted. Ensure that your output is valid JSON and matches the schema structure exactly.
</instructions>

Now, analyze the utterance and provide your output as instructed."""


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

    # print("RESPONSE")
    # pprint(response.choices[0].message.content)

    logprobs = response.choices[0].logprobs

    if logprobs is None or logprobs.content is None:
        msg = "No logprobs found in response"
        raise ValueError(msg)

    json_with_confidence = add_confidence_to_json_values(logprobs.content)

    return json_with_confidence
