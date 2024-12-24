import asyncio
import json
from collections.abc import Callable
from typing import Annotated, Any, Literal, get_args

import httpx
import rich
from langchain_core.runnables.config import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import NodeInterrupt
from langgraph.graph import END, StateGraph
from openai.types.chat import (
    ChatCompletionMessageParam,
)
from pydantic import BaseModel, ValidationError, model_validator
from rich import print

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
from ember_agents.common.transaction import Token, link_chain, link_token
from ember_agents.common.utils import format_transaction_url
from ember_agents.common.validators import PositiveAmount
from ember_agents.settings import SETTINGS


class ConvertTokenAmount(BaseModel):
    from_amount: InferredEntity[float] | None = None
    to_amount: InferredEntity[float] | None = None

    @model_validator(mode="after")
    def check_amounts(self):
        if (self.from_amount is None and self.to_amount is None) or (
            self.from_amount is not None and self.to_amount is not None
        ):
            msg = "Missing either 'from_amount' or 'to_amount'. Must provide only one of 'from_amount' or 'to_amount'. Do not include both."
            raise ValueError(msg)
        return self


class ConvertTokenSchema(BaseModel):
    amount: ConvertTokenAmount
    from_token: InferredEntity[str]
    from_network: InferredEntity[str]
    to_token: InferredEntity[str]
    to_network: InferredEntity[str]

    @classmethod
    def model_validate(cls, obj: Any, *args, **kwargs) -> "ConvertTokenSchema":
        if isinstance(obj, dict):
            amount_data = {}
            if "from_amount" in obj:
                amount_data["from_amount"] = obj.pop("from_amount")
            if "to_amount" in obj:
                amount_data["to_amount"] = obj.pop("to_amount")

            obj["amount"] = amount_data

        return super().model_validate(obj, *args, **kwargs)

    """@classmethod
    def model_construct(cls, *args: Any, **kwargs: Any) -> "ConvertTokenSchema":
        if "from_amount" in kwargs or "to_amount" in kwargs:
            amount_data = {}
            if "from_amount" in kwargs:
                amount_data["from_amount"] = kwargs.pop("from_amount")
            if "to_amount" in kwargs:
                amount_data["to_amount"] = kwargs.pop("to_amount")

            kwargs["amount"] = amount_data

        return super().model_construct(*args, **kwargs)"""


class TokenConvertTo(BaseModel):
    """Request for doing cross chain convert"""

    network_id: int
    token: Token


class ConvertRequest(BaseModel):
    """Request for doing cross chain convert"""

    amount: PositiveAmount
    token: Token
    user_chat_id: str
    network_id: int
    to: TokenConvertTo
    type: str
    store_transaction: Any
    user_address: str | None


class TxPreview(BaseModel):
    id: str
    sign_url: str
    network_name: str
    token_amount: str
    token_symbol: str
    token_explorer_url: str
    to_network_name: str
    to_token_amount: str
    to_token_symbol: str
    to_token_explorer_url: str
    transaction_hash: str | None = None


Participant = Literal["entity_extractor", "schema_validator", "clarifier", "transactor"]


class AgentState(BaseModel):
    conversation: Annotated[Conversation[Participant], conversation_reducer]
    user_utterance: str
    intent_classification: str
    next_node: str | None = None
    revised_utterance: str | None = None
    extracted_entities: ExtractedEntities | None = None
    transaction_request: ConvertRequest | None = None
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
    "from_amount",
    "from_token",
    "from_network",
    "to_amount",
    "to_token",
    "to_network",
]


class ConvertTokenAgentTeam(AgentTeam):

    def __init__(
        self,
        on_complete: Callable[[], Any],
        store_transaction_info: Any,
        user_chat_id: str,
        user_address: str | None,
    ):
        super().__init__(on_complete)
        self._init_graph()
        self._store_transaction_info = store_transaction_info
        self._user_chat_id = user_chat_id
        self._user_address = user_address

    async def _run_conversation(
        self, message: str, context: list[ChatCompletionMessageParam] | None = None
    ):

        self._send_activity_update("Understanding your convert request...")

        participants = list(get_args(Participant))

        await self._run_graph(
            self._app, self._config, message, participants=participants
        )

    async def _entity_extractor_action(self, state: AgentState):
        utterance = (
            state.user_utterance
            if state.revised_utterance is None
            else f"Original: {state.user_utterance}\nClarified: {state.revised_utterance}"
        )
        intent_classification = f"Intent Classification: {state.intent_classification}"
        entity_extractor_context = get_context(state.conversation, "entity_extractor")
        [extracted_entities, reasoning] = await extract_entities(
            utterance,
            CONVERT_TOKEN_ENTITIES,
            intent_classification,
            entity_extractor_context,
        )

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
        return chain_match["entity"]["chain_id"]

    async def _get_linked_token(
        self, token: str, chain_id: str, chain_name: str
    ) -> Token:
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
        return Token.model_validate(token_match["entity"])

    async def _get_linked_entities(self, schema: ConvertTokenSchema):
        async def link_from():
            from_network_entity = schema.from_network.named_entity
            linked_from_chain_id = await self._get_linked_chain_id(from_network_entity)
            linked_from_token = await self._get_linked_token(
                schema.from_token.named_entity,
                linked_from_chain_id,
                from_network_entity,
            )
            return linked_from_chain_id, linked_from_token

        async def link_to():
            to_network_entity = schema.to_network.named_entity
            linked_to_chain_id = await self._get_linked_chain_id(to_network_entity)
            linked_to_token = await self._get_linked_token(
                schema.to_token.named_entity, linked_to_chain_id, to_network_entity
            )
            return linked_to_chain_id, linked_to_token

        results = await asyncio.gather(link_from(), link_to(), return_exceptions=True)

        # Check each result individually
        if isinstance(results[0], BaseException):
            msg = f"Error in source chain/token: {results[0]!s}"
            raise ValueError(msg) from results[0]
        if isinstance(results[1], BaseException):
            msg = f"Error in destination chain/token: {results[1]!s}"
            raise ValueError(msg) from results[1]

        return results[0] + results[1]

    async def _schema_validator_action(self, state: AgentState):
        try:
            if state.extracted_entities is None:
                msg = "Extracted entities are empty or not present."
                raise ValueError(msg)
            schema = convert_to_schema(ConvertTokenSchema, state.extracted_entities)
            (
                linked_from_chain_id,
                linked_from_token,
                linked_to_chain_id,
                linked_to_token_address,
            ) = await self._get_linked_entities(schema)

            # rich.print(f"linked_to_chain_id: {linked_to_chain_id}")
            # rich.print(f"linked_to_token_address: {linked_to_token_address}")
            # rich.print(f"linked_from_chain_id: {linked_from_chain_id}")
            # rich.print(f"linked_from_token_address: {linked_from_token}")

            token_convert_to = TokenConvertTo(
                network_id=int(linked_to_chain_id),
                token=linked_to_token_address,
            )
            amount = (
                ("buy", schema.amount.to_amount.named_entity)
                if schema.amount.to_amount is not None
                else (
                    ("swap", schema.amount.from_amount.named_entity)
                    if schema.amount.from_amount is not None
                    else None
                )
            )
            if amount is None:
                msg = "Amount is not present."
                raise ValueError(msg)
            transaction_request = ConvertRequest(
                amount=str(amount[1]),
                token=linked_from_token,
                user_chat_id=self._user_chat_id,
                network_id=int(linked_from_chain_id),
                to=token_convert_to,
                type=amount[0],
                store_transaction=self._store_transaction_info,
                user_address=self._user_address,
            )
            return {"transaction_request": transaction_request}
        except ValidationError as e:
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
            print(f"ERROR: {e}")
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

    async def _prepare_transaction_preview(self, request: ConvertRequest):
        url = f"{SETTINGS.transaction_service_url}/swap/preview"
        async with httpx.AsyncClient(http2=True, timeout=65) as client:
            response = await client.post(url, json=request.model_dump(by_alias=True))

        response_json = response.json()
        if not response_json["success"]:
            raise Exception(response_json["message"])

        try:
            return TxPreview.model_validate(response_json)
        except ValidationError as err:
            msg = "Failed processing response, try again."
            raise Exception(msg) from err

    async def _transactor_action(self, state: AgentState):
        self._send_activity_update("Preparing convert token transaction...")

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
            rich.print(f"ERROR: {e}")
            error_message = str(e) if str(e) else str(type(e))
            message = f"""Failed to prepare transaction. 😔

Details: {error_message}"""
            raise NodeInterrupt(message) from e

        response_message = f"""Transaction *{transaction_preview.id}* is ready for you to sign! 💸

↩️ **Convert From ・** {transaction_preview.token_amount} [{transaction_preview.token_symbol}]({transaction_preview.token_explorer_url}) ({transaction_preview.network_name})
↪️ **To ・** {transaction_preview.to_token_amount} [{transaction_preview.to_token_symbol}]({transaction_preview.to_token_explorer_url}) ({transaction_preview.to_network_name})

🔏 {format_transaction_url(transaction_preview.sign_url)}"""

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
            "sign_url": transaction_preview.sign_url,
            "transaction_hash": transaction_preview.transaction_hash,
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
