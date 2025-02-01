from pprint import pprint
import pytest


from brokeshire_agents.common.entity_linker import link_entity
from brokeshire_agents.common.transaction import link_chain, link_token


@pytest.mark.parametrize(
    "chain_name, expected_chain_id",
    [
        (
            "arbitrum",
            42161,
        ),
        (
            "optimism",
            10,
        ),
        (
            "ethereum",
            1,
        ),
        (
            "base",
            8453,
        ),
    ],
)
@pytest.mark.skip
async def test_link_chain(
    chain_name: str,
    expected_chain_id: int,
):
    print("\n---")

    results = await link_chain(chain_name)

    pprint(results["llm_matches"])

    llm_matches = results["llm_matches"]
    if llm_matches is None or len(llm_matches) == 0:
        raise ValueError("No LLM matches found")
    entity_match = llm_matches[0]

    is_confident = entity_match["confidence_percentage"] >= 80

    assert is_confident
    assert entity_match["entity"]["id"] == expected_chain_id


@pytest.mark.parametrize(
    "token_name, chain_id, expected_token_address",
    [
        ("usd", 42161, "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"),
        ("usdc", 42161, "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"),
        ("usdce", 42161, "0xff970a61a04b1ca14834a43f5de4533ebddb5cc8"),
        ("arbitrum", 42161, "0x912CE59144191C1204E64559FE8253a0e49E6548"),
        ("usdt", 8453, "0x7f5373AE26c3E8FfC4c77b7255DF7eC1A9aF52a6"),
        ("axl", 8453, "0x23ee2343B892b1BB63503a4FAbc840E0e2C6810f"),
        ("axelar", 8453, "0x23ee2343B892b1BB63503a4FAbc840E0e2C6810f"),
        ("doge coin", 56, "0xbA2aE424d960c26247Dd6c32edC70B295c744C43"),
        ("btc", 43114, "0x152b9d0FdC40C096757F570A51E494bd4b943E50"),
        ("op", 10, "0x4200000000000000000000000000000000000042"),
    ],
)
@pytest.mark.skip
async def test_link_token_by_name(
    token_name: str,
    chain_id: int,
    expected_token_address: str,
):
    print("\n---")

    results = await link_token(token_name, chain_id)

    pprint(results["llm_matches"])

    llm_matches = results["llm_matches"]
    if llm_matches is None or len(llm_matches) == 0:
        raise ValueError("No LLM matches found")
    entity_match = llm_matches[0]

    is_confident = entity_match["confidence_percentage"] >= 75

    assert is_confident
    assert entity_match["entity"]["address"] == expected_token_address


@pytest.mark.parametrize(
    "token_address, chain_id, expected_token_name",
    [
        ("0x912CE59144191C1204E64559FE8253a0e49E6548", 42161, "Arbitrum"),
        ("0x23ee2343B892b1BB63503a4FAbc840E0e2C6810f", 8453, "Axelar"),
        ("0xbA2aE424d960c26247Dd6c32edC70B295c744C43", 56, "Dogecoin"),
        ("0x152b9d0FdC40C096757F570A51E494bd4b943E50", 43114, "Bitcoin"),
        ("0x4200000000000000000000000000000000000042", 10, "Optimism"),
    ],
)
@pytest.mark.skip
async def test_link_token_by_address(
    token_address: str,
    chain_id: int,
    expected_token_name: str,
):
    print("\n---")

    results = await link_token(token_address, chain_id)

    pprint(results["fuzzy_matches"])

    entity_match = results["fuzzy_matches"][0]

    is_confident = entity_match["confidence_percentage"] >= 95

    assert is_confident
    assert entity_match["entity"]["name"] == expected_token_name
