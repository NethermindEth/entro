import json

from eth_utils import to_checksum_address as tca

from nethermind.entro.decoding.dispatcher import (
    DecodingDispatcher,
    filter_events,
    filter_functions,
)
from nethermind.entro.decoding.event_decoders import EVMEventDecoder
from nethermind.entro.decoding.function_decoders import EVMFunctionDecoder
from nethermind.idealis.utils import to_bytes
from tests.resources.ABI import ERC20_ABI_JSON, ERC721_ABI_JSON

ERC_20_ABI = json.loads(ERC20_ABI_JSON)
ERC721_ABI = json.loads(ERC721_ABI_JSON)


def test_decoder_initialization():
    decoder_instance = DecodingDispatcher("EVM")

    decoder_instance.add_abi("ERC20", ERC_20_ABI, 10)
    decoder_instance.add_abi("ERC721", ERC721_ABI, 0)

    loaded_functions = [func.id_str(True) for func in decoder_instance.function_decoders.values()]
    loaded_events = [event.id_str(True) for event in decoder_instance.get_flattened_events()]

    assert "transfer(address,uint256)" in loaded_functions
    assert "transferFrom(address,address,uint256)" in loaded_functions
    assert "balanceOf(address)" in loaded_functions

    assert "Transfer(address,address,uint256)" in loaded_events
    assert "Approval(address,address,uint256)" in loaded_events


def test_decode_transfers():
    funcs = filter_functions(ERC_20_ABI)
    transfer_func = [f for f in funcs if f["name"] == "transfer"][0]
    transfer_from_func = [f for f in funcs if f["name"] == "transferFrom"][0]

    transfer_decoder = EVMFunctionDecoder(transfer_func, "ERC20", 100)
    transfer_from_decoder = EVMFunctionDecoder(transfer_from_func, "ERC20", 100)

    address_1 = "000000000000000000000000f8e81D47203A594245E36C48e151709F0C19fBe8"
    address_2 = "000000000000000000000000bEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7"
    amount = "000000000000000000000000000000000000000000000000000000000227376b"

    decoded_transfer = transfer_decoder.decode([to_bytes(address_1), to_bytes(amount)])
    decoded_transfer_from = transfer_from_decoder.decode([to_bytes(address_1), to_bytes(address_2), to_bytes(amount)])

    assert decoded_transfer.name == "transfer"
    assert decoded_transfer.inputs["recipient"] == "0xf8e81D47203A594245E36C48e151709F0C19fBe8"
    assert decoded_transfer.inputs["amount"] == 36124523

    assert decoded_transfer_from.name == "transferFrom"
    assert decoded_transfer_from.inputs["recipient"] == "0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7"
    assert decoded_transfer_from.inputs["amount"] == 36124523


def test_decode_function_with_tuple_argument():
    test_abi = [
        {
            "name": "testFunction",
            "type": "function",
            "inputs": [
                {
                    "name": "testTuple",
                    "type": "tuple",
                    "components": [
                        {"name": "testTupleParameter0", "type": "uint256"},
                        {"name": "testTupleParameter1", "type": "uint256"},
                    ],
                }
            ],
            "outputs": [],
        }
    ]

    decoder = EVMFunctionDecoder(test_abi[0], "TestABI", 200)

    decoder.signature = bytes.fromhex("febf2115")

    uint1 = "0000000000000000000000000000000000000000000000000000000000000001"
    uint2 = "0000000000000000000000000000000000000000000000000000000000000120"

    decoded_tx = decoder.decode([to_bytes(uint1), to_bytes(uint2)])
    assert decoded_tx.name == "testFunction"
    assert decoded_tx.inputs == {"testTuple": (1, 288)}


def test_erc20_transfer_event_decoding():
    transfer_event = [event for event in filter_events(ERC_20_ABI) if event["name"] == "Transfer"][0]

    decoder_instance = EVMEventDecoder(transfer_event, "ERC20")

    decoded = decoder_instance.decode(
        data=[to_bytes("0x00000000000000000000000000000000000000000000079d1561aacbdc064000")],
        keys=[
            to_bytes("ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"),
            to_bytes("000000000000000000000000c0140cfc3988101a7c1ac769af92fb1ffca80f58"),
            to_bytes("000000000000000000000000ae542fc36f457426f3711747dc2340f5ac8b560f"),
        ],
    )

    assert decoded.name == "Transfer"
    assert decoded.data["from"] == tca("0xC0140CFC3988101A7C1aC769aF92Fb1fFCa80F58")
    assert decoded.data["to"] == tca("0xae542fc36F457426f3711747Dc2340f5Ac8B560F")
    assert decoded.data["value"] == 35954244900000000000000


def test_erc721_event_decoding():
    transfer_event = [event for event in filter_events(ERC721_ABI) if event["name"] == "Transfer"][0]

    decoder_instance = EVMEventDecoder(transfer_event, "ERC721")

    decoded = decoder_instance.decode(
        keys=[
            to_bytes("ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"),
            to_bytes("000000000000000000000000f8e81d47203a594245e36c48e151709f0c19fbe8"),
            to_bytes("000000000000000000000000bebc44782c7db0a1a60cb6fe97d0b483032ff1c7"),
            to_bytes("0000000000000000000000000000000000000000000000000000000000000bf3"),
        ],
        data=[b""],
    )

    assert decoded.name == "Transfer"

    assert decoded.data["from"] == tca("0xf8e81d47203a594245e36c48e151709f0c19fbe8")
    assert decoded.data["to"] == tca("0xbebc44782c7db0a1a60cb6fe97d0b483032ff1c7")
    assert decoded.data["tokenId"] == 0xBF3
