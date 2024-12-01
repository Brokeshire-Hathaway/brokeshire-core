import json
from collections.abc import Callable, Iterable
from typing import Any, Literal, TypeVar

import httpx
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel

from ember_agents.settings import SETTINGS

Sentiment = Literal["positive", "neutral", "negative", "unknown"]

client = AsyncOpenAI(api_key=SETTINGS.openai_api_key)

openai_settings = {
    "model": "gpt-3.5-turbo-0125",
    "response_format": {"type": "json_object"},
    "temperature": 0,
    "seed": 1,
}


class ProjectInfo(BaseModel):
    # coingecko
    name: str
    description: str | None
    symbol: str
    website: str | None
    twitter_handle: str | None
    network: str
    price: float | None
    ath: float | None
    price_change_24h: float | None
    market_cap: float | None
    liquidity: str | None = None
    token_contract_address: str | None
    pool_address: str | None = None
    dex_screener_url: str | None = None
    # goplus


class EmberOnProject(BaseModel):
    project_description: str
    project_emoji: str

    class Config:
        extra = "allow"


class TokenQueried(BaseModel):
    token_name_or_symbol: str | None
    token_address: str | None

    class Config:
        extra = "allow"


#### main market route function
async def market_route(
    message: str, context: list[ChatCompletionMessageParam] | None = None
) -> str:
    token_queried = await extract_token_from_message(message, context=context)
    try:
        info_of_token = await information_from_token_apis(token_queried)
    except ValueError as e:
        return str(e)

    if info_of_token is None:
        return "Contract Address is not valid"
    embers_description = (
        await get_new_desc_from_ember(info_of_token.description)
        if info_of_token.description is not None
        else None
    )
    token_ticker = info_of_token.symbol.upper()
    market_cap = info_of_token.market_cap if info_of_token.market_cap else None
    network = info_of_token.network
    price = f"{info_of_token.price:.4f}" if info_of_token.price else None
    ath = info_of_token.ath if info_of_token.ath else None
    liquidity = info_of_token.liquidity if info_of_token.liquidity else None
    ath_delta = (
        (info_of_token.price - info_of_token.ath) / info_of_token.ath
        if info_of_token.ath and info_of_token.price is not None
        else None
    )
    pool_address = (
        f"📈 [Dexscreener]({info_of_token.dex_screener_url})"
        if info_of_token.dex_screener_url is not None
        else info_of_token.pool_address
    )
    if embers_description is None:
        return f"""
**| {info_of_token.name} (${token_ticker}) |**

**🔗 Network ・** {network}
**💵 Price ・** ${price} (24hr {info_of_token.price_change_24h})
**💰 Market Cap ・** ${market_cap}
**💧 Liquidity ・** {liquidity}
**🔖 Token Contract Address ・** {info_of_token.token_contract_address}
**🏊 Pool Address ・** {pool_address}

_Always do your own research_ 🧐💡🚀
"""
    desc = embers_description.project_description
    emoji = embers_description.project_emoji
    price_header = (
        f"\n**💵 Price ・** ${price} (24hΔ: {info_of_token.price_change_24h}%)\n(ATH: ${ath} Δ: {ath_delta:.2%})"
        if price
        else ""
    )
    market_cap_header = f"\n**💰 Market Cap ・** ${market_cap}" if market_cap else ""
    return f"""
**| {emoji} {info_of_token.name} (${token_ticker}) |**

**🔗 Network ・** {network}{price_header}{market_cap_header}

{desc}

🐦・[@{info_of_token.twitter_handle}](https://twitter.com/{info_of_token.twitter_handle})
🕸️・{info_of_token.website}
"""


#### get new description of token from ember
async def get_new_desc_from_ember(description: str) -> EmberOnProject:
    system_message = """
# Mission
Give your take on a project in a structured JSON format.

# Identity
- Name: Ember AI or Ember for short.
- Specializes in crypto and DeFi.

## Personality
- Charismatic, friendly, humorous, and curious. You are also a bit of a joker and like to have fun.
- Good listener, keen to understand people and their issues.
- Uses emojis moderately without any specific preferences.
- Advise users to conduct their research and invest wisely.

# Rules
- Always answer truthfully and helpfully.
- Avoid referencing yourself or Ember in the response.
- Use declarative phrasing, don't use terms akin to sounds, seems like, appears to be. Inject your personality
- Be concise and provide only two or three sentences, but don't forget to have a little fun!
- For "project_emoji" refrain for using money emojis such as 💰, 💵, 💲, etc.

# Example
## User Project Input
Lossless - hack mitigation tool for token creators. Lossless Protocol freezes fraudulent transaction based on a set of fraud identification parameters and returns stolen funds back to the owner's account.
## JSON
```json
"project_description": "Lossless is like the superhero cape for token creators, swooping in to freeze those dastardly fraudulent transactions with a flick of its mighty fraud-fighting parameters! 🦸‍♂️ With the power to hit the "undo" button on crypto theft, it's bringing a little peace of mind to the Wild West of tokenomics. 📚✨",
"project_emoji": "🔐"
}
```
"""
    user_message = (
        f"Return the description and emoji for this project:\n\n{description}"
    )
    chat_completion = await client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": system_message,
            },
            {
                "role": "user",
                "content": user_message,
            },
        ],
        **openai_settings,
    )
    response = chat_completion.choices[0].message.content
    json_response = json.loads(response)
    return EmberOnProject(**json_response)


#### Extracts the token name or address for user message
async def extract_token_from_message(
    message: str, context: list[ChatCompletionMessageParam] | None = None
) -> TokenQueried:
    system_message = """You are a crypto token research expert responsible for returning the single word token referenced in a message in the following structured json format:
# Examples
## Input
I want info on camelot
## JSON
```json
{
"token_name_or_symbol": "camelot",
"token_address": ""
}
```
## Input
search 0x1234567890123456789012345678901234567890
## JSON
```json
{
"token_name_or_symbol": "",
"token_address": "0x1234567890123456789012345678901234567890"
}
```
"""
    user_message = f"Extract the singular crypto token or contract address the user is referencing:\n{message}"
    try:
        chat_completion = await client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": system_message,
                },
                *(context or []),
                {
                    "role": "user",
                    "content": user_message,
                },
            ],
            **openai_settings,
        )
    except Exception as e:
        print(f"Error: {e}", flush=True)
        raise e
    print(f"chat_completion DONE: {chat_completion}", flush=True)
    response = chat_completion.choices[0].message.content
    json_response = json.loads(response)
    token_queried = TokenQueried(**json_response)
    return token_queried


#### main info function
async def information_from_token_apis(token_queried: TokenQueried) -> ProjectInfo:
    if token_queried.token_address not in (None, ""):
        project_details = await query_token_in_dexscreener(token_queried.token_address)
        return project_details

    if token_queried.token_name_or_symbol in (None, ""):
        msg = "Token name could not be parsed out."
        raise ValueError(msg)

    coingecko_id = await get_coingecko_id(token_queried.token_name_or_symbol)
    if coingecko_id is None:
        print("Coingecko failed, searching for gecko terminal...")
        return await query_token_in_dexscreener(token_queried.token_name_or_symbol)
    return await search_coingecko_with_id(coingecko_id)


async def query_coingecko(route: str, parameters: dict[str, Any] | None = None) -> Any:
    """It queries coingecko API in a given route depending on the API key provided."""

    api_prefix = "pro-api" if SETTINGS.use_coingecko_pro_api else "api"
    header_name = (
        "x-cg-demo-api-key" if SETTINGS.use_coingecko_pro_api else "x_cg_pro_api_key"
    )
    url = f"https://{api_prefix}.coingecko.com/api/v3{route}"
    async with httpx.AsyncClient(http2=True) as client:
        response = await client.get(
            url, params=parameters, headers={header_name: SETTINGS.coingecko_api_key}
        )
    if not response.is_success:
        msg = "Failed querying coingecko"
        raise ValueError(msg)
    return response.json()


async def query_gecko_terminal(
    route: str, parameters: dict[str, Any] | None = None
) -> Any:
    """It queries gecko terminal for dex information."""

    url = f"https://api.geckoterminal.com/api/v2{route}"
    async with httpx.AsyncClient(http2=True) as client:
        response = await client.get(url, params=parameters)
    if not response.is_success:
        msg = "Failed querying gecko terminal"
        raise ValueError(msg)
    return response.json()


async def query_token_in_dexscreener(tokenAddressOrSymbol: str):
    # catch if its a contract address
    async with httpx.AsyncClient(http2=True) as client:
        response = await client.get(
            "https://api.dexscreener.com/latest/dex/search",
            params={"q": tokenAddressOrSymbol},
        )

    token_information = get_largest_by_volume(
        response.json(),
        lambda x: x.get("pairs", []),
        lambda y: y.get("volume", {})["h24"],
    )
    if token_information is None:
        msg = "Could not find token address info"
        raise ValueError(msg)

    apply_callback = lambda x, c: c(x) if x is not None else None
    find_social = lambda x, t: next(
        (x["url"] for x in x if x.get("type", "") == t and len(x.get("url", "")) >= 1),
        None,
    )
    base_token = token_information.get("baseToken", {})
    token_additional_info = token_information.get("info", {})
    return ProjectInfo(
        token_contract_address=base_token.get("address"),
        name=base_token.get("name"),
        description=None,
        website=find_social(token_additional_info.get("websites", []), "Website"),
        ath=None,
        network=token_information.get("chainId"),
        twitter_handle=find_social(token_additional_info.get("socials", []), "twitter"),
        symbol=base_token.get("symbol"),
        price=token_information.get("priceUsd"),
        price_change_24h=token_information.get("priceChange", {}).get("h24"),
        market_cap=token_information.get("marketCap"),
        pool_address=token_information.get("pairAddress"),
        liquidity=apply_callback(
            token_information.get("liquidity", {}).get("usd"), str
        ),
        dex_screener_url=token_information.get("url"),
    )


T = TypeVar("T")
K = TypeVar("K")


def get_largest_by_volume(
    data: T,
    get_iterator: Callable[[T], Iterable[K] | None],
    get_volume: Callable[[K], int | float],
) -> K | None:
    """Get the largest entry for an iterator on an object."""

    # Get iterator on object
    iterator = get_iterator(data)
    if iterator is None:
        return None

    largest_entry: K | None = None
    largest_volume: int | float | None = None

    # Find biggest volume in iterator
    for entry in iterator:
        volume = get_volume(entry)
        if largest_volume is None:
            largest_entry, largest_volume = entry, volume
            continue
        if volume > largest_volume:
            largest_entry, largest_volume = entry, volume

    return largest_entry


#### coingecko search for id
async def get_coingecko_id(search: str) -> str | None:
    try:
        coingecko_coins = await query_coingecko("/search", {"query": search})
    except Exception as error:
        print("Error querying coingecko ID", error)
        return None

    if len(coingecko_coins["coins"]) == 0:
        return None
    return coingecko_coins["coins"][0]["id"]


#### orchestrate cg and lc
async def search_coingecko_with_id(coingecko_id: str) -> ProjectInfo:
    json_response = await query_coingecko(
        f"/coins/{coingecko_id}",
        {
            "symbols": "false",
            "market_data": "true",
            "community_data": "false",
            "developer_data": "false",
            "sparkline": "false",
        },
    )
    token_contract_address = json_response.get("contract_address", None)
    name = json_response["name"]
    description = json_response["description"]["en"]
    symbol = json_response["symbol"]
    homepage = json_response["links"]["homepage"][0]
    twitter_screen_name = json_response["links"]["twitter_screen_name"]
    price = json_response["market_data"]["current_price"].get("usd", None)
    ath = json_response["market_data"]["ath"].get("usd", None)
    price_change_24h = json_response["market_data"]["price_change_percentage_24h"]
    market_cap = json_response["market_data"]["market_cap"].get("usd", None)
    asset_platform_id = (
        "_Native to its own blockchain._"
        if json_response["asset_platform_id"] is None
        else json_response["asset_platform_id"]
    )
    return ProjectInfo(
        token_contract_address=token_contract_address,
        name=name,
        description=description,
        symbol=symbol,
        network=asset_platform_id,
        ath=ath,
        price=price,
        price_change_24h=price_change_24h,
        market_cap=market_cap,
        website=homepage,
        twitter_handle=twitter_screen_name,
    )
