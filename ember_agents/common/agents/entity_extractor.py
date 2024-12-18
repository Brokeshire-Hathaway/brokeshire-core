import json
from collections.abc import Sequence
from typing import Literal, TypedDict, TypeVar, get_args

from pydantic import BaseModel
from rich.console import Console

from ember_agents.common.ai_inference import openrouter
from ember_agents.common.ai_inference.parse_response import extract_xml_content
from ember_agents.common.conversation import ContextMessage

console = Console()

T = TypeVar("T", bound=str)

C = TypeVar("C", bound=str)


ConfidenceLevel = Literal["high", "normal", "low"]


"""class ClassifiedEntity(BaseModel):
    named_entity: str
    confidence: confidence_level


class ExtractedEntities(BaseModel, Generic[T]):
    classified_entities: dict[T, list[ClassifiedEntity]]"""


class ExtractedEntity(BaseModel):
    category: str
    named_entity: str
    confidence_level: ConfidenceLevel


class ExtractedEntities(BaseModel):
    extracted_entities: list[ExtractedEntity]


class ClassifiedEntity(TypedDict):
    named_entity: str
    confidence_level: ConfidenceLevel


ClassifiedEntities = dict[str, ClassifiedEntity]


Reasoning = str


def flatten_classified_entities(
    data: ExtractedEntities,
) -> ClassifiedEntities:
    return {
        classified_entity.category: {
            "named_entity": classified_entity.named_entity,
            "confidence_level": classified_entity.confidence_level,
        }
        for classified_entity in data.extracted_entities
    }


SYSTEM_PROMPT = """You are an Named-entity recognition (NER) processor tasked with identifying and classifying entities in a given utterance according to the provided JSON schema."""


"""
{
    "properties": {
        "extracted_entities": {
            "type": "object",
            "properties": {
                category: {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "named_entity": {"type": "string"},
                            "confidence_level": {
                                "type": "string",
                                "enum": list(get_args(confidence_level)),
                            },
                        },
                        "required": ["named_entity", "confidence_level"],
                    },
                }
                for category in categories
            },
            "required": categories,
        },
    },
    "required": ["extracted_entities"],
}
"""


def get_instructions_prompt(
    utterance: str, categories: Sequence[str], additional_context: str | None
):
    schema = {
        "properties": {
            "extracted_entities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "named_entity": {"type": "string"},
                        "confidence_level": {
                            "type": "string",
                            "enum": list(get_args(ConfidenceLevel)),
                        },
                    },
                    "required": [
                        "category",
                        "named_entity",
                        "confidence_level",
                    ],
                },
            },
        },
        "required": ["extracted_entities"],
    }

    # TODO: Make entity descriptions dynamic

    return f"""Follow these instructions carefully to complete the task:

1. Here is the utterance you need to analyze:
<utterance>
{utterance}
</utterance>

2. Here is some additional context that should help you identify and classify entities in the utterance:
<additional_context>
{additional_context}
</additional_context>

3. Use the following categories for classification:
<categories>
{json.dumps(categories, indent=2)}
</categories>

4. Your output should follow this JSON schema:
<json_schema>
{json.dumps(schema, indent=2)}
</json_schema>

5. Follow these steps to identify and classify entities:
   a. Assume that the utterance is related to any additional context provided and understand how they are related.
   b. Carefully read through the utterance and identify any words or phrases that represent entities associated with the provided categories. Pay attention to context and potential variations in how entities might be expressed.
   c. For each identified entity:
      - When presented with a phrase, identify and focus only on the single key element. Ignore any surrounding elements in the named entity unless they are absolutely necessary to fully identify the entity.
         * The entity name should exclude any nouns that are also found in the matching category
      - Extract the exact text of the entity from the utterance
      - Identify which categories that the entity could belong to (in no particular order)
         * Make reasonable assumptions even when confidence is low
      - For entities that might belong to multiple categories, you must choose only one.
         * Assume that one of the categories is the correct one.
         * Assess which category is the most likely one and why.
         * Give low confidence if the category choice is unclear or ambiguous
      - For number + unit expressions, treat the number as the focus, even if it doesn't make semantic sense on its own.
   d. For any category that you didn't initially identify any entities in, double check the utterance to ensure you have not missed any.
      - A single entity may belong to multiple categories.

6. Before providing your final output, use a <scratchpad> to think through your entity identification and classification process.
   - Consider any ambiguities or challenges and how you're addressing them.
   - Justify any assumptions made.
      * Ensure that low confidence is given to any highly speculative assumptions made
   - Carefully consider the confidence of your identified entities and category classifications.
      * Give low confidence to high uncertainty uncovered in your analysis.

7. Construct a JSON object that follows the provided schema, populating it with all of the entities you've extracted. Ensure that your output is valid JSON and matches the schema structure exactly.

8. Provide your final analysis and output in the following format:
   <scratchpad>
   [Your thought process here]
   </scratchpad>

   <output>
   [Your JSON output here]
   </output>

Remember to adhere strictly to the provided JSON schema and ensure your output is valid JSON. Do not include any explanations or additional text outside of the specified tags."""


# If there is no match, do not include the entity in the output.
async def extract_entities(
    text: str,
    categories: Sequence[str],
    additional_context: str,
    message_history: list[ContextMessage],
) -> tuple[ExtractedEntities, Reasoning]:
    instructions_prompt = get_instructions_prompt(text, categories, additional_context)
    response = await openrouter.get_openrouter_response(
        messages=[
            openrouter.Message(role="system", content=SYSTEM_PROMPT),
            *[
                openrouter.Message(role=msg["role"], content=msg["content"])
                for msg in message_history
                if msg["role"] in ("system", "user", "assistant")
            ],
            openrouter.Message(role="user", content=instructions_prompt),
        ],
        models=["google/gemini-flash-1.5-8b"],
        temperature=openrouter.Temperature(value=0),
        seed=42,
    )

    message_content = openrouter.get_chat_completion_message(response)

    scratchpad_content = extract_xml_content(message_content, "scratchpad")

    output_json = extract_xml_content(message_content, "output")
    if output_json is None:
        msg = "No JSON content found in expected XML output"
        raise ValueError(msg)

    extracted_entities = ExtractedEntities.model_validate_json(output_json)

    return extracted_entities, "" if scratchpad_content is None else scratchpad_content
