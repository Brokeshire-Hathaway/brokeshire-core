import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from functools import partial
from math import log
from typing import Any, TypedDict

from rich.console import Console

from ember_agents.token_tech_analysis.birdeye_client import query_birdeye_security
from ember_agents.token_tech_analysis.dex_screener_client import (
    query_dex_screener,
)
from ember_agents.token_tech_analysis.gecko_terminal_client import (
    GeckoTerminalResponse,
    PoolData,
    PoolDataWithScore,
    query_gecko_terminal,
)
from ember_agents.token_tech_analysis.token_metrics import (
    Boosts,
    DexScreenerPayments,
    QuoteToken,
    TokenMetrics,
)

console = Console(force_terminal=True)

SINGLE_TOKEN_PROBABILITY = 0.7


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


async def find_token(search_term: str) -> TokenMetrics:
    console.print(f"[yellow]Searching for token: {search_term}[/yellow]")
    search_parameters = {"query": search_term, "page": 1}
    response = await query_gecko_terminal("/search/pools", search_parameters)

    if not response.data:
        msg = f"No pools found for search term: {search_term}"
        raise Exception(msg)

    # Get the pool with highest reserves
    highest_reserve_pool = max(
        response.data, key=lambda pool: float(pool.attributes.reserve_in_usd or 0)
    )

    # Get base token address
    base_token = highest_reserve_pool.relationships.base_token.data
    token_address = (
        base_token.id.split("_", 1)[1] if "_" in base_token.id else base_token.id
    )

    # Create tasks for parallel API calls
    tasks = [query_dex_screener(token_address), query_birdeye_security(token_address)]
    api_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Use the shared create_token_metrics function
    return create_token_metrics(highest_reserve_pool, api_results[0], api_results[1])


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
            console.print(f"[red]Error processing pool data: {e!s}[/red]")
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
            console.print(f"[red]Error calculating score: {e!s}[/red]")
            token["score"] = 0

    # Sort tokens by descending score
    tokens_with_scores.sort(key=lambda x: x["score"], reverse=True)

    # Return the top tokens with their original data and scores
    return [
        PoolDataWithScore(score=t["score"], **t["item"].model_dump())
        for t in tokens_with_scores[:10]
    ]


async def get_trending_tokens() -> list[TokenMetrics]:
    try:
        # Get trending pools from GeckoTerminal (first page should be enough)
        search_parameters = {"page": 1}
        response = await query_gecko_terminal(
            "/networks/trending_pools", search_parameters
        )

        if not isinstance(response, GeckoTerminalResponse) or not response.data:
            console.print("[red]No trending pools found[/red]")
            return []

        # Get base token addresses from the pool data
        tasks = []
        for pool in response.data[:10]:  # Limit to top 10 pools
            base_token = pool.relationships.base_token.data
            token_address = (
                base_token.id.split("_", 1)[1]
                if "_" in base_token.id
                else base_token.id
            )

            # Create tasks for DexScreener and Birdeye API calls
            tasks.append(query_dex_screener(token_address))
            tasks.append(query_birdeye_security(token_address))

        # Execute API calls in parallel
        api_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results and create TokenMetrics objects
        token_metrics = []
        for i in range(0, len(api_results), 2):  # Process results in pairs
            pool = response.data[i // 2]
            dex_result = api_results[i]
            birdeye_result = api_results[i + 1]

            # Create TokenMetrics using the pool data and API results
            metrics = create_token_metrics(pool, dex_result, birdeye_result)
            token_metrics.append(metrics)

        return token_metrics

    except Exception as error:
        console.print(f"[red]Error in get_trending_tokens: {error!s}[/red]")
        return []


def create_token_metrics(
    pool: PoolData,
    dex_result: Any,
    birdeye_result: Any,
) -> TokenMetrics:
    """Create TokenMetrics object from pool data and API results"""

    console.print(
        f"[yellow]DexScreener token metrics for {pool.attributes.name}[/yellow]"
    )
    console.print(f"[yellow]DexScreener result: {dex_result}[/yellow]")
    console.print(f"[yellow]Birdeye token metrics for {pool.attributes.name}[/yellow]")
    console.print(f"[yellow]Birdeye result: {birdeye_result}[/yellow]")

    attrs = pool.attributes
    raw_symbol = attrs.name.split(" / ")[0] if attrs.name else "Unknown"
    cleaned_symbol = raw_symbol.lstrip("$").upper()

    base_token = pool.relationships.base_token.data
    token_address = (
        base_token.id.split("_", 1)[1] if "_" in base_token.id else base_token.id
    )

    # Initialize with GeckoTerminal data
    metadata = TokenMetrics(
        name=attrs.name or "",
        symbol=cleaned_symbol,
        address=token_address,
        pool_address=attrs.address,
        pool_created_at=datetime.fromisoformat(
            attrs.pool_created_at.replace("Z", "+00:00")
        ),
        liquidity_usd=attrs.reserve_in_usd,
        # Price changes
        price_change_5m=(
            str(attrs.price_change_percentage.m5)
            if attrs.price_change_percentage.m5 is not None
            else None
        ),
        price_change_15m=(
            str(attrs.price_change_percentage.m15)
            if attrs.price_change_percentage.m15 is not None
            else None
        ),
        price_change_30m=(
            str(attrs.price_change_percentage.m30)
            if attrs.price_change_percentage.m30 is not None
            else None
        ),
        price_change_1h=(
            str(attrs.price_change_percentage.h1)
            if attrs.price_change_percentage.h1 is not None
            else None
        ),
        price_change_6h=(
            str(attrs.price_change_percentage.h6)
            if attrs.price_change_percentage.h6 is not None
            else None
        ),
        price_change_24h=(
            str(attrs.price_change_percentage.h24)
            if attrs.price_change_percentage.h24 is not None
            else None
        ),
        # Volume metrics
        volume_5m=str(attrs.volume_usd.m5) if attrs.volume_usd.m5 is not None else "0",
        volume_15m=(
            str(attrs.volume_usd.m15) if attrs.volume_usd.m15 is not None else "0"
        ),
        volume_30m=(
            str(attrs.volume_usd.m30) if attrs.volume_usd.m30 is not None else "0"
        ),
        volume_1h=str(attrs.volume_usd.h1) if attrs.volume_usd.h1 is not None else "0",
        volume_6h=str(attrs.volume_usd.h6) if attrs.volume_usd.h6 is not None else "0",
        volume_24h=(
            str(attrs.volume_usd.h24) if attrs.volume_usd.h24 is not None else "0"
        ),
        # Transaction metrics
        buys_5m=attrs.transactions.m5.buys if attrs.transactions else None,
        sells_5m=attrs.transactions.m5.sells if attrs.transactions else None,
        buyers_5m=attrs.transactions.m5.buyers if attrs.transactions else None,
        sellers_5m=attrs.transactions.m5.sellers if attrs.transactions else None,
        buys_15m=attrs.transactions.m15.buys if attrs.transactions else None,
        sells_15m=attrs.transactions.m15.sells if attrs.transactions else None,
        buyers_15m=attrs.transactions.m15.buyers if attrs.transactions else None,
        sellers_15m=attrs.transactions.m15.sellers if attrs.transactions else None,
        buys_30m=attrs.transactions.m30.buys if attrs.transactions else None,
        sells_30m=attrs.transactions.m30.sells if attrs.transactions else None,
        buyers_30m=attrs.transactions.m30.buyers if attrs.transactions else None,
        sellers_30m=attrs.transactions.m30.sellers if attrs.transactions else None,
        buys_1h=attrs.transactions.h1.buys if attrs.transactions else None,
        sells_1h=attrs.transactions.h1.sells if attrs.transactions else None,
        buyers_1h=attrs.transactions.h1.buyers if attrs.transactions else None,
        sellers_1h=attrs.transactions.h1.sellers if attrs.transactions else None,
        buys_24h=attrs.transactions.h24.buys if attrs.transactions else None,
        sells_24h=attrs.transactions.h24.sells if attrs.transactions else None,
        buyers_24h=attrs.transactions.h24.buyers if attrs.transactions else None,
        sellers_24h=attrs.transactions.h24.sellers if attrs.transactions else None,
        # Token prices
        base_token_price_usd=attrs.base_token_price_usd or "0",
        base_token_price_native_currency=attrs.base_token_price_native_currency or "0",
        quote_token_price_usd=attrs.quote_token_price_usd or "0",
        quote_token_price_native_currency=attrs.quote_token_price_native_currency
        or "0",
        gecko_terminal_data=True,
    )

    # Add DexScreener data if available
    if isinstance(dex_result, tuple) and not isinstance(dex_result[0], BaseException):
        dex_data, orders_data = dex_result
        if hasattr(dex_data, "pairs") and dex_data.pairs:
            pair = dex_data.pairs[0]
            metadata.chain_id = pair.chain_id
            metadata.price_usd = pair.price_usd or "0"
            metadata.price_native = pair.price_native or "0"
            metadata.market_cap_usd = (
                str(pair.market_cap) if pair.market_cap is not None else "0"
            )
            metadata.fdv_usd = str(pair.fdv) if pair.fdv is not None else "0"

            if pair.quote_token:
                metadata.quote_token = QuoteToken(
                    address=pair.quote_token.address,
                    name=pair.quote_token.name,
                    symbol=pair.quote_token.symbol,
                )

            if pair.liquidity:
                metadata.liquidity_usd = (
                    str(pair.liquidity.usd) if pair.liquidity.usd is not None else "0"
                )
                metadata.liquidity_base = (
                    str(pair.liquidity.base) if pair.liquidity.base is not None else "0"
                )
                metadata.liquidity_quote = (
                    str(pair.liquidity.quote)
                    if pair.liquidity.quote is not None
                    else "0"
                )

            metadata.dex_id = pair.dex_id
            metadata.dex_url = pair.url
            metadata.labels = pair.labels

            if pair.info:
                metadata.image_url = pair.info.image_url
                if pair.info.websites:
                    metadata.websites = [w.url for w in pair.info.websites]
                if pair.info.socials:
                    metadata.socials = [s.url for s in pair.info.socials]

            if pair.boosts:
                metadata.boosts = Boosts(active=pair.boosts.active)

            if orders_data:
                metadata.dex_screener_payments = [
                    DexScreenerPayments(
                        payment_timestamp=status.payment_timestamp,
                        type=status.type,
                        status=status.status,
                    )
                    for status in orders_data.data
                ]

        metadata.dex_screener_data = True

    # Add Birdeye data if available
    if isinstance(birdeye_result, dict) and birdeye_result.get("success"):
        security_data = birdeye_result["data"]
        metadata.creator_address = security_data["creatorAddress"]
        metadata.creator_balance = str(security_data["creatorBalance"])
        metadata.creator_percentage = str(security_data["creatorPercentage"])
        metadata.creation_time = datetime.fromtimestamp(
            security_data["creationTime"], tz=UTC
        )
        metadata.top10_holder_balance = str(security_data["top10HolderBalance"])
        metadata.top10_holder_percent = str(security_data["top10HolderPercent"])
        metadata.top10_user_balance = str(security_data["top10UserBalance"])
        metadata.top10_user_percent = str(security_data["top10UserPercent"])
        metadata.total_supply = str(security_data["totalSupply"])
        metadata.is_token2022 = security_data["isToken2022"]
        metadata.mutable_metadata = security_data["mutableMetadata"]
        metadata.freezeable = security_data["freezeable"]
        metadata.transfer_fee_enable = security_data["transferFeeEnable"]
        metadata.birdeye_data = True

    return metadata
