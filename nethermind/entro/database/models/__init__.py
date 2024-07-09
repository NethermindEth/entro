from typing import Literal, Type, Union

from sqlalchemy.orm import DeclarativeBase

from nethermind.entro.types.backfill import SupportedNetwork

from .base import (
    AbstractBlock,
    AbstractERC20Transfer,
    AbstractEvent,
    AbstractTrace,
    AbstractTransaction,
)
from .ethereum import Block as EthereumBlock
from .ethereum import DefaultEvent as EthereumDefaultEvent
from .ethereum import ERC20Transfer as EthereumERC20Transfer
from .ethereum import Trace as EthereumTrace
from .ethereum import Transaction as EthereumTransaction
from .internal import BackfilledRange, ContractABI
from .starknet import Block as StarknetBlock
from .starknet import DefaultEvent as StarknetDefaultEvent
from .starknet import ERC20Transfer as StarknetERC20Transfer
from .starknet import Transaction as StarknetTransaction
from .zk_sync import EraBlock as ZKSyncEraBlock
from .zk_sync import EraDefaultEvent as ZKSyncEraDefaultEvent
from .zk_sync import EraERC20Transfer as ZKSyncEraERC20Transfer
from .zk_sync import EraTransaction as ZKSyncEraTransaction

EVMBlock = Union[EthereumBlock, ZKSyncEraBlock]
EVMTransaction = Union[EthereumTransaction, ZKSyncEraTransaction]
EVMDefaultEvent = Union[EthereumDefaultEvent, ZKSyncEraDefaultEvent]


def block_model_for_network(network: SupportedNetwork) -> Type[AbstractBlock]:
    """
    Returns the block model for the given network

    :param network:
    :return:
    """
    match network:
        case SupportedNetwork.ethereum:
            return EthereumBlock
        case SupportedNetwork.zk_sync_era:
            return ZKSyncEraBlock
        case SupportedNetwork.starknet:
            return StarknetBlock
        case _:
            raise ValueError(f"Unsupported network: {network}")


def transaction_model_for_network(
    network: SupportedNetwork,
) -> Type[AbstractTransaction]:
    """
    Returns the transaction model for the given network
    :param network:
    :return:
    """
    match network:
        case SupportedNetwork.ethereum:
            return EthereumTransaction
        case SupportedNetwork.zk_sync_era:
            return ZKSyncEraTransaction
        case SupportedNetwork.starknet:
            return StarknetTransaction
        case _:
            raise ValueError(f"Unsupported network: {network}")


def default_event_model_for_network(
    network: SupportedNetwork,
) -> Type[AbstractEvent]:
    """
    Returns the default event model for the given network
    :param network:
    :return:
    """
    match network:
        case SupportedNetwork.ethereum:
            return EthereumDefaultEvent
        case SupportedNetwork.zk_sync_era:
            return ZKSyncEraDefaultEvent
        case SupportedNetwork.starknet:
            return StarknetDefaultEvent
        case _:
            raise ValueError(f"Unsupported network: {network}")


def transfer_model_for_network(
    network: SupportedNetwork,
) -> Type[AbstractERC20Transfer]:
    """
    Returns the transfer model for the given network
    """

    match network:
        case SupportedNetwork.ethereum:
            return EthereumERC20Transfer
        case SupportedNetwork.zk_sync_era:
            return ZKSyncEraERC20Transfer
        case SupportedNetwork.starknet:
            return StarknetERC20Transfer
        case _:
            raise ValueError(f"Unsupported network: {network}")


def trace_model_for_network(
    network: SupportedNetwork,
) -> Type[AbstractTrace]:
    """
    Returns the trace model for the given network
    """

    raise NotImplementedError("Trace model is not implemented yet")


def model_for_network(
    network: SupportedNetwork,
    model_type: Literal["Block", "Transaction", "DefaultEvent"],
) -> Type[DeclarativeBase]:
    """
    Returns the model for the given network and model type
    :param network:
    :param model_type:
    :return:
    """
    match model_type:
        case "Block":
            return block_model_for_network(network)
        case "Transaction":
            return transaction_model_for_network(network)
        case "DefaultEvent":
            return default_event_model_for_network(network)
        case _:
            raise ValueError(f"Unsupported model type: {model_type}")
