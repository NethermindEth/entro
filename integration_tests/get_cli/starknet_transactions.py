from click.testing import CliRunner

from nethermind.entro.cli import entro_cli


def test_starknet_simple_txn(starknet_rpc_url):
    runner = CliRunner()

    result = runner.invoke(
        entro_cli,
        [
            "get",
            "starknet",
            "transaction",
            "0x044c8d0d48bbdfd1f062ba47337edf501a1b3beb65d8193d89102e0ab708d819",
            "--json-rpc",
            starknet_rpc_url,
        ],
    )

    expected_output = [
        "0x044c8d0d48bbdfd1f062ba47337edf501a1b3beb65d8193d89102e0ab708d819",
        "Execute Trace",
        "└──  __execute__  --  0x03b1ac62...c321c5e6",
        "    ├──  transfer  --  0x049d3657...9e004dc7",
        "    └──  watch  --  0x02299378...2ac4a8c4",
        # Events
        "TransactionExecuted  -- 0x03b1ac62...c321c5e6",
        "Transfer  -- 0x049d3657...9e004dc7",
        "watch_ls_id  -- 0x02299378...2ac4a8c4",
    ]

    assert result.exit_code == 0
    for out in expected_output:
        assert out in result.output


def test_get_invalid_trace_txn(starknet_rpc_url):
    runner = CliRunner()

    result = runner.invoke(
        entro_cli,
        [
            "get",
            "starknet",
            "transaction",
            "0x5d4f4be4095b0966a8e27f2c0e8bd1f818186a712610455334d78a1d379f470",
            "--json-rpc",
            *starknet_rpc_url,
        ],
    )

    assert result.exit_code == 1
