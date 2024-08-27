Starknet Commands
=================


GET
---

Class ABI
*********

The `entro get starknet class 0x123...` endpoint queries the set JSON_RPC for that specific class hash.
The class ABI is parsed into a human-readable format and displayed to the user.

.. code-block:: shell

    entro get starknet class 0x04f9849485e35f4a1c57d69b297feda94e743151f788202a6d731173babf4aec

The output will list the functions for the class in alphabetical order, followed by the events in alphabetical order.
The function params with their types are displayed, as well as the output types
(starknet function outputs are unnamed).

Events are displayed in the same way, with the event params and their types displayed.  If an event parameter is
surrounded by <>, it is indexed & extracted from the event keys.  All other parameters are non-indexed and are
decoded from the event data

.. code-block:: shell

    ╭─────────────────────────────────────────────────────────────────────────────────────────╮
    │ ABI for Class 0x04f9849485e35f4a1c57d69b297feda94e743151f788202a6d731173babf4aec        │
    ╰─────────────────────────────────────────────────────────────────────────────────────────╯
    ---- Functions ----
      mint(to: ContractAddress) -> (U256)
      burn(to: ContractAddress) -> ((U256, U256))
      swap(amount_0_out: U256, amount_1_out: U256, to: ContractAddress, data: [Felt]) -> ()
      out_given_in(amount_in: U256, first_token_in: Bool) -> (U256)
      in_given_out(amount_out: U256, first_token_in: Bool) -> (U256)
      upgrade(new_class_hash: ClassHash) -> ()
      owner() -> (ContractAddress)
      transfer_ownership(new_owner: ContractAddress) -> ()
      renounce_ownership() -> ()
      total_supply() -> (U256)
      balance_of(account: ContractAddress) -> (U256)
      allowance(owner: ContractAddress, spender: ContractAddress) -> (U256)
      transfer(recipient: ContractAddress, amount: U256) -> (Bool)
      transfer_from(sender: ContractAddress, recipient: ContractAddress, amount: U256) -> (Bool)
      approve(spender: ContractAddress, amount: U256) -> (Bool)
      name() -> (Felt)
      symbol() -> (Felt)
      increaseAllowance(spender: ContractAddress, addedValue: U256) -> (Bool)
      decreaseAllowance(spender: ContractAddress, subtractedValue: U256) -> (Bool)
      skim(to: ContractAddress) -> ()
      sync() -> ()
      token_0() -> (ContractAddress)
      token_1() -> (ContractAddress)
      get_reserves() -> ((U256, U256))
      k_last() -> (U256)
      swap_fee() -> (U16)
    ---- Events ----
      Transfer(<from>: ContractAddress, <to>: ContractAddress, value: U256)
      Approval(<owner>: ContractAddress, <spender>: ContractAddress, value: U256)
      PairMint(sender: ContractAddress, amount_0: U256, amount_1: U256)
      PairBurn(sender: ContractAddress, amount_0: U256, amount_1: U256, to: ContractAddress)
      Swap(sender: ContractAddress, amount_0_in: U256, amount_1_in: U256, amount_0_out: U256, amount_1_out: U256, to: ContractAddress)
      Sync(reserve_0: U256, reserve_1: U256)
      OwnershipTransferred(previous_owner: ContractAddress, new_owner: ContractAddress)
      Upgraded(class_hash: ClassHash)



Contract Implementation
***********************

The `entro get starknet contract 0x123...` endpoint queries the set JSON_RPC for the contract address,
and generates an implementation history over time.
(This is unique to starknet.  For more info, check out the `Starknet Docs <https://docs.starknet.io/architecture-and-concepts/smart-contracts/system-calls-cairo1/#replace_class>`_)

.. code-block:: shell

    entro get starknet contract 0x04f9849485e35f4a1c57d69b297feda94e743151f788202a6d731173babf4aec

The output will list the class_hashes implemented by the contract over time. The block_number that the
class hash was implemented at is displayed to show the upgrades to the contract over time.  If a contract
implements a class with a proxy function, it will call this proxy function to show the proxied address over time.

In the below example for the Starknet ETH Contract, the contract was deployed at block 1407, with class 0x00de...
which was a proxy.  When the contract was deployed, it proxied all calls to 0x00... which was a null placeholder.
At block 1472, the contract was upgraded to class 0x038c...

The proxy was upgraded another 2 times, then at block 541384, the class for Starknet ETH was replaced to class 0x05ff,
which did not implement a proxy, and then the class was further upgraded at 629092 to the
current implementation (as of August 2024)

.. code-block:: shell

    ╭───────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
    │ Implementation History for Contract 0x049d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7        │
    ╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
    {
        "1407": {
            "proxy_class": "0x00d0e183745e9dae3e4e78a8ffedcce0903fc4900beace4e0abf192d4c202da3",
            "1407": "0x0000000000000000000000000000000000000000000000000000000000000000",
            "1472": "0x038c25d465b4c5edf024aefae63dc2f6266dd8ba303763de00da4430b5ee8759",
            "2823": "0x048624e084dc68d82076582219c7ed8cb0910c01746cca3cd72a28ecfe07e42d",
            "541380": "0x053c91253bc9682c04929ca02ed00b3e423f6710d2ee7e0d5ebb06f3ecf368a8"
        },
        "541384": "0x05ffbcfeb50d200a0677c48a129a11245a3fc519d1d98d76882d1c9a1b19c6ed",
        "629092": "0x07f3777c99f3700505ea966676aac4a0d692c2a9f5e667f4c606b51ca1dd3420"
    }

.. admonition::  Runtime Complexity & RPC Calls

    The contract implementation algorithm performs a binary search over the block space.  Ie, it will
    query the starknet_getClassHashAt rpc function at the current block, then the midpoint of the block space,
    then the midpoint of the lower half, etc.  This allows for accurate identification of implementation transitions.

    This process is repeated for each new implementation.  If a contract is a proxy, it performs this same algorithm,
    but performs a starknet_call() with the method 'get_implementation' instead...

    For complex contracts, this requires (impl_count) * log2(latest_block_number) RPC calls, and can
    be expensive.


.. admonition:: Notes on Proxies

    There is no proxy standard, and there are a bunch of different implementations.  A small set of ABI functions
    are recognized as valid proxy functions, (all others are not recognized as proxies &
    the proxy history isnt queried)

    * 'getImplementation'
    * 'get_implementation'
    * 'getImplementationHash'
    * 'get_implementation_hash'
    * 'implementation'

    Each of these functions returns a Felt252, which can represent anything...  DO NOT ASSUME THE RESULTS FROM THIS
    FUNCTION ARE A VALID CONTRACT ADDRESS...



Decoded Transaction
*******************

The `entro get starknet transaction 0x123...` endpoint queries the set JSON_RPC for the transaction trace, and
decodes the transaction into a human-readable format.  This method is useful for debugging transactions, and
can fetch & decode transactions on public & private testnets as long as the RPC is correctly configured, and will
be accurate the second a block is confirmed.

.. code-block:: shell

    entro get starknet transaction 0x014d85119a1c17f0325a2f51f85d020ee3894be1327103c45ccb45ece74ff2ac


This will output a nested tree showing the decoded calls for each of the subtraces.  The contract addresses are
truncated in the base view for better readability, but available in the full-trace view, alongside class hashes and
decoded input & output

.. code-block:: shell

    ╭─────────────────────────────────────────────────────────────────────────────────────────────────╮
    │  Transaction Trace -- 0x014d85119a1c17f0325a2f51f85d020ee3894be1327103c45ccb45ece74ff2ac        │
    ╰─────────────────────────────────────────────────────────────────────────────────────────────────╯
    Execute Trace

    └──  __execute__  --  0x00b8e5a4...59130711
        ├──  approve  --  0x053c9125...ecf368a8
        └──  swap  --  0x01088417...9e944a28
            ├──  balanceOf  --  0x053c9125...ecf368a8
            ├──  transferFrom  --  0x053c9125...ecf368a8
            └──  transfer  --  0x049d3657...9e004dc7
    ╭─────────────────────────────────────────────────────────────────────────────────────────────────╮
    │ Execute Events                                                                                  │
    ╰─────────────────────────────────────────────────────────────────────────────────────────────────╯
       Approval  -- 0x053c9125...ecf368a8
       Approval  -- 0x053c9125...ecf368a8
       Transfer  -- 0x053c9125...ecf368a8
       Transfer  -- 0x049d3657...9e004dc7


The same function can also be used to view detailed debug information on a transaction & events.  To do this,
supply the `--full-trace` flag to the CLI to printout full class hash & contract address info,
as well as the decoded input & output for each trace

.. code-block:: shell

    ╭───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
    │  Transaction Trace -- 0x014d85119a1c17f0325a2f51f85d020ee3894be1327103c45ccb45ece74ff2ac                                                                                          │
    ╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
    Execute Trace
    └──  __execute__  --  0x00b8e5a4f76d3338e9982951debbf79a9872a0498d7c01cfff63d4f859130711
        ╭─────────────────┬─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
        │ Decoded Inputs  │ {"calls": [{"to": "0x053c91253bc9682c04929ca02ed00b3e423f6710d2ee7e0d5ebb06f3ecf368a8", "selector":                                                         │
        │                 │ "0x0219209e083275171774dab1df80982e9df2096516f06319c5c6d71ae0a8480c", "calldata": ["0x010884171baf1914edc28d7afb619b40a4051cfae78a094a55d230f19e944a28",    │
        │                 │ "0xdfd6ed", "0x00"]}, {"to": "0x010884171baf1914edc28d7afb619b40a4051cfae78a094a55d230f19e944a28", "selector":                                              │
        │                 │ "0x015543c3708653cda9d418b4ccd3be11368e40636c10c44b18cfe756b6d88b29", "calldata": ["0x01",                                                                  │
        │                 │ "0x053c91253bc9682c04929ca02ed00b3e423f6710d2ee7e0d5ebb06f3ecf368a8", "0xdfd6ed", "0x00", "0x0ebdfbf616faaa", "0x00"]}]}                                    │
        │ Decoded Outputs │ [["0x01"], ["0x0f0b011a757d2b", "0x00"]]                                                                                                                    │
        │ Class Hash      │ 0x00816dd0297efc55dc1e7559020a3a825e81ef734b558f03c83325d4da7e6253                                                                                          │
        ╰─────────────────┴─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
        ├──  approve  --  0x053c91253bc9682c04929ca02ed00b3e423f6710d2ee7e0d5ebb06f3ecf368a8
        │   ╭─────────────────┬───────────────────────────────────────────────────────────────────────────────────────────────────────╮
        │   │ Decoded Inputs  │ {"spender": "0x010884171baf1914edc28d7afb619b40a4051cfae78a094a55d230f19e944a28", "amount": 14669549} │
        │   │ Decoded Outputs │ ["True"]                                                                                              │
        │   │ Class Hash      │ 0x05ffbcfeb50d200a0677c48a129a11245a3fc519d1d98d76882d1c9a1b19c6ed                                    │
        │   ╰─────────────────┴───────────────────────────────────────────────────────────────────────────────────────────────────────╯
        └──  swap  --  0x010884171baf1914edc28d7afb619b40a4051cfae78a094a55d230f19e944a28
            ╭─────────────────┬─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
            │ Decoded Inputs  │ {"pool_id": "0x01", "token_from_addr": "0x053c91253bc9682c04929ca02ed00b3e423f6710d2ee7e0d5ebb06f3ecf368a8", "amount_from": 14669549, "amount_to_min":  │
            │                 │ 4149539537091242}                                                                                                                                       │
            │ Decoded Outputs │ [4234224017440043]                                                                                                                                      │
            │ Class Hash      │ 0x055ef1b2cb1313b8202f68ef32aaefca4133b21cbce68c4bfee453e595ce646f                                                                                      │
            ╰─────────────────┴─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
            ├──  balanceOf  --  0x053c91253bc9682c04929ca02ed00b3e423f6710d2ee7e0d5ebb06f3ecf368a8
            │   ╭─────────────────┬───────────────────────────────────────────────────────────────────────────────────╮
            │   │ Decoded Inputs  │ {"account": "0x00b8e5a4f76d3338e9982951debbf79a9872a0498d7c01cfff63d4f859130711"} │
            │   │ Decoded Outputs │ [14669549]                                                                        │
            │   │ Class Hash      │ 0x05ffbcfeb50d200a0677c48a129a11245a3fc519d1d98d76882d1c9a1b19c6ed                │
            │   ╰─────────────────┴───────────────────────────────────────────────────────────────────────────────────╯
            ├──  transferFrom  --  0x053c91253bc9682c04929ca02ed00b3e423f6710d2ee7e0d5ebb06f3ecf368a8
            │   ╭─────────────────┬─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
            │   │ Decoded Inputs  │ {"sender": "0x00b8e5a4f76d3338e9982951debbf79a9872a0498d7c01cfff63d4f859130711", "recipient":                                                       │
            │   │                 │ "0x010884171baf1914edc28d7afb619b40a4051cfae78a094a55d230f19e944a28", "amount": 14669549}                                                           │
            │   │ Decoded Outputs │ ["True"]                                                                                                                                            │
            │   │ Class Hash      │ 0x05ffbcfeb50d200a0677c48a129a11245a3fc519d1d98d76882d1c9a1b19c6ed                                                                                  │
            │   ╰─────────────────┴─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
            └──  transfer  --  0x049d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7
                ╭─────────────────┬─────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
                │ Decoded Inputs  │ {"recipient": "0x00b8e5a4f76d3338e9982951debbf79a9872a0498d7c01cfff63d4f859130711", "amount": 4234224017440043} │
                │ Decoded Outputs │ ["True"]                                                                                                        │
                │ Class Hash      │ 0x07f3777c99f3700505ea966676aac4a0d692c2a9f5e667f4c606b51ca1dd3420                                              │
                ╰─────────────────┴─────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
    ╭───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
    │ Execute Events                                                                                                                                                                    │
    ╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
    ╭──────────┬────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
    │ Name     │ Approval                                                                                                                                                               │
    │ Contract │ 0x053c91253bc9682c04929ca02ed00b3e423f6710d2ee7e0d5ebb06f3ecf368a8                                                                                                     │
    │ Decoded  │ {"owner": "0x00b8e5a4f76d3338e9982951debbf79a9872a0498d7c01cfff63d4f859130711", "spender": "0x010884171baf1914edc28d7afb619b40a4051cfae78a094a55d230f19e944a28",       │
    │          │ "value": 14669549}                                                                                                                                                     │
    ╰──────────┴────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
    ╭──────────┬────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
    │ Name     │ Approval                                                                                                                                                               │
    │ Contract │ 0x053c91253bc9682c04929ca02ed00b3e423f6710d2ee7e0d5ebb06f3ecf368a8                                                                                                     │
    │ Decoded  │ {"owner": "0x00b8e5a4f76d3338e9982951debbf79a9872a0498d7c01cfff63d4f859130711", "spender": "0x010884171baf1914edc28d7afb619b40a4051cfae78a094a55d230f19e944a28",       │
    │          │ "value": 0}                                                                                                                                                            │
    ╰──────────┴────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
    ╭──────────┬────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
    │ Name     │ Transfer                                                                                                                                                               │
    │ Contract │ 0x053c91253bc9682c04929ca02ed00b3e423f6710d2ee7e0d5ebb06f3ecf368a8                                                                                                     │
    │ Decoded  │ {"from": "0x00b8e5a4f76d3338e9982951debbf79a9872a0498d7c01cfff63d4f859130711", "to": "0x010884171baf1914edc28d7afb619b40a4051cfae78a094a55d230f19e944a28", "value":    │
    │          │ 14669549}                                                                                                                                                              │
    ╰──────────┴────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
    ╭──────────┬────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
    │ Name     │ Transfer                                                                                                                                                               │
    │ Contract │ 0x049d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7                                                                                                     │
    │ Decoded  │ {"from": "0x010884171baf1914edc28d7afb619b40a4051cfae78a094a55d230f19e944a28", "to": "0x00b8e5a4f76d3338e9982951debbf79a9872a0498d7c01cfff63d4f859130711", "value":    │
    │          │ 4234224017440043}                                                                                                                                                      │
    ╰──────────┴────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯


BACKFILL
--------

Backfill Methods can either write records to a Sqlalchemy DB_URL (Currently only postgres is supported),
or it can write to CSV files, with | as the delimiter.  The CSV files are specified with the `--block-file`,
`--transaction-file`, and `--event-file` flags.

The Data Formats for the Backfills are listed in the :ref:`Starknet Data Reference <starknet-data-formats>` section of the Starknet Docs


Full Blocks
***********

The `entro backfill starknet full-blocks` endpoint performs a backfill between block
ranges for Starknet.  This data includes event data, transaction data, and block data.

This process also supports full ABI Decoding, and can be configured to decode from a list of
ABIs that are loaded into the Decoder

.. code-block:: shell

    entro decode add-class Starknet-ETH 0x03e8d67c8817de7a2185d418e88d321c89772a9722b752c6fe097192114621be --priority 200
    entro decode add-class EKOBU-Core 0x03e8d67c8817de7a2185d418e88d321c89772a9722b752c6fe097192114621be --priority 50

    entro backfill starknet full-blocks --start-block 620000 --end-block 620500 -abi Starknet-ETH -abi EKOBU-Core \
        --json-rpc http://localhost:8545 --block-file starknet-blocks.csv --transaction-file starknet-transactions.csv \
        --event-file starknet-events.csv

Before executing the backfill, entro will prompt the user with the backfill parameters

.. code-block:: shell

                                 Backfill Block Ranges
    ┏━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃ Start Block              ┃ End Block            ┃               Total Blocks ┃
    ┡━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │ 620,000                  │ 620,500              │                        500 │
    └──────────────────────────┴──────────────────────┴────────────────────────────┘
                              Backfill Filters & Metadata
    ┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃ Key                    ┃ Value                                               ┃
    ┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │ json_rpc               │ http://homelab.cicerolabs.xyz:9545                  │
    │ no_interaction         │ False                                               │
    └────────────────────────┴─────────────────────────────────────────────────────┘
                                                                    Cairo Decoder ABIs
    ┏━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃ Name         ┃ Priority ┃ Functions                                                                  ┃ Events                                  ┃
    ┡━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │ Starknet-ETH │ 100      │ 'add_new_implementation', 'allowance', 'approve', 'balanceOf',             │ 'Approval', 'GovernanceAdminAdded',     │
    │              │          │ 'balance_of', 'decimals', 'decreaseAllowance', 'decrease_allowance',       │ 'GovernanceAdminRemoved',               │
    │              │          │ 'get_impl_activation_time', 'get_role_admin', 'get_upgrade_delay',         │ 'ImplementationAdded',                  │
    │              │          │ 'has_role', 'increaseAllowance', 'increase_allowance',                     │ 'ImplementationFinalized',              │
    │              │          │ 'is_governance_admin', 'is_upgrade_governor', 'name', 'permissionedBurn',  │ 'ImplementationRemoved',                │
    │              │          │ 'permissionedMint', 'permissioned_burn', 'permissioned_mint',              │ 'ImplementationReplaced',               │
    │              │          │ 'register_governance_admin', 'register_upgrade_governor',                  │ 'RoleAdminChanged', 'RoleGranted',      │
    │              │          │ 'remove_governance_admin', 'remove_implementation',                        │ 'RoleRevoked', 'Transfer',              │
    │              │          │ 'remove_upgrade_governor', 'renounce', 'replace_to', 'symbol',             │ 'UpgradeGovernorAdded',                 │
    │              │          │ 'totalSupply', 'total_supply', 'transfer', 'transferFrom',                 │ 'UpgradeGovernorRemoved',               │
    │              │          │ 'transfer_from',                                                           │                                         │
    ├──────────────┼──────────┼────────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────┤
    │ EKOBU-Core   │ 0        │ 'accumulate_as_fees', 'collect_fees', 'get_call_points',                   │ 'ClassHashReplaced',                    │
    │              │          │ 'get_locker_state', 'get_owner', 'get_pool_fees_per_liquidity',            │ 'FeesAccumulated', 'LoadedBalance',     │
    │              │          │ 'get_pool_fees_per_liquidity_inside', 'get_pool_liquidity',                │ 'OwnershipTransferred',                 │
    │              │          │ 'get_pool_price', 'get_pool_tick_fees_outside',                            │ 'PoolInitialized',                      │
    │              │          │ 'get_pool_tick_liquidity_delta', 'get_pool_tick_liquidity_net',            │ 'PositionFeesCollected',                │
    │              │          │ 'get_position', 'get_position_with_fees', 'get_primary_interface_id',      │ 'PositionUpdated', 'ProtocolFeesPaid',  │
    │              │          │ 'get_protocol_fees_collected', 'get_saved_balance', 'initialize_pool',     │ 'ProtocolFeesWithdrawn',                │
    │              │          │ 'load', 'lock', 'maybe_initialize_pool', 'next_initialized_tick', 'pay',   │ 'SavedBalance', 'Swapped',              │
    │              │          │ 'prev_initialized_tick', 'replace_class_hash', 'save', 'set_call_points',  │                                         │
    │              │          │ 'swap', 'transfer_ownership', 'update_position', 'withdraw',               │                                         │
    │              │          │ 'withdraw_protocol_fees',                                                  │                                         │
    └──────────────┴──────────┴────────────────────────────────────────────────────────────────────────────┴─────────────────────────────────────────┘
    Querying Transactions, Logs, and Receipts for Block Range
    ------------------------------------------------------------------------------------------------------------------------------------------------
    Execute Backfill?   [y/n]:


This will show the block range to query, the number of blocks to query, and the ABIs used to decode this data.
If everything looks correct, the user can confirm the backfill, and entro will begin querying the RPC for the data.

During the Backfill, the CLI will display a progress bar showing the percentage of the backfill completed, the time
elapsed, and the time remaining.  The CLI will also display the current block being searched, and the total number of
blocks searched.

.. code-block:: shell

    Backfill StarkNet Full Blocks ⠴ ━━━━╸━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  12% 0:00:22 0:02:19 Searched: 60/500 Searching Block: 620060


Events
******

The entro tool can also backfill specific events for a contract address.  This is a particularly useful tool for
generating analytics datasets from just an RPC node.  For this example, we will backfill the 'Transfer' event for
the Starknet ETH contract

.. code-block:: shell

    entro backfill starknet events --contract-address 0x049d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7 --event-name Transfer \
        --from-block 620000 --to-block 640000 --json-rpc http://localhost:8545 --event-file starknet-transfer-events.csv \
        --decode-abis Starknet-ETH

This will backfill the 'Transfer' event for the Starknet ETH contract between blocks 620000 and 640000, and write the
output to the file 'starknet-transfer-events.csv'.  The Starknet-ETH ABI will be used to decode the event data.

.. code-block:: shell

                             Backfill Block Ranges
    ┏━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃ Start Block              ┃ End Block            ┃               Total Blocks ┃
    ┡━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │ 620,000                  │ 640,000              │                     20,000 │
    └──────────────────────────┴──────────────────────┴────────────────────────────┘
                                      Backfill Filters & Metadata
    ┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃ Key              ┃ Value                                                                    ┃
    ┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │ contract_address │ 0x049d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7       │
    │ event_names      │ ['Transfer']                                                             │
    │ abi_name         │ Starknet-ETH                                                             │
    │ json_rpc         │ http://homelab.cicerolabs.xyz:9545                                       │
    │ no_interaction   │ False                                                                    │
    │ topics           │ [['0x0099cd8bde557814842a3121e8ddfd433a539b8c9f14bf31ebf108d12e6196e9']] │
    └──────────────────┴──────────────────────────────────────────────────────────────────────────┘
                                                           Cairo Decoder ABIs
    ┏━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃ Name         ┃ Priority ┃ Events                                                                                             ┃
    ┡━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │ Starknet-ETH │ 100      │ 'Approval', 'GovernanceAdminAdded', 'GovernanceAdminRemoved', 'ImplementationAdded',               │
    │              │          │ 'ImplementationFinalized', 'ImplementationRemoved', 'ImplementationReplaced', 'RoleAdminChanged',  │
    │              │          │ 'RoleGranted', 'RoleRevoked', 'Transfer', 'UpgradeGovernorAdded', 'UpgradeGovernorRemoved',        │
    └──────────────┴──────────┴────────────────────────────────────────────────────────────────────────────────────────────────────┘
    Querying Events for Contract: 0x049d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7
    Starknet-ETH ABI Decoding Events:
            'Transfer',
    ------------------------------------------------------------------------------------------------------------------------------------------------
    Execute Backfill?   [y/n]:

