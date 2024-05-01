import asyncio
import os
from collections.abc import Callable

import httpx
from ember_agents.common.agents import AgentTeam
from ember_agents.education.education import EducationAgentTeam
from ember_agents.project_market_info.market_agent_team import MarketAgentTeam
from ember_agents.send_token.send import (
    SendTokenAgentTeam,
    TxIdStatus,
    TxPreview,
    TxRequest,
)
from ember_agents.swap_token.swap import SwapTokenAgentTeam
from semantic_router import Route
from semantic_router.encoders import CohereEncoder
from semantic_router.layer import RouteLayer

"""tx_details = TxDetails(
    sender_did="ethereum://84738954.telegram.org",
    recipient_did="ethereum://0xc6A9f8f20d79Ae0F1ADf448A0C460178dB6655Cf",
    receive_token_address="0x514910771AF9Ca656af840dff83E8264EcF986CA",
    receive_token_name="",
    receive_token_symbol="",
    display_currency_symbol="",
    amount="0.0001",
    amount_in_display_currency="",
    gas_fee="",
    gas_fee_in_display_currency="",
    service_fee="",
    service_fee_in_display_currency="",
    total_fee="",
    total_fee_in_display_currency="",
    total_amount="",
    total_amount_in_display_currency="",
)"""

TRANSACTION_SERVICE = os.environ.get(
    "TRANSACTION_SERVICE_URL", "http://firepot_chatgpt_app:3000"
)


async def prepare_transaction(tx_request: TxRequest):
    url = f"{TRANSACTION_SERVICE}/transactions/prepare"
    async with httpx.AsyncClient(http2=True, timeout=65) as client:
        response = await client.post(url, json=tx_request.dict())

    return TxPreview.parse_raw(response.text)


async def get_transaction_result(tx_id: str):
    print(f"getting update for transaction id: {tx_id}")
    await asyncio.sleep(1)
    tx_status = TxIdStatus(
        tx_id,
        tx_hash="0xeef10fc5170f669b86c4cd0444882a96087221325f8bf2f55d6188633aa7be7c",
        explorer_link="https://etherscan.io/tx/0xeef10fc5170f669b86c4cd0444882a96087221325f8bf2f55d6188633aa7be7c",
        confirmations=6,
        status="finalized",
        # final_tx_details=tx_details,
    )
    return tx_status


class AgentTeamSessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, AgentTeam] = {}

    def create_session(self, agent_team: AgentTeam):
        session_id = self._get_session_id(agent_team.sender_did, agent_team.thread_id)
        if session_id in self._sessions:
            self.remove_session(agent_team.sender_did, agent_team.thread_id)
        agent_team.on_complete = self.remove_session
        self._sessions[session_id] = agent_team

    def get_session(self, sender_did: str, thread_id: str):
        session_id = self._get_session_id(sender_did, thread_id)
        agent_team = self._sessions.get(session_id)
        return agent_team

    def remove_session(self, sender_did: str, thread_id: str):
        session_id = self._get_session_id(sender_did, thread_id)
        if session_id in self._sessions:
            del self._sessions[session_id]
        else:
            msg = f"Session ID ({session_id}) does not exist"
            raise Exception(msg)

    def _get_session_id(self, sender_did: str, thread_id: str) -> str:
        return f"{sender_did}:{thread_id}"


print("COHERE_API_KEY")
print(os.getenv("COHERE_API_KEY"))
encoder = CohereEncoder(cohere_api_key=os.getenv("COHERE_API_KEY"))

send = Route(
    name="send",
    utterances=[
        "give 5 bitcoin to alice",
        "send token",
        "send {token}",
        "send sol to bob",
        "transfer crypto",
        "1.25 eth to 0xC7F97cCC3b899fd0372134570A7c5404f6F887F8",
        "48.06 bob to mike",
        "22 usdc to 0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
    ],
)

terminate = Route(
    name="terminate",
    utterances=["terminate session", "cancel action"],
)

swap = Route(
    name="swap",
    utterances=[
        "swap 1 uasdc from sepolia to polygon-mumbai",
        "swap token",
        "buy crypto",
        "buy {token}",
        "purchase {token}",
        "I want to purchase crypto",
        "change me my 5 uausdc",
        "change crypto",
        "48.5 bitcoin to other network",
        "1.01 from sepolia to polygon-mumbai",
        "change some of my tokens",
    ],
)

market = Route(
    name="market",
    utterances=[
        "what's the price of {token}?",
        "current {token} price",
        "how much is {token}?",
        "market cap of {token}",
        "{token} volume",
        "doland tremp",
        "tell me about {token}",
        "market info",
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
        "what is the difference between {protocol Y} and {protocol Z}?",
        "technology comparison of {protocol A} and {protocol B}",
        "Will the price of {token} go up?",
        "educational content",
        "tell me a joke",
        "technical questions",
    ],
)

routes = [send, market, education, swap, terminate]
decision_layer = RouteLayer(encoder=encoder, routes=routes)


class Router:
    def __init__(self, session_manager: AgentTeamSessionManager):
        self._session_manager = session_manager

    async def send(
        self,
        sender_did: str,
        thread_id: str,
        message: str,
        activity: Callable[[str], None] | None = None,
    ):
        route = decision_layer(message).name
        agent_team = self._get_agent_team_session(sender_did, thread_id)
        if route == "terminate" or agent_team is None:
            agent_team = self._create_agent_team_session(sender_did, thread_id, route)
        if activity is not None:
            agent_team.get_activity_updates(activity)
        return await agent_team.send(message)

    def _create_agent_team_session(
        self, sender_did: str, thread_id: str, route: str | None
    ) -> AgentTeam:
        match route:
            case "send":
                agent_team = SendTokenAgentTeam(
                    sender_did, thread_id, prepare_transaction, get_transaction_result
                )
            case "education" | "terminate":
                agent_team = EducationAgentTeam(sender_did, thread_id)
            case "swap":
                agent_team = SwapTokenAgentTeam(sender_did, thread_id)
            case "market" | None | _:
                agent_team = MarketAgentTeam(sender_did, thread_id)
        self._session_manager.create_session(agent_team)
        return agent_team

    def _get_agent_team_session(
        self, sender_did: str, thread_id: str
    ) -> AgentTeam | None:
        return self._session_manager.get_session(sender_did, thread_id)


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
