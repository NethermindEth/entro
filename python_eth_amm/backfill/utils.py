import os
import signal
from typing import Any

import requests
from rich.console import Console

from python_eth_amm.abi_decoder import DecodingDispatcher
from python_eth_amm.database.models import (
    AbstractBlock,
    AbstractTrace,
    AbstractTransaction,
)
from python_eth_amm.database.models.ethereum import Block as EthereumBlock
from python_eth_amm.database.models.ethereum import Trace as EthereumTrace
from python_eth_amm.database.models.ethereum import Transaction as EthereumTransaction
from python_eth_amm.database.models.polygon import ZKEVMBlock, ZKEVMTransaction
from python_eth_amm.database.models.zk_sync import EraBlock as ZKSyncBlock
from python_eth_amm.database.models.zk_sync import EraTransaction as ZKSyncTransaction
from python_eth_amm.database.writers.utils import db_encode_dict, db_encode_hex
from python_eth_amm.types import BlockIdentifier
from python_eth_amm.types.backfill import SupportedNetwork as SN
from python_eth_amm.utils import maybe_hex_to_int, to_bytes


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
        case SN.polygon_zk_evm:
            return "https://zkevm-rpc.com/"
        case SN.zk_sync_era:
            return "https://mainnet.era.zksync.io"
        case SN.starknet:
            return "https://starknet-mainnet.public.blastapi.io"
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
            raise NotImplementedError(
                f"Network {network} not available through Etherscan"
            )


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
        case SN.ethereum | SN.polygon_zk_evm | SN.zk_sync_era:
            rpc = os.environ.get("JSON_RPC", default_rpc(network))

            response = requests.post(
                rpc,
                json={"jsonrpc": "2.0", "id": 0, "method": "eth_blockNumber"},
                timeout=30,
            ).json()
            return int(response["result"], 16)

        case SN.starknet:
            rpc = os.environ.get("JSON_RPC", default_rpc(network))

            response = requests.post(
                rpc,
                json={"id": 1, "jsonrpc": "2.0", "method": "starknet_blockNumber"},
                timeout=30,
            ).json()
            return int(response["result"])

        case SN.zk_sync_lite:
            response = requests.get(
                "https://api.zksync.io/api/v0.1/blocks", params={"limit": 1}, timeout=30
            ).json()
            return int(response[0]["block_number"])

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
                "Generalized Safe block not implemented.  Compute safe block manually and use "
                "integer block numbers"
            )
        case "finalized":
            raise NotImplementedError(
                "Generaelized Finalized block not implemented. Compute finalized block manually and use "
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


# ------------------------------
# RPC Query Object Parsing
# ------------------------------


def parse_rpc_block_requests(
    block_numbers: list[int] | int, network: SN = SN.ethereum, full_txns: bool = True
) -> list[dict[str, Any]]:
    """
    Parses a list of block numbers into a list of JSON RPC requests for block data.

    :param block_numbers:
    :param network:
    :param full_txns:
    :return:
    """
    if isinstance(block_numbers, int):
        block_numbers = [block_numbers]
    match network:
        case SN.starknet:
            return [
                {
                    "id": number,
                    "jsonrpc": "2.0",
                    "method": "starknet_getBlockWithTxs"
                    if full_txns
                    else "starknet_getBlockWithTxHashes",
                    "params": [{"block_number": number}],
                }
                for number in block_numbers
            ]
        case SN.ethereum | SN.zk_sync_era | SN.polygon_zk_evm:
            return [
                {
                    "id": number,
                    "jsonrpc": "2.0",
                    "method": "eth_getBlockByNumber",
                    "params": [hex(number), full_txns],
                }
                for number in block_numbers
            ]
        case _:
            raise NotImplementedError(
                f"Unsupported Network for JSON-RPC Block Backfills: {network}"
            )


def parse_rpc_receipt_request(
    tx_hashes: str | list[str], network: SN = SN.ethereum
) -> list[dict[str, Any]]:
    """
    Parses a list of transaction hashes into a list of JSON RPC requests for transaction receipts.

    :param tx_hashes:
    :param network:
    :return:
    """
    if isinstance(tx_hashes, str):
        tx_hashes = [tx_hashes]

    match network:
        case SN.starknet:
            raise NotImplementedError("Starknet Tx Receipts not implemented")
        case SN.ethereum | SN.zk_sync_era | SN.polygon_zk_evm:
            return [
                {
                    "id": 0,
                    "jsonrpc": "2.0",
                    "method": "eth_getTransactionReceipt",
                    "params": [tx_hash],
                }
                for tx_hash in tx_hashes
            ]
        case _:
            raise NotImplementedError(
                f"Unsupported Network for JSON-RPC Tx Receipt Backfills: {network}"
            )


def parse_event_request(
    start_block: int,
    end_block: int,
    contract_address: str,
    topics: list[str | list[str]],
    network: SN = SN.ethereum,
) -> dict[str, Any]:
    """
    Parses a request for event logs into a JSON RPC request.

    :param start_block:
    :param end_block:
    :param contract_address:
    :param topics:
    :param network:
    :return:
    """
    match network:
        case SN.starknet:
            raise NotImplementedError("Starknet Event Backfills not implemented")
        case SN.ethereum | SN.zk_sync_era | SN.polygon_zk_evm:
            return {
                "id": 2,
                "jsonrpc": "2.0",
                "method": "eth_getLogs",
                "params": [
                    {
                        "fromBlock": hex(start_block),
                        "toBlock": hex(end_block),
                        "address": contract_address,
                        "topics": topics,
                    }
                ],
            }
        case _:
            raise NotImplementedError(
                f"Unsupported Network for JSON-RPC Event Backfills: {network}"
            )


# ----------------------------------------
# Parsing RPC Responses to DB Models
# ----------------------------------------


def rpc_response_to_trace_model(
    traces: list[dict[str, Any]],
    network: SN,
    db_dialect: str,
    abi_decoder: DecodingDispatcher,
) -> list[AbstractTrace]:
    """
    Parse a trace from a JSON RPC response into a list of Trace objects.
    Will run ABI decoding with the provided DecodingDispatcher, for both the trace input and output

    :param traces:
    :param network:
    :param db_dialect:
    :param abi_decoder:
    :return:
    """
    return_traces: list[AbstractTrace] = []
    for trace in traces:
        decoded_trace = abi_decoder.decode_trace(trace)
        match network:
            case SN.ethereum | SN.zk_sync_era | SN.polygon_zk_evm:
                trace_data = {
                    "transaction_hash": db_encode_hex(
                        trace["transaction_hash"], db_dialect
                    ),
                    "block_number": trace["block_number"],
                    "trace_address": trace["trace_address"],
                    "from_address": db_encode_hex(trace["action"]["from"], db_dialect),
                    "to_address": db_encode_hex(trace["action"]["to"], db_dialect),
                    "input": db_encode_hex(trace["action"]["input"], db_dialect),
                    "gas_used": int(trace["result"]["gasUsed"], 16),
                    "decoded_function": decoded_trace.function_signature
                    if decoded_trace
                    else None,
                    "decoded_input": decoded_trace.decoded_input
                    if decoded_trace
                    else None,
                    "decoded_output": decoded_trace.decoded_output
                    if decoded_trace
                    else None,
                }
            case _:
                raise NotImplementedError(
                    f"Cannot parse RPC Trace Response for network {network}"
                )

        match network:
            case SN.ethereum:
                return_traces.append(EthereumTrace(**trace_data))

            case _:
                raise NotImplementedError(f"Cannot parse Trace for network {network}")

    return return_traces


def rpc_response_to_block_model(
    block: dict[str, Any],
    network: SN,
    db_dialect: str,
    abi_decoder: DecodingDispatcher | None = None,
) -> tuple[AbstractBlock, list[AbstractTransaction], str | None]:
    """
    Parse a block from a JSON RPC response into a Block object and a list of Transaction objects.
    Runs the block through the ABI Decoder if one is provided.

    :param block:
    :param network:  Network to parse RPC response.
    :param db_dialect:
    :param abi_decoder:
    :return: (block, list[transactions], last_tx_in_block)
    """

    tx_count = len(block.get("transactions", []))
    block_number = maybe_hex_to_int(block["number"])
    block_timestamp = maybe_hex_to_int(block["timestamp"])
    match network:
        case SN.ethereum | SN.zk_sync_era | SN.polygon_zk_evm:
            block_data = {
                "block_number": block_number,
                "block_hash": db_encode_hex(block["hash"], db_dialect),
                "parent_hash": db_encode_hex(block["parentHash"], db_dialect),
                "timestamp": block_timestamp,
                "miner": db_encode_hex(block["miner"], db_dialect),
                "difficulty": maybe_hex_to_int(block["difficulty"]),
                "gas_limit": maybe_hex_to_int(block["gasLimit"]),
                "gas_used": maybe_hex_to_int(block["gasUsed"]),
                "extra_data": db_encode_hex(block["extraData"], db_dialect),
                "transaction_count": tx_count,
            }
        case SN.starknet:
            raise NotImplementedError("Starknet Block Parsing not implemented")
        case _:
            raise NotImplementedError(
                f"Cannot parse RPC Block Response for network {network}"
            )

    all_txns = []

    if tx_count > 0 and isinstance(block["transactions"][0], dict):
        if abi_decoder is None:
            abi_decoder = DecodingDispatcher()

        for tx in block["transactions"]:
            decoded_input = abi_decoder.decode_transaction(tx)

            match network:
                case SN.ethereum | SN.zk_sync_era | SN.polygon_zk_evm:
                    all_txns.append(
                        {
                            "transaction_hash": db_encode_hex(tx["hash"], db_dialect),
                            "block_number": block_number,
                            "transaction_index": maybe_hex_to_int(
                                tx["transactionIndex"]
                            ),
                            "timestamp": block_timestamp,
                            "nonce": maybe_hex_to_int(tx["nonce"]),
                            "from_address": db_encode_hex(tx["from"], db_dialect),
                            "to_address": db_encode_hex(tx["to"], db_dialect)
                            if tx["to"]
                            else None,
                            "input": db_encode_hex(tx["input"], db_dialect),
                            "value": maybe_hex_to_int(tx["value"]),
                            "error": None,
                            "gas_price": maybe_hex_to_int(tx["gasPrice"]),
                            "gas_available": maybe_hex_to_int(tx["gas"]),
                            "gas_used": None,
                            "decoded_signature": decoded_input.function_signature
                            if decoded_input
                            else None,
                            "decoded_input": db_encode_dict(decoded_input.decoded_input)
                            if decoded_input
                            else None,
                        }
                    )
                case SN.starknet:
                    raise NotImplementedError(
                        "Starknet Transaction Parsing not implemented"
                    )
                case _:
                    raise NotImplementedError(
                        f"Cannot parse RPC Transaction Response for network {network}"
                    )

    last_tx = block["transactions"][-1] if len(block["transactions"]) > 0 else None
    last_tx_hash: str | None = last_tx["hash"] if isinstance(last_tx, dict) else last_tx

    match network:
        case SN.ethereum:
            return (
                EthereumBlock(**block_data),
                [EthereumTransaction(**tx) for tx in all_txns],
                last_tx_hash,
            )
        case SN.zk_sync_era:
            return (
                ZKSyncBlock(**block_data),
                [ZKSyncTransaction(**tx) for tx in all_txns],
                last_tx_hash,
            )
        case SN.polygon_zk_evm:
            return (
                ZKEVMBlock(**block_data),
                [ZKEVMTransaction(**tx) for tx in all_txns],
                last_tx_hash,
            )
        case _:
            raise NotImplementedError(f"Cannot parse Block for network {network}")


def add_receipt_to_tx_models(
    transactions: list[AbstractTransaction],
    receipt_responses: list[dict[str, Any]],
    strict: bool = False,
) -> list[AbstractTransaction]:
    """
    Adds receipt data to a list of transactions.  Parses in gas_used and error fields.

    :param transactions:
    :param receipt_responses:
    :param strict:
    :return:
    """

    receipt_dict = {
        to_bytes(receipt["transactionHash"]): receipt for receipt in receipt_responses
    }

    for transaction in transactions:
        tx_hash = to_bytes(transaction.transaction_hash)
        if tx_hash in receipt_dict:
            receipt = receipt_dict[tx_hash]
            transaction.error = (
                None if receipt["status"] == "0x0" else receipt["status"]
            )
            transaction.gas_used = maybe_hex_to_int(receipt["gasUsed"])
        elif strict:
            raise ValueError(f"Receipt for transaction 0x{tx_hash.hex()} not found")
        else:
            continue

    return transactions
