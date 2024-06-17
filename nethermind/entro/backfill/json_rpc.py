import logging
from typing import Any, Literal

from rich.progress import Progress
from sqlalchemy import Connection, Engine

from nethermind.entro.backfill.planner import BackfillPlan
from nethermind.entro.backfill.utils import GracefulKiller
from nethermind.entro.database.models import (
    AbstractBlock,
    AbstractTransaction,
    block_model_for_network,
    transaction_model_for_network,
)
from nethermind.entro.database.writers import EventWriter, ModelWriter
from nethermind.entro.decoding import DecodingDispatcher
from nethermind.entro.types.backfill import BackfillDataType, SupportedNetwork

from ..exceptions import BackfillError
from ..utils import to_hex
from .async_rpc import retry_enabled_batch_post
from .utils import (
    add_receipt_to_tx_models,
    parse_event_request,
    parse_rpc_block_requests,
    parse_rpc_receipt_request,
    rpc_response_to_block_model,
)

root_logger = logging.getLogger("nethermind")
logger = root_logger.getChild("entro").getChild("backfill").getChild("json_rpc")

# pylint: disable=raise-missing-from,too-many-locals


def cli_get_blocks(
    backfill_plan: BackfillPlan,
    db_engine: Engine | Connection,
    json_rpc: str,
    progress: Progress,
):
    """
    CLI operator to download blocks from RPC and write them to the database

    :param backfill_plan:
    :param db_engine:
    :param json_rpc:
    :param progress:
    :return:
    """
    killer = GracefulKiller(console=progress.console)

    for range_idx, (from_block, to_block) in enumerate(backfill_plan.range_plan.backfill_ranges):
        backfill_result = backfill_block_range(
            db_engine=db_engine,
            json_rpc=json_rpc,
            from_block=from_block,
            to_block=to_block,
            network=backfill_plan.network,
            abi_decoder=backfill_plan.decoder,
            killer=killer,
            batch_size=backfill_plan.metadata_dict.get("batch_size", 50),
            max_concurrency=backfill_plan.metadata_dict.get("max_concurrency", 20),
            save_txns=backfill_plan.backfill_type != BackfillDataType.blocks,
            progress=progress,
            task_name=backfill_plan.backfill_label(range_idx),
        )

        if isinstance(backfill_result, int):
            logger.error(
                f"Backfilled up to Block {backfill_result}.  Terminating Backfill & "
                f"Updating Backfilled Range in DB..."
            )
            backfill_plan.process_failed_backfill(backfill_result)
            break
        backfill_plan.range_plan.mark_finalized(range_idx)


# pylint: disable=too-many-arguments
def backfill_block_range(
    db_engine: Engine | Connection,
    json_rpc: str,
    from_block: int,
    to_block: int,
    network: SupportedNetwork,
    abi_decoder: DecodingDispatcher | None = None,
    killer: GracefulKiller | None = None,
    batch_size: int = 50,
    max_concurrency: int = 20,
    save_txns: bool = True,
    progress: Progress | None = None,
    task_name: str = "",
) -> Literal["success"] | int:
    """
    Backfill blocks from RPC

    :param db_engine:
    :param json_rpc:
    :param from_block:
    :param to_block:
    :param network:
    :param abi_decoder:
    :param killer:
    :param batch_size:
    :param max_concurrency:
    :param save_txns:
    :param progress:
    :param task_name:
    :return:
    """

    if abi_decoder is None:
        abi_decoder = DecodingDispatcher()

    block_writer = ModelWriter(db_engine=db_engine, db_model=block_model_for_network(network))
    transaction_writer = (
        ModelWriter(
            db_engine=db_engine,
            db_model=transaction_model_for_network(network),
        )
        if save_txns
        else None
    )
    if progress:
        block_task = progress.add_task(task_name, total=to_block - from_block, searching_block=from_block)

    search_block = from_block
    while search_block <= to_block:
        if killer and killer.kill_now:
            return search_block

        if progress:
            progress.update(block_task, advance=batch_size, searching_block=search_block)

        try:
            block_models, tx_models = get_block_models_for_range(
                from_block=search_block,
                to_block=min(to_block, search_block + batch_size),
                json_rpc=json_rpc,
                network=network,
                decoder=abi_decoder,
                db_dialect=block_writer.db_dialect,
                full_txns=save_txns,
                max_concurrency=max_concurrency,
            )
        except BackfillError:
            logger.error(f"Failed to fetch blocks ({search_block} - {min(to_block, search_block + batch_size)})")
            if killer:
                killer.kill_now = True
            continue

        block_writer.add_backfill_data(block_models)
        if transaction_writer:
            transaction_writer.add_backfill_data(tx_models)

        search_block += batch_size

    if progress:
        progress.console.print("[green]Backfill Finished.  Writing Model Cache to Database....")

    block_writer.finish()
    if transaction_writer:
        transaction_writer.finish()

    if killer and killer.kill_now:
        return search_block
    return "success"


def get_block_models_for_range(
    from_block: int,
    to_block: int,
    json_rpc: str,
    network: SupportedNetwork,
    decoder: DecodingDispatcher,
    db_dialect: str,
    full_txns: bool = True,
    get_gas_used: bool = True,
    max_concurrency: int = 20,
) -> tuple[list[AbstractBlock], list[AbstractTransaction]]:
    """
    Asyncronously fetch blocks from RPC and decode them into models

    :param from_block:
    :param to_block:
    :param json_rpc:
    :param network:
    :param decoder:
    :param db_dialect:
    :param full_txns:
    :param get_gas_used:
    :param max_concurrency:
    :return:
    """
    request_objects = parse_rpc_block_requests(
        list(range(from_block, to_block)),
        network=network,
        full_txns=full_txns,
    )

    block_json = retry_enabled_batch_post(request_objects, json_rpc, max_concurrency)

    if block_json == "failed":
        logger.error(f"Querying Blocks from RPC failed between ({from_block} - {to_block - 1})")
        raise BackfillError()

    all_blocks, all_txns, last_hashes = [], [], []

    for block in block_json:
        block_data, transactions, last_tx = rpc_response_to_block_model(
            block=block,
            network=network,
            db_dialect=db_dialect,
            abi_decoder=decoder,
        )
        all_blocks.append(block_data)
        all_txns.extend(transactions)
        if last_tx:
            last_hashes.append(last_tx)

    if get_gas_used:
        receipts = retry_enabled_batch_post(
            request_objects=parse_rpc_receipt_request(last_hashes, network=network),
            json_rpc=json_rpc,
            max_concurrency=max_concurrency,
        )
        if receipts == "failed":
            logger.error(f"Querying Receipts from RPC failed between ({from_block} - {to_block - 1})")
            raise BackfillError()

        block_map = {block.block_number: block for block in all_blocks}

        for receipt in receipts:
            receipt_block = int(receipt["blockNumber"], 16)
            if receipt_block not in block_map:
                continue

            block_map[receipt_block].effective_gas_price = int(receipt["effectiveGasPrice"], 16)

    return all_blocks, all_txns


def get_transaction_receipts_for_txns(
    txns: list[AbstractTransaction],
    json_rpc: str,
    network: SupportedNetwork,
    max_concurrency: int = 20,
) -> tuple[list[AbstractTransaction], list[dict[str, Any]]]:
    """
    Asynchronously fetch transaction receipts from RPC and add them to the transaction models, returning enriched
    transaction models and the raw logs
    :param txns:
    :param json_rpc:
    :param network:
    :param max_concurrency:
    :return:  (enriched_txns, output_logs)
    """
    receipt_requests = parse_rpc_receipt_request(
        [to_hex(tx.transaction_hash) for tx in txns],
        network=network,
    )

    receipt_json = retry_enabled_batch_post(receipt_requests, json_rpc, max_concurrency)

    if receipt_json == "failed":
        raise BackfillError()

    enriched_txns = add_receipt_to_tx_models(transactions=txns, receipt_responses=receipt_json, strict=True)

    output_logs = []
    for receipt in receipt_json:
        output_logs += receipt["logs"]

    return enriched_txns, output_logs


def cli_get_full_blocks(
    backfill_plan: BackfillPlan,
    db_engine: Engine | Connection,
    json_rpc: str,
    progress: Progress,
):
    """
    Asynchronously fetch transactions, blocks, and receipts from RPC.

    :param backfill_plan:
    :param db_engine:
    :param json_rpc:
    :param progress:
    :return:
    """

    batch_size = backfill_plan.metadata_dict.get("batch_size", 20)

    block_writer = ModelWriter(db_engine=db_engine, db_model=block_model_for_network(backfill_plan.network))
    transaction_writer = ModelWriter(
        db_engine=db_engine,
        db_model=transaction_model_for_network(backfill_plan.network),
    )
    event_writer = EventWriter(
        db_engine=db_engine,
        network=backfill_plan.network,
    )

    killer = GracefulKiller(console=progress.console)

    for range_idx, (from_block, to_block) in enumerate(backfill_plan.range_plan.backfill_ranges):
        backfill_task = progress.add_task(
            backfill_plan.backfill_label(range_idx),
            total=to_block - from_block,
            searching_block=from_block,
        )

        search_block = from_block

        while search_block <= to_block:
            if killer.kill_now:
                progress.console.print(f"[red]Processing Terminated Backfill up to block {search_block}")
                backfill_plan.process_failed_backfill(search_block)
                break

            progress.update(backfill_task, advance=batch_size, searching_block=search_block)

            try:
                block_models, intermediate_tx_models = get_block_models_for_range(
                    search_block,
                    min(to_block, search_block + batch_size),
                    network=backfill_plan.network,
                    json_rpc=json_rpc,
                    decoder=backfill_plan.decoder,
                    db_dialect=block_writer.db_dialect,
                    max_concurrency=backfill_plan.metadata_dict.get("max_concurrency", 50),
                )
            except BackfillError:
                logger.error(
                    f"Failed to fetch full blocks ({search_block} - {min(to_block, search_block + batch_size)})"
                )
                killer.kill_now = True
                continue

            try:
                tx_models, raw_logs = get_transaction_receipts_for_txns(
                    txns=intermediate_tx_models,
                    json_rpc=json_rpc,
                    network=backfill_plan.network,
                    max_concurrency=backfill_plan.metadata_dict.get("max_concurrency", 50),
                )

            except BackfillError:
                logger.error(
                    f"Failed to fetch transaction receipts for Range "
                    f"({search_block} - {min(to_block, search_block + batch_size)})"
                )
                killer.kill_now = True
                continue

            for log in raw_logs:
                decoding_result = backfill_plan.decoder.decode_log(log)
                if decoding_result is None:
                    continue

                event_writer.write_event(
                    decoding_result=decoding_result,
                    raw_log=log,
                )

            block_writer.add_backfill_data(block_models)
            transaction_writer.add_backfill_data(tx_models)

            search_block += batch_size

        if killer.kill_now:
            break
        backfill_plan.range_plan.mark_finalized(range_idx)

    progress.console.print("[green]Finished Backfill.  Writing Model Cache to Database...")
    block_writer.finish()
    event_writer.finish()
    transaction_writer.finish()


# def cli_trace_transactions(
#     json_rpc: str,
#     network: SupportedNetwork,
#     db_engine: Engine,
#     transaction_hashes: List[str],
#     decoders: Optional[List[ABIDecoder]] = None,
# ):
#     traces = []
#
#     with click.progressbar(transaction_hashes) as bar:
#         for tx_hash in bar:
#             trace_data = w3.manager.request_blocking("trace_transaction", [tx_hash])
#             parsed_traces = [
#                 parse_eth_trace(trace, network, db_engine.dialect.name)
#                 for trace in trace_data
#                 if trace["type"] in ["call", "delegatecall"]
#             ]
#             if len(parsed_traces) > 0:
#                 traces.extend(parsed_traces)
#
#             if len(traces) >= 100:
#                 db_session.bulk_save_objects(traces)
#                 db_session.commit()
#                 traces = []
#


def cli_get_logs(  # pylint: disable=too-many-branches
    backfill_plan: BackfillPlan,
    db_engine: Engine | Connection,
    json_rpc: str,
    progress: Progress,
):
    """
    Asynchronously fetch logs from RPC, Decode, and Write to Database. Fetches logs from a single Contract

    :param backfill_plan:
    :param db_engine:
    :param json_rpc:
    :param progress:
    :return:
    """

    batch_size = backfill_plan.metadata_dict.get("batch_size", 1000)
    max_concurrency = backfill_plan.metadata_dict.get("max_concurrency", 20)
    contract_address = backfill_plan.get_filter_param("contract_address")

    model_overrides = backfill_plan.load_model_overrides()

    event_writer = EventWriter(
        db_engine=db_engine,
        network=backfill_plan.network,
        event_model_overrides=model_overrides,
    )

    killer = GracefulKiller(console=progress.console)

    for range_idx, (start_block, end_block) in enumerate(backfill_plan.range_plan.backfill_ranges):
        all_request_objects = [
            parse_event_request(
                start_block=start_block,
                end_block=min(start_block + batch_size, end_block),
                contract_address=contract_address,
                topics=backfill_plan.get_metadata("topics"),
                network=backfill_plan.network,
            )
            for start_block in range(start_block, end_block, batch_size)
        ]

        backfill_res = decode_events_for_requests(
            request_objects=all_request_objects,
            json_rpc=json_rpc,
            event_writer=event_writer,
            decoder=backfill_plan.decoder,
            batch_size=batch_size,
            max_concurrency=max_concurrency,
            killer=killer,
            progress=progress,
            task_name=backfill_plan.backfill_label(range_idx),
        )

        if isinstance(backfill_res, int):
            logger.error(
                f"Backfilled up to Block {backfill_res}.  Terminating Backfill & " f"Updating Backfilled Range in DB..."
            )
            backfill_plan.process_failed_backfill(backfill_res)
            break
        backfill_plan.range_plan.mark_finalized(range_idx)

    progress.console.print("[green]Backfill Finished.  Writing Model Cache to Database....")
    event_writer.finish()


def decode_events_for_requests(
    request_objects: list[dict[str, Any]],
    json_rpc: str,
    event_writer: EventWriter,
    decoder: DecodingDispatcher,
    batch_size: int = 10_000,
    max_concurrency: int = 20,
    killer: GracefulKiller | None = None,
    progress: Progress | None = None,
    task_name: str = "",
) -> Literal["success"] | int:
    """
    Asynchronously fetch logs from RPC, Decode, and Write to Database.

    :param request_objects: List of RPC Request Objects
    :param json_rpc:
    :param event_writer:
    :param decoder:
    :param batch_size:
    :param max_concurrency:
    :param killer:
    :param progress:
    :param task_name:
    :return:
    """

    start_block = int(request_objects[0]["params"][0]["fromBlock"], 16)
    end_block = int(request_objects[-1]["params"][0]["toBlock"], 16) + 1

    if progress:
        backfill_task = progress.add_task(
            description=task_name,
            total=end_block - start_block,
            searching_block=start_block,
        )

    search_block = start_block

    for batch_index in range(0, len(request_objects), max_concurrency):
        if killer and killer.kill_now:
            logger.warning(f"[red]Processing Terminated Backfill up to block {search_block}")
            event_writer.finish()
            return search_block

        batch_query_objs = request_objects[batch_index : batch_index + max_concurrency]
        search_block = int(batch_query_objs[0]["params"][0]["fromBlock"], 16)

        if progress:
            progress.update(
                backfill_task,
                advance=batch_size * max_concurrency,
                searching_block=search_block,
            )

        request_responses = retry_enabled_batch_post(
            request_objects=batch_query_objs,
            json_rpc=json_rpc,
            max_concurrency=max_concurrency,
        )

        if request_responses == "failed":
            logger.error(
                f"RPC Query Failed During Log Query Between ({search_block} - "
                f"{int(batch_query_objs[-1]['params'][0]['toBlock'], 16)})"
            )
            if killer:
                killer.kill_now = True
                continue

            return search_block

        raw_logs: list[dict[str, Any]] = []
        for resp in request_responses:
            raw_logs.extend(resp)

        for log in raw_logs:
            decoding_result = decoder.decode_log(log)
            if decoding_result is None:
                continue

            event_writer.write_event(
                decoding_result=decoding_result,
                raw_log=log,
            )

    event_writer.finish()
    return "success"
