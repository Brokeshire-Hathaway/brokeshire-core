from ember_agents.common.agents import AgentTeam
from ember_agents.project_market_info.info_from_apis import market_route


class MarketAgentTeam(AgentTeam):
    async def _run_conversation(self, message: str):
        self._send_activity_update("I'm searching for the information you requested.")
        response = await market_route(message)
        print(f"MarketAgentTeam response: {response}", flush=True)
        self._send_team_response(response)
