import logging
import shutil
import traceback
from dataclasses import dataclass
from typing import Any, Type, Union

from rich.console import Console
from rich.progress import Progress
from rich.table import Table
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from nethermind.entro.backfill.exporters import (
    AbstractResourceExporter,
    get_db_exporters_for_backfill,
    get_file_exporters_for_backfill,
)
from nethermind.entro.backfill.importers import get_importer_for_backfill
from nethermind.entro.database.readers.internal import fetch_backfills_by_datatype
from nethermind.entro.database.writers.utils import automap_sqlalchemy_model
from nethermind.entro.decoding import DecodingDispatcher
from nethermind.entro.exceptions import BackfillError, DecodingError
from nethermind.entro.types.backfill import BackfillDataType as BDT
from nethermind.entro.types.backfill import Dataclass, DataSources, ImporterCallable
from nethermind.entro.types.backfill import SupportedNetwork as SN
from nethermind.entro.utils import pprint_list

from .filter import _clean_block_inputs, _generate_topics, _unpack_kwargs
from .ranges import BackfillRangePlan
from .utils import GracefulKiller, progress_defaults

root_logger = logging.getLogger("nethermind")
logger = root_logger.getChild("entro").getChild("backfill").getChild("planner")


# pylint: disable=raise-missing-from


def _default_batch_size(backfill_type: BDT) -> int:
    """
    Returns the default batch size for a given backfill type

    :param backfill_type: The backfill type
    :return: The default batch size
    """
    match backfill_type:
        case BDT.events | BDT.transfers:
            return 1000
        case BDT.full_blocks | BDT.traces:
            return 10
        case BDT.blocks | BDT.transactions:
            return 50
        case _:
            raise NotImplementedError(f"Cannot determine default batch size for {backfill_type}")


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

    importer: ImporterCallable
    exporters: dict[str, AbstractResourceExporter]

    metadata_dict: dict[str, Any]  # Metadata that is cached for DB backfills
    filter_params: dict[str, Any]  # Filters to further narrow down the backfilled resources

    decoder: DecodingDispatcher | None  # Optional ABI Decoder

    batch_size: int  # Number of blocks to backfill at a time
    max_concurrency: int = 10  # Maximum number of concurrent requests
    confirm: bool = True  # Whether to confirm the backfill before executing

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
        db_session = sessionmaker(create_engine(kwargs["db_url"]))() if kwargs["db_url"] else None

        decoder = cls._initialize_decoder(db_session, metadata_dict, network)

        if backfill_type == BDT.events:
            assert decoder is not None, "Decoder must be initialized for Event Backfill"
            cls._inject_event_topics(decoder, filter_params, metadata_dict)

        if db_session:
            exporters = get_db_exporters_for_backfill(backfill_type, db_session.get_bind(), network, kwargs)
            range_plan = BackfillRangePlan.compute_db_backfills(
                from_block=start_block,
                to_block=end_block,
                conflicting_backfills=fetch_backfills_by_datatype(db_session, backfill_type, network),
            )

        else:
            exporters = get_file_exporters_for_backfill(backfill_type, kwargs)
            range_plan = BackfillRangePlan(from_block=start_block, to_block=end_block, conflicts=[])

        return BackfillPlan(
            db_session=db_session,
            range_plan=range_plan,
            backfill_type=backfill_type,
            network=network,
            exporters=exporters,
            importer=get_importer_for_backfill(network, backfill_type),
            metadata_dict=metadata_dict,
            filter_params=filter_params,
            decoder=decoder,
            batch_size=metadata_dict.get("batch_size", _default_batch_size(backfill_type)),
        )

    @staticmethod
    def _initialize_decoder(
        db_session: Session | None,
        backfill_metadata: dict[str, Any],
        network: SN,
    ) -> DecodingDispatcher | None:
        decode_abis = backfill_metadata.pop("decode_abis", [])

        if not len(decode_abis):
            return None

        return DecodingDispatcher.from_abis(
            classify_abis=decode_abis,
            db_session=db_session,
            decoder_os=DecodingDispatcher.decoder_os_for_network(network),
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
                f"Specify a single ABI using --contract-abi flag"
            )
        event_names, topics = _generate_topics(decoder, filter_params.get("event_names", []))

        filter_params.update({"abi_name": decoder.loaded_abis[0], "event_names": event_names})
        metadata_dict.update({"topics": topics})

    def execute_backfill(self, console: Console, killer: GracefulKiller):
        """
        Executes the backfill plan

        :param console: Rich Console
        :param killer: Graceful Killer
        """

        with Progress(*progress_defaults, console=console) as progress:
            for range_idx, (range_start, range_end) in enumerate(self.range_plan.backfill_ranges):
                range_progress = progress.add_task(
                    description=self.backfill_label(range_idx),
                    total=range_end - range_start,
                    searching_block=range_start,
                )

                for batch_start in range(range_start, range_end, self.batch_size):
                    batch_end = min(batch_start + self.batch_size, range_end)
                    if killer.kill_now:
                        self.process_failed_backfill(batch_start)
                        return

                    try:
                        batch_dataclasses = self.importer(
                            from_block=batch_start,
                            to_block=batch_end,
                            **self.metadata_dict,
                            **self.filter_params,
                        )

                        for data_key, exporter in self.exporters.items():
                            export_dataclasses = batch_dataclasses.get(data_key, [])

                            if self.decoder:
                                self.decoder.decode_dataclasses(data_kind=data_key, dataclasses=export_dataclasses)

                            exporter.write(export_dataclasses)

                        progress.update(range_progress, advance=batch_end - batch_start, searching_block=batch_end)

                    except BaseException as e:  # pylint: disable=broad-except
                        console.print(
                            f"[red] ----  Unexpected Error Processing Blocks {batch_start} - {batch_end}  ----"
                        )
                        console.print(traceback.format_exception(type(e), e, e.__traceback__))
                        self.process_failed_backfill(batch_start)
                        return

        console.print("[green]---- Backfill Complete ------")

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

        # Print Decoded ABis
        if self.decoder:
            self.print_decode_abis(console, term_width)

        match self.backfill_type:
            case BDT.events:
                console.print(f"[bold green]Querying Events for Contract: {self.get_filter_param('contract_address')}")
                console.print(f"[bold]{self.filter_params['abi_name']} ABI Decoding Events:")
                for row in pprint_list(self.filter_params["event_names"], int(term_width * 0.8)):
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

    def print_decode_abis(self, console: Console, term_width: int):
        if self.metadata_dict.get("all_abis", False):
            console.print(f"[bold]Decoding with All {len(self.decoder.loaded_abis)} {self.decoder.os} ABIs in DB:")
            for row in pprint_list(sorted(self.decoder.loaded_abis), int(term_width * 0.9)):
                console.print(f"\t{row}")

        else:
            print_funcs = self.backfill_type not in [BDT.events, BDT.transfers]
            print_events = self.backfill_type in [BDT.events, BDT.full_blocks]

            abi_table = self.decoder.decoder_table(print_funcs, print_events)
            console.print(abi_table)

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

    def range_kwargs(self) -> dict[str, Any]:
        return {
            "data_type": self.backfill_type,
            "network": self.network,
            "filter_data": self.filter_params,
            "metadata_dict": self.metadata_dict,
            "decoded_abis": self.decoder.loaded_abis
            if self.decoder and self.metadata_dict.get("all_abis", False)
            else [],
        }

    def process_failed_backfill(self, end_block: int):
        """
        Updates the backfill plan to account for a failed backfill. Updates the add and remove backfill
        parameters so they are correctly reflected in the database.

        :param end_block: The block number that the backfill failed on
        """

        for index, (from_blk, to_blk) in enumerate(self.range_plan.backfill_ranges):
            if from_blk <= end_block < to_blk:
                self.range_plan.mark_failed(index, end_block, self.range_kwargs())
                break

            self.range_plan.mark_finalized(index, self.range_kwargs())

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
                return f"Backfill {self.decoder.loaded_abis[0]} Events"
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

        model_overrides = {}

        for event, model in model_override_dict.items():
            if "(" not in event:
                event = [e for e in self.decoder.event_decoders.values() if event in e.name][0]
            split = list(reversed(model.split(".")))
            res = automap_sqlalchemy_model(
                db_engine=self.db_session.get_bind(),
                table_names=[split[0]],
                schema=split[1] if split[1:] else "public",
            )
            model_overrides.update({event: res[split[0]]})

        return model_overrides
