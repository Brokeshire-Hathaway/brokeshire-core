import json
import os
from typing import Literal, Optional
from pprint import pprint
import httpx
from attr import asdict
from numpy import empty, full
from openai import AsyncOpenAI
from pydantic import BaseModel, Extra, HttpUrl
from regex import P

Sentiment = Literal["positive", "neutral", "negative", "unknown"]

client = AsyncOpenAI(
    # This is the default and can be omitted
    api_key=os.environ.get("OPENAI_API_KEY"),
)

openai_settings = {
    "model":"gpt-3.5-turbo-0125",
    "response_format":{"type": "json_object"},
    "temperature": 0,
    "seed": 1
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
    price: str
    ath: Optional[str]
    price_change_24h: str
    market_cap: str
    liquidity: Optional[str]
    # dex screener
    token_contract_address: Optional[str]
    pool_address: Optional[str]
    # lunarcrush
    sentiment: Optional[Sentiment]
    #goplus

class CoinGecko(BaseModel):
    token_contract_address: Optional[str]
    name: str
    description: str
    symbol: str
    homepage: HttpUrl  # Use only the first valid URL
    twitter_screen_name: str
    asset_platform_id: str
    ath: str
    price: str
    price_change_24h: str
    market_cap: str

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
    network: str #network
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
    token_name_or_symbol: str
    token_address: str

    class Config:
        extra = Extra.ignore

#### main market route function
async def market_route(message:str) -> str:
    token_queried = await extract_token_from_message(message)
    print("___token_queried___")
    print(token_queried)
    try:
        info_of_token = await info_from_apis(token_queried)
        if info_of_token is None:
            return "Contract Address is not valid"
    except ValueError as e:
        print(e)
        return str(e)
    print("___info_of_token___")
    print(info_of_token)
    if info_of_token is None:
        response = "token not found"
    embers_description = await get_new_desc_from_ember(info_of_token.description) if info_of_token.description is not None else None
    token_ticker = info_of_token.symbol.upper()
    market_cap=format(int(info_of_token.market_cap), ",") 
    network=info_of_token.network.capitalize()
    price=format(round(float(info_of_token.price),2), ",")
    ath=format(float(info_of_token.ath), ",") if info_of_token.ath is not None else None
    liquidity=format(float(info_of_token.liquidity), ",") if info_of_token.liquidity is not None else None
    ath_delta = round(((float(info_of_token.price) - float(info_of_token.ath)) / float(info_of_token.ath)),2) if info_of_token.ath is not None else None
    if embers_description is None:
        response = f"""
**| {info_of_token.name} (${token_ticker}) |**

**🔗 Network・** {network}
**💵 Price・** ${price} (24hr {info_of_token.price_change_24h}%) 
**💰 Market Cap・** ${market_cap}
**💧 Liquidity・** {liquidity}
**🔖 Token Contract Address・** {info_of_token.token_contract_address}
**🏊 Pool Address・** {info_of_token.pool_address}

_Always do your own research_ 🧐💡🚀
"""
        return response
    else:
        desc=embers_description.project_description
        emoji=embers_description.project_emoji
        #print(f"desc: {desc}")
        #print(f"emoji: {emoji}")
        # ADD SENTIMENT BACK WHEN LUNARCRUSH IS PAID FOR
        response = f"""
**| {emoji} {info_of_token.name}** **(${token_ticker}) |**

**🔗 Network・** {network}
**💵 Price・** ${price} (24hΔ: {info_of_token.price_change_24h}%)
(ATH: ${ath} Δ: {ath_delta}%) 
**💰 Market Cap・** ${market_cap}

{desc}

🐦・(@{info_of_token.twitter_handle})[https://twitter.com/{info_of_token.twitter_handle}]
🕸️・{info_of_token.website}
"""
        return response    
#### get new description of token from ember
async def get_new_desc_from_ember(description: str) -> EmberOnProject:
    system_message = """
# Mission
You will, in a few words, tell me what you think about projects and return a single emoji that best represents the theme of the project in a structured JSON format.

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
- for "project_emoji" refrain for using money emojis such as 💰, 💵, 💲, etc.

# Example
## Input
Lossless - hack mitigation tool for token creators. Lossless Protocol freezes fraudulent transaction based on a set of fraud identification parameters and returns stolen funds back to the owner’s account.
## JSON
```json
{
"project_description": "Lossless is an innovative solution that enhances security for token creators. By providing a mechanism to freeze and reverse fraudulent transactions, it helps mitigate the risks associated with hacks and unauthorized transfers, potentially increasing trust and safety for participants in the DeFi ecosystem. 👍🔒🔄",
"project_emoji": "🔐"
}
```
"""
    user_message = (
        f"Return the description and emoji for this:\n{description}"
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
        **openai_settings
    )
    response = chat_completion.choices[0].message.content
    json_response = json.loads(response)
    EmbersTake = EmberOnProject(**json_response)
    print(f"EmbersTake:\n{EmbersTake}")
    return EmbersTake

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
    user_message = (
        f"Extract the singular crypto token or contract address the user is referencing:\n{message}"
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
        **openai_settings
    )
    response = chat_completion.choices[0].message.content
    json_response = json.loads(response)
    token_queried = TokenQueried(**json_response)
    return token_queried 

#### main info function
async def info_from_apis(token_queried: TokenQueried) -> Optional[ProjectInfo]:
    if token_queried.token_address is not (None or ""):
        print("===0x detected===")
        print(token_queried.token_address)
        project_details = await dexscreener(token_queried.token_address)
        print("___project_details____")
        print(project_details)
    else:
        coingeckoid = await getidfromcoingecko(token_queried.token_name_or_symbol)
        print(f"====found in coingecko - name or ticker is {coingeckoid}====")
        if coingeckoid is not None:
            project_details = await coingecko_and_lunarcrush(coingeckoid)
            print("___project_details____")
            print(project_details)
        else:
            raise ValueError("Token not found, please use Contract Address")
    return project_details

#### orchestrate cg and lc
async def coingecko_and_lunarcrush(input: str) -> ProjectInfo:
    cg_response = await coingecko(input)
    #print(f"___cg_response___{cg_response}")
    lc_response = await lunarcrush(cg_response.symbol)
    #print(f"___lc_response___{lc_response}")
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
    )  # type: ignore

#### coingecko search for id
async def getidfromcoingecko(searchterm: str):
    URL = f"https://api.coingecko.com/api/v3/search?query={searchterm}"
    async with httpx.AsyncClient(http2=True) as client:
        response = await client.get(URL)
    json_response = response.json()
    #    with open(f"{searchterm}_getidfromcoingecko.json", "w") as file:
    #        json.dump(json_response, file, indent=4)
    if len(json_response["coins"]) == 0:
        return None
    else:
        return json_response["coins"][0]["id"]

#### coingecko info from id
async def coingecko(token_id: str):
    URL = f"https://api.coingecko.com/api/v3/coins/{token_id}?symbols=false&market_data=true&community_data=false&developer_data=false&sparkline=false"
    async with httpx.AsyncClient(http2=True) as client:
        response = await client.get(URL)
    json_response = response.json()
    #pprint(f"___coingecko_response___{json_response}")
    #Output json_response to a file
    #with open(f"{token_id}_coingecko_response.json", "w") as file:
    #    json.dump(json_response, file, indent=4)

    #    print("____contract address___")
    #    print(json_response["contract_address"])
    return CoinGecko(
        token_contract_address=json_response["contract_address"]
        if json_response.get("contract_address")
        else None,
        name=json_response["name"],
        description=json_response["description"]["en"],
        symbol=json_response["symbol"],
        homepage=json_response["links"]["homepage"][0],
        twitter_screen_name=json_response["links"]["twitter_screen_name"],
        price=json_response["market_data"]["current_price"]["usd"],
        ath=json_response["market_data"]["ath"]["usd"],
        price_change_24h=json_response["market_data"]["price_change_percentage_24h"],
        market_cap=json_response["market_data"]["market_cap"]["usd"],
        asset_platform_id=json_response["asset_platform_id"]
        if json_response.get("asset_platform_id")
        else "_Native to its own blockchain._",
    )

#### lunarcrush info
async def lunarcrush(symbol: str):
    URL = f"https://lunarcrush.com/api4/public/coins/{symbol}/time-series/v2"
    HEADERS = {"Authorization": "Bearer 10yzku3g0fh5ok48wvq65p1r7plt360axtmw7ec0z"}
    async with httpx.AsyncClient(http2=True) as client:
        response = await client.get(URL, headers=HEADERS)
    json = response.json()
    print(f"___lunarcrush_response___{json}")
    if "data" in json and len(json["data"]) > 0:
        if "sentiment" in json["data"][0]:
            mapped_sentiment = map_sentiment_to_literal(json["data"][0]["sentiment"])
        else:
            mapped_sentiment = "unknown"

        if "galaxy_score" in json["data"][0]:
            gscore = json["data"][0]["galaxy_score"]
        else:
            gscore = "unknown"
    else:
        mapped_sentiment = "unknown"
        gscore = "unknown"

    return LunarCrush(
        sentiment=mapped_sentiment,
        galaxy_score=gscore,
    )

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
async def dexscreener(token_contract_address: str) -> ProjectInfo | None:
    # catch if its a contract address
    URL = f"https://api.dexscreener.com/latest/dex/search/?q={token_contract_address}"
    async with httpx.AsyncClient(http2=True) as client:
        response = await client.get(URL)
    #    with open(f"{token_contract_address}_dexscreener.json", "w") as file:
    #        json.dump(response.json(), file, indent=4)
    # pics largest pool by volume
    jsonresp = get_largest_by_volume_24h(response.json())
    pprint(f"___largest_pool___: {jsonresp}")
    print("================= (all info local to this pool) =============")
    if jsonresp is None:
        print("=====No pairs found for the given token contract address.======")
        return None ###how to handle this correctly?
    print(
        jsonresp.get("baseToken", {}).get("symbol")
        + " / "
        + jsonresp.get("quoteToken", {}).get("symbol")
        + ". Volume: "
        + str(jsonresp.get("volume", {}).get("h24"))
        + " @ "
        + str(jsonresp.get("pairAddress"))
    )
    price=jsonresp.get("priceUsd")
    print(f"{price}")
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
        liquidity=jsonresp.get("liquidity").get("usd"), #
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
            "volume" in entry and "h24" in entry["volume"]
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
