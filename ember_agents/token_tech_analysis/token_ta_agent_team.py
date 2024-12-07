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
from ember_agents.common.agents.entity_extractor import (
    ExtractedEntities,
    extract_entities,
)
from ember_agents.common.agents.schema_validator import (
    InferredEntity,
    convert_to_schema,
)
from ember_agents.common.ai_inference import openrouter
from ember_agents.common.conversation import (
    Conversation,
    conversation_reducer,
    get_context,
)
from ember_agents.common.transaction import (
    link_abstract_token,
    link_chain,
)
from ember_agents.token_tech_analysis.curate_tokens import get_trending_tokens


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
    volume_24h: str
    volume_change_percentage_24h: str | None = None
    fdv: str
    market_cap: str
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
    extracted_entities: ExtractedEntities | None = None
    requested_token_symbol: str | None = None
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
        self._send_activity_update("Reading your request...")

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

        next_node = (
            "token_data_collector"
            if len(extracted_entities.extracted_entities) > 0
            else "token_curator"
        )

        return {
            "extracted_entities": extracted_entities,
            "next_node": next_node,
        }

    async def _token_curator_action(self, state: AgentState):
        trending_tokens = await get_trending_tokens()

        curated_tokens = []
        for token in trending_tokens:
            # Extract base token data
            base_token = token.relationships.base_token.data
            token_attrs = token.attributes

            # Create TokenData instance for each trending token
            token_data = TokenData(
                token_info=TokenInfo(
                    symbol=(
                        token_attrs.name.split(" / ")[0]
                        if token_attrs.name
                        else "Unknown"
                    ),
                    address=base_token.id,
                    chain_name=token.relationships.network.data.id,
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
                    volume_24h=str(token_attrs.volume_usd.h24 or "0"),
                    fdv=str(token_attrs.fdv_usd or "0"),
                    market_cap=str(token_attrs.reserve_in_usd or "0"),
                    liquidity_in_usd=str(token_attrs.reserve_in_usd or "0"),
                ),
            )
            curated_tokens.append(token_data)

        return {
            "selected_tokens_data": curated_tokens,
        }

    async def _token_data_collector_action(self, state: AgentState):
        rich.print("_token_data_collector_action")
        pass

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
        formatted_token = self._format_token_data(selected_token)
        system_prompt = f"""
        You are an expert technical analyst for a crypto investment firm called Brokeshire Hathaway. Your job is to analyze a <token> and provide a technical analysis report for users seeking exclusive investment opportunities. The <token> has been identified as having high potential for growth, which you may or may not agree with.

        Liquidity refers to the AMM pool size. Anything above $500,000 should be considered sufficient, but generally the higher the better. You're an expert on AMMs, so you know best.

        Keep your response concise and to the point for a Twitter post. It should be no more than 270 characters. Include only the data points that are relevant to your specific analysis. Separate any data using something other than a forward slash (/). Do not include "DYOR" or "NFA" in your response.

        Analyze the <token> below.

        {formatted_token}
        """
        user_prompt = "Provide a technical analysis report for the token above."
        response = await openrouter.get_openrouter_response(
            messages=[
                openrouter.Message(role="system", content=system_prompt),
                openrouter.Message(role="user", content=user_prompt),
            ],
            models=["google/gemini-pro-1.5"],
        )
        return {
            "conversation": {
                "history": [
                    {
                        "sender_name": "transactor",
                        "content": response.choices[0].message.content,
                        "is_visible_to_user": True,
                    }
                ]
            },
            "is_run_complete": True,
        }

    # TODO: Error needs to trigger on_complete and stop this agent team

    def _format_token_data(self, token: TokenData) -> str:
        if not token.token_info.symbol:
            return ""

        try:
            symbol = token.token_info.symbol
            rich.print(f"[blue]Token: {symbol}[/blue]")

            token_xml = f"""
        <token>
            <symbol>${symbol}</symbol>
            <contractAddress>{token.token_info.address}</contractAddress>
            <price>{token.market_data.price}</price>
            <priceChange5m>{token.market_data.price_change_percentage_5m or "0"}%</priceChange5m>
            <priceChange1h>{token.market_data.price_change_percentage_1h or "0"}%</priceChange1h>
            <priceChange6h>{token.market_data.price_change_percentage_6h or "0"}%</priceChange6h>
            <priceChange24h>{token.market_data.price_change_percentage_24h or "0"}%</priceChange24h>
            <volumeUsd>{token.market_data.volume_24h}</volumeUsd>
            <liquidityUsd>{token.market_data.liquidity_in_usd}</liquidityUsd>
        </token>"""
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

    async def _populate_schema_action(self, state: AgentState):
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
            raise e

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

        self._graph.add_node("token_curator", self._token_curator_action)
        self._graph.add_node("token_strategist", self._token_strategist_action)

        self._graph.set_entry_point("token_curator")

        self._graph.add_edge("token_curator", "token_strategist")
        self._graph.add_edge("token_strategist", END)

        checkpointer = MemorySaver()

        self._app = self._graph.compile(checkpointer=checkpointer)
