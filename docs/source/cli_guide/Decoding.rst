Decoding
========

The entro library provides a robust multi-abi decoding structure called the DecodingDispatcher.

This allows users to load in a dozen different ABIs, and decode functions & events using all of these ABIs.
To perform this, there is a priority heirarchy of ABIs, which provides an order for decoding.

In this example, lets create a decoder, and load in the ERC20 ABI, and the UniswapV2Pool ABI.  The Uniswap V2 ABI is a
superset of the ERC20 ABI, so when we look up the ABI decoder for the transfer() function, we can use
both the ERC20 and UniswapV2Pool ABIs.

To handle this, we will set the ERC20 ABI to priority 100, and the UniswapV2Pool to priority 50.  From here, if we
encounter a transfer() or approve() function, the decoder will use the ERC20 ABI, and if we encounter a mint() or burn()
function, the decoder will use the UniswapV2Pool ABI.

Adding ABIs to Decoder
----------------------

To add an ABI to the decoder, we can use the `entro decode add-abi` CLI endpoint.
Specify the ABI file, the priority of the ABI, and a unique name for the ABI.

.. code-block:: shell

    entro decode add-abi ERC20 abis/erc20.json --priority 100
    entro decode add-abi UniswapV2 abis/uniswap_v2.json --priority 50


The decoder also supports Starknet Cairo ABIs, and the full decoding functionality is avaiable for both
Starknet and EVM Chains.  Cairo and EVM Abis are loaded separately & their priorities do not interfere

.. code-block:: shell

    entro decode add-class EKOBU-Core 0x03e8d67c8817de7a2185d418e88d321c89772a9722b752c6fe097192114621be --priority 50


Inspecting Loaded ABIs
----------------------

.. code-block:: shell

    entro decode list-abis

The list-abis command will show the ABIs loaded into the decoder, and their priority.

.. code-block:: shell

    ╭──────────────────────────────────────╮
    │ -- EVM ABIs --                       │
    ╰──────────────────────────────────────╯
     ABI Name       Priority
     ERC20          100
     UniswapV2Pair  50
    ╭──────────────────────────────────────╮
    │ -- Cairo ABIs --                     │
    ╰──────────────────────────────────────╯
     ABI Name       Priority
     Ekobu-Core     50


For more verbose information on loaded ABIs, functions, and events, use the `list-abi-decoders` command.

.. code-block:: shell

    entro decode list-abi-decoders EVM

The decoder supports both EVM & Cairo ABIs, so you can specify the ABI type as an argument to the command.
In this case, we are using the EVM ABI type.

.. code-block:: shell

                                                              EVM Decoder ABIs
    ┏━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃ Name          ┃ Priority ┃ Functions                                                                  ┃ Events                           ┃
    ┡━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │ ERC20         │ 100      │ 'allowance', 'approve', 'balanceOf', 'decimals', 'decreaseAllowance',      │ 'Approval', 'Transfer',          │
    │               │          │ 'increaseAllowance', 'name', 'symbol', 'totalSupply', 'transfer',          │                                  │
    │               │          │ 'transferFrom',                                                            │                                  │
    ├───────────────┼──────────┼────────────────────────────────────────────────────────────────────────────┼──────────────────────────────────┤
    │ UniswapV2Pair │ 50       │ 'DOMAIN_SEPARATOR', 'MINIMUM_LIQUIDITY', 'PERMIT_TYPEHASH', 'burn',        │ 'Burn', 'Mint', 'Swap', 'Sync',  │
    │               │          │ 'factory', 'getReserves', 'initialize', 'kLast', 'mint', 'nonces',         │                                  │
    │               │          │ 'permit', 'price0CumulativeLast', 'price1CumulativeLast', 'skim', 'swap',  │                                  │
    │               │          │ 'sync', 'token0', 'token1',                                                │                                  │
    └───────────────┴──────────┴────────────────────────────────────────────────────────────────────────────┴──────────────────────────────────┘

This output shows which functions & events are decoded by each ABI.  As described above, the ERC20 functions & events
are decoded by the ERC20 ABI, and the UniswapV2Pair functions & events are decoded by the UniswapV2Pair ABI.

Adding ABI at a higher priority can disrupt which selectors are decoded by which ABI.


Caching ABI JSON
----------------

If a DB_URL is set, ABIs will be stored to the internal.contract_abis table.  Otherwise, they are cached
in the system application data directory in a JSON file.

On windows, this file is located at
~/AppData/Roaming/entro/contract-abis.json

On linux, this file is typically located at
~/.config/entro/contract-abis.json

On MacOS, this file is located at
~/Library/Application Support/entro/contract-abis.json


Deleting ABIs
-------------

To delete an ABI from the decoder, use the `delete-abi` command with the ABI name & the Decoder type.

.. code-block:: shell

    entro decode delete-abi ERC20 EVM
