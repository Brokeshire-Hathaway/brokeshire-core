import math

import httpx
from pydantic import BaseModel, ConfigDict, HttpUrl
from pydantic.alias_generators import to_camel
from solders.pubkey import Pubkey
from web3 import Web3

from brokeshire_agents.common.entity_linker import link_entity
from brokeshire_agents.settings import SETTINGS


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
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    chain_id: str
    chain_type: str
    icon_uri: str
    name: str
    block_explorer_urls: list[str]
    last_updated: str
    supported_protocols: list[str]


class AbstractToken(BaseModel):
    name: list[str]
    symbol: str


class Token(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    address: str
    name: str
    symbol: str
    decimals: int
    chain_id: str
    chain_name: str
    icon_uri: str | None = None
    coingecko_id: str | None = None
    usd_price: float | None = None
    primary_data_source: str
    is_vetted_by_primary_data_source: bool
    last_updated: str
    supported_protocols: list[str]


class YieldStrategy(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    vault_id: str
    name: str
    token_address: str
    chain_id: str
    protocol_name: str
    wrapped_protocol_name: str | None = None
    apy_day: str
    points_yield: str | None = None
    tvl: str
    last_updated: str
    lockup_period: str | None = None


async def link_chain(chain_name: str):
    supported_chains = await _get_supported_chains()
    return await link_entity(
        chain_name,
        [chain.model_dump() for chain in supported_chains],
        ["name", "chain_id"],
        ["name", "chain_id"],
    )


async def link_abstract_token(token: str):
    supported_abstract_tokens = await _get_supported_abstract_tokens()
    return await link_entity(
        token,
        [token.model_dump() for token in supported_abstract_tokens],
        ["name", "symbol"],
        ["name", "symbol"],
    )


def is_valid_sol_address(addr: str) -> bool:
    """Check if string is a valid Solana pubkey without raising an exception."""
    # Optional: you can also check for correct length
    try:
        _ = Pubkey.from_string(addr)
        return True
    except ValueError:
        return False


async def link_token(token: str, chain_id: str):
    supported_tokens = await _get_supported_tokens(chain_id)
    print("Token length", len(supported_tokens))
    supported_tokens_dict = [token.model_dump() for token in supported_tokens]

    # Check if it's an address (either ETH or SOL)
    if Web3.is_address(token) or is_valid_sol_address(token):
        fuzzy_keys = ["address"]
        return await link_entity(
            token,
            supported_tokens_dict,
            fuzzy_keys,
        )

    fuzzy_keys = ["name", "symbol"]
    fuzzy_results = await link_entity(
        token,
        supported_tokens_dict,
        fuzzy_keys,
    )
    fuzzy_matches = fuzzy_results.get("fuzzy_matches")
    if fuzzy_matches:
        # Check if any matches are vetted by the primary data source
        vetted_matches = [
            match
            for match in fuzzy_matches
            if match["entity"]["is_vetted_by_primary_data_source"]
        ]
        if vetted_matches:
            # If there are vetted matches, use only those
            llm_entity_list = [match["entity"] for match in vetted_matches]
        else:
            # If none are vetted, include all matches
            llm_entity_list = [match["entity"] for match in fuzzy_matches]
    else:
        # If fuzzy_matches is None or empty, use the full list
        llm_entity_list = supported_tokens_dict

    llm_keys = ["name", "symbol"]

    return await link_entity(
        token,
        llm_entity_list,
        None,
        llm_keys,
    )


async def get_best_yield_strategy(
    abstract_token_symbol: str | None = None,
    token_address: str | None = None,
    chain_id: str | None = None,
):
    url = f"{SETTINGS.transaction_service_url}/yield-strategies"
    params = {
        "abstract_token_symbol": abstract_token_symbol,
        "token_address": token_address,
        "chain_id": chain_id,
    }
    try:
        async with httpx.AsyncClient(http2=True, timeout=3) as client:
            response = await client.get(url, params=params)
    except Exception as e:
        msg = f"An error occurred while requesting {url}: {e}"
        raise Exception(msg) from e

    yield_strategies = [YieldStrategy(**strategy) for strategy in response.json()]
    return _select_optimal_yield_strategy(yield_strategies)


async def _get_supported_chains():
    url = f"{SETTINGS.transaction_service_url}/chains"
    try:
        async with httpx.AsyncClient(http2=True, timeout=2) as client:
            response = await client.get(url)
    except Exception as e:
        msg = f"An error occurred while requesting {url}: {e}"
        raise Exception(msg) from e
    # rich.print(response.json())
    return [Chain.model_validate(chain) for chain in response.json()]


async def _get_supported_abstract_tokens():
    url = f"{SETTINGS.transaction_service_url}/tokens/abstract"
    try:
        async with httpx.AsyncClient(http2=True, timeout=2) as client:
            response = await client.get(url)
    except Exception as e:
        msg = f"An error occurred while requesting {url}: {e}"
        raise Exception(msg) from e
    return [AbstractToken.model_validate(token) for token in response.json()]


async def _get_supported_tokens(chain_id: str):
    url = f"{SETTINGS.transaction_service_url}/tokens/{chain_id}"
    try:
        async with httpx.AsyncClient(http2=True, timeout=2) as client:
            response = await client.get(url)
    except Exception as e:
        msg = f"An error occurred while requesting {url}: {e}"
        raise Exception(msg) from e
    return [Token.model_validate(token) for token in response.json()]


def _select_optimal_yield_strategy(
    strategies: list[YieldStrategy],
    alpha: float = 1.5,
    beta: float = 1,
    kappa: float = 100,
) -> YieldStrategy | None:
    """
    Determines the optimal yield strategy based on a heuristic equation considering APY and TVL.

    Parameters:
    - strategies (list[YieldStrategy]): List of YieldStrategy objects to evaluate.
    - alpha (float): Exponent for APY in the scoring formula. Default is 1.5.
    - beta (float): Exponent for the TVL term in the scoring formula. Default is 1.
    - kappa (float): Scaling parameter for TVL range normalization. Default is 100.

    Returns:
    - YieldStrategy | None: The strategy with the highest calculated score, or None if no strategies are provided.
    """

    # Filter out strategies with negative yields
    positive_yield_strategies = [s for s in strategies if float(s.apy_day) > 0]

    if not positive_yield_strategies:
        return None

    # Extract all TVL values to compute Min and Max
    tvl_values = [float(strategy.tvl) for strategy in positive_yield_strategies]
    max_tvl = max(tvl_values)
    min_tvl = min(tvl_values)

    # Ensure t is always positive
    t = (max_tvl - min_tvl) / kappa
    if t <= 0:
        t = 1e-6  # Assign a small positive value to avoid division by zero or negative t

    best_strategy = None
    highest_score = -math.inf  # Initialize with negative infinity

    # Iterate through each strategy to calculate its score
    for strategy in positive_yield_strategies:
        apy = float(strategy.apy_day)
        tvl = float(strategy.tvl)

        # Calculate the exponential term
        exponent = -(tvl - min_tvl) / t
        exp_term = 1 - math.exp(exponent)

        # Ensure that TVL is not less than Min TVL
        if tvl < min_tvl:
            exp_term = 0  # Penalize strategies with TVL less than Min TVL

        # Calculate the score
        score = (apy**alpha) * (exp_term**beta)

        # Debugging: Print intermediate values (optional)
        print(f"Strategy: {strategy.vault_id}, APY: {apy}, TVL: {tvl}, Score: {score}")

        # Update the best strategy if current score is higher
        if score > highest_score:
            highest_score = score
            best_strategy = strategy

    return best_strategy


# Example Usage
"""
if __name__ == "__main__":
    # Define the strategy data
    strategy_data = [
        YieldStrategy(strategy_id="A", token_address="0x...", protocol_name="ProtocolA", apy="15", tvl="1000000"),
        YieldStrategy(strategy_id="B", token_address="0x...", protocol_name="ProtocolB", apy="10", tvl="10000000"),
        YieldStrategy(strategy_id="C", token_address="0x...", protocol_name="ProtocolC", apy="20", tvl="500000"),
        YieldStrategy(strategy_id="D", token_address="0x...", protocol_name="ProtocolD", apy="8", tvl="50000000"),
        YieldStrategy(strategy_id="E", token_address="0x...", protocol_name="ProtocolE", apy="12", tvl="5000000"),
        YieldStrategy(strategy_id="F", token_address="0x...", protocol_name="ProtocolF", apy="100", tvl="10000"),
    ]

    # Get the best strategy
    best = get_best_strategy(strategy_data)

    if best:
        print(f"The best strategy is {best.strategy_id} with APY {best.apy}% and TVL ${float(best.tvl)/1e6:.2f} million.")
    else:
        print("No strategies found.")
"""
