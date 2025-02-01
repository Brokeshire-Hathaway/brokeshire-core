from typing import TypedDict

import httpx

from brokeshire_agents.settings import SETTINGS

BIRDEYE_BASE_URL = "https://public-api.birdeye.so"
BIRDEYE_API_KEY = SETTINGS.birdeye_api_key


class PreMarketHolder(TypedDict):
    pass  # Add fields if needed


class LockInfo(TypedDict):
    pass  # Add fields if needed


class TransferFeeData(TypedDict):
    pass  # Add fields if needed


class TokenSecurityData(TypedDict):
    creatorAddress: str
    creatorOwnerAddress: str | None
    ownerAddress: str | None
    ownerOfOwnerAddress: str | None
    creationTx: str
    creationTime: int
    creationSlot: int
    mintTx: str
    mintTime: int
    mintSlot: int
    creatorBalance: float
    ownerBalance: float | None
    ownerPercentage: float | None
    creatorPercentage: float
    metaplexUpdateAuthority: str
    metaplexOwnerUpdateAuthority: str
    metaplexUpdateAuthorityBalance: float | None
    metaplexUpdateAuthorityPercent: float | None
    mutableMetadata: bool
    top10HolderBalance: float
    top10HolderPercent: float
    top10UserBalance: float
    top10UserPercent: float
    isTrueToken: bool | None
    totalSupply: float
    preMarketHolder: list[PreMarketHolder]
    lockInfo: LockInfo | None
    freezeable: bool | None
    freezeAuthority: str | None
    transferFeeEnable: bool | None
    transferFeeData: TransferFeeData | None
    isToken2022: bool
    nonTransferable: bool | None


class BirdeyeResponse(TypedDict):
    data: TokenSecurityData
    success: bool
    statusCode: int


class BirdeyeErrorResponse(TypedDict):
    success: bool
    message: str


async def query_birdeye_security(
    token_address: str,
) -> BirdeyeResponse | BirdeyeErrorResponse:
    """Query Birdeye API for token security information."""
    headers = {"X-API-KEY": BIRDEYE_API_KEY, "accept": "application/json"}

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BIRDEYE_BASE_URL}/defi/token_security",
            params={"address": token_address},
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

        if not data.get("success"):
            msg = f"Birdeye API error: {data.get('message', 'Unknown error')}"
            raise ValueError(msg)

        return data
