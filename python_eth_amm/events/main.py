from logging import Logger
from typing import List, Optional, Type

from eth_typing import ChecksumAddress
from sqlalchemy.orm import Session
from tqdm import tqdm
from web3.eth import Contract
from web3.types import LogReceipt

from .db import EventBase


def _get_last_backfilled_block(
    db_session: Session, contract_address: ChecksumAddress, db_model: Type[EventBase]
) -> Optional[int]:
    last_db_block = (
        db_session.query(db_model)
        .filter(db_model.contract_address == contract_address)
        .order_by(db_model.block_number.desc())
        .limit(1)
        .scalar()
    )
    if last_db_block:
        return last_db_block.block_number
    return None


def query_events_from_db(
    db_session: Session,
    db_model: Type[EventBase],
    to_block: int,
    from_block: Optional[int] = 0,
    contract_address: Optional[ChecksumAddress] = None,
) -> List[Type[EventBase]]:
    """
    Retrieves events from the database using a Sqlalchemy model and a database session.

    :param db_session: sqlalchemy session object
    :param db_model: sqlalchemy model object
    :param to_block: Inclusive end block to query
    :param from_block: Inclusive start block to query.  Defaults to 0.
    :param contract_address: Contract address to filter events.  For Transfer events, this is the token address.
    """

    if contract_address is None:
        query = db_session.query(db_model).filter(
            db_model.block_number >= from_block, db_model.block_number <= to_block
        )
    else:
        query = db_session.query(db_model).filter(
            db_model.contract_address == str(contract_address),
            db_model.block_number >= from_block,
            db_model.block_number <= to_block,
        )

    return query.order_by(db_model.block_number, db_model.log_index).all()


def fetch_events_from_chain(
    contract: Contract,
    event_name: str,
    from_block: int,
    to_block: Optional[int] = None,
    chunk_size: Optional[int] = 10_000,
) -> List[LogReceipt]:
    """
    Fetch Event Data Between Two Blocks.

    .. warning::
        This can be a very slow process if querying frequent events like ERC20 Transfers.  If an RPC error occurs in
        the middle, all the progress is lost.  When querying large numbers of events, it is reccomended to add
        database models and cache the intermediary results using :func:`backfill_events` instead.

    :param contract: web3.eth.contract object that events are fetched from
    :param event_name: Name of the Event to backfill
    :param from_block:
        First block to query.  If from_block is none, it will first try to get the last backfilled block from the
        db_model in the database.  If that doesn't exist, it will then use 0.  Blindly Using 0 as a start block is
        inefficient, and if there are no existing backfilled records in the database, use the contract initialization
        block is possible

    :param to_block:
        Inclusive end block to query.  If left as none, uses current web3.eth.block_number

    :param chunk_size:
        Number of blocks to query at a time.  For frequent events like Transfer or Approve, this should be 1k-5k.
        For semi-frequent events like Swaps, 10k usually works well.  Infrequent events on smaller contracts
        can be queried in 100k block batches.
    """

    if to_block is None:
        to_block = contract.w3.eth.block_number

    all_events = []

    for block_num in tqdm(
        range(from_block, to_block, chunk_size), f"Backfilling {event_name} Events"
    ):
        all_events.extend(
            contract.events[event_name].get_logs(
                fromBlock=block_num, toBlock=block_num + chunk_size - 1
            )
        )
    return all_events


def backfill_events(
    contract: Contract,
    event_name: str,
    db_session: Session,
    db_model: Type[EventBase],
    model_parsing_func: callable,
    from_block: int,
    to_block: int,
    logger: Logger,
    chunk_size: Optional[int] = 10_000,
):
    """
    Backfills events for a contract between two blocks.  First checks the database session for events, and if they
    do not exist, runs an event backfill before returning the data.
    :param contract: web3.eth.contract object that events are fetched from
    :param event_name: name of Event
    :param db_session: sqlalchemy session object
    :param db_model: sqlalchemy model object
    :param model_parsing_func: function to parse event data into a sqlalchemy model
    :param from_block: Inclusive starting block for event query
    :param to_block: Exclusive end block for event query
    :param logger: Logger object
    :param chunk_size: Number of blocks to backfill at a time if events are not found in the database
    """
    logger.info(f"Backfilling {event_name} Events from {from_block} to {to_block}")
    last_db_block = _get_last_backfilled_block(
        db_session=db_session,
        db_model=db_model,
        contract_address=contract.address,
    )
    logger.debug(f"Last block in DB: {last_db_block}")
    if last_db_block and to_block <= last_db_block:
        logger.info("Events already saved to DB, loading from sqlalchemy")
        return

    if last_db_block:
        from_block = last_db_block + 1

    for start_block in tqdm(
        range(from_block, to_block, chunk_size), desc=f"Backfilling {event_name} Events"
    ):
        events = contract.events[event_name].get_logs(
            fromBlock=start_block,
            toBlock=min(start_block + chunk_size - 1, to_block - 1),
        )

        db_session.bulk_save_objects(
            [model_parsing_func(data=event, event_name=event_name) for event in events]
        )
        db_session.commit()
