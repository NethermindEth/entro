from dataclasses import asdict

from nethermind.entro.database.migrations import migrate_up
from nethermind.entro.database.models.starknet import Block as StarknetBlockModel
from nethermind.idealis.types.starknet import Block
from nethermind.idealis.types.starknet.enums import BlockDataAvailabilityMode
from nethermind.idealis.utils import to_bytes


def test_block(integration_db_session):
    migrate_up(integration_db_session.get_bind())

    test_block = Block(
        block_number=623436,
        timestamp=1710916519,
        block_hash=to_bytes("00363b0aadce91115528ebed89ce276820c6b2ed4ff579f9ff72a3528ed4456e"),
        parent_hash=to_bytes("020990f763d0d6d5b3446d1f42234541920047fec02e8fdf9f585a63a97237c7"),
        new_root=to_bytes("0218574db3422f6a70c928ec209f01684a3498823527bb85bd2445451cef6f72"),
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

    model = StarknetBlockModel(**asdict(test_block))

    integration_db_session.add(model)
    integration_db_session.commit()

    db_block = integration_db_session.query(StarknetBlockModel).filter_by(block_number=623436).first()

    assert db_block.block_number == 623436
