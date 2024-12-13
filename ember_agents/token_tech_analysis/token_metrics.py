from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class QuoteToken(BaseModel):
    address: str | None = None
    name: str | None = None
    symbol: str | None = None


class DexScreenerPayments(BaseModel):
    payment_timestamp: int
    type: Literal["tokenProfile", "communityTakeover", "tokenAd", "trendingBarAd"]
    status: Literal["processing", "cancelled", "on-hold", "approved", "rejected"]


class Boosts(BaseModel):
    active: int


class TokenMetrics(BaseModel):
    # Basic token info
    name: str
    symbol: str
    address: str
    chain_id: str | None = None

    # Quote token info
    quote_token: QuoteToken | None = None

    # Price data
    price_usd: str | None = None
    price_native: str | None = None
    price_quote: str | None = None  # base_token_price_quote_token
    quote_price: str | None = None  # quote_token_price_base_token
    base_token_price_usd: str | None = None
    base_token_price_native_currency: str | None = None
    quote_token_price_usd: str | None = None
    quote_token_price_native_currency: str | None = None

    # Market metrics
    market_cap_usd: str | None = None
    fdv_usd: str | None = None

    # Liquidity data
    liquidity_usd: str | None = None
    liquidity_base: str | None = None
    liquidity_quote: str | None = None

    # Volume metrics by period
    volume_5m: str | None = None
    volume_15m: str | None = None
    volume_30m: str | None = None
    volume_1h: str | None = None
    volume_6h: str | None = None
    volume_24h: str | None = None

    # Transaction metrics by period
    buys_5m: int | None = None
    sells_5m: int | None = None
    buyers_5m: int | None = None
    sellers_5m: int | None = None

    buys_15m: int | None = None
    sells_15m: int | None = None
    buyers_15m: int | None = None
    sellers_15m: int | None = None

    buys_30m: int | None = None
    sells_30m: int | None = None
    buyers_30m: int | None = None
    sellers_30m: int | None = None

    buys_1h: int | None = None
    sells_1h: int | None = None
    buyers_1h: int | None = None
    sellers_1h: int | None = None

    buys_24h: int | None = None
    sells_24h: int | None = None
    buyers_24h: int | None = None
    sellers_24h: int | None = None

    # Price changes by period
    price_change_5m: str | None = None
    price_change_15m: str | None = None
    price_change_30m: str | None = None
    price_change_1h: str | None = None
    price_change_6h: str | None = None
    price_change_24h: str | None = None

    # Pool info
    pool_address: str | None = None
    pool_created_at: datetime | None = None
    reserve_usd: str | None = None

    # DEX info
    dex_id: str | None = None
    dex_url: str | None = None
    labels: list[str] | None = None

    # Additional metadata
    image_url: str | None = None
    websites: list[str] | None = None
    socials: list[str] | None = None

    # DexScreener Payments data
    dex_screener_payments: list[DexScreenerPayments] | None = None

    # Source tracking
    gecko_terminal_data: bool = False
    dex_screener_data: bool = False

    # Boosts information
    boosts: Boosts | None = None

    # Birdeye Security Data
    creator_address: str | None = None
    creator_balance: str | None = None
    creator_percentage: str | None = None
    creation_time: datetime | None = None
    top10_holder_balance: str | None = None
    top10_holder_percent: str | None = None
    top10_user_balance: str | None = None
    top10_user_percent: str | None = None
    total_supply: str | None = None
    is_token2022: bool | None = None
    mutable_metadata: bool | None = None
    freezeable: bool | None = None
    transfer_fee_enable: bool | None = None
    birdeye_data: bool = False
