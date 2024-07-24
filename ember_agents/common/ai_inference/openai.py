from typing import Annotated, Literal, TypedDict

from openai import NOT_GIVEN, AsyncOpenAI, NotGiven
from openai.types.chat import ChatCompletion, ChatCompletionMessageParam
from openai.types.chat.completion_create_params import ResponseFormat
from pydantic import BaseModel, Field

from ember_agents.settings import SETTINGS

Role = Literal["system", "user", "assistant"]


class Message(TypedDict):
    role: Role
    content: str


Model = Literal["gpt-4o-2024-05-13", "gpt-4o-mini-2024-07-18"]


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
    Get a response from the OpenRouter API.
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
