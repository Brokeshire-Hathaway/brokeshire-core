import asyncio
import json
from collections.abc import Callable
from typing import Annotated, Any, Literal, get_args

import httpx
import rich
from langchain_core.runnables.config import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from openai.types.chat import (
    ChatCompletionMessageParam,
)
from pydantic import BaseModel, ValidationError

from ember_agents.common.agent_team import AgentTeam
from ember_agents.common.agents.clarifier import get_clarifier_response
from ember_agents.common.agents.entity_extractor import (
    ExtractedEntities,
    extract_entities,
)
from ember_agents.common.agents.schema_validator import (
    InferredEntity,
    convert_to_schema,
    flatten_classified_entities,
)
from ember_agents.common.conversation import (
    Conversation,
    conversation_reducer,
    get_context,
)
from ember_agents.common.transaction import (
    get_best_yield_strategy,
    link_abstract_token,
    link_chain,
    link_token,
)
from ember_agents.common.utils import format_currency_string, format_transaction_url
from ember_agents.common.validators import PositiveAmount
from ember_agents.settings import SETTINGS


class EarnSchema(BaseModel):
    deposit_token: InferredEntity[str]
    deposit_chain: InferredEntity[str] | None = (
        None  # TODO: make this optional so that abstract token can be used
    )
    amount: InferredEntity[float]
    # yield_protocol: InferredEntity[str]
    # strategy_id: InferredEntity[str]
    from_token: InferredEntity[str] | None = None
    from_chain: InferredEntity[str] | None = None


class FromToken(BaseModel):
    id: str
    chainId: str | None = None
    amount: PositiveAmount


class DepositToken(BaseModel):
    id: str
    chainId: str | None = None
    amount: PositiveAmount | None = None


class EarnRequest(BaseModel):
    """Request for doing cross chain earn"""

    fromToken: FromToken | None = None
    depositToken: DepositToken
    strategyId: str
    userChatId: str
    storeTransaction: Any


class TokenInfo(BaseModel):
    symbol: str
    amount: str
    address: str
    chainId: str
    chainName: str
    explorerUri: str


class YieldStrategy(BaseModel):
    id: str
    name: str
    apy: str
    tvl: str
    lockupPeriod: str


class TransactionCost(BaseModel):
    total: str
    networkFee: str
    serviceFee: str
    exchangeCost: str | None = None


class TransactionSummary(BaseModel):
    finalAmountUsd: str
    transactionCostUsd: TransactionCost
    totalUsd: str | None = None
    exchangeRatePercent: str | None = None


class TxPreview(BaseModel):
    success: bool
    id: str
    signUrl: str
    fromToken: TokenInfo | None = None
    depositToken: TokenInfo
    yieldStrategy: YieldStrategy
    transactionSummary: TransactionSummary


Participant = Literal["entity_extractor", "schema_validator", "clarifier", "transactor"]


class AgentState(BaseModel):
    conversation: Annotated[Conversation[Participant], conversation_reducer]
    user_utterance: str
    intent_classification: str
    next_node: str | None = None
    revised_utterance: str | None = None
    extracted_entities: ExtractedEntities | None = None
    transaction_request: EarnRequest | None = None
    sign_url: str | None = None
    is_run_complete: bool = False

    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
    }

    def __init__(self, **data):
        super().__init__(**data)
        if self.next_node is None:
            self.next_node = "default"


CONVERT_TOKEN_ENTITIES = [
    "deposit_token",
    "deposit_chain",
    "amount",
    "from_token",
    "from_chain",
]


class EarnAgentTeam(AgentTeam):

    def __init__(
        self,
        on_complete: Callable[[], Any],
        store_transaction_info: Any,
        user_chat_id: str,
    ):
        super().__init__(on_complete)
        self._init_graph()
        self._store_transaction_info = store_transaction_info
        self._user_chat_id = user_chat_id

    async def _run_conversation(
        self, message: str, context: list[ChatCompletionMessageParam] | None = None
    ):

        self._send_activity_update("Understanding your earn request...")

        participants = list(get_args(Participant))

        await self._run_graph(
            self._app, self._config, message, participants=participants
        )

    async def _entity_extractor_action(self, state: AgentState):
        self._send_activity_update("Reading your transaction details...")

        utterance = (
            state.user_utterance
            if state.revised_utterance is None
            else f"Original: {state.user_utterance}\nClarified: {state.revised_utterance}"
        )
        additional_context = f"- Typically any chain mentioned can be assumed to be the from_chain unless specified otherwise\n\n- The token that is being used to earn is always the deposit_token\n\nIntent Classification: {state.intent_classification}"
        entity_extractor_context = get_context(state.conversation, "entity_extractor")
        [extracted_entities, reasoning] = await extract_entities(
            utterance,
            CONVERT_TOKEN_ENTITIES,
            additional_context,
            entity_extractor_context,
        )

        rich.print(f"reasoning: {reasoning}")
        rich.print(f"extracted_entities: {extracted_entities}")

        return {
            "extracted_entities": extracted_entities,
        }

    # TODO: Error needs to trigger on_complete and stop this agent team

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

    async def _get_linked_token_address(
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
        return token_match["entity"]["address"]

    async def _get_linked_entities(
        self, schema: EarnSchema
    ) -> tuple[str | None, str | None, str, str]:
        async def link_from():
            if schema.from_chain is None and schema.from_token is not None:
                self._send_activity_update(
                    f"Matching '{schema.from_token.named_entity}' with known abstract tokens..."
                )
                linked_token_symbol = await self._get_linked_abstract_token_symbol(
                    schema.from_token.named_entity
                )
                return None, linked_token_symbol
            if schema.from_chain is None or schema.from_token is None:
                return None, None
            from_chain_entity = schema.from_chain.named_entity
            self._send_activity_update(
                f"Matching '{from_chain_entity}' with known chains..."
            )
            linked_from_chain_id = await self._get_linked_chain_id(from_chain_entity)
            from_token_entity = schema.from_token.named_entity
            self._send_activity_update(
                f"Matching '{from_token_entity}' with known tokens..."
            )
            linked_from_token_address = await self._get_linked_token_address(
                from_token_entity,
                linked_from_chain_id,
                from_chain_entity,
            )
            return linked_from_chain_id, linked_from_token_address

        async def link_deposit():
            if schema.deposit_chain is None:
                self._send_activity_update(
                    f"Matching '{schema.deposit_token.named_entity}' with known abstract tokens..."
                )
                linked_token_symbol = await self._get_linked_abstract_token_symbol(
                    schema.deposit_token.named_entity
                )
                return None, linked_token_symbol
            deposit_chain_entity = schema.deposit_chain.named_entity
            self._send_activity_update(
                f"Matching '{deposit_chain_entity}' with known chains..."
            )
            linked_deposit_chain_id = await self._get_linked_chain_id(
                deposit_chain_entity
            )
            rich.print(f"linked_deposit_chain_id: {linked_deposit_chain_id}")
            deposit_token_entity = schema.deposit_token.named_entity
            self._send_activity_update(
                f"Matching '{deposit_token_entity}' with known tokens..."
            )
            linked_deposit_token_address = await self._get_linked_token_address(
                deposit_token_entity,
                linked_deposit_chain_id,
                deposit_chain_entity,
            )
            rich.print(f"linked_deposit_token_address: {linked_deposit_token_address}")
            return linked_deposit_chain_id, linked_deposit_token_address

        results = await asyncio.gather(
            link_from(), link_deposit(), return_exceptions=True
        )

        errors = [r for r in results if isinstance(r, BaseException)]
        if errors:
            raise ValueError(str(errors))

        valid_results = [r for r in results if not isinstance(r, BaseException)]
        expected_results = 2
        if len(valid_results) != expected_results:
            msg = f"Expected {expected_results} valid results, but got {len(valid_results)}"
            raise ValueError(msg)

        return valid_results[0] + valid_results[1]

    async def _schema_validator_action(self, state: AgentState):
        try:
            if state.extracted_entities is None:
                msg = "Extracted entities are empty or not present."
                raise ValueError(msg)
            self._send_activity_update("Verifying you have everything needed...")
            schema = convert_to_schema(EarnSchema, state.extracted_entities)
            (
                linked_from_chain_id,
                linked_from_token_id,
                linked_to_chain_id,
                linked_to_token_id,
            ) = await self._get_linked_entities(schema)

            rich.print(f"linked_to_chain_id: {linked_to_chain_id}")
            rich.print(f"linked_to_token_id: {linked_to_token_id}")
            rich.print(f"linked_from_chain_id: {linked_from_chain_id}")
            rich.print(f"linked_from_token_id: {linked_from_token_id}")

            self._send_activity_update("Finding the best yield strategy...")
            best_yield_strategy = await get_best_yield_strategy(
                linked_to_token_id, linked_to_chain_id
            )

            rich.print(f"best_yield_strategy: {best_yield_strategy}")

            if best_yield_strategy is None:
                msg = (
                    f"No yield strategy found for {schema.deposit_token.named_entity} ({linked_to_token_id}) on the {schema.deposit_chain.named_entity} ({linked_to_chain_id}) chain"
                    if schema.deposit_chain is not None
                    else f"No yield strategy found for {schema.deposit_token.named_entity} ({linked_to_token_id})"
                )
                raise ValueError(msg)

            self._best_yield_strategy = best_yield_strategy

            from_token = (
                FromToken(
                    id=linked_from_token_id,
                    chainId=linked_from_chain_id,
                    amount=PositiveAmount(schema.amount.named_entity),
                )
                if linked_from_token_id is not None and linked_from_chain_id is not None
                else None
            )

            deposit_token = DepositToken(
                id=best_yield_strategy.token_address,
                chainId=best_yield_strategy.chain_id,
                amount=(
                    PositiveAmount(schema.amount.named_entity)
                    if linked_from_token_id is None
                    else None
                ),
            )

            transaction_request = EarnRequest(
                fromToken=from_token,
                depositToken=deposit_token,
                strategyId=self._best_yield_strategy.id,
                userChatId=self._user_chat_id,
                storeTransaction=self._store_transaction_info,
            )

            return {"transaction_request": transaction_request}
        except ValidationError as e:
            rich.print(e)
            message = e.json(
                indent=2, include_url=False, include_context=True, include_input=False
            )
            return {
                "conversation": {
                    "history": [
                        {
                            "sender_name": "schema_validator",
                            "content": message,
                            "is_visible_to_user": False,
                        }
                    ]
                },
                "next_node": "clarifier",
            }
        except ValueError as e:
            rich.print(e)
            return {
                "conversation": {
                    "history": [
                        {
                            "sender_name": "schema_validator",
                            "content": str(e),
                            "is_visible_to_user": False,
                        }
                    ]
                },
                "next_node": "clarifier",
            }
        except Exception as e:
            rich.print(f"ERROR: {e}")
            raise e

    async def _clarifier_action(self, state: AgentState):
        clarifier_context = get_context(state.conversation, "clarifier")
        last_message = clarifier_context[-1].get("content", None)
        if not isinstance(last_message, str):
            msg = "Message content is empty or not present."
            raise ValueError(msg)
        provided_info = (
            ""
            if state.extracted_entities is None
            else json.dumps(flatten_classified_entities(state.extracted_entities))
        )
        clarifier_response = await get_clarifier_response(
            state.user_utterance,
            state.intent_classification,
            provided_info,
            last_message,
            clarifier_context,
        )
        assistant_message = (
            clarifier_response.revised_utterance
            if clarifier_response.questions is None
            else clarifier_response.questions
        )

        return {
            "conversation": {
                "history": [
                    {
                        "sender_name": "clarifier",
                        "content": assistant_message,
                        "is_visible_to_user": clarifier_response.next_node
                        == "ask_user",
                    }
                ]
            },
            "next_node": clarifier_response.next_node,
            "revised_utterance": clarifier_response.revised_utterance,
        }

    async def _prepare_transaction_preview(self, request: EarnRequest):
        # NOTE: ERC-7683 Intent standard might be returned here in the future
        url = f"{SETTINGS.transaction_service_url}/earn/deposit/preview"
        async with httpx.AsyncClient(http2=True, timeout=65) as client:
            response = await client.post(url, json=request.model_dump())

        response_json = response.json()
        if not response_json["success"]:
            msg = f"{response_json['message']}: {response_json['error']}"
            raise Exception(msg)

        try:
            return TxPreview.model_validate(response_json)
        except ValidationError as err:
            msg = "Failed processing response, try again."
            raise Exception(msg) from err

    async def _transactor_action(self, state: AgentState):
        self._send_activity_update("Preparing earn transaction...")

        try:
            if state.transaction_request is None:
                msg = "Transaction request not found"
                raise ValueError(msg)
            transaction_preview = await self._prepare_transaction_preview(
                state.transaction_request
            )
            if transaction_preview is None:
                msg = "Transaction preview not found"
                raise Exception(msg)
        except Exception as e:
            error_message = str(e) if str(e) else str(type(e))
            message = f"""Failed to prepare transaction. 😔

Details: {error_message}"""
            raise Exception(message) from e

        self.sign_url = transaction_preview.signUrl

        from_token = transaction_preview.fromToken
        to_token = transaction_preview.depositToken
        strategy = transaction_preview.yieldStrategy
        strategy_tvl_usd = format_currency_string(strategy.tvl)
        final_amount_usd = format_currency_string(
            transaction_preview.transactionSummary.finalAmountUsd
        )
        exchange_rate_percent = (
            transaction_preview.transactionSummary.exchangeRatePercent
        )
        fees_usd = format_currency_string(
            transaction_preview.transactionSummary.transactionCostUsd.total, 4
        )
        total_usd = (
            format_currency_string(transaction_preview.transactionSummary.totalUsd)
            if transaction_preview.transactionSummary.totalUsd
            else None
        )

        convert_step_text = (
            f"""
↩️ **Convert From ・** {from_token.amount} [{from_token.symbol}]({from_token.explorerUri}) _({from_token.chainName})_"""
            if from_token is not None
            else ""
        )

        response_message = f"""Transaction *{transaction_preview.id}* is ready for you to sign! 💸
{convert_step_text}
⤵️ **[${final_amount_usd}] Deposit ・** {to_token.amount} [{to_token.symbol}]({to_token.explorerUri}) _({to_token.chainName})_
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;├ **{strategy.name}** ┈ {strategy.apy}% APY _({self._best_yield_strategy.wrapped_protocol_name or self._best_yield_strategy.protocol_name})_
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;╰ ${strategy_tvl_usd} TVL ┈ {strategy.lockupPeriod}d lockup

╭ Fees&Tab;${fees_usd}
╰ Total&Tab;${total_usd}

🔏 Sign transaction (coming soon)"""

        return {
            "conversation": {
                "history": [
                    {
                        "sender_name": "transactor",
                        "content": response_message,
                        "is_visible_to_user": True,
                    }
                ]
            },
            "next_node": "default",
            "sign_url": transaction_preview.signUrl,
            "is_run_complete": True,
        }

    def _ask_user_action(self, _: AgentState):
        pass

    def _choose_next_node(self, state: AgentState):
        return state.next_node

    def _init_graph(self):
        self._config: RunnableConfig = {"configurable": {"thread_id": 42}}
        self._graph = StateGraph(AgentState)

        self._graph.add_node("entity_extractor", self._entity_extractor_action)
        self._graph.add_node("schema_validator", self._schema_validator_action)
        self._graph.add_node("clarifier", self._clarifier_action)
        self._graph.add_node("ask_user", self._ask_user_action)
        self._graph.add_node("transactor", self._transactor_action)

        self._graph.set_entry_point("entity_extractor")

        self._graph.add_edge("entity_extractor", "schema_validator")
        self._graph.add_conditional_edges(
            "schema_validator",
            self._choose_next_node,
            {
                "clarifier": "clarifier",
                "default": "transactor",
            },
        )
        self._graph.add_conditional_edges(
            "clarifier",
            self._choose_next_node,
            {
                "ask_user": "ask_user",
                "default": "entity_extractor",
            },
        )
        self._graph.add_edge("ask_user", "clarifier")
        self._graph.add_edge("transactor", END)

        checkpointer = MemorySaver()

        self._app = self._graph.compile(
            checkpointer=checkpointer, interrupt_before=["ask_user"]
        )
