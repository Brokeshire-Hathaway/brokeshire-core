from asyncio import Task

_background_tasks: set[Task] = set()


def delete_task(task: Task) -> None:
    """It adds a background task to avoid early garbage collection."""

    _background_tasks.discard(task)


def add_bg_task(task: Task) -> None:
    """It adds a background task to avoid early garbage collection."""

    _background_tasks.add(task)
    task.add_done_callback(delete_task)
