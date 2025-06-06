from openai.types.chat import ChatCompletionMessageParam

from brokeshire_agents.common.agent_team import AgentTeam
from brokeshire_agents.project_market_info.info_from_apis import market_route


class MarketAgentTeam(AgentTeam):
    async def _run_conversation(
        self, message: str, context: list[ChatCompletionMessageParam] | None = None
    ):
        self._send_activity_update("I'm searching for the information you requested...")
        try:
            response = await market_route(message, context=context)
        except Exception as error:
            print(error)
            self._send_team_response("Failed querying token information")
            return

        print(f"MarketAgentTeam response: {response}", flush=True)
        self._send_team_response(response)
