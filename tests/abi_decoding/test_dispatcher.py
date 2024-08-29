import json

from nethermind.entro.decoding import DecodingDispatcher
from nethermind.entro.decoding.event_decoders import EVMEventDecoder
from nethermind.entro.decoding.function_decoders import EVMFunctionDecoder
from nethermind.idealis.utils import to_bytes

from ..resources.ABI import ERC20_ABI_JSON, ERC721_ABI_JSON, UNISWAP_V2_PAIR_JSON


def test_abi_conflicts():
    dispatcher = DecodingDispatcher()

    dispatcher.add_abi("ERC20", json.loads(ERC20_ABI_JSON), 10)
    dispatcher.add_abi("UniswapV2Pair", json.loads(UNISWAP_V2_PAIR_JSON), 0)

    # Both UniV2 and ERC20 define decimals().  Make sure that the ERC20 version is prioritized
    decoder = dispatcher.function_decoders[b"1<\xe5g"]
    assert decoder.abi_name == "ERC20"
    assert isinstance(decoder, EVMFunctionDecoder)
    assert decoder.function_signature == "decimals()"


def test_overlapping_events():
    dispatcher = DecodingDispatcher()

    dispatcher.add_abi("ERC20", json.loads(ERC20_ABI_JSON), 10)
    dispatcher.add_abi("ERC721", json.loads(ERC721_ABI_JSON), 0)

    approval_events = dispatcher.event_decoders[
        to_bytes("8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b925")
    ]

    assert len(approval_events) == 2

    erc_20_approve = approval_events[2]
    assert isinstance(erc_20_approve, EVMEventDecoder)
    assert erc_20_approve.abi_name == "ERC20"
    assert erc_20_approve.event_signature == "Approval(address,address,uint256)"

    erc_721_approve = approval_events[3]
    assert isinstance(erc_721_approve, EVMEventDecoder)
    assert erc_721_approve.abi_name == "ERC721"
    assert erc_721_approve.event_signature == "Approval(address,address,uint256)"
