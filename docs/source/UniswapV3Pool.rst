UniswapV3Pool
=============

Uniswap V3 Usage
----------------

.. warning::

    TWAP Oracle support is currently experimental, and not suggested for use.  Additionally, fee switch behavior is
    not yet tested, and any protocol_fees may not be implemented correctly.

Creating Uniswap V3 Pools
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from python_eth_amm import PoolFactory

    factory = PoolFactory(w3='https://', sqlalchemy_url='postgresql:db_uri')

    # Create an empty pool with no liquidity & 1:1 price ratio, and 0.3% fee
    low_fee = factory.initialize_empty_pool("uniswap_v3")

    # Create a pool with liquidity & 1:1 price ratio, and 1% fee
    high_fee = factory.initialize_empty_pool("uniswap_v3", initialization_args={"fee":10_000, "tick_spacing":200})

Initializing Pools From Chain
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.. admonition:: Pool Initialization Sequence
    Pool initialization from chain is fairly taxing, requiring the following steps:

    1. Fetching the pool's immutable parameters & state (1-3 seconds and ~20 RPC Calls)
    2. Fetching the Initialized Ticks:
        a. Search Tick Bitmap (~120 queries on pool with 60 tick spacing.  ~700 on pool with 10 tick spacing5).

.. code-block:: python

    # Load the current USDC/WETH .3% pool from mainnet
    usdc_weth = factory.initialize_from_chain(
        "uniswap_v3",
        pool_address="0x8ad599c3a0ff1de082011efddc58f1908eb6e6d8",
    )

    # Load historical USDC/WETH .3% pool from mainnet
    usdc_weth = factory.initialize_from_chain(
        "uniswap_v3",
        pool_address="0x8ad599c3a0ff1de082011efddc58f1908eb6e6d8",
        at_block=14_000_000,
    )

.. warning::

    When using initialize_from_chain with a non-archival node, the chain state is typically only stored for the last 50
    blocks.  If a pool is initialized without a block identifier, the current block will be fetched, and the pool
    will be initialized at that block.  On a slow RPC and a busy pool, it may take upwards of 20 minutes to initialize
    a pool, and the state may be discarded, leaving the pool in an uninitialized state.


API Documentation
-----------------

.. autoclass:: python_eth_amm.uniswap_v3.UniswapV3Pool
    :members:
    :exclude-members: from_chain, initialize_empty_pool, __init__


Uniswap V3 Types
----------------

.. autopydantic_model:: python_eth_amm.uniswap_v3.types.PoolImmutables
    :members:

.. autopydantic_model:: python_eth_amm.uniswap_v3.types.PoolState
    :members:
    :exclude-members: uninitialized

.. autopydantic_model:: python_eth_amm.uniswap_v3.types.Slot0
    :members:
    :exclude-members: uninitialized

.. autopydantic_model:: python_eth_amm.uniswap_v3.types.Tick
    :members:
    :exclude-members: uninitialized

.. autopydantic_model:: python_eth_amm.uniswap_v3.types.OracleObservation
    :members:
    :exclude-members: uninitialized

.. autopydantic_model:: python_eth_amm.uniswap_v3.types.PositionInfo
    :members:
    :exclude-members: uninitialized
