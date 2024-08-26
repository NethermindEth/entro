Data Persistence
================

CSV File Formats
****************

Blocks
------

.. list-table:: Starknet Blocks
    :widths: 20, 30, 50
    :header-rows: 1

    * - Column Name
      - Datatype
      - Description
    * - block_number
      - integer
      - Block Number
    * - timestamp
      - int
      - Unix timestamp for block
    * - block_hash
      - 0x prefixed hex string
      - Hash of the block
    * - parent_hash
      - 0x prefixed hex string
      - Hash of the parent block
    * - state_root
      - 0x prefixed hex string
      - Hash of the state root
    * - sequencer_address
      - 0x prefixed hex string
      - Address of the sequencer
    * - l1_gas_price_wei
      - int
      - L1 gas price in WEI (1e-18 ETH)
    * - l1_gas_price_fri
      - int
      - L1 gas price in FRI (1e-18 STRK)
    * - l1_data_gas_price_wei
      - int
      - L1 gas price for posting calldata
    * - l1_data_gas_price_fri
      - int
      - L1 gas price for posting calldata
    * - l1_da_mode
      - 'blob' or 'calldata'
      - Where calldata is being posted.
    * - starknet_version
      - string
      - Version of Starknet, ie '13.1.0'
    * - transaction_count
      - int
      - Number of transactions in the block
    * - total_fee
      - int
      - Not Yet Implemented: TODO


Transactions
------------

.. list-table:: Starknet Transactions
    :widths: 20, 30, 50
    :header-rows: 1

    * - Column Name
      - Datatype
      - Description
    * - transaction_hash
      - 0x prefixed hex string
      - Hash of the transaction
    * - block_number
      - integer
      - Block Number
    * - transaction_index
      - integer
      - Index of the transaction in the block
    * - transaction_type
      - enum string
      - Type of transaction ('invoke', 'deploy', 'declare', 'deploy_account', 'l1_handler')
    * - nonce
      - integer
      - Nonce of the transaction
    * - signature
      - list of 2 0x prefixed hex strings
      - Signature of the transaction
    * - version
      - integer
      - Version of the transaction.  Newer versions include more fields
    * - timestamp
      - int
      - Unix timestamp for block
    * - status
      - enum string
      - Status of the transaction ('not_received', 'received', 'rejected', 'reverted', 'accepted_on_l2', 'accepted_on_l1')
    * - max_fee
      - int
      - Maximum fee for the transaction (in fee_unit)
    * - actual_fee
      - int
      - Actual fee paid for the transaction (in fee_unit)
    * - fee_unit
      - enum string
      - Fee unit ('wei', 'fri', 'calldata')
    * - execution_resources
      - JSON encoded dict
      - Execution resources used by the transaction, ie. {'steps': 100, 'memory_holes': 20}
    * - gas_used
      - int
      - Gas used by the transaction
    * - tip
      - int
      - Not in Use -- Will Eventually Enable Fee Market
    * - resource_bounds
      - JSON encoded dict
      - Not in Use -- Will Eventually Enable Fee Market
    * - paymaster_data
      - list of 0x prefixed hex strings
      - Not in Use -- Will Eventually Enable Fee Market
    * - account_deployment_data
      - list of 0x prefixed hex strings
      - Used in V3+ transactions on deploy txns
    * - data_availablity_mode
      - tuple of 2 enum strings (Fee DA Mode, Nonce DA Mode)
      - Data Availability Mode for Fee and Nonce ('calldata', 'blob')
    * - contract_address
      - 0x prefixed hex string
      - If invoke transaction, this is the contract address sending the txn.  If deploy transaction, this is the contract address being deployed.
    * - selector
      - 0x prefixed hex string
      - Function selector for the transaction
    * - calldata
      - list of 0x prefixed hex strings
      - Calldata for the transaction
    * - class_hash
      - 0x prefixed hex string
      - used for declare transactions, hash of class being initialized
    * - user_operations
      - list of JSON encoded dicts
      - List of user operations in the transaction
    * - revert_error
      - string
      - Revert error message if transaction was reverted
