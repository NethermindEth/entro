.. _installation:

Installation
============

.. note::
    As soon as the library is stable, builds will be published to PyPi.  Until then, the development installation
    instructions below can be used.

Requirements
------------
This library extensively uses RPC calls to Ethereum nodes, and running your own node is highly recommended.  There are
also many stateful features that require access to an archive node to be used, such as the ability to get historical
liquidity and position data from Uniswap Pools, or get historical ERC20 token balances for an address.

Erigon Archive nodes require the least storage space, and can be run on a machine with 2TB of SSD storage and 16+ GB
of RAM.  Nethermind Nodes can also be configured to run in a hybrid-archive mode, storing the full states for the past
6 months of blockchain history, and storing only the logs and transactions for older history.

**Features requiring access to archive node:**
    * Querying Uniswap V3 Pool at a historical block



Development Installation
------------------------

For implementation accuracy, this library uses a standalone EVM instance to simulate on-chain behavior.
Pyrevm is the most efficient standalone EVM, and is available on all platforms.  This provides significant performance
improvements over ganache, or any other EVM implementations.

The evm instance is used during testing & development, and is not required for normal usage of the library.  To
enable this functionality, pass the option exact_math=True to the PoolFactory object.

.. code-block:: console

    $ git clone https://github.com/nethermindETH/python-eth-amm.git
    $ cd python-eth-amm
    $ git clone https://github.com/elicbarbieri/pyrevm.git  # temporary until official pyrevm supports result decoding
    $ poetry env use python3.10
    $ poetry install --all-extras
    $ poetry run pytest
    $ maturin develop --release pyrevm/


Development Guide
-----------------


Installing & Manually Running Pre-Commit

Linting & Pre-commits
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: console

    $ poetry run pre-commit install
    $ poetry run pre-commit run --all-files

Test Environment
^^^^^^^^^^^^^^^^

.. code-block::
    :caption: tests/.env

    SQLALCHEMY_DB_URI='postgresql://user:pass@host:5432/db_name'
    ARCHIVE_NODE_RPC_URL='http://node_ip:8545'

Running Tests
^^^^^^^^^^^^^

.. code-block:: console

    $ poetry run pytest tests/

    # Run only Pricing Oracle Tests
    $ poetry run pytest tests/oracle/

