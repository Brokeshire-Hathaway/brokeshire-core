from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel, Field, field_validator
from rich.console import Console

console = Console()


class TokenResponseData(BaseModel):
    id: str
    type: str


class PriceChangePercentage(BaseModel):
    m5: float | None = Field(default=0)
    m15: float | None = Field(default=0)
    m30: float | None = Field(default=0)
    h1: float | None = Field(default=0)
    h6: float | None = Field(default=0)
    h24: float | None = Field(default=0)

    @field_validator("m5", "m15", "m30", "h1", "h6", "h24", mode="before")
    @classmethod
    def validate_price_change(cls, v):
        if v is None:
            return 0
        try:
            return float(v)
        except (ValueError, TypeError):
            return 0


class VolumeUSD(BaseModel):
    m5: float | None = Field(default=0)
    m15: float | None = Field(default=0)
    m30: float | None = Field(default=0)
    h1: float | None = Field(default=0)
    h6: float | None = Field(default=0)
    h24: float | None = Field(default=0)

    @field_validator("m5", "m15", "m30", "h1", "h6", "h24", mode="before")
    @classmethod
    def validate_volume(cls, v):
        if v is None:
            return 0
        try:
            return float(v)
        except (ValueError, TypeError):
            return 0


class TransactionData(BaseModel):
    buys: int
    sells: int
    buyers: int
    sellers: int


class Transactions(BaseModel):
    m5: TransactionData
    m15: TransactionData
    m30: TransactionData
    h1: TransactionData
    h24: TransactionData


class Relationship(BaseModel):
    data: TokenResponseData


class Relationships(BaseModel):
    base_token: Relationship
    quote_token: Relationship
    dex: Relationship
    network: Relationship | None = None


class PoolAttributes(BaseModel):
    name: str | None = None
    pool_created_at: str
    volume_usd: VolumeUSD
    reserve_in_usd: str
    price_change_percentage: PriceChangePercentage
    transactions: Transactions
    base_token_price_usd: str | None = None
    base_token_price_native_currency: str | None = None
    quote_token_price_usd: str | None = None
    quote_token_price_native_currency: str | None = None
    base_token_price_quote_token: str | None = None
    quote_token_price_base_token: str | None = None
    address: str
    fdv_usd: str | None = None
    market_cap_usd: str | None = None


class PoolData(BaseModel):
    id: str
    type: str
    attributes: PoolAttributes
    relationships: Relationships


class PoolDataWithScore(PoolData):
    score: float = 0


class GeckoTerminalResponse(BaseModel):
    data: list[PoolData]


async def query_gecko_terminal(
    route: str, parameters: dict[str, Any] | None = None
) -> GeckoTerminalResponse:
    url = f"https://api.geckoterminal.com/api/v2{route}"
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (compatible; MyBot/1.0)",
    }

    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        try:
            response = await client.get(url, params=parameters)
            response.raise_for_status()
            return GeckoTerminalResponse.model_validate(response.json())
        except httpx.TimeoutException as e:
            msg = "Gecko Terminal API request timed out"
            raise Exception(msg) from e
        except httpx.HTTPStatusError as e:
            msg = f"Gecko Terminal API returned status code: {e.response.status_code}"
            raise Exception(msg) from e
        except Exception as error:
            msg = f"Failed querying gecko terminal: {error!s}"
            raise Exception(msg) from error
