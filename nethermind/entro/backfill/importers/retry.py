import asyncio
import logging
import time
from typing import Any, Callable

from nethermind.entro.exceptions import BackfillError
from nethermind.idealis.exceptions import RPCRateLimitError

root_logger = logging.getLogger("nethermind")
logger = root_logger.getChild("entro").getChild("importer")


def retry_async_run(func: Callable[..., Any], **kwargs: Any) -> Any:
    """
    Run an async function, retrying up to 5 times until it succeeds, backing off
    """

    max_concurrency = kwargs.pop("max_concurrency", 10)

    for retry_count in range(5):
        if retry_count > 0:
            logger.info(f"Executing {func.__name__}() -- Retry {retry_count}")
        try:
            result = asyncio.run(func(max_concurrency=max_concurrency, **kwargs))
            if retry_count > 0:
                logger.info("Successful Retry... Continuing to next Data Batch")
            return result

        except RPCRateLimitError:
            logger.warning(
                f"Rate Limit Error with Concurrency {max_concurrency}... retrying in {30 * (retry_count + 1)} seconds"
            )
            time.sleep((retry_count + 1) * 30)
            max_concurrency = max(max_concurrency // 2, 1)

        except Exception as e:
            raise BackfillError(f"Unhandled Error executing {func.__name__}") from e

    raise BackfillError(f"Failed to execute {func.__name__} after 5 retries...")
