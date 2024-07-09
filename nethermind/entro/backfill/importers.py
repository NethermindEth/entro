from nethermind.entro.types.backfill import Dataclass, ImporterCallable


def get_importers_for_backfill() -> dict[str, ImporterCallable]:
    """
    Returns a dictionary of importers for backfill operations
    :return:
    """
    from nethermind.idealis.rpc.starknet import get_blocks_with_txns

    return {
        "blocks": get_blocks_with_txns,
    }
