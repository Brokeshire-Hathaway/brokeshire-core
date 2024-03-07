from typing import List, Optional
import re
from pydantic import BaseModel
import json

from src.ember_agents.project_directory.parse_c4_updates import Launch, NewsItem, Project, ThreadsAndReads



#### news items
def generate_news_item_query(news_item: NewsItem):
    query = f"""
        MERGE (n:NewsItem {{
            name: '{news_item.name}',
            description: '{news_item.description}',
            sentiment: '{news_item.sentiment}',
            publication_date: date('{news_item.publication_date}'),
            source_link: '{news_item.source_link}',
            author: '{news_item.author}',
            category: '{news_item.category}'
        }})
        WITH n as newsItem
        UNWIND {news_item.organization} AS org
        MERGE (o:Project {{ name: org }})
        MERGE (o)-[:HAS_NEWS]->(newsItem)
    """.strip()
    return query

def news_to_cypher(parsed_news_items: List[dict]) -> List[str]:
    list_of_news = [NewsItem(**news) for news in parsed_news_items]
    queries = [generate_news_item_query(n) for n in list_of_news]
    return queries

def main_news_items(json_data):
    data = json.loads(json_data)
    parsed_news_items = data.get('parsed_news_items', [])
    queries = news_to_cypher(parsed_news_items)
    print("\n".join(queries))
    return queries

### project updates
def generate_project_updates_query(project_updates: NewsItem):
    query = f"""
        MERGE (n:NewsItem {{
            name: '{project_updates.name}',
            description: '{project_updates.description}',
            sentiment: '{project_updates.sentiment}',
            publication_date: date('{project_updates.publication_date}'),
            source_link: '{project_updates.source_link}',
            author: '{project_updates.author}',
            category: '{project_updates.category}'
        }})
        WITH n as newsItem
        UNWIND {project_updates.organization} AS org
        MERGE (o:Project {{ name: org }})
        MERGE (o)-[:HAS_NEWS]->(newsItem)
    """.strip()
    return query

def project_updates_to_cypher(parsed_project_updates: List[dict]) -> List[str]:
    list_of_news = [NewsItem(**project_update) for project_update in parsed_project_updates]
    queries = [generate_project_updates_query(n) for n in list_of_news]
    return queries

def main_project_updates(json_data):
    data = json.loads(json_data)
    print(f"json_data: {json_data}")
    parsed_project_updates = data.get('parsed_news_items', [])
    print(f"parsed_project_updates: {parsed_project_updates}")
    queries = news_to_cypher(parsed_project_updates)
    print("\n".join(queries))
    return queries

#### educational content
def generate_threads_and_reads_query(threads_and_reads: ThreadsAndReads):
    query = f"""
        MERGE (e:EducationalContent {{
            name: '{threads_and_reads.name}',
            description: '{threads_and_reads.description}',
            publication_date: date('{threads_and_reads.publication_date}'),
            source_link: '{threads_and_reads.source_link}',
            author: '{threads_and_reads.author}',
            category: '{threads_and_reads.category}',
            evergreen_score: {threads_and_reads.evergreen_score}
        }})
        WITH e as EducationalContent
        FOREACH (org IN {threads_and_reads.organization} |
            FOREACH (ignoreMe IN CASE WHEN org <> '' THEN [1] ELSE [] END |
                MERGE (o:Project {{ name: org }})
                MERGE (o)-[:HAS_EDUCATIONAL_CONTENT]->(EducationalContent)
            )
        )
    """.strip()
    return query

def threads_and_reads_to_cypher(parsed_threads_and_reads: List[dict]) -> List[str]:
    list_of_threads_and_reads = [ThreadsAndReads(**educational) for educational in parsed_threads_and_reads]
    queries = [generate_threads_and_reads_query(n) for n in list_of_threads_and_reads]
    return queries

def main_threads_and_reads(json_data):
    data = json.loads(json_data)
    parsed_threads_and_reads = data.get('parsed_threads_and_reads', [])
    queries = threads_and_reads_to_cypher(parsed_threads_and_reads)
    print("\n".join(queries))
    return queries


#### launches
def generate_launches_query(launch: Launch):
    launch_time = launch.launch_time
    if not re.match(r"T\d{2}:\d{2}:\d{2}", launch_time):
        launch_time = f"'{launch_time}'"
    else:
        launch_time = f"'T{launch_time}'"
    
    query = f"""
        MERGE (l:Launch {{
            name: '{launch.name}',
            launch_date: date('{launch.publication_date}'),
            launch_time: {launch_time},
            network: '{launch.network}',
            source_link: '{launch.source_link}',
            author: '{launch.author}',
            website: '{launch.website}',
            category: '{launch.category}'
        }})
        WITH l as Launch
        FOREACH (org IN {launch.organization} |
            FOREACH (ignoreMe IN CASE WHEN org <> '' THEN [1] ELSE [] END |
                MERGE (o:Project {{ name: org }})
                MERGE (o)-[:HAS_LAUNCH]->(Launch)
            )
        )
    """.strip()
    return query

def launches_to_cypher(parsed_launches: List[dict]) -> List[str]:
    list_of_launches = [Launch(**launch) for launch in parsed_launches]
    queries = [generate_launches_query(n) for n in list_of_launches]
    return queries

def main_launches(json_data):
    data = json.loads(json_data)
    parsed_launches = data.get('parsed_launches', [])
    queries = launches_to_cypher(parsed_launches)
    print("\n".join(queries))
    return queries

#### new projects
def generate_new_projects_query(new_project: Project):
    network_str = ', '.join([f"'{net}'" for net in new_project.network])
    category_str = ', '.join([f"'{cat}'" for cat in new_project.category])
    query = f"""
        MERGE ({new_project.name}:Project {{
            name: '{new_project.name}',
            publication_date: '{new_project.publication_date}',
            launch_quarter: '{new_project.launch_quarter}',
            network: [{network_str}],
            category: [{category_str}],
            x_handle: '{new_project.x_handle}',
            website: '{new_project.website}'
        }})
    """.strip()
    return query

def new_projects_to_cypher(parsed_new_projects: List[dict]) -> List[str]:
    list_of_new_projects = [Project(**project) for project in parsed_new_projects]
    queries = [generate_new_projects_query(n) for n in list_of_new_projects]
    return queries

def main_new_projects(json_data):
    data = json.loads(json_data)
    parsed_new_projects = data.get('parsed_new_projects', [])
    queries = new_projects_to_cypher(parsed_new_projects)
    print("\n".join(queries))
    return queries