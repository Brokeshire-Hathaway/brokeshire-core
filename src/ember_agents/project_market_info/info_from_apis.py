import json
import os
from pprint import pprint
from time import sleep
from typing import Literal, Optional

import httpx
from openai import AsyncOpenAI
from pydantic import BaseModel, Extra, HttpUrl

Sentiment = Literal["positive", "neutral", "negative", "unknown"]

client = AsyncOpenAI(
    # This is the default and can be omitted
    api_key=os.environ.get("OPENAI_API_KEY"),
)

openai_settings = {
    "model": "gpt-3.5-turbo-0125",
    "response_format": {"type": "json_object"},
    "temperature": 0,
    "seed": 1,
}


class ResponseFormat(BaseModel):
    # coingecko
    ember_response: str
    name: str
    description: Optional[str]
    symbol: str
    website: Optional[str]
    twitter_handle: Optional[str]
    network: Optional[str]
    price: str
    price_change_24h: str
    market_cap: str
    liquidity: Optional[str]
    # dex screener
    token_contract_address: Optional[str]
    # lunarcrush
    sentiment: Optional[Sentiment]


class ProjectInfo(BaseModel):
    # coingecko
    name: str
    description: Optional[str]
    symbol: str
    website: Optional[str]
    twitter_handle: Optional[str]
    network: str
    price: Optional[str]
    ath: Optional[str]
    price_change_24h: Optional[str]
    market_cap: Optional[str]
    liquidity: str | None = None
    token_contract_address: Optional[str]
    pool_address: str | None = None
    # lunarcrush
    sentiment: Sentiment | None
    # goplus


class CoinGecko(BaseModel):
    token_contract_address: Optional[str]
    name: str
    description: str
    symbol: str
    homepage: HttpUrl  # Use only the first valid URL
    twitter_screen_name: str
    asset_platform_id: str
    ath: Optional[str]
    price: Optional[str]
    price_change_24h: Optional[str]
    market_cap: Optional[str]

    class Config:
        extra = Extra.ignore


class LunarCrush(BaseModel):
    sentiment: Sentiment
    galaxy_score: str

    class Config:
        extra = Extra.ignore


class DexScreener(BaseModel):
    token_contract_address: str
    name: str
    description: str
    symbol: str
    network: str  # network
    price: str
    price_change_24h: str
    market_cap: str
    liquidity: str

    class Config:
        extra = Extra.ignore


class EmberOnProject(BaseModel):
    project_description: str
    project_emoji: str

    class Config:
        extra = Extra.ignore


class TokenQueried(BaseModel):
    token_name_or_symbol: str | None
    token_address: str | None

    class Config:
        extra = Extra.ignore


#### main market route function
async def market_route(message: str) -> str:
    token_queried = await extract_token_from_message(message)
    try:
        info_of_token = await info_from_apis(token_queried)
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
    market_cap = float(info_of_token.market_cap) if info_of_token.market_cap else None
    network = info_of_token.network
    price = f"{float(info_of_token.price):.4f}" if info_of_token.price else None
    ath = info_of_token.ath if info_of_token.ath else None
    liquidity = info_of_token.liquidity if info_of_token.liquidity else None
    ath_delta = (
        f"{((float(info_of_token.price) - float(info_of_token.ath)) / float(info_of_token.ath)):.2%}"
        if info_of_token.ath and info_of_token.price is not None
        else None
    )
    if embers_description is None:
        return f"""
**| {info_of_token.name} (${token_ticker}) |**

**🔗 Network ・** {network}
**💵 Price ・** ${price} (24hr {info_of_token.price_change_24h}%)
**💰 Market Cap ・** ${market_cap}
**💧 Liquidity ・** {liquidity}
**🔖 Token Contract Address ・** {info_of_token.token_contract_address}
**🏊 Pool Address ・** {info_of_token.pool_address}

_Always do your own research_ 🧐💡🚀
"""
    desc = embers_description.project_description
    emoji = embers_description.project_emoji
    price_header = (
        f"\n**💵 Price ・** ${price} (24hΔ: {info_of_token.price_change_24h}%)\n(ATH: ${ath} Δ: {ath_delta}%)"
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
Lossless - hack mitigation tool for token creators. Lossless Protocol freezes fraudulent transaction based on a set of fraud identification parameters and returns stolen funds back to the owner’s account.
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
    EmbersTake = EmberOnProject(**json_response)
    return EmbersTake


"""
## Input
Lossless - hack mitigation tool for token creators. Lossless Protocol freezes fraudulent transaction based on a set of fraud identification parameters and returns stolen funds back to the owner’s account.
"project_description": "Lossless is an innovative solution that enhances security for token creators. 🔒 By providing a mechanism to freeze and reverse fraudulent transactions, it helps mitigate the risks associated with hacks and unauthorized transfers, potentially increasing trust and safety for participants in the DeFi ecosystem. 👍🔄","""


#### Extracts the token name or address for user message
async def extract_token_from_message(message: str) -> TokenQueried:
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
async def info_from_apis(token_queried: TokenQueried):
    if token_queried.token_address not in (None, ""):
        project_details = await dexscreener(token_queried.token_address)
        return project_details

    if token_queried.token_name_or_symbol in (None, ""):
        raise ValueError("Token name could not be parsed out.")

    coingeckoid = await getidfromcoingecko(token_queried.token_name_or_symbol)
    if coingeckoid is None:
        raise ValueError("Token not found, please use Contract Address")
    return await coingecko_and_lunarcrush(coingeckoid)


#### orchestrate cg and lc
async def coingecko_and_lunarcrush(input: str) -> ProjectInfo:
    cg_response = await coingecko(input)
    lc_response = await lunarcrush(cg_response.symbol)
    return ProjectInfo(
        token_contract_address=cg_response.token_contract_address,
        name=cg_response.name,
        description=cg_response.description,
        symbol=cg_response.symbol,
        ath=cg_response.ath,
        website=cg_response.homepage,
        twitter_handle=cg_response.twitter_screen_name,
        network=cg_response.asset_platform_id,
        price=cg_response.price,
        price_change_24h=cg_response.price_change_24h,
        market_cap=cg_response.market_cap,
        sentiment=lc_response.sentiment,
    )


#### coingecko search for id
async def getidfromcoingecko(searchterm: str):
    URL = f"https://api.coingecko.com/api/v3/search?query={searchterm}"
    async with httpx.AsyncClient(http2=True) as client:
        response = await client.get(URL)

    if response.status_code != 200:
        msg = "Failed finding ID of token"
        raise ValueError(msg)

    json_response = response.json()
    if len(json_response["coins"]) == 0:
        return None
    return json_response["coins"][0]["id"]


#### coingecko info from id
async def coingecko(token_id: str):
    sleep(0.1)
    URL = f"https://api.coingecko.com/api/v3/coins/{token_id}?symbols=false&market_data=true&community_data=false&developer_data=false&sparkline=false"
    async with httpx.AsyncClient(http2=True) as client:
        response = await client.get(URL)

    if response.status_code != 200:
        msg = "Failed finding information of coin"
        raise ValueError(msg)

    json_response = response.json()
    try:
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
        coingecko = CoinGecko(
            token_contract_address=token_contract_address,
            name=name,
            description=description,
            symbol=symbol,
            homepage=homepage,
            twitter_screen_name=twitter_screen_name,
            asset_platform_id=asset_platform_id,
            ath=ath,
            price=price,
            price_change_24h=price_change_24h,
            market_cap=market_cap,
        )
    except Exception as e:
        print(f"Error: {e}", flush=True)
        raise e

    return coingecko


#### lunarcrush info
async def lunarcrush(symbol: str):
    URL = f"https://lunarcrush.com/api4/public/coins/{symbol}/time-series/v2"
    HEADERS = {"Authorization": "Bearer 10yzku3g0fh5ok48wvq65p1r7plt360axtmw7ec0z"}
    async with httpx.AsyncClient(http2=True) as client:
        response = await client.get(URL, headers=HEADERS)

    if response.status_code != 200:
        return LunarCrush(sentiment="unknown", galaxy_score="unknown")

    json = response.json()
    if len(json.get("data", [])) == 0:
        return LunarCrush(
            sentiment="unknown",
            galaxy_score="unknown",
        )

    mapped_sentiment, gscore = "unknown", "unknown"
    gscore = json["data"][0].get("galaxy_score", "unknown")
    if "sentiment" in json["data"][0]:
        mapped_sentiment = map_sentiment_to_literal(json["data"][0]["sentiment"])
    return LunarCrush(sentiment=mapped_sentiment, galaxy_score=gscore)


#### map lunarcursh sentiment to literal
def map_sentiment_to_literal(sentiment_score: int) -> Sentiment:
    if sentiment_score > 88:
        return "positive"
    elif sentiment_score > 50:
        return "neutral"
    elif sentiment_score > 0:
        return "negative"
    else:
        return "unknown"


#### get dexscreener info of token contract
async def dexscreener(token_contract_address: str):
    # catch if its a contract address
    URL = f"https://api.dexscreener.com/latest/dex/search/?q={token_contract_address}"
    async with httpx.AsyncClient(http2=True) as client:
        response = await client.get(URL)
    jsonresp = get_largest_by_volume_24h(response.json())
    if jsonresp is None:
        raise ValueError("Could not find token address info")
    return ProjectInfo(
        token_contract_address=token_contract_address,
        name=jsonresp.get("baseToken", {}).get("name"),
        description=None,
        website=None,
        ath=None,
        network=jsonresp.get("chainId"),
        twitter_handle=None,
        sentiment=None,
        symbol=jsonresp.get("baseToken", {}).get("symbol"),
        price=jsonresp.get("priceUsd"),
        price_change_24h=str(jsonresp.get("priceChange", {}).get("h24")),
        market_cap=jsonresp.get("fdv"),
        pool_address=jsonresp.get("pairAddress"),
        liquidity=jsonresp.get("liquidity").get("usd"),  #
    )


#### get largest pool with passed contract by volume
def get_largest_by_volume_24h(data):
    """
    This function takes a dictionary representing the received object and returns the entry with the largest 24-hour volume.

    Args:
      data: A dictionary representing the received object.

    Returns:
      The entry from the data with the largest 24-hour volume, or None if the object doesn't have a "pairs" key or any entry within "pairs" lacks a "volume" key with "h24" key.
    """
    # Check if the data has a "pairs" key
    if "pairs" not in data:
        print("No pairs found")
        return None

    # Initialize variables
    largest_entry = None
    largest_volume = None
    #    baseToken = None
    #    quoteToken = None

    # Iterate through each entry in "pairs"
    for entry in data["pairs"]:
        quoteToken = entry.get("quoteToken")
        baseToken = entry.get("baseToken")
        #        print(
        #            "================================================================= symbol ================================================================="
        #        )
        # print("---entry---")
        # print(entry)
        #        print(
        #            "================================================================= quote/basetokensymbol ================================================================="
        #        )
        #        print(str(baseToken.get("symbol")))
        #        print(str(quoteToken.get("symbol")))
        #        print(entry.get("volume", {}).get("h24"))

        # Check if the current entry has a "volume" key and "h24" key within it
        if (
            "volume" in entry
            and "h24" in entry["volume"]
            #            and (
            #               # matches symbol
            #                str(baseToken.get("symbol")) == str(symbol.upper())
            #                or str(quoteToken.get("symbol")) == str(symbol.upper())
            #            )
            ##            and (
            #                # matches name
            #                str(baseToken.get("name")) == str(project)
            #                or str(quoteToken.get("name")) == str(project)
            #            )
        ):
            #  Get the current entry's 24-hour volume
            volume = entry["volume"]["h24"]
            # Check if it's the largest encountered so far
            if largest_volume is None or volume > largest_volume:
                largest_volume = volume
                largest_entry = entry

    return largest_entry
