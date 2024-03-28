import json
import os

from typing import List, Literal, Optional
from openai import AsyncOpenAI
from pydantic import BaseModel
from regex import R

client = AsyncOpenAI(
    # This is the default and can be omitted
    api_key=os.environ.get("OPENAI_API_KEY"),
)

openai_settings = {
    "model":"gpt-4-0125-preview",
    "response_format":{"type": "json_object"},
    "temperature": 0,
    "seed": 1
}

RelationshipType = Literal[
    "HAS_NEWS", "HAS_MENTION", "NEXT_ITEM", "IS_PARTNER", "ON_CHAIN"
]

class HeadersAndContents(BaseModel):
    date: str
    news: list[str]
    project_updates: list[str]
    launches: list[str]
    new_projects: list[str]
    threads_and_reads: list[str]


#### properties model for items
class NewsItem(BaseModel):
    name: str
    description: str
    sentiment: str
    publication_date: str
    source_link: str
    author: str
    category: str
    organization: List[str]

class ThreadsAndReads(BaseModel):
    name: str
    description: str
    publication_date: str
    source_link: str
    author: str
    category: str
    evergreen_score: float
    organization: list[str]

class Launch(BaseModel):
    name: str
    publication_date: str
    launch_time: str
    network: str
    source_link: str
    author: Optional[str]
    website: str
    category: str
    organization: list[str]

class Project(BaseModel):
    name: str
    publication_date: str
    launch_quarter: Optional[str] 
    description: Optional[str]
    symbol: Optional[str] 
    network: list[str]
    category: list[str]
    x_handle: str
    website: str
#### base model for nodes and relationships
class Node(BaseModel):
    label: str
    properties: NewsItem | ThreadsAndReads | Project

class Relationship(BaseModel):
    from_node: str
    to_node: str
    properties: RelationshipType


# - Scrape data (scrape.py)
# - Extract relevant messages from scraped (WIP pick_updates.py)
    
# - LLM extracts all detected headers (parse_headers)
    # - Contents deterministically split by headers and added to pydanitic data model 
    # - Ignore headers that are not whitelisted
# - Extra individual news items from header contents and save to pydanitic data model (parse_items)
    # - Use LLM to fill in extra context for each news item data model (parse_news_items)
# - Load knowledge graph with news item data model using query language

async def parse_headers(raw_post: str):
    system_message = """You are a content parser responsible for identifying ALL headers in a daily update and returning the content list in the following structured json format:
```json
{
    "date": "**January 23**",
    "news": [],
    "project_updates": ["- [@SenecaUSD has a critical exploit, revoke ASAP](https://twitter.com/spreekaway/status/1762857769714012217)", "- [@OndoFinance introduces Ondo Global Markets](https://twitter.com/OndoFinance/status/1763249939294163085)"],
    "threads_and_reads": ["- [@Binance MVB Season 7 cohort announced](https://www.bnbchain.org/en/blog/meet-the-most-valuable-builder-mvb-season-7-cohort)"],
    "launches": ["[fxUSD](https://twitter.com/protocol_fx/status/1762507404371996866) | [Live, Eth]\n[Website](http://fx.aladdin.club/)"],
    "new_projects": ["[Nettensor ](https://twitter.com/nettensor)| Bittensor, Ethereum | AI\n[Website](http://nettensor.com/)"],
}
```"""
    user_message = (
        f"Parse the headers into json from the following daily update:\n{raw_post}"
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
    response = response if response else ""
    print(f"response:\n{response}")
    headers_response = json.loads(response)
    data = HeadersAndContents(**headers_response)
    with open(
        f"src/ember_agents/project_directory/docs/cached_daily_updates/parsed_headers_response_{data.date}.json", "w"
)   as f:
        f.write(response)
        #will depricate once live is only version
    with open(
        "src/ember_agents/project_directory/docs/cached_daily_updates/parsed_headers_response.json", "w"
)   as f:
        f.write(response)
    return response
#validated

async def parse_news_items(expected_result): #pass it the result of prase_headers
#### loading stuff from file
    with open(
        "src/ember_agents/project_directory/docs/cached_daily_updates/parsed_headers_response.json", "r"
    ) as f:
        headers_response = f.read()

    headers_response = headers_response if headers_response else ""
    #print(f"response:\n{headers_response}")
    headers_response = json.loads(headers_response)
    data = HeadersAndContents(**headers_response)
    print(f"data.news:\n{data.news}")
#### loading stuff from file
    news = str(data.news)
    system_message = """You are a semantic content parser responsible for populating news items properties into the following structured json:
```json
{
    "parsed_news_items": [
        {
            "name": "RobinhoodPartnersArbitrum",
            "description": "Robinhood partners with @Arbitrum to offer cheap swaps for users",
            "sentiment": "positive",
            "publication_date": "20240301",
            "source_link": "https://twitter.com/News_Of_Alpha/status/1763272992069468385",
            "author": "News_Of_Alpha",
            "category": "partnership",
            "organization": ["Robinhood", "Arbitrum"]
        },
        {
            "name": "RedditIpoDao",
            "description": "Potential Reddit IPO DAO?",
            "sentiment": "neutral",
            "publication_date": "20240301",
            "source_link": "https://twitter.com/balajis/status/1763067849218850939",
            "author": "balajis",
            "category": "token_launch",
            "organization": ["RedditIpoDao"]
        },
        {
            "name": "WellsFargoBankOfAmericaOfferBTCETF",
            "description": "Wells Fargo & Bank of America's Merrill offering BTC ETF to clients",
            "sentiment": "positive",
            "publication_date": "20240301",
            "source_link": "https://twitter.com/WatcherGuru/status/1763265462887223740",
            "author": "WatcherGuru",
            "category": "update",
            "organization": ["WellsFargo", "BankOfAmerica", "Merrill"]
        },
    ]
}
```
# Additional Context
Publication Date: March 1
Categories: ["exploit", "partnership", "token_launch", "legal", "update"]
you must not add apostrophes "'" to any field."""
    user_message = (
        f"Parse the following news into json:\n{news}\nPublication Date: {data.date}"
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
    response = response if response else ""
    with open(f"src/ember_agents/project_directory/docs/cached_daily_updates/parsed_news_items_{data.date}.json", "w") as f:
        f.write(response)
    print(f"response:\n{response}")
    return response
#validated with mocked data

async def parse_project_updates(expected_result): #pass it the result of prase_headers
#### loading stuff from file
    with open(
        "src/ember_agents/project_directory/docs/cached_daily_updates/parsed_headers_response.json", "r"
    ) as f:
        headers_response = f.read()
    headers_response = headers_response if headers_response else ""
    #print(f"response:\n{headers_response}")
    headers_response = json.loads(headers_response)
    data = HeadersAndContents(**headers_response)
    print(f"data.project_updates:\n{data.project_updates}")
#### loading stuff from file
    project_updates = str(data.project_updates)
    system_message = """You are a semantic content parser responsible for populating news items properties into the following structured json:
```json
{
    "parsed_news_items": [
        {
            "name": "RobinhoodPartnersArbitrum",
            "description": "Robinhood partners with @Arbitrum to offer cheap swaps for users",
            "sentiment": "positive",
            "publication_date": "20240301",
            "source_link": "https://twitter.com/News_Of_Alpha/status/1763272992069468385",
            "author": "News_Of_Alpha",
            "category": "partnership",
            "organization": ["Robinhood", "Arbitrum"]
        },
        {
            "name": "RedditIpoDao",
            "description": "Potential Reddit IPO DAO?",
            "sentiment": "neutral",
            "publication_date": "20240301",
            "source_link": "https://twitter.com/balajis/status/1763067849218850939",
            "author": "balajis",
            "category": "token_launch",
            "organization": ["RedditIpoDao"]
        },
        {
            "name": "WellsFargoBankOfAmericaOfferBTCETF",
            "description": "Wells Fargo & Bank of America's Merrill offering BTC ETF to clients",
            "sentiment": "positive",
            "publication_date": "20240301",
            "source_link": "https://twitter.com/WatcherGuru/status/1763265462887223740",
            "author": "WatcherGuru",
            "category": "update",
            "organization": ["WellsFargo", "BankOfAmerica", "Merrill"]
        },
    ]
}
```
# Additional Context
Publication Date: March 1
Categories: ["exploit", "partnership", "token_launch", "legal", "update"]
you must not add apostrophes "'" to any field."""
    user_message = (
        f"Parse the following news into json:\n{project_updates}\nPublication Date: {data.date}"
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
    response = response if response else ""
    with open(f"src/ember_agents/project_directory/docs/cached_daily_updates/parsed_project_updates_{data.date}.json", "w") as f:
        f.write(response)
    print(f"response:\n{response}")
    return response
#validated with mocked data

async def parse_threads_and_reads(expected_result): #pass it the result of prase_headers
#### loading stuff from file
    with open(
        "src/ember_agents/project_directory/docs/cached_daily_updates/parsed_headers_response.json", "r"
    ) as f:
        headers_response = f.read()
    headers_response = headers_response if headers_response else ""
    #print(f"response:\n{headers_response}")
    headers_response = json.loads(headers_response)
    data = HeadersAndContents(**headers_response)
    print(f"data.threads_and_reads:\n{data.threads_and_reads}")
#### loading stuff from file
    threads_and_reads = str(data.threads_and_reads)
    system_message = """You are a semantic content parser responsible for populating educational content properties into the following structured json:
```json
{
    "parsed_threads_and_reads": [
        {
            "name": "NarrativesFromConvosEthDenver",
            "description": "Narratives from convos in ETH Denver by @shaaa256",
            "publication_date": "20240301",
            "source_link": "https://twitter.com/shaaa256/status/1764351507456217369",
            "author": "shaaa256",
            "category": "narrative",
            "evergreen_score": 0.8,
            "organization": ["EthDenver"]
        },
    ]
}
```
# Additional Context
Publication Date: March 1
Categories: ["tech", "narrative", "legal", "investing", "other"]
you must not add apostrophes "'" to any field.
- "name" should ALWAYS be PascalCase
- Newlines and escaped characters are not allowed in any field
- "organization" should be an array of strings, even if empty """

    user_message = f"Parse the following news into json:\n{threads_and_reads}\nPublication Date: {data.date}"
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
    response = response if response else ""
    with open(
        f"src/ember_agents/project_directory/docs/cached_daily_updates/parsed_threads_and_reads_items_{data.date}.json", "w"
    ) as f:
        f.write(response)
    print(f"response:\n{response}")
    return response
#validated with mocked data

async def parse_launches(expected_result): #pass it the result of prase_headers
#### loading stuff from file
    with open(
        "src/ember_agents/project_directory/docs/cached_daily_updates/parsed_headers_response.json", "r"
    ) as f:
        headers_response = f.read()
    headers_response = headers_response if headers_response else ""
    #print(f"response:\n{headers_response}")
    headers_response = json.loads(headers_response)
    data = HeadersAndContents(**headers_response)
    print(f"data.launches:\n{data.launches}")
#### loading stuff from file
    launches = str(data.launches)
    system_message = """You are a semantic content parser responsible for populating launch content properties into the following structured json:
```json
{
    "parsed_launches": [
        {
            "name": "HyChainNodeKeySale",
            "publication_date": "20240302",
            "launch_time": "T22:00:00",
            "network": "Ethereum",
            "source_link": "https://twitter.com/HYCHAIN_GAMES/status/1763630878868332888",
            "website": "http://nodes.hychain.com/",
            "author": "HYCHAIN_GAMES",
            "category": "other",
            "organization": ["HyChain"]
        },
        {
            "name": "GrandBaseMigration",
            "publication_date": "20240301",
            "launch_time": "Today",
            "network": "Base",
            "source_link": "https://twitter.com/grandbase_fi/status/1762567956058218652",
            "website": "",
            "author": "grandbase_fi",
            "category": "migration",
            "organization": ["GrandBaseFi"]
        },
        {
            "name": "MonaiTge",
            "publication_date": "20240301",
            "launch_time": "Live",
            "network": "Ethereum",
            "source_link": "https://twitter.com/monaidev",
            "website": "http://monai.dev/",
            "author": "monaidev",
            "category": "token",
            "organization": ["Monai"]
        }
    ]
}
```
# Instructions
- "name" should ALWAYS be PascalCase
# Additional Context
Publication Date: March 1
Categories: ["token", "farm", "nft", "app", "migration", "other"]
you must not add apostrophes "'" to any field."""
    user_message = f"Parse the following launches into json:\n{launches}\nPublication Date: {data.date}"
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
    response = response if response else ""
    with open(f"src/ember_agents/project_directory/docs/cached_daily_updates/parsed_launches_items_{data.date}.json", "w") as f:
        f.write(response)
    print(f"response:\n{response}")
    return response 
#validated with mocked data

async def parse_new_projects(expected_result): #pass it the result of prase_headers
#### loading stuff from file
    with open(
        "src/ember_agents/project_directory/docs/cached_daily_updates/parsed_headers_response.json", "r"
    ) as f:
        headers_response = f.read()
    headers_response = headers_response if headers_response else ""
    #print(f"response:\n{headers_response}")
    headers_response = json.loads(headers_response)
    data = HeadersAndContents(**headers_response)
    print(f"data.new_projects:\n{data.new_projects}")
#### loading stuff from file
    # NEW PROJECTS
    new_projects = str(data.new_projects)
    system_message = """You are a semantic content parser responsible for populating new project properties into the following structured json:
```json
{
    "parsed_new_projects": [
        {
            "name": "ChakraChain",
            "publication_date": "20240301",
            "launch_quarter": "Q12024",
            "network": ["Bitcoin"],
            "category": ["Restaking", "ZKP"],
            "x_handle": "ChakraChain",
            "website": "http://linktr.ee/ChakraChain",
            "symbol": "",
            "description": ""
        },
        {
            "name": "Ironclad",
            "publication_date": "20240301",
            "launch_quarter": "Q12024",
            "network": ["Mode"],
            "category": ["Money Market"],
            "x_handle": "IroncladFinance",
            "website": "http://ironclad.finance/",
            "symbol": "",
            "description": ""
        },
        {
            "name": "Nettensor",
            "publication_date": "20240301",
            "launch_quarter": "Q12024",
            "network": ["Bittensor", "Ethereum"],
            "category": ["AI"],
            "x_handle": "nettensor",
            "website": "http://nettensor.com/",
            "symbol": "",
            "description": ""
        }
    ]
}
```
# Instructions
- "name" should ALWAYS be PascalCase
you must not add apostrophes "'" to any field.
# Additional Context
Publication Date: March 1"""
    user_message = f"Parse the following new projects into json:\n{new_projects}\nPublication Date: {data.date}"
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
    response = response if response else ""
    with open(
        f"src/ember_agents/project_directory/docs/cached_daily_updates/parsed_new_projects_items_{data.date}.json", "w"
    ) as f:
        f.write(response)
#validated with mocked data


#################
### these are the live versions of the functions plugged to passed data and not loading 
#############################


async def parse_news_items_live(expected_result): #pass it the result of prase_headers
    headers_response = expected_result
    headers_response = headers_response if headers_response else ""
    #print(f"response:\n{headers_response}")
    headers_response = json.loads(headers_response)
    data = HeadersAndContents(**headers_response)
    print(f"data.news:\n{data.news}")
#### loading stuff from file
    news = str(data.news)
    system_message = """You are a semantic content parser responsible for populating news items properties into the following structured json:
```json
{
    "parsed_news_items": [
        {
            "name": "RobinhoodPartnersArbitrum",
            "description": "Robinhood partners with @Arbitrum to offer cheap swaps for users",
            "sentiment": "positive",
            "publication_date": "20240301",
            "source_link": "https://twitter.com/News_Of_Alpha/status/1763272992069468385",
            "author": "News_Of_Alpha",
            "category": "partnership",
            "organization": ["Robinhood", "Arbitrum"]
        },
        {
            "name": "RedditIpoDao",
            "description": "Potential Reddit IPO DAO?",
            "sentiment": "neutral",
            "publication_date": "20240301",
            "source_link": "https://twitter.com/balajis/status/1763067849218850939",
            "author": "balajis",
            "category": "token_launch",
            "organization": ["RedditIpoDao"]
        },
        {
            "name": "WellsFargoBankOfAmericaOfferBTCETF",
            "description": "Wells Fargo & Bank of America's Merrill offering BTC ETF to clients",
            "sentiment": "positive",
            "publication_date": "20240301",
            "source_link": "https://twitter.com/WatcherGuru/status/1763265462887223740",
            "author": "WatcherGuru",
            "category": "update",
            "organization": ["WellsFargo", "BankOfAmerica", "Merrill"]
        },
    ]
}
```
# Additional Context
Publication Date: March 1
Categories: ["exploit", "partnership", "token_launch", "legal", "update"]
you must not add apostrophes "'" to any field."""
    user_message = (
        f"Parse the following news into json:\n{news}\nPublication Date: {data.date}"
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
    response = response if response else ""
    with open(f"src/ember_agents/project_directory/docs/cached_daily_updates/parsed_news_items_{data.date}.json", "w") as f:
        f.write(response)
    print(f"response:\n{response}")
    return response


async def parse_project_updates_live(expected_result): #pass it the result of prase_headers
    headers_response = expected_result
    headers_response = headers_response if headers_response else ""
    #print(f"response:\n{headers_response}")
    headers_response = json.loads(headers_response)
    data = HeadersAndContents(**headers_response)
    print(f"data.project_updates:\n{data.project_updates}")
#### loading stuff from file
    project_updates = str(data.project_updates)
    system_message = """You are a semantic content parser responsible for populating news items properties into the following structured json:
```json
{
    "parsed_news_items": [
        {
            "name": "RobinhoodPartnersArbitrum",
            "description": "Robinhood partners with @Arbitrum to offer cheap swaps for users",
            "sentiment": "positive",
            "publication_date": "20240301",
            "source_link": "https://twitter.com/News_Of_Alpha/status/1763272992069468385",
            "author": "News_Of_Alpha",
            "category": "partnership",
            "organization": ["Robinhood", "Arbitrum"]
        },
        {
            "name": "RedditIpoDao",
            "description": "Potential Reddit IPO DAO?",
            "sentiment": "neutral",
            "publication_date": "20240301",
            "source_link": "https://twitter.com/balajis/status/1763067849218850939",
            "author": "balajis",
            "category": "token_launch",
            "organization": ["RedditIpoDao"]
        },
        {
            "name": "WellsFargoBankOfAmericaOfferBTCETF",
            "description": "Wells Fargo & Bank of America's Merrill offering BTC ETF to clients",
            "sentiment": "positive",
            "publication_date": "20240301",
            "source_link": "https://twitter.com/WatcherGuru/status/1763265462887223740",
            "author": "WatcherGuru",
            "category": "update",
            "organization": ["WellsFargo", "BankOfAmerica", "Merrill"]
        },
    ]
}
```
# Additional Context
Publication Date: March 1
Categories: ["exploit", "partnership", "token_launch", "legal", "update"]
you must not add apostrophes "'" to any field."""
    user_message = (
        f"Parse the following news into json:\n{project_updates}\nPublication Date: {data.date}"
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
    response = response if response else ""
    with open(f"src/ember_agents/project_directory/docs/cached_daily_updates/parsed_project_updates_{data.date}.json", "w") as f:
        f.write(response)
    print(f"response:\n{response}")
    return response


async def parse_threads_and_reads_live(expected_result): #pass it the result of prase_headers
    headers_response = expected_result
    headers_response = headers_response if headers_response else ""
    #print(f"response:\n{headers_response}")
    headers_response = json.loads(headers_response)
    data = HeadersAndContents(**headers_response)
    print(f"data.threads_and_reads:\n{data.threads_and_reads}")
#### loading stuff from file
    threads_and_reads = str(data.threads_and_reads)
    system_message = """You are a semantic content parser responsible for populating educational content properties into the following structured json:
```json
{
    "parsed_threads_and_reads": [
        {
            "name": "NarrativesFromConvosEthDenver",
            "description": "Narratives from convos in ETH Denver by @shaaa256",
            "publication_date": "20240301",
            "source_link": "https://twitter.com/shaaa256/status/1764351507456217369",
            "author": "shaaa256",
            "category": "narrative",
            "evergreen_score": 0.8,
            "organization": ["EthDenver"]
        },
    ]
}
```
# Additional Context
Publication Date: March 1
Categories: ["tech", "narrative", "legal", "investing", "other"]
you must not add apostrophes "'" to any field.
- "name" should ALWAYS be PascalCase
- Newlines and escaped characters are not allowed in any field
- "organization" should be an array of strings, even if empty"""

    user_message = f"Parse the following news into json:\n{threads_and_reads}\nPublication Date: {data.date}"
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
    response = response if response else ""
    with open(
        f"src/ember_agents/project_directory/docs/cached_daily_updates/parsed_threads_and_reads_items_{data.date}.json", "w"
    ) as f:
        f.write(response)
    print(f"response:\n{response}")
    return response


async def parse_launches_live(expected_result): #pass it the result of prase_headers
    headers_response = expected_result
    headers_response = headers_response if headers_response else ""
    #print(f"response:\n{headers_response}")
    headers_response = json.loads(headers_response)
    data = HeadersAndContents(**headers_response)
    print(f"data.launches:\n{data.launches}")
#### loading stuff from file
    launches = str(data.launches)
    system_message = """You are a semantic content parser responsible for populating launch content properties into the following structured json:
```json
{
    "parsed_launches": [
        {
            "name": "GearboxProtocol",
            "publication_date": "20240301",
            "launch_time": "Live",
            "network": "Arbitrum",
            "source_link": "https://twitter.com/GearboxProtocol/status/1764197536124866619",
            "website": "http://app.gearbox.fi/",
            "author": "GearboxProtocol",
            "category": "app",
            "organization": ["GearboxProtocol"]
        },
        {
            "name": "GrandBaseMigration",
            "publication_date": "20240301",
            "launch_time": "Today",
            "network": "Base",
            "source_link": "https://twitter.com/grandbase_fi/status/1762567956058218652",
            "website": "",
            "author": "grandbase_fi",
            "category": "migration",
            "organization": ["GrandBaseFi"]
        },
        {
            "name": "MonaiTge",
            "publication_date": "20240301",
            "launch_time": "Live",
            "network": "Ethereum",
            "source_link": "https://twitter.com/monaidev",
            "website": "http://monai.dev/",
            "author": "monaidev",
            "category": "token",
            "organization": ["Monai"]
        },
    ]
}
```
# Instructions
- "name" should ALWAYS be PascalCase
# Additional Context
Publication Date: March 1
Categories: ["token", "farm", "nft", "app", "migration", "other"]
you must not add apostrophes "'" to any field."""
    user_message = f"Parse the following launches into json:\n{launches}\nPublication Date: {data.date}"
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
    response = response if response else ""
    with open(f"src/ember_agents/project_directory/docs/cached_daily_updates/parsed_launches_items_{data.date}.json", "w") as f:
        f.write(response)
    print(f"response:\n{response}")
    return response 


async def parse_new_projects_live(expected_result): #pass it the result of prase_headers
    headers_response = expected_result
    headers_response = headers_response if headers_response else ""
    #print(f"response:\n{headers_response}")
    headers_response = json.loads(headers_response)
    data = HeadersAndContents(**headers_response)
    print(f"data.new_projects:\n{data.new_projects}")
#### loading stuff from file
    # NEW PROJECTS
    new_projects = str(data.new_projects)
    system_message = """You are a semantic content parser responsible for populating new project properties into the following structured json:
```json
{
    "parsed_new_projects": [
        {
            "name": "ChakraChain",
            "publication_date": "20240301",
            "launch_quarter": "Q12024",
            "network": ["Bitcoin"],
            "category": ["Restaking", "ZKP"],
            "x_handle": "ChakraChain",
            "website": "http://linktr.ee/ChakraChain",
            "symbol": "",
            "description": ""
        },
        {
            "name": "Ironclad",
            "publication_date": "20240301",
            "launch_quarter": "Q12024",
            "network": ["Mode"],
            "category": ["Money Market"],
            "x_handle": "IroncladFinance",
            "website": "http://ironclad.finance/",
            "symbol": "",
            "description": ""
        },
        {
            "name": "Nettensor",
            "publication_date": "20240301",
            "launch_quarter": "Q12024",
            "network": ["Bittensor", "Ethereum"],
            "category": ["AI"],
            "x_handle": "nettensor",
            "website": "http://nettensor.com/",
            "symbol": "",
            "description": ""
        }
    ]
}
```
# Instructions
- "name" should ALWAYS be PascalCase
# Additional Context
Publication Date: March 1"""
    user_message = f"Parse the following new projects into json:\n{new_projects}\nPublication Date: {data.date}"
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
    response = response if response else ""
    with open(
        f"src/ember_agents/project_directory/docs/cached_daily_updates/parsed_new_projects_items_{data.date}.json", "w"
    ) as f:
        f.write(response)


