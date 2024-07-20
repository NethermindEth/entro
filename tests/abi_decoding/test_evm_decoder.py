import json

from eth_utils import to_checksum_address as tca

from nethermind.entro.decoding.event_decoders import EVMEventDecoder
from nethermind.idealis.utils import to_bytes
from tests.resources.ABI import ERC20_ABI_JSON, ERC721_ABI_JSON

ERC_20_ABI = json.loads(ERC20_ABI_JSON)
ERC721_ABI = json.loads(ERC721_ABI_JSON)


def test_decoder_initialization():
    decoder_instance = EVMEventDecoder("ERC20", ERC_20_ABI)

    loaded_functions = [func.function_signature for func in decoder_instance.function_decoders.values()]
    loaded_events = [event.event_signature for event in decoder_instance.event_decoders.values()]

    assert "transfer(address,uint256)" in loaded_functions
    assert "transferFrom(address,address,uint256)" in loaded_functions
    assert "balanceOf(address)" in loaded_functions

    assert "Transfer(address,address,uint256)" in loaded_events
    assert "Approval(address,address,uint256)" in loaded_events


def test_decode_transfers():
    decoder_instance = EVMEventDecoder("ERC20", ERC_20_ABI)

    address_1 = "000000000000000000000000f8e81D47203A594245E36C48e151709F0C19fBe8"
    address_2 = "000000000000000000000000bEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7"
    amount = "000000000000000000000000000000000000000000000000000000000227376b"

    transfer_calldata = bytes.fromhex("a9059cbb" + address_1 + amount)
    transfer_from_calldata = bytes.fromhex("23b872dd" + address_1 + address_2 + amount)

    decoded_transfer = decoder_instance.decode_function(transfer_calldata)
    decoded_transfer_from = decoder_instance.decode_function(transfer_from_calldata)

    assert decoded_transfer[0] == "transfer(address,uint256)"
    assert decoded_transfer[1]["recipient"] == "0xf8e81D47203A594245E36C48e151709F0C19fBe8"
    assert decoded_transfer[1]["amount"] == 36124523

    assert decoded_transfer_from[0] == "transferFrom(address,address,uint256)"
    assert decoded_transfer_from[1]["recipient"] == "0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7"
    assert decoded_transfer_from[1]["amount"] == 36124523


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

    decoder = EVMDecoder("TestABI", test_abi)

    assert "febf2115" in decoder.function_decoders.keys()

    uint1 = "0000000000000000000000000000000000000000000000000000000000000001"
    uint2 = "0000000000000000000000000000000000000000000000000000000000000120"

    decoded_tx = decoder.decode_function(bytes.fromhex("febf2115" + uint1 + uint2))
    assert decoded_tx[0] == "testFunction((uint256,uint256))"
    assert decoded_tx[1] == {"testTuple": (1, 288)}


def test_erc20_transfer_event_decoding():
    decoder_instance = EVMDecoder("ERC20", ERC_20_ABI)

    sig, data = decoder_instance.decode_event(
        topics=[
            to_bytes("ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"),
            to_bytes("000000000000000000000000c0140cfc3988101a7c1ac769af92fb1ffca80f58"),
            to_bytes("000000000000000000000000ae542fc36f457426f3711747dc2340f5ac8b560f"),
        ],
        data=to_bytes("0x00000000000000000000000000000000000000000000079d1561aacbdc064000"),
    )

    assert sig == "Transfer(address,address,uint256)"
    assert data["from"] == tca("0xC0140CFC3988101A7C1aC769aF92Fb1fFCa80F58")
    assert data["to"] == tca("0xae542fc36F457426f3711747Dc2340f5Ac8B560F")
    assert data["value"] == 35954244900000000000000


def test_erc721_event_decoding():
    decoder_instance = EVMDecoder("ERC721", ERC721_ABI)

    sig, data = decoder_instance.decode_event(
        topics=[
            to_bytes("ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"),
            to_bytes("000000000000000000000000f8e81d47203a594245e36c48e151709f0c19fbe8"),
            to_bytes("000000000000000000000000bebc44782c7db0a1a60cb6fe97d0b483032ff1c7"),
            to_bytes("0000000000000000000000000000000000000000000000000000000000000bf3"),
        ],
        data=b"",
    )

    assert sig == "Transfer(address,address,uint256)"

    assert data["from"] == tca("0xf8e81d47203a594245e36c48e151709f0c19fbe8")
    assert data["to"] == tca("0xbebc44782c7db0a1a60cb6fe97d0b483032ff1c7")
    assert data["tokenId"] == 0xBF3
