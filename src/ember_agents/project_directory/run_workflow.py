from ember_agents.project_directory.parse_c4_updates import (
    parse_headers,
    parse_new_projects,
    parse_threads_and_reads_live,
    parse_launches_live,
    parse_new_projects_live,
    parse_news_items_live,
    parse_project_updates_live,
)
from ember_agents.project_directory.cypher_conversion import (
    main_news_items,
    main_new_projects,
    main_project_updates,
    main_threads_and_reads,
    main_launches,
)

### functions here as defined to load data from a file


async def run_workflow_saved(daily_update):
    print(f"=====CURRENTLY running workflow; parse headers (aprox 70s)")
    with open(
        f"src/ember_agents/project_directory/docs/cached_daily_updates/parsed_headers_response.json",
        "r",
    ) as f:
        data = f.read()
    #  data = await parse_headers(daily_update)
    print(f"=====CURRENTLY running workflow; parse news (aprox 30s)")
    #  news = await parse_news_items(data)
    print(f"=====CURRENTLY running workflow; parse project updates (aprox 30s)")
    #  project_updates = await parse_project_updates(data)
    print(f"=====CURRENTLY running workflow; parse educational content (aprox 30s)")
    #  threads_and_reads = await parse_threads_and_reads(data)
    print(f"=====CURRENTLY running workflow; parse launches (aprox 30s)")
    #  launches = await parse_launches(data)
    print(f"=====CURRENTLY running workflow; parse new projects (aprox 30s)")
    new_projects = await parse_new_projects(data)
    return "yay"


### functions here as defined to load data from what is passed (daily_update)
#### level 1 of llm calls


async def run_workflow_live(daily_update):
    print(f"=====CURRENTLY running workflow; parse headers (aprox 70s)")
    data = await parse_headers(daily_update)

    #### level 2 of llm calls
    print(f"=====CURRENTLY running workflow; parse news (aprox 30s)")
    news = await parse_news_items_live(data)
    print(f"=====CURRENTLY running workflow; parse project updates (aprox 30s)")
    project_updates = await parse_project_updates_live(data)
    print(f"=====CURRENTLY running workflow; parse educational content (aprox 30s)")
    threads_and_reads = await parse_threads_and_reads_live(data)
    print(f"=====CURRENTLY running workflow; parse launches (aprox 30s)")
    launches = await parse_launches_live(data)
    print(f"=====CURRENTLY running workflow; parse new projects (aprox 30s)")
    new_projects = await parse_new_projects_live(data)
    return f"======= parsing workflow complete ======== for {data}"


####
### tests the conversion to cypher queries from file
############
def run_conversion(date):
    print(f"=====CURRENTLY running conversion======")
    all_queries = ""
    with open(
        f"src/ember_agents/project_directory/docs/cached_daily_updates/parsed_news_items_{date}.json",
        "r",
    ) as f:
        data = f.read()
        news_queries = main_news_items(data)
        all_queries += "\n".join(news_queries)
    print(f"=====CURRENTLY running conversion; news_queries: {news_queries}")
    with open(
        f"src/ember_agents/project_directory/docs/cached_daily_updates/parsed_project_updates_{date}.json",
        "r",
    ) as f:
        data = f.read()
        project_updates_queries = main_project_updates(data)
        print("@@@@@@@@@@@@@@@@")
        print(data)
        all_queries += "\n".join(project_updates_queries)
    print(
        f"=====CURRENTLY running conversion; project_updates_queries: {project_updates_queries}"
    )
    with open(
        f"src/ember_agents/project_directory/docs/cached_daily_updates/parsed_threads_and_reads_items_{date}.json",
        "r",
    ) as f:
        data = f.read()
        threads_and_reads_queries = main_threads_and_reads(data)
        all_queries += "\n".join(threads_and_reads_queries)
    print(
        f"=====CURRENTLY running conversion; threads_and_reads_queries: {threads_and_reads_queries}"
    )
    with open(
        f"src/ember_agents/project_directory/docs/cached_daily_updates/parsed_launches_items_{date}.json",
        "r",
    ) as f:
        data = f.read()
        launches_queries = main_launches(data)
        all_queries += "\n".join(launches_queries)
    print(f"=====CURRENTLY running conversion; launches_queries: {launches_queries}")
    with open(
        f"src/ember_agents/project_directory/docs/cached_daily_updates/parsed_new_projects_items_{date}.json",
        "r",
    ) as f:
        data = f.read()
        new_project_queries = main_new_projects(data)
        all_queries += "\n".join(new_project_queries)
    print(
        f"=====CURRENTLY running conversion; new_project_queries: {new_project_queries}"
    )
    with open(
        f"src/ember_agents/project_directory/docs/populate_database/cypher_scripts/all_queries_{date}.txt",
        "w",
    ) as f:
        f.write(all_queries)
    return f"======= conversion complete ======== for {date}"


async def run_all_things(update_post, date: str):
    result_from_parsing = await run_workflow_live(update_post)
    result_from_queries = run_conversion(date)
    return "\nyay"


# flag system for reading off of file
# console logging
#
