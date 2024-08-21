import httpx
from pydantic import BaseModel, Field, HttpUrl
from web3 import Web3

from ember_agents.common.entity_linker import link_entity
from ember_agents.settings import SETTINGS


class Explorer(BaseModel):
    name: str
    url: HttpUrl


class BlockExplorers(BaseModel):
    default: Explorer


class Contract(BaseModel):
    address: str


class Contracts(BaseModel):
    multicall3: Contract


class NativeCurrency(BaseModel):
    decimals: int
    name: str
    symbol: str


class RpcUrls(BaseModel):
    default: dict[str, list[HttpUrl]]
    public: dict[str, list[HttpUrl]]


class Chain(BaseModel):
    id: int
    name: str
    network: str
    native_currency: NativeCurrency = Field(..., alias="nativeCurrency")
    contracts: Contracts
    rpc_urls: RpcUrls = Field(..., alias="rpcUrls")
    block_explorers: BlockExplorers = Field(..., alias="blockExplorers")

    class Config:
        allow_population_by_field_name = True


class Token(BaseModel):
    chain_id: int = Field(..., alias="chainId")
    address: str
    name: str
    symbol: str
    decimals: int
    logo_uri: HttpUrl = Field(..., alias="logoURI")
    coingecko_id: str | None = Field(None, alias="coingeckoId")
    common_key: str | None = Field(None, alias="commonKey")
    bridge_only: bool | None = Field(None, alias="bridgeOnly")

    class Config:
        allow_population_by_field_name = True


async def link_chain(chain_name: str):
    supported_chains = await _get_supported_chains()
    return await link_entity(
        chain_name,
        [chain.model_dump() for chain in supported_chains],
        ["name", "network"],
        ["name", "network"],
    )


async def link_token(token: str, chain_id: int):
    supported_tokens = await _get_supported_tokens(chain_id)

    if Web3.is_address(token):
        fuzzy_keys = ["address"]
        llm_keys = None
    else:
        fuzzy_keys = ["name", "symbol"]
        llm_keys = ["name", "symbol"]

    return await link_entity(
        token,
        [token.model_dump() for token in supported_tokens],
        fuzzy_keys,
        llm_keys,
    )


async def _get_supported_chains():
    url = f"{SETTINGS.transaction_service_url}/chains"
    try:
        async with httpx.AsyncClient(http2=True, timeout=2) as client:
            response = await client.get(url)
    except Exception as e:
        msg = f"An error occurred while requesting {url}: {e}"
        raise Exception(msg) from e
    return [Chain(**chain) for chain in response.json()]


async def _get_supported_tokens(chain_id: int):
    url = f"{SETTINGS.transaction_service_url}/tokens/{chain_id}"
    try:
        async with httpx.AsyncClient(http2=True, timeout=2) as client:
            response = await client.get(url)
    except Exception as e:
        msg = f"An error occurred while requesting {url}: {e}"
        raise Exception(msg) from e
    return [Token(**token) for token in response.json()]
