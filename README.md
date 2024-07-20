## Python package for Interacting with Blockchains

## Features:
* Backfill & Decode blockchain Data to CSV (ethereum-etl w/ ABI decoding)
* Starknet Data Backfilling
* Utility functions for interacting with Starknet
* Simulate Uniswap V3 Behavior


## Installation
```bash
# Using pip install
pip install git+https://github.com/NethermindEth/entro

# Adding as poetry dependency
poetry add git+https://github.com/NethermindEth/entro
```


## Basic CLI Use
Entro uses the python rich package extensively for styling and formatting console output.  Most modern consoles are
supported, but if the output from commands is not formatted correctly or characters are missing, check out
the [Rich Documentation](https://rich.readthedocs.io/en/stable/introduction.html)

```bash
# Configure RPC Node for CLI
export JSON_RPC=https://free-rpc.nethermind.io/mainnet-juno/

entro get starknet contract 0x049d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7

# Outputs the Contract Implementation History for a Contract Address
╭───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ Implementation History for Contract 0x049d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7                                                                            │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
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


# inspect a starknet ABI & get the functions & events defined inside a Starknet Class 
# Gets Starknet ABI JSON & Parses into function & event signatures

entro get starknet class 0x07f3777c99f3700505ea966676aac4a0d692c2a9f5e667f4c606b51ca1dd3420

╭───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ ABI for Class 0x07f3777c99f3700505ea966676aac4a0d692c2a9f5e667f4c606b51ca1dd3420                                                                                                  │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
---- Functions ----
  increase_allowance(spender: ContractAddress, added_value: U256) -> (Bool)
  decrease_allowance(spender: ContractAddress, subtracted_value: U256) -> (Bool)
  increaseAllowance(spender: ContractAddress, addedValue: U256) -> (Bool)
  decreaseAllowance(spender: ContractAddress, subtractedValue: U256) -> (Bool)
  permissioned_mint(account: ContractAddress, amount: U256) -> ()
  permissioned_burn(account: ContractAddress, amount: U256) -> ()
  permissionedMint(account: ContractAddress, amount: U256) -> ()
  permissionedBurn(account: ContractAddress, amount: U256) -> ()
  get_upgrade_delay() -> (U64)
  get_impl_activation_time(implementation_data: {impl_hash: ClassHash, eic_data: Option[{eic_hash: ClassHash, eic_init_data: [Felt]}], final: Bool}) -> (U64)
  add_new_implementation(implementation_data: {impl_hash: ClassHash, eic_data: Option[{eic_hash: ClassHash, eic_init_data: [Felt]}], final: Bool}) -> ()
  remove_implementation(implementation_data: {impl_hash: ClassHash, eic_data: Option[{eic_hash: ClassHash, eic_init_data: [Felt]}], final: Bool}) -> ()
  replace_to(implementation_data: {impl_hash: ClassHash, eic_data: Option[{eic_hash: ClassHash, eic_init_data: [Felt]}], final: Bool}) -> ()
  has_role(role: Felt, account: ContractAddress) -> (Bool)
  get_role_admin(role: Felt) -> (Felt)
  is_governance_admin(account: ContractAddress) -> (Bool)
  is_upgrade_governor(account: ContractAddress) -> (Bool)
  register_governance_admin(account: ContractAddress) -> ()
  remove_governance_admin(account: ContractAddress) -> ()
  register_upgrade_governor(account: ContractAddress) -> ()
  remove_upgrade_governor(account: ContractAddress) -> ()
  renounce(role: Felt) -> ()
  name() -> (Felt)
  symbol() -> (Felt)
  decimals() -> (U8)
  total_supply() -> (U256)
  balance_of(account: ContractAddress) -> (U256)
  allowance(owner: ContractAddress, spender: ContractAddress) -> (U256)
  transfer(recipient: ContractAddress, amount: U256) -> (Bool)
  transfer_from(sender: ContractAddress, recipient: ContractAddress, amount: U256) -> (Bool)
  approve(spender: ContractAddress, amount: U256) -> (Bool)
  totalSupply() -> (U256)
  balanceOf(account: ContractAddress) -> (U256)
  transferFrom(sender: ContractAddress, recipient: ContractAddress, amount: U256) -> (Bool)
---- Events ----
  Transfer(from: ContractAddress, to: ContractAddress, value: U256)
  Approval(owner: ContractAddress, spender: ContractAddress, value: U256)
  ImplementationAdded(implementation_data: {impl_hash: ClassHash, eic_data: Option[{eic_hash: ClassHash, eic_init_data: [Felt]}], final: Bool})
  ImplementationRemoved(implementation_data: {impl_hash: ClassHash, eic_data: Option[{eic_hash: ClassHash, eic_init_data: [Felt]}], final: Bool})
  ImplementationReplaced(implementation_data: {impl_hash: ClassHash, eic_data: Option[{eic_hash: ClassHash, eic_init_data: [Felt]}], final: Bool})
  ImplementationFinalized(impl_hash: ClassHash)
  RoleGranted(role: Felt, account: ContractAddress, sender: ContractAddress)
  RoleRevoked(role: Felt, account: ContractAddress, sender: ContractAddress)
  RoleAdminChanged(role: Felt, previous_admin_role: Felt, new_admin_role: Felt)
  GovernanceAdminAdded(added_account: ContractAddress, added_by: ContractAddress)
  GovernanceAdminRemoved(removed_account: ContractAddress, removed_by: ContractAddress)
  UpgradeGovernorAdded(added_account: ContractAddress, added_by: ContractAddress)
  UpgradeGovernorRemoved(removed_account: ContractAddress, removed_by: ContractAddress)
```

## Decode Starknet Transactions
The get transaction command fetches the transaction trace, and searches through all of the class hashes present 
in the trace.  From here, it decoded all sub-calls of the trace.  The output shows the contract address
and the called function.  To list the full decoded trace & events, add cli option --full-trace.
To include the raw calldata, result, and event data/keys, pass the --raw flag
```bash
entro get starknet transaction 0x01eaebf1a9ff736c78d07b4948ad446ea179351d39b4ddcd9cc68a027fc23683

╭───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│  Transaction Trace -- 0x01eaebf1a9ff736c78d07b4948ad446ea179351d39b4ddcd9cc68a027fc23683                                                                                          │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
Execute Trace
└──  __execute__  --  0x01fc0e4b...1641f198
    ├──  transfer  --  0x049d3657...9e004dc7
    ├──  mint_and_deposit  --  0x02e0af29...22184067
    │   ├──  mint  --  0x07b696af...45318b30
    │   ├──  is_account_authorized  --  0x07b696af...45318b30
    │   ├──  get_pool_price  --  0x00000005...e0325b4b
    │   ├──  balanceOf  --  0x049d3657...9e004dc7
    │   ├──  balanceOf  --  0x053c9125...ecf368a8
    │   └──  lock  --  0x00000005...e0325b4b
    │       └──  locked  --  0x02e0af29...22184067
    │           ├──  update_position  --  0x00000005...e0325b4b
    │           ├──  transfer  --  0x049d3657...9e004dc7
    │           └──  deposit  --  0x00000005...e0325b4b
    │               └──  balanceOf  --  0x049d3657...9e004dc7
    └──  clear  --  0x02e0af29...22184067
        ├──  balanceOf  --  0x049d3657...9e004dc7
        └──  transfer  --  0x049d3657...9e004dc7
╭───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ Execute Events                                                                                                                                                                    │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
   transaction_executed  -- 0x01fc0e4b...1641f198
   Transfer  -- 0x049d3657...9e004dc7
   PositionMinted  -- 0x02e0af29...22184067
   Deposit  -- 0x02e0af29...22184067
   Transfer  -- 0x07b696af...45318b30
   PositionUpdated  -- 0x00000005...e0325b4b
   Transfer  -- 0x049d3657...9e004dc7
   Transfer  -- 0x049d3657...9e004dc7


# For full decoded data & events
entro get starknet transaction 0x44c8d0d48bbdfd1f062ba47337edf501a1b3beb65d8193d89102e0ab708d819 --full-trace

╭───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│  Transaction Trace -- 0x044c8d0d48bbdfd1f062ba47337edf501a1b3beb65d8193d89102e0ab708d819                                                                                          │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
Execute Trace
└──  __execute__  --  0x03b1ac62aa5d4f596a0c6058f4a57716072e53da44ce67999f69e9b6c321c5e6
    ╭─────────────────┬─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
    │ Decoded Inputs  │ {"calls": [{"to": "0x049d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7", "selector":                                                         │
    │                 │ "0x83afd3f4caedc6eebf44246fe54e38c95e3179a5ec9ea81740eca5b482d12e", "calldata": ["0x019252b1deef483477c4d30cfcc3e5ed9c82fafea44669c182a45a01b4fdb97a",      │
    │                 │ "0x71afd498d00000", "0x00"]}, {"to": "0x022993789c33e54e0d296fc266a9c9a2e9dcabe2e48941f5fa1bd5692ac4a8c4", "selector":                                      │
    │                 │ "0x54cd8cfffad75abfde6525af316085ef4b5d27975ed55042d341c61d19c7a4", "calldata": ["0x409d72"]}]}                                                             │
    │ Decoded Outputs │ [["0x01"], []]                                                                                                                                              │
    │ Class Hash      │ 0x01a736d6ed154502257f02b1ccdf4d9d1089f80811cd6acad48e6b6a9d1f2003                                                                                          │
    ╰─────────────────┴─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
    ├──  transfer  --  0x049d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7
    │   ╭─────────────────┬──────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
    │   │ Decoded Inputs  │ {"recipient": "0x019252b1deef483477c4d30cfcc3e5ed9c82fafea44669c182a45a01b4fdb97a", "amount": 32000000000000000} │
    │   │ Decoded Outputs │                                                                                                                  │
    │   │ Class Hash      │ 0x05ffbcfeb50d200a0677c48a129a11245a3fc519d1d98d76882d1c9a1b19c6ed                                               │
    │   ╰─────────────────┴──────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
    └──  watch  --  0x022993789c33e54e0d296fc266a9c9a2e9dcabe2e48941f5fa1bd5692ac4a8c4
        ╭─────────────────┬────────────────────────────────────────────────────────────────────╮
        │ Decoded Inputs  │ {"_Id": "0x409d72"}                                                │
        │ Decoded Outputs │ []                                                                 │
        │ Class Hash      │ 0x0228e8e5f1a078a7f43763d3d19be58689fcdfba4589629bf65180139db7ea3d │
        ╰─────────────────┴────────────────────────────────────────────────────────────────────╯
╭───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ Execute Events                                                                                                                                                                    │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭──────────┬────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ Name     │ TransactionExecuted                                                                                        │
│ Contract │ 0x03b1ac62aa5d4f596a0c6058f4a57716072e53da44ce67999f69e9b6c321c5e6                                         │
│ Decoded  │ {"hash": "0x044c8d0d48bbdfd1f062ba47337edf501a1b3beb65d8193d89102e0ab708d819", "response": [["0x01"], []]} │
╰──────────┴────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭──────────┬────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ Name     │ Transfer                                                                                                                                                               │
│ Contract │ 0x049d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7                                                                                                     │
│ Decoded  │ {"from": "0x03b1ac62aa5d4f596a0c6058f4a57716072e53da44ce67999f69e9b6c321c5e6", "to": "0x019252b1deef483477c4d30cfcc3e5ed9c82fafea44669c182a45a01b4fdb97a", "value":    │
│          │ 32000000000000000}                                                                                                                                                     │
╰──────────┴────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭──────────┬────────────────────────────────────────────────────────────────────╮
│ Name     │ watch_ls_id                                                        │
│ Contract │ 0x022993789c33e54e0d296fc266a9c9a2e9dcabe2e48941f5fa1bd5692ac4a8c4 │
│ Decoded  │ {"id": "0x409d72"}                                                 │
╰──────────┴────────────────────────────────────────────────────────────────────╯

```

## Backfill CLI
```bash
export JSON_RPC=https://free-rpc.nethermind.io/mainnet-juno/
# Full blocks downloads blocks, transactions, and events
entro backfill starknet full-blocks --from-block 600000 --to-block 600500 --block-file=blocks.csv --transaction-file=transactions.csv --event-file=events.csv

                             Backfill Block Ranges
┏━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Start Block              ┃ End Block            ┃               Total Blocks ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 600,000                  │ 600,500              │                        500 │
└──────────────────────────┴──────────────────────┴────────────────────────────┘
                          Backfill Filters & Metadata                           
┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Key             ┃ Value                                                      ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ json_rpc        │ https://free-rpc.nethermind.io/mainnet-juno/                         │
└─────────────────┴────────────────────────────────────────────────────────────┘
Querying Transactions, Logs, and Receipts for Block Range
------------------------------------------------------------------------------------------------------------------------------------------------
Execute Backfill?   [y/n]:

# Once a backfill is confirmed, the CLI will begin downloading the data from the RPC node
# Progress Bar will display backfill progress

Backfill StarkNet Full Blocks ⠧ ━━╺━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   6% 0:00:17 0:05:26 Searched: 30/500 Searching Block: 600030
```

## ABI Decoding
Entro supports ABI Decoding for most datatypes.  Abis are loaded by event/function signature.

ABI-Priority is used to determine which ABI definition is used to decode a certain datatype.

An AMM Pool and ERC20 token will both implement a transfer function.  By setting the priority of the ERC20 ABI to 5, and the AMM ABI to 4, any function or event with the Transfer signature/event-key will be decoded by the ERC20 ABI, and ignored by the AMM ABI.


```bash
# EVM Abis are added using a path to a JSON file
entro decode add-abi ERC20 /path/to/ERC20.json --priority = 100 # Set Standard ABIs with the highest priorities

# Starknet Abis are added using a Class Hash
entro decode add-class Starknet-ETH 0x07f3777c99f3700505ea966676aac4a0d692c2a9f5e667f4c606b51ca1dd3420 --priority=100
entro decode add-class AVNU-Exchange 0x07b33a07ec099c227130ddffc9d74ad813fbcb8e0ff1c0f3ce097958e3dfc70b --priority=40

# To view the currently known ABIs & the functions they decode, list-abi-decoders
entro decode list-abi-decoders

                                                    EVM Decoder ABIs                                                    
┏━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Name  ┃ Priority ┃ Functions                                                              ┃ Events                   ┃
┡━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ ERC20 │ 100      │ 'allowance', 'approve', 'balanceOf', 'decimals', 'decreaseAllowance',  │ 'Approval', 'Transfer',  │
│       │          │ 'increaseAllowance', 'name', 'symbol', 'totalSupply', 'transfer',      │                          │
│       │          │ 'transferFrom',                                                        │                          │
└───────┴──────────┴────────────────────────────────────────────────────────────────────────┴──────────────────────────┘
                                                               Cairo Decoder ABIs                                                               
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Name          ┃ Priority ┃ Functions                                                                  ┃ Events                               ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Starknet-ETH  │ 100      │ 'add_new_implementation', 'allowance', 'approve', 'balanceOf',             │ 'Approval', 'GovernanceAdminAdded',  │
│               │          │ 'balance_of', 'decimals', 'decreaseAllowance', 'decrease_allowance',       │ 'GovernanceAdminRemoved',            │
│               │          │ 'get_impl_activation_time', 'get_role_admin', 'get_upgrade_delay',         │ 'ImplementationAdded',               │
│               │          │ 'has_role', 'increaseAllowance', 'increase_allowance',                     │ 'ImplementationFinalized',           │
│               │          │ 'is_governance_admin', 'is_upgrade_governor', 'name', 'permissionedBurn',  │ 'ImplementationRemoved',             │
│               │          │ 'permissionedMint', 'permissioned_burn', 'permissioned_mint',              │ 'ImplementationReplaced',            │
│               │          │ 'register_governance_admin', 'register_upgrade_governor',                  │ 'RoleAdminChanged', 'RoleGranted',   │
│               │          │ 'remove_governance_admin', 'remove_implementation',                        │ 'RoleRevoked', 'Transfer',           │
│               │          │ 'remove_upgrade_governor', 'renounce', 'replace_to', 'symbol',             │ 'UpgradeGovernorAdded',              │
│               │          │ 'totalSupply', 'total_supply', 'transfer', 'transferFrom',                 │ 'UpgradeGovernorRemoved',            │
│               │          │ 'transfer_from',                                                           │                                      │
├───────────────┼──────────┼────────────────────────────────────────────────────────────────────────────┼──────────────────────────────────────┤
│ AVNU-Exchange │ 40       │ 'get_adapter_class_hash', 'get_fees_active', 'get_fees_bps_0',             │ 'OwnershipTransferred', 'Swap',      │
│               │          │ 'get_fees_bps_1', 'get_fees_recipient', 'get_owner',                       │                                      │
│               │          │ 'get_swap_exact_token_to_fees_bps', 'locked', 'multi_route_swap',          │                                      │
│               │          │ 'set_adapter_class_hash', 'set_fees_active', 'set_fees_bps_0',             │                                      │
│               │          │ 'set_fees_bps_1', 'set_fees_recipient',                                    │                                      │
│               │          │ 'set_swap_exact_token_to_fees_bps', 'swap_exact_token_to',                 │                                      │
│               │          │ 'transfer_ownership', 'upgrade_class',                                     │                                      │
└───────────────┴──────────┴────────────────────────────────────────────────────────────────────────────┴──────────────────────────────────────┘

```


## Backfilling Decoded Events
```bash
entro backfill starknet events --contract-address 0x04270219d365d6b017231b52e92b3fb5d7c8378b05e9abc97724537a80e93b0f -abi AVNU-Exchange --event-file=swap_events.csv --from-block 640000 --to-block 655000 --event-name Swap --batch-size 5000

                             Backfill Block Ranges
┏━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Start Block              ┃ End Block            ┃               Total Blocks ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 640,000                  │ 655,000              │                     15,000 │
└──────────────────────────┴──────────────────────┴────────────────────────────┘
                                  Backfill Filters & Metadata                                  
┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Key              ┃ Value                                                                    ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ contract_address │ 0x04270219d365d6b017231b52e92b3fb5d7c8378b05e9abc97724537a80e93b0f       │
│ event_names      │ ['Swap']                                                                 │
│ abi_name         │ AVNU-Exchange                                                            │
│ json_rpc         │ https://free-rpc.nethermind.io/mainnet-juno/                             │
│ batch_size       │ 5000                                                                     │
│ topics           │ [['0x00e316f0d9d2a3affa97de1d99bb2aac0538e2666d0d8545545ead241ef0ccab']] │
└──────────────────┴──────────────────────────────────────────────────────────────────────────┘
                               Cairo Decoder ABIs                               
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Name               ┃ Priority    ┃ Events                                    ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ AVNU-Exchange      │ 40          │ 'OwnershipTransferred', 'Swap',           │
└────────────────────┴─────────────┴───────────────────────────────────────────┘
Querying Events for Contract: 0x04270219d365d6b017231b52e92b3fb5d7c8378b05e9abc97724537a80e93b0f
AVNU-Exchange ABI Decoding Events:
        'Swap',
------------------------------------------------------------------------------------------------------------------------------------------------
Execute Backfill?   [y/n]:

Backfill AVNU-Exchange Events ⠧ ━━━━━━━━━━━╺━━━━━━━━━━━━━━━━━━━━━━━━━━━━  29% 0:00:12 -:--:-- Searched: 5000/15000 Searching Block: 64500

---- Backfill Complete ------

# CSV Data will be saved pipe-separated, and array/dict columns will be encoded as JSON

head -2 swap_events.csv

#   block_number|tx_index|event_index|contract_address|class_hash|keys|data|event_name|decoded_params
#   640000|-1|-1|0x04270219d365d6b017231b52e92b3fb5d7c8378b05e9abc97724537a80e93b0f||["0x00e316f0d9d2a3affa97de1d99bb2aac0538e2666d0d8545545ead241ef0ccab"]|["0x061e1a7ffad235cd34d5da18c
#   75efd01c3ae7b5029cafbf9f136f74c3fd6603c", "0x00585c32b625999e6e5e78645ff8df7a9001cf5cf3eb6b80ccdd16cb64bd3a34", "0x000000000000000000000000000000000000000000000001bded06268d96b74f",
#   "0x0000000000000000000000000000000000000000000000000000000000000000", "0x053c91253bc9682c04929ca02ed00b3e423f6710d2ee7e0d5ebb06f3ecf368a8", "0x0000000000000000000000000000000000000
#   0000000000000000000013a5221", "0x0000000000000000000000000000000000000000000000000000000000000000", "0x061e1a7ffad235cd34d5da18c75efd01c3ae7b5029cafbf9f136f74c3fd6603c"]|Swap|{"take
#   r_address": "0x061e1a7ffad235cd34d5da18c75efd01c3ae7b5029cafbf9f136f74c3fd6603c", "sell_address": "0x00585c32b625999e6e5e78645ff8df7a9001cf5cf3eb6b80ccdd16cb64bd3a34", "sell_amount"
#   : 32132345679012345679, "buy_address": "0x053c91253bc9682c04929ca02ed00b3e423f6710d2ee7e0d5ebb06f3ecf368a8", "buy_amount": 20599329, "beneficiary": "0x061e1a7ffad235cd34d5da18c75efd01c3ae7b5029cafbf9f136f74c3fd6603c"}
```

## Development Installation

```bash
git clone https://github.com/NethermindEth/entro
cd entro
poetry env use python3.12  # Can use older versions, but 12 performs much better
poetry install --all-extras

# Installing Pre-Commit
poetry run pre-commit install

# Running the Pre-Commit checks on demand
poetry run pre-commit run --all-files

# Running unit tests
poetry run pytest tests/

# Running Integration Tests --> Follow instructions in docs/Installation
```


## CLI Help
Each command & group has a --help flag available with details on the sub-commands and the 
arguments, options & flags for each command
```bash
# For additional help on commands
entro --help

#  Usage: entro [OPTIONS] COMMAND [ARGS]...
#  
#    Command Line Interface for Nethermind Entro
#  
#  Options:
#    --help  Show this message and exit.
#  
#  Commands:
#    backfill
#    decode      ABI Decoding & Event Classification
#    get         Utilities for Fetching Data from RPC Node
#    migrate-up  Migrate DB Tables to Latest Version
#    prices      Backfill ERC20 Token Prices
#    tokens      Utilities for ERC Tokens

entro backfill starknet events --help
#  Usage: entro backfill starknet events [OPTIONS]
#  
#    Backfill & ABI Decode StarkNet Events for a Contract
#  
#  Options:
#    -rpc, --json-rpc TEXT           JSONRPC URL to use for backfilling.  If not
#                                    provided, will use the JSON_RPC environment
#                                    variable
#    -db, --db-url TEXT              SQLAlchemy DB URL to use for backfilling.
#                                    If not provided, will use the DB_URL
#                                    environment variable
#    -from, --from-block TEXT        Start block for backfill. Can be an integer,
#                                    or a block identifier string like 'earliest'
#                                    [default: earliest]
#    -to, --to-block TEXT            End block for backfill. Can be an integer,
#                                    or a block identifier string like 'pending'
#                                    [default: latest]
#    -addr, --contract-address TEXT  Contract address for event/log backfills
#                                    [required]
#    -abi, --decode_abis TEXT        Names of ABIs to use for Decoding.  To view
#                                    available ABIs, run `entro list-abis`ABIs
#                                    can be added to the database using `entro
#                                    decoding add-abi`
#    -e, --event-name TEXT           Event name for event/log backfills.  Can be
#                                    input multiple times.  If not provided, will
#                                    backfill all events present in contract-abi
#    --batch-size INTEGER            Batch size to use for query.  When querying
#                                    an API, the batch is usually the page size.
#                                    For JSON RPC calls, the batch size is the
#                                    number of blocks each query will cover.
#    --event-file PATH               File to save event data
#    --help                          Show this message and exit.
```


## Documentation:
Documentation is currently being refactored and not live on github.  To view current documentation,
clone & setup the Repo & Run `poetry run sphinx-build docs/source/ docs/_build/`
