from aiohttp import ClientSession, TCPConnector

from nethermind.entro.exceptions import BackfillError
from nethermind.entro.types.backfill import Dataclass, ExporterDataType
from nethermind.idealis.rpc.ethereum import get_blocks, get_events_for_contract
from nethermind.idealis.utils import to_bytes
from nethermind.idealis.wrapper.etherscan import get_transactions_for_account

from .retry import retry_async_run


def ethereum_block_importer(from_block: int, to_block: int, **kwargs) -> dict[ExporterDataType, list[Dataclass]]:
    """Import ethereum blocks from a range of block numbers"""

    async def _get_rpc_block_data(**kwargs):
        connector = TCPConnector(limit=kwargs.get("max_concurrency", 20))
        client_session = ClientSession(connector=connector)
        try:
            blocks, _ = await get_blocks(
                list(range(from_block, to_block)), kwargs["json_rpc"], client_session, full_transactions=False
            )
        finally:
            await client_session.close()
        return {ExporterDataType.blocks: blocks}

    if "json_rpc" in kwargs:
        return retry_async_run(_get_rpc_block_data, **kwargs)
    raise BackfillError("'json_rpc' required to backfill starknet transactions")


def ethereum_transaction_importer(from_block: int, to_block: int, **kwargs) -> dict[ExporterDataType, list[Dataclass]]:
    """Import ethereum transactions from a range of blocks"""

    async def _get_rpc_block_data(**kwargs):
        connector = TCPConnector(limit=kwargs.get("max_concurrency", 20))
        client_session = ClientSession(connector=connector)
        try:
            blocks, transactions = await get_blocks(
                list(range(from_block, to_block)),
                kwargs["json_rpc"],
                client_session,
            )
        finally:
            await client_session.close()
        return {ExporterDataType.blocks: blocks, ExporterDataType.transactions: transactions}

    async def _get_account_txns(**kwargs):
        account_txns = get_transactions_for_account(
            api_key=kwargs["etherscan_api_key"],
            api_endpoint="https://api.etherscan.io/api",
            from_block=from_block,
            to_block=to_block,
            account_address=to_bytes(kwargs["for_address"], pad=20),
        )

        return {ExporterDataType.transactions: account_txns}

    if kwargs["etherscan_api_key"]:
        assert kwargs["for_address"], "Missing 'for_address' in kwargs for etherscan account tx import"
        return retry_async_run(_get_account_txns, **kwargs)

    if kwargs["json_rpc"]:
        return retry_async_run(_get_rpc_block_data, **kwargs)

    raise BackfillError("'json_rpc' or 'etherscan_api_key' required to backfill starknet transactions")


def ethereum_event_importer(from_block: int, to_block: int, **kwargs) -> dict[ExporterDataType, list[Dataclass]]:
    """Import ethereum events from a range of blocks"""

    async def _get_rpc_block_data(**kwargs):
        client_session = ClientSession()
        try:
            events = await get_events_for_contract(
                contract_address=to_bytes(kwargs["contract_address"], pad=20),
                topics=[
                    to_bytes(topic) if not isinstance(topic, list) else [to_bytes(t) for t in topic]
                    for topic in kwargs["topics"]
                ],
                from_block=from_block,
                to_block=to_block,
                rpc_url=kwargs["json_rpc"],
                aiohttp_session=client_session,
            )
        finally:
            await client_session.close()

        return {ExporterDataType.events: events}

    if kwargs["json_rpc"]:
        assert kwargs["contract_address"], "Missing 'contract_address' in kwargs for event import"
        assert kwargs["topics"], "Missing 'topics' in kwargs for event import"

        return retry_async_run(_get_rpc_block_data, **kwargs)

    raise BackfillError("'json_rpc' required to backfill starknet transactions")
