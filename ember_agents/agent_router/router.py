from functools import partial
from collections.abc import Callable
from typing import Any

from openai.types.chat import ChatCompletionMessageParam
from semantic_router import Route
from semantic_router.encoders import CohereEncoder
from semantic_router.layer import RouteLayer

from ember_agents.common.agents import AgentTeam
from ember_agents.education.education import EducationAgentTeam
from ember_agents.project_market_info.market_agent_team import MarketAgentTeam
from ember_agents.send_token.send import SendTokenAgentTeam
from ember_agents.settings import SETTINGS
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


encoder = CohereEncoder(cohere_api_key=SETTINGS.cohere_api_key)

send = Route(
    name="send",
    utterances=[
        "give 5 {token} to alice",
        "send token",
        "send {token}",
        "send {token} to bob",
        "transfer crypto",
        "1.25 {token} to 0xC7F97cCC3b899fd0372134570A7c5404f6F887F8",
        "48.06 {token} to mike",
        "22 {token} to 0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
    ],
)

terminate = Route(
    name="terminate",
    utterances=["terminate", "cancel", "stop", "quit", "exit"],
)

swap = Route(
    name="swap",
    utterances=[
        "swap 1 {token} from {network} to {network}",
        "swap token",
        "swap {token} to {token}",
        "buy crypto",
        "buy {token}",
        "purchase {token}",
        "I want to purchase crypto",
        "convert my 5 {token}",
        "change crypto",
        "48.5 {token} to other chain",
        "1.01 from {network} to {network}",
        "change some of my tokens",
    ],
)

market = Route(
    name="market",
    utterances=[
        "info on {token}",
        "what's the price of {token}?",
        "current {token} price",
        "how much is {token}?",
        "market cap of {token}",
        "{token} volume",
        "doland tremp",
        "tell me about {token}",
        "market info",
        "{name} {network}",
        "project details",
        "{token} summary",
    ],
)

education = Route(
    name="education",
    utterances=[
        "how does {protocol} work?",
        "what is a blockchain?",
        "explain a smart contract",
        "tell me about yourself",
        "good morning",
        "what is an L2 {network}?",
        "what is the difference between {protocol Y} and {protocol Z}?",
        "technology comparison of {protocol A} and {protocol B}",
        "Will the price of {token} go up?",
        "educational content",
        "tell me a joke",
        "technical questions",
        "yes",
        "proceed",
        "ok",
    ],
)

routes = [send, market, education, swap, terminate]
decision_layer = RouteLayer(encoder=encoder, routes=routes)


class Router:
    def __init__(
        self,
        session_manager: AgentTeamSessionManager,
        possible_routes: list[str] | None,
    ):
        self._session_manager = session_manager
        self._possible_routes = possible_routes

    async def send(
        self,
        user_chat_id: str,
        store_transaction_info: Any,
        session_id: str,
        message: str,
        activity: Callable[[str], None] | None = None,
        context: list[ChatCompletionMessageParam] | None = None,
    ):
        route = decision_layer(message).name
        print(f"Route: {route}")
        agent_team = self._get_agent_team_session(session_id)
        if route == "terminate" or agent_team is None:
            agent_team = self._create_agent_team_session(
                session_id, route, store_transaction_info, user_chat_id
            )
        if activity is not None:
            agent_team.get_activity_updates(activity)
        return await agent_team.send(message, context=context)

    def _create_agent_team_session(
        self,
        session_id: str,
        route: str | None,
        store_transaction_info: Any,
        user_chat_id: str,
    ) -> AgentTeam:
        if self._possible_routes is not None:
            route = (
                route if route is not None and route in self._possible_routes else None
            )
        on_complete = partial(self._session_manager.remove_session, session_id)
        match route:
            case "send":
                agent_team = SendTokenAgentTeam(
                    on_complete, store_transaction_info, user_chat_id
                )
            case "swap":
                agent_team = SwapTokenAgentTeam(
                    on_complete, store_transaction_info, user_chat_id
                )
            case "market":
                agent_team = MarketAgentTeam(on_complete)
            case "education" | "terminate" | None | _:
                agent_team = EducationAgentTeam(on_complete)
        self._session_manager.create_session(session_id, agent_team)
        return agent_team

    def _get_agent_team_session(self, session_id: str) -> AgentTeam | None:
        return self._session_manager.get_session(session_id)


"""
def router(message: str) -> str:
    \"""Route a user message to the appropriate agent team.\"""

    # TODO: Track sessions using a user id and thread id.
    #       (A thread represents a private chat, public group, or chat thread)

    # TODO: Each time an agent team ends their session with the user, they should return
    #       a summary of their conversation with the user so that it can be included in
    #       the top level conversation for context.

    route = decision_layer(message).name
    match route:
        case "send":
            return "send"
        case "market":
            return "market"
        case "education" | None | _:
            return "education"
"""
