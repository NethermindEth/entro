from eth_typing import ChecksumAddress
from eth_utils import to_checksum_address as tca

# Major ERC20 Tokens
USDC_ADDRESS: ChecksumAddress = tca("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48")
WETH_ADDRESS: ChecksumAddress = tca("0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2")


# Uniswap Adresses
UNISWAP_V3_FACTORY = tca("0x1F98431c8aD98523631AE4a59f267346ea31F984")
UNISWAP_V2_FACTORY = tca("0x5c69bee701ef814a2b6a3edd4b1652cb9cc5aa6f")
# Rollup & L2 Addresses
