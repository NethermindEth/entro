Ethereum Commands
=================


BACKFILL
--------

The Entro CLI also supports Ethereum Event backfill operations, making it easy to download
and ABI Decode Ethereum events from a specific contract. As long as the contract ABI is known,
the CLI can decode the events and save them to a file or database.


Events
******

.. code-block:: shell

    entro decode add-abi ERC20 <path to abi JSON> --priority 200

    entro backfill ethereum events --from-block 19000000 --to-block 19000500 --contract-address 0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2 --decode-abis ERC20 --event-name Transfer --event-file weth_transfers.json --json-rpc http://localhost:8545


First add the ERC20 ABI to the decoder, then launch a backfill over a 500 block range to capture all Transfer events from the WETH contract. The events will be decoded using the ERC20 ABI and saved
to the file weth_transfers.json

.. code-block:: shell

                                 Backfill Block Ranges
    ┏━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃ Start Block              ┃ End Block              ┃             Total Blocks ┃
    ┡━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │ 10,000,000               │ 10,000,500             │                      500 │
    └──────────────────────────┴────────────────────────┴──────────────────────────┘
                                     Backfill Filters & Metadata
    ┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃ Key              ┃ Value                                                                  ┃
    ┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │ contract_address │ 0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2                             │
    │ event_names      │ ['Transfer']                                                           │
    │ abi_name         │ ERC20                                                                  │
    │ json_rpc         │ http://localhost:8545                                                  │
    │ source           │ json_rpc                                                               │
    │ topics           │ ['0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'] │
    └──────────────────┴────────────────────────────────────────────────────────────────────────┘
                                    EVM Decoder ABIs
    ┏━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃ Name        ┃ Priority         ┃ Events                                      ┃
    ┡━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │ ERC20       │ 0                │ 'Approval', 'Transfer',                     │
    └─────────────┴──────────────────┴─────────────────────────────────────────────┘
    ------------------------------------------------------------------------------------------------------------------------------------------------
    Execute Backfill?   [y/n]:


The output of the event backfill will include decoded events, and will printout the progress of the backfill as it searches through the block range.

.. code-block:: shell

    Backfill ERC20 Events   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00 0:00:00 Searched: 500/500 Searching Block: 10000500
    [Log Date & Time  ] INFO     ---- Backfill Complete ------
                        INFO     Saving Backfill Progress to Database
                        INFO     Exported 563 Events in 0.0 minutes 11.2 seconds

