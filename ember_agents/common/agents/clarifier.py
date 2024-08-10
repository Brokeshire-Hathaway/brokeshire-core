from defusedxml import ElementTree
from openai.types.chat import (
    ChatCompletionMessageParam,
)
from pydantic import BaseModel

from ember_agents.common.ai_inference.openai import Temperature, get_openai_response


class ClarifierResponse(BaseModel):
    next_node: str
    questions: str | None
    revised_utterance: str | None


SYSTEM_PROMPT = """You are an AI assistant tasked with clarifying information needed to complete users intents. Your goal is to analyze the user's intent, identify any problems with the information, and formulate appropriate questions to gather or correct that information."""


def extract_xml_content(xml_string, tag_name):
    # Wrap the input in a root element
    wrapped_xml = f"<root>{xml_string}</root>"
    root = ElementTree.fromstring(wrapped_xml)
    element = root.find(f".//{tag_name}")
    return (
        element.text.strip()
        if element is not None and element.text is not None
        else None
    )


def get_instructions_prompt(
    utterance: str, intent_classification: str, provided_info: str, deficient_info: str
) -> str:
    return f"""You will be provided with three inputs:
1. The user's initial intent
2. Any information that has already been provided
3. Any information that still needs to be clarified

Here's what you need to do:
<instructions>
1. Analyze the user's intent:
<user_intent>
    <utterance>
    ${utterance}
    </utterance>
    <classification>
    ${intent_classification}
    </classification>
</user_intent>

2. Review the information already provided:
<provided_info>
${provided_info}
</provided_info>

3. Review the information that still needs to be clarified:
<deficient_info>
${deficient_info}
</deficient_info>

4. Identify any missing or unclear information that is necessary to fully understand and complete the user's intent. Consider details such as:
    - Who: Relevant people or entities
    - What: Specific items, actions, or services
    - When: Dates, times, or durations
    - Where: Locations or venues
    - How: Methods, processes, or preferences
    - Why: Reasons or motivations (if relevant)

5. Formulate clear and concise questions to gather the deficient information. Ensure that:
    - Questions are directly related to the user's intent
    - Each question addresses a single piece of deficient information
    - Questions are phrased in a polite and user-friendly manner

6. Carefully reflect on the deficient information and ensure that the user has fully satisfied the requirements of the deficient information.

7. Choose the next node to call based on the following rules:
    - If all deficient information has been satisfied, choose "default"
    - Otherwise, choose "ask_user"

8. Provide your response based on the following rules:
    - When choosing "default", provide your response in the following format:
    <analysis>
    Briefly explain how the deficient information has been satisfied.
    </analysis>

    <revised_utterance>
    Create a new utterance that satisfies both the user's intent and the deficient information. It should be as clear and concise as possible.
    </revised_utterance>

    <next_node>
    default
    </next_node>

    - When choosing "ask_user", provide your response in the following format:
    <analysis>
    Briefly explain your understanding of the user's intent and how to elucidate the deficient information.
    </analysis>

    <questions>
    List your questions, one per line, numbered.
    </questions>

    <next_node>
    ask_user
    </next_node>
</instructions>

Remember to tailor your questions to the specific context of the user's intent and the information already provided. Your goal is to gather all necessary information efficiently and politely."""


async def get_clarifier_response(
    utterance: str,
    intent_classification: str,
    provided_info: str,
    deficient_info: str,
    message_history: list[ChatCompletionMessageParam],
) -> ClarifierResponse:
    instructions_prompt = get_instructions_prompt(
        utterance, intent_classification, provided_info, deficient_info
    )
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": instructions_prompt},
        *message_history,
    ]
    response = await get_openai_response(
        messages,
        "gpt-4o-2024-05-13",
        Temperature(value=0.5),
    )

    questions = extract_xml_content(response.choices[0].message.content, "questions")
    revised_utterance = extract_xml_content(
        response.choices[0].message.content, "revised_utterance"
    )
    next_node = extract_xml_content(response.choices[0].message.content, "next_node")

    if next_node is None:
        msg = "No next agent found in clarifier response"
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
