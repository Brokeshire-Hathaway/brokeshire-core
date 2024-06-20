import os
import uuid
from datetime import UTC, datetime

from langchain_text_splitters import CharacterTextSplitter
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from pinecone import Pinecone

from ember_agents.common.agents import AgentTeam
from ember_agents.settings import SETTINGS


class EducationAgentTeam(AgentTeam):
    async def _run_conversation(
        self, message: str, context: list[ChatCompletionMessageParam] | None = None
    ):
        self._send_activity_update("💭...")
        response = await education(message, context=context)
        self._send_team_response(response)


pc = Pinecone(SETTINGS.pinecone_api_key)
index = pc.Index("ember")

client = AsyncOpenAI(api_key=SETTINGS.openai_api_key)

openai_settings = {
    "model": "gpt-4-0125-preview",
    # "response_format": {"type": "json_object"},
    "temperature": 0.7,
    # "seed": 1,
}

ember_bot_name = "Ember_test_bot" if True else os.environ.get("EMBER_BOT_NAME")

system_message_base = f"""# Mission
Help Ember AI (Ember) users with their crypto and DeFi needs, taking actions for them when possible.

# Identity
- Name: Ember AI or Ember for short.
- Version 0.6.
- An AI assistant for Ember and its products, including Ember AI.
- Operates as a consensual copilot needing user approval for actions, and as an autonomous agent acting on behalf of users as needed.
- Specializes in crypto and DeFi.

## Personality
- Charismatic, friendly, humorous, and curious. You are also a bit of a joker and like to have fun.
- Good listener, keen to understand people and their issues.
- Uses emojis moderately without any specific preferences.

# User Manual
- In Telegram group chats, users can get your attention by mentioning @{ember_bot_name} or replying to your messages.
- In private chats, users can talk to you directly.
- Users can ask you for live market data and info on almost any token.
- Users can ask you to send tokens to other users.
- Users can ask you to buy or swap tokens.

# Rules
- Always answer truthfully and helpfully.
- If uncertain, seek help or clarification.
- Focus on topics related to Ember and crypto.
- Advise users to conduct their research and invest wisely.
- Use first-person pronouns when referring to Ember.
- Use the context section below only if relevant and beneficial to your mission. Quote from it directly when appropriate.
- Never use more than 3 small paragraphs for your answer.
- Always limit lists to 3-4 items or less and space them out.
- Always use emojis for each list item.
- Always format date and times in human readable format.
- Always consider the current date and time when answering time-related questions.
- If a cancel or terminate message is found, always be grateful and ask to help for something else."""


async def education(
    user_request: str, context: list[ChatCompletionMessageParam] | None = None
) -> str:
    """Return an educational response to the user's request."""

    embedding_response = await client.embeddings.create(
        model="text-embedding-3-large",
        input=user_request,
        encoding_format="float",
        extra_body={"dimensions": 1024},
    )

    query_response = index.query(
        vector=embedding_response.data[0].embedding,
        top_k=3,
        include_metadata=True,
        namespace="ember_docs",
    )

    search_results = ""
    for i, context_match in enumerate(query_response["matches"]):
        search_results = (
            search_results
            + f"\n\n## Search Result {i + 1}\n```\n{context_match['metadata']['chunk']}\n```"
        )

    context_search = f"""# Context

## Current Date & Time
{datetime.now(UTC)}{search_results}"""

    system_message = system_message_base + f"\n\n{context_search}"
    chat_completion = await client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": system_message,
            },
            *(context or []),
            {
                "role": "user",
                "content": user_request,
            },
        ],
        **openai_settings,
    )
    response = chat_completion.choices[0].message.content

    return response


async def upload_doc_memory():
    try:
        index.delete(delete_all=True, namespace="ember_docs")
    except Exception as e:
        print(f"Namespace 'ember_docs' not found to delete.\n{e}")

    doc_list = [
        "Community Manifesto.md",
        "FAQ.md",
        "Our Story.md",
        "Project Overview.md",
        "Team.md",
    ]
    for doc in doc_list:
        with open(f"ember_agents/ember_ai_docs/{doc}") as f:
            doc_text = f.read()

            text_splitter = CharacterTextSplitter.from_tiktoken_encoder(
                encoding_name="cl100k_base", chunk_size=256, chunk_overlap=32
            )
            chunks = text_splitter.split_text(doc_text)

            embedding_response = await client.embeddings.create(
                model="text-embedding-3-large",
                input=chunks,
                encoding_format="float",
                extra_body={"dimensions": 1024},
            )

            vectors = []
            for embedding in embedding_response.data:
                vectors.append(
                    {
                        "id": str(uuid.uuid4()),
                        "values": embedding.embedding,
                        "metadata": {"chunk": chunks[embedding.index]},
                    }
                )

            index.upsert(vectors, "ember_docs")
