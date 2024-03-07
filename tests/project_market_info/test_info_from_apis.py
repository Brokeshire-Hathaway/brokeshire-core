import json
from urllib import response

import httpx
import pytest

from src.ember_agents.project_market_info.info_from_apis import (
    extract_token_from_message,
    info_from_apis,
    lunarcrush,
    market_route,
)

#    coingecko,    dexscreener,    get_largest_by_volume_24h,    lunarcrush,


@pytest.mark.parametrize(
    "message",
    [
        ("UNI"),
    ],
)
@pytest.mark.skip
async def test_lunarcrush(message):
    response = await lunarcrush(message)
    print(response)


@pytest.mark.parametrize(
    "message",
    [
        ("I want info on lossless defi"),
        ("please search 0x3d9907f9a368ad0a51be60f7da3b97cf940982d8"),
    ],
)
@pytest.mark.skip
async def test_extract_token_from_message(message):
    token = await extract_token_from_message(message)
    print(token)


@pytest.mark.parametrize(
    "name",
    [
        # ("camelot"),
        # ("0x3d9907f9a368ad0a51be60f7da3b97cf940982d8"),
        # ("Camelot_token"),
        # ("camelot"),
        # ("airdao"),
        # ("SCALE")
        # ("thorchain"),
        # ("LSS"),
        # (""),
    ],
)
@pytest.mark.skip
async def test_info_from_apis(name):
    response = await info_from_apis(name)

    #    assert project_details.name == "Uniswap"  # This will pass
    #    assert (
    #        project_details.description
    #        == "UNI is the governance token for Uniswap, an Automated Market Marker DEX on the Ethereum blockchain. The UNI token allows token holders to participate in the governance of the protocol. Key decisions such as usage of the treasury or future upgrades can be decided through a governance vote."
    #    )
    #    assert project_details.twitter_handle == "Uniswap"
    #    assert project_details.network == "ethereum"
    #    assert project_details.website == "https://uniswap.org/"
    #    assert project_details.sentiment == "positive"
    #    assert project_details.pool_contract_addresses != None


@pytest.mark.parametrize(
    "message",
    [
        ("I want info on bitcoin token"),
        # ("I want info on doopy token"),
        # ("please search 6uybx1x8yucfj8ystpyizbyg7uqzaq2s46zwphumkjg5"),
        # ("please search 0x3d990asdasde60f7da3b97cf940982d8"),
    ],
)
@pytest.mark.skip
async def test_market_route(message):
    response = await market_route(message)
    print(f"========{message}==========")
    print(response)
