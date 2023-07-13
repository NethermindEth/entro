.. _quickstart:

Quickstart
==========

Setup
-----

1. Install the package:
    :ref:`Install <installation>` the library

2. Initialize Pool Factory:

.. code-block:: python

    from python_eth_amm import PoolFactory
    pool_factory = PoolFactory(
        w3=Web3(Web3.HTTPProvider("http://localhost:8545"),
        sqlalchemy_url="sqlite:///test.db",
    )


Uniswap V3
----------

.. code-block:: python

    v3_pool = pool_factory.initialize_empty_pool("uniswap_v3")
    v3_pool.mint(
        recipient="0x1234512345123451234512345123451234512345",
        tick_lower=-60000,
        tick_upper=60000,
        amount=100000
    )

Executing Swap on Test Pool
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    swap_id = v3_pool.swap(
        zero_for_one=True,
        amount_specified=1000,
        sqrt_price_limit=,
        log_swap=True,
    )

    # Fetch swap event from the database
    swap_event = v3_pool.get_swap_event(swap_id)



Burning Liquidity & Collecting Swap Fees
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    token_0, token_1 = v3_pool.burn(
        owner="0x1234512345123451234512345123451234512345",
        tick_lower=-60000,
        tick_upper=60000,
        amount=100000,
    )

    >>> token_0
    1000

    >>> token_1
    1000


Initializing Pool From on-chain Contract
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    usdc_weth_pool = pool_factory.initialize_from_chain(
        "uniswap_v3",
        "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640"
        # Older blocks are faster to initialize since there is usually less liquidity deployed
        at_block = 14_000_000,
    )

Reading Pool Parameters

.. code-block:: python

    >>> usdc_weth_pool.immutables.token_0
    ERC20Token(name='USD Coin', symbol='USDC', decimals=6, address='0xA0b86991c6218b3....

    >>> usdc_weth_pool.immutables.token_1
    ERC20Token(name='Wrapped Ether', symbol='WETH', decimals=18, address='0xC02aaA39b223FE8D...

    >>> usdc_weth_pool.state.balance_0  # Token 0 Held by Pool
    42551690315144

    >>> usdc_weth_pool.state.balance_1  # Token 1 Held by Pool
    44536306936710426696786

    >>> usdc_weth_pool.state.liquidity  # Currently Active Liquidity
    48717626097494941106

    >>> usdc_weth_pool.slot0.tick  # Current Tick of the pool
    195455

    >>> usdc_weth_pool.get_price_at_tick(195455)
    '0.000307665'  # That looks like the USDC price in WETH

    >>> usdc_weth_pool.get_price_at_tick(195455, reverse_tokens=True)
    '3250.29'  # There is the price we are looking for

    >>> usdc_weth_pool.get_price_at_tick(195455, reverse_tokens=True, string_description=True)
    'WETH: 3250.29 USDC'  # More human readable


Analyzing Liquidity
^^^^^^^^^^^^^^^^^^^
.. code-block:: python

    from matplotlib import pyplot as plt

    >>> len(usdc_weth_pool.ticks)
    798

    >>> usdc_weth_pool.ticks[186200].liquidity_net
    842438616907770

    # To generate the liquidity distribution of the pool:
    >>> raw_dataframe = usdc_weth_pool.compute_liquidity_at_price(reverse_tokens=True, compress=False)

    # The compressed dataframe is compressed if the liquidity changes less than 10%
    >>> compressed_dataframe = usdc_weth_pool.compute_liquidity_at_price(
            reverse_tokens=True,  # Switches token Order to represent price in USDC
            compress=True
        )

    # Plot the dataframe as a bar chart
    >>> compressed_dataframe.plot.bar(x="price", y="active_liquidity", width=1, figsize=(15, 7)))
    >>> plt.show()

.. image:: _static/liquidity-bar-chart.png



Analyzing Liquidity Positions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.. code-block:: python

    >>> len(usdc_weth_pool.positions)
    9388

    # Created list of all positions ordered by liquidity
    >>> sorted_positions = sorted(execution_pool.positions.items(), key=lambda p: p[1].liquidity, reverse=True)

    >>> sorted_positions[0]
    (('0xC36442b4a4522E871399CD717aBDD847Ab11FE88', 193150, 193160), PositionInfo(liquidity=51169817151707577348, ...

    >>> for key, data in sorted_positions[:20]:
    >>>    # Invert lower & upper price since we are reversing token order
    >>>    lower_price = usdc_weth_pool.get_price_at_tick(key[2], reverse_tokens=True)
    >>>    upper_price = usdc_weth_pool.get_price_at_tick(key[1], reverse_tokens=True)
    >>>    print(f"${lower_price:,.2f} -- ${upper_price:,.2f}:   {data.liquidity}")

    $4,088.72 -- $4,092.81:   51169817151707577348
    $3,232.46 -- $3,439.20:   41216075085584681672
    $2,586.37 -- $2,588.96:   2229824879481991308
    $3,001.90 -- $3,800.89:   1592927280599964178
    $3,219.56 -- $3,371.11:   1476666465406343250
    $4,183.84 -- $4,209.02:   1403630509387477744
    $4,851.19 -- $4,899.94:   1396564059748048295
    $3,601.09 -- $3,622.77:   1386665198155116829
    $3,361.01 -- $3,364.37:   932757285461212862
    $68,991,935.85 -- $69,060,958.84:   830863045158786350
    $3,242.17 -- $3,245.41:   741582070492356794
    $1,800.87 -- $5,197.72:   463849567934926093
    $3,778.15 -- $4,183.84:   313890945617665242
    $4,315.57 -- $17,996.14:   310527552650769165
    $1,499.72 -- $6,197.90:   306118131189390769
    $0.00 -- $0.00:   297698757815726047
    $3,823.76 -- $3,831.42:   292261645555047518
    $3,901.00 -- $4,230.12:   261232565060386965
    $2,898.66 -- $3,601.09:   253551489707673563
    $2,535.16 -- $4,774.19:   248416175392960717


    # Get the current price of the pool
    >>> usdc_weth_pool.get_price_at_tick(usdc_weth_pool.slot0.tick, reverse_tokens=True)
    3250.2861765942507


