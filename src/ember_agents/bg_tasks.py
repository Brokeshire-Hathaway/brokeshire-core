from asyncio import Task

_background_tasks: set[Task] = set()


def add_bg_task(task: Task) -> None:
    """It adds a background task to avoid early garbage collection."""

    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
