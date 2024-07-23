import os
import signal

import requests
from rich.console import Console
from rich.progress import (
    BarColumn,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from nethermind.idealis.exceptions import RPCError
from nethermind.entro.types import BlockIdentifier
from nethermind.entro.types.backfill import SupportedNetwork as SN

progress_defaults = [
    TextColumn("[progress.description]{task.description}"),
    SpinnerColumn(),
    BarColumn(),
    TaskProgressColumn(),
    TimeElapsedColumn(),
    TimeRemainingColumn(),
    TextColumn("[green]Searched: {task.completed}/{task.total}"),
    TextColumn("[magenta]Searching Block: {task.fields[searching_block]}"),
]


def default_rpc(network: SN) -> str:
    """
    Returns the default RPC for a network.

    .. warning::
        This function is not guaranteed to return a working or high capacity RPC.  It is only used as a fallback when
        no RPC is specified in the environment.  For intensive backfills, specify RPC manually

    :param network:
    :return:
    """
    match network:
        case SN.ethereum:
            return "https://eth.public-rpc.com/"
        case SN.zk_sync_era:
            return "https://mainnet.era.zksync.io"
        case SN.starknet:
            return "https://free-rpc.nethermind.io/mainnet-juno/"
        case _:
            raise NotImplementedError(f"Network {network} does not")


def etherscan_base_url(network: SN) -> str:
    """
    Returns the base url for etherscan API requests.  Switches between etherscan clones for different
    EVM chains.
    :param network:
    :return:
    """
    match network:
        case SN.ethereum:
            return "https://api.etherscan.io/api"
        case _:
            raise NotImplementedError(f"Network {network} not available through Etherscan")


def get_current_block_number(network: SN) -> int:
    """
    Returns the current block number for a network.  Fetches data from default RPCs and APIs.

    .. note::
        The default RPCs used will likely timeout quickly, but this is called once infrequently so
        timeouts and rate limits shouldn't be an issue.

    :param network: Network to fetch current block for
    :return:
    """
    match network:
        case SN.ethereum | SN.zk_sync_era:
            rpc = os.environ.get("JSON_RPC", default_rpc(network))

            response = requests.post(
                rpc,
                json={"jsonrpc": "2.0", "id": 0, "method": "eth_blockNumber"},
                timeout=30,
            ).json()
            try:
                return int(response["result"], 16)
            except KeyError:
                raise RPCError(f"Error fetching current block number for Ethereum: {response}")

        case SN.starknet:
            rpc = os.environ.get("JSON_RPC", default_rpc(network))

            response = requests.post(
                rpc,
                json={"id": 1, "jsonrpc": "2.0", "method": "starknet_blockNumber"},
                timeout=30,
            ).json()
            try:
                return int(response["result"])
            except KeyError:
                raise RPCError(f"Error fetching current block number for Starknet: {response}")

        case _:
            raise NotImplementedError(f"Network {network} not implemented")


def block_identifier_to_block(
    block: BlockIdentifier,
    network: SN,
) -> int:
    """
    Converts block identifiers to block numbers.  If block is an integer, returns the integer.  If block is a string,
    returns the block number for the string identifier.  Will attempt to query the supplied network for additional
    block data if the block identifier is a string literal.

    :param block:
    :param network:
    :return:
    """
    if isinstance(block, int):
        return block

    match block:
        case "latest":
            return get_current_block_number(network)
        case "pending":
            return get_current_block_number(network) + 1
        case "earliest":
            return 0
        case "safe":
            raise NotImplementedError(
                "Generalized Safe block not implemented.  Compute safe block manually and use " "integer block numbers"
            )
        case "finalized":
            raise NotImplementedError(
                "Generalized Finalized block not implemented. Compute finalized block manually and use "
                "integer block numbers"
            )
        case _:
            raise ValueError(f"Invalid block identifier: {block}")


class GracefulKiller:
    """
    handle sigint / sigterm gracefully
    taken from https://stackoverflow.com/a/31464349
    """

    signal_names = {signal.SIGINT: "SIGINT", signal.SIGTERM: "SIGTERM"}

    def __init__(self, console: Console):
        self.kill_now = False
        self.console = console
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signum, frame):  # pylint: disable=unused-argument
        """Prints out a message and sets kill_now to True"""
        self.console.print("[green]Received Shutdown Signal.  Finishing Backfill...")
        self.kill_now = True
