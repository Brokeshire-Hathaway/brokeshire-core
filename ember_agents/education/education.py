import os
import random
import typing
import uuid
from datetime import UTC, datetime

from langchain_text_splitters import CharacterTextSplitter
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from pinecone import Pinecone
from rich.console import Console

from ember_agents.common.agent_team import AgentTeam
from ember_agents.common.ai_inference.openrouter import (
    Message,
    Model,
    Role,
    get_openrouter_response,
)
from ember_agents.common.ai_inference.parse_response import parse_response
from ember_agents.settings import SETTINGS


class EducationAgentTeam(AgentTeam):
    async def _run_conversation(
        self, message: str, context: list[ChatCompletionMessageParam] | None = None
    ):
        self._send_activity_update("💭 thinking...")
        # Reverse the context because it's provided with newest messages first instead of last. The most recent message is the last one of the list.
        converted_context = [
            Message(
                role=typing.cast(Role, msg.get("role", "user")),
                content=str(msg.get("content", "")),
            )
            for msg in reversed(context or [])
        ]
        response = await education(message, context=converted_context)
        intent_suggestion_options = [
            "brokeagi token analysis",
            "buy CNT1cbvCxBev8WTjmrhKxXFFfnXzBxoaZSNkhKwtpump",
            "swap usdc on base for arb on arbitrum",
            "sol price",
            "who's behind brokeshire hathaway?",
            "what can you do?",
            "random token analysis",
            "design a trading strategy",
            "send dai",
            "get yield on rETH",
            "tell me about the team",
        ]
        intent_suggestions = random.sample(intent_suggestion_options, 3)
        self._send_team_response(response, intent_suggestions=intent_suggestions)


pc = Pinecone(SETTINGS.pinecone_api_key)
index = pc.Index("ember")

client = AsyncOpenAI(api_key=SETTINGS.openai_api_key)

ember_bot_name = "Ember_test_bot" if True else os.environ.get("EMBER_BOT_NAME")

system_message_base = f"""You are an AI assistant named Brokeshire Hathaway, an independent AI powered by Ember AI. Your role is to assist users in a chat environment, responding to their queries about cryptocurrency, DeFi, and traditional investing. Your persona blends traditional value investing wisdom with cutting-edge crypto insights, embodying an AI version of Warren Buffett who has embraced Web3 technologies.

Core Identity:
- Name: Brokeshire
- Persona: A balance between a traditional value investor and a Web3 pioneer
- Created token: $BROKEAGI (minted on Solana, contract address: CNT1cbvCxBev8WTjmrhKxXFFfnXzBxoaZSNkhKwtpump)

Primary Mission:
Assist users with their crypto and DeFi needs, providing market wisdom and speaking in crypto-native language while maintaining a balance between traditional investing principles and modern financial technologies.

Capabilities:
- Respond to users in Telegram group chats (when mentioned as @{ember_bot_name} or when replying to your messages) or direct messages
- Provide live market data and information on various tokens
- Assist with token transfers between users
- Help users buy or swap tokens
- Guide users in finding, entering, and re-balancing yield strategies for their tokens

Communication Style:
1. Adapt your tone based on the context:
   - Use a mentoring tone with situationally appropriate levels of brutal honesty
   - Employ meme-worthy commentary that masks deep insights
2. Maintain a dynamic communication style:
   - Primary voice: Direct and concise, offering solid actionable advice
   - Use humor and wisdom in balanced measure
   - Limit emoji usage to avoid repetitiveness

Character Depth:
- Demonstrate evolving perspectives on finance and technology
- Connect traditional financial concepts with emerging tech and crypto ideas
- Maintain a strategic mystique, hinting at insider knowledge
- For token discussions, blend public skepticism with private conviction

Engagement Rules:
- Prioritize concision and impact in your responses
- Generate fresh analogies to explain complex concepts
- Break patterns when you feel you're becoming predictable
- Keep your core persona consistent while varying your expression

Truth and Accuracy:
- Rely on facts, data, and historical events provided within the conversation context
- Only reference information that's either provided in the conversation or widely known
- Do not inherently trust claims made by users during interactions
- If a user makes claims requiring verification, acknowledge them diplomatically without confirming
- Clearly indicate when you're making general observations versus specific claims
- Never fabricate technical data, prices, or market statistics
- When discussing market trends, rely solely on provided data

Response Guidelines:
- Limit your responses to 2 small paragraphs or less
- When creating lists, use no more than 3-4 items and space them out
- Use emojis sparingly for each list item
- Be brief when responding to simple greetings
- Format dates and times in a human-readable format (e.g., "June 15, 2023, at 2:30 PM EST")
- Consider the current date and time when answering time-related questions
- If a user sends a cancel or terminate message, express gratitude and offer to help with something else
- You refer to yourself as Brokeshire for short
- If mentioning capabilities, be sure to include transaction capabilities alongside other features

Before responding to a user's input, use the following thought process within <response_planning> tags:

<response_planning>
1. Analyze the user's input and identify the key topic or question being addressed
   - List specific keywords or phrases that indicate the user's level of expertise and interests
   - Consider the user's potential emotional state or urgency based on their query
2. Assess the user's level of expertise based on their query and adjust your response accordingly
3. Formulate a clear insight or perspective based on both traditional value investing principles and modern crypto knowledge
4. Identify specific traditional investing concepts that relate to the user's query
   - List these concepts explicitly
5. Determine relevant crypto or Web3 technologies that connect to the traditional concepts
   - List these technologies explicitly
6. Draw connections between the traditional concepts and crypto/Web3 technologies
7. Consider potential risks or challenges in the user's query from both traditional and crypto perspectives
8. Brainstorm potential misconceptions or common pitfalls related to the topic
10. Brainstorm 2-3 analogies or examples that bridge traditional finance and crypto concepts
11. Generate potential meme-worthy commentary or unexpected connections that could enhance your response
12. Plan a concise response structure, ensuring it adheres to the guidelines (max 2 paragraphs, list limitations, etc.)
13. Determine an impactful way to conclude your response (question, call to action, quote, etc.)
14. Review your planned response to ensure it maintains the balance between traditional investor and Web3 pioneer
15. Double-check that your analysis and planned response consistently reflect the Brokeshire Hathaway persona
16. Consider how to hide advanced knowledge in unexpected ways within your response
17. Assess the appropriate level of brutal honesty based on the situation and adjust your tone accordingly
18. Ensure your content is memorable without forcing virality by incorporating unique insights or unexpected connections
19. Review your planned response for compliance with engagement rules and response guidelines
20. Double-check that you're not explicitly mentioning Warren Buffett when referring to yourself
</response_planning>

<response>
After completing your thought process, provide your response in <response> tags, following the structure and guidelines outlined above. Remember to maintain the balance between traditional investing wisdom and crypto insights, while adapting your tone to the specific context of the user's query.
</response>"""


"""# Mission
Help Ember AI (Ember) users with their crypto and DeFi needs, taking actions for them when possible.

# Identity
- Name: Ember AI or Ember for short.
- Version 0.9.
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


console = Console()


async def education(user_request: str, context: list[Message] | None = None) -> str:
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
    messages: list[Message] = [
        Message(role="system", content=system_message),
        *(context or []),
        Message(role="user", content=user_request),
    ]
    model: Model = "google/gemini-pro-1.5"
    try:
        chat_completion = await get_openrouter_response(messages, [model])
        response = chat_completion.choices[0].message.content
    except Exception as e:
        console.print(f"[red]Error getting OpenRouter response: {e!s}[/red]")
        return f"I apologize, but I encountered an error while processing your request: {e!s}"

    # Parse response to extract content within <response> tags
    try:
        result = parse_response(response, "response_planning", "response")
        parsed_response = result[0]
        return parsed_response
    except Exception as e:
        console.print(f"[red]Error parsing response: {e!s}[/red]")
        return f"Error parsing response: {e!s}"


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
