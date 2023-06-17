class ArchivalNodeRequired(Exception):
    """

    Raised when archival features of an RPC connection are inadequate, and simulations need to be reworked, or
    node infrastructure needs to be upgraded.

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


class PriceBackfillError(Exception):
    """
    # TODO: Add docstring
    """
