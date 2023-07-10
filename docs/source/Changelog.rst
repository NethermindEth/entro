Releases
========

.. note::
        This library is currently in an alpha stage and actively under development.  If you experience
        a bug or want to suggest a new feature, raise an issue on Github!


0.0.2 - USD Token Valuation
---------------------------

* Added Pricing Oracle to fetch ERC20 Token prices from Uniswap V3 contracts
    * Can price any ERC20 Token that has a USDC or WETH pair on Uniswap V3
    * Added USD Valuation to price LP positions in USD
* Initialization modes for Pools
    * Allows customizing what data is extracted when initializing a pool from a chain
    * Lightweight "Translation" mode to convert raw data to human friendly format


0.0.1 - Uniswap V3 pre-release
------------------------------

* Uniswap V3 Core Functionality
    * Querying Pool State from Chain
    * Simulating Swaps, Mints, and Burns
    * Analytics & Reporting Functionality
* Pool Factory API
* ERC20Token API
* Basic Event Scraping Support
    * Fetching Uniswap V3 Events
    * Generalized Event Backfill with minimal configuration


Upcoming Features in Development
--------------------------------

* Improve Accuracy for Fee tier & Liquidity Edge Cases
    * Several swap tests are currently failing with extreme fee tiers
    * Max liquidity simulations are also having issues (deploying near max liquidity)
* Multi-database support (currently only postgres is tested)
* ERC20 Transfer Event Scraping & Analytics
* Adding better plotting support for analytics
* Daily & Hourly price summary methods for Oracles


Possible Future Features
------------------------
* ERC20 Account Balances over time
* Additional Dex Support (Uni V2, Curve, Balancer, Sushi, etc.)
* Arbitrage Simulator
* **'Turbo'** mode event backfills


.. admonition:: Contact

    For Direct Questions, reach out to Eli Barbieri on telegram: `@elicbarbieri <https://t.me/elicbarbieri>`_

