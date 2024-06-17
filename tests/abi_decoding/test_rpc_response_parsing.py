from nethermind.entro.backfill.utils import rpc_response_to_block_model
from nethermind.entro.database.models.starknet import Block as StarknetBlock
from nethermind.entro.decoding import DecodingDispatcher
from nethermind.entro.types.backfill import SupportedNetwork
from tests.resources.rpc_responses import (
    STARKNET_GET_BLOCK_WITH_TX_HASHES,
    STARKNET_GET_BLOCK_WITH_TXS,
)


def test_starknet_basic_block_sqlite():
    starknet_block, txns = rpc_response_to_block_model(
        block=STARKNET_GET_BLOCK_WITH_TX_HASHES,
        network=SupportedNetwork.starknet,
        db_dialect="sqlite",
        abi_decoder=DecodingDispatcher(),
    )

    assert isinstance(starknet_block, StarknetBlock)
    assert len(txns) == 0

    assert starknet_block.block_hash == "0x3a095054a69b74031cefb69117589868a710c510c2d74e5642890a30f7cb257"
    assert starknet_block.block_number == 488504


def test_starknet_block_postgres():
    block, txns = rpc_response_to_block_model(
        block=STARKNET_GET_BLOCK_WITH_TXS,
        network=SupportedNetwork.starknet,
        db_dialect="postgres",
        abi_decoder=DecodingDispatcher(),
    )

    assert isinstance(block, StarknetBlock)
    assert len(txns) == 149

    # TODO: Check that binary fields are encoded correctly


def test_invalid_networks():
    # Verify that we raise an exception when we get a network that we don't support.
    # Properly handle KeyErrors and raise appropiriate warnings and errors.
    pass
