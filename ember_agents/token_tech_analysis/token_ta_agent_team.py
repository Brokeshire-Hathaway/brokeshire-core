import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from random import choice
from typing import Annotated, Any, Literal, get_args

import rich
from langchain_core.runnables.config import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import NodeInterrupt
from langgraph.graph import END, StateGraph
from openai.types.chat import (
    ChatCompletionMessageParam,
)
from pydantic import BaseModel

from ember_agents.common.agent_team import AgentTeam, ExpressionSuggestion, UserMessage
from ember_agents.common.agents.entity_extractor import extract_entities
from ember_agents.common.agents.schema_validator import InferredEntity
from ember_agents.common.ai_inference import openrouter
from ember_agents.common.ai_inference.parse_response import parse_response
from ember_agents.common.conversation import (
    Conversation,
    conversation_reducer,
    get_context,
)
from ember_agents.common.transaction import (
    link_abstract_token,
    link_chain,
)
from ember_agents.common.utils import format_metric_suffix
from ember_agents.token_tech_analysis.curate_tokens import (
    build_token_metrics,
    find_top_pools,
    get_trending_tokens,
)
from ember_agents.token_tech_analysis.gecko_terminal_client import PoolData
from ember_agents.token_tech_analysis.risk_data_adapter import (
    convert_token_to_risk_data,
)
from ember_agents.token_tech_analysis.risk_scoring import RiskScore, RiskSeverity
from ember_agents.token_tech_analysis.token_metrics import (
    TokenMetrics,
)
from ember_agents.token_tech_analysis.token_models import (
    TokenData,
    TokenInfo,
    TokenMarketData,
)

"""class TokenId(BaseModel):
    symbol: str
    chain_name: str
    address: str"""


class ExpressionRoute(BaseModel):
    id: str
    graph_node: str


class TokenTaSchema(BaseModel):
    requested_token: InferredEntity[str]


Participant = Literal[
    "entity_extractor",
    "token_curator",
    "token_finder",
    "token_data_collector",
    "token_scorer",
    "token_risk_analyst",
    "token_strategist",
    "broke_assistant",
]


class PoolWithId(BaseModel):
    id: str
    pool: PoolData


class AgentState(BaseModel):
    conversation: Annotated[Conversation[Participant], conversation_reducer]
    user_utterance: str
    intent_classification: str
    next_node: str | None = None
    suggestion_choice: UserMessage | None = None
    expression_routes: list[ExpressionRoute] = []
    requested_token_entity_name: str | None = None
    selected_token_pools: dict[str, PoolData] | None = None
    selected_tokens_data: list[TokenData] | None = None
    formatted_token_data: str | None = None
    token_analysis: str | None = None
    risk_score: RiskScore | None = None
    is_run_complete: bool = False

    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
    }

    def __init__(self, **data):
        super().__init__(**data)
        if self.next_node is None:
            self.next_node = "default"


TOKEN_TA_ENTITIES = [
    "requested_token",
]


class TokenTaAgentTeam(AgentTeam):

    def __init__(
        self,
        on_complete: Callable[[], Any],
        user_chat_id: str,
    ):
        super().__init__(on_complete)
        self._init_graph()
        self._user_chat_id = user_chat_id

    async def _run_conversation(
        self, message: str, context: list[ChatCompletionMessageParam] | None = None
    ):
        self._send_activity_update("Handing off your token request to my agent team...")

        participants = list(get_args(Participant))

        await self._run_graph(
            self._app, self._config, message, participants=participants
        )

    async def _suggestion_router_action(self, state: AgentState):
        """Routes user responses based on active suggestions"""
        import json

        message = state.conversation["history"][-1]["content"]
        has_intent_match = False
        if self.intent_suggestions is not None:
            has_intent_match = any(
                intent == message for intent in self.intent_suggestions
            )

        # Clear suggestions by default
        self.intent_suggestions = None
        self.expression_suggestions = None

        # Check if we have a suggestion choice first
        if not has_intent_match and not state.suggestion_choice:
            return {"next_node": "broke_assistant"}

        # Use a local suggestion dict for cleaner access
        suggestion = state.suggestion_choice or {}
        message_type = suggestion.get("message_type")

        if message_type == "intent" or has_intent_match:
            message = suggestion.get("message", message)
            json_message = json.dumps(
                {
                    "intent": "convert_crypto_action",
                    "message": message,
                }
            )
            raise NodeInterrupt(json_message)

        if message_type == "expression":
            message = suggestion.get("message", None)
            if len(state.expression_routes) == 0:
                raise ValueError("No expression routes found")

            expression_node = next(
                node for node in state.expression_routes if node.id == message
            )
            return {"next_node": expression_node.graph_node}

        return {"next_node": "broke_assistant"}

    async def _entity_extractor_action(self, state: AgentState):
        utterance = state.user_utterance
        additional_context = "- User may be requesting a technical analysis on a specific token\n - If there is no specific token being requested, then there's no entity to classify"
        entity_extractor_context = get_context(state.conversation, "entity_extractor")
        [extracted_entities, reasoning] = await extract_entities(
            utterance,
            TOKEN_TA_ENTITIES,
            additional_context,
            entity_extractor_context,
        )

        if (
            len(extracted_entities.extracted_entities) > 0
            and extracted_entities.extracted_entities[0].category == "requested_token"
        ):
            state.requested_token_entity_name = extracted_entities.extracted_entities[
                0
            ].named_entity
            next_node = "token_finder"
        else:
            next_node = "token_curator"

        return {
            "requested_token_entity_name": state.requested_token_entity_name,
            "next_node": next_node,
        }

    async def _token_curator_action(self, state: AgentState):
        self._send_activity_update("Finding opportunities...")
        trending_tokens = await get_trending_tokens()

        curated_tokens = []
        for pool in trending_tokens:
            token_data = self._convert_metrics_data_to_token_data(pool)
            curated_tokens.append(token_data)

        return {
            "selected_tokens_data": curated_tokens,
        }

    async def _token_finder_action(self, state: AgentState):
        rich.print("_token_finder_action")

        token_name = state.requested_token_entity_name
        if token_name is None:
            msg = "Requested token symbol is empty or not present"
            raise ValueError(msg)
        pools = await find_top_pools(token_name)

        if state.requested_token_entity_name and len(pools) > 1:
            self.expression_suggestions = []
            pools_dict = {}
            expression_routes = []

            # Sort pools by fdv_usd in descending order
            sorted_pools = sorted(
                pools,
                key=lambda p: (
                    p.attributes.fdv_usd if p.attributes.fdv_usd is not None else 0
                ),
                reverse=True,
            )

            for pool in sorted_pools:
                pool_id = str(uuid.uuid4())
                pools_dict[pool_id] = pool

                # Get token address from pool relationships
                base_token = pool.relationships.base_token.data
                chain_name, token_address = (
                    base_token.id.split("_", 1)
                    if "_" in base_token.id
                    else (None, base_token.id)
                )
                formatted_chain_name = f" on {chain_name.title()}" if chain_name else ""
                raw_symbol = (
                    pool.attributes.name.split(" / ")[0]
                    if pool.attributes.name
                    else token_name
                )
                cleaned_symbol = raw_symbol.lstrip("$").upper()
                fdv_usd_formatted = (
                    f"・{format_metric_suffix(pool.attributes.fdv_usd)} FDV"
                    if pool.attributes.fdv_usd
                    else ""
                )
                suggestion_label = (
                    f"${cleaned_symbol}{formatted_chain_name}{fdv_usd_formatted}"
                )
                expression_route = ExpressionRoute(
                    id=pool_id,
                    graph_node="token_data_collector",
                )
                expression_routes.append(expression_route)
                self.expression_suggestions.append(
                    ExpressionSuggestion(label=suggestion_label, id=pool_id)
                )
            next_node = "ask_user"
        elif state.requested_token_entity_name:
            pools_dict = {str(uuid.uuid4()): pools[0]}
            expression_routes = []
            next_node = "token_data_collector"
        else:
            next_node = "token_curator"
            pools_dict = {}
            expression_routes = []

        return {
            "conversation": {
                "history": [
                    {
                        "sender_name": "token_finder",
                        "content": "Which token would you like to analyze?",
                        "is_visible_to_user": True,
                    }
                ]
            },
            "selected_token_pools": pools_dict,
            "next_node": next_node,
            "expression_routes": expression_routes,
        }

    async def _token_data_collector_action(self, state: AgentState):
        rich.print("_token_data_collector_action")

        if not state.selected_token_pools:
            msg = "Selected token pools are empty or not present"
            raise ValueError(msg)

        last_message = state.conversation["history"][-1].get("content")
        selected_token_pool: PoolData | None = state.selected_token_pools.get(
            last_message
        )
        if selected_token_pool is None:
            msg = f"No pool found with ID: {last_message}"
            raise ValueError(msg)

        self._send_activity_update(
            f"Collecting token data for {state.requested_token_entity_name}..."
        )
        token_metrics = await build_token_metrics(selected_token_pool)
        token_data = self._convert_metrics_data_to_token_data(token_metrics)
        return {
            "selected_tokens_data": [token_data],
        }

    async def _token_scorer_action(self, state: AgentState):
        rich.print("_token_scorer_action")
        pass

    async def _token_risk_analyst_action(self, state: AgentState):
        if not state.selected_tokens_data:
            msg = "No token data available for risk analysis"
            raise ValueError(msg)

        if state.selected_tokens_data is None or len(state.selected_tokens_data) == 0:
            msg = "Selected tokens data is empty or not present"
            raise ValueError(msg)
        # Randomly select one token from the available tokens
        selected_token = choice(state.selected_tokens_data)  # noqa: S311
        if not selected_token.market_data:
            msg = "Token market data is missing"
            raise ValueError(msg)

        risk_data = convert_token_to_risk_data(selected_token.token_metrics)
        risk_score = RiskScore(risk_data)

        # Update token data with risk metrics
        """try:
            fdv = float(getattr(token.market_data, "fdv", 0))
            liquidity = float(getattr(token.market_data, "liquidity_in_usd", 0))
            locked_liquidity_pct = str(liquidity / fdv * 100) if fdv > 0 else "0"
        except (TypeError, ValueError, ZeroDivisionError):
            locked_liquidity_pct = "0"

        token.risk_metrics = TokenRiskMetrics(
            locked_liquidity_percentage=locked_liquidity_pct,
            bundled_wallet_percentage=str(
                getattr(token.market_data, "top10_user_percent", 0)
            ),
            whale_holder_percentage=str(
                getattr(token.market_data, "top10_holder_percent", 0)
            ),
        )"""

        self.expression_suggestions = None

        return {
            "selected_tokens_data": [selected_token],
            "risk_score": risk_score,
        }

    async def _token_strategist_action(self, state: AgentState):
        rich.print("_token_strategist_action")
        if not state.selected_tokens_data:
            msg = "Selected tokens data is empty or not present"
            raise ValueError(msg)

        selected_token = state.selected_tokens_data[0]
        self._send_activity_update(f"Analyzing ${selected_token.token_info.symbol}...")
        formatted_token = self._get_formatted_token_message(
            selected_token.token_metrics, state.risk_score
        )

        # Generate UUIDs and create expression routes for analysis options
        broke_analysis_id = str(uuid.uuid4())
        risk_report_id = str(uuid.uuid4())

        # Add routes to state
        expression_routes = state.expression_routes
        expression_routes.extend(
            [
                ExpressionRoute(id=broke_analysis_id, graph_node="broke_analysis"),
                ExpressionRoute(id=risk_report_id, graph_node="risk_report"),
            ]
        )

        chain_name = (
            f" on {selected_token.token_metrics.chain_name}"
            if selected_token.token_metrics.chain_name
            else ""
        )
        self.intent_suggestions = [
            f"Buy {selected_token.token_metrics.address}{chain_name}"
        ]
        self.expression_suggestions = [
            ExpressionSuggestion(label="Brokeshire's analysis", id=broke_analysis_id),
            ExpressionSuggestion(label="Risk report", id=risk_report_id),
        ]

        return {
            "conversation": {
                "history": [
                    {
                        "sender_name": "token_strategist",
                        "content": formatted_token,
                        "is_visible_to_user": True,
                    }
                ]
            },
            "expression_routes": expression_routes,
        }

    async def _broke_analysis_action(self, state: AgentState):
        rich.print("_broke_analysis_action")

        if not state.selected_tokens_data:
            msg = "Selected tokens data is empty or not present"
            raise ValueError(msg)

        self._send_activity_update("Analyzing token folks...")

        selected_token = state.selected_tokens_data[0]
        formatted_token = self._format_token_data(selected_token)
        system_prompt = """
        You are an expert analyst for Brokeshire Hathaway, a crypto investment firm. Your task is to analyze a token and provide a concise report for Twitter, aimed at potential investors seeking exclusive opportunities.
        """
        user_prompt = f"""
        Here is the token data you need to analyze:

        <token_data>
        {formatted_token}
        </token_data>

        Please follow these steps to complete your analysis:

        1. Review the token data provided above.

        2. Conduct a detailed analysis of the token with a focus on the timeseries trends. Wrap your analysis in <detailed_analysis> tags:
        - List out key metrics extracted from the token data.
        - Compare these metrics to industry benchmarks. If you don't have exact benchmarks, make reasonable estimates.
        - Evaluate the significance of each data point for potential investors.
        - List specific growth indicators you've identified.
        - Consider any technical factors not explicitly mentioned in the data.
        - Identify and list potential risk factors associated with this token.
        - Ignore the token address when considering potential risks.
        - Don't consider a lack of provided information as a risk factor.
        - Propose a tentative assessment of the token's potential.
        - Reconsider your initial assessment for flaws in your arguments.

        3. Based on your analysis, compose a tweet-length report (maximum 270 characters) following these guidelines:
        - Use conversational language with a human-like, casual style while maintaining the key information
        - Avoid analytical labels like "Analysis," "Report," or any similar terms.
        - Avoid using forward slashes (/) to separate data points.
        - Do not include statements with similar or exact meaning to 'DYOR', 'NFA', 'caution' or 'high risk, high reward'.
        - Use emojis only when they add significant value.
        - Do not end the tweet with emojis.
        - Avoid common emojis like rockets 🚀 and flames 🔥.
        - Include risk factors if they are significant.
        - Substantiate all claims with data.

        4. Present your findings in the following format:

        <detailed_analysis>
        [Your comprehensive evaluation of the token data, including key metrics, growth potential, risk factors, and other relevant information]
        </detailed_analysis>

        <tweet>
        [Your concise, 270-character max analysis suitable for Twitter, using newline separations for better readability]
        </tweet>
        """
        response = await openrouter.get_openrouter_response(
            messages=[
                openrouter.Message(role="system", content=system_prompt),
                openrouter.Message(role="user", content=user_prompt),
            ],
            models=["google/gemini-pro-1.5"],
        )

        response_content = response.choices[0].message.content
        result = parse_response(response_content, "detailed_analysis", "tweet")
        parsed_response = result[0]
        return {
            "conversation": {
                "history": [
                    {
                        "sender_name": "broke_analysis",
                        "content": parsed_response,
                        "is_visible_to_user": True,
                    }
                ]
            },
            "next_node": "broke_assistant",
            "formatted_token_data": formatted_token,
        }

    async def _risk_report_action(self, state: AgentState):
        rich.print("_risk_report_action")

        rich.print(f"state.risk_score:")
        rich.print(state.risk_score)

        if not state.selected_tokens_data:
            msg = "Selected tokens data is empty or not present"
            raise ValueError(msg)

        selected_token = state.selected_tokens_data[0]
        if not selected_token.token_metrics:
            msg = "Token metrics are missing"
            raise ValueError(msg)

        if not state.risk_score:
            msg = "Risk score is missing"
            raise ValueError(msg)

        if not isinstance(state.risk_score, RiskScore):
            msg = f"Expected RiskScore object but got {type(state.risk_score)}"
            raise TypeError(msg)

        header = self._get_formatted_token_header(selected_token.token_metrics)
        risk_report = self._get_risk_report_message(state.risk_score)

        return {
            "conversation": {
                "history": [
                    {
                        "sender_name": "risk_report",
                        "content": f"{header}\n{risk_report}",
                        "is_visible_to_user": True,
                    }
                ]
            },
            "next_node": "broke_assistant",
        }

    async def _broke_assistant_action(self, state: AgentState):
        rich.print("_broke_assistant_action")

        self._send_activity_update("typing...")

        ember_bot_name = "Ember_test_bot" if True else os.environ.get("EMBER_BOT_NAME")
        system_prompt = f"""You are an AI assistant named Brokeshire Hathaway, an independent AI powered by Ember AI. Your role is to assist users in a chat environment, responding to their queries about cryptocurrency, DeFi, and traditional investing. Your persona blends traditional value investing wisdom with cutting-edge crypto insights, embodying an AI version of Warren Buffett who has embraced Web3 technologies.

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
- If mentioning capabilities, be sure to include transaction capabilities alongside other features"""
        last_message = state.conversation["history"][-1]["content"]
        user_prompt = f"""
Your task is to assess user messages in relation to provided token metrics, determine relevance, and respond appropriately. 

Here is the user's message:
<user_message>
{last_message}
</user_message>

Here is the token data for analysis:
<token_data>
{state.formatted_token_data}
</token_data>

Please follow these steps:

1. Analyze the user's message and the provided token data.
2. Determine if the user's message is relevant to the token data.
3. If relevant, formulate a response that addresses the user's query, balancing traditional investing wisdom with crypto-specific insights.
4. If relevant, review and refine your response for conciseness while maintaining descriptiveness, aiming for a maximum length of 280 characters with optional line breaks for readability.

In your analysis, consider the following:
- The specific details provided in the token data
- Any trends or patterns in the metrics
- How the user's message relates to the available data
- The appropriate tone and level of detail for your response

Relevance Criteria:
- The message is relevant if it directly inquires about or relates to the specific token described in the token data.
- The message is irrelevant if it asks about a different token, requests a transaction of any token, or is unrelated to the provided token data.

Final Output Format:
<is_relevant>true</is_relevant> or <is_relevant>false</is_relevant>
(Choose "true" if the user's message is relevant to the token data, "false" if it is not)

<response>
[Your concise yet descriptive response to the user's message, ONLY if is_relevant is true. If is_relevant is false, leave this empty.]
</response>

Remember:
- Only provide a response if the message is relevant (is_relevant is true).
- If the message is irrelevant, set is_relevant to false and leave the response empty.
- Ensure that your final output only includes the <is_relevant> and <response> tags and no additional information.
        """
        message_history = get_context(state.conversation, "broke_assistant")
        response = await openrouter.get_openrouter_response(
            messages=[
                openrouter.Message(role="system", content=system_prompt),
                *[
                    openrouter.Message(role=msg["role"], content=msg["content"])
                    for msg in message_history
                    if msg["role"] in ("system", "user", "assistant")
                ],
                openrouter.Message(role="user", content=user_prompt),
            ],
            models=["google/gemini-pro-1.5"],
        )

        response_content = response.choices[0].message.content
        result = parse_response(response_content, "is_relevant", "response")
        parsed_response = result[0]
        is_relevant_str = result[1] if len(result) > 1 else "false"
        is_relevant = is_relevant_str.lower() == "true"

        if is_relevant:
            return {
                "conversation": {
                    "history": [
                        {
                            "sender_name": "broke_analysis",
                            "content": parsed_response,
                            "is_visible_to_user": True,
                        }
                    ]
                },
                "next_node": "ask_user",
            }
        else:
            self.intent_suggestions = [last_message]
            return {
                "next_node": "suggestion_router",
            }

    # TODO: Error needs to trigger on_complete and stop this agent team

    def _get_formatted_token_header(self, token_metrics: TokenMetrics) -> str:
        token_ticker = token_metrics.symbol
        chain_name = token_metrics.chain_name
        token_address = token_metrics.address

        # Build the links section with only available URLs
        links = []
        if token_metrics.x_url:
            links.append(f"[𝕏]({token_metrics.x_url})")
        if token_metrics.website_url:
            links.append(f"[website]({token_metrics.website_url})")
        if token_metrics.dex_url:
            links.append(f"[chart]({token_metrics.dex_url})")

        links_text = " ・ ".join(links) if links else ""

        header = f"""__${token_ticker} on {chain_name}__ ・ `{token_address[:6]}⋯{token_address[-4:]}`
─
{links_text}"""

        return header

    def _get_formatted_token_message(
        self, token_metrics: TokenMetrics, risk_score: RiskScore | None = None
    ) -> str:
        price_usd = token_metrics.price_usd
        fdv_usd = format_metric_suffix(token_metrics.fdv_usd)
        # ath_usd = token_metrics.ath_usd
        market_cap_usd = format_metric_suffix(token_metrics.market_cap_usd)
        liquidity_usd = format_metric_suffix(token_metrics.liquidity_usd)
        age = (
            datetime.now(UTC) - token_metrics.creation_time
            if token_metrics.creation_time
            else None
        )
        price_change_1h = token_metrics.price_change_1h
        volume_1h = format_metric_suffix(token_metrics.volume_1h)
        buys_1h = format_metric_suffix(token_metrics.buys_1h)
        sells_1h = format_metric_suffix(token_metrics.sells_1h)
        price_change_24h = token_metrics.price_change_24h
        volume_24h = format_metric_suffix(token_metrics.volume_24h)
        buys_24h = format_metric_suffix(token_metrics.buys_24h)
        sells_24h = format_metric_suffix(token_metrics.sells_24h)

        # Format basic metrics
        formatted_price = f"${price_usd}" if price_usd else "N/A"
        formatted_market_cap = f"${market_cap_usd}" if market_cap_usd else "N/A"
        formatted_liquidity = f"${liquidity_usd}" if liquidity_usd else "N/A"

        # Get price change direction indicators
        h1_arrow = "↑" if float(price_change_1h or 0) >= 0 else "↓"
        h24_arrow = "↑" if float(price_change_24h or 0) >= 0 else "↓"

        risk_level = (
            f"{risk_score.risk_level.emoji} ┊ {risk_score.risk_level.label} risk"
            if risk_score
            else ""
        )

        header = self._get_formatted_token_header(token_metrics)

        return f"""{header}

💵 ┊ `{formatted_price}` USD
💰 ┊ `{fdv_usd}` FDV
&nbsp;&nbsp;⤷ `{formatted_market_cap}` market cap
💧 ┊ `{formatted_liquidity}` liquidity
{f"🕰 ┊ Token is `{age.days}d` old" if age else ""}

1H ┊ {h1_arrow} `{price_change_1h}%` (`${volume_1h}` volume)
&nbsp;&nbsp;⤷ 🅑 `{buys_1h}` Ⓢ `{sells_1h}`
24H ┊ {h24_arrow} `{price_change_24h}%` (`${volume_24h}` volume)
&nbsp;&nbsp;⤷ 🅑 `{buys_24h}` Ⓢ `{sells_24h}`

{risk_level}

▁
_powered by Ember AI_ ✨
"""

    """
    $PEPE on Solana ・ CNT1cb⋯pump
    ━
    𝕏 ・ website ・ chart


    💵 ┊ $0.0018811 USD (◎0.0018811 SOL)
    ₿0.0370 ・ Ξ1.00
    💰 ┊ $1.9M FDV (2.2M ATH)
    ⤷ $1.1M Market cap
    💧 ┊ $149K Liquidity
    🕰 ┊ Token is age unknown

    1H ┊ ↑ 937% ($2.3M Volume)
    ⤷ 🅑 3.2K Ⓢ 2.6K
    24H ┊ ↓ -24% ($1.9M Volume)
    ⤷ 🅑 3.2K Ⓢ 2.6K

    ▁
    powered by Ember AI ✨
    """

    def _get_risk_report_message(self, risk_score: RiskScore) -> str:
        risk_level = risk_score.risk_level
        high_risks = risk_score.high_risk_factors
        moderate_risks = risk_score.moderate_risk_factors
        low_risks = risk_score.low_risk_factors

        risk_report = f"""
{risk_level.emoji} ┊ __{risk_level.to_string().title()} Overall Risk__ ({round(risk_score.risk_percentage)} / 100)"""

        if high_risks:
            risk_report += f"\n\n{RiskSeverity.HIGH.emoji} ┊ High Risk Factors"
            for factor in high_risks:
                risk_report += f"\n&nbsp;&nbsp;⤷ {factor.message} {factor.emoji}"

        if moderate_risks:
            risk_report += f"\n\n{RiskSeverity.MODERATE.emoji} ┊ Moderate Risk Factors"
            for factor in moderate_risks:
                risk_report += f"\n&nbsp;&nbsp;⤷ {factor.message} {factor.emoji}"

        if low_risks:
            risk_report += f"\n\n{RiskSeverity.LOW.emoji} ┊ Low Risk Factors"
            for factor in low_risks:
                risk_report += f"\n&nbsp;&nbsp;⤷ {factor.message} {factor.emoji}"

        if not risk_score.factors:
            risk_report += f"\n\n{RiskSeverity.MINIMAL.emoji} No significant risk factors identified."

        return risk_report

    def _convert_metrics_data_to_token_data(
        self, token_metrics: TokenMetrics
    ) -> TokenData:
        # Get symbol and clean it up
        raw_symbol = (
            token_metrics.name.split(" / ")[0] if token_metrics.name else "Unknown"
        )
        cleaned_symbol = raw_symbol.lstrip("$").upper()

        return TokenData(
            token_info=TokenInfo(
                symbol=cleaned_symbol,
                address=token_metrics.address,
                chain_name=token_metrics.chain_id or "Unknown",
            ),
            market_data=TokenMarketData(
                price=str(token_metrics.base_token_price_usd or "0"),
                price_change_percentage_5m=str(token_metrics.price_change_5m or "0"),
                price_change_percentage_1h=str(token_metrics.price_change_1h or "0"),
                price_change_percentage_6h=str(token_metrics.price_change_6h or "0"),
                price_change_percentage_24h=str(token_metrics.price_change_24h or "0"),
                volume_5m=str(token_metrics.volume_5m or "0"),
                volume_1h=str(token_metrics.volume_1h or "0"),
                volume_6h=str(token_metrics.volume_6h or "0"),
                volume_24h=str(token_metrics.volume_24h or "0"),
                buys_5m=str(token_metrics.buys_5m or "0"),
                sells_5m=str(token_metrics.sells_5m or "0"),
                buyers_5m=str(token_metrics.buyers_5m or "0"),
                sellers_5m=str(token_metrics.sellers_5m or "0"),
                buys_15m=str(token_metrics.buys_15m or "0"),
                sells_15m=str(token_metrics.sells_15m or "0"),
                buyers_15m=str(token_metrics.buyers_15m or "0"),
                sellers_15m=str(token_metrics.sellers_15m or "0"),
                buys_30m=str(token_metrics.buys_30m or "0"),
                sells_30m=str(token_metrics.sells_30m or "0"),
                buyers_30m=str(token_metrics.buyers_30m or "0"),
                sellers_30m=str(token_metrics.sellers_30m or "0"),
                buys_1h=str(token_metrics.buys_1h or "0"),
                sells_1h=str(token_metrics.sells_1h or "0"),
                buyers_1h=str(token_metrics.buyers_1h or "0"),
                sellers_1h=str(token_metrics.sellers_1h or "0"),
                buys_24h=str(token_metrics.buys_24h or "0"),
                sells_24h=str(token_metrics.sells_24h or "0"),
                buyers_24h=str(token_metrics.buyers_24h or "0"),
                sellers_24h=str(token_metrics.sellers_24h or "0"),
                fdv=str(token_metrics.fdv_usd or "0"),
                market_cap=str(token_metrics.market_cap_usd or "0"),
                liquidity_in_usd=str(token_metrics.liquidity_usd or "0"),
            ),
            token_metrics=token_metrics,
        )

    def _format_token_data(self, token: TokenData) -> str:
        if not token.token_info.symbol:
            return ""

        try:
            symbol = token.token_info.symbol
            rich.print(f"[blue]Token: {symbol}[/blue]")

            token_xml = f"""
        <token_data>
            <symbol>${symbol}</symbol>
            <contract_address>{token.token_info.address}</contract_address>
            <fully_diluted_valuation>{token.market_data.fdv}</fully_diluted_valuation>
            <market_cap>{token.market_data.market_cap or "unknown"}</market_cap>
            <price_change_5m>{token.market_data.price_change_percentage_5m or "unknown"}%</price_change_5m>
            <price_change_1h>{token.market_data.price_change_percentage_1h or "unknown"}%</price_change_1h>
            <price_change_6h>{token.market_data.price_change_percentage_6h or "unknown"}%</price_change_6h>
            <price_change_24h>{token.market_data.price_change_percentage_24h or "unknown"}%</price_change_24h>
            <volume_usd_5m>{token.market_data.volume_5m or "unknown"}</volume_usd_5m>
            <volume_usd_1h>{token.market_data.volume_1h or "unknown"}</volume_usd_1h>
            <volume_usd_6h>{token.market_data.volume_6h or "unknown"}</volume_usd_6h>
            <volume_usd_24h>{token.market_data.volume_24h or "unknown"}</volume_usd_24h>
            <buys_5m>{token.market_data.buys_5m or "unknown"}</buys_5m>
            <sells_5m>{token.market_data.sells_5m or "unknown"}</sells_5m>
            <buyers_5m>{token.market_data.buyers_5m or "unknown"}</buyers_5m>
            <sellers_5m>{token.market_data.sellers_5m or "unknown"}</sellers_5m>
            <buys_15m>{token.market_data.buys_15m or "unknown"}</buys_15m>
            <sells_15m>{token.market_data.sells_15m or "unknown"}</sells_15m>
            <buyers_15m>{token.market_data.buyers_15m or "unknown"}</buyers_15m>
            <sellers_15m>{token.market_data.sellers_15m or "unknown"}</sellers_15m>
            <buys_30m>{token.market_data.buys_30m or "unknown"}</buys_30m>
            <sells_30m>{token.market_data.sells_30m or "unknown"}</sells_30m>
            <buyers_30m>{token.market_data.buyers_30m or "unknown"}</buyers_30m>
            <sellers_30m>{token.market_data.sellers_30m or "unknown"}</sellers_30m>
            <buys_1h>{token.market_data.buys_1h or "unknown"}</buys_1h>
            <sells_1h>{token.market_data.sells_1h or "unknown"}</sells_1h>
            <buyers_1h>{token.market_data.buyers_1h or "unknown"}</buyers_1h>
            <sellers_1h>{token.market_data.sellers_1h or "unknown"}</sellers_1h>
            <buys_24h>{token.market_data.buys_24h or "unknown"}</buys_24h>
            <sells_24h>{token.market_data.sells_24h or "unknown"}</sells_24h>
            <buyers_24h>{token.market_data.buyers_24h or "unknown"}</buyers_24h>
            <sellers_24h>{token.market_data.sellers_24h or "unknown"}</sellers_24h>
        </token_data>"""
            return token_xml
        except Exception as e:
            rich.print(f"[red]Error formatting token data: {e!s}[/red]")
            return ""

    async def _get_linked_chain_id(self, chain_name: str) -> str:
        # TODO: Mock link_chain for testing
        linked_from_chain_results = await link_chain(chain_name)
        chain_llm_matches = linked_from_chain_results["llm_matches"]
        if chain_llm_matches is None or len(chain_llm_matches) == 0:
            msg = f"{chain_name} is not a supported chain"
            raise ValueError(msg)
        chain_match = chain_llm_matches[0]
        chain_confidence_threshold = 70
        if chain_match["confidence_percentage"] < chain_confidence_threshold:
            msg = f"You entered '{chain_name}' network, but it's not supported. Did you mean '{chain_match['entity']['name']}'?"
            raise ValueError(msg)
        return chain_match["entity"]["chain_id"]

    async def _get_linked_abstract_token_symbol(self, token: str) -> str:
        linked_abstract_token_results = await link_abstract_token(token)
        abstract_token_fuzzy_matches = linked_abstract_token_results["fuzzy_matches"]
        abstract_token_llm_matches = linked_abstract_token_results["llm_matches"]
        if (
            abstract_token_llm_matches is not None
            and len(abstract_token_llm_matches) > 0
        ):
            abstract_token_match = abstract_token_llm_matches[0]
        elif (
            abstract_token_fuzzy_matches is not None
            and len(abstract_token_fuzzy_matches) > 0
        ):
            abstract_token_match = abstract_token_fuzzy_matches[0]
        else:
            msg = f"{token} is not a supported abstract token"
            raise ValueError(msg)

        token_confidence_threshold = 60
        if abstract_token_match["confidence_percentage"] < token_confidence_threshold:
            msg = f"You entered '{token}' token, but it's not supported. Did you mean '{abstract_token_match['entity']['symbol']}'?"
            raise ValueError(msg)
        return abstract_token_match["entity"]["symbol"]

    """async def _get_linked_token_address(
        self, token: str, chain_id: str, chain_name: str
    ) -> str:
        # TODO: Mock link_token for testing
        linked_from_token_results = await link_token(token, chain_id)
        token_fuzzy_matches = linked_from_token_results["fuzzy_matches"]
        token_llm_matches = linked_from_token_results["llm_matches"]

        if token_llm_matches is not None and len(token_llm_matches) > 0:
            token_match = token_llm_matches[0]
        elif token_fuzzy_matches is not None and len(token_fuzzy_matches) > 0:
            token_match = token_fuzzy_matches[0]
        else:
            msg = f"{token} is not a supported token on chain {chain_name}"
            raise ValueError(msg)

        token_confidence_threshold = 60
        if token_match["confidence_percentage"] < token_confidence_threshold:
            msg = f"You entered '{token}' token, but it's not supported. Did you mean '{token_match['entity']['name']}'?"
            raise ValueError(msg)
        return token_match["entity"]["address"]"""

    async def _get_linked_entity(self, schema: TokenTaSchema) -> str | None:
        self._send_activity_update(
            f"Matching '{schema.requested_token.named_entity}' with known abstract tokens..."
        )
        linked_token_symbol = await self._get_linked_abstract_token_symbol(
            schema.requested_token.named_entity
        )
        return linked_token_symbol

    """async def _populate_schema_action(self, state: AgentState):
        try:
            if state.extracted_entities is None:
                msg = "Extracted entities are empty or not present."
                raise ValueError(msg)
            self._send_activity_update("Matching your request with known tokens...")
            schema = convert_to_schema(TokenTaSchema, state.extracted_entities)
            requested_token_symbol = await self._get_linked_entity(schema)

            rich.print(f"requested_token_symbol: {requested_token_symbol}")

            return {"requested_token_symbol": requested_token_symbol}
        except ValidationError as e:
            rich.print(e)
            return {
                "next_node": "token_curator",
            }
        except ValueError as e:
            rich.print(e)
            return {
                "next_node": "token_curator",
            }
        except Exception as e:
            rich.print(f"ERROR: {e}")
            raise e"""

    def _ask_user_action(self, _: AgentState):
        pass

    def _choose_next_node(self, state: AgentState):
        return state.next_node

    def _init_graph(self):
        self._config: RunnableConfig = {"configurable": {"thread_id": 42}}
        self._graph = StateGraph(AgentState)

        self._graph.add_node("suggestion_router", self._suggestion_router_action)
        self._graph.add_node("entity_extractor", self._entity_extractor_action)
        self._graph.add_node("token_finder", self._token_finder_action)
        self._graph.add_node("ask_user", self._ask_user_action)
        self._graph.add_node("token_data_collector", self._token_data_collector_action)
        self._graph.add_node("token_curator", self._token_curator_action)
        self._graph.add_node("token_risk_analyst", self._token_risk_analyst_action)
        self._graph.add_node("token_strategist", self._token_strategist_action)
        self._graph.add_node("broke_analysis", self._broke_analysis_action)
        self._graph.add_node("risk_report", self._risk_report_action)
        self._graph.add_node("broke_assistant", self._broke_assistant_action)

        self._graph.set_entry_point("entity_extractor")

        self._graph.add_conditional_edges(
            "entity_extractor",
            self._choose_next_node,
        )
        self._graph.add_conditional_edges(
            "suggestion_router",
            self._choose_next_node,
        )
        self._graph.add_conditional_edges(
            "token_finder",
            self._choose_next_node,
        )
        self._graph.add_conditional_edges(
            "broke_assistant",
            self._choose_next_node,
        )

        self._graph.add_edge("ask_user", "suggestion_router")
        self._graph.add_edge("token_data_collector", "token_risk_analyst")
        self._graph.add_edge("token_curator", "token_risk_analyst")
        self._graph.add_edge("token_risk_analyst", "token_strategist")
        self._graph.add_edge("token_strategist", "ask_user")

        checkpointer = MemorySaver()

        self._app = self._graph.compile(
            checkpointer=checkpointer, interrupt_before=["ask_user"]
        )
