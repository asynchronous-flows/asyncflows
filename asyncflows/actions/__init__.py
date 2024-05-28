from typing import Type, Any

from asyncflows.actions.base import ActionMeta, InternalActionBase
from asyncflows.models.primitives import ExecutableName


def recursive_import(package_name):
    import pkgutil
    import importlib

    package = importlib.import_module(package_name)
    if not hasattr(package, "__path__"):
        print(f"Package {package_name} has no __path__ attribute")
        raise ImportError
    for _, module_name, is_pkg in pkgutil.walk_packages(
        package.__path__, package.__name__ + "."
    ):
        try:
            importlib.import_module(module_name)
            if is_pkg:
                recursive_import(module_name)
        except ImportError as e:
            print(f"Failed to import {module_name}: {e}")


_processed_entrypoints = set()


def get_actions_dict() -> dict[ExecutableName, Type[InternalActionBase[Any, Any]]]:
    import importlib_metadata

    # import all action entrypoints, including `asyncflows.actions` and other installed packages
    entrypoints = importlib_metadata.entry_points(group="asyncflows")
    for entrypoint in entrypoints.select(name="actions"):
        if entrypoint.dist.name in _processed_entrypoints:
            continue
        _processed_entrypoints.add(entrypoint.dist.name)
        try:
            recursive_import(entrypoint.value)
        except Exception as e:
            print(f"Failed to import entrypoint {entrypoint.name}: {e}")

    # return all subclasses of Action as registered in the metaclass
    return ActionMeta.actions_registry
