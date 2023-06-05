from typing import Optional

from eth_typing import ChecksumAddress
from pydantic import BaseModel

from python_eth_amm.base.token import ERC20Token


class JSONEncodingBaseModel(BaseModel):
    """Abstract Pydantic Model with JSON Encoder for ChecksumAddress"""

    class Config:
        """JSON Encoder"""

        json_encoders = {
            ChecksumAddress: lambda v: v.hex(),
        }


class Slot0(BaseModel):
    """Stores the current price, tick, and oracle info"""

    sqrt_price: int
    """
        Current Exchange rate between token_0 and token_1.
        
        This value is represented as the square root of the ratio between token_0 and token_1, in a 
        fixed point Q64.96 Number (64 bits of integer precision & 96 bits of fractional precision).
    """
    tick: int
    """
        Current Tick of the Pool.  Ticks are discrete price ranges representing a 0.1% change in price.
        
        The Token 0 to Token 1 exchange rate at a tick can be calculated by the following formula:
        1.0001 ** tick
    """
    observation_index: int
    """
        Current index that is used internally to store the oracle data.
    """
    observation_cardinality: int
    """
        Current number of observations stored in the oracle.  When this value is increased, the oracle stores
        more price history within the oracle.
    """
    observation_cardinality_next: int
    """
        Parameter that is used when increasing the historical prices within the oracle.
    """
    fee_protocol: int
    """
        Amount of swap fees that are given to the Uniswap Protocol.  This is currently turned off on all official
        Uniswap deployments, but can be turned on by governance at a later date.
    """

    @classmethod
    def uninitialized(cls) -> "Slot0":
        """Returns an uninitialized slot0 used during pool initialization"""
        return Slot0(
            sqrt_price=79228162514264337593543950336,  # 1 for 1
            tick=0,
            observation_index=0,
            observation_cardinality=1,
            observation_cardinality_next=1,
            fee_protocol=0,
        )


class PoolState(BaseModel):
    """Stores the current balances, liquidity, and fee growths"""

    liquidity: int  # Current amount of active liquidity
    """
    Amount of active liquidity.  This parameter remains constant during swaps where the price does not move ticks.
    When crossing a tick, this value is increased or reduced.
    """
    fee_growth_global_0: int  # Parameters for tracking fee accumulation
    """
    Tracks fee accumulation for token_0.  When selling token_0, the swap fee is collected in token_0, and addded to
    this accumulator.  When a position is modified or burned, the position fees are calculated from this 
    global accumulator. 
    """
    fee_growth_global_1: int
    """
    Tracks fee accumulation for token_1.  When selling token_1, the swap fee is collected in token_1.
    """
    balance_0: int  # Current balance of token_0 in pool
    """
    Current balance of token_0 in pool.  This value is modified during each swap, and liquidity modification.
    """
    balance_1: int
    """
    Current balance of token_1 in pool.  This value is modified during each swap, and liquidity modification.
    """

    @classmethod
    def uninitialized(cls) -> "PoolState":
        """Returns an uninitialized pool state used during pool initialization"""
        return PoolState(
            liquidity=0,
            fee_growth_global_0=0,
            fee_growth_global_1=0,
            balance_0=0,
            balance_1=0,
        )


class PoolImmutables(BaseModel):
    """
    Stores the pool's immutable parameters that are set once during pool initialization and will
    never change.

    """

    pool_address: ChecksumAddress
    """
        Deployment address of the pool contract.
    """
    token_0: ERC20Token
    """
        The Token 0 of the pool that can be bought and sold through this pool
    """
    token_1: ERC20Token
    """
        The Token 1 of the pool that can be bought and sold through this pool
    """
    fee: int
    """
        The fee that is charged on each swap.  This value is measured in hundredths of a bip (0.0001%).
        
        A pool with a 0.3% swap fee would have an immutable fee value of 3000, and a .05% pool would 
        have an immutable fee parameter of 500
    """

    tick_spacing: int
    """
        Number of ticks between liquidity deployments.  On a pool with a 0.3% swap fee, the tick spacing is 60 
        (.6% minimum liquidity ranges)  Lower tick spacings increase precision for liquidity providers, but 
        each tick crossing requires several SSLOAD and SSTORE operations, increasing the cost of swaps.  
        On low fee pools with stable assets, tick spacings are low since prices dont fluctuate frequently, 
        and the tick spacing on a 1% pool is 200 (2% minimum liquidity ranges) 
        to reduce the number of ticks that need to be crossed when swapping a volatile asset.
    """

    max_liquidity_per_tick: int
    """
        Parameter that is used to limit the amount of liquidity that can be deployed to a single tick.  This parameter
        is initialized based on the total amount of liquidity that can ever be active without causing overflows, and
        divides that by the number of usable ticks within the pool
    """


class Tick(BaseModel):
    """Stores liquidity data and fee growth for each tick"""

    liquidity_gross: int  # 128
    """ Total liquidity owned by all positions that use this tick as an upper tick or a lower tick.
    used by the pool to determine if it is okay to delete a tick when a position is removed.
    """
    liquidity_net: int  # 128
    """
    Net liquidity to add/remove from the pool when a swap moves the price across tick boundaries.
    If price is moving up, add liquidity_net to current liquidity.
    If price is moving down, liquidity_net is subtracted from current liquidity.
    """
    fee_growth_outside_0: int  # 256
    """
        Internal parameter tracking fee growth per unit of liquidity when the liquidity in this tick is inactive
    """
    fee_growth_outside_1: int  # 256
    """
        Internal parameter tracking the fee growth that occurs when this tick is not active.  Used to calculate fees
        and position valuations
    """
    tick_cumulative_outside: int  # 56
    """
        the cumulative tick value on the other side of the tick
    """
    seconds_per_liquidity_outside: int  # 160
    """
        Internal parameter that tracks the seconds per liquidity outside of this tick.  Used to calculate fees
    """
    seconds_outside: int  # 32
    """
        Internal fee accrual tracking parameter
    """

    @classmethod
    def uninitialized(cls) -> "Tick":
        """
        Returns an uninitialized tick with each field set to 0
        """
        return Tick(
            liquidity_gross=0,
            liquidity_net=0,
            fee_growth_outside_0=0,
            fee_growth_outside_1=0,
            tick_cumulative_outside=0,
            seconds_per_liquidity_outside=0,
            seconds_outside=0,
        )


class PositionInfo(BaseModel):
    """
    Stores the current liquidity, fee growth, and fees owed for each position.

    .. note::
        This data is semi-stateful, and doesnt represent the value of a position at a given time.  In order
        to compute the token_0 and token_1 value of a position at a given time, the best mechanism through
        this library is the save_position_snapshot() function.
    """

    liquidity: int  # Amount of Liquidity Owned by this Position
    """ 
        Amount of liquidity owned by this position
    """

    fee_growth_inside_0_last: int  # fee growth per unit of ticks since last ticks update
    """
        Token 0 fee growth per unit of ticks since last ticks update.  This paramter is allowed to underflow in the 
        Uniswap Codebase, creating bizzare behavior.  If the value of this field is a number greater than 10 ** 77, 
        the value has underflowed.  This is expected behavior, and is handled by the library.
    """
    fee_growth_inside_1_last: int
    """
        Token 1 Fee growth per unit of ticks since last ticks update.  This paramter is allowed to underflow in the
        same manner as fee_growth_inside_0_last
    """
    tokens_owed_0: int  # fees owed to position owner
    """
        Number of token_0 owed to the position owner.  Is only updated when position is burned
    """
    tokens_owed_1: int
    """
        Number of token_1 owed to the position owner.  Is only updated when position is burned
    """

    @classmethod
    def uninitialized(cls) -> "PositionInfo":
        """
        Returns an uninitialized position info with each field set to 0
        """
        return PositionInfo(
            liquidity=0,
            fee_growth_inside_0_last=0,
            fee_growth_inside_1_last=0,
            tokens_owed_0=0,
            tokens_owed_1=0,
        )


class OracleObservation(BaseModel):
    """Stores oracle observation data"""

    block_timestamp: int
    tick_cumulative: int
    seconds_per_liquidity_cumulative: int
    initialized: bool

    @classmethod
    def uninitialized(cls) -> "OracleObservation":
        """
        Returns an uninitialized oracle observation with each field set to 0
        :return: OracleObservation
        """
        return OracleObservation(
            block_timestamp=0,
            tick_cumulative=0,
            seconds_per_liquidity_cumulative=0,
            initialized=False,
        )


class SwapCache(BaseModel):
    """Model used to track initial state throughout swap computation"""

    liquidity_start: int
    """ 
        Amount of liquidity in the pool at the start of the swap. Caches the PoolState.liquidity value into memory. 
    """
    block_timestamp: int
    """ Block timestamp of the current swap execution """
    fee_protocol: int
    """ Protocol fee for the current swap.  Is currently always zero on mainnet pools """
    seconds_per_liquidity_cumulative: int
    """ Seconds per liquidity cumulative for the current swap.  Caches values extracted from the oracle """
    tick_cumulative: int
    """ Tick cumulative for the current swap.  Caches values extracted from the oracle """
    computed_last_observation: bool
    """ 
        Flag to indicate if the last observation has been computed.  Used to determine whether the pool should 
        write an oracle entry at the next tick crossing
    """


class SwapState(BaseModel):
    """Model to store the pool state during swap execution"""

    amount_specified_remaining: int
    amount_calculated: int
    sqrt_price: int
    tick: int
    fee_growth_global: int
    protocol_fee: int
    liquidity: int


class SwapStep(BaseModel):
    """Model to store the results of a single swap step"""

    sqrt_price_start: Optional[int] = None
    tick_next: Optional[int] = None
    sqrt_price_next: Optional[int] = None
    amount_in: Optional[int] = None
    amount_out: Optional[int] = None
    fee_amount: Optional[int] = None
