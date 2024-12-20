from typing import Annotated, Any, Literal

import httpx
from pydantic import BaseModel, Field

from ember_agents.settings import SETTINGS

Role = Literal["system", "user", "assistant"]


class Message(BaseModel):
    role: Role
    content: str


Model = Literal[
    "openai/gpt-4o-2024-05-13",
    "anthropic/claude-3.5-sonnet:beta",
    "anthropic/claude-3.5-sonnet",
    "google/gemini-pro-1.5",
    "google/gemini-flash-1.5-8b",
    "google/gemini-2.0-flash-exp:free",
    "openai/o1",
]


class OpenRouterChoice(BaseModel):
    finish_reason: str
    index: int
    message: Message
    logprobs: dict[str, Any] | None


class OpenRouterUsage(BaseModel):
    completion_tokens: int
    prompt_tokens: int
    total_tokens: int


class OpenRouterResponse(BaseModel):
    choices: list[OpenRouterChoice]
    created: int
    id: str
    model: str
    object: str
    system_fingerprint: str | None = None
    usage: OpenRouterUsage


class Temperature(BaseModel):
    value: Annotated[float, Field(ge=0, le=2)]


ResponseFormat = Literal["json_object"]


SITE_URL = "https://www.emberai.xyz/"
APP_NAME = "Ember AI"


async def get_openrouter_response(
    messages: list[Message],
    models: list[Model],
    temperature: Temperature | None = None,
    response_format: ResponseFormat | None = None,
    *,
    seed: int | None = None,
    logprobs: bool = False,
    top_logprobs: int | None = None,
) -> OpenRouterResponse:
    """
    Get a response from the OpenRouter API.

    Raises:
        httpx.HTTPError: If the HTTP request fails
        ValueError: If the API returns an error response
    """
    temperature = Temperature(value=0.7) if temperature is None else temperature

    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {SETTINGS.openrouter_api_key}",
                "HTTP-Referer": SITE_URL,
                "X-Title": APP_NAME,
            },
            json={
                "models": models,
                "messages": [message.model_dump() for message in messages],
                "temperature": temperature.value,
                "seed": seed,
                "response_format": (
                    None if response_format is None else {"type": response_format}
                ),
                "logprobs": True,
                "top_logprobs": top_logprobs,
            },
        )

        # Raise for HTTP status errors
        response.raise_for_status()

        # Parse the response JSON
        data = response.json()

        # Check if the response contains an error
        if "error" in data:
            raise ValueError(
                f"OpenRouter API error: {data['error'].get('message', 'Unknown error')}"
            )

    return OpenRouterResponse.model_validate(data)


class NoChoicesError(Exception):
    """Raised when there are no choices in the OpenRouterResponse."""

    pass


class NoContentError(Exception):
    """Raised when no content could be extracted from the OpenRouterResponse."""

    pass


def get_chat_completion_message(completion: OpenRouterResponse) -> str:
    """
    Extract the message from an OpenRouterResponse object.

    Args:
        completion: The OpenRouterResponse object to extract the message from

    Returns:
        str: The content of the message

    Raises:
        NoChoicesError: If there are no choices in the completion
        NoContentError: If no content could be extracted from the completion
    """
    if not completion.choices:
        msg = "The OpenRouterResponse object contains no choices."
        raise NoChoicesError(msg)

    choice = completion.choices[0]

    if choice.message.content:
        return choice.message.content

    msg = "No content could be extracted from the OpenRouterResponse."
    raise NoContentError(msg)
