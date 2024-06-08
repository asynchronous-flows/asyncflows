import inspect
from typing import Any, Literal, Union, Annotated

import pydantic
from pydantic import Field

from asyncflows.models.primitives import HintType, HintLiteral


def _get_recursive_subfields(
    obj: dict | pydantic.BaseModel | Any, prefix: str = ""
) -> list[type[str]]:
    out = []
    if isinstance(obj, dict):
        for name, field in obj.items():
            # out.append(name)
            out.extend(_get_recursive_subfields(field, prefix=f"{name}."))
    elif inspect.isclass(obj) and issubclass(obj, pydantic.BaseModel):
        for name, field in obj.model_fields.items():
            field_annotation = Field(...)
            if field.description:
                field_annotation.description = field.description
            out.append(
                Annotated[
                    Literal[f"{prefix}{name}"],  # type: ignore
                    field_annotation,
                ]
            )
            out.extend(_get_recursive_subfields(field.annotation, prefix=f"{name}."))
    return out


def get_path_literal(
    vars_: HintType,
    strict: bool,
) -> type[str]:
    union_elements = []

    if not strict:
        union_elements.append(str)

    # if there are any strings, then that's the name of the var
    string_vars = [var for var in vars_ if isinstance(var, str)]
    if string_vars:
        union_elements.append(Literal[tuple(string_vars)])  # type: ignore

    # if there are any models, then each recursive subfield is a var, like jsonpath
    model_vars = [var for var in vars_ if isinstance(var, (pydantic.BaseModel, dict))]
    for model_var in model_vars:
        subfields = _get_recursive_subfields(model_var)
        if subfields:
            union_elements.extend(subfields)

    if union_elements:
        return Union[tuple(union_elements)]  # type: ignore
    else:
        return str


def get_var_string(
    hint_literal: HintLiteral | None,
    strict: bool,
) -> str:
    if hint_literal is None:
        var_str = ""
    else:
        # hint_literal is a nested annotated literal union, pull out only the strings
        strings = []
        frontier = [hint_literal]
        while frontier:
            arg = frontier.pop()
            if isinstance(arg, str):
                strings.append(arg)
            elif hasattr(arg, "__args__"):
                frontier.extend(arg.__args__)  # type: ignore

        var_str = "".join(strings)
    if strict:
        var_str = var_str + "__strict"
    return var_str
