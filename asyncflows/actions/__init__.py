from typing import Type, Any

from asyncflows.actions.base import ActionMeta, InternalActionBase
from asyncflows.models.primitives import ExecutableName


def get_actions_dict() -> dict[ExecutableName, Type[InternalActionBase[Any, Any]]]:
    # import all Action subclass declarations in the folder
    import os
    import importlib

    for filename in os.listdir(os.path.dirname(__file__)):
        if filename in ["__init__.py", "base.py"] or filename[-3:] != ".py":
            continue
        module_name = filename.removesuffix(".py")
        importlib.import_module(f"asyncflows.actions.{module_name}")

    # return all subclasses of Action as registered in the metaclass
    return ActionMeta.actions_registry
