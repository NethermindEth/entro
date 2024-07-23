import pytest
from aiohttp import ClientSession

from nethermind.idealis.parse.starknet.trace import replace_delegate_calls_for_tx
from nethermind.idealis.rpc.starknet.trace import trace_transaction
from nethermind.idealis.utils import to_bytes
from nethermind.idealis.utils.starknet import PessimisticDecoder


@pytest.mark.asyncio
async def test_decode_tx_traces(starknet_rpc_url):
    session = ClientSession()
    tx_trace = await trace_transaction(
        transaction_hash=to_bytes("0x044c8d0d48bbdfd1f062ba47337edf501a1b3beb65d8193d89102e0ab708d819"),
        rpc_url=starknet_rpc_url,
        aiohttp_session=session,
    )
    await session.close()

    call_traces = replace_delegate_calls_for_tx(tx_trace.execute_traces)

    class_decoder = PessimisticDecoder(starknet_rpc_url)

    for trace in call_traces:
        decoded = class_decoder.decode_function(
            calldata=[int.from_bytes(c, "big") for c in trace.calldata],
            result=[int.from_bytes(r, "big") for r in trace.result],
            function_selector=trace.selector,
            class_hash=trace.class_hash,
        )

        trace.decoded_inputs = decoded.inputs
        trace.decoded_outputs = decoded.outputs
        trace.function_name = decoded.name

    assert call_traces[0].function_name == "__execute__"

    assert call_traces[1].function_name == "transfer"
    assert call_traces[1].contract_address == to_bytes(
        "0x049d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7"
    )
    assert call_traces[1].decoded_outputs == [True]
    assert call_traces[1].decoded_inputs == {
        "recipient": "0x019252b1deef483477c4d30cfcc3e5ed9c82fafea44669c182a45a01b4fdb97a",
        "amount": 32000000000000000,
    }

    assert call_traces[2].function_name == "watch"
    assert call_traces[2].contract_address == to_bytes(
        "0x022993789c33e54e0d296fc266a9c9a2e9dcabe2e48941f5fa1bd5692ac4a8c4"
    )
