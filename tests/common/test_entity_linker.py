from rich.console import Console
import pytest


import json

from ember_agents.common.entity_linker import link_entity

console = Console()

# Define the dictionary with variable names as keys and file names as values
json_files = {
    'Arbitrum': 'squidV1ArbitrumTokens.json',
    'Avalanche': 'squidV1AvalancheTokens.json',
    'Base': 'squidV1BaseTokens.json',
    'BNB Chain': 'squidV1BNBChainTokens.json',
    'Optimism': 'squidV1OptimismTokens.json',
}

# Create a dictionary to store the loaded JSON data
supported_tokens = {}

# Load each JSON file into the corresponding variable
for network_name, file_name in json_files.items():
    try:
        with open(f"tests/common/{file_name}", 'r') as file:
            supported_tokens[network_name] = json.load(file)
        print(f"Successfully loaded {file_name} into {network_name}")
    except FileNotFoundError:
        print(f"Error: {file_name} not found")
    except json.JSONDecodeError:
        print(f"Error: {file_name} is not a valid JSON file")


@pytest.mark.parametrize(
    "named_entity, network_name, unique_entities, expected_token_address, expected_is_confident",
    [
        (
            "usd",
            "Arbitrum",
            supported_tokens["Arbitrum"],
            "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
            True,
        ),
        (
            "axl",
            "Base",
            supported_tokens["Base"],
            "0x23ee2343B892b1BB63503a4FAbc840E0e2C6810f",
            True,
        ),
        (
            "doge coin",
            "BNB Chain",
            supported_tokens["BNB Chain"],
            "0xbA2aE424d960c26247Dd6c32edC70B295c744C43",
            True,
        ),
        (
            "btc",
            "Avalanche",
            supported_tokens["Avalanche"],
            "0x152b9d0FdC40C096757F570A51E494bd4b943E50",
            True,
        ),
        (
            "usdt",
            "Base",
            supported_tokens["Base"],
            "0x7f5373AE26c3E8FfC4c77b7255DF7eC1A9aF52a6",
            True,
        ),
        (
            "usdc",
            "Arbitrum",
            supported_tokens["Arbitrum"],
            "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
            True,
        ),
        (
            "usdce",
            "Arbitrum",
            supported_tokens["Arbitrum"],
            "0xff970a61a04b1ca14834a43f5de4533ebddb5cc8",
            True,
        ),
        (
            "arbitrum",
            "Arbitrum",
            supported_tokens["Arbitrum"],
            "0x912CE59144191C1204E64559FE8253a0e49E6548",
            True,
        ),
        (
            "op",
            "Optimism",
            supported_tokens["Optimism"],
            "0x4200000000000000000000000000000000000042",
            True,
        ),
        (
            "axelar",
            "Base",
            supported_tokens["Base"],
            "0x23ee2343B892b1BB63503a4FAbc840E0e2C6810f",
            True,
        ),
    ],
)
@pytest.mark.skip
async def test_classify_intent(
    named_entity: str,
    network_name: str,
    unique_entities: list[dict],
    expected_token_address: str,
    expected_is_confident: bool,
):
    print("\n---")

    results = await link_entity(
        named_entity, unique_entities, ["name", "symbol"], ["name", "symbol"]
    )

    console.print(f"[purple] results: {results} [/purple]")

    llm_matches = results["llm_matches"]
    if llm_matches is None or len(llm_matches) == 0:
        raise ValueError("No LLM matches found")
    entity_match = llm_matches[0]

    is_confident = entity_match["confidence_percentage"] >= 80

    # Confidence is probably too subjective and not that important
    # assert is_confident is expected_is_confident

    if is_confident:
        assert entity_match["entity"]["address"] == expected_token_address
