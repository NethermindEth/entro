import logging

from rich.progress import Progress
from sqlalchemy.orm import Session

from python_eth_amm.addresses import UNISWAP_V2_FACTORY, UNISWAP_V3_FACTORY

from ..cli.utils import progress_defaults
from ..types.backfill import BackfillDataType, SupportedNetwork
from .json_rpc import cli_get_logs
from .planner import BackfillPlan

package_logger = logging.getLogger("python_eth_amm")
backfill_logger = package_logger.getChild("backfill")
logger = backfill_logger.getChild("prices")


def download_pool_creations(
    db_session: Session,
    json_rpc: str,
):
    """
    Downloads pool creations from the Ethereum blockchain and saves them to the database.

    :param db_session:
    :param json_rpc:

    :return:
    """
    shared_params = {
        "batch_size": 100_000,
    }
    uniswap_v3_backfill = BackfillPlan.generate(
        db_session=db_session,
        network=SupportedNetwork.ethereum,
        start_block=12369621,
        end_block="latest",
        backfill_type=BackfillDataType.events,
        decode_abis=["UniswapV3Factory"],
        contract_address=UNISWAP_V3_FACTORY,
        event_names=["PoolCreated"],
        **shared_params,
    )
    uniswap_v2_backfill = BackfillPlan.generate(
        db_session=db_session,
        network=SupportedNetwork.ethereum,
        start_block=10000835,
        end_block="latest",
        backfill_type=BackfillDataType.events,
        decode_abis=["UniswapV2Factory"],
        contract_address=UNISWAP_V2_FACTORY,
        event_names=["PairCreated"],
        **shared_params,
    )

    if uniswap_v3_backfill is None or uniswap_v2_backfill is None:
        logger.error("Could not generate backfill plan for pool creations")
        return

    with Progress(*progress_defaults) as progress:
        cli_get_logs(
            uniswap_v3_backfill,
            db_engine=db_session.get_bind(),
            json_rpc=json_rpc,
            progress=progress,
        )
        cli_get_logs(
            uniswap_v2_backfill,
            db_engine=db_session.get_bind(),
            json_rpc=json_rpc,
            progress=progress,
        )
