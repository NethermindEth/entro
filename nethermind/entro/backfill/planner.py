import logging
import shutil
from dataclasses import dataclass
from typing import Any, Optional, Type, Union

from rich.console import Console
from rich.table import Table
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from nethermind.entro.backfill.exporters import (
    AbstractResourceExporter,
    get_db_exporters_for_backfill,
    get_file_exporters_for_backfill,
)
from nethermind.entro.database.readers.internal import fetch_backfills_by_datatype
from nethermind.entro.database.writers.utils import automap_sqlalchemy_model
from nethermind.entro.decoding import DecodingDispatcher
from nethermind.entro.exceptions import BackfillError
from nethermind.entro.types.backfill import BackfillDataType
from nethermind.entro.types.backfill import BackfillDataType as BDT
from nethermind.entro.types.backfill import DataSources
from nethermind.entro.types.backfill import SupportedNetwork as SN
from nethermind.entro.utils import pprint_list

from ..types import BlockIdentifier
from .filter import (
    _clean_block_inputs,
    _filter_conflicting_backfills,
    _generate_topics,
    _unpack_kwargs,
    _verify_filters,
)
from .ranges import BackfillRangePlan

root_logger = logging.getLogger("nethermind")
logger = root_logger.getChild("entro").getChild("backfill").getChild("planner")


# pylint: disable=raise-missing-from


def _handle_event_backfill(decoder: DecodingDispatcher, filter_params: dict[str, Any], metadata_dict: dict[str, Any]):
    """
    Handles the event backfill by generating the event topics and adding them to the metadata dictionary

    :param decoder: ABI Decoder
    :param filter_params: Filter Parameters
    :param metadata_dict: Metadata Dictionary
    """
    if len(decoder.loaded_abis) != 1:
        raise BackfillError(
            f"Expected 1 ABI for Event backfill, but found {len(decoder.loaded_abis)}.  "
            f"Specify an ABI using --contract-abi"
        )
    abi_name, decoder_instance = list(decoder.loaded_abis.items())[0]
    filter_params.update({"abi_name": abi_name})
    metadata_dict.update(
        {
            "topics": _generate_topics(
                decoder_instance,
                filter_params.get("event_names", []),
            )
        }
    )


@dataclass
class BackfillPlan:
    """
    Describes the backfill plan for a given backfill request.  Contains the block ranges to backfill, the backfills
    to remove, and the backfill to add.
    """

    db_session: Session | None  # db session to use for SQLalchemy exporting & range planning
    range_plan: BackfillRangePlan  # Set of blocks to backfill
    backfill_type: BDT  # Data Resources being exported
    network: SN  # Network data is being extracted from

    exporters: dict[str, AbstractResourceExporter]

    metadata_dict: dict[str, Any]  # Metadata that is cached for DB backfills
    filter_params: dict[str, Any]  # Filters to further narrow down the backfilled resources

    decoder: DecodingDispatcher | None  # Optional ABI Decoder

    @classmethod
    def from_cli(
        cls,
        network: SN,
        backfill_type: BDT,
        supported_datasources: list[str],
        **kwargs,
    ) -> Union["BackfillPlan", None]:
        start_block, end_block = _clean_block_inputs(kwargs["from_block"], kwargs["to_block"], backfill_type, network)

        datasource = None
        for ds in supported_datasources:
            if ds in kwargs:
                datasource = DataSources(ds)

        if datasource is None:
            logger.error(f"No Data Source specified for backfill...  Supported Datasources: {supported_datasources}")
            return None

        filter_params, metadata_dict = _unpack_kwargs(kwargs, backfill_type)
        db_session = sessionmaker(create_engine(kwargs["db_url"]))() if "db_url" in kwargs else None

        decoder = cls._initialize_decoder(db_session, metadata_dict)

        if backfill_type == BDT.events:
            cls._inject_event_topics(decoder, filter_params, metadata_dict)

        if db_session:
            exporters = get_db_exporters_for_backfill(backfill_type, db_session.get_bind(), network, kwargs)
            range_plan = BackfillRangePlan.compute_db_backfills(
                from_block=start_block,
                to_block=end_block,
                conflicting_backfills=fetch_backfills_by_datatype(db_session, backfill_type, network),
                backfill_kwargs={  # Parameters saved to Sqlalchemy model
                    "data_type": backfill_type.value,
                    "network": network.value,
                    "filter_data": filter_params,
                    "metadata_dict": metadata_dict,
                    "decoded_abis": decoder.loaded_abis,
                },
            )

        else:
            exporters = get_file_exporters_for_backfill(backfill_type, kwargs)
            range_plan = BackfillRangePlan(
                from_block=start_block, to_block=end_block, conflicts=[], backfill_kwargs=kwargs
            )

        return BackfillPlan(
            db_session=db_session,
            range_plan=range_plan,
            backfill_type=backfill_type,
            network=network,
            exporters=exporters,
            metadata_dict=metadata_dict,
            filter_params=filter_params,
            decoder=None,
        )

    @staticmethod
    def _initialize_decoder(
        db_session: Session | None,
        backfill_metadata: dict[str, Any],
    ) -> DecodingDispatcher | None:
        decode_abis = backfill_metadata.pop("decode_abis", [])

        if not len(decode_abis):
            return None
        return DecodingDispatcher.from_database(
            classify_abis=decode_abis,
            db_session=db_session,
            all_abis=backfill_metadata.get("all_abis", False),
        )

    @staticmethod
    def _inject_event_topics(
        decoder: DecodingDispatcher,
        filter_params: dict[str, Any],
        metadata_dict: dict[str, Any],
    ):
        if len(decoder.loaded_abis) != 1:
            raise BackfillError(
                f"Expected 1 ABI for Event backfill, but found {len(decoder.loaded_abis)}.  "
                f"Specify an ABI using --contract-abi"
            )
        abi_name, decoder_instance = list(decoder.loaded_abis.items())[0]
        filter_params.update({"abi_name": abi_name})
        metadata_dict.update(
            {
                "topics": _generate_topics(
                    decoder_instance,
                    filter_params.get("event_names", []),
                )
            }
        )

    def generate(
        cls,
        db_session: Session,
        backfill_type: BDT,
        network: SN,
        start_block: BlockIdentifier,
        end_block: BlockIdentifier,
        **kwargs,
    ) -> Optional["BackfillPlan"]:
        """
        Generates a backfill plan for a given backfill request.  Contains the block ranges to backfill, the backfills
        to remove, and the backfill to add.

        :param db_session:
        :param backfill_type:
        :param network:
        :param start_block:
        :param end_block:
        :return:
        """
        start_block, end_block = _clean_block_inputs(start_block, end_block, backfill_type, network)
        filter_params, metadata_dict = _unpack_kwargs(kwargs, backfill_type)

        decode_abis = metadata_dict.pop("decode_abis", [])

        decoder: DecodingDispatcher = (
            metadata_dict.pop("decoder")
            if "decoder" in metadata_dict
            else DecodingDispatcher.from_database(
                classify_abis=decode_abis,
                db_session=db_session,
                all_abis=metadata_dict.get("all_abis", False),
            )
        )
        if backfill_type in [BDT.events]:
            if len(decoder.loaded_abis) != 1:
                raise BackfillError(
                    f"Expected 1 ABI for Event backfill, but found {len(decoder.loaded_abis)}.  "
                    f"Specify an ABI using --contract-abi"
                )
            abi_name, decoder_instance = list(decoder.loaded_abis.items())[0]
            filter_params.update({"abi_name": abi_name})
            metadata_dict.update(
                {
                    "topics": _generate_topics(
                        decoder_instance,
                        filter_params.get("event_names", []),
                    )
                }
            )

        _verify_filters(backfill_type, filter_params)

        conflicting_backfills = _filter_conflicting_backfills(
            backfill_type,
            fetch_backfills_by_datatype(db_session, backfill_type, network),
            filter_params.copy() if filter_params else None,
        )

        backfill_range_plan = BackfillRangePlan.compute_db_backfills(
            from_block=start_block,
            to_block=end_block,
            conflicting_backfills=conflicting_backfills,
            backfill_kwargs={
                "data_type": backfill_type.value,
                "network": network.value,
                "filter_data": filter_params,
                "metadata_dict": metadata_dict,
                "decoded_abis": decode_abis,
            },
        )

        if backfill_range_plan.backfill_mode == "empty":
            # The planned backfill is redundant, data is already in db
            return None

        return BackfillPlan(
            db_session=db_session,
            range_plan=backfill_range_plan,
            backfill_type=backfill_type,
            network=network,
            filter_params=filter_params,
            metadata_dict=metadata_dict,
            decoder=decoder,
        )

    def print_backfill_plan(self, console: Console):  # pylint: disable=too-many-locals
        """Prints the backfill plan to the console"""

        if len(self.range_plan.backfill_ranges) == 0:
            console.print("[green]No blocks to backfill")
            return

        backfill_type, network = (
            self.backfill_type.value.capitalize(),
            self.network.value.capitalize(),
        )
        term_width = shutil.get_terminal_size().columns

        console.print(f"[bold]------ Backfill Plan for {network} {backfill_type} ------")

        block_range_table = Table(title="Backfill Block Ranges", min_width=80)
        block_range_table.add_column("Start Block")
        block_range_table.add_column("End Block")
        block_range_table.add_column("Total Blocks", justify="right")

        for start_block, end_block in self.range_plan.backfill_ranges:
            block_range_table.add_row(
                f"{start_block:,}",
                f"{end_block:,}",
                f"{end_block - start_block:,}",
            )
        console.print(block_range_table)

        filter_meta_table = Table(title="Backfill [green]Filters [white]& [cyan]Metadata", min_width=80)
        filter_meta_table.add_column("Key")
        filter_meta_table.add_column("Value")
        for key, val in self.filter_params.items():
            filter_meta_table.add_row(f"[green]{key}", f"{val}")
        for key, val in self.metadata_dict.items():
            filter_meta_table.add_row(f"[cyan]{key}", f"{val}")
        console.print(filter_meta_table)

        if self.metadata_dict.get("all_abis", False):
            console.print(f"[bold]Decoding with All {len(self.decoder.loaded_abis)} ABIs in DB:")
            print_data = pprint_list(sorted(list(self.decoder.loaded_abis.keys())), int(term_width * 0.9))
            for row in print_data:
                console.print(f"\t{row}")

        else:
            print_funcs = self.backfill_type not in [BDT.events, BDT.transfers]
            print_events = self.backfill_type in [BDT.events, BDT.full_blocks]

            abi_table = self.decoder.decoder_table(print_funcs, print_events)
            console.print(abi_table)

        match self.backfill_type:
            case BDT.events:
                abi_name, decoder_instance = list(self.decoder.loaded_abis.items())[0]
                console.print(f"[bold green]Querying Events for Contract: {self.get_filter_param('contract_address')}")
                console.print(f"[bold]{abi_name} ABI Decoding Events:")
                event_name_print = pprint_list(
                    self.filter_params.get("event_names", decoder_instance.get_all_decoded_events(False)),
                    int(term_width * 0.8),
                )
                for row in event_name_print:
                    console.print(f"\t{row}")

            case BDT.transactions | BDT.traces:
                if not self.filter_params:
                    console.print(f"[bold]Querying all {backfill_type} in each block")

            case BDT.full_blocks:
                console.print("[bold]Querying Transactions, Logs, and Receipts for Block Range")
            case BDT.blocks:
                pass
            case _:
                raise NotImplementedError(f"Cannot Printout {backfill_type} Backfills")

        console.print(f"[bold]{'-' * int(term_width * .8)}")

    def total_blocks(self) -> int:
        """Returns the total number of blocks within backfill plan"""
        return sum(end_block - start_block for start_block, end_block in self.range_plan.backfill_ranges)

    def get_filter_param(self, filter_key) -> str:
        """Safely Fetch value of Filter Key.  If filter_key is None, will raise error"""
        if self.filter_params is None:
            raise BackfillError(f"No Filters set for backfill plan, but Filter Key: {filter_key} expected")
        try:
            return self.filter_params[filter_key]
        except KeyError:
            raise BackfillError(f"Filter Key: {filter_key} expected for backfill but not found in filter params")

    def get_metadata(self, metadata_key: str) -> Any:
        """Safely Fetch value of Metadata Key.  If metadata_key is None, will raise error"""
        if self.metadata_dict is None:
            raise BackfillError(
                f"No Metadata set for {self.backfill_type.value.capitalize()} backfill, "
                f"but Metadata Key: {metadata_key} expected"
            )
        try:
            return self.metadata_dict[metadata_key]
        except KeyError:
            raise BackfillError(
                f"Metadata Key: {metadata_key} expected for {self.backfill_type.value.capitalize()} "
                f"backfill but not found in metadata"
            )

    def process_failed_backfill(self, end_block: int):
        """
        Updates the backfill plan to account for a failed backfill. Updates the add and remove backfill
        parameters so they are correctly reflected in the database.

        :param end_block: The block number that the backfill failed on
        """

        for index, (from_blk, to_blk) in enumerate(self.range_plan.backfill_ranges):
            if from_blk <= end_block < to_blk:
                self.range_plan.mark_failed(index, end_block)
                break

            self.range_plan.mark_finalized(index)

    def save_to_db(self):
        """Saves backfill plan to database"""

        for remove_bfill in self.range_plan.remove_backfills:
            self.db_session.delete(remove_bfill)

        if self.range_plan.add_backfill:
            self.db_session.add(self.range_plan.add_backfill)

        self.db_session.commit()

    def backfill_label(self, range_index: int = 0):  # pylint: disable=unused-argument
        """
        Returns a label for the backfilled range.  For a mainnet transaction backfill with the ranges
        [(0, 100), (100, 200)], the label label at range index 0 would be
        "Backfill Ethereum Transactions Between (0 - 100)"
        :param range_index:
        :return:
        """

        net = self.network.pretty()
        typ = self.backfill_type.pretty()

        match self.backfill_type:
            case BDT.events:
                abi_name = list(self.decoder.loaded_abis.keys())[0]
                return f"Backfill {abi_name} Events"
            case _:
                return f"Backfill {net} {typ}"

    def load_model_overrides(self) -> dict[str, Type[DeclarativeBase]]:
        """
        Generates the event topics and model overrides for an event backfill

        :return: (topics, event_model_overrides)
        """
        model_override_dict: dict[str, str] = self.metadata_dict.get("db_models", {})
        if len(model_override_dict) == 0:
            return {}

        _, decoder = list(self.decoder.loaded_abis.items())[0]
        model_overrides = {}

        all_events_in_decoder = decoder.get_all_decoded_events()

        for event, model in model_override_dict.items():
            if "(" not in event:
                event = [sig for sig in all_events_in_decoder if event in sig][0]
            split = list(reversed(model.split(".")))
            res = automap_sqlalchemy_model(
                db_engine=self.db_session.get_bind(),
                table_names=[split[0]],
                schema=split[1] if split[1:] else "public",
            )
            model_overrides.update({event: res[split[0]]})

        return model_overrides
