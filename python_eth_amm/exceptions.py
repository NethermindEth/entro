class ArchivalNodeRequired(Exception):
    """

    Raised when archival features of an RPC connection are inadequate, and simulations need to be reworked, or
    node infrastructure needs to be upgraded.

    """


class BackfillError(Exception):
    """

    Raised when issues occur with backfilling data

    """


class BackfillRateLimitError(BackfillError):
    """Raised when gateway rate limits are implmented by the remote host"""


class BackfillHostError(BackfillError):
    """Raised when the remote host returns error, fails to provide correct data, or when timeout occurs"""


class DatabaseError(Exception):
    """

    Raised when issues occur with database operations

    """


class DecodingError(Exception):
    """

    Raised when issues occur with input decoding during data backfills

    """


class UniswapV3Revert(Exception):
    """
    Uniswap V3 Revert Exception is thrown when a pool action causes behavior that would throw a revert on-chain.
    The following conditions will result in this error being raised:

        * Ticks exceed the maximum tick value of 887272 or the minimum tick value of -887272
        * uint values are set to a negative value
        * operations cause uints and ints to overflow or underflow
        * Minting & Burning positions with zero liquidity
        * Executing Swaps with invalid sqrt_price bounds or zero input

    """


class FullMathRevert(Exception):
    """
    Raised when the result of (a * b) / c overflows the maximum value of a uint256.

    Will typically trigger a `UniswapV3Revert`
    """


class TickMathRevert(Exception):
    """
    Raised when a tick value is out of bounds, or a sqrt_price exceeds the maximum sqrt_price
    """


class SqrtPriceMathRevert(Exception):
    """
    Raised when a sqrt_price value is out of bounds, or the inputs to a price calculation are
    invalid, ie swapping with zero input or swapping with a sqrt_price limit in the opposite direction
    """


class OracleError(Exception):
    """
    Raised when PricingOracle fails to return a valid price.  Typically caused when the oracle cannot
    extract the prices for a token.  Troubleshooting steps:

    * Verify that all addresses are checksummed with eth_utils.to_checksum_address
    * Check the token address on etherscan to ensure it is a valid ERC20 token
    * Double check that RPC connection is working & node is synced to correct chain

    """
