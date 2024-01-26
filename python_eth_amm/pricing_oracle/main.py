import datetime
import logging

from eth_typing import ChecksumAddress
from pandas import DataFrame
from sqlalchemy import select
from sqlalchemy.orm import Session

from python_eth_amm.addresses import STABLECOIN_ADDRESSES, USDC_ADDRESS, WETH_ADDRESS
from python_eth_amm.backfill.planner import BackfillPlan
from python_eth_amm.backfill.prices import update_pool_creations
from python_eth_amm.backfill.utils import get_current_block_number
from python_eth_amm.database.models import BackfilledRange
from python_eth_amm.database.readers.prices import get_supported_markets
from python_eth_amm.exceptions import OracleError
from python_eth_amm.pricing_oracle.timestamp_converter import TimestampConverter
from python_eth_amm.types.backfill import BackfillDataType, SupportedNetwork
from python_eth_amm.types.prices import AbstractTokenMarket, TokenMarketInfo

package_logger = logging.getLogger("python_eth_amm")
logger = package_logger.getChild("prices")


def _sort_tokens(
    a: ChecksumAddress, b: ChecksumAddress
) -> tuple[ChecksumAddress, ChecksumAddress]:
    """
    Sorts two token addresses as integer, and returns the sorted tuple.
    """
    return (b, a) if int(a, 16) > int(b, 16) else (a, b)


def _filter_markets(
    markets: list[TokenMarketInfo],
    # at_block: BlockIdentifier = "latest",
) -> TokenMarketInfo:
    """
    If there are multiple pools for a token pair, returns the pool that the price should be queries from.

    Currently this checks for a 30 bips pool, then checks for a 10 bips, then a 200.  This process should be
    refined in a future update to get the price from the pool with the most liquidity and activity

    :param markets:
        List of all markets for a token pair.
    :param at_block:
        Optional block identifier for filtering algo.  If filtering markets by active liquidity, will
        query the liquidity at the specified block.  If None, will use the current block.
    """
    if len(markets) == 0:
        raise ValueError("At least 1 market is required to filter")

    return markets[0]


class PriceOracle:
    """
    Interfacing class for processing price data from the database.
    """

    json_rpc: str
    " JSON RPC Endpoint for querying the blockchain "

    latest_block: int
    """ 
        Stores the most recent updated block number for the price oracle.  If a block number is requested that is
        greater than the latest block, it will auto-trigger an update from the database.  Fetching all prices
        will alsotrigger an update
    """

    network: SupportedNetwork
    " Network that the price oracle is running on.  [Default: Ethereum] "

    available_markets: dict[
        tuple[ChecksumAddress, ChecksumAddress], list[TokenMarketInfo]
    ]
    """
        Mapping between (token_a, token_b) and a list of all the onchain markets that can be used to price that
        token pair.  This is used to generate the list of all available markets for computing price mappings.

        The (token_a, token_b) tuple is sorted alphabetically, so that the same pair of tokens will always 
        map to the same list of markets.
    """

    timestamp_converter: TimestampConverter | None
    """
        Optional TimestampConverter instance.  If provided, will be used to convert block numbers to timestamps.
        If not provided, prices will be referenced in blocks instead of datetime.
    """

    weth_price: DataFrame | None
    """
        Stores the WETH to USD price from the database.  This is used to convert WETH prices to USD prices.
        for tokens that dont have a USDC pair, and are priced in WETH.
    """

    def __init__(self, json_rpc: str, db_session: Session, **kwargs):
        self.json_rpc = json_rpc
        self.db_session = db_session
        self.network = SupportedNetwork(kwargs.get("network", "ethereum"))
        self.latest_block = get_current_block_number(self.network)

        self.timestamp_converter = kwargs.get("timestamp_converter", None)

        self._generate_market_list()

    def update_price_feeds(self):
        """
        Updates all backfilled price feeds in the database to the latest block.  This function is intended to be run
        as a cron job to keep the price feeds up to date.

        It will update the WETH price, as well as any other token that has been backfilled in the database.

        ..warning::
            If the last backfilled price for a token is more than 1 week behind the latest block, the price will
            not be updated, and a warning will be logged.   Utilize the `backfill_prices()` method to extract
            historical price data.

        """
        self.latest_block = get_current_block_number(self.network)

        backfilled_price_data = self.db_session.execute(
            select(BackfilledRange).filter(
                BackfilledRange.data_type.in_(
                    [BackfillDataType.prices.value, BackfillDataType.spot_prices.value]
                ),
            )
        ).all()

        for pool in backfilled_price_data:
            if self.latest_block - pool.backfill_end > 50_400:  # 1 week of blocks
                logger.warning(
                    f"Skipping price update for {pool.priced_token} as the last backfill was more than 1 week ago."
                    f"To update the price, run the backfill_prices() method for the token before attempting to update"
                )
                continue

    def _generate_market_list(self):
        """
        Generates a list of all pools that are available for querying prices.  This list is generated from all
        creation events in the database.

        :return:
        """

        update_pool_creations(
            db_session=self.db_session,
            latest_block=self.latest_block,
            json_rpc=self.json_rpc,
            network=self.network,
        )
        self.available_markets = get_supported_markets(self.db_session)

    def _load_weth_to_usd_price(self):
        """
        Loads the WETH to USD price from the database.  This is used to convert WETH prices to USD prices.
        for tokens that dont have a USDC pair, and are priced in WETH.
        """

    def get_price_at_block(self, block_number: int, token_id: ChecksumAddress):
        """
        Returns the precise price of a token at a given block number.  Spot prices represent the pool's state at the
        end of a block.

        ..warning::
            This function performs a single database query, and returns the result without performing
            any safety checks.  If a price is backfilled to block 14m, and you query the price at block 15m, it will
            return the last price stored in the database (block 14m) and wont raise any warnings that the requested
            block is not backfilled.  For a safer way to query prices, use
            :py:func:`python_eth_amm.Pricing.get_price_over_time`

        :param block_number: Block Number to query price at
        :param token_id: Address of ERC20 Token that is being priced
        :return:
        """

    def backfill_prices(
        self,
        token_id: ChecksumAddress,
        start: int | datetime.date | None = None,
        end: int | datetime.date | None = None,
    ):
        """
        Backfill prices for a given token from the spot price on Uniswap V3 pools.  This data is extracted from Swap
        events, and is highly granular.  To backfill a price, convert the ERC20 token address to a checksummed address,\
        and then specify a start and end point.  The start and end bounds can be input as either a block number, or a
        datetime.date object.  If no start or end point is provided, it will backfill from the contract initialization
        block to the current block.

        .. warning::
            This function queries all swap events within a price range to generate the spot price.  On large pools
            like USDC/WETH, this backfill process can take hours depending on the speed of the RPC node.
            It is best to specify a start and end point for backfilling, and only backfill the price range needed.

        :param token_id:
            Hex Address of Token to be Priced
        :param start:
            Start point for backfill operation.  Can be input as a blocknumber, or a datetime.date object.
            If no start point is provided, it will backfill from the contract initialization block.
        :param end:
            End point for backfill operation.  Can be input as a blocknumber, or a datetime.date object.
            If no end point is provided, it will backfill to the current block.

        """
        if token_id in STABLECOIN_ADDRESSES:
            raise OracleError(
                f"Token {token_id} is a stablecoin, and does not need to be priced."
            )

        if (
            not isinstance(start, int) or not isinstance(end, int)
        ) and self.timestamp_converter is None:
            raise OracleError(
                "Timestamp Converter is required to backfill prices when start or end is specified as a date. "
                "Provide a TimestampConverter, or specify start and end limits as block numbers"
            )

        usdc_pools = self.available_markets.get(
            _sort_tokens(token_id, USDC_ADDRESS), []
        )
        if usdc_pools:
            backfill_pool = _filter_markets(usdc_pools)
        else:
            weth_pool = _filter_markets(
                self.available_markets.get(_sort_tokens(token_id, WETH_ADDRESS), [])
            )

    def backfill_weth_price(self):
        """
        Backfills the WETH price from the USDC/WETH pool.  This is used to convert WETH prices to USD prices.
        for tokens that dont have a USDC pair, and are priced in WETH.  Is also used for the Baseline WETH Price
        """

        usdc_weth_pool = _filter_markets(
            self.available_markets.get(_sort_tokens(USDC_ADDRESS, WETH_ADDRESS), [])
        )

        self.backfill_spot_price(usdc_weth_pool)

    def backfill_spot_price(self, market_info: TokenMarketInfo):
        """

        :param market_info:
        :return:
        """

        backfill_plan = BackfillPlan.generate(
            db_session=self.db_session,
            backfill_type=BackfillDataType.spot_prices,
            network=self.network,
            start_block=market_info.initialization_block,
            end_block=self.latest_block,
            market_address=market_info.market_address,
            market_protocol=market_info.pool_class,
        )
        pass
