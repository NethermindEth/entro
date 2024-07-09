import asyncio
import json
import logging

import click
from rich.console import Console
from rich.highlighter import RegexHighlighter

from nethermind.entro.cli.utils import group_options, json_rpc_option
from nethermind.entro.utils import to_bytes


@click.group(name="starknet")
def starknet_group():
    ...


@starknet_group.command("class")
@click.argument("class_hash")
@group_options(
    json_rpc_option,
)
def get_starknet_class(class_hash: str, json_rpc: str):
    from nethermind.idealis.rpc.starknet import sync_get_class_abi
    from nethermind.starknet_abi.core import StarknetAbi

    class_abi = sync_get_class_abi(to_bytes(class_hash), json_rpc)
    if isinstance(class_abi, str):
        try:
            class_abi = json.loads(class_abi)
        except json.JSONDecodeError:
            logging.error(f"Invalid ABI for class 0x{class_hash}.  Could not parse ABI JSON...")
            return None

    try:
        abi = StarknetAbi.from_json(abi_json=class_abi, class_hash=to_bytes(class_hash), abi_name="")
    except BaseException as e:
        logging.error(f"Error parsing ABI for class 0x{class_hash}...  {e}")
        return None

    class IndexedParamHighligher(RegexHighlighter):
        base_style = "repr."
        highlights = [r"(?P<uuid><[^>]+>)"]  # uuid group formats text as repr.uuid (yellow)

    console = Console()
    console.print(f"{'-' * 80}\n[bold]ABI for Class {class_hash}\n{'-' * 80}")
    console.print("[bold green]---- Functions ----")
    for func_name, abi_func in abi.functions.items():
        console.print(f"  {abi_func.id_str().replace('Function', func_name)}")
    console.print("[bold green]---- Events ----")
    for event_name, abi_event in abi.events.items():
        highlight = IndexedParamHighligher()
        console.print(
            f"  [bold magenta]{event_name}[not bold default]", highlight(abi_event.id_str().replace("Event", ""))
        )


@starknet_group.command("contract")
@click.argument("contract_address")
@group_options(
    json_rpc_option,
)
def get_starknet_contract_implementation(contract_address: str, json_rpc: str):
    from aiohttp import ClientSession

    from nethermind.idealis.rpc.starknet import (
        generate_contract_implementation,
        sync_get_current_block,
    )
    from nethermind.idealis.types.starknet import ContractImplementation
    from nethermind.idealis.utils.starknet import PessimisticDecoder

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

    impl = asyncio.run(_get_contract_impl(to_bytes(contract_address)))
    console = Console()

    console.print(f"{'-' * 102}\n[bold]Implementation History for Contract {contract_address}\n{'-' * 102}")
    console.print_json(json.dumps(impl.history))


@starknet_group.command("transaction")
@click.argument("transaction_hash")
@group_options(
    json_rpc_option,
)
def get_decoded_transaction(transaction_hash, json_rpc):
    pass
