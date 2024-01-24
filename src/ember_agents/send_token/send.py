import asyncio
import pprint
from inspect import cleandoc
from typing import Awaitable, Callable, Literal, NamedTuple, Optional

from autogen import (
    Agent,
    AssistantAgent,
    ConversableAgent,
    GroupChat,
    GroupChatManager,
    UserProxyAgent,
    config_list_from_json,
)
from guidance import assistant, gen, instruction, models, select, system, user


# NOTE: I can use this as a universal format for single user swaps and sending between users.
class TxRequest(NamedTuple):
    # NOTE: Employ a Universal Money Address(UMA) or Decentralized ID (DID) scheme for
    #       sender and recipient.
    #
    #       It must include the following:
    #           - UID
    #           - Platform
    #           - Network
    #           - (MAYBE) Token Symbol
    #
    #       EXAMPLES:
    #           ethereum://0x2D6c1025994dB45c7618571d6cB49B064DA9881B
    #           ethereum:0x2D6c1025994dB45c7618571d6cB49B064DA9881B
    #           ethereum://alice.telegram.org
    #           bitcoin://84738954.telegram.org
    #           ethereum:alice@telegram.org
    #           solana://+1234567890
    #           solana:+1234567890/$SOL

    sender_did: str
    recipient_did: str
    receive_token_address: str
    amount: str
    send_token_address: str | None = None
    # NOTE: I might be able to have an abstract trigger for limit orders and other varous automations.


class TxDetails(NamedTuple):
    sender_did: str
    recipient_did: str
    receive_token_address: str
    receive_token_name: str
    receive_token_symbol: str
    display_currency_symbol: str
    amount: str
    amount_in_display_currency: str
    gas_fee: str
    gas_fee_in_display_currency: str
    service_fee: str
    service_fee_in_display_currency: str
    total_fee: str
    total_fee_in_display_currency: str
    total_amount: str
    total_amount_in_display_currency: str
    send_token_address: str | None = None
    send_token_name: str | None = None
    send_token_symbol: str | None = None
    exchange_rate: str | None = None


class TxPreview(NamedTuple):
    tx_id: str
    tx_details: TxDetails
    signature_link: str


"""
class TxState(Enum):
    PENDING = 0  # The transaction is in the mempool, meaning it has been broadcasted to the network but not yet included in a block.
    UNCONFIRMED = 1  # The transaction is included in a block, but this block has not yet been confirmed by subsequent blocks.
    FINALIZED = 2  # The transaction has received many confirmations, making it extremely unlikely to be reversed. It is permanently recorded in the blockchain.
    CANCELLED = 3  # The transaction was cancelled by the sender before it was processed by the network.
    FAILED = 4  # The transaction failed or was rejected by the network.
"""

TxState = Literal["pending", "unconfirmed", "finalized", "cancelled", "failed"]


class TxIdState(NamedTuple):
    tx_id: str
    tx_hash: str
    explorer_link: str
    confirmations: int
    state: TxState
    final_tx_details: TxDetails | None = None
    error_message: str | None = None


llm_config = {
    **config_list_from_json("OAI_CONFIG_LIST")[0],
    "stream": True,
}  # use the first config
# gpt = models.OpenAI("gpt-4", api_key=llm_config.get("api_key"))


class SendTokenGroupChat(GroupChat):
    def __init__(self, agents, messages, max_round=10):
        self.last_speaker = None
        super().__init__(agents, messages, max_round)

    async def a_select_speaker(self, last_speaker: Agent, selector: ConversableAgent):
        """Select the next speaker."""
        print(f"last_speaker = {last_speaker.name}")
        print(
            f"self.last_speaker = {self.last_speaker.name if self.last_speaker is not None else None}"
        )
        # print(f"self.messages = {self.messages}")

        next_speaker = self.agent_by_name("user")

        selected_agent, agents = self._prepare_and_select_agents(last_speaker)
        last_message = self.messages[-1] if self.messages else None
        if selected_agent:
            next_speaker = selected_agent
        elif last_message:
            if "NEXT:" in last_message["content"]:
                suggested_next = last_message["content"].split("NEXT: ")[-1].strip()
                print(f"Extracted suggested_next = {suggested_next}")
                try:
                    next_speaker = self.agent_by_name(suggested_next)
                except ValueError:
                    pass
            elif "TERMINATE" in last_message["content"]:
                try:
                    next_speaker = self.agent_by_name("user")
                except ValueError:
                    pass
            elif self.last_speaker is None:
                next_speaker = self.agent_by_name("interpreter")
            else:
                match last_speaker.name:
                    case "interpreter":
                        next_speaker = self.agent_by_name("validator")
                    case "broker":
                        next_speaker = self.agent_by_name("user")
                    case "user":
                        next_speaker = self.last_speaker
                    case "executor":
                        next_speaker = self.agent_by_name("user")
                    case "technician":
                        next_speaker = self.last_speaker

        self.last_speaker = last_speaker

        print(f"next_speaker = {next_speaker.name}")

        return next_speaker


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
            raise Exception("Assistant message not found")

        message = last_message.get("content")
        if message is None:
            raise Exception("Assistant message content not found")

        if self.is_termination_msg(last_message):
            self.assistant_reply(message.replace("TERMINATE", ""))
            return "exit"

        self.assistant_reply(message)
        return await self.a_human_reply()


def convert_to_request(recipient: ConversableAgent, messages, sender, config):
    # pprint.pprint(messages)

    gpt_instruct = models.OpenAI(
        "gpt-3.5-turbo-instruct", api_key=llm_config.get("api_key")
    )

    last_message = recipient.last_message()
    if last_message is not None:
        intent = last_message.get("content")
    else:
        raise Exception("No intent found")

    with instruction():
        # TODO: Add link to token for user verification

        lm = (
            gpt_instruct
            + f"""
            You are an intent interpreter responsible for converting user intent into a structured JSON request.
            Use the following JSON example as a guide.
            ---
            # Intent
            Send .5 Chainlink to Susan
            ```json
            [
                {{
                    "recipient_name": "Susan",
                    "recipient_address": "None",
                    "amount": "0.5",
                    "token_name": "Chainlink",
                    "token_address": "None"
                }}
            ]
            ```
            ---
            # Intent
            {intent}
            """
        )

    lm += gen("json", stop="```\n")

    return True, {
        "content": cleandoc(lm["json"]),
        "name": "interpreter",
        "role": "assistant",
    }


validator_system_message = """
You are a validator responsible for determining if a request is valid.
A request is only valid if it contains a Recipient Address, Amount, and Token Address.
If the request is valid, you must use \"NEXT: executor\" to pass the request to the executor.
If the request is invalid, list the missing information.
Be brief and clear.
You must append \"NEXT: broker\" to pass along your message.
"""

broker_system_message = """
You are a cryptocurrency copilot responsible for gathering missing information from the user necessary to complete their request.
After the user has satisfied all requirements, you will send the revised intent to the interpreter on their behalf.
Your messages to the interpreter must be in the following format:
---
Original Intent: Send .5 Chainlink to Susan
Recipient Address: 0x604f7cA57A338de9bbcE4ff0e2C41bAcE744Df03
Amount: 0.5
Token Address: 0x514910771AF9Ca656af840dff83E8264EcF986CA
NEXT: interpreter
"""

# TODO: Add new agent for showing tx preview, determining if any changes are needed, and
#       confirming if the user will proceed or cancel. Broker might be able to handle this.

# PROBLEM:  The executor expects a reply after sending the preview and signature link to the user.
#           However, the user must sign using the URL, not by replying to the executor.
#
#           - Maybe the prepare transaction function should send the preview and signature link to the user
#           and only return with a success or failure result.
#           - Another option might be to have the human input method to check if the last message
#           from the executor. If so, then it will reply either from the user or signing result.
#           Whichever comes first.

# TODO: Skip signature link for now and just have the user reply with proceed or cancel.
executor_system_message = """
You are an executor responsible for showing the user a preview of their transaction request
and asking them to confirm if they will proceed or cancel.
You must use the "a_prepare_transaction" function to prepare the transaction and get the preview.
After getting a confirmation from the user, you must use the "get_transaction_result"
function to get the outcome of the transaction and pass it along to the user.
You must append \"TERMINATE\" to pass along the result and end the conversation.
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


async def send(
    intent: str,
    user_reply: Callable[[], Awaitable[str]],
    assistant_reply: Callable[[str], None],
    prepare_transaction: Callable[[TxRequest], Awaitable[TxPreview]],
    get_transaction_result: Callable[[str], Awaitable[TxIdState]],
):
    # Interpreter: Guidance agent to convert intent into structured request

    # Validator: Determistic Pydantic agent. Is the request valid? What are the issues?

    # Broker: Collect missing information from user and update intent.

    # Round robin to Interpreter

    # Executor: Execute the request

    user_proxy = MessagingUserProxyAgent(
        "user",
        human_input_mode="ALWAYS",
        code_execution_config={"work_dir": "coding"},
        is_termination_msg=lambda x: x.get("content", "")
        and x.get("content", "").rstrip().endswith("TERMINATE"),
        a_human_reply=user_reply,
        assistant_reply=assistant_reply,
    )

    # No system message needed for OpenAI completion API used by Guidance agent.
    interpreter_agent = AssistantAgent("interpreter", llm_config=llm_config)
    interpreter_agent.register_reply(Agent, convert_to_request, 1)

    validator = AssistantAgent(
        "validator", system_message=validator_system_message, llm_config=llm_config
    )

    broker = AssistantAgent(
        "broker",
        system_message=broker_system_message,
        llm_config=llm_config,
    )

    executor = AssistantAgent(
        "executor", system_message=executor_system_message, llm_config=llm_config
    )

    technician = AssistantAgent(
        "technician", system_message=technician_system_message, llm_config=llm_config
    )

    @technician.register_for_execution()
    @executor.register_for_llm(
        description="Prepare a transaction for the user to review and sign."
    )
    async def a_prepare_transaction():
        tx_request = TxRequest(
            sender_did="ethereum://84738954.telegram.org",
            recipient_did="ethereum://0xc6A9f8f20d79Ae0F1ADf448A0C460178dB6655Cf",
            receive_token_address="0x514910771AF9Ca656af840dff83E8264EcF986CA",
            amount="0.0001",
        )
        return await prepare_transaction(tx_request)

    @technician.register_for_execution()
    @executor.register_for_llm(description="Get the results of a transaction.")
    async def a_get_transaction_result(tx_id: str):
        return await get_transaction_result(tx_id)

    groupchat = SendTokenGroupChat(
        agents=[user_proxy, interpreter_agent, validator, broker, executor, technician],
        messages=[],
        max_round=20,
    )
    manager = GroupChatManager(groupchat=groupchat, llm_config=llm_config)

    await user_proxy.a_initiate_chat(manager, message=intent)
