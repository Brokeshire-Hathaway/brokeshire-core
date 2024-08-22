import pytest
from ember_agents.common.conversation import (
    Message,
    ContextMessage,
    Conversation,
    create_context_message,
    create_conversation_update,
    get_context,
)


@pytest.mark.parametrize(
    "sender, content, participant, expected",
    [
        ("User", "Hello", "Assistant", {"role": "user", "content": "User: Hello"}),
        ("Assistant", "Hi", "User", {"role": "assistant", "content": "Assistant: Hi"}),
        (
            "Assistant1",
            "Hello",
            "Assistant2",
            {"role": "user", "content": "Assistant1: Hello"},
        ),
    ],
)
def test_create_context_message(sender, content, participant, expected):
    assert create_context_message(sender, content, participant) == expected


@pytest.mark.parametrize(
    "sender, content, participants, is_visible_to_user, expected",
    [
        (
            "User",
            "Hello",
            ["Assistant"],
            True,
            {
                "history": [{"sender": "User", "content": "Hello"}],
                "contexts": {"Assistant": [{"role": "user", "content": "User: Hello"}]},
            },
        ),
        (
            "Assistant1",
            "Internal message",
            ["Assistant2", "User"],
            False,
            {
                "history": [{"sender": "Assistant1", "content": "Internal message"}],
                "contexts": {
                    "Assistant2": [
                        {"role": "user", "content": "Assistant1: Internal message"}
                    ]
                },
            },
        ),
        (
            "User",
            "Hello everyone",
            ["Assistant1", "Assistant2", "User"],
            True,
            {
                "history": [{"sender": "User", "content": "Hello everyone"}],
                "contexts": {
                    "Assistant1": [{"role": "user", "content": "User: Hello everyone"}],
                    "Assistant2": [{"role": "user", "content": "User: Hello everyone"}],
                    "User": [{"role": "user", "content": "User: Hello everyone"}],
                },
            },
        ),
    ],
)
def test_create_conversation_update(
    sender, content, participants, is_visible_to_user, expected
):
    assert (
        create_conversation_update(
            sender, content, participants, is_visible_to_user=is_visible_to_user
        )
        == expected
    )


# @pytest.mark.skip
def test_get_context():
    conversation: Conversation = {
        "history": [
            {"sender": "User", "content": "Hello"},
            {"sender": "Assistant", "content": "Hi there"},
        ],
        "contexts": {
            "User": [
                {"role": "user", "content": "User: Hello"},
                {"role": "assistant", "content": "Assistant: Hi there"},
            ],
            "Assistant": [
                {"role": "user", "content": "User: Hello"},
                {"role": "assistant", "content": "Assistant: Hi there"},
            ],
        },
    }

    assert get_context(conversation, "User") == [
        {"role": "user", "content": "User: Hello"},
        {"role": "assistant", "content": "Assistant: Hi there"},
    ]

    assert get_context(conversation, "Assistant") == [
        {"role": "user", "content": "User: Hello"},
        {"role": "assistant", "content": "Assistant: Hi there"},
    ]

    # Test non-existent participant
    assert get_context(conversation, "NonExistent") == []


@pytest.mark.parametrize(
    "conversation, participant, expected",
    [
        ({"history": [], "contexts": {}}, "Any", []),
        (
            {
                "history": [{"sender": "User", "content": "First message"}],
                "contexts": {
                    "Assistant": [{"role": "user", "content": "User: First message"}]
                },
            },
            "Assistant",
            [{"role": "user", "content": "User: First message"}],
        ),
    ],
)
def test_empty_and_single_message_conversation(conversation, participant, expected):
    assert get_context(conversation, participant) == expected
