Extracting Block-by-Block Price Data
====================================

Setting Up Oracle
-----------------

To set up a pricing oracle, a Full Node is required to extract historical swap events.  When an oracle is initialized,
it generates a list of all Uniswap V3 pools to extract prices from.  It will also query the timestamp for every
10,000th block (`configurable through timestamp_resolution param`) to allow approximate block-to-date conversion.

.. code-block:: python

    import logging
    from python_eth_amm import Factory
    from eth_utils import to_checksum_address

    project_logger = logging.getLogger("my_project")
    project_logger.setLevel(logging.INFO)

    factory = Factory(
        sqlalchemy_db_uri="postgresql://postgres:postgres@localhost:5432/postgres",
        w3="https://infura.io/v3/...",
        logger=project_logger,
    )

    oracle_instance = factory.initialize_oracle()

    .. note::
        Unlike the Pool Simulations, the Oracle can be initialized from a standard full node (e.g. Infura) instead of
        a full archive node.  The RPC call requirements are also significantly reduced, which makes this a much more
        lightweight process.



Extracting Historical Prices
----------------------------

.. code-block:: python

    WETH_ADDRESS = to_checksum_address("0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2")
    current_block = oracle_instance.w3.eth.block_number

    # Backfill ~1 month of ETH prices.
    oracle_instance.backfill_prices(token_id=WETH_ADDRESS, start=current_block - 225_000)

.. code-block::

    >>> Backfilling PoolCreated Events: 100%|██████████| 1/1 [00:00<00:00,  21.2s/it]
    >>> Backfilling Swap Events: 100%|██████████| 225/225 [01:14<00:00,  3.03it/s]



Updating Backfilled prices
--------------------------

Once prices are backfilled up to the current block, it is easy to create a cronjob or DAG to keep all price feeds up
to date.  The `update_prices` method will query the latest block and update all prices for the last 10,000 blocks.

If the price backfill for a token is more than 10k blocks behind the current chain head, the `update_prices` method
will skip these tokens and log a warning to avoid stalling the update task backfilling years of history.  First run
the `backfill_prices` method to catch up to the current block, then run `update_prices` to keep prices up to date.

.. code-block:: python

    oracle_instance.update_prices()

.. code-block::

    >>> Backfilling Swap Events: 100%|██████████| 3/3 [00:01<00:00,  4.23it/s]


