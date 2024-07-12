import asyncio

from aiohttp import ClientSession

from nethermind.entro.exceptions import BackfillError
from nethermind.entro.types.backfill import (
    BackfillDataType,
    Dataclass,
    ImporterCallable,
    SupportedNetwork,
)
from nethermind.entro.utils import to_bytes
from nethermind.idealis.rpc.starknet import (
    get_blocks_with_txns,
    get_events_for_contract,
)


def starknet_transaction_importer(from_block: int, to_block: int, **kwargs) -> dict[str, list[Dataclass]]:
    async def _get_rpc_block_data():
        client_session = ClientSession()
        blocks, transactions, events = await get_blocks_with_txns(
            list(range(from_block, to_block)), kwargs["json_rpc"], client_session
        )
        await client_session.close()
        return {"blocks": blocks, "transactions": transactions, "events": events}

    if "json_rpc" in kwargs:
        return asyncio.run(_get_rpc_block_data())
    raise BackfillError("'json_rpc' required in metadata to backfill starknet transactions")


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


def starknet_event_importer(from_block: int, to_block: int, **kwargs) -> dict[str, list[Dataclass]]:
    async def _get_starknet_events_for_range():
        client_session = ClientSession()
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
        await client_session.close()
        return output_events

    if "json_rpc" in kwargs and "contract_address" in kwargs and "topics" in kwargs:
        return {"events": asyncio.run(_get_starknet_events_for_range())}
    raise BackfillError("'json_rpc', 'contract_address', and 'topics' required in metadata to backfill starknet events")


def get_importer_for_backfill(
    network: SupportedNetwork,
    data_type: BackfillDataType,
) -> ImporterCallable:
    """
    Returns a dictionary of importers for backfill operations
    :return:
    """
    match data_type:
        case BackfillDataType.transactions:
            return get_transaction_importer(network)
        case BackfillDataType.full_blocks:
            return get_full_block_importer(network)
        case BackfillDataType.events:
            return get_event_importer(network)
        case _:
            raise ValueError(f"Cannot find importer for Backfill Type: {data_type}")


def get_transaction_importer(network: SupportedNetwork) -> ImporterCallable:
    match network:
        case network.starknet:
            return starknet_transaction_importer
        case _:
            raise ValueError(f"Cannot find Transaction Importer for {network}")


def get_full_block_importer(network: SupportedNetwork) -> ImporterCallable:
    match network:
        case network.starknet:
            return starknet_transaction_importer
        case _:
            raise ValueError(f"Cannot find Full Block Importer for {network}")


def get_event_importer(network: SupportedNetwork) -> ImporterCallable:
    match network:
        case network.starknet:
            return starknet_event_importer
        case _:
            raise ValueError(f"Cannot find Event Importer for {network}")
