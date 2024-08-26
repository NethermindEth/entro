import logging
import click


from nethermind.entro.cli.utils import (
    cli_logger_config,
    group_options,
    json_rpc_option,
    rich_json,
)
from nethermind.idealis.utils import to_bytes, to_hex, zero_pad_hexstr

root_logger = logging.getLogger("nethermind")
logger = root_logger.getChild("cli").getChild("starknet")

# isort: skip_file
# pylint: disable=too-many-arguments,import-outside-toplevel,too-many-locals


@click.group(name="starknet")
def starknet_group():
    """Starknet CLI Commands"""


@starknet_group.command("class")
@click.argument("class_hash")
@group_options(
    json_rpc_option,
)
def get_starknet_class(class_hash: str, json_rpc: str | None = None):
    """Get ABI for a Starknet Class & Print a formatted list of functions and events"""
    import json
    from nethermind.idealis.rpc.starknet import sync_get_class_abi
    from nethermind.starknet_abi.core import StarknetAbi
    from rich.console import Console
    from rich.highlighter import RegexHighlighter
    from rich.panel import Panel

    assert json_rpc is not None, "Environment var JSON_RPC or --json-rpc flag must be set"

    class_hash_bytes = to_bytes(class_hash, pad=32)
    class_abi = sync_get_class_abi(class_hash_bytes, json_rpc)
    if isinstance(class_abi, str):
        try:
            class_abi = json.loads(class_abi)
        except json.JSONDecodeError:
            logging.error(f"Invalid ABI for class 0x{class_hash_bytes.hex()}.  Could not parse ABI JSON...")
            return

    try:
        abi = StarknetAbi.from_json(abi_json=class_abi, class_hash=class_hash_bytes, abi_name="")
    except BaseException as e:  # pylint: disable=broad-except
        logging.error(f"Error parsing ABI for class 0x{class_hash}...  {e}")
        return

    class IndexedParamHighligher(RegexHighlighter):
        """Highlight any text inside <> brackets as yellow"""

        base_style = "repr."
        highlights = [r"(?P<uuid><[^>]+>)"]  # uuid group formats text as repr.uuid (yellow)

    console = Console()
    console.print(Panel(f"[bold]ABI for Class [magenta]0x{class_hash_bytes.hex()}"))
    console.print("[bold green]---- Functions ----")
    for func_name, abi_func in abi.functions.items():
        console.print(f"  {abi_func.id_str().replace('Function', func_name).replace(',', ', ').replace(':', ': ')}")
    console.print("[bold green]---- Events ----")
    for event_name, abi_event in abi.events.items():
        highlight = IndexedParamHighligher()
        console.print(
            f"  [bold magenta]{event_name}[not bold default]",
            highlight(abi_event.id_str().replace("Event", "").replace(",", ", ").replace(":", ": ")),
            sep="",
        )


@starknet_group.command("contract")
@click.argument("contract_address")
@group_options(
    json_rpc_option,
)
def get_starknet_contract_implementation(contract_address: str, json_rpc: str | None = None):
    """Get the implementation history for a Starknet Contract"""
    import asyncio
    import json
    from aiohttp import ClientSession
    from rich.panel import Panel

    from nethermind.idealis.rpc.starknet import (
        generate_contract_implementation,
        sync_get_current_block,
    )
    from nethermind.idealis.types.starknet import ContractImplementation
    from nethermind.idealis.utils.starknet import PessimisticDecoder

    console = cli_logger_config(root_logger)

    assert json_rpc is not None, "Environment Variable JSON_RPC or --json-rpc flag must be set"

    current_block = sync_get_current_block(json_rpc)

    async def _get_contract_impl(contract: bytes) -> ContractImplementation | None:
        session = ClientSession()
        class_decoder = PessimisticDecoder(json_rpc)

        impl = await generate_contract_implementation(
            class_decoder=class_decoder,
            rpc_url=json_rpc,
            aiohttp_session=session,
            contract_address=contract,
            to_block=current_block,
        )

        await session.close()
        return impl

    contract_bytes = to_bytes(contract_address, pad=32)
    impl = asyncio.run(_get_contract_impl(contract_bytes))
    if impl is None:
        logger.error(
            f"Could not generate implementation history for contract 0x{contract_bytes.hex()} at "
            f"starknet block {current_block}"
        )
        return

    console.print(Panel(f"[bold]Implementation History for Contract [magenta]{contract_address}"))
    console.print_json(json.dumps(impl.history))


@starknet_group.command("transaction")
@click.argument("transaction_hash")
@click.option("--full-trace", is_flag=True, default=False, help="Show Decoded Calldata, Events, and Class Hashes")
@click.option("--raw", is_flag=True, default=False, help="Show Raw Calldata, Result, and Selectors")
@group_options(
    json_rpc_option,
)
def get_decoded_transaction(transaction_hash, json_rpc, full_trace, raw):
    """
    Decode Starknet Transaction Trace & Events
    """
    import asyncio
    from aiohttp import ClientSession
    from rich import box
    from rich.console import Group, group
    from rich.table import Table
    from rich.tree import Tree
    from rich.console import Console
    from rich.panel import Panel

    from nethermind.idealis.parse.shared.trace import group_traces
    from nethermind.idealis.parse.starknet.trace import replace_delegate_calls_for_tx
    from nethermind.idealis.rpc.starknet.trace import trace_transaction
    from nethermind.idealis.types.starknet import Event, Trace
    from nethermind.idealis.utils.formatting import pprint_hash
    from nethermind.idealis.utils.starknet import PessimisticDecoder
    from nethermind.starknet_abi.exceptions import InvalidCalldataError

    cli_logger_config(root_logger)

    async def _get_tx_trace() -> tuple[list[Trace], list[Event]]:
        session = ClientSession()
        tx_trace = await trace_transaction(
            transaction_hash=to_bytes(transaction_hash),
            rpc_url=json_rpc,
            aiohttp_session=session,
        )

        call_trace = replace_delegate_calls_for_tx(tx_trace.execute_traces)
        await session.close()
        return call_trace, tx_trace.execute_events

    class_decoder = PessimisticDecoder(json_rpc)

    call_traces, events = asyncio.run(_get_tx_trace())

    for trace in call_traces:
        try:
            decoded = class_decoder.decode_function(
                calldata=[int.from_bytes(c, "big") for c in trace.calldata],
                result=[int.from_bytes(r, "big") for r in trace.result],
                function_selector=trace.selector,
                class_hash=trace.class_hash,
            )

            if decoded is None:
                logger.warning("Cannot decode trace...")
                continue

            trace.decoded_inputs = decoded.inputs
            trace.decoded_outputs = decoded.outputs
            trace.function_name = decoded.name

        except InvalidCalldataError as e:
            logger.error(f"Error decoding trace: {e}")
            trace.function_name = "Unknown"
            continue

    for event in events:
        decoded_event = class_decoder.decode_event(
            keys=[int.from_bytes(k, "big") for k in event.keys],
            data=[int.from_bytes(d, "big") for d in event.data],
            class_hash=event.class_hash,
        )

        event.decoded_params = decoded_event.data
        event.event_name = decoded_event.name

    grouped_traces = group_traces(call_traces)
    root_call_tree = Tree("[bold yellow]Execute Trace")

    def add_to_tree(call_tree: Tree, call_trace: Trace, children: list[tuple[Trace, list]] | None):
        tree_text = [
            f"[bold blue] {call_trace.function_name} [default] -- [green] "
            f"{to_hex(call_trace.contract_address) if full_trace else pprint_hash(call_trace.contract_address)}",
        ]

        trace_table = Table(show_header=False, show_lines=False, box=box.ROUNDED, highlight=True)
        trace_table.add_column("Param", style="bold magenta")
        trace_table.add_column("Value")

        if full_trace:
            trace_table.add_row("Decoded Inputs", rich_json(call_trace.decoded_inputs))
            trace_table.add_row("Decoded Outputs", rich_json(call_trace.decoded_outputs))
            trace_table.add_row("Class Hash", to_hex(call_trace.class_hash))

        if raw:
            trace_table.add_row("Calldata", rich_json([to_hex(c) for c in call_trace.calldata]))
            trace_table.add_row("Result", rich_json([to_hex(r) for r in call_trace.result]))
            trace_table.add_row("Selector", to_hex(call_trace.selector))
        if trace_table.row_count > 0:
            tree_text.append(trace_table)

        child_tree = call_tree.add(Group(*tree_text))
        if not children:
            return

        for child in children:
            add_to_tree(child_tree, child[0], child[1])

    add_to_tree(root_call_tree, grouped_traces[0], grouped_traces[1])

    @group()
    def event_tables(list_events: list[Event]):
        for list_event in list_events:
            event_table = Table(box=box.ROUNDED, show_header=False, highlight=True)
            event_table.add_column("Param", style="bold magenta")
            event_table.add_column("Value")

            event_table.add_row("Name", f"[bold blue]{list_event.event_name}")
            event_table.add_row("Contract", f"0x{list_event.contract_address.hex()}")
            event_table.add_row("Decoded", rich_json(list_event.decoded_params))

            if raw:
                event_table.add_row("Keys", rich_json([to_hex(k) for k in list_event.keys]))
                event_table.add_row("Data", rich_json([to_hex(d) for d in list_event.data]))
                event_table.add_row("Class Hash", to_hex(list_event.class_hash))

            yield event_table

    console = Console()
    console.print(Panel(f"[bold] Transaction Trace [/bold]-- [bold magenta]{zero_pad_hexstr(transaction_hash, 32)}"))
    console.print(root_call_tree)
    console.print(Panel("[bold yellow]Execute Events"))
    if full_trace:
        console.print(event_tables(events))
    else:
        event_text = [
            f"   [bold blue]{e.event_name} [default] -- [green]{pprint_hash(e.contract_address)}" for e in events
        ]
        console.print(*event_text, sep="\n")
