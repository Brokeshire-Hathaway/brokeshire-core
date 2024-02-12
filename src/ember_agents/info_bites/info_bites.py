import random

bites_list = [
    "The first-ever Bitcoin transaction was used to buy two pizzas for 10,000 BTC in 2010.",
    "The creator of Bitcoin, known as Satoshi Nakamoto, remains anonymous to this day.",
    "It's estimated that around 20% of all Bitcoins are lost forever, due to lost private keys, forgotten wallets, or the death of the wallet owner without sharing the keys.",
    "Ethereum, the second most popular cryptocurrency after Bitcoin, was proposed by Vitalik Buterin when he was just 19 years old.",
    "In 2017, Blockstream started broadcasting Bitcoin blockchain from space, allowing users without an internet connection to access the Bitcoin network.",
    "In 2017, the Ethereum-based game CryptoKitties became so popular that it congested the network.",
    "There will only ever be 21 million Bitcoins.",
    "DAOs are organizations that run on blockchain without any central authority.",
    "Researchers are exploring quantum-resistant blockchains.",
    "The Bitcoin network's energy consumption rivals that of some small countries.",
    "Companies like Walmart and IBM are using blockchain for food traceability.",
    "DeFi applications allow financial transactions, lending, and borrowing to occur without traditional banks.",
    "Several countries and organizations are experimenting with blockchain for secure and transparent voting systems.",
    "In 2016, the DAO on Ethereum was hacked, leading to a loss of over $50 million.",
    "May 22 is celebrated as Bitcoin Pizza Day.",
    'Although blockchain technology underpins Bitcoin, the term "blockchain" itself was never used in the original Bitcoin whitepaper.',
    "While Ethereum popularized smart contracts, the concept was first proposed by Nick Szabo in 1996.",
    "In March 2021, a digital artwork by Beeple sold for $69 million at Christie's.",
    "Blockchain is being explored for securely storing and sharing medical records.",
    "In 2013, a baby was born thanks to a fertility treatment that was paid for with Bitcoin.",
    "In the Americas, Bitcoin knowledge leans more towards men, whereas in EMEA and APAC regions, women are more likely to consider themselves Bitcoin experts.",
    "Over 230 million people owned Ethereum as of May 2023, marking an 18% increase from the previous year.",
    "The NFT market revenue reached $892 million worldwide in 2022 and is expected to hit $1.6 billion by the end of 2023.",
    "2024 sees the inevitable introduction of Central Bank Digital Currencies (CBDCs), offering benefits like efficiency, security, and cost-effectiveness. JP Morgan has pioneered programmable payments via its Onyx platform.",
    "The UK and EU announced plans for formal legislation to regulate crypto activities in 2024, aiming to ensure market integrity and financial stability.",
    "The SEC took significant legal actions against crypto asset securities' unregistered offer and sale in 2023, signaling tighter regulation but also approved the sale of spot bitcoin exchange-traded products in January 2024.",
    "Despite turmoil in the cryptocurrency sector, enterprises continue exploring blockchain for identity management, supply chains, and more.",
    "Monad's Testnet launch in Q1 2024, Celestia's modular blockchain approach, and LayerZero's solutions for cross-chain interoperability spotlight innovative blockchain projects to watch.",
    "Major companies like Tesla, Microsoft, and PayPal now accept cryptocurrencies, highlighting its growing acceptance and integration into various industries.",
    "Predictions for 2024 include Ethereum's continued growth with Layer 2 networks, a significant rebound in the NFT market, new Bitcoin yield opportunities through blockchain-based remittances, and the anticipated growth of Solana.",
]


def get_random_info_bite():
    return random.choice(bites_list)
