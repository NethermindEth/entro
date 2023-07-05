Extracting Block-by-Block Price Data
====================================

Setting Up Oracle
-----------------

.. code-block:: python

    from python_eth_amm import Factory

    factory = Factory(
        sqlalchemy_db_uri="postgresql://postgres:postgres@localhost:5432/postgres",
        w3="https://infura.io/v3/...",
    )

    oracle_instance = factory.initialize_oracle()


    .. note::
        Unlike the Pool Simulations, the Oracle can be initialized from a standard full node (e.g. Infura) instead of
        a full archive node.  The RPC call requirements are also significantly reduced, which makes this a much more
        lightweight process.



