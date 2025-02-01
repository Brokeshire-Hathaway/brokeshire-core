import json
from collections.abc import Callable
from functools import partial
from typing import Any

import rich
from langgraph.errors import NodeInterrupt
from openai.types.chat import ChatCompletionMessageParam

from brokeshire_agents.agent_router.intent_classifier import (
    INTENT,
    ClassifiedIntent,
    classify_intent,
)
from brokeshire_agents.common.agent_team import AgentTeam
from brokeshire_agents.common.broke_twitter.broke_twitter import BrokeTwitterAgentTeam
from brokeshire_agents.common.types import MessageType
from brokeshire_agents.convert_token.convert_token_agent_team import (
    ConvertTokenAgentTeam,
)
from brokeshire_agents.earn.earn_agent_team import EarnAgentTeam
from brokeshire_agents.education.education import EducationAgentTeam
from brokeshire_agents.send_token.send import SendTokenAgentTeam
from brokeshire_agents.token_tech_analysis.token_ta_agent_team import TokenTaAgentTeam


class AgentTeamSessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, AgentTeam] = {}

    def create_session(self, session_id: str, agent_team: AgentTeam):
        rich.print(f"Creating session: {session_id}")
        if session_id in self._sessions:
            rich.print(f"Session already exists: {session_id}")
            self.remove_session(session_id)
        self._sessions[session_id] = agent_team

    def get_session(self, session_id: str):
        rich.print(f"Getting session: {session_id}")
        agent_team = self._sessions.get(session_id)
        return agent_team

    def remove_session(self, session_id: str):
        rich.print(f"Removing session: {session_id}")
        if session_id in self._sessions:
            del self._sessions[session_id]
            return

        rich.print(f"Session ID ({session_id}) does not exist")

    def get_session_id(self, sender_did: str, thread_id: str, client_id: int) -> str:
        rich.print(f"Getting session ID: {sender_did}:{thread_id}:{client_id}")
        return f"{sender_did}:{thread_id}:{client_id}"


# TODO: Track sessions using a user id and thread id.
#       (A thread represents a private chat, public group, or chat thread)

# TODO: Each time an agent team ends their session with the user, they should return
#       a summary of their conversation with the user so that it can be included in
#       the top level conversation for context.


class Router:
    def __init__(
        self,
        session_manager: AgentTeamSessionManager,
        intents: list[INTENT] | None,
        requested_intents: list[INTENT] | None,
    ):
        self._session_manager = session_manager
        self._intents = intents
        self._requested_intents = requested_intents

    async def send(
        self,
        user_chat_id: str,
        store_transaction_info: Any,
        session_id: str,
        message: str,
        message_type: MessageType,
        activity: Callable[[str], None] | None = None,
        context: list[ChatCompletionMessageParam] | None = None,
        user_address: str | None = None,
        _retry_count: int = 0,
        _max_retries: int = 3,
        required_route: INTENT | None = None,
    ):

        # ===================================================
        # Checking required_route in params and if exist then creating classified intent instance from it
        # ===================================================
        if required_route is not None:
            session_id = f"{session_id}:{required_route}"
            intent = ClassifiedIntent(name=required_route, linear_probability=0.9)
        else:
            intent = await classify_intent(message)

        route = intent.name
        rich.print(f"Intent Name: {route}")
        if self._requested_intents is not None and route not in self._requested_intents:
            msg = f"Requested intents {', '.join(self._requested_intents)} mismatches with matched intent {route}"
            raise ValueError(msg)

        agent_team = self._get_agent_team_session(session_id)
        rich.print(f"Agent Team: {agent_team}")
        if route == "terminate" or agent_team is None:
            agent_team = self._create_agent_team_session(
                session_id, route, store_transaction_info, user_chat_id, user_address
            )
        if activity is not None:
            agent_team.get_activity_updates(activity)

        try:
            response = await agent_team.send(message, message_type, context=context)
            return response
        except NodeInterrupt as interrupt_tuple:
            if _retry_count >= _max_retries:
                raise ValueError(
                    f"Maximum number of retries ({_max_retries}) exceeded while handling NodeInterrupt"
                )

            if not interrupt_tuple.args or len(interrupt_tuple.args) != 1:
                raise interrupt_tuple

            interrupt = interrupt_tuple.args[0][0]
            self._session_manager.remove_session(session_id)

            try:
                interrupt_data = json.loads(interrupt.value)
                new_route = interrupt_data.get("intent")
                new_message = interrupt_data.get("message")
            except json.JSONDecodeError as e:
                rich.print(f"Failed to parse interrupt data as JSON: {e}")
                raise

            # ===================================================
            # returning recommendations inf the provided message scope is out of the requested route
            # ===================================================
            if required_route is not None:
                recommended_intent = await classify_intent(message)
                recommended_intent = recommended_intent.name

                if recommended_intent in [
                    "capabilities_query",
                    "advice_query",
                    "unclear",
                    "out_of_scope",
                    "terminate",
                    None,
                ]:
                    recommended_intent = "explanation_query"
                elif recommended_intent in ["crypto_price_query", "market_news_query"]:
                    recommended_intent = "token_analysis_query"

                # =============================================================
                # needs to be scaled further to suggest different workflow
                # =============================================================
                route_recommendations = [recommended_intent]

                response = {}
                response["status"] = "done"
                response["message"] = (
                    "Out of Scope! Please choose from the below workflow to proceed this action."
                )
                response["intent_suggestions"] = None
                response["expression_suggestions"] = None
                response["sign_tx_url"] = None
                response["transaction_hash"] = None
                response["route_recommendations"] = route_recommendations
                return response

            # Recursively call send() with incremented retry count
            return await self.send(
                user_chat_id=user_chat_id,
                store_transaction_info=store_transaction_info,
                session_id=session_id,
                message=new_message,
                message_type=message_type,
                activity=activity,
                context=context,
                user_address=user_address,
                _retry_count=_retry_count + 1,
                _max_retries=_max_retries,
            )

    def _create_agent_team_session(
        self,
        session_id: str,
        route: INTENT | None,
        store_transaction_info: Any,
        user_chat_id: str,
        user_address: str | None,
    ) -> AgentTeam:
        if self._intents is not None:
            route = route if route is not None and route in self._intents else None
        on_complete = partial(self._session_manager.remove_session, session_id)
        match route:
            case "transfer_crypto_action":
                agent_team = SendTokenAgentTeam(
                    on_complete, store_transaction_info, user_chat_id, user_address
                )
            case "convert_crypto_action":
                agent_team = ConvertTokenAgentTeam(
                    on_complete, store_transaction_info, user_chat_id, user_address
                )
            case "earn_crypto_action":
                agent_team = EarnAgentTeam(
                    on_complete, store_transaction_info, user_chat_id
                )
            case "token_analysis_query" | "crypto_price_query" | "market_news_query":
                agent_team = TokenTaAgentTeam(on_complete, user_chat_id)
            case "broke_twitter_query":
                agent_team = BrokeTwitterAgentTeam(on_complete)
            case (
                "explanation_query"
                | "capabilities_query"
                | "advice_query"
                | "unclear"
                | "out_of_scope"
                | "terminate"
                | None
                | _
            ):
                agent_team = EducationAgentTeam(on_complete)
        self._session_manager.create_session(session_id, agent_team)
        return agent_team

    def _get_agent_team_session(self, session_id: str) -> AgentTeam | None:
        return self._session_manager.get_session(session_id)
