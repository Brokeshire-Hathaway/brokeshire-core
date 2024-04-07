from altair import URI
from neo4j import GraphDatabase
from dotenv import load_dotenv
import os

# Rest of your code
load_dotenv("/.env")

URI = os.getenv("URI")
AUTH = os.getenv("AUTH")

with GraphDatabase.driver(URI, auth=AUTH) as driver:
    driver.verify_connectivity()


def main():
    with GraphDatabase.driver(URI, auth=AUTH) as driver:
        with driver.session(database="neo4j") as session:
            for n in cypherdoc:
                session.run(n)
