import asyncio
import logging
import time
from typing import Any, Literal

import aiohttp
from aiohttp.client_exceptions import (
    ClientConnectionError,
    ContentTypeError,
    ServerDisconnectedError,
)

from nethermind.entro.exceptions import (
    BackfillError,
    BackfillHostError,
    BackfillRateLimitError,
)

root_logger = logging.getLogger("nethermind")
logger = root_logger.getChild("entro").getChild("backfill").getChild("async")

DEFAULT_HEADERS = {"Content-Type": "application/json"}

# pylint: disable=raise-missing-from


def retry_enabled_batch_post(
    request_objects: list[dict[str, Any]],
    json_rpc: str,
    max_concurrency: int,
    request_headers: dict[str, str] | None = None,
) -> list[Any] | Literal["failed"]:
    """
    Retry enabled batch post request.  Retries on rate limit errors, host errors, and server disconnect errors.
    If the retry count exceeds 4, the query is considered failed and the function returns "failed"

    :param request_objects:
    :param json_rpc:
    :param max_concurrency:
    :param request_headers:
    :return:
    """
    for retry in range(5):
        if retry == 4:
            logger.error("4th Retry for Same block range. Exiting out of failed backfill")
            return "failed"

        response = asyncio.run(
            batch_post_request(
                request_objects=request_objects,
                host_address=json_rpc,
                request_headers=request_headers,
                max_concurrency=max_concurrency,
            )
        )

        if any(isinstance(item, BackfillRateLimitError) for item in response):
            retry_secs = 30 * (retry + 1)
            logger.error(
                f"RPC Rate Limits initialized...  Retrying in {retry_secs} seconds... "
                f"(Retry Count:  {retry + 1}\tConcurrency: {max_concurrency})"
            )
            time.sleep(retry_secs)
            continue

        if any(isinstance(item, BackfillHostError) for item in response):
            logger.error(f"Host Error Occurred...  Retrying in 120 seconds...   (Retry Count: {retry + 1})")
            time.sleep(120)
            continue

        if any(isinstance(item, ServerDisconnectedError) for item in response):
            logger.error(f"Server Disconnect Error Occurred...  Retrying in 120 seconds...  (Retry Count: {retry + 1})")
            time.sleep(120)
            continue

        if any(isinstance(item, (ClientConnectionError, TimeoutError)) for item in response):
            logger.error(
                f"Could Not Connect to RPC {json_rpc}...  Potential IP Blacklist or Network Error. Exiting Backfill..."
            )
            return "failed"

        if any(isinstance(item, Exception) for item in response):
            for row in response:
                if isinstance(row, Exception):
                    logger.error(f"Unexpected Error Type: {type(row)}({row})")
                    return "failed"

        return response

    return "failed"


def _handle_rpc_error(response_json: dict[str, Any]) -> None:
    if "error" in response_json.keys():
        logger.debug(f"Error in RPC response: {response_json}")
        raise BackfillError("Error in RPC response: " + response_json["error"]["message"])


async def batch_post_request(
    request_objects: list[dict[str, Any]],
    host_address: str,
    request_headers: dict[str, str] | None = None,
    max_concurrency: int = 20,
):
    """
    Batch Post a host address.  Used for batch JSON RPC Queries

    :param request_objects:
        List[dict].  Each dictionary is passed to the json field of the POST request.  Number of requests in batch
        determined by length of this list
    :param host_address: host address
    :param request_headers: headers for request.   Default: {"Content-Type": "application/json"}
    :param max_concurrency: Max number of concurrent connections.   Default: 20
    :return: List[response.json() ...]
    """
    connector = aiohttp.TCPConnector(limit=max_concurrency)
    logger.debug(f"Sending {len(request_objects)} requests to {host_address}")
    aiohttp_timeout = aiohttp.ClientTimeout(total=120)

    async with aiohttp.ClientSession(
        headers=request_headers or DEFAULT_HEADERS,
        connector=connector,
        timeout=aiohttp_timeout,
    ) as session:

        async def query_rpc(request: dict[str, Any]):
            async with session.post(host_address, json=request) as response:
                try:
                    response_json = await response.json()
                except ContentTypeError:
                    match response.status:
                        case 1015 | 429:
                            raise BackfillRateLimitError("JSON RPC Server Initializing Rate Limits")
                        case 500 | 502 | 503 | 504:
                            raise BackfillHostError("Internal Server Error")

                        case _:
                            logger.error(f"\n{'-' * 40}")
                            logger.error("Unexpected Error in response for request: ", request)
                            logger.error(f"Error Code: {response.status}")
                            logger.error(await response.text())
                            logger.error("-" * 40)
                            raise BackfillError("Unexpected Content Type AioHttp Error")
                except TimeoutError:
                    raise TimeoutError(f"Timeout Error for RPC Host {host_address}")
                _handle_rpc_error(response_json)
                return response_json["result"]

        return [
            *await asyncio.gather(
                *[query_rpc(request_obj) for request_obj in request_objects],
                return_exceptions=True,
            )
        ]


async def batch_get_request(
    request_objects: list[dict[str, Any]],
    host_address: str,
    request_headers: dict[str, str] | None = None,
    max_concurrency: int = 20,
):
    """
    Batch get request an endpoint.

    >>> requests = [
    ...     {"page_number": 12, "from_address": "0x..."},
    ...     {"page_number": 13, "from_address": "0x..."}
    ... ]
    ... response_json = batch_get_request(
    ...     request_objects=requests,
    ...     host_address="api.etherscan.io"
    ... )
    '[{<page 12 response>}, {<page 13 response>}]'

    :param request_objects:
        List of dictionaries with query parameters. The number of requests in batch is determined by the length of
        this list.  The values inside each dictionary are passed to the parameters of the get response
    :param host_address: host address
    :param request_headers: headers for request.   Default: {"Content-Type": "application/json"}
    :param max_concurrency: Max number of concurrent connections.   Default: 20
    :return: List[response.json() ...]
    """
    connector = aiohttp.TCPConnector(limit=max_concurrency)

    async with aiohttp.ClientSession(
        headers=request_headers or DEFAULT_HEADERS,
        connector=connector,
    ) as session:

        async def get_request(request: dict[str, Any]):
            async with session.get(host_address, params=request) as response:
                try:
                    response_json = await response.json()
                except ContentTypeError:
                    match response.status:
                        case 1015, 429:
                            raise BackfillRateLimitError("Server Initializing Rate Limits")
                        case 500, 502, 503, 504:
                            raise BackfillHostError("Internal Server Error")
                        case _:
                            logger.error(f"\n{'-' * 40}")
                            logger.error("Unexpected Error in response for request: ", request)
                            logger.error("Error Code: ", response.status)
                            logger.error(await response.text())
                            logger.error("-" * 40)
                            raise BackfillError("Unexpected Error")

                return response_json

        return [
            *await asyncio.gather(
                *[get_request(req_obj) for req_obj in request_objects],
                return_exceptions=True,
            )
        ]
