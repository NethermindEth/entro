import json

from nethermind.entro.decoding import DecodingDispatcher

from ..resources.ABI import ERC20_ABI_JSON, ERC721_ABI_JSON, UNISWAP_V2_PAIR_JSON


def test_abi_conflicts():
    dispatcher = DecodingDispatcher()

    dispatcher.add_abi("ERC20", json.loads(ERC20_ABI_JSON), 10)
    dispatcher.add_abi("UniswapV2Pair", json.loads(UNISWAP_V2_PAIR_JSON), 0)

    # Both UniV2 and ERC20 define decimals().  Make sure that the ERC20 version is prioritized
    decoding_result = dispatcher.decode_function(bytes.fromhex("313ce567"))

    assert decoding_result.function_signature == "decimals()"
    assert decoding_result.abi_name == "ERC20"
    assert decoding_result.decoded_input == {}


def test_overlapping_events():
    dispatcher = DecodingDispatcher()

    dispatcher.add_abi("ERC20", json.loads(ERC20_ABI_JSON), 10)
    dispatcher.add_abi("ERC721", json.loads(ERC721_ABI_JSON), 0)

    erc_20_decoding_result = dispatcher.decode_log(
        {
            "topics": [
                "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                "0x000000000000000000000000c0140cfc3988101a7c1ac769af92fb1ffca80f58",
                "0x000000000000000000000000ae542fc36f457426f3711747dc2340f5ac8b560f",
            ],
            "data": "0x00000000000000000000000000000000000000000000000000000014bdafe400",
            "address": "0x2565ae0385659badcada1031db704442e1b69982",
            "transactionHash": "0xabcef",
        }
    )

    erc_721_decoding_result = dispatcher.decode_log(
        {
            "topics": [
                "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                "0x000000000000000000000000c0140cfc3988101a7c1ac769af92fb1ffca80f58",
                "0x000000000000000000000000ae542fc36f457426f3711747dc2340f5ac8b560f",
                "0x0000000000000000000000000000000000000000000000000000000000000ab4",
            ],
            "data": "",
            "address": "0x2565ae0385659badcada1031db704442e1b69982",
            "transactionHash": "0xabcef",
        }
    )

    assert erc_20_decoding_result.event_signature == "Transfer(address,address,uint256)"
    assert erc_20_decoding_result.abi_name == "ERC20"
    assert erc_20_decoding_result.event_data["from"] == "0xC0140CFC3988101A7C1aC769aF92Fb1fFCa80F58"
    assert erc_20_decoding_result.event_data["to"] == "0xae542fc36F457426f3711747Dc2340f5Ac8B560F"
    assert erc_20_decoding_result.event_data["value"] == 89081766912

    assert erc_721_decoding_result.event_signature == "Transfer(address,address,uint256)"
    assert erc_721_decoding_result.abi_name == "ERC721"
    assert erc_721_decoding_result.event_data["from"] == "0xC0140CFC3988101A7C1aC769aF92Fb1fFCa80F58"
    assert erc_721_decoding_result.event_data["to"] == "0xae542fc36F457426f3711747Dc2340f5Ac8B560F"
    assert erc_721_decoding_result.event_data["tokenId"] == 0xAB4
