import asyncio

from aiohttp import ClientSession, TCPConnector

from nethermind.entro.exceptions import BackfillError
from nethermind.entro.types.backfill import Dataclass, ExporterDataType
from nethermind.idealis.parse.starknet.transaction import parse_transaction_responses
from nethermind.idealis.rpc.starknet import (
    get_blocks,
    get_blocks_with_txns,
    get_events_for_contract,
)
from nethermind.idealis.utils import to_bytes

from .retry import retry_async_run


def starknet_transaction_importer(from_block: int, to_block: int, **kwargs) -> dict[ExporterDataType, list[Dataclass]]:
    """Import starknet transactions from a range of blocks"""

    async def _get_rpc_block_data(**kwargs):
        connector = TCPConnector(limit=kwargs.get("max_concurrency", 20))
        client_session = ClientSession(connector=connector)
        try:
            blocks, transactions, events = await get_blocks_with_txns(
                list(range(from_block, to_block)), kwargs["json_rpc"], client_session
            )
        finally:
            await client_session.close()
        return {
            ExporterDataType.blocks: blocks,
            ExporterDataType.transactions: parse_transaction_responses(transactions),
            ExporterDataType.events: events,
        }

    if "json_rpc" in kwargs:
        return retry_async_run(_get_rpc_block_data, **kwargs)
    raise BackfillError("'json_rpc' required to backfill starknet transactions")


def _split_range(start: int, end: int, num_splits: int = 10) -> list[tuple[int, int]]:
    length = end - start
    split_size = length // num_splits
    ranges = []
    for i in range(num_splits):
        sub_start = start + i * split_size
        sub_end = sub_start + split_size
        ranges.append((sub_start, sub_end))
    # Adjust the last range to include any remaining elements
    ranges[-1] = (ranges[-1][0], end)
    return ranges


def starknet_event_importer(from_block: int, to_block: int, **kwargs) -> dict[ExporterDataType, list[Dataclass]]:
    """Import starknet events from a range of block numbers"""

    async def _get_starknet_events_for_range(**kwargs):
        connector = TCPConnector(limit=kwargs.get("max_concurrency", 20))
        client_session = ClientSession(connector=connector)
        try:
            event_batches = await asyncio.gather(
                *[
                    get_events_for_contract(
                        contract_address=kwargs["contract_address"],
                        event_keys=[to_bytes(t) for t in kwargs["topics"][0]],
                        from_block=from_,
                        to_block=to_,
                        rpc_url=kwargs["json_rpc"],
                        aiohttp_session=client_session,
                    )
                    for from_, to_ in _split_range(from_block, to_block)
                ]
            )
            output_events = []
            for batch in event_batches:
                output_events.extend(batch)
        finally:
            await client_session.close()
        return output_events

    if "json_rpc" in kwargs and "contract_address" in kwargs and "topics" in kwargs:
        return {ExporterDataType.events: retry_async_run(_get_starknet_events_for_range, **kwargs)}

    raise BackfillError("'json_rpc', 'contract_address', and 'topics' required in metadata to backfill starknet events")


def starknet_block_importer(from_block: int, to_block: int, **kwargs) -> dict[ExporterDataType, list[Dataclass]]:
    """Import starknet blocks from a range of block numbers"""

    async def _get_starknet_blocks_for_range(**kwargs):
        connector = TCPConnector(limit=kwargs.get("max_concurrency", 20))
        client_session = ClientSession(connector=connector)
        try:
            blocks = await get_blocks(list(range(from_block, to_block)), kwargs["json_rpc"], client_session)
        finally:
            await client_session.close()

        return {ExporterDataType.blocks: blocks}

    if "json_rpc" in kwargs:
        return retry_async_run(_get_starknet_blocks_for_range, **kwargs)

    raise BackfillError("'json_rpc' required to backfill starknet blocks")
