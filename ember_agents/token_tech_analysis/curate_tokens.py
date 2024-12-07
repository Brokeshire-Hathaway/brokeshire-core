import asyncio
from collections.abc import Sequence
from datetime import datetime
from functools import partial
from math import log
from typing import Any, TypedDict

import httpx
import rich
from pydantic import BaseModel, Field, field_validator
from rich.console import Console

console = Console()

SINGLE_TOKEN_PROBABILITY = 0.7


class TokenData(BaseModel):
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


class TransactionData(TypedDict):
    buys: int
    sells: int
    buyers: int
    sellers: int


class Transactions(BaseModel):
    m5: TransactionData | None = Field(
        default_factory=lambda: {"buys": 0, "sells": 0, "buyers": 0, "sellers": 0}
    )
    m15: TransactionData | None = Field(
        default_factory=lambda: {"buys": 0, "sells": 0, "buyers": 0, "sellers": 0}
    )
    m30: TransactionData | None = Field(
        default_factory=lambda: {"buys": 0, "sells": 0, "buyers": 0, "sellers": 0}
    )
    h1: TransactionData | None = Field(
        default_factory=lambda: {"buys": 0, "sells": 0, "buyers": 0, "sellers": 0}
    )
    h24: TransactionData | None = Field(
        default_factory=lambda: {"buys": 0, "sells": 0, "buyers": 0, "sellers": 0}
    )


class BaseToken(BaseModel):
    data: TokenData


class Relationships(BaseModel):
    base_token: BaseToken
    quote_token: BaseToken
    network: BaseToken
    dex: BaseToken


class PoolAttributes(BaseModel):
    name: str | None = None
    pool_created_at: str
    volume_usd: VolumeUSD
    reserve_in_usd: str
    price_change_percentage: PriceChangePercentage
    transactions: Transactions | None = None
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


class ComputedValues(TypedDict):
    pool_created_at: float
    volume_usd: float
    reserve_usd: float
    price_change_1h: float
    price_change_6h: float
    price_change_24h: float
    transactions_count: int


class TokenScore(TypedDict):
    item: PoolData
    computed_values: ComputedValues
    score: float


async def query_gecko_terminal(
    route: str, parameters: dict[str, Any] | None = None
) -> GeckoTerminalResponse:
    url = f"https://api.geckoterminal.com/api/v2{route}"

    async with httpx.AsyncClient(timeout=30.0) as client:
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


def get_top_tokens(pool_data: list[PoolData]) -> list[PoolDataWithScore]:
    epsilon = 1e-6

    def normalize(value: float, min_val: float, max_val: float) -> float:
        return 0 if max_val - min_val == 0 else (value - min_val) / (max_val - min_val)

    def get_percentile(sorted_values: Sequence[float], percentile: float) -> float:
        if not sorted_values:
            return 0
        index = (percentile / 100) * (len(sorted_values) - 1)
        lower = int(index)
        upper = min(lower + 1, len(sorted_values) - 1)
        weight = index % 1

        if upper >= len(sorted_values):
            return sorted_values[lower]
        return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight

    def safe_parse_float(value: Any) -> float:
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0

    # Extract and preprocess token data
    tokens_with_scores: list[TokenScore] = []
    for item in pool_data:
        try:
            attrs = item.attributes
            pool_created_at = (
                datetime.fromisoformat(
                    attrs.pool_created_at.replace("Z", "+00:00")
                ).timestamp()
                * 1000
            )
            volume_usd = safe_parse_float(attrs.volume_usd.h24) + epsilon
            reserve_usd = safe_parse_float(attrs.reserve_in_usd) + epsilon

            price_change_1h = safe_parse_float(attrs.price_change_percentage.h1)
            price_change_6h = safe_parse_float(attrs.price_change_percentage.h6)
            price_change_24h = safe_parse_float(attrs.price_change_percentage.h24)

            transactions = attrs.transactions.h24 if attrs.transactions else {}
            transactions_count = (
                transactions.get("buys", 0) + transactions.get("sells", 0)
                if isinstance(transactions, dict)
                else 0
            )

            tokens_with_scores.append(
                {
                    "item": item,
                    "computed_values": {
                        "pool_created_at": pool_created_at,
                        "volume_usd": volume_usd,
                        "reserve_usd": reserve_usd,
                        "price_change_1h": max(-100, min(price_change_1h, 500)),
                        "price_change_6h": max(-100, min(price_change_6h, 500)),
                        "price_change_24h": max(-100, min(price_change_24h, 500)),
                        "transactions_count": transactions_count,
                    },
                    "score": 0,
                }
            )
        except Exception as e:
            rich.print(f"[red]Error processing pool data: {e!s}[/red]")
            continue

    # Collect all values for normalization
    pool_created_at_times = [
        t["computed_values"]["pool_created_at"] for t in tokens_with_scores
    ]
    volume_values = [t["computed_values"]["volume_usd"] for t in tokens_with_scores]
    reserve_values = [t["computed_values"]["reserve_usd"] for t in tokens_with_scores]
    price_change_1h_values = [
        t["computed_values"]["price_change_1h"] for t in tokens_with_scores
    ]
    price_change_6h_values = [
        t["computed_values"]["price_change_6h"] for t in tokens_with_scores
    ]
    price_change_24h_values = [
        t["computed_values"]["price_change_24h"] for t in tokens_with_scores
    ]
    transactions_values = [
        t["computed_values"]["transactions_count"] for t in tokens_with_scores
    ]

    # Sort values for percentile calculation
    sorted_created_at = sorted(pool_created_at_times)
    sorted_volumes = sorted(volume_values)
    sorted_reserves = sorted(reserve_values)
    sorted_price_change_1h = sorted(price_change_1h_values)
    sorted_price_change_6h = sorted(price_change_6h_values)
    sorted_price_change_24h = sorted(price_change_24h_values)
    sorted_transactions = sorted(transactions_values)

    # Calculate percentiles
    percentile_calc = partial(get_percentile)
    min_created_at = percentile_calc(sorted_created_at, 5)
    max_created_at = percentile_calc(sorted_created_at, 95)
    min_volume = percentile_calc(sorted_volumes, 5)
    max_volume = percentile_calc(sorted_volumes, 95)
    min_reserve = percentile_calc(sorted_reserves, 5)
    max_reserve = percentile_calc(sorted_reserves, 95)
    min_price_change_1h = percentile_calc(sorted_price_change_1h, 5)
    max_price_change_1h = percentile_calc(sorted_price_change_1h, 95)
    min_price_change_6h = percentile_calc(sorted_price_change_6h, 5)
    max_price_change_6h = percentile_calc(sorted_price_change_6h, 95)
    min_price_change_24h = percentile_calc(sorted_price_change_24h, 5)
    max_price_change_24h = percentile_calc(sorted_price_change_24h, 95)
    min_transactions = percentile_calc(sorted_transactions, 5)
    max_transactions = percentile_calc(sorted_transactions, 95)

    # Calculate scores
    for token in tokens_with_scores:
        cv = token["computed_values"]

        try:
            recency_score = normalize(
                cv["pool_created_at"], min_created_at, max_created_at
            )
            volume_score = normalize(
                log(cv["volume_usd"] + epsilon),
                log(min_volume + epsilon),
                log(max_volume + epsilon),
            )
            reserve_score = normalize(
                log(cv["reserve_usd"] + epsilon),
                log(min_reserve + epsilon),
                log(max_reserve + epsilon),
            )
            price_change_score_1h = normalize(
                cv["price_change_1h"], min_price_change_1h, max_price_change_1h
            )
            price_change_score_6h = normalize(
                cv["price_change_6h"], min_price_change_6h, max_price_change_6h
            )
            price_change_score_24h = normalize(
                cv["price_change_24h"], min_price_change_24h, max_price_change_24h
            )
            transactions_score = normalize(
                log(cv["transactions_count"] + epsilon),
                log(min_transactions + epsilon),
                log(max_transactions + epsilon),
            )

            # Combine price change scores with weights
            price_change_score = (
                price_change_score_1h * 0.5
                + price_change_score_6h * 0.3
                + price_change_score_24h * 0.2
            )

            # Calculate final score with weights
            token["score"] = (
                recency_score * 0.35
                + volume_score * 0.25
                + reserve_score * 0.15
                + price_change_score * 0.15
                + transactions_score * 0.1
            )
        except Exception as e:
            rich.print(f"[red]Error calculating score: {e!s}[/red]")
            token["score"] = 0

    # Sort tokens by descending score
    tokens_with_scores.sort(key=lambda x: x["score"], reverse=True)

    # Return the top tokens with their original data and scores
    return [
        PoolDataWithScore(score=t["score"], **t["item"].model_dump())
        for t in tokens_with_scores[:10]
    ]


async def get_trending_tokens() -> list[PoolDataWithScore]:
    try:
        aggregated_data: list[PoolData] = []
        tasks = []

        # Create tasks for parallel execution
        for page in range(1, 6):
            search_parameters = {"page": page}
            tasks.append(
                query_gecko_terminal("/networks/trending_pools", search_parameters)
            )

        # Execute API calls in parallel
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        for i, response in enumerate(responses, 1):
            if isinstance(response, Exception):
                rich.print(f"[red]Error fetching page {i}: {response!s}[/red]")
                continue
            if isinstance(response, GeckoTerminalResponse):
                rich.print(
                    f"[green]Gecko Terminal returned {len(response.data)} trending pools on page {i}[/green]"
                )
                aggregated_data.extend(response.data)

        if not aggregated_data:
            return []

        top_tokens = get_top_tokens(aggregated_data)
        rich.print(
            f"Top tokens: {', '.join(t.attributes.name for t in top_tokens if t.attributes.name)}"
        )

        return top_tokens
    except Exception as error:
        rich.print(f"[red]Error in get_trending_tokens: {error!s}[/red]")
        return []
