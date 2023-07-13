import logging
from decimal import getcontext
from logging import Logger
from typing import Dict, List, Literal, Optional, Type

from eth_utils import to_checksum_address
from sqlalchemy.engine import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from web3 import Web3

from python_eth_amm.math import (
    ExactMathModule,
    FullMathModule,
    SqrtPriceMathModule,
    TickMathModule,
    TranslatedMathModule,
    UniswapV3SwapMath,
)
from python_eth_amm.pricing_oracle import PricingOracle
from python_eth_amm.uniswap_v3 import UniswapV3Pool


class PoolFactory:
    """
    Pool Factory class for initializing pools.

    :param Optional[web3.Web3] w3:
        Web3 RPC Connection
    :param Optional[bool] exact_math = False:
        If True, initializes test evm & deploys math modules
    :param str sqlalchemy_uri:
        URI for sqlalchemy database.
        Database is used for caching on-chain events, and logging pool state for anaytics purposes
    :param Optional[Logger] logger:
        Logger instance
    """

    w3: Optional[Web3]  # pylint: disable=invalid-name
    """
    :class:`~web3.Web3` Archival RPC Connection for querying on-chain state & events
    """

    loaded_math_modules: Dict[str, ExactMathModule | TranslatedMathModule]
    exact_math: bool = False
    logger: logging.Logger
    """
    Logger instance for all pools initialized by this factory instance.
    Logs to stdout by default with INFO level.
    Logs are split into the following levels:

        **INFO**

        * RPC Event Queries
        * Output of Swaps
        * Info on minting & burning of liquidity positions
        * Tick Crossings & Liquidity Activation/Deactivation

        **DEBUG**

        * Individual Swap Steps & Fee Amount Accruals
        * Price Slippage casued by trades
    """

    sqlalchemy_engine: Engine
    """
    :class:`~sqlalchemy.engine.Engine` for caching on-chain events & pool state
    """

    initialized_pools: List = []

    """
    List of all pools initialized by this factory instance.
    
    :return: List of Pools initialized by the factory
    """

    oracle: Optional[PricingOracle] = None
    """ 
    Pricing oracle to be used for converting token prices to USD.  
    
    Initialized by calling :meth:`initialize_pricing_oracle`
    """

    _initialized_classes: List[str]

    def __init__(
        self,
        sqlalchemy_uri: str,
        w3: Optional[Web3] = None,  # pylint: disable=invalid-name
        exact_math: Optional[bool] = False,
        logger: Optional[Logger] = None,
    ):
        self.loaded_math_modules = {}
        self.w3 = w3  # pylint: disable=invalid-name
        self._initialized_classes = []

        if exact_math:
            # pylint: disable=import-outside-toplevel,no-name-in-module,import-error
            from pyrevm import EVM  # type: ignore[attr-defined]

            # pylint: enable=import-outside-toplevel,no-name-in-module,import-error

            getcontext().prec = 80

            self.exact_math = True
            self.evm_state = EVM()

        if logger is None:
            self.logger = logging.getLogger("python_eth_amm")
            self.logger.setLevel(logging.INFO)

        else:
            self.logger = logger

        self.sqlalchemy_engine = create_engine(
            sqlalchemy_uri if sqlalchemy_uri else "sqlite:///:memory:"
        )

    def pool_pre_init(self, pool_type: Literal["uniswap_v3"]):
        """
        Runs Migrations & Setup for Pool Class.  Called internally each time a pool is initialized.

        :param pool_type: Pool Type to Initialize
        """
        if pool_type not in self._initialized_classes:
            self.logger.info(f"Initializing {pool_type} Pool Class")
            match pool_type:
                case "uniswap_v3":
                    UniswapV3Pool.migrate_up(self.sqlalchemy_engine)
                    tick_math = TickMathModule(factory=self)
                    full_math = FullMathModule(factory=self)
                    sqrt_price_math = SqrtPriceMathModule(factory=self)
                    exact_math_modules = {
                        "TickMathModule": tick_math,
                        "FullMathModule": full_math,
                        "SqrtPriceMathModule": sqrt_price_math,
                    }
                    self.loaded_math_modules.update(exact_math_modules)

                    if self.exact_math:
                        self.logger.info(
                            "Exact Math Mode Enabled.  Deploying Uniswap V3 Math Modules to EVM."
                        )
                        # pylint: disable=import-outside-toplevel,no-name-in-module,import-error
                        from pyrevm import AccountInfo  # type: ignore[attr-defined]

                        # pylint: enable=import-outside-toplevel,no-name-in-module,import-error

                        for name, model in exact_math_modules.items():
                            deploy_address, deploy_bin = model.deploy_params()
                            self.evm_state.insert_account_info(
                                deploy_address, AccountInfo(code=deploy_bin)
                            )
                            self.logger.debug(
                                f"Deploying {name} to pyrevm at address {deploy_address}"
                            )

                    self.loaded_math_modules["UniswapV3SwapMath"] = UniswapV3SwapMath(
                        factory=self
                    )

                case _:
                    raise ValueError(f"Unknown pool type: {pool_type}")

            self._initialized_classes.append(pool_type)
            self.logger.info(f"Successfully Initialized {pool_type} Pool Class")

    def initialize_empty_pool(
        self,
        pool_type: Literal["uniswap_v3"],
        initialization_args: Optional[dict] = None,
    ):
        """
        Initializes Empty Pool Instance at 1 for 1 price with no liquidity.  Initial price, liquidity,
        and parameters are set using the initialization dict passed to the pool subclass through the
        initialization_args dictionary.

        :param Literal[uniswap_v3] pool_type:
            Type of pool to intitialize
        :param initialization_args:
            Initialization kwargs for pool class
        :return:
            Pool instance
        """

        self.pool_pre_init(pool_type)

        match pool_type:
            case "uniswap_v3":
                pool_instance = UniswapV3Pool.initialize_empty_pool(
                    factory=self, **initialization_args if initialization_args else {}
                )
            case _:
                raise ValueError(f"Unknown pool type: {pool_type}")

        self.initialized_pools.append(pool_instance)

        return pool_instance

    def initialize_from_chain(
        self,
        pool_type: Literal["uniswap_v3"],
        pool_address: str,
        init_mode: Literal["simulation", "load_liquidity", "chain_translation"],
        at_block: Optional[int] = None,
        initialization_args: Optional[dict] = None,
    ):
        """
        Initializes Pool Instance from contract address, pulling on-chain liquidity, prices, and parameters.

        .. admonition:: Requires Archive Node

            If initializing at current block, 256+ blocks af historical state is reccomended. If initializing
            at historical blocks, an archive node is likely necessary.

        :param Literal[uniswap_v3] pool_type:
            Type of pool to initialize
        :param pool_address:
            Address of pool to initialize
        :param Literal[simulation, load_liquidity, chain_translation] init_mode:
            Initialization mode for loading pool from chain

            # TODO: Document init modes

        :param Optional[int] at_block:
            Block number to pull on-chain state from.  If None, w3.eth.block_number is used.
            block_number='latest' is rarely used in this library due to inaccuracies if the 'latest' block at the
            beginning and end of pool initialization differ.
        :param Optional[dict] initialization_args:
            Initialization kwargs for pool class
        :return:
            Pool instance
        """
        if self.w3 is None:
            raise ValueError("Web3 Instance Required for initialize_from_chain")

        self.pool_pre_init(pool_type)

        if at_block is None:
            at_block = self.w3.eth.block_number

        match pool_type:
            case "uniswap_v3":
                pool_instance = UniswapV3Pool.from_chain(
                    self,
                    to_checksum_address(pool_address),
                    init_mode=init_mode,
                    at_block=at_block,
                    **initialization_args if initialization_args else {},
                )
            case _:
                raise ValueError(f"Unknown pool type: {pool_type}")

        self.initialized_pools.append(pool_instance)

        return pool_instance

    def initialize_pricing_oracle(
        self,
        timestamp_resolution: int = 10_000,
    ) -> PricingOracle:
        """
        Initializes Pricing Oracle Instance

        :param Optional[int] timestamp_resolution:
            Optional Parameter to set the resolution of the oracle.  If None, the oracle will query every 10_000th
            (~ 2 Days) block, and average between blocks to generate timestamps for blocks

        :return:
            Pricing Oracle Instance
        """
        self.oracle = PricingOracle(
            factory=self, timestamp_resolution=timestamp_resolution
        )
        return self.oracle

    def _get_math_module(self, module_name) -> ExactMathModule | TranslatedMathModule:
        return self.loaded_math_modules[module_name]

    def call_evm_contract(
        self,
        to_address: str,
        data: bytes,
        exception_class: Optional[Type[Exception]] = None,
    ) -> str:
        """
        Internal Method used during exact math mode.  Contracts are deployed to a Rust EVM implementation,
        and can be called to generate math results identical to the Solidity implementation.
        Is only available if exact_math=True is passed to the factory constructor, and the pyrevm package is installed.

        :param str to_address: deployment address of the contract
        :param bytes data: call data to pass to EVM
        :param exception_class: Exception to raise if EVM call fails.  Defaults to RuntimeError

        :return: Response bytes formatted as HexString
        """
        try:
            tx_result = self.evm_state.call_raw(
                caller="0x0123456789012345678901234567890123456789",
                to=to_address,
                data=list(data),
            )
        except RuntimeError:
            raise exception_class if exception_class else RuntimeError  # pylint: disable=raise-missing-from
        return tx_result

    def create_db_session(self) -> Session:
        """
        Creates a new sqlalchemy session from the factory's engine URI

        :return: sqlalchemy session

        """
        return sessionmaker(bind=self.sqlalchemy_engine)()

    def get_oracle(self) -> PricingOracle:
        """
        Returns an initialized pricing oracle

        :return: PricingOracle
        """
        if self.oracle is None:
            raise ValueError("Oracle Not Initialized")

        return self.oracle
