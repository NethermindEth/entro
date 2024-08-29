from dataclasses import asdict

from nethermind.entro.backfill.exporters import db_encode_dataclass
from nethermind.entro.database.migrations import migrate_up
from nethermind.entro.database.models.ethereum import Block as BlockModel
from nethermind.entro.database.models.ethereum import Transaction as TransactionModel
from nethermind.idealis.types.ethereum import Block, Transaction
from nethermind.idealis.utils import to_bytes


def test_block(integration_db_session):
    migrate_up(integration_db_session.get_bind())

    test_block = Block(
        block_number=16592887,
        block_hash=to_bytes("0x7de9c923b2eab68a6a750fbe321638387911e9d02bda4671fa89e38999adbab1"),
        difficulty=0,
        extra_data=to_bytes("0x506f776572656420627920626c6f58726f757465"),
        gas_limit=30000000,
        gas_used=29961996,
        miner=to_bytes("0x388c818ca8b9251b393131c08a736a67ccb19297"),
        nonce=to_bytes("0x0000000000000000"),
        parent_hash=to_bytes("0x6f207bcfe8afb73f9b21fc8bb2ad36724d4f46aedf63bc6f0341002688493c99"),
        size=25888,
        state_root=to_bytes("0x51b6d009dbd487d279a2efdc3385ef38cec4124e5a700da200d01062fad3bb16"),
        timestamp=1675966139,
        total_difficulty=58750003716598352816469,
        base_fee_per_gas=77550695617,
    )

    model = BlockModel(**db_encode_dataclass(test_block))

    integration_db_session.add(model)
    integration_db_session.commit()

    db_block = integration_db_session.query(BlockModel).filter_by(block_number=16592887).first()

    assert db_block.block_number == 16592887


def test_transaction(integration_db_session):
    migrate_up(integration_db_session.get_bind())

    test_tx = Transaction(
        block_number=0xDC10DA,
        transaction_index=0,
        transaction_hash=to_bytes("0x1fb4eac2b0e87afb62dcdc8cfc35eb6e58d199503d53510c09f9e159360a5a90"),
        timestamp=0x6236E927,
        nonce=0x8DA,
        from_address=to_bytes("0x7b018835d45f02cac14fe9b38f5aae2f5205200e"),
        gas_supplied=0x37C9C,
        gas_price=0x232592785,
        max_priority_fee=0,
        max_fee=0x3E42350F3,
        input=to_bytes(
            "0x51887695000000000000000000000000000000000000000000000000000000000000020300000000000000000000000000000000000000000000011b899adb3386e000000000000000000000000000000000000000000000000003cd2e0bf63a4480000000000000000000000000000000000000000000000000011cd72945045de000000000000000000000000000000000000000000000000293a1181c89008000000000000000000000000000000000000000000000000000000000100dbd28c856b00000000000000000000000000000000000000000000000000000000000000000"
        ),
        to_address=to_bytes("0x8aff5ca996f77487a4f04f1ce905bf3d27455580"),
        value=0,
        type=None,
        gas_used=109231,
        decoded_input=None,
        function_name=None,
    )

    model = TransactionModel(**db_encode_dataclass(test_tx))

    integration_db_session.add(model)
    integration_db_session.commit()

    db_tx = (
        integration_db_session.query(TransactionModel)
        .filter_by(transaction_hash="0x1fb4eac2b0e87afb62dcdc8cfc35eb6e58d199503d53510c09f9e159360a5a90")
        .first()
    )

    assert db_tx is not None
