import os
from typing import Annotated

from pydantic import AfterValidator
from pydantic_settings import BaseSettings, SettingsConfigDict


def file_string(v: str) -> str:
    if not os.path.isfile(v):
        return v

    with open(v) as file_value:
        return file_value.read()


SensitiveField = Annotated[str, AfterValidator(file_string)]


class Environment(BaseSettings):
    """All environment settings for the file."""

    model_config = SettingsConfigDict(env_file=".env", extra="allow")
    openai_api_key: SensitiveField
    pinecone_api_key: SensitiveField
    cohere_api_key: SensitiveField
    fireworks_api_key: SensitiveField
    openrouter_api_key: SensitiveField
    transaction_service_url: str
    coingecko_api_key: SensitiveField
    use_coingecko_pro_api: bool = False
    disable_transaction_signing_url: bool = False
    birdeye_api_key: SensitiveField


SETTINGS = Environment()  # type: ignore
