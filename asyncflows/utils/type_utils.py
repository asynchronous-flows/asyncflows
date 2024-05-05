import typing
from typing import Any, Literal

import pydantic

from asyncflows.models.primitives import HintType


def _get_recursive_subfields(obj: dict | pydantic.BaseModel | Any) -> list[str]:
    out = []
    if isinstance(obj, dict):
        for name, field in obj.items():
            # out.append(name)
            sub_out = _get_recursive_subfields(field)
            out.extend([name + "." + sub_name for sub_name in sub_out])
    elif isinstance(obj, type) and issubclass(obj, pydantic.BaseModel):
        for name, field in obj.model_fields.items():
            out.append(name)
            sub_out = _get_recursive_subfields(field.annotation)
            out.extend([name + "." + sub_name for sub_name in sub_out])
    return out


def get_path_literal(
    vars_: HintType,
    strict: bool,
) -> type[str | None]:
    if not strict:
        var_type = str
    else:
        # TODO it doesn't really make sense to include NoneType, but starting the type with Never breaks pydantic
        var_type = type(None)

    # if there are any strings, then that's the name of the var
    string_vars = [var for var in vars_ if isinstance(var, str)]
    if string_vars:
        var_type = var_type | Literal[tuple(string_vars)]  # type: ignore

    # if there are any models, then each recursive subfield is a var, like jsonpath
    model_vars = [var for var in vars_ if isinstance(var, (pydantic.BaseModel, dict))]
    for model_var in model_vars:
        subfields = _get_recursive_subfields(model_var)
        if subfields:
            var_type = var_type | Literal[tuple(subfields)]  # type: ignore

    return var_type


def get_var_string(
    vars_: HintType | None,
    strict: bool,
) -> str:
    if vars_ is None:
        var_str = ""
    else:
        var_list = [
            var
            if isinstance(var, str)
            else list(var)[0]
            if isinstance(var, dict)
            else str(__name__)
            for var in vars_
            if var
        ]
        var_str = "_".join(var_list)
    if strict:
        var_str = var_str + "__strict"
    return var_str


def filter_none_from_type(
    type_: type[Any],
) -> type[Any]:
    type_args = typing.get_args(type_)
    if type(None) not in type_args:
        raise ValueError(f"Type {type_} does not contain None")
    new_type_args = tuple(arg for arg in type_args if arg is not type(None))
    if len(type_args) == 1:
        return type_args[0]
    else:
        return typing.Union[new_type_args]  # type: ignore
