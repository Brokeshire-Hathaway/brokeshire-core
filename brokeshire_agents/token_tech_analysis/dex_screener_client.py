from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field
from rich.console import Console


def to_camel(string: str) -> str:
    words = string.split("_")
    return words[0] + "".join(word.capitalize() for word in words[1:])


class TokenInfo(BaseModel):
    address: str
    name: str
    symbol: str


class QuoteTokenInfo(BaseModel):
    address: str | None = None
    name: str | None = None
    symbol: str | None = None


class TimePeriodTxns(BaseModel):
    buys: int
    sells: int


class TransactionsByPeriod(BaseModel):
    m5: TimePeriodTxns
    h1: TimePeriodTxns
    h6: TimePeriodTxns
    h24: TimePeriodTxns


class TimePeriodVolume(BaseModel):
    h24: float
    h6: float
    h1: float
    m5: float


class TimePeriodPriceChange(BaseModel):
    m5: float = 0
    h1: float = 0
    h6: float = 0
    h24: float = 0


class Liquidity(BaseModel):
    usd: float | None = None
    base: float | None = None
    quote: float | None = None


class WebsiteInfo(BaseModel):
    label: str
    url: str


class SocialInfo(BaseModel):
    type: str
    url: str


class TokenInfoExtended(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    image_url: str | None = None
    open_graph: str | None = None
    header: str | None = None
    websites: list[WebsiteInfo] | None = None
    socials: list[SocialInfo] | None = None


class Boosts(BaseModel):
    active: int


class DexScreenerPair(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    chain_id: str
    dex_id: str
    url: str
    pair_address: str
    labels: list[str] | None = None
    base_token: TokenInfo
    quote_token: QuoteTokenInfo
    price_native: str
    price_usd: str | None = None
    txns: TransactionsByPeriod | None = None
    volume: TimePeriodVolume | None = None
    price_change: TimePeriodPriceChange | None = None
    liquidity: Liquidity | None = None
    fdv: float | None = None
    market_cap: float | None = None
    pair_created_at: int | None = None
    info: TokenInfoExtended | None = None
    boosts: Boosts | None = None


class DexScreenerResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    schema_version: str
    pairs: list[DexScreenerPair] | None = None


class TokenProfileStatus(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    payment_timestamp: int
    type: Literal["tokenProfile", "communityTakeover", "tokenAd", "trendingBarAd"]
    status: Literal["processing", "cancelled", "on-hold", "approved", "rejected"]


class DexScreenerOrdersResponse(BaseModel):
    data: list[TokenProfileStatus]


async def query_dex_screener_orders(
    chain_id: str, token_address: str
) -> DexScreenerOrdersResponse:
    url = f"https://api.dexscreener.com/orders/v1/{chain_id}/{token_address}"
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (compatible; MyBot/1.0)",
    }

    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            return DexScreenerOrdersResponse.model_validate({"data": response.json()})
        except httpx.TimeoutException as e:
            msg = "DexScreener Orders API request timed out"
            raise Exception(msg) from e
        except httpx.HTTPStatusError as e:
            msg = (
                f"DexScreener Orders API returned status code: {e.response.status_code}"
            )
            raise Exception(msg) from e
        except Exception as error:
            msg = f"Failed querying DexScreener Orders: {error!s}"
            raise Exception(msg) from error


console = Console()


async def query_dex_screener(
    token_address: str,
) -> tuple[DexScreenerResponse, DexScreenerOrdersResponse | None]:
    console.print(
        f"[blue]Querying DexScreener with token address: {token_address}[/blue]"
    )
    pairs_data = await _query_dex_screener_pairs(token_address)

    # If we have pairs, get the orders data using the chain ID from the first pair
    if pairs_data.pairs:
        try:
            chain_id = pairs_data.pairs[0].chain_id
            orders_data = await query_dex_screener_orders(chain_id, token_address)
        except Exception as e:
            console.print(f"[yellow]Failed to fetch orders data: {e}[/yellow]")

    return pairs_data, orders_data


async def _query_dex_screener_pairs(token_address: str) -> DexScreenerResponse:
    url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (compatible; MyBot/1.0)",
    }

    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            json_response = response.json()

            # The DexScreener API returns pairs in a different structure
            # We need to wrap it in the expected format
            formatted_response = {
                "schemaVersion": "1.0.0",
                "pairs": json_response.get("pairs", []),
            }

            return DexScreenerResponse.model_validate(formatted_response)
        except httpx.TimeoutException as e:
            msg = "DexScreener API request timed out"
            raise Exception(msg) from e
        except httpx.HTTPStatusError as e:
            msg = f"DexScreener API returned status code: {e.response.status_code}"
            raise Exception(msg) from e
        except Exception as error:
            msg = f"Failed querying DexScreener: {error!s}"
            raise Exception(msg) from error
