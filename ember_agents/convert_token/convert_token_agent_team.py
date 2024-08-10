import operator
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from langchain_core.runnables.config import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from openai.types.chat import (
    ChatCompletionMessageParam,
)
from pydantic import BaseModel, ValidationError, model_validator
from rich import print

from ember_agents.common.agents.clarifier import get_clarifier_response
from ember_agents.common.agents.entity_extractor import (
    ExtractedEntities,
    extract_entities,
)
from ember_agents.common.agents.schema_validator import InferredValue, convert_to_schema


class ConvertTokenAmount(BaseModel):
    from_amount: InferredValue[float] | None = None
    to_amount: InferredValue[float] | None = None

    @model_validator(mode="after")
    def check_amounts(self):
        if (self.from_amount is None and self.to_amount is None) or (
            self.from_amount is not None and self.to_amount is not None
        ):
            msg = "Either 'from_amount' or 'to_amount' must be provided, but not both."
            raise ValueError(msg)
        return self


class ConvertTokenSchema(BaseModel):
    amount: ConvertTokenAmount
    from_token: InferredValue[str]
    from_network: InferredValue[str]
    to_token: InferredValue[str]
    to_network: InferredValue[str]

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


class AgentState(BaseModel):
    messages: Annotated[list[ChatCompletionMessageParam], operator.add]
    user_utterance: Annotated[str, operator.setitem]
    intent_classification: Annotated[str, operator.setitem]
    next_node: Annotated[str | None, operator.setitem] = None
    revised_utterance: Annotated[str | None, operator.setitem] = None
    extracted_entities: Annotated[ExtractedEntities | None, operator.setitem] = None
    schema: Annotated[ConvertTokenSchema | None, operator.setitem] = None

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


convert_token = StateGraph(AgentState)


async def entity_extractor_action(state: AgentState):
    utterance = (
        state.user_utterance
        if state.revised_utterance is None
        else state.revised_utterance
    )
    intent_classification = f"Intent Classification: {state.intent_classification}"
    extracted_entities = await extract_entities(
        utterance, CONVERT_TOKEN_ENTITIES, intent_classification
    )
    print(f"Extracted entities: {extracted_entities}")
    return {
        "extracted_entities": extracted_entities,
    }


def schema_validator_action(state: AgentState):
    try:
        if state.extracted_entities is None:
            msg = "Extracted entities are empty or not present."
            raise ValueError(msg)
        schema = convert_to_schema(ConvertTokenSchema, state.extracted_entities)
        return {"schema": schema, "next_node": "default"}
    except ValidationError as e:
        return {
            "messages": [{"role": "user", "content": str(e)}],
            "next_node": "clarifier",
        }


async def clarifier_action(state: AgentState):
    last_message = state.messages[-1].get("content", None)
    if not isinstance(last_message, str):
        msg = "Message content is empty or not present."
        raise ValueError(msg)
    provided_info = (
        ""
        if state.extracted_entities is None
        else convert_to_schema(
            ConvertTokenSchema, state.extracted_entities, validate=False
        ).model_dump_json(indent=2)
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


async def transaction_action(state: AgentState):
    pass


def ask_user_action(state: AgentState):
    pass


def choose_next_node(state: AgentState):
    return state.next_node


convert_token.add_node("entity_extractor", entity_extractor_action)
convert_token.add_node("schema_validator", schema_validator_action)
convert_token.add_node("clarifier", clarifier_action)
convert_token.add_node("ask_user", ask_user_action)
convert_token.add_node("transaction", transaction_action)


convert_token.set_entry_point("entity_extractor")


convert_token.add_edge("entity_extractor", "schema_validator")
convert_token.add_conditional_edges(
    "schema_validator",
    choose_next_node,
    {
        "clarifier": "clarifier",
        "default": "transaction",
    },
)
convert_token.add_conditional_edges(
    "clarifier",
    choose_next_node,
    {
        "ask_user": "ask_user",
        "default": "entity_extractor",
    },
)
convert_token.add_edge("ask_user", "clarifier")
convert_token.add_edge("transaction", END)


checkpointer = MemorySaver()


app = convert_token.compile(checkpointer=checkpointer, interrupt_before=["ask_user"])


async def convert_token_agent_team(
    user_message: str, ask_user: Callable[[], Awaitable[str]]
):
    config: RunnableConfig = {"configurable": {"thread_id": 42}}

    async def stream_updates(graph_input: dict[str, Any] | Any):
        async for updates in app.astream(graph_input, config, stream_mode="updates"):
            print(updates)

    intent_classification = "convert_token_action"
    graph_input = {
        "user_utterance": user_message,
        "intent_classification": intent_classification,
    }
    await stream_updates(graph_input)

    is_pending_interrupt = True
    while is_pending_interrupt:
        user_message = await ask_user()
        node_name = "ask_user"
        state_values = {"messages": [{"role": "user", "content": user_message}]}
        app.update_state(
            config,
            state_values,
            as_node=node_name,
        )
        # Manually print the user state update because it won't be printed by the stream
        print({node_name: state_values})

        await stream_updates(None)

        snapshot = app.get_state(config)
        if "schema" in snapshot.values and snapshot.values["schema"] is not None:
            is_pending_interrupt = False

    return "Sign to complete the transaction"
