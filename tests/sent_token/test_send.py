import asyncio
import uuid
from typing import List

import pytest
from ember_agents.send_token.send import (
    TxDetails,
    TxIdState,
    TxPreview,
    TxRequest,
    send,
)

pytest_plugins = "pytest_asyncio"


@pytest.mark.parametrize(
    "intent, user_replies",
    [
        (
            ".0001 link to joe",
            [
                "0xc6A9f8f20d79Ae0F1ADf448A0C460178dB6655Cf is joe's address. Use whatever you have for link.",
                "execute",
            ],
        ),
        # ("Send 5 Bitcoin to 0x2D6c1025994dB45c7618571d6cB49B064DA9881B", ""),
        # ("send token", ""),
    ],
)
async def test_send(intent: str, user_replies: List[str]):
    async def user_reply():
        print("awaiting user reply")
        await asyncio.sleep(1)
        print("sending user reply")

        return user_replies.pop(0)

    def assistant_reply(message: str):
        print(f"ASSISTANT: {message}")

    tx_details = TxDetails(
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
    )

    async def prepare_transaction(tx_request: TxRequest):
        print(f"preparing transaction:\n{tx_request}")
        await asyncio.sleep(3)
        tx_preview = TxPreview(
            tx_id=str(uuid.uuid4()),
            tx_details=tx_details,
            signature_link="https://ember.ai/tx/1234",
        )
        return tx_preview

    async def get_transaction_result(tx_id: str):
        print(f"getting update for transaction id: {tx_id}")
        await asyncio.sleep(1)
        tx_status = TxIdState(
            tx_id,
            tx_hash="0xeef10fc5170f669b86c4cd0444882a96087221325f8bf2f55d6188633aa7be7c",
            explorer_link="https://etherscan.io/tx/0xeef10fc5170f669b86c4cd0444882a96087221325f8bf2f55d6188633aa7be7c",
            confirmations=6,
            state="finalized",
            final_tx_details=tx_details,
        )
        return tx_status

    await send(
        intent, user_reply, assistant_reply, prepare_transaction, get_transaction_result
    )
