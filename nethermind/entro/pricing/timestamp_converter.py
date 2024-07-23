import asyncio
import os
from bisect import bisect_right
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Sequence

from aiohttp import ClientSession
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from nethermind.entro.backfill.async_rpc import retry_enabled_batch_post
from nethermind.entro.backfill.utils import (
    block_identifier_to_block,
    default_rpc,
    get_current_block_number,
)
from nethermind.entro.database.models import AbstractBlock, block_model_for_network
from nethermind.entro.database.readers.internal import (
    first_block_timestamp,
    get_block_timestamps,
)
from nethermind.entro.database.writers.internal import write_block_timestamps
from nethermind.entro.exceptions import BackfillError
from nethermind.entro.types import BlockIdentifier
from nethermind.entro.types.backfill import (
    BlockProtocol,
    BlockTimestamp,
    SupportedNetwork,
)


def get_blocks_for_network(
    block_numbers: list[int],
    json_rpc: str,
    network: SupportedNetwork,
) -> Sequence[BlockProtocol]:
    """
    Given a network and a sequence of block numbers, returns the block dataclasses for the provided network
    """

    from nethermind.idealis.rpc.starknet.core import get_blocks

    async def _get_blocks() -> Sequence[BlockProtocol]:
        client_session = ClientSession()
        match network:
            case SupportedNetwork.starknet:
                return await get_blocks(block_numbers, json_rpc, client_session)
            case _:
                raise ValueError(f"Unsupported Network: {network}")

    return asyncio.run(_get_blocks())


def _default_resolution(network: SupportedNetwork) -> int:
    "Default block resolution.  Networks with faster block times will have larger block resolutions"
    match network:
        case SupportedNetwork.ethereum:
            return 10_000
        case SupportedNetwork.zk_sync_era:
            return 20_000
        case SupportedNetwork.starknet:
            return 100
        case _:
            raise ValueError(f"Unsupported Network: {network}")


class TimestampConverter:
    """
    Class to convert between block numbers and datetimes.
    """

    timestamp_data: list[BlockTimestamp] = []
    """
        List of BlockTimestamps.  This is the source of truth for block to datetime conversions.
        
        If db_session is not None, this will be populated from the DB.  Otherwise, it will be populated from a
        cached json file in the CWD.
        
        BlockTimestamps are ordered by block number, and the block number is guaranteed to be a multiple of
        timestamp_resolution.  When performing conversions, array bisection is used to find the closest blocks
    """

    last_update_block: int
    """
        Block number of the last block that was used to update the timestamp_data list.  This is used to determine
        if the timestamp_data list needs to be updated.
    """

    timestamp_resolution: int = 10_000
    """ 
        Resolution of timestamps.  Default is 10k, which gives a block to datetime conversion accuracy 
        of +- 10 mins and backfills all data in 1 or 2 minutes.
    """

    network: SupportedNetwork = SupportedNetwork.ethereum
    """ 
        Network to convert timestamps for.  Defaults to Ethereum Mainnet 
    """

    db_session: Session | None
    """ 
        DB Session to use when pulling from DB. If None, wont interact with DB and will cache timestamps 
        to a csv file in the CWD instead.
    """

    def __init__(
        self,
        network: SupportedNetwork,
        db_url: str | None = None,
        resolution: int | None = None,
        json_rpc: str | None = None,
    ):
        self.network = network
        self.timestamp_resolution = resolution or _default_resolution(network)

        if json_rpc:
            os.environ["JSON_RPC"] = json_rpc
            self.json_rpc = json_rpc
        else:
            self.json_rpc = default_rpc(network)

        self.db_session = sessionmaker(create_engine(db_url))() if db_url else None

        self.timestamp_data = get_block_timestamps(db_session=self.db_session, network=network, resolution=resolution)

        self.update_timestamps()

    def update_timestamps(self):
        """
        Updates the timestamp_data list with the latest block timestamps.  If db_session is not None, this will
        update the DB as well.

        :return:
        """
        current_block = get_current_block_number(self.network)
        block_ranges = set(range(0, current_block, self.timestamp_resolution))
        existing_blocks = {ts.block_number for ts in self.timestamp_data}
        blocks_to_query = list(block_ranges - existing_blocks)

        if not blocks_to_query:
            return

        new_timestamps = self.get_timestamps_from_rpc(blocks_to_query)

        self.timestamp_data.extend(new_timestamps)
        self.timestamp_data.sort(key=lambda x: x.block_number)
        self.last_update_block = current_block

    def get_timestamps_from_rpc(self, blocks: list[int]) -> list[BlockTimestamp]:
        """
        Gets block timestamps from the RPC for a given list of blocks, and saves block models to the database

        :param blocks:
        :return:
        """

        new_block_dataclasses = get_blocks_for_network(
            block_numbers=blocks,
            json_rpc=self.json_rpc,
            network=self.network,
        )

        if self.db_session:
            # Convert dataclasses to models & Save to DB
            # TODO: handle this for DB caching of timestamps
            pass

        block_timestamps = [
            BlockTimestamp(
                block_number=block.block_number,
                timestamp=(
                    datetime.fromtimestamp(block.timestamp, tz=timezone.utc)
                    if block.block_number != 0
                    else first_block_timestamp(self.network)
                ),
            )
            for block in new_block_dataclasses
        ]

        if self.db_session is None:
            # Dont save block dataclasses to DB, save BlockTimestamp dataclasses to disk
            write_block_timestamps(block_timestamps, self.network)

        return block_timestamps

    def block_to_datetime(self, block_number: int) -> datetime:
        """
        Converts a block number to an approximate   The accuracy of this method is determined the
        timestamp_resolution parameter when initializing an oracle.  By default, this value is 10k, which gives
        the block to datetime conversion an accuracy of += 10 mins.

        :param block_number: Block number to convert to datetime
        :return: datetime object in UTC timezone
        """
        if block_number >= self.last_update_block:
            self.update_timestamps()

        floor_num = block_number // self.timestamp_resolution

        if block_number % self.timestamp_resolution == 0:
            return self.timestamp_data[floor_num].timestamp

        lower, upper = (
            self.timestamp_data[floor_num],
            self.timestamp_data[floor_num + 1],
        )
        block_time = (upper.timestamp - lower.timestamp) / self.timestamp_resolution

        return lower.timestamp + ((block_number - lower.block_number) * block_time)

    def datetime_to_block(self, dt: datetime | date) -> int:
        """
        Converts a datetime object to a block number.  Just like block_to_datetime, the accuracy of this method is
        determined by the timestamp_resolution parameter when initializing an oracle.  With the default value of 10k,
        the prescision of this method is +- 50 blocks

        :param dt:
            Date to convert to approximate block number.  If a date object is passed, it will get the block at
            UTC midnight of that date.
        :return:
        """
        # isinstance() was failing here, so using type() instead and disabling warnings
        # pylint: disable=unidiomatic-typecheck
        if type(dt) == date:
            dt = datetime(dt.year, dt.month, dt.day, 0, 0, 0, tzinfo=timezone.utc)
        # pylint: enable=unidiomatic-typecheck

        elif dt.tzinfo is None:  # type: ignore[union-attr]
            dt.replace(tzinfo=timezone.utc)  # type: ignore[call-arg]

        timestamp_index = bisect_right(self.timestamp_data, dt, key=lambda x: x.timestamp)

        lower = self.timestamp_data[timestamp_index - 1]
        upper = self.timestamp_data[timestamp_index]

        block_time = (upper.timestamp - lower.timestamp) / self.timestamp_resolution

        return lower.block_number + int((dt - lower.timestamp) / block_time)

    def process_range(
        self,
        start: BlockIdentifier | date | datetime,
        end: BlockIdentifier | date | datetime,
    ) -> tuple[int, int]:
        """
        Processes a range of blocks or datetimes into a start and end block number.  If a datetime is passed, it will
        be converted to a block number using the timestamp_converter.  If a block number is passed, it will be
        returned as is.

        :param start:
        :param end:

        :return: (start_block, end_block)
        """

        if isinstance(start, (date, datetime)):
            start_block = self.datetime_to_block(start)
        elif isinstance(start, BlockIdentifier):  # type: ignore
            start_block = block_identifier_to_block(start, self.network)
        else:
            raise ValueError(f"Invalid Start Parameter: {start}")

        if isinstance(end, (date, datetime)):
            end_block = self.datetime_to_block(end)
        elif isinstance(end, BlockIdentifier):  # type: ignore
            end_block = block_identifier_to_block(end, self.network)
        else:
            raise ValueError(f"Invalid End Parameter: {end}")

        return start_block, end_block
