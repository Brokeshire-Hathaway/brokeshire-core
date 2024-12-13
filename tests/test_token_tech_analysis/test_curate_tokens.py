import pytest

from ember_agents.token_tech_analysis.curate_tokens import (
    find_token,
    get_trending_tokens,
)
from ember_agents.token_tech_analysis.token_metrics import TokenMetrics


@pytest.mark.asyncio
async def test_find_token_brokeagi():
    """Test finding BROKEAGI token - a known token with good liquidity"""
    token = await find_token("BROKEAGI")

    # Basic validations
    assert isinstance(token, TokenMetrics)
    assert token.name is not None
    assert token.symbol is not None
    assert token.liquidity_usd is not None
    assert token.gecko_terminal_data is True

    # Check DexScreener data
    assert token.dex_screener_data is True
    assert token.chain_id is not None
    assert token.quote_token is not None
    assert token.dex_id is not None

    # Check Birdeye data
    assert token.birdeye_data is True
    assert token.creator_address is not None
    assert token.creator_balance is not None
    assert token.creator_percentage is not None
    assert token.top10_holder_balance is not None
    assert token.top10_holder_percent is not None
    assert token.total_supply is not None


@pytest.mark.asyncio
async def test_find_token_nonexistent():
    """Test finding a token that shouldn't exist"""
    with pytest.raises(Exception) as exc_info:
        await find_token("NONEXISTENTTOKENXYZ123456789")
    assert "No pools found for search term" in str(exc_info.value)


@pytest.mark.asyncio
async def test_find_token_pepe():
    """Test finding PEPE - should always have data"""
    token = await find_token("PEPE")

    # Basic validations
    assert isinstance(token, TokenMetrics)
    assert token.liquidity_usd is not None
    assert token.volume_24h is not None
    assert token.gecko_terminal_data is True
    assert token.dex_screener_data is True

    # Check liquidity data
    assert token.liquidity_usd is not None
    assert float(token.liquidity_usd) > 0

    # Check Birdeye data
    assert token.birdeye_data is False
    assert token.creator_address is None
    assert token.total_supply is None
    assert token.top10_holder_balance is None


@pytest.mark.asyncio
async def test_get_trending_tokens():
    """Test getting trending tokens and validating their data"""
    trending_tokens = await get_trending_tokens()

    # Basic validations
    assert isinstance(trending_tokens, list)
    assert len(trending_tokens) > 0
    assert all(isinstance(token, TokenMetrics) for token in trending_tokens)

    # Test first token in detail since it should be most reliable
    token = trending_tokens[0]

    # Basic token data
    assert token.name is not None
    assert token.symbol is not None
    assert token.address is not None
    assert token.pool_address is not None
    assert token.pool_created_at is not None
    assert token.gecko_terminal_data is True

    # Liquidity and volume data
    assert token.liquidity_usd is not None
    assert float(token.liquidity_usd) > 0
    assert token.volume_24h is not None
    assert float(token.volume_24h) >= 0

    # Price changes should exist
    assert token.price_change_24h is not None
    assert token.price_change_1h is not None

    # Transaction metrics
    assert token.buys_24h is not None or token.buys_24h == 0
    assert token.sells_24h is not None or token.sells_24h == 0

    # DexScreener data
    assert token.dex_screener_data in (True, False)
    if token.dex_screener_data:
        assert token.chain_id is not None
        assert token.price_usd is not None
        assert float(token.price_usd) >= 0
        assert token.dex_id is not None

    # Birdeye data (might not be available for all tokens)
    assert token.birdeye_data in (True, False)
    if token.birdeye_data:
        assert token.creator_address is not None
        assert token.total_supply is not None
        assert token.top10_holder_percent is not None
