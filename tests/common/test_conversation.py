import json
from typing import Literal
import pytest
from ember_agents.common.conversation import (
    Conversation,
    conversation_reducer,
    create_context_message,
    create_contexts_update,
    get_context,
)
from rich import print


@pytest.mark.parametrize(
    "sender, content, participant, expected",
    [
        (
            "user",
            "Hello",
            "assistant",
            {
                "role": "user",
                "content": "<sender_name>user</sender_name>\n<message>Hello</message>",
            },
        ),
        (
            "assistant",
            "Hi",
            "user",
            {
                "role": "assistant",
                "content": "<sender_name>assistant</sender_name>\n<message>Hi</message>",
            },
        ),
        (
            "assistant1",
            "Hello",
            "assistant2",
            {
                "role": "user",
                "content": "<sender_name>assistant1</sender_name>\n<message>Hello</message>",
            },
        ),
    ],
)
@pytest.mark.skip
def test_create_context_message(sender, content, participant, expected):
    assert create_context_message(sender, content, participant) == expected


@pytest.mark.parametrize(
    "new_message, participants, expected",
    [
        (
            {"sender_name": "user", "content": "Hello", "is_visible_to_user": True},
            ["assistant", "user"],
            {
                "assistant": [
                    {
                        "role": "user",
                        "content": "<sender_name>user</sender_name>\n<message>Hello</message>",
                    }
                ],
                "user": [
                    {
                        "role": "user",
                        "content": "<sender_name>user</sender_name>\n<message>Hello</message>",
                    }
                ],
            },
        ),
        (
            {
                "sender_name": "assistant1",
                "content": "Internal message",
                "is_visible_to_user": False,
            },
            ["assistant1", "assistant2", "user"],
            {
                "assistant1": [
                    {
                        "role": "assistant",
                        "content": "<sender_name>assistant1</sender_name>\n<message>Internal message</message>",
                    }
                ],
                "assistant2": [
                    {
                        "role": "user",
                        "content": "<sender_name>assistant1</sender_name>\n<message>Internal message</message>",
                    }
                ],
            },
        ),
    ],
)
@pytest.mark.skip
def test_create_contexts_update(new_message, participants, expected):
    assert create_contexts_update(new_message, participants) == expected


@pytest.mark.skip
def test_get_context():
    conversation: Conversation = {
        "history": [
            {"sender_name": "user", "content": "Hello", "is_visible_to_user": True},
            {
                "sender_name": "assistant",
                "content": "Hi there",
                "is_visible_to_user": True,
            },
        ],
        "contexts": {
            "user": [
                {
                    "role": "user",
                    "content": "<sender_name>user</sender_name>\n<message>Hello</message>",
                },
                {
                    "role": "assistant",
                    "content": "<sender_name>assistant</sender_name>\n<message>Hi there</message>",
                },
            ],
            "assistant": [
                {
                    "role": "user",
                    "content": "<sender_name>user</sender_name>\n<message>Hello</message>",
                },
                {
                    "role": "assistant",
                    "content": "<sender_name>assistant</sender_name>\n<message>Hi there</message>",
                },
            ],
        },
        "participants": ["user", "assistant"],
    }

    assert get_context(conversation, "user") == [
        {
            "role": "user",
            "content": "<sender_name>user</sender_name>\n<message>Hello</message>",
        },
        {
            "role": "assistant",
            "content": "<sender_name>assistant</sender_name>\n<message>Hi there</message>",
        },
    ]

    assert get_context(conversation, "assistant") == [
        {
            "role": "user",
            "content": "<sender_name>user</sender_name>\n<message>Hello</message>",
        },
        {
            "role": "assistant",
            "content": "<sender_name>assistant</sender_name>\n<message>Hi there</message>",
        },
    ]

    # Test non-existent participant
    assert get_context(conversation, "nonexistent") == []


@pytest.mark.parametrize(
    "conversation, participant, expected",
    [
        ({"history": [], "contexts": {}, "participants": []}, "any", []),
        (
            {
                "history": [
                    {
                        "sender_name": "user",
                        "content": "First message",
                        "is_visible_to_user": True,
                    }
                ],
                "contexts": {
                    "assistant": [
                        {
                            "role": "user",
                            "content": "<sender_name>user</sender_name>\n<message>First message</message>",
                        }
                    ]
                },
                "participants": ["user", "assistant"],
            },
            "assistant",
            [
                {
                    "role": "user",
                    "content": "<sender_name>user</sender_name>\n<message>First message</message>",
                }
            ],
        ),
    ],
)
@pytest.mark.skip
def test_empty_and_single_message_conversation(conversation, participant, expected):
    assert get_context(conversation, participant) == expected


@pytest.fixture
def initial_conversation():
    return {
        "history": [
            {
                "sender_name": "user",
                "content": "First message",
                "is_visible_to_user": True,
            }
        ],
        "contexts": {
            "user": [
                {
                    "role": "user",
                    "content": "<sender_name>user</sender_name>\n<message>First message</message>",
                }
            ],
            "assistant": [
                {
                    "role": "user",
                    "content": "<sender_name>user</sender_name>\n<message>First message</message>",
                }
            ],
            "agent": [
                {
                    "role": "user",
                    "content": "<sender_name>user</sender_name>\n<message>First message</message>",
                }
            ],
        },
        "participants": ["user", "assistant", "agent"],
    }


@pytest.mark.parametrize(
    "new_message, expected_changes",
    [
        (
            {
                "sender_name": "assistant",
                "content": "Second message",
                "is_visible_to_user": True,
            },
            {
                "history_addition": {
                    "sender_name": "assistant",
                    "content": "Second message",
                    "is_visible_to_user": True,
                },
                "context_additions": {
                    "user": {
                        "role": "assistant",
                        "content": "<sender_name>assistant</sender_name>\n<message>Second message</message>",
                    },
                    "assistant": {
                        "role": "assistant",
                        "content": "<sender_name>assistant</sender_name>\n<message>Second message</message>",
                    },
                    "agent": {
                        "role": "user",
                        "content": "<sender_name>assistant</sender_name>\n<message>Second message</message>",
                    },
                },
            },
        ),
        (
            {
                "sender_name": "agent",
                "content": "Internal message",
                "is_visible_to_user": False,
            },
            {
                "history_addition": {
                    "sender_name": "agent",
                    "content": "Internal message",
                    "is_visible_to_user": False,
                },
                "context_additions": {
                    "assistant": {
                        "role": "user",
                        "content": "<sender_name>agent</sender_name>\n<message>Internal message</message>",
                    },
                    "agent": {
                        "role": "assistant",
                        "content": "<sender_name>agent</sender_name>\n<message>Internal message</message>",
                    },
                    # Note: No context addition for "user" due to is_visible_to_user being False
                },
            },
        ),
    ],
)
@pytest.mark.skip
def test_conversation_reducer(initial_conversation, new_message, expected_changes):
    new_conversation = {
        "history": [new_message],
    }
    updated_conversation = conversation_reducer(initial_conversation, new_conversation)

    # Check history
    assert updated_conversation["history"][-1] == expected_changes["history_addition"]

    # Check contexts for all participants
    for participant in initial_conversation["participants"]:
        if participant in expected_changes["context_additions"]:
            assert (
                updated_conversation["contexts"][participant][-1]
                == expected_changes["context_additions"][participant]
            )
        else:
            # If no context addition is expected for this participant, ensure the context didn't change
            assert len(updated_conversation["contexts"][participant]) == len(
                initial_conversation["contexts"][participant]
            )

    # Check participants (shouldn't change)
    assert updated_conversation["participants"] == initial_conversation["participants"]
