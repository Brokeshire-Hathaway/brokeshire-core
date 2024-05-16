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

    model_config = SettingsConfigDict(env_file=".env")
    openai_api_key: SensitiveField
    pinecone_api_key: SensitiveField
    cohere_api_key: SensitiveField
    transaction_service_url: str


SETTINGS = Environment()  # type: ignore
