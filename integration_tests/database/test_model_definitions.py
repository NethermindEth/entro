import importlib.util
import inspect
import os
from pathlib import Path
import dataclasses

import pytest
from nethermind.entro.database.models.base import Base


PARENT_DIRECTORY = Path(__file__).parents[2]

# List of DB Models which dont have idealis dataclasses defined
SKIPPED_PYTHON_MODULES = [
    "nethermind.entro.database.models.prices",
    "nethermind.entro.database.models.internal",
    "nethermind.entro.database.models.uniswap",
]


SKIPPED_FILES = [
    "base.py",
    "__init__.py",
]


def construct_import_path(file_path):
    # Convert file path to import path
    relative_path = os.path.relpath(file_path, PARENT_DIRECTORY)

    # replace / with . and remove .py
    return relative_path.replace(os.sep, ".")[:-3]


def walk_directory(directory) -> list[str]:
    """Walk through a directory and return model paths"""
    model_paths = []

    for root, _, files in os.walk(directory):

        for file in files:
            if not file.endswith(".py") or file in SKIPPED_FILES:
                continue

            Base.metadata.clear()
            file_path = os.path.join(root, file)
            module_path = construct_import_path(file_path)

            if module_path in SKIPPED_PYTHON_MODULES:
                continue

            try:
                spec = importlib.util.spec_from_file_location(module_path, file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, Base):
                        if not hasattr(obj, "__tablename__"):
                            continue  # Abstract classes dont have a __tablename__ defined

                        model_paths.append(f"{module_path}.{name}")

            except Exception as e:
                print(f"Could not import {module_path}: {e}")

    return model_paths


model_paths = walk_directory(PARENT_DIRECTORY / "nethermind" / "entro" / "database" / "models")


# Step 1:
# Recursively look through the python_eth_amm/database/models directory & generate list of DB Models

# Step 2 pytest.mark.parametrize the list of DB Models to the test function
# Call inspect.getmembers on the module to get all the class attributes (ignore methods)
# Call class.__dict__() to get the declared attributes of the class
# If there are attributes in the getmembers that are not present in the __dict__ then they are inherited attributes
# If inherited attributes not in [__tablename__, etc...] raise error since attribute needs to be overriden with
#   sqlalchemy type that can be mapped to DB


@pytest.mark.parametrize("database_model", model_paths)
def test_sqlalchemy_models_override_all_dataclass_fields(database_model):
    """
    Test that all dataclass fields in a SQLAlchemy model are overridden with SQLAlchemy types.

    nethermind.idealis defines dataclasses for parsed blockchain data.  The python-eth-amm models override these
    attributes with sqlalchemy orm mapped_columns specifying DB types.  This test ensures that all dataclass
    fields have been overridden with sqlalchemy types, allowing dataclasses to be converted into models using
    db_model(**dataclasses.to_dict(dataclass)) syntax
    """
    Base.metadata.clear()

    module_name, db_model_name = database_model.rsplit(".", 1)

    spec = importlib.util.spec_from_file_location(
        module_name, PARENT_DIRECTORY / f"{module_name.replace('.', os.sep)}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class_def = getattr(module, db_model_name)
    unique_keys = {k for k in class_def.__table__.columns.keys() if not k.startswith("_")}

    assert set(class_def.__table__.columns.keys()) == unique_keys

    dataclass_path = database_model.rsplit(".", 2)[1:-1]
    dataclass_mod_path = f"nethermind.idealis.types." + ".".join(dataclass_path)

    spec = importlib.util.find_spec(dataclass_mod_path)
    dataclass_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dataclass_module)

    if db_model_name.endswith("DefaultEvent"):
        dataclass_search_name = "Event"
    else:
        dataclass_search_name = db_model_name

    dataclass = getattr(dataclass_module, dataclass_search_name)
    fields = dataclasses.fields(dataclass)
    print(fields)
