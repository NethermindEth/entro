import asyncio

from aiohttp import ClientSession

from nethermind.entro.exceptions import BackfillError
from nethermind.entro.types.backfill import (
    BackfillDataType,
    Dataclass,
    ImporterCallable,
    SupportedNetwork,
)
from nethermind.idealis.rpc.starknet import (
    get_blocks_with_txns,
    get_events_for_contract,
)
from nethermind.idealis.utils import to_bytes

# Network Importer Callables
from .starknet import starknet_transaction_importer, starknet_event_importer, starknet_block_importer
from .ethereum import ethereum_block_importer

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
        case BackfillDataType.blocks:
            return get_block_importer(network)
        case _:
            raise ValueError(f"Cannot find importer for Backfill Type: {data_type}")


def get_block_importer(network: SupportedNetwork) -> ImporterCallable:
    match network:
        case network.starknet:
            return starknet_block_importer
        case network.ethereum:
            return ethereum_block_importer
        case _:
            raise ValueError(f"Cannot find Block Importer for {network}")


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
