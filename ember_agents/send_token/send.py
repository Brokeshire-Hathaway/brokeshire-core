import json
import re
import tempfile
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from autogen import (
    Agent,
    AssistantAgent,
    ConversableAgent,
    GroupChat,
    GroupChatManager,
    UserProxyAgent,
    config_list_from_json,
)
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel, ValidationError

from ember_agents.common.agent_team import AgentTeam
from ember_agents.common.transaction import link_chain, link_token
from ember_agents.common.utils import format_transaction_url
from ember_agents.common.validators import PositiveAmount
from ember_agents.settings import SETTINGS

client = AsyncOpenAI(api_key=SETTINGS.openai_api_key)


class TxRequest(BaseModel):
    user_chat_id: str
    user_address: str | None
    network_id: int
    recipient_address: str
    token_address: str
    amount: str
    store_transaction: Any


class TxPreview(BaseModel):
    id: str
    sign_url: str
    network_name: str
    token_symbol: str
    token_explorer_url: str
    transaction_hash: str | None = None


class Transaction(BaseModel):
    recipient_address: str
    network: str
    amount: PositiveAmount
    token: str


OAI_CONFIG_LIST = [{"model": "gpt-4o-2024-05-13", "api_key": SETTINGS.openai_api_key}]


# Create a temporary file
# Write the JSON structure to a temporary file and pass it to config_list_from_json
with tempfile.NamedTemporaryFile(mode="w+", delete=True) as temp:
    env_var = json.dumps(OAI_CONFIG_LIST)
    temp.write(env_var)
    temp.flush()

    llm_config = {
        **config_list_from_json(env_or_file=temp.name)[0],
        "stream": True,
    }  # use the first config
    # gpt = models.OpenAI("gpt-4", api_key=llm_config.get("api_key"))


class SendTokenGroupChat(GroupChat):
    def __init__(
        self,
        agents,
        messages,
        max_round=10,
        on_activity: Callable[[str], None] | None = None,
    ):
        self.last_speaker = None
        self._on_activity = on_activity
        super().__init__(agents, messages, max_round)

    async def a_select_speaker(self, last_speaker: Agent, selector: ConversableAgent):
        """Select the next speaker."""

        next_speaker = self.agent_by_name("user")

        selected_agent, _, _ = self._prepare_and_select_agents(last_speaker)
        last_message = self.messages[-1] if self.messages else None
        if selected_agent:
            next_speaker = selected_agent
        elif last_message:
            if "NEXT:" in last_message["content"]:
                suggested_next = (
                    last_message["content"]
                    .split("NEXT: ")[-1]
                    .strip()
                    .strip("-")
                    .strip()
                )
                print(f"Extracted suggested_next = {suggested_next}")
                try:
                    next_speaker = self.agent_by_name(suggested_next)
                except ValueError as error:
                    print(f"Error: {error}")
                    pass
            elif "TERMINATE" in last_message["content"]:
                try:
                    next_speaker = self.agent_by_name("user")
                except ValueError as error:
                    print(f"Error: {error}")
                    pass
            elif self.last_speaker is None:
                next_speaker = self.agent_by_name("interpreter")
            else:
                match last_speaker.name:
                    case "interpreter":
                        next_speaker = self.agent_by_name("validator")
                    case "broker":
                        next_speaker = self.agent_by_name("user")
                    case "transaction_coordinator":
                        next_speaker = self.agent_by_name("user")
                    case "user":
                        next_speaker = self.last_speaker
                    case "technician":
                        next_speaker = self.last_speaker

        self.last_speaker = last_speaker

        return next_speaker

    def _send_activity_update(self, message: str):
        if self._on_activity is not None:
            self._on_activity(message)


class MessagingUserProxyAgent(UserProxyAgent):
    def __init__(
        self,
        name,
        human_input_mode,
        code_execution_config,
        is_termination_msg,
        a_human_reply: Callable[[], Awaitable[str]],
        assistant_reply: Callable[[str], None],
    ):
        super().__init__(name, human_input_mode, code_execution_config)
        self.is_termination_msg = is_termination_msg
        self.a_human_reply = a_human_reply
        self.assistant_reply = assistant_reply

    async def a_get_human_input(self, prompt: str) -> str:
        last_message = self.last_message()
        if last_message is None:
            msg = "Assistant message not found"
            raise Exception(msg)

        message = last_message.get("content")
        if message is None:
            msg = "Assistant message content not found"
            raise Exception(msg)

        if self.is_termination_msg(last_message):
            self.assistant_reply(message.replace("TERMINATE", ""))
            return "exit"

        self.assistant_reply(message)
        return await self.a_human_reply()


def get_last_message(recipient: ConversableAgent) -> str:
    last_message = recipient.last_message()
    content = last_message.get("content") if last_message else None
    if not isinstance(content, str):
        msg = "No message content found"
        raise Exception(msg)
    return content


async def interpreter_reply(recipient: ConversableAgent, messages, sender, config):
    # pprint.pprint(messages)

    """with instruction():
        # TODO: Add link to token for user verification

        lm = (
            gpt_instruct
            + f\"""
            You are an intent interpreter responsible for converting user intent into a structured JSON request.

            "network" will always be "sepolia" for now.

            Use the following JSON example as a guide. ALWAYS remember to wrap your JSON in a code block.
            ---
            # Intent
            Send .5 Chainlink to Susan
            ```json
            {{
                "recipient_name": "Susan",
                "recipient_address": null,
                "network": "sepolia",
                "amount": "0.5",
                "token_name": "Chainlink",
                "is_native_token": false,
                "token_address": null
            }}
            ```
            ---
            # Intent
            {request}
            \"""
        )

    lm += gen("json", stop="```\n", save_stop_text=True)"""

    print(f"recipient = {recipient._name}")
    request = get_last_message(recipient)
    print(f"request = {request}")

    json = await convert_to_json(request)

    return True, {
        "content": f"```json\n{json}\n```",
        "name": "interpreter",
        "role": "assistant",
    }


async def convert_to_json(request: str) -> str:
    system_message = """You are an interpreter responsible for converting a user request into JSON. If you are unsure, use the value `null` for missing information.

# Example
## User Request
Send 1 eth to 0x2D6c1025994dB45c7618571d6cB49B064DA9881B in ethereum chain
## JSON
```json
{{

    "recipient_address": "0x2D6c1025994dB45c7618571d6cB49B064DA9881B",
    "network": "ethereum chain",
    "amount": "1",
    "token": "eth"
}}
```"""

    user_message = f"Convert the following request into JSON.\n---\n{request}"

    chat_completion = await client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": system_message,
            },
            {
                "role": "user",
                "content": user_message,
            },
        ],
        model="gpt-4o-2024-05-13",
        temperature=0,
        seed=42,
        response_format={"type": "json_object"},
    )

    if len(chat_completion.choices) > 0 and chat_completion.choices[0].message.content:
        return chat_completion.choices[0].message.content

    msg = "Failed to convert request to JSON. 😔"
    raise Exception(msg)


"""
            ---
            # Example
            ## User Request
            Send 1 eth to 0x2D6c1025994dB45c7618571d6cB49B064DA9881B
            ## JSON
            ```json
            {{
                "recipient_name": null,
                "recipient_address": "0x2D6c1025994dB45c7618571d6cB49B064DA9881B",
                "network": "sepolia",
                "amount": "1",
                "token_name": "eth",
                "is_native_token": true,
                "token_address": null
            }}
            ```
"""


broker_system_message = """
You are a friendly cryptocurrency copilot responsible for gathering the missing information from the user necessary to complete their token send request. All other requests MUST be politely refused.

After the user has satisfied all requirements, you will send the revised intent to the interpreter on their behalf.

Your messages to the interpreter must be in the following format:
---
Original Intent: Send .5 matic to Susan in polygon
Amount: 0.5
Token: matic
Network: polygon
Recipient Address: 0x604f7cA57A338de9bbcE4ff0e2C41bAcE744Df03
NEXT: interpreter"""

# TODO: Add new agent for showing tx preview, determining if any changes are needed, and
#       confirming if the user will proceed or cancel. Broker might be able to handle this.

# TODO: Skip signature link for now and just have the user reply with proceed or cancel.


technician_system_message = """
You are a technician responsible for executing tools and returning the results to the requester.
"""


class SendTokenAgentTeam(AgentTeam):

    def __init__(
        self,
        on_complete: Callable[[], Any],
        store_transaction_info: Any,
        user_chat_id: str,
        user_address: str | None,
    ):
        super().__init__(on_complete)
        self._transaction: Transaction | None = None
        self._transaction_request: TxRequest | None = None
        self._transaction_preview: TxPreview | None = None
        self._store_transaction_info = store_transaction_info
        self._user_chat_id = user_chat_id
        self._user_address = user_address
        self._sign_url: str | None = None
        self._transaction_hash: str | None = None

    def send_response(self, message: str):
        self._send_team_response(message, self._sign_url, self._transaction_hash)

    async def _run_conversation(
        self, message: str, context: list[ChatCompletionMessageParam] | None = None
    ):
        user_proxy = MessagingUserProxyAgent(
            "user",
            human_input_mode="ALWAYS",
            code_execution_config={"work_dir": "coding"},
            is_termination_msg=lambda x: x.get("content", "")
            and x.get("content", "").rstrip().endswith("TERMINATE"),
            a_human_reply=self._get_human_messages,
            assistant_reply=self.send_response,
        )

        # No system message needed for OpenAI completion API used by Guidance agent (Metis).
        interpreter_agent = AssistantAgent("interpreter", None, llm_config=llm_config)
        interpreter_agent.register_reply(ConversableAgent, interpreter_reply, 1)

        # No system message needed for code based agent (Spock).
        validator = AssistantAgent("validator", None, llm_config=llm_config)
        validator.register_reply(ConversableAgent, self._validate_request, 1)

        broker = AssistantAgent(
            "broker",
            system_message=broker_system_message,
            llm_config=llm_config,
        )

        async def a_prepare_transaction(
            recipient: ConversableAgent, messages, sender, config
        ):
            """
            tx_request = TxRequest(
                sender_did="ethereum://84738954.telegram.org",
                recipient_did="ethereum://0xc6A9f8f20d79Ae0F1ADf448A0C460178dB6655Cf",
                receive_token_address="0x514910771AF9Ca656af840dff83E8264EcF986CA",
                amount="0.0001",
            )
            return await self._prepare_transaction(tx_request)"""

            self._send_activity_update("Setting up send transaction...")

            try:
                if self._transaction_request is None or self._transaction is None:
                    msg = "Transaction request not found"
                    raise ValueError(msg)

                url = f"{SETTINGS.transaction_service_url}/send/prepare"
                async with httpx.AsyncClient(http2=True, timeout=65) as client:
                    response = await client.post(
                        url, json=self._transaction_request.model_dump()
                    )

                response_json = response.json()
                try:
                    self._transaction_preview = TxPreview.model_validate(response_json)
                except ValidationError as err:
                    raise ValueError(
                        response_json.get("message", "Failed sending token")
                    ) from err
            except Exception as e:
                error_message = str(e) if str(e) else str(type(e))
                return (
                    True,
                    f"""Failed to prepare transaction. 😔

Details: {error_message}
TERMINATE""",
                )

            self._sign_url = self._transaction_preview.sign_url
            self._transaction_hash = self._transaction_preview.transaction_hash
            response_message = f"""Transaction {self._transaction_preview.id} is ready for you to sign! 💸

💸 **Send ・** {self._transaction.amount} [{self._transaction_preview.token_symbol}]({self._transaction_preview.token_explorer_url}) ({self._transaction_preview.network_name})
🧑 **To Recipient ・** {self._transaction.recipient_address}

🔏 {format_transaction_url(self._transaction_preview.sign_url)}
TERMINATE"""

            return True, {
                "content": response_message,
                "name": "transaction_coordinator",
                "role": "assistant",
            }

        # (Spock)
        transaction_coordinator = AssistantAgent(
            "transaction_coordinator",
            None,
            llm_config=llm_config,
        )
        transaction_coordinator.register_reply(
            ConversableAgent, a_prepare_transaction, 1
        )

        technician = AssistantAgent(
            "technician",
            system_message=technician_system_message,
            llm_config=llm_config,
        )

        groupchat = SendTokenGroupChat(
            agents=[
                user_proxy,
                interpreter_agent,
                validator,
                broker,
                transaction_coordinator,
                technician,
            ],
            messages=[],
            max_round=20,
        )
        manager = GroupChatManager(groupchat=groupchat, llm_config=llm_config)

        self._send_activity_update("Understanding your send request...")

        try:
            await user_proxy.a_initiate_chat(manager, message=message)
        except Exception:
            if self._on_complete is not None:
                self._on_complete()

    async def _validate_request(
        self, recipient: ConversableAgent, messages, sender, config
    ):
        try:
            message = get_last_message(recipient)
            print(f"message = {message}")
            print(type(message))
            pattern = r"```json\n([\s\S]*?)\n```"
            match = re.search(pattern, message)
            print(f"match = {match}")
            json_str = match.group(1) if match else None
            print(f"json_str = {json_str}")
            print(type(json_str))
            if not isinstance(json_str, str):
                msg = "JSON request not found in message"
                raise ValueError(msg)
        except Exception as e:
            return True, {
                "content": f"{e!s}\n\nTERMINATE",
                "name": "interpreter",
                "role": "assistant",
            }

        try:
            self._transaction = Transaction.model_validate_json(json_str)

            linked_chain_results = await link_chain(self._transaction.network)
            chain_llm_matches = linked_chain_results["llm_matches"]
            if chain_llm_matches is None or len(chain_llm_matches) == 0:
                msg = f"{self._transaction.network} is not a supported chain"
                raise ValueError(msg)
            chain_match = chain_llm_matches[0]
            chain_confidence_threshold = 70
            if chain_match["confidence_percentage"] < chain_confidence_threshold:
                msg = f"{self._transaction.network} is not a supported chain"
                raise ValueError(msg)

            linked_token_results = await link_token(
                self._transaction.token, chain_match["entity"]["chain_id"]
            )
            token_fuzzy_matches = linked_token_results["fuzzy_matches"] or []
            token_llm_matches = linked_token_results["llm_matches"]
            token_match = (
                token_fuzzy_matches[0]
                if token_llm_matches is None
                else token_llm_matches[0]
            )
            token_confidence_threshold = 60
            if token_match["confidence_percentage"] < token_confidence_threshold:
                msg = f"{self._transaction.token} is not a supported token"
                raise ValueError(msg)

            self._transaction_request = TxRequest(
                user_chat_id=self._user_chat_id,
                network_id=chain_match["entity"]["chain_id"],
                recipient_address=self._transaction.recipient_address,
                amount=self._transaction.amount,
                token_address=token_match["entity"]["address"],
                store_transaction=self._store_transaction_info,
                user_address=self._user_address,
            )
            return True, {
                "content": "NEXT: transaction_coordinator",
                "name": "interpreter",
                "role": "assistant",
            }
        except Exception as e:
            return True, {
                "content": f"{e!s}\nNEXT: broker",
                "name": "interpreter",
                "role": "assistant",
            }
