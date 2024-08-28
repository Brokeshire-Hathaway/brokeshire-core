import asyncio
import json
import operator
from collections.abc import Callable
from typing import Annotated, Any

import httpx
from langchain_core.runnables.config import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from openai.types.chat import (
    ChatCompletionMessageParam,
)
from pydantic import BaseModel, ValidationError, field_validator, model_validator
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
from ember_agents.common.transaction import link_chain, link_token
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
    def model_validate(cls, obj: Any, *, strict: bool = False) -> "ConvertTokenSchema":
        if isinstance(obj, dict):
            amount_data = {}
            if "from_amount" in obj:
                amount_data["from_amount"] = obj.pop("from_amount")
            if "to_amount" in obj:
                amount_data["to_amount"] = obj.pop("to_amount")

            obj["amount"] = amount_data

        return super().model_validate(obj, strict=strict)

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
    token_address: str


class ConvertRequest(BaseModel):
    """Request for doing cross chain convert"""

    amount: PositiveAmount
    token_address: str
    user_chat_id: str
    network_id: int
    to: TokenConvertTo
    type: str
    store_transaction: Any


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


class AgentState(BaseModel):
    messages: Annotated[list[ChatCompletionMessageParam], operator.add]
    user_utterance: Annotated[str, operator.setitem]
    intent_classification: Annotated[str, operator.setitem]
    next_node: Annotated[str | None, operator.setitem] = None
    revised_utterance: Annotated[str | None, operator.setitem] = None
    extracted_entities: Annotated[ExtractedEntities | None, operator.setitem] = None
    transaction_request: Annotated[ConvertRequest | None, operator.setitem] = None
    sign_url: Annotated[str | None, operator.setitem] = None

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
    ):
        super().__init__(on_complete)
        self._init_graph()
        self._store_transaction_info = store_transaction_info
        self._user_chat_id = user_chat_id

    async def _run_conversation(
        self, message: str, context: list[ChatCompletionMessageParam] | None = None
    ):

        self._send_activity_update("Understanding your convert request...")

        async def stream_updates(graph_input: dict[str, Any] | Any):
            async for values in self._app.astream(
                graph_input, self._config, stream_mode="values"
            ):
                messages = values.get("messages")
                if messages is None or len(messages) == 0:
                    continue

                print(messages[-1])

                if values.get("next_node") == "ask_user":
                    return values["messages"][-1]["content"]

        try:
            intent_classification = "convert_token_action"
            graph_input = {
                "user_utterance": message,
                "intent_classification": intent_classification,
            }
            response = await stream_updates(graph_input)

            is_pending_interrupt = True
            while is_pending_interrupt:
                user_message_future = asyncio.create_task(self._get_human_messages())
                if isinstance(response, str):
                    self._send_team_response(response)
                user_message = await user_message_future
                node_name = "ask_user"
                state_values = {"messages": [{"role": "user", "content": user_message}]}
                self._app.update_state(
                    self._config,
                    state_values,
                    as_node=node_name,
                )
                # Manually print the user state update because it won't be printed by the stream
                print({node_name: state_values})

                response = await stream_updates(None)

                snapshot = self._app.get_state(self._config)
                sign_url = snapshot.values.get("sign_url")
                if sign_url is not None:
                    is_pending_interrupt = False
                    self._send_team_response(
                        snapshot.values["messages"][-1]["content"], sign_url
                    )

        except Exception as error:
            self._send_team_response(str(error))

    async def _entity_extractor_action(self, state: AgentState):
        utterance = (
            state.user_utterance
            if state.revised_utterance is None
            else f"Original: {state.user_utterance}\nClarified: {state.revised_utterance}"
        )
        intent_classification = f"Intent Classification: {state.intent_classification}"
        [extracted_entities, reasoning] = await extract_entities(
            utterance, CONVERT_TOKEN_ENTITIES, intent_classification
        )
        print(reasoning)
        return {
            "extracted_entities": extracted_entities,
        }

    # TODO: Error needs to trigger on_complete and stop this agent team

    async def _get_linked_chain_id(self, chain_name: str) -> int:
        # TODO: Mock link_chain for testing
        linked_from_chain_results = await link_chain(chain_name)
        chain_llm_matches = linked_from_chain_results["llm_matches"]
        if chain_llm_matches is None or len(chain_llm_matches) == 0:
            msg = f"{chain_name} is not a supported chain"
            raise ValueError(msg)
        chain_match = chain_llm_matches[0]
        chain_confidence_threshold = 70
        if chain_match["confidence_percentage"] < chain_confidence_threshold:
            msg = f"You entered '{chain_name}', but did you mean '{chain_match['entity']['name']}'?"
            raise ValueError(msg)
        return chain_match["entity"]["id"]

    async def _get_linked_token_address(
        self, token: str, chain_id: int, chain_name: str
    ) -> str:
        # TODO: Mock link_token for testing
        linked_from_token_results = await link_token(token, chain_id)
        token_fuzzy_matches = linked_from_token_results["fuzzy_matches"]
        if token_fuzzy_matches is None or len(token_fuzzy_matches) == 0:
            msg = f"{token} is not a supported token on chain {chain_name}"
            raise ValueError(msg)
        token_llm_matches = linked_from_token_results["llm_matches"]
        token_match = (
            token_fuzzy_matches[0]
            if token_llm_matches is None or len(token_llm_matches) == 0
            else token_llm_matches[0]
        )
        token_confidence_threshold = 60
        if token_match["confidence_percentage"] < token_confidence_threshold:
            msg = f"You entered '{token}', but did you mean '{token_match['entity']['name']}'?"
            raise ValueError(msg)
        return token_match["entity"]["address"]

    async def _get_linked_entities(self, schema: ConvertTokenSchema):
        async def link_from():
            from_network_entity = schema.from_network.named_entity
            linked_from_chain_id = await self._get_linked_chain_id(from_network_entity)
            linked_from_token_address = await self._get_linked_token_address(
                schema.from_token.named_entity,
                linked_from_chain_id,
                from_network_entity,
            )
            return linked_from_chain_id, linked_from_token_address

        async def link_to():
            to_network_entity = schema.to_network.named_entity
            linked_to_chain_id = await self._get_linked_chain_id(to_network_entity)
            linked_to_token_address = await self._get_linked_token_address(
                schema.to_token.named_entity, linked_to_chain_id, to_network_entity
            )
            return linked_to_chain_id, linked_to_token_address

        results = await asyncio.gather(link_from(), link_to(), return_exceptions=True)

        errors = [r for r in results if isinstance(r, BaseException)]
        if errors:
            msg = f"Errors occurred: {errors}"
            raise Exception(msg)

        valid_results = [r for r in results if not isinstance(r, BaseException)]
        if len(valid_results) != 2:
            msg = f"Expected 2 valid results, but got {len(valid_results)}"
            raise ValueError(msg)

        return valid_results[0] + valid_results[1]

    async def _schema_validator_action(self, state: AgentState):
        try:
            if state.extracted_entities is None:
                msg = "Extracted entities are empty or not present."
                raise ValueError(msg)
            schema = convert_to_schema(ConvertTokenSchema, state.extracted_entities)
            (
                linked_from_chain_id,
                linked_from_token_address,
                linked_to_chain_id,
                linked_to_token_address,
            ) = await self._get_linked_entities(schema)
            token_convert_to = TokenConvertTo(
                network_id=linked_to_chain_id,
                token_address=linked_to_token_address,
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
                amount=PositiveAmount(amount[1]),
                token_address=linked_from_token_address,
                user_chat_id=self._user_chat_id,
                network_id=linked_from_chain_id,
                to=token_convert_to,
                type=amount[0],
                store_transaction=self._store_transaction_info,
            )
            return {"transaction_request": transaction_request}
        except ValidationError as e:
            message = e.json(
                indent=2, include_url=False, include_context=True, include_input=False
            )
            return {
                "messages": [{"role": "user", "content": message}],
                "next_node": "clarifier",
            }

    async def _clarifier_action(self, state: AgentState):
        last_message = state.messages[-1].get("content", None)
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
            state.messages,
        )
        assistant_message = (
            clarifier_response.revised_utterance
            if clarifier_response.questions is None
            else clarifier_response.questions
        )
        return {
            "messages": [{"role": "assistant", "content": assistant_message}],
            "next_node": clarifier_response.next_node,
            "revised_utterance": clarifier_response.revised_utterance,
        }

    async def _prepare_transaction_preview(self, request: ConvertRequest):
        print("PREPARE TRANSACTION PREVIEW")
        print(request)
        print(request.model_dump())
        url = f"{SETTINGS.transaction_service_url}/swap/preview"
        async with httpx.AsyncClient(http2=True, timeout=65) as client:
            response = await client.post(url, json=request.model_dump())

        response_json = response.json()
        if not response_json["success"]:
            print(response_json)
            raise Exception(response_json["message"])

        try:
            print(response_json)
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
            print(state.transaction_request)
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

        self.sign_url = transaction_preview.sign_url
        response_message = f"""Transaction *{transaction_preview.id}* is ready for you to sign! 💸

↩️ **Convert From ・** {transaction_preview.token_amount} [{transaction_preview.token_symbol}]({transaction_preview.token_explorer_url}) ({transaction_preview.network_name})
↪️ **To ・** {transaction_preview.to_token_amount} [{transaction_preview.to_token_symbol}]({transaction_preview.to_token_explorer_url}) ({transaction_preview.to_network_name})

🔏 **[Sign here]({transaction_preview.sign_url})** to complete your transaction."""

        return {
            "messages": [{"role": "assistant", "content": response_message}],
            "next_node": "default",
            "sign_url": transaction_preview.sign_url,
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
