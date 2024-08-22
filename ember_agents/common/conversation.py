from typing import TypedDict


class Message(TypedDict):
    sender: str
    content: str


class ContextMessage(TypedDict):
    role: str
    content: str


class Conversation(TypedDict):
    history: list[Message]
    contexts: dict[str, list[ContextMessage]]


def create_context_message(
    sender: str, content: str, participant: str
) -> ContextMessage:
    if participant == "User":
        role = "user" if sender == "User" else "assistant"
    else:
        role = "assistant" if sender == participant else "user"

    return {"role": role, "content": f"{sender}: {content}"}


def create_conversation_update(
    sender: str,
    content: str,
    participants: list[str],
    *,
    is_visible_to_user: bool = False,
) -> Conversation:
    new_message: Message = {"sender": sender, "content": content}
    conversation_update: Conversation = {
        "history": [new_message],
        "contexts": {},
    }

    for participant in participants:
        if participant == "User" and not is_visible_to_user:
            continue

        conversation_update["contexts"][participant] = [
            create_context_message(sender, content, participant)
        ]

    return conversation_update


def get_context(conversation: Conversation, participant: str) -> list[ContextMessage]:
    return conversation["contexts"].get(participant, [])
