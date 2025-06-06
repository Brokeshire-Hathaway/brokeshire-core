import json
from math import exp
from typing import Annotated, Any, Literal, TypedDict

from openai import NOT_GIVEN, AsyncOpenAI, NotGiven
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionMessage,
    ChatCompletionMessageParam,
    ChatCompletionTokenLogprob,
)
from openai.types.chat.completion_create_params import ResponseFormat
from pydantic import BaseModel, Field

from brokeshire_agents.settings import SETTINGS

Role = Literal["system", "user", "assistant"]


class Message(TypedDict):
    role: Role
    content: str


Model = Literal["gpt-4o-2024-05-13", "gpt-4o-2024-08-06", "gpt-4o-mini-2024-07-18"]


class Temperature(BaseModel):
    value: Annotated[float, Field(ge=0, le=2)]


client = AsyncOpenAI(api_key=SETTINGS.openai_api_key)


async def get_openai_response(
    messages: list[ChatCompletionMessageParam],
    model: Model,
    temperature: Temperature | None = None,
    response_format: ResponseFormat | NotGiven = NOT_GIVEN,
    *,
    seed: int | None = None,
    logprobs: bool = False,
    top_logprobs: int | None = None,
) -> ChatCompletion:
    """
    Get a response from the OpenAI API.
    """

    temperature = Temperature(value=0.7) if temperature is None else temperature

    chat_completion = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature.value,
        seed=seed,
        response_format=response_format,
        logprobs=logprobs,
        top_logprobs=top_logprobs,
    )

    return chat_completion


class ChatCompletionError(Exception):
    """Base exception for chat completion errors."""

    pass


class NoChoicesError(ChatCompletionError):
    """Raised when there are no choices in the ChatCompletion."""

    pass


class NoContentError(ChatCompletionError):
    """Raised when no content could be extracted from the ChatCompletion."""

    pass


def get_chat_completion_message(completion: ChatCompletion) -> str:
    """
    Extract the message from a ChatCompletion object.

    :param completion: The ChatCompletion object to convert
    :return: A string containing the message from ChatCompletion
    :raises NoChoicesError: If there are no choices in the completion
    :raises NoContentError: If no content could be extracted from the completion
    """
    if not completion.choices:
        msg = "The ChatCompletion object contains no choices."
        raise NoChoicesError(msg)

    choice = completion.choices[0]

    if isinstance(choice.message, ChatCompletionMessage) and choice.message.content:
        return choice.message.content

    msg = "No content could be extracted from the ChatCompletion."
    raise NoContentError(msg)


def get_chat_completion_logprobs(
    completion: ChatCompletion,
) -> list[ChatCompletionTokenLogprob]:
    if not completion.choices:
        msg = "The ChatCompletion object contains no choices."
        raise NoChoicesError(msg)

    logprobs = completion.choices[0].logprobs

    if logprobs is None or logprobs.content is None:
        msg = "No logprobs found in response"
        raise ValueError(msg)

    return logprobs.content


def find_json_logprobs(
    json_content: str, tokens: list[ChatCompletionTokenLogprob]
) -> list[ChatCompletionTokenLogprob]:
    """
    Find the matching logprobs for the JSON content in the token list.

    Args:
    json_content (str): The JSON content to find.
    tokens (List[ChatCompletionTokenLogprob]): Full list of token logprob objects.

    Returns:
    List[ChatCompletionTokenLogprob]: The list of logprob objects that match the JSON content.

    Raises:
    ValueError: If the JSON content cannot be found in the tokens.
    """
    # Normalize the input JSON content
    json_content_normalized = json.dumps(json.loads(json_content), sort_keys=True)

    accumulated_content = ""
    matching_logprobs = []

    for token in tokens:
        accumulated_content += token.token
        matching_logprobs.append(token)

        # Try to parse and normalize the accumulated content
        try:
            accumulated_normalized = json.dumps(
                json.loads(accumulated_content), sort_keys=True
            )
            if accumulated_normalized == json_content_normalized:
                return matching_logprobs
        except json.JSONDecodeError:
            # If it's not valid JSON yet, continue accumulating
            pass

        # If accumulated content is too long, trim the oldest token and continue
        while len(accumulated_content) > len(json_content):
            accumulated_content = accumulated_content[len(matching_logprobs[0].token) :]
            matching_logprobs.pop(0)

    msg = "JSON content not found in tokens"
    raise ValueError(msg)


def add_confidence_to_json_values(
    logprobs: list[ChatCompletionTokenLogprob],
) -> dict[str, Any]:
    # Reconstruct the original JSON string
    json_string = "".join(logprob.token for logprob in logprobs)

    # Parse the JSON string
    json_obj = json.loads(json_string)

    def find_matching_logprobs(obj: Any, start_index: int) -> tuple[float, int]:
        obj_str = str(obj)  # Use json.dumps to handle all types correctly
        obj_index = 0
        current_index = start_index
        matching_logprobs = []

        while obj_index < len(obj_str) and current_index < len(logprobs):
            token = logprobs[current_index].token
            if obj_str.startswith(token, obj_index):
                matching_logprobs.append(logprobs[current_index])
                obj_index += len(token)
                current_index += 1
            else:
                # If we don't match, reset and start from the next token
                obj_index = 0
                matching_logprobs = []
                current_index = start_index + 1
                start_index += 1

        if obj_index == len(obj_str):
            if matching_logprobs:
                first_logprob = matching_logprobs[0].logprob
                print(f"*** top_logprobs: {matching_logprobs[0].top_logprobs}")
            else:
                first_logprob = 0  # Default value for empty strings or other edge cases
            return first_logprob, current_index
        else:
            msg = f"No match found for {obj} at index {start_index}"
            raise ValueError(msg)

    def logprob_to_percentage(logprob: float) -> float:
        # Convert logprob to linear probability and then to percentage
        return round(exp(logprob) * 100, 4)

    def replace_recursive(obj: Any, start_index: int) -> tuple[Any, int]:
        if isinstance(obj, dict):
            new_obj = {}
            for key, value in obj.items():
                new_value, start_index = replace_recursive(value, start_index)
                new_obj[key] = new_value
            return new_obj, start_index
        elif isinstance(obj, list):
            new_list = []
            for item in obj:
                new_item, start_index = replace_recursive(item, start_index)
                new_list.append(new_item)
            return new_list, start_index
        else:  # Replace any scalar value (string, number, boolean, null)
            first_logprob, new_index = find_matching_logprobs(obj, start_index)
            percentage = logprob_to_percentage(first_logprob)
            return {"value": obj, "confidence_percentage": percentage}, new_index

    result, _ = replace_recursive(json_obj, 0)
    return result
