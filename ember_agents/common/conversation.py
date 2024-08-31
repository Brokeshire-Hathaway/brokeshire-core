from typing import Dict, Generic, List, Literal, TypedDict, TypeVar, Union

from rich import print

P = TypeVar("P", bound=str)
UserAndOthers = Literal["user"] | P


class Message(TypedDict):
    sender_name: str
    content: str
    is_visible_to_user: bool


class ContextMessage(TypedDict):
    role: str
    content: str


class Conversation(TypedDict, Generic[P]):
    history: list[Message]
    contexts: dict[UserAndOthers[P], list[ContextMessage]]
    participants: list[UserAndOthers[P]]


def create_context_message(
    sender: str, content: str, participant: str
) -> ContextMessage:
    if participant == "user":
        role = "user" if sender == "user" else "assistant"
    else:
        role = "assistant" if sender == participant else "user"

    return {
        "role": role,
        "content": f"<sender_name>{sender}</sender_name>\n<message>{content}</message>",
    }


def get_context(
    conversation: Conversation[P], participant: UserAndOthers[P]
) -> list[ContextMessage]:
    return conversation["contexts"].get(participant, [])


def create_contexts_update(
    new_message: Message, participants: list[UserAndOthers[P]]
) -> dict[UserAndOthers[P], list[ContextMessage]]:
    """
    Create context updates for each participant based on the new message.

    Args:
        new_message (Message): The new message to create contexts for.
        participants (List[P]): List of participants.

    Returns:
        Dict[P, List[ContextMessage]]: Dictionary of context updates for each participant.
    """

    return {
        participant: [
            create_context_message(
                new_message["sender_name"], new_message["content"], participant
            )
        ]
        for participant in participants
        if participant != "user" or new_message["is_visible_to_user"]
    }


def create_default_conversation(
    participants: list[UserAndOthers[P]],
) -> Conversation[P]:
    return {
        "history": [],
        "contexts": {},
        "participants": participants,
    }


def is_valid_message(msg: Message | dict) -> bool:
    return (
        isinstance(msg, dict)
        and "sender_name" in msg
        and isinstance(msg["sender_name"], str)
        and "content" in msg
        and isinstance(msg["content"], str)
        and "is_visible_to_user" in msg
        and isinstance(msg["is_visible_to_user"], bool)
    )


def conversation_reducer(
    current_conversation: Conversation[P], new_conversation: Conversation[P]
) -> Conversation[P]:
    participants = current_conversation.get("participants") or new_conversation.get(
        "participants"
    )

    if not participants:
        msg = "Participants list cannot be empty"
        raise ValueError(msg)

    conversation = current_conversation or create_default_conversation(participants)

    if not new_conversation["history"]:
        return conversation

    new_message = new_conversation["history"][-1]

    if not is_valid_message(new_message):
        msg = f"Invalid message: {new_message}"
        raise ValueError(msg)

    contexts_update = create_contexts_update(
        new_message=new_message,
        participants=participants,
    )

    return {
        "history": conversation["history"] + [new_message],
        "contexts": {
            participant: (
                conversation["contexts"].get(participant, [])
                + contexts_update.get(participant, [])
            )
            for participant in participants
        },
        "participants": participants,
    }
