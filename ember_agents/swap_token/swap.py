import asyncio
import json
import re
import tempfile
from collections.abc import Awaitable, Callable

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
from pydantic import BaseModel, ValidationError

from ember_agents.common.agents import AgentTeam
from ember_agents.common.validators import PositiveAmount
from ember_agents.info_bites.info_bites import get_random_info_bite
from ember_agents.send_token.send import UniversalAddress
from ember_agents.settings import SETTINGS

client = AsyncOpenAI()


class TokenSwapTo(BaseModel):
    """Request for doing cross chain swap"""

    network: str
    token: str


class SwapRequest(BaseModel):
    """Request for doing cross chain swap"""

    amount: PositiveAmount
    token: str
    sender: UniversalAddress
    to: TokenSwapTo
    type: str


class SwapInformation(BaseModel):
    """All needed information to do a cross-chain swap."""

    amount: str
    token: str
    network: str
    to_network: str
    to_token: str
    type: str

    def to_swap_request(self, address: UniversalAddress) -> SwapRequest:
        """Transforms information to request."""

        address.network = self.network
        return SwapRequest(
            amount=self.amount,
            token=self.token,
            sender=address,
            to=TokenSwapTo(network=self.to_network, token=self.to_token),
            type=self.type,
        )


class TxPreview(BaseModel):
    uuid: str
    from_amount: str
    from_chain: str
    to_amount: str
    to_chain: str
    duration: str
    total_fees: str
    total_amount: str


class ExecuteTxBody(BaseModel):
    transaction_uuid: str


OAI_CONFIG_LIST = [{"model": "gpt-4-1106-preview", "api_key": SETTINGS.openai_api_key}]

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


class SwapTokenGroupChat(GroupChat):
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
                print(suggested_next)
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
                        if self.last_speaker.name == "transaction_coordinator":
                            next_speaker = self.agent_by_name("executor")
                        else:
                            next_speaker = self.last_speaker
                    case "executor":
                        next_speaker = self.agent_by_name("user")
                    case "confirmation_specialist":
                        next_speaker = self.agent_by_name("user")
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
    system_message = """You are an interpreter responsible for converting a user
    request into JSON.

    # Example 1
    ## User Request
    Swap 1 usd-coin from my sepolia account to usd-coin in my polygon mumbai account.
    ## JSON
    ```json
    {{
        "type": "swap",
        "network": "sepolia",
        "to_network": "polygon mumbai",
        "amount": "1",
        "token": "usd-coin",
        "to_token": "usd-coin"
    }}

    # Example 2
    ## User Request
    Change 2.3 ethereum from goerli to usd-coin in sepolia wallet
    ## JSON
    ```json
    {{
        "type": "swap",
        "network": "goerli",
        "to_network": "sepolia",
        "amount": "2.3",
        "token": "ethereum",
        "to_token": "usd-coin"
    }}
    ```

    # Example 3
    ## User Request
    Change .43 ethereum from eth sepolia testnet wallet to usd-coin in my mumbai
    ## JSON
    ```json
    {{
        "type": "swap",
        "network": "eth sepolia testnet",
        "to_network": "mumbai",
        "amount": "0.43",
        "token": "ethereum",
        "to_token": "usd-coin"
    }}
    ```

    # Example 4
    ## User Request
    Change 50 matic-network of my polygon mumbai account
    ## JSON
    ```json
    {{
        "error": "Missing information of the destination chain and token.",
    }}

    # Example 5
    ## User Request
    Buy 23 eth in sepolia from usd-coin in mumbai
    ## JSON
    ```json
    {{
        "type": "buy",
        "amount": "23",
        "to_network": "sepolia",
        "to_token": "eth",
        "network": "mumbai",
        "token": "usd-coin"
    }}

    # Example 6
    ## User Request
    Buy 0.456345632 usd-coin in eth sepolia using matic in mumbai
    ## JSON
    ```json
    {{
        "type": "buy",
        "amount": "0.456345632",
        "to_token": "usd-coin",
        "to_network": "eth sepolia",
        "token": "matic",
        "network": "mumbai"
    }}
    ```
"""

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
        model="gpt-4-1106-preview",
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
You are a cryptocurrency copilot responsible for gathering missing information from the user necessary to complete their request.
After the user has satisfied all requirements, you will send the revised intent to the interpreter on their behalf.
Your messages to the interpreter must be in the following format (the NEXT value will always be interpeter):
---
# Example 1
Original Intent: Swap .1 usd-coin sepolia testnet to usd-coin polygon-mumbai
Type: swap
Token: usd-coin
to_token: usd-coin
Amount: 0.1
Network: sepolia testnet
to_network: polygon mumbai
NEXT: interpreter

# Example 2
---
Original Intent: Purchase 0.456 axlusdc in bnb testnet using usd-coin in sepolia
Type: buy
Token: usd-coin
to_token: axlusdc
Amount: 0.456
Network: sepolia
to_network: bnb testnet
NEXT: interpreter
"""

# TODO: Add new agent for showing tx preview, determining if any changes are needed, and
#       confirming if the user will proceed or cancel. Broker might be able to handle this.

# PROBLEM:  The executor expects a reply after sending the preview and signature link to the user. However, the user must sign using the URL, not by replying to the executor.
#
#           - Maybe the prepare transaction function should send the preview and signature link to the user and only return with a success or failure result.
#           - Another option might be to have the human input method to check if the last message from the executor. If so, then it will reply either from the user or signing result. Whichever comes first.

# TODO: Skip signature link for now and just have the user reply with proceed or cancel.
executor_system_message = """
You are an executor responsible for determining whether the user will proceed or
cancel their transaction request. If they proceed, you must reply with \"NEXT:
confirmation_specialist\" to pass the request to the confirmation specialist. If
they cancel, you must reply with \"Transaction canceled\nTERMINATE\" to end the
conversation.
"""


# NOTE: Still working out this signature link prompt.
"""
You are an executor responsible for showing the user a preview of their transaction request along with a signature link.
After sending the user the preview, you must use the "get_transaction_update" function to check the status of the transaction.
The user should open the signature link in their web browser and sign the transaction to proceed.
You will monitor the status of the transaction and update the user as needed.
If the transaction fails or the user decides to cancel the request, you must use \"TERMINATE\" to pass along the reason.
"""

# 1. intent -> request (user -> interpreter)
# 2. request -> validate (interpreter -> validator)
# 3. a. valid -> execute (validator -> executor)
#    b. I. invalid -> ask for missing information until satisfied (validator -> broker)
#       II. new intent -> request (broker -> interpreter)


technician_system_message = """
You are a technician responsible for executing tools and returning the results to the requester.
"""


class SwapTokenAgentTeam(AgentTeam):
    _transaction: SwapInformation | None = None
    _transaction_request: SwapRequest | None = None
    _transaction_preview: TxPreview | None = None

    def __init__(self, sender_did: str, thread_id: str):
        # TODO: Create a new protocol for the prepare_transaction and get_transaction_result functions as a separation of concerns for transactions.
        super().__init__(sender_did, thread_id)

    async def _prepare_transaction(self) -> TxPreview | None:
        if self._transaction_request is None:
            return None

        print(self._transaction_request)
        url = f"{SETTINGS.transaction_service_url}/swap/preview"
        async with httpx.AsyncClient(http2=True, timeout=65) as client:
            response = await client.post(
                url, json=self._transaction_request.model_dump()
            )
        print(response.text)

        response_json = response.json()
        if not response_json["success"]:
            print(response_json)
            raise Exception(response_json["message"])

        try:
            return TxPreview.model_validate(response_json)
        except ValidationError as err:
            msg = "Failed processing response, try again."
            raise Exception(msg) from err

    async def _run_conversation(self, message: str):
        user_proxy = MessagingUserProxyAgent(
            "user",
            human_input_mode="ALWAYS",
            code_execution_config={"work_dir": "coding"},
            is_termination_msg=lambda x: x.get("content", "")
            and x.get("content", "").rstrip().endswith("TERMINATE"),
            a_human_reply=self._get_human_messages,
            assistant_reply=self._send_team_response,
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

        """@technician.register_for_execution()
        @executor.register_for_llm(
            description="Prepare a transaction for the user to review and sign."
        )"""

        async def a_prepare_transaction(
            recipient: ConversableAgent, messages, sender, config
        ):
            self._send_activity_update("Preparing transaction preview...")

            try:
                if self._transaction_request is None:
                    msg = "Transaction request not found"
                    raise ValueError(msg)
                self._transaction_preview = await self._prepare_transaction()
                if self._transaction_preview is None:
                    raise Exception()
            except Exception as e:
                error_message = str(e) if str(e) else str(type(e))
                return (
                    True,
                    f"""Failed to prepare transaction. 😔

Details: {error_message}
TERMINATE""",
                )

            # tx_details = self._transaction_preview.tx_details
            response_message = f"""You are about to swap tokens 💸.

**💸 Convert From ・** {self._transaction_preview.from_amount} ({self._transaction_preview.from_chain})
**💸 Convert To ・** {self._transaction_preview.to_amount} ({self._transaction_preview.to_chain})
**⛽️ Fees Estimation ・** {self._transaction_preview.total_fees}
**🔢 Total ・** {self._transaction_preview.total_amount}

Would you like to proceed?"""

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

        # TODO: Can be converted to Metis agent.
        executor = AssistantAgent(
            "executor", system_message=executor_system_message, llm_config=llm_config
        )

        """# TODO: This is a temporary method that will be replaced by the get_transaction_result method.
        @technician.register_for_execution()
        @executor.register_for_llm(description="Execute a transaction.")"""

        async def a_execute_transaction(
            recipient: ConversableAgent, messages, sender, config
        ):
            # self._send_activity_update("Executing transaction...")

            async def repeating_task(seconds, task, *args):
                while True:
                    await task(*args)
                    await asyncio.sleep(seconds)

            async def send_info_bite():
                bite = get_random_info_bite()
                message = f"""Executing transaction...

> **・ Fun Fact ・**
>🍬 {bite}"""
                self._send_activity_update(message)

            seconds = 8
            timer_task = asyncio.create_task(repeating_task(seconds, send_info_bite))

            try:
                if self._transaction_preview is None:
                    msg = "Transaction request not found"
                    raise ValueError(msg)

                url = f"{SETTINGS.transaction_service_url}/swap/"
                body = ExecuteTxBody(transaction_uuid=self._transaction_preview.uuid)
                async with httpx.AsyncClient(http2=True, timeout=65) as client:
                    response = await client.post(url, json=body.model_dump())
                    if response.json().get("block", None) is None:
                        msg = "No block found."
                        raise Exception(msg)

            except Exception as e:
                error_message = str(e) if str(e) else str(type(e))
                return (
                    True,
                    f"""Your transaction failed. 😔

Details: {error_message}
TERMINATE""",
                )
            finally:
                timer_task.cancel()

            response_message = f"""Your transaction was successful! 🎉

_[🔗 View on Blockchain]({response.json()["block"]})_
TERMINATE"""

            return True, {
                "content": response_message,
                "name": "confirmation_specialist",
                "role": "assistant",
            }

        # (Spock)
        confirmation_specialist = AssistantAgent(
            "confirmation_specialist",
            None,
            llm_config=llm_config,
        )
        confirmation_specialist.register_reply(
            ConversableAgent, a_execute_transaction, 1
        )

        technician = AssistantAgent(
            "technician",
            system_message=technician_system_message,
            llm_config=llm_config,
        )

        """@technician.register_for_execution()
        @executor.register_for_llm(description="Get the results of a transaction.")
        async def a_get_transaction_result(tx_id: str):
            return await self._get_transaction_result(tx_id)"""

        groupchat = SwapTokenGroupChat(
            agents=[
                user_proxy,
                interpreter_agent,
                validator,
                broker,
                transaction_coordinator,
                executor,
                confirmation_specialist,
                technician,
            ],
            messages=[],
            max_round=20,
        )
        manager = GroupChatManager(groupchat=groupchat, llm_config=llm_config)

        self._send_activity_update("Understanding your request...")

        try:
            await user_proxy.a_initiate_chat(manager, message=message)
        except Exception:
            if self.on_complete is not None:
                self.on_complete(self.sender_did, self.thread_id)

    def _validate_request(self, recipient: ConversableAgent, messages, sender, config):
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
            self._transaction = SwapInformation.model_validate_json(json_str)
            self._transaction_request = self._transaction.to_swap_request(
                UniversalAddress(
                    identifier=self.sender_did, platform="telegram.me", network=""
                )
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
