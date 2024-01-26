import logging
from typing import Any

import requests
from rich.progress import Progress
from sqlalchemy import Connection, Engine

from python_eth_amm.abi_decoder import DecodingDispatcher
from python_eth_amm.abi_decoder.utils import signature_to_name
from python_eth_amm.backfill.planner import BackfillPlan
from python_eth_amm.backfill.utils import GracefulKiller, etherscan_base_url
from python_eth_amm.database.models import transaction_model_for_network
from python_eth_amm.database.models.ethereum import Transaction as EthereumTransaction
from python_eth_amm.database.writers.model_writer import ModelWriter
from python_eth_amm.database.writers.utils import db_encode_dict, db_encode_hex
from python_eth_amm.exceptions import BackfillError
from python_eth_amm.types.backfill import SupportedNetwork

package_logger = logging.getLogger("python_eth_amm")
backfill_logger = package_logger.getChild("backfill")
logger = backfill_logger.getChild("etherscan")


def _validate_api_key(key: str | None) -> str:
    if key is None:
        raise BackfillError("API key is required for Etherscan backfill")

    if len(key) != 34:
        raise BackfillError(
            "Etherscan API keys are 34 characters long.  Double check --api-key"
        )

    return key


def handle_etherscan_error(response: requests.Response) -> Any:
    """
    Check status codes and Response parameters before returning the json result from API
    :param response: requests.Response object
    :return: respone.json()['result']
    """
    match response.status_code:
        case 200:
            response_data = response.json()
            if response_data.get("status") == "1":
                return response_data["result"]

            # Error Handling Section
            match response_data["message"]:
                case "OK-Missing/Invalid API Key, rate limit of 1/5sec applied":
                    raise BackfillError("Invalid Etherscan API Key")
                case _:
                    raise BackfillError("Unhandled Etherscan Error: " + response_data)
        case _:
            raise BackfillError(
                f"Unexpected Response Status Code ({response.status_code}) for Etherscan API. "
                f"Response Data: {response}"
            )


def etherscan_backfill_txs(
    backfill_plan: BackfillPlan,
    db_engine: Engine | Connection,
    api_key: str | None,
    progress: Progress,
):
    """
    Backfills Transactions from Etherscan API

    :param backfill_plan:
    :param db_engine:
    :param api_key:
    :param progress:
    :return:
    """

    valid_api_key = _validate_api_key(api_key)
    writer = ModelWriter(
        db_engine=db_engine,
        db_model=transaction_model_for_network(backfill_plan.network),
    )

    if backfill_plan.filter_params is None:
        # Proxy-calling eth_getBlockByNumber()
        raise NotImplementedError()

    if "for_address" in backfill_plan.filter_params.keys():
        # Backfilling Transactions From Etherscan Account API
        backfill_txns_from_account_api(
            backfill_plan=backfill_plan,
            writer=writer,
            api_key=valid_api_key,
            progress=progress,
        )
    else:
        raise BackfillError(
            "Etherscan transaction backfill only supports --for-address filters or no filters"
        )


# pylint: disable=too-many-locals
def backfill_txns_from_account_api(
    backfill_plan: BackfillPlan,
    writer: ModelWriter,
    api_key: str,
    progress: Progress,
):
    """
    Backfills Transactions from Etherscan Account API.   Requires a for-address filter to be specifed

    :param backfill_plan:
    :param writer:
    :param api_key:
    :param progress:
    :return:
    """
    page_size = backfill_plan.metadata_dict.get("page_size", 1_000)
    backfill_task = progress.add_task(
        description="Backfill Blocks",
        total=backfill_plan.total_blocks(),
        searching_block=backfill_plan.range_plan.backfill_ranges[0][0],
    )

    killer = GracefulKiller(console=progress.console)

    for range_idx, (start_block, end_block) in enumerate(
        backfill_plan.range_plan.backfill_ranges
    ):
        search_block = start_block

        while True:
            if killer.kill_now:
                progress.console.print(
                    f"[red]Processing Terminated Backfill up to Block {search_block}"
                )
                backfill_plan.process_failed_backfill(search_block)
                break

            response = requests.get(
                etherscan_base_url(backfill_plan.network),
                params={  # type: ignore
                    "module": "account",
                    "action": "txlist",
                    "address": backfill_plan.get_filter_param("for_address"),
                    "startblock": search_block,
                    "endblock": end_block,
                    "page": 1,
                    "offset": page_size,
                    "sort": "asc",
                    "apikey": api_key,
                },
                timeout=300,
            )
            raw_tx_batch = handle_etherscan_error(response)

            logger.debug(
                f"Queried {len(raw_tx_batch)} Transactions from Blocks {raw_tx_batch[0]['blockNumber']} "
                f"- {raw_tx_batch[-1]['blockNumber']}"
            )

            break_loop = len(raw_tx_batch) < page_size

            parsed_transactions = _parse_etherscan_transactions(
                network=backfill_plan.network,
                tx_batch=raw_tx_batch if break_loop else _trim_last_block(raw_tx_batch),
                db_dialect=writer.db_dialect,
                abi_decoder=backfill_plan.decoder,
            )
            writer.add_backfill_data(parsed_transactions)

            if break_loop:
                logger.info(
                    f"Finished Writing Final Batch of {len(raw_tx_batch)} Transactions.  Breaking Loop..."
                )
                break

            blocks_in_batch = int(
                parsed_transactions[-1].block_number
                - parsed_transactions[0].block_number
            )
            search_block = int(parsed_transactions[-1].block_number) + 1

            progress.update(
                backfill_task, advance=blocks_in_batch, searching_block=search_block
            )

        if killer.kill_now:
            break
        backfill_plan.range_plan.mark_finalized(range_idx)

    progress.console.print(
        "[green]Finished Backfilling Transactions. Saving Cached Models to DB..."
    )
    writer.finish()


def _trim_last_block(tx_batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
    last_block = tx_batch[-1]["blockNumber"]
    slice_index = -1
    while True:
        slice_index -= 1
        current_block = tx_batch[slice_index]["blockNumber"]
        if current_block != last_block:
            return tx_batch[: slice_index + 1]


# def etherscan_backfill_blocks(
#     backfill_plan: BackfillPlan,
#     db_engine: Engine | Connection,
#     api_key: str | None,
#     progress: Progress,
# ):
#     """
#     Backfills blocks through etherscan RPC Proxy API
#
#     :param backfill_plan:
#     :param db_engine:
#     :param api_key:
#     :param progress:
#     :return:
#     """
#     valid_api_key = _validate_api_key(api_key)
#     save_txns: bool = backfill_plan.backfill_type == BackfillDataType.transactions
#
#     block_writer = ModelWriter(
#         db_engine=db_engine, db_model=block_model_for_network(backfill_plan.network)
#     )
#     transaction_writer = (
#         ModelWriter(
#             db_engine=db_engine,
#             db_model=transaction_model_for_network(backfill_plan.network),
#         )
#         if save_txns
#         else None
#     )
#
#     backfill_task = progress.add_task(
#         description="Backfill Blocks",
#         total=backfill_plan.total_blocks(),
#         searching_block=backfill_plan.range_plan.backfill_ranges[0][0],
#     )
#
#     for range_idx, (start_block, end_block) in enumerate(
#         backfill_plan.range_plan.backfill_ranges
#     ):
#         for block in range(start_block, end_block):
#             progress.update(
#                 backfill_task,
#                 advance=1,
#                 searching_block=block,
#             )
#
#             response = requests.get(
#                 etherscan_base_url(backfill_plan.network),
#                 params=[
#                     ("module", "proxy"),
#                     ("action", "eth_getBlockByNumber"),
#                     ("tag", str(hex(block))),
#                     ("boolean", save_txns),
#                     ("apikey", valid_api_key),
#                 ],
#                 timeout=120,
#             )
#
#             parsed_block, parsed_txns = rpc_response_to_block_model(
#                 block=handle_etherscan_error(response),
#                 network=backfill_plan.network,
#                 db_dialect=block_writer.db_dialect,
#                 abi_decoder=backfill_plan.decoder,
#             )
#             block_writer.add_backfill_data([parsed_block])
#             if transaction_writer:
#                 transaction_writer.add_backfill_data(parsed_txns)


def _parse_etherscan_transactions(
    network: SupportedNetwork,
    tx_batch: list[dict[str, Any]],
    db_dialect: str,
    abi_decoder: DecodingDispatcher,
) -> list[EthereumTransaction]:
    output_models = []
    for tx_data in tx_batch:
        decoded_input = abi_decoder.decode_function(tx_data["input"])
        if decoded_input:
            function_name = signature_to_name(decoded_input.function_signature)
        else:
            etherscan_class = tx_data.get("functionName")
            if etherscan_class:
                function_name = signature_to_name(etherscan_class)
            else:
                function_name = None

        encoded_tx_data = {
            "transaction_hash": db_encode_hex(tx_data["hash"], db_dialect),
            "block_number": int(tx_data["blockNumber"]),
            "transaction_index": int(tx_data["transactionIndex"]),
            "timestamp": int(tx_data["timeStamp"]),
            "nonce": int(tx_data["nonce"]),
            "from_address": db_encode_hex(tx_data["from"], db_dialect),
            "to_address": db_encode_hex(tx_data["to"], db_dialect),
            "input": db_encode_hex(tx_data["input"], db_dialect),
            "value": int(tx_data["value"]),
            "error": bool(tx_data["isError"]),
            "gas_price": int(tx_data["gasPrice"]),
            "gas_used": int(tx_data["gasUsed"]),
            "decoded_signature": function_name,
            "decoded_input": db_encode_dict(decoded_input.decoded_input)
            if decoded_input
            else None,
        }

        match network:
            case SupportedNetwork.ethereum:
                output_models.append(EthereumTransaction(**encoded_tx_data))
            case _:
                raise NotImplementedError()
    return output_models
