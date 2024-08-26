from aiohttp import ClientSession, TCPConnector

from nethermind.entro.exceptions import BackfillError
from nethermind.entro.types.backfill import Dataclass
from nethermind.idealis.rpc.ethereum import get_blocks
from nethermind.idealis.utils import to_bytes
from nethermind.idealis.wrapper.etherscan import get_transactions_for_account

from .retry import retry_async_run


def ethereum_block_importer(from_block: int, to_block: int, **kwargs) -> dict[str, list[Dataclass]]:
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
        return {"blocks": blocks}

    if "json_rpc" in kwargs:
        return retry_async_run(_get_rpc_block_data, **kwargs)
    raise BackfillError("'json_rpc' required to backfill starknet transactions")


def ethereum_transaction_importer(from_block: int, to_block: int, **kwargs) -> dict[str, list[Dataclass]]:
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
        return {"blocks": blocks, "transactions": transactions}

    async def _get_account_txns(**kwargs):
        account_txns = get_transactions_for_account(
            api_key=kwargs["etherscan_api_key"],
            api_endpoint="https://api.etherscan.io/api",
            from_block=from_block,
            to_block=to_block,
            account_address=to_bytes(kwargs["for_address"], pad=20),
        )

        return {"transactions": account_txns}

    if "etherscan_api_key" in kwargs:
        assert "for_address" in kwargs, "Missing 'for_address' in kwargs for etherscan account tx import"
        return retry_async_run(_get_account_txns, **kwargs)
    if "json_rpc" in kwargs:
        return retry_async_run(_get_rpc_block_data, **kwargs)
    raise BackfillError("'json_rpc' or 'etherscan_api_key' required to backfill starknet transactions")
