from collections.abc import Callable
from random import choice
from typing import Annotated, Any, Literal, get_args

import rich
from langchain_core.runnables.config import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from openai.types.chat import (
    ChatCompletionMessageParam,
)
from pydantic import BaseModel, ValidationError

from ember_agents.common.agent_team import AgentTeam
from ember_agents.common.agents.entity_extractor import extract_entities
from ember_agents.common.agents.schema_validator import (
    InferredEntity,
    convert_to_schema,
)
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
from ember_agents.token_tech_analysis.curate_tokens import (
    PoolData,
    find_token,
    get_trending_tokens,
)


class TokenTaSchema(BaseModel):
    requested_token: InferredEntity[str]


class TokenInfo(BaseModel):
    symbol: str
    address: str
    chain_id: str | None = None
    chain_name: str
    explorer_uri: str | None = None


class TokenMarketData(BaseModel):
    price: str
    price_change_percentage_5m: str | None = None
    price_change_percentage_1h: str | None = None
    price_change_percentage_6h: str | None = None
    price_change_percentage_24h: str | None = None
    volume_5m: str
    volume_1h: str
    volume_6h: str
    volume_24h: str
    buys_5m: str
    sells_5m: str
    buyers_5m: str
    sellers_5m: str
    buys_15m: str
    sells_15m: str
    buyers_15m: str
    sellers_15m: str
    buys_30m: str
    sells_30m: str
    buyers_30m: str
    sellers_30m: str
    buys_1h: str
    sells_1h: str
    buyers_1h: str
    sellers_1h: str
    buys_24h: str
    sells_24h: str
    buyers_24h: str
    sellers_24h: str
    fdv: str
    market_cap: str | None = None
    market_cap_change_percentage_24h: str | None = None
    liquidity_in_usd: str | None = None
    holders: str | None = None
    holders_change_percentage_24h: str | None = None


class TokenRiskMetrics(BaseModel):
    locked_liquidity_percentage: str
    bundled_wallet_percentage: str
    whale_holder_percentage: str


class TokenData(BaseModel):
    token_info: TokenInfo
    market_data: TokenMarketData
    risk_metrics: TokenRiskMetrics | None = None


Participant = Literal[
    "entity_extractor",
    "token_curator",
    "token_data_collector",
    "token_scorer",
    "token_risk_analyst",
    "token_strategist",
]


class AgentState(BaseModel):
    conversation: Annotated[Conversation[Participant], conversation_reducer]
    user_utterance: str
    intent_classification: str
    next_node: str | None = None
    requested_token_entity_name: str | None = None
    selected_tokens_data: list[TokenData] | None = None
    token_analysis: str | None = None
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
        self._send_activity_update(
            "Handing off your technical analysis request my agent team..."
        )

        participants = list(get_args(Participant))

        await self._run_graph(
            self._app, self._config, message, participants=participants
        )

    async def _entity_extractor_action(self, state: AgentState):
        utterance = state.user_utterance
        additional_context = "- User may be requesting a technical analysis on a specific token\n - If there is no specific token requested, the user is likely asking for a token recommendation"
        entity_extractor_context = get_context(state.conversation, "entity_extractor")
        [extracted_entities, reasoning] = await extract_entities(
            utterance,
            TOKEN_TA_ENTITIES,
            additional_context,
            entity_extractor_context,
        )

        rich.print(f"reasoning: {reasoning}")
        rich.print(f"extracted_entities: {extracted_entities}")

        if (
            len(extracted_entities.extracted_entities) > 0
            and extracted_entities.extracted_entities[0].category == "requested_token"
        ):
            state.requested_token_entity_name = extracted_entities.extracted_entities[
                0
            ].named_entity
            next_node = "token_data_collector"
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
            token_data = self._convert_pool_data_to_token_data(pool)
            curated_tokens.append(token_data)

        return {
            "selected_tokens_data": curated_tokens,
        }

    async def _token_data_collector_action(self, state: AgentState):
        rich.print("_token_data_collector_action")
        token_symbol = state.requested_token_entity_name
        if token_symbol is None:
            msg = "Requested token symbol is empty or not present"
            raise ValueError(msg)
        self._send_activity_update(f"Collecting token data for {token_symbol}...")
        pool_data = await find_token(token_symbol)
        token_data = self._convert_pool_data_to_token_data(pool_data)
        return {
            "selected_tokens_data": [token_data],
        }

    async def _token_scorer_action(self, state: AgentState):
        rich.print("_token_scorer_action")
        pass

    async def _token_risk_analyst_action(self, state: AgentState):
        rich.print("_token_risk_analyst_action")
        pass

    async def _token_strategist_action(self, state: AgentState):
        rich.print("_token_strategist_action")
        if state.selected_tokens_data is None or len(state.selected_tokens_data) == 0:
            msg = "Selected tokens data is empty or not present"
            raise ValueError(msg)
        # Randomly select one token from the available tokens
        selected_token = choice(state.selected_tokens_data)  # noqa: S311
        self._send_activity_update(f"Analyzing ${selected_token.token_info.symbol}...")
        formatted_token = self._format_token_data(selected_token)

        rich.print(f"formatted_token:\n{formatted_token}")

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

        2. Conduct a detailed analysis of the token. Wrap your analysis in <detailed_analysis> tags:
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
        parsed_response = parse_response(response_content, "detailed_analysis", "tweet")

        return {
            "conversation": {
                "history": [
                    {
                        "sender_name": "transactor",
                        "content": parsed_response,
                        "is_visible_to_user": True,
                    }
                ]
            },
            "is_run_complete": True,
        }

    # TODO: Error needs to trigger on_complete and stop this agent team

    def _convert_pool_data_to_token_data(self, pool_data: PoolData) -> TokenData:
        token_attrs = pool_data.attributes
        base_token = pool_data.relationships.base_token.data
        chain_name = (
            pool_data.relationships.network.data.id
            if pool_data.relationships.network
            else "Unknown"
        )
        token_address = (
            base_token.id.split("_", 1)[1] if "_" in base_token.id else base_token.id
        )

        # Get symbol and clean it up
        raw_symbol = token_attrs.name.split(" / ")[0] if token_attrs.name else "Unknown"
        cleaned_symbol = raw_symbol.lstrip("$").upper()

        return TokenData(
            token_info=TokenInfo(
                symbol=cleaned_symbol,
                address=token_address,
                chain_name=chain_name,
            ),
            market_data=TokenMarketData(
                price=str(token_attrs.base_token_price_usd or "0"),
                price_change_percentage_5m=str(
                    token_attrs.price_change_percentage.m5 or "0"
                ),
                price_change_percentage_1h=str(
                    token_attrs.price_change_percentage.h1 or "0"
                ),
                price_change_percentage_6h=str(
                    token_attrs.price_change_percentage.h6 or "0"
                ),
                price_change_percentage_24h=str(
                    token_attrs.price_change_percentage.h24 or "0"
                ),
                volume_5m=str(token_attrs.volume_usd.m5 or "0"),
                volume_1h=str(token_attrs.volume_usd.h1 or "0"),
                volume_6h=str(token_attrs.volume_usd.h6 or "0"),
                volume_24h=str(token_attrs.volume_usd.h24 or "0"),
                buys_5m=str(token_attrs.transactions.m5.buys or "0"),
                sells_5m=str(token_attrs.transactions.m5.sells or "0"),
                buyers_5m=str(token_attrs.transactions.m5.buyers or "0"),
                sellers_5m=str(token_attrs.transactions.m5.sellers or "0"),
                buys_15m=str(token_attrs.transactions.m15.buys or "0"),
                sells_15m=str(token_attrs.transactions.m15.sells or "0"),
                buyers_15m=str(token_attrs.transactions.m15.buyers or "0"),
                sellers_15m=str(token_attrs.transactions.m15.sellers or "0"),
                buys_30m=str(token_attrs.transactions.m30.buys or "0"),
                sells_30m=str(token_attrs.transactions.m30.sells or "0"),
                buyers_30m=str(token_attrs.transactions.m30.buyers or "0"),
                sellers_30m=str(token_attrs.transactions.m30.sellers or "0"),
                buys_1h=str(token_attrs.transactions.h1.buys or "0"),
                sells_1h=str(token_attrs.transactions.h1.sells or "0"),
                buyers_1h=str(token_attrs.transactions.h1.buyers or "0"),
                sellers_1h=str(token_attrs.transactions.h1.sellers or "0"),
                buys_24h=str(token_attrs.transactions.h24.buys or "0"),
                sells_24h=str(token_attrs.transactions.h24.sells or "0"),
                buyers_24h=str(token_attrs.transactions.h24.buyers or "0"),
                sellers_24h=str(token_attrs.transactions.h24.sellers or "0"),
                fdv=str(token_attrs.fdv_usd or "0"),
                market_cap=str(token_attrs.reserve_in_usd or "0"),
                liquidity_in_usd=str(token_attrs.reserve_in_usd or "0"),
            ),
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
        return chain_match["entity"]["id"]

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

        """self._graph.add_node("entity_extractor", self._entity_extractor_action)
        self._graph.add_node("token_curator", self._token_curator_action)
        self._graph.add_node("token_data_collector", self._token_data_collector_action)
        self._graph.add_node("token_scorer", self._token_scorer_action)
        self._graph.add_node("token_risk_analyst", self._token_risk_analyst_action)
        self._graph.add_node("token_strategist", self._token_strategist_action)

        self._graph.set_entry_point("entity_extractor")

        self._graph.add_conditional_edges(
            "entity_extractor",
            self._choose_next_node,
            {
                "token_curator": "token_curator",
                "default": "token_data_collector",
            },
        )
        self._graph.add_edge("token_curator", "token_scorer")
        self._graph.add_edge("token_data_collector", "token_scorer")
        self._graph.add_edge("token_scorer", "token_risk_analyst")
        self._graph.add_edge("token_risk_analyst", "token_strategist")
        self._graph.add_edge("token_strategist", END)"""

        self._graph.add_node("entity_extractor", self._entity_extractor_action)
        self._graph.add_node("token_data_collector", self._token_data_collector_action)
        self._graph.add_node("token_curator", self._token_curator_action)
        self._graph.add_node("token_strategist", self._token_strategist_action)

        self._graph.set_entry_point("entity_extractor")

        self._graph.add_conditional_edges(
            "entity_extractor",
            self._choose_next_node,
            {
                "token_curator": "token_curator",
                "token_data_collector": "token_data_collector",
            },
        )
        self._graph.add_edge("token_data_collector", "token_strategist")
        self._graph.add_edge("token_curator", "token_strategist")
        self._graph.add_edge("token_strategist", END)

        checkpointer = MemorySaver()

        self._app = self._graph.compile(checkpointer=checkpointer)
