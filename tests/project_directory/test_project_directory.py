from unittest import result
from numpy import full
import pytest
from src.ember_agents.project_directory.parse_c4_updates import parse_launches, parse_new_projects, parse_news_items, parse_project_updates, parse_threads_and_reads
from src.ember_agents.project_directory.run_workflow import run_all_things, run_workflow_live, run_workflow_saved
from update_samples import raw_update_full, raw_update_full_2, raw_update_full_3, raw_update_feb_19, raw_update_simple, headers_response








@pytest.mark.parametrize(
    "update_post",
    [
        # (raw_update_simple),
        # (raw_update_full),
        (raw_update_full_2),
    ],
)
@pytest.mark.skip()
async def test_parse_headers(update_post):
    headers = await parse_headers(update_post) # type: ignore
    print(f"headers:\n{headers}")
#validated

@pytest.mark.parametrize(
    "update_post",
    [
        (headers_response),
    ],
)
@pytest.mark.skip()
async def test_parse_news_items(update_post):
    resp = await parse_news_items(update_post)
    print(f"resp:\n{resp}")
#validated
    
@pytest.mark.parametrize(
    "update_post",
    [
        (headers_response),
    ],
)
@pytest.mark.skip()
async def test_project_updates(update_post):
    resp = await parse_project_updates(update_post)
    print(f"resp:\n{resp}")
#validated
    
@pytest.mark.parametrize(
    "update_post",
    [
        (headers_response),
    ],
)
@pytest.mark.skip()
async def test_parse_threads_and_reads(update_post):
    resp = await parse_threads_and_reads(update_post)
    print(f"resp:\n{resp}")
#validated

@pytest.mark.parametrize(
    "update_post",
    [
        (headers_response),
    ],
)
@pytest.mark.skip()
async def test_parse_launches(update_post):
    resp = await parse_launches(update_post)
    print(f"resp:\n{resp}")
#validated

@pytest.mark.parametrize(
    "update_post",
    [
        (headers_response),
    ],
)
@pytest.mark.skip()
async def test_parse_new_projects(update_post):
    resp = await parse_new_projects(update_post)
    print(f"resp:\n{resp}")
#validated

@pytest.mark.parametrize(
    "update_post",
    [
        (raw_update_full_2),
    ],
)
@pytest.mark.skip()
async def test_full_workflow_saved(update_post):
    data_frame = await run_workflow_saved(update_post)
    print(f"data_frame:\n{data_frame}")

@pytest.mark.parametrize(
    "update_post",
    [
        (raw_update_full_3),
    ],
)
@pytest.mark.skip()
async def test_full_workflow_live(update_post):
    data_frame = await run_workflow_live(update_post)
    print(f"data_frame:\n{data_frame}")


@pytest.mark.parametrize(
    "update",
    [
        (raw_update_feb_19),
    ],
    
)
#@pytest.mark.skip()
async def test_run_all_things(update):
    date= "**February 19**"
    print(f"============running test for {date}==================")
    result = await run_all_things(update, date)
    print("===================test complete========================")

