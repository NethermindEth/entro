.. _erc20token:

Standard Token Interface
========================
.. note::

    Python ETH AMM provides basic support for ERC20 tokens. This support will expand later to encompass more token
    standards and additional functionality

ERC20 Token Usage
-----------------

Initializing an ERC20Token from an address
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from web3 import Web3
    from python_eth_amm import ERC20Token

    w3 = Web3(Web3.HTTPProvider("http://******"))
    weth_token = ERC20Token.from_chain(w3, "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2")


Reading Token Paramters
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    >>> weth_token.name
    'Wrapped Ether'
    >>> weth_token.symbol
    'WETH'
    >>> weth_token.decimals
    18


ERC20Token API
--------------

.. autoclass:: python_eth_amm.base.token.ERC20Token
   :members:



