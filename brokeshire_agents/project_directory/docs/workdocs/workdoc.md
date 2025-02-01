- # Steps
    0. Scrape daily entries going back to Dec 8 2022
      - TG Bot
    1. Preprocessing
      - Select only messages related to  
      - Cleanup (Move to separate "uncaught" files)
    2. Reduce down JSON to 
      
      Based on the provided database schema, identify the necessary JSON structures for each segment. For instance:

      - **News_Item**: For news entries under 📰News.
      - **Project**: For project updates and new projects.
      - **Content_Piece**: For threads/reads.
      - **Chain**: For any specific blockchain mentioned in launches or projects.

    3. Extract and Transform Data

        For each segment identified in Step 1, extract relevant information and transform it into the corresponding JSON structure. This involves:

        - **Parsing Text**: Use regular expressions or string manipulation techniques to extract information like names, links, and descriptions.
        - **Filling Properties**: Based on the extracted information, fill in the properties for each JSON structure as defined in the database schema.

        #### Example for a News_Item:

        ```json

        {

        "heading": "VanEck launches NFT marketplace and digital assets platform SegMint",

        "sentiment": "positive",

        "publication_date": "2023-02-28",

        "source_link": "https://twitter.com/TheBlock__/status/1762814990849876013",

        "news_source": "Twitter",

        "topic": "NFT Marketplace Launch",

        "category": "shills"

        }

        ```

    4. Create JSON Files

        - **One File per Entry**: You can create one JSON file for each type of entry (News, Project Update, Thread/Read, Launch, New Project) or one big JSON file that includes arrays of each type.
        - **Filename Convention**: Use a descriptive and consistent naming convention for the files, e.g., `news_items.json`, `project_updates.json`, etc.

    5. Validate JSON Structure

        - **Schema Validation**: Ensure that the created JSON files adhere to the schema provided in the database structure. Tools like JSON Schema Validator can be helpful.
        - **Correctness Checking**: Manually check a few entries to ensure that the information has been parsed and structured correctly.

    6. Finalization

        - **Review and Adjust**: Review the JSON files for any anomalies or errors and adjust as necessary.
        - **Documentation**: Document the process and structure of the JSON files for future reference or for use by other team mbrokeshires.
    7. Normalize dates
    8. Create Database [once]
    8a. Pre-load with network nodes
    9. Load data into db



    10. Create script for entire process
    11. Run script daily
- # Entry for Feb28
    - *February 28**

    Don't forget to follow my [Twitter](https://twitter.com/CJCJCJCJ_) and [C4's](https://twitter.com/C4dotgg). Here's what's happening today:

    📰News

    - [VanEck launches NFT marketplace and digital assets platform SegMint](https://twitter.com/TheBlock__/status/1762814990849876013)

    [Project Updates]
    - [@SenecaUSD has a critical exploit, revoke ASAP](https://twitter.com/spreekaway/status/1762857769714012217)
    - [@Arweave releases testnet for Arweave AO](https://www.theblock.co/post/279215/arweave-releases-testnet-for-absurdly-scalable-compute-layer-designed-for-social-media-ai)
    - [@LensProtocol now open for everyone](https://twitter.com/StaniKulechov/status/1762573665466486859)
    - [@TeamUnibot launches on Blast](https://twitter.com/UnibotOnBlast/status/1762584994369978450)
    - [@BinanceLabs invests in Babylon](https://www.theblock.co/post/279344/binance-labs-bitcoin-staking-protocol-babylon)
    - [@MaviaGame to build their L2 on Base](https://twitter.com/MaviaGame/status/1762492595404468436)

    [Threads/Reads]

    - [@ThanefieldRes thesis on Gnosis](https://twitter.com/ThanefieldRes/status/1762468229564305793)
    - [@wublockchain article about OEV](https://wublock.substack.com/p/api3-what-is-oev-oracle-extractable)
    - [@Shoalresearch 2024 watchlist shared](https://twitter.com/Shoalresearch/status/1762539464566677869)

    🚀Launches

    [fxUSD](https://twitter.com/protocol_fx/status/1762507404371996866) | [Live, Eth]

    [Website](http://fx.aladdin.club/)

    [Babylon Testnet](https://twitter.com/babylon_chain/status/1762824546854510914) | [Live, Babylon]

    [Website](http://babylonchain.io/)

    💎New Projects

    [Inferix](https://twitter.com/InferixGPU) | GPU Network

    [Website](http://dash.inferix.io/workers)

    [Vallista](https://twitter.com/callista) | Blast | Game Fi

    [Website](http://callista.world/)

    [Exabits](https://twitter.com/exa_bits) | Cloud

    [Website](http://exabits.ai/)

    - *My Links:**

    [GetGrass](https://app.getgrass.io/register?referralCode=kguLYPh4XSwTC7S) (ongoing points)

    [Shuffle](https://shuffle.com/?r=cjfromc4) (airdrop soon)

    [Mode Network](http://ref.mode.network/uEgYnH) (ongoing points)

    [Aevo](https://app.aevo.xyz/r/cjfromc4) (ongoing points)

    [Blast Signup Link](http://blast.io/1C0UP) (ongoing points)

    [Ethena Shard Campaign](http://app.ethena.fi/join/n71ph) (ongoing points, TGE in May)

    If you'd like to support me, donations can be sent to c4ggregator.eth or 0x051d615289c527d09efe581ccca4018011638733

--—
- # Database JSON Schema
{
  "nodes": {
    "Project": {
      "label": "Project",
      "properties": {
        "name": "String",
        "description": "String",
        "start_date": "Date (YYYY-MM-DD)",
        "symbol": "String"
        "website": "String"
        "twitter_handle": "String"
      }
    },
    "Social_Piece: {
      "label": "X_Thread",
      "properties": {
        "heading": "String", 
        "sentiment": "Enum (positive, negative)",
        "publication_date": "Date (YYYY-MM-DD)",
        "source_link": "URL",
        "author": "String",
        "topic": "String",
        "category": "Enum (shills, calls)"
      }
    },
    "News_Item": {
      "label": "News_Item",
      "properties": {
        "heading": "String",
        "sentiment": "Enum (positive, negative)",
        "publication_date": "Date (YYYY-MM-DD)",
        "source_link": "URL",
        "news_source": "String",
        "category": "Enum (security, business_deal, tech_update, project_birth)"
      }
    },
    "Chain": {
      "label": "Chain",
      "properties": {
        "name": "String"
        "token": "String"
      }
    }
  },
  "relationships": {
    "HAS_NEWS": {
      "from": "Project",
      "to": "News_Item"
    },
    "HAS_Mention": {
      "from": "Project",
      "to": "Social_Piece"
    },
    "IS_PARTNER": {
      "from": "Project",
      "to": "Project",
      "properties": {
        "type": "Enum (technical, strategic)"
      }
    },
    "NEXT_ITEM": {
      "from": "News_Item",
      "to": "News_Item",
      "properties": {
        "days_between": "Integer"
      }
    },
    "ON_CHAIN": {
      "from": "Project",
      "to": "Chain"
    }
  }
}
