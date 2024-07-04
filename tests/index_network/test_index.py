import pytest
from indexclient import IndexClient
from web3 import Web3

w3 = Web3()
acc = w3.eth.account.create()


"""@pytest.mark.parametrize(
    "message, expected",
    [
        ("Send 5 Bitcoin to Alice", ""),
    ],
)"""


# @pytest.mark.skip
async def test_index_network():
    print(f'private key={w3.to_hex(acc.key)}, account={acc.address}')
    client = IndexClient(
        domain="emberai.xyz",
        # private_key=w3.to_hex(acc.key),
        wallet=acc,
        network="ethereum",  # Specify the network you're working on
    )
    client.authenticate()
    print("authentication successful")
