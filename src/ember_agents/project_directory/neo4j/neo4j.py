import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

# Rest of your code
load_dotenv("/.env")

uri = os.getenv("URI")
AUTH = os.getenv("AUTH")

with GraphDatabase.driver(uri, auth=AUTH) as driver:
    driver.verify_connectivity()


def main():
    with GraphDatabase.driver(uri, auth=AUTH) as driver:
        with driver.session(database="neo4j") as session:
            for n in cypherdoc:
                session.run(n)
