Pricing Oracle
==============

Initializing Pricing Oracle
---------------------------


Class Documentation
-------------------

.. autoclass:: python_eth_amm.PricingOracle
   :exclude-members: __init__
   :members:


Database Tables
---------------
All database objects for the Pricing oracle are stored under the `pricing_oracle` schema.


``backfilled_pools``
____________________

.. list-table::
    :header-rows: 1

    * - Field
      - Type
      - Description

    * - pool_id
      - varchar(42)
      - Hex Address of the Pool Contract

    * - backfill_start
      - integer
      - Block Number the Pool Backfill Started

    * - backfill_end
      - integer
      - Block Number the Pool Backfill Ended


``block_timestamps``
____________________

.. list-table::
    :header-rows: 1

    * - Field
      - Type
      - Description

    * - block_number
      - integer
      - Block Number

    * - timestamp
      - timestamp
      - UTC Timestamp for the Block


``token_prices``
________________

.. list-table::
    :header-rows: 1

    * - Field
      - Type
      - Description

    * - token_id
      - varchar(42)
      - Hex Token Address

    * - block_number
      - bigint(20) unsigned
      - Block Number the Price was recorded at

    * - spot_price
      - numeric
      - Spot Price of the Pool at end of block


``uni_v3_pool_creations``
_________________________

.. list-table::
    :header-rows: 1

    * - Field
      - Type
      - Description

    * - token_0
      - varchar(42)
      - Hex Token Address for Token 0

    * - token_1
      - varchar(42)
      - Hex Token Address for Token 1

    * - pool_address
      - varchar(42)
      - Hex Address of the Pool Contract

    * - fee
      - integer
      - Swap fee for pool in 100ths of a bip

    * - block_number
      - integer
      - Block Number the Pool was created at
