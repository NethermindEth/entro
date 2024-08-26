from nethermind.entro.backfill.exporters import db_encode_dataclass
from nethermind.entro.database.migrations import migrate_up
from nethermind.entro.database.models.starknet import Block as StarknetBlockModel
from nethermind.entro.database.models.starknet import Transaction as TransactionModel
from nethermind.idealis.types.starknet import Block, Transaction
from nethermind.idealis.types.starknet.enums import (
    BlockDataAvailabilityMode,
    StarknetFeeUnit,
    StarknetTxType,
    TransactionStatus,
)
from nethermind.idealis.utils import to_bytes


def test_block(integration_db_session):
    migrate_up(integration_db_session.get_bind())

    test_block = Block(
        block_number=623436,
        timestamp=1710916519,
        block_hash=to_bytes("00363b0aadce91115528ebed89ce276820c6b2ed4ff579f9ff72a3528ed4456e"),
        parent_hash=to_bytes("020990f763d0d6d5b3446d1f42234541920047fec02e8fdf9f585a63a97237c7"),
        state_root=to_bytes("0218574db3422f6a70c928ec209f01684a3498823527bb85bd2445451cef6f72"),
        sequencer_address=to_bytes("01176a1bd84444c89232ec27754698e5d2e7e1a7f1539f12027f28b23ec9f3d8"),
        l1_gas_price_wei=32461239745,
        l1_gas_price_fri=52970903581913,
        l1_data_gas_price_wei=1,
        l1_data_gas_price_fri=1631,
        l1_da_mode=BlockDataAvailabilityMode.blob,
        starknet_version="0.13.1",
        transaction_count=191,
        total_fee=820297381255144003,
    )

    model = StarknetBlockModel(**db_encode_dataclass(test_block, "postgresql"))

    integration_db_session.add(model)
    integration_db_session.commit()

    db_block = integration_db_session.query(StarknetBlockModel).filter_by(block_number=623436).first()

    assert db_block.block_number == 623436


def test_transaction(integration_db_session):
    migrate_up(integration_db_session.get_bind())

    test_tx = Transaction(
        transaction_hash=to_bytes("01139643045af8ad540f84685aad59115073f7aae58b1c46fd57cffdef438657"),
        block_number=100,
        transaction_index=0,
        type=StarknetTxType.invoke,
        nonce=69,
        signature=[
            to_bytes("01", pad=32),
            to_bytes("05fa4f83501d55b68af607f8f0e16848052738d856d511c2ab25bfbb7c28b85c"),
            to_bytes("26d858383b0ed587d031d59007917a8d1df018cab20786f3456507b808c0f18"),
        ],
        version=1,
        timestamp=1234,
        status=TransactionStatus.accepted_on_l1,
        max_fee=153626538877863,
        actual_fee=0,
        fee_unit=StarknetFeeUnit.wei,
        execution_resources={},
        gas_used=0,
        tip=0,
        resource_bounds={},
        paymaster_data=[],
        account_deployment_data=[],
        contract_address=to_bytes("02d46760b9253183269588e29123d5cb5770bbde47049d3369be3a21fb9a1f1c"),
        selector=to_bytes("015d40a3d6ca2ac30f4031e42be28da9b056fef9bb7357ac5e85627ee876e5ad"),
        calldata=[
            to_bytes("01"),
            to_bytes("07c2e1e733f28daa23e78be3a4f6c724c0ab06af65f6a95b5e0545215f1abc1b"),
            to_bytes("03e8cfd4725c1e28fa4a6e3e468b4fcf75367166b850ac5f04e33ec843e82c1"),
            to_bytes("04"),
            to_bytes("02d46760b9253183269588e29123d5cb5770bbde47049d3369be3a21fb9a1f1c"),
            to_bytes("02d46760b9253183269588e29123d5cb5770bbde47049d3369be3a21fb9a1f1c"),
            to_bytes("1043d272d8b0538000"),
            to_bytes("00"),
        ],
        class_hash=None,
        user_operations=[],
        revert_error=None,
    )

    print(db_encode_dataclass(test_tx, "postgresql"))
    model = TransactionModel(**db_encode_dataclass(test_tx, "postgresql"))

    integration_db_session.add(model)
    integration_db_session.commit()

    db_tx = (
        integration_db_session.query(TransactionModel)
        .filter_by(transaction_hash=to_bytes("01139643045af8ad540f84685aad59115073f7aae58b1c46fd57cffdef438657"))
        .first()
    )

    assert db_tx is not None
