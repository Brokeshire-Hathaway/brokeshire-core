from collections.abc import Callable
from functools import partial
from typing import Any

from openai.types.chat import ChatCompletionMessageParam

from ember_agents.agent_router.intent_classifier import INTENT, classify_intent
from ember_agents.common.agent_team import AgentTeam
from ember_agents.education.education import EducationAgentTeam
from ember_agents.project_market_info.market_agent_team import MarketAgentTeam
from ember_agents.send_token.send import SendTokenAgentTeam
from ember_agents.swap_token.swap import SwapTokenAgentTeam


class AgentTeamSessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, AgentTeam] = {}

    def create_session(self, session_id: str, agent_team: AgentTeam):
        if session_id in self._sessions:
            self.remove_session(session_id)
        self._sessions[session_id] = agent_team

    def get_session(self, session_id: str):
        agent_team = self._sessions.get(session_id)
        return agent_team

    def remove_session(self, session_id: str):
        if session_id in self._sessions:
            del self._sessions[session_id]
            return

        print(f"Session ID ({session_id}) does not exist")

    def get_session_id(self, sender_did: str, thread_id: str, client_id: int) -> str:
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
        intents: list[str] | None,
    ):
        self._session_manager = session_manager
        self._intents = intents

    async def send(
        self,
        user_chat_id: str,
        store_transaction_info: Any,
        session_id: str,
        message: str,
        activity: Callable[[str], None] | None = None,
        context: list[ChatCompletionMessageParam] | None = None,
    ):
        intent = await classify_intent(message)
        route = intent.name
        print(f"Route: {route}")
        agent_team = self._get_agent_team_session(session_id)
        if route == "terminate" or agent_team is None:
            agent_team = self._create_agent_team_session(
                session_id, route, store_transaction_info, user_chat_id
            )
        if activity is not None:
            agent_team.get_activity_updates(activity)
        return {
            "message": await agent_team.send(message, context=context),
            "sign_url": agent_team.sign_url,
        }

    def _create_agent_team_session(
        self,
        session_id: str,
        route: INTENT | None,
        store_transaction_info: Any,
        user_chat_id: str,
    ) -> AgentTeam:
        if self._intents is not None:
            route = route if route is not None and route in self._intents else None
        on_complete = partial(self._session_manager.remove_session, session_id)
        match route:
            case "transfer_crypto_action":
                agent_team = SendTokenAgentTeam(
                    on_complete, store_transaction_info, user_chat_id
                )
            case "swap_crypto_action":
                agent_team = SwapTokenAgentTeam(
                    on_complete, store_transaction_info, user_chat_id
                )
            case "crypto_price_query" | "market_news_query":
                agent_team = MarketAgentTeam(on_complete)
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
