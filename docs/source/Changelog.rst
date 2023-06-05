Releases
========

.. note::
        This library is currently in an alpha stage and actively under development.  If you experience
        a bug or want to suggest a new feature, raise an issue on Github!


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

* ERC20 Token price feeds through Dex Contracts
    * Valuing Positions in USD
    * Logging Token Data in USD
* Improve Accuracy for Fee tier & Liquidity Edge Cases
    * Several swap tests are currently failing with extreme fee tiers
    * Max liquidity simulations are also having issues (deploying near max liquidity)
* Multi-database support (currently only postgres is tested)
* ERC20 Transfer Event Scraping & Analytics
* Adding better plotting support for analytics
* Enhance On-Chain Query Capabilities
    * Enable Lookup & Valuation of Single LP Position
    * Add optimized initialization modes for Uni V3


Possible Future Features
------------------------
* ERC20 Account Balances over time
* Additional Dex Support (Uni V2, Curve, Balancer, Sushi, etc.)
* Arbitrage Simulator



