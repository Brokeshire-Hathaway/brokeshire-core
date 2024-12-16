from pydantic import BaseModel
from rich import print

from ember_agents.common.ai_inference.openai import (
    Temperature,
    get_openai_response,
)
from ember_agents.common.ai_inference.parse_response import extract_xml_content
from ember_agents.common.conversation import ContextMessage


class ClarifierResponse(BaseModel):
    next_node: str
    questions: str | None
    revised_utterance: str | None


SYSTEM_PROMPT = """You are an AI assistant tasked with refining a user's intent and gathering necessary information. Your goal is to analyze the provided inputs, identify missing information, and formulate appropriate questions or a revised utterance based on the completeness of the information."""


def get_instructions_prompt(
    utterance: str, intent_classification: str, provided_info: str, deficient_info: str
) -> str:
    """
    4. Identify any missing or unclear information that is necessary to fully understand and complete the user's intent. Consider details such as:
    - Who: Relevant people or entities
    - What: Specific items, actions, or services
    - When: Dates, times, or durations
    - Where: Locations or venues
    - How: Methods, processes, or preferences
    - Why: Reasons or motivations (if relevant)
    """

    """
    Rewrite or rephrase the user's utterance to completely satisfy the deficient information. It should include any information necessary to make the user's intent clear and complete.


    - Your understanding of the user's intent using the provided information and the information that has been gathered or clarified.
      - An explanation of what information is still needed that is not already provided.
      - Any assumptions made based on the context and user's intent.
    """

    return f"""Follow these instructions carefully:

1. Review the following inputs:

<user_intent>
<utterance>
{utterance}
</utterance>
<classification>
{intent_classification}
</classification>
</user_intent>

<sufficient_info>
{provided_info}
</sufficient_info>

<deficient_info>
{deficient_info}
</deficient_info>

2. Analyze the user's intent and the sufficient information:
   a. Understand the user's initial request and its classification.
   b. Identify what information has already been provided.
   c. Carefully review the original utterance to identify any information that may already satisfy deficient fields.
   d. Determine what information is still missing or needs clarification.
   e. Make reasonable assumptions based on the context and user's intent, to be confirmed later if necessary.

3. Process the deficient information:
   a. Identify all required fields from the deficient_info that are still needed.
   b. Note any specific rules or constraints (e.g., mutually exclusive fields).
   c. Create a mental map of what information is still needed.

4. Formulate your response:
   a. Prepare a brief review of your analysis.
   b. If all required information has been provided:
      - Create a revised utterance that clearly and completely expresses the user's intent.
         * Include all information required to satisfy the user's intent from the sufficient_info, the deficient_info, and any other information that the user may have provided or clarified.
         * Ensure all names from the required information are preserved. Always use the original entity names unless otherwise revised by the user.
         * Do not modify the entity names from the required information for any reason, including pluralization (e.g., do not change 'zombie' to 'zombies')
      - Set the next_node to "default".
   c. If information is still missing:
      - Formulate clear, concise questions to confirm assumptions and gather only the truly missing information. Ensure each question:
        * Addresses a single piece of deficient information.
        * Is directly related to the user's intent and required fields.
        * Is phrased politely and in a user-friendly manner.
        * Converts fields from snake case to title case if mentioning them in questions.
        * Explains any constraints or rules if applicable.
        * Avoids asking for information already provided in the original utterance or by the user.
        * Presents assumptions for confirmation when appropriate.
      - Set the next_node to "ask_user".

5. Provide your response in the following format:

<analysis>
[Your analysis here]
</analysis>

[If all information is provided, include:]
<revised_utterance>
[Your revised utterance here]
</revised_utterance>

[If information is missing, include:]
<questions>
[Your numbered list of questions here]
</questions>

<next_node>
[Either "default" or "ask_user"]
</next_node>

6. Before finalizing your response, validate that:
   - All required fields identified from the deficient information are addressed.
   - Your response adheres to any specific rules or constraints mentioned in the deficient information.
   - If constructing a revised utterance, it includes all necessary information in a natural, conversational format.
   - Your response adheres to the format specified in the instructions.
      * Ensure that the <analysis>, <revised_utterance>, <questions>, and <next_node> tags are present, correctly formatted, and not empty.

Remember, your goal is to efficiently and politely gather all necessary information or provide a clear, complete revised utterance based on the user's intent and the information available."""


async def get_clarifier_response(
    utterance: str,
    intent_classification: str,
    provided_info: str,
    deficient_info: str,
    message_history: list[ContextMessage],
) -> ClarifierResponse:
    instructions_prompt = get_instructions_prompt(
        utterance, intent_classification, provided_info, deficient_info
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": instructions_prompt},
        *message_history,
    ]
    response = await get_openai_response(
        messages,
        "gpt-4o-2024-05-13",
        Temperature(value=0),
        seed=42,
    )

    questions = extract_xml_content(response.choices[0].message.content, "questions")
    analysis = extract_xml_content(response.choices[0].message.content, "analysis")
    print(f"analysis: {analysis}")
    revised_utterance = extract_xml_content(
        response.choices[0].message.content, "revised_utterance"
    )
    next_node = extract_xml_content(response.choices[0].message.content, "next_node")

    if next_node is None:
        msg = "No next agent found in clarifier response"
        raise ValueError(msg)

    if next_node == "default" and analysis is None:
        msg = "No analysis found in clarifier response"
        raise ValueError(msg)

    if next_node == "default" and revised_utterance is None:
        msg = "No updated utterance found in clarifier response"
        raise ValueError(msg)

    if next_node == "ask_user" and questions is None:
        msg = "No questions found in clarifier response"
        raise ValueError(msg)

    return ClarifierResponse(
        questions=questions,
        next_node=next_node,
        revised_utterance=revised_utterance,
    )
