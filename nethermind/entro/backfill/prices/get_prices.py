import logging
from typing import Any

from eth_typing import ChecksumAddress
from rich.console import Console
from rich.progress import Progress
from sqlalchemy.orm import Session

from nethermind.entro.backfill.planner import BackfillPlan
from nethermind.entro.backfill.utils import GracefulKiller
from nethermind.entro.database.models.prices import (
    SUPPORTED_POOL_CREATION_EVENTS,
    MarketSpotPrice,
)
from nethermind.entro.database.readers.prices import get_pool_creation_backfills
from nethermind.entro.decoding import DecodingDispatcher
from nethermind.entro.exceptions import BackfillError, OracleError
from nethermind.entro.types.backfill import BackfillDataType, SupportedNetwork
from nethermind.entro.types.prices import (
    AbstractTokenMarket,
    SupportedPricingPool,
    TokenMarketInfo,
)

root_logger = logging.getLogger("nethermind")
logger = root_logger.getChild("entro").getChild("backfill").getChild("prices")


def cli_download_pool_creations(
    console: Console,
    db_session: Session,
    json_rpc: str,
):
    """
    Downloads pool creations from the Ethereum blockchain and saves them to the database.
    """

    killer = GracefulKiller(console=console)
    for factory_addr, pool_data in SUPPORTED_POOL_CREATION_EVENTS.items():
        backfill_plan = BackfillPlan.from_database(
            db_session=db_session,
            network=SupportedNetwork.ethereum,
            backfill_type=BackfillDataType.events,
            from_block=pool_data["start_block"],
            to_block="latest",
            filter_params={
                "contract_address": factory_addr,
                "decode_abis": [pool_data["abi_name"]],
                "event_names": [pool_data["event_name"]],
            },
            backfill_metadata={"batch_size": 100_000, "json_rpc": json_rpc},
        )

        if backfill_plan is None:
            raise OracleError("Failed to Backfill Pool Creation Events")

        backfill_plan.execute_backfill(console, killer, display_progress=True)
        backfill_plan.save_to_db()


def update_pool_creations(
    db_session: Session,
    latest_block: int,
    json_rpc: str,
    network: SupportedNetwork,
):
    """
    Updates pool creations for computing price backfills.

    :param db_session:
    :param latest_block:
    :param json_rpc:
    :param network:
    :return:
    """

    pool_creation_bfills = get_pool_creation_backfills(db_session, network)

    if len(pool_creation_bfills) != len(SUPPORTED_POOL_CREATION_EVENTS) or any(
        (latest_block - bfill.end_block) > 50_400 for bfill in pool_creation_bfills
    ):
        raise OracleError(
            "Pool Creation Backfills are out of date.  Run the CLI command `entro prices initialize` "
            "to update Pool Creation Events"
        )

    for pool_bfill in pool_creation_bfills:
        # TODO: Add BackfillPlan.from_cache()  & BackfillPlan.update()
        pass


def get_price_events_for_range(
    contract_address: ChecksumAddress,
    decoder: DecodingDispatcher,
    topics: list[str | list[str]],
    json_rpc: str,
    network: SupportedNetwork,
    start: int,
    end: int,
) -> list[dict[str, Any]]:
    """
    Returns a list of swap events for a given token market within a specified block range.  If desired events
    are already backfilled, this function will return the events from the database.  If the desired events are
    not backfilled, it will query the blockchain for the events, and return the results.  Intermediate Events
    queried by this function are not stored in the database.

    """

    return_vals: list[dict[str, Any]] = []

    # If Events are Backfilled in DB, Trim down the required query range
    # Generate BackfillPlan for the Swap events

    return return_vals


def backfill_spot_prices(
    backfill_plan: BackfillPlan,
    market_info: TokenMarketInfo,
    translator: AbstractTokenMarket,
    db_session: Session,
    json_rpc: str,
    network: SupportedNetwork,
    progress: Progress,
):
    """
    Backfills spot prices for all token markets.  This function will query the blockchain for all swap events
    for a given token market, and store them in the database.  If the events are already backfilled, this function
    will skip the query, and move on to the next token market.
    """

    batch_size = backfill_plan.metadata_dict.get("batch_size", 5_000)
    ref_token = backfill_plan.get_metadata("reference_token")

    match market_info.pool_class:
        case SupportedPricingPool.uniswap_v3:
            pass

    killer = GracefulKiller(console=progress.console)

    decoder = backfill_plan.decoder
    assert decoder is not None, "Decoder must be provided for backfilling spot prices"
    price_event_topics = backfill_plan.get_metadata("topics")

    for range_idx, (start_block, end_block) in enumerate(backfill_plan.range_plan.backfill_ranges):
        backfill_task = progress.add_task(
            description=backfill_plan.backfill_label(range_idx),
            total=end_block - start_block,
            searching_block=start_block,
        )

        for start_slice in range(start_block, end_block, batch_size):
            spot_price_models: list[MarketSpotPrice] = []
            if killer and killer.kill_now:
                logger.warning(f"[red]Processing Terminated Backfill up to block {start_slice}")
                return

            progress.update(
                backfill_task,
                advance=min(batch_size, end_block - start_slice),
                searching_block=start_slice,
            )
            try:
                pricing_events = get_price_events_for_range(
                    contract_address=market_info.market_address,
                    decoder=decoder,
                    topics=price_event_topics,
                    json_rpc=json_rpc,
                    network=network,
                    start=start_slice,
                    end=min(start_slice + batch_size, end_block),
                )
            except BackfillError:
                logger.error(
                    f"Failed to Backfill Price Events for {market_info.pool_class} "
                    f"market {market_info.market_address}"
                )
                killer.kill_now = True
                backfill_plan.process_failed_backfill(start_slice)
                break

            sorted_events = sorted(pricing_events, key=lambda x: (x["block_number"], x["log_index"]))
            prev_event = sorted_events[0]

            # TODO: Cleanup DRY
            for event in sorted_events[1:]:
                if prev_event["block_number"] != event["block_number"]:
                    spot_price_models.append(
                        MarketSpotPrice(
                            market_address=market_info.market_address,
                            block_number=prev_event["block_number"],
                            transaction_index=prev_event["transaction_index"],
                            spot_price=translator.decode_price_from_event(prev_event, ref_token),
                        )
                    )

                prev_event = event

            spot_price_models.append(
                MarketSpotPrice(
                    market_address=market_info.market_address,
                    block_number=prev_event["block_number"],
                    transaction_index=prev_event["transaction_index"],
                    spot_price=translator.decode_price_from_event(prev_event, ref_token),
                )
            )

            db_session.add_all(spot_price_models)
            db_session.commit()

        if killer.kill_now:
            return

        backfill_plan.range_plan.mark_finalized(range_idx, backfill_plan.range_kwargs())
