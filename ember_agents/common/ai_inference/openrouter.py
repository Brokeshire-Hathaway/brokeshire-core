from typing import Annotated, Literal

import httpx
from pydantic import BaseModel, Field

from ember_agents.settings import SETTINGS

Role = Literal["system", "user", "assistant"]


class Message(BaseModel):
    role: Role
    content: str


Model = Literal[
    "openai/gpt-4o-2024-05-13",
    "anthropic/claude-3.5-sonnet",
    "google/gemini-pro-1.5",
]


class OpenRouterChoice(BaseModel):
    finish_reason: str
    index: int
    message: Message


class OpenRouterUsage(BaseModel):
    completion_tokens: int
    prompt_tokens: int
    total_tokens: int


class OpenRouterResponse(BaseModel):
    choices: list[OpenRouterChoice]
    created: int
    id: str
    model: Model
    object: str
    system_fingerprint: str
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
    """

    temperature = Temperature(value=0.7) if temperature is None else temperature

    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {SETTINGS.openrouter_api_key}",
                "HTTP-Referer": SITE_URL,  # Optional, for including your app on openrouter.ai rankings.
                "X-Title": APP_NAME,  # Optional. Shows in rankings on openrouter.ai.
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

    return OpenRouterResponse.model_validate_json(response.text)
