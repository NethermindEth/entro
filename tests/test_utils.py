from python_eth_amm.utils import camel_to_snake


def test_camel_to_snake_conversion():
    assert camel_to_snake("camelCase") == "camel_case"
    assert camel_to_snake("CamelCase") == "camel_case"
    assert camel_to_snake("amount0") == "amount_0"
    assert camel_to_snake("amount1LessFee") == "amount_1_less_fee"
    assert camel_to_snake("amountUSD") == "amount_usd"
    assert camel_to_snake("ERC20ABI") == "erc_20_abi"
    assert camel_to_snake("ERC1175") == "erc_1175"
