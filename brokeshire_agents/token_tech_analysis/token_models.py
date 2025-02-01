from pydantic import BaseModel

from brokeshire_agents.token_tech_analysis.token_metrics import TokenMetrics


class TokenInfo(BaseModel):
    symbol: str
    address: str
    chain_id: str | None = None
    chain_name: str
    explorer_uri: str | None = None


class TokenMarketData(BaseModel):
    price: str
    price_change_percentage_5m: str | None = None
    price_change_percentage_1h: str | None = None
    price_change_percentage_6h: str | None = None
    price_change_percentage_24h: str | None = None
    volume_5m: str
    volume_1h: str
    volume_6h: str
    volume_24h: str
    buys_5m: str
    sells_5m: str
    buyers_5m: str
    sellers_5m: str
    buys_15m: str
    sells_15m: str
    buyers_15m: str
    sellers_15m: str
    buys_30m: str
    sells_30m: str
    buyers_30m: str
    sellers_30m: str
    buys_1h: str
    sells_1h: str
    buyers_1h: str
    sellers_1h: str
    buys_24h: str
    sells_24h: str
    buyers_24h: str
    sellers_24h: str
    fdv: str
    market_cap: str | None = None
    market_cap_change_percentage_24h: str | None = None
    liquidity_in_usd: str | None = None
    holders: str | None = None
    holders_change_percentage_24h: str | None = None


class TokenRiskMetrics(BaseModel):
    locked_liquidity_percentage: str
    bundled_wallet_percentage: str
    whale_holder_percentage: str


class TokenData(BaseModel):
    token_info: TokenInfo
    market_data: TokenMarketData
    token_metrics: TokenMetrics
    risk_metrics: TokenRiskMetrics | None = None
