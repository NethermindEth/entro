import json

from nethermind.entro.backfill.utils import rpc_response_to_trace_model
from nethermind.entro.decoding import DecodingDispatcher
from nethermind.entro.types.backfill import SupportedNetwork
from tests.resources.ABI import ERC20_ABI_JSON


def test_trace_parsing():
    trace_json = '[{"action":{"callType":"call","from":"0xa6cc3c2531fdaa6ae1a3ca84c2855806728693e8","gas":"0x24465","input":"0xa9059cbb00000000000000000000000057c1e0c2adf6eecdb135bcf9ec5f23b319be2c940000000000000000000000000000000000000000000000e9cff2c7dd6572495e","to":"0x514910771af9ca656af840dff83e8264ecf986ca","value":"0x0"},"block_hash":"0x1b75b316f7df1d4ab9f3686180c1147cf015af42885d8e7b5fe2ea079834c606","block_number":16217506,"result":{"gasUsed":"0x3421","output":"0x0000000000000000000000000000000000000000000000000000000000000001"},"subtraces":0,"trace_address":[1,0],"transaction_hash":"0xc80bc9848eaa50ab54d4abee62870f2f68e189a1cc486479b1a16b93a4ea23cc","transaction_position":0,"type":"call","error":null}]'
    trace_data = json.loads(trace_json)
    decoder = DecodingDispatcher()
    decoder.add_abi("ERC20", json.loads(ERC20_ABI_JSON))
    parsed_trace = rpc_response_to_trace_model(trace_data, SupportedNetwork.ethereum, "postgresql", decoder)


def test_transfer_traces_are_decoded():
    pass


def test_decoded_trace_has_null_input_data():
    pass


def test_swap_trace_is_not_decoded():
    pass
