import inspect
import os
import types
import typing
from enum import Enum
from typing import Any, Literal, Union, Annotated
from weakref import WeakValueDictionary

import pydantic
from pydantic import Field, BaseModel
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

from asyncflows.models.config.transform import TransformsFrom
from asyncflows.models.primitives import HintType, HintLiteral


# forgive me father for I have sinned
# "I have used a global variable", says copilot
# this goes beyond mere global variables
# here is a function that transforms types, and renamespaces them to this module if they're pydantic models
# some types have recursive references, so we cache their forward references

# edit: im kind of proud of this function now that it's been refactored a bit

_forward_ref_cache = WeakValueDictionary()
_transformation_cache = {}  # TODO this could be a WeakValueDictionary too, but it complains about types being stored


def templatify_fields(
    type_: type[BaseModel],
    vars_: HintLiteral | None = None,
    links: HintLiteral | None = None,
    add_union: type | None = None,
    strict: bool = False,
):
    fields = {}
    for field_name, field_ in type_.model_fields.items():
        # Annotate optional fields with a default of None
        if field_.default is not PydanticUndefined:
            default = field_.default
        elif not field_.is_required():
            default = None
        else:
            default = ...
        field_type = field_.annotation

        # recurse over each field
        new_field_type = transform_and_templatify_type(
            field_type, vars_, links, add_union, strict
        )

        # add a union to the mix
        if add_union is not None:
            # raise if `add_union` collides with existing an existing field name
            # TODO should we just not add the union if it collides?
            # for field_name in type_.model_fields:
            #     if any(
            #         field_name in m.model_fields for m in typing.get_args(add_union)
            #     ):
            #         raise ValueError(f"{field_name} is a restricted field name.")
            new_field_type = Union[new_field_type, add_union]

        # keep original FieldInfo
        annotated_field_type = typing.Annotated[new_field_type, field_]

        fields[field_name] = (annotated_field_type, default)

    return fields


def transform_and_templatify_type(
    type_: Any,
    vars_: HintLiteral | None = None,
    links: HintLiteral | None = None,
    add_union: type | None = None,
    strict: bool = False,
) -> Any:  # Union[type[ConfigType], type[ImplementsTransformsInContext]]:
    # cache resolved types to avoid forward references when unnecessary
    var_string = get_var_string(vars_, strict)
    cache_key = str((type_, var_string))
    if cache_key in _transformation_cache:
        return _transformation_cache[cache_key]
    # cache ForwardRefs to avoid infinite recursion
    if cache_key in _forward_ref_cache:
        return _forward_ref_cache[cache_key]

    # determine `name` and `module`,
    # store ForwardRef if necessary
    if (
        hasattr(type_, "__name__")
        and not hasattr(type_, "__origin__")
        and type_.__module__ != "builtins"
    ):
        if inspect.isclass(type_) and issubclass(type_, BaseModel):
            name = f"{type_.__name__}_{var_string}"
            module = __name__
        else:
            name = type_.__name__
            module = type_.__module__
        _forward_ref_cache[cache_key] = typing.ForwardRef(
            arg=name,
            module=module,
        )
    else:
        name = None
        module = None

    origin = typing.get_origin(type_)
    args = typing.get_args(type_)
    if origin is types.UnionType:
        origin = Union

    # remove None from union and denote as optional
    if origin is Union and type(None) in args:
        is_optional = True
        args = tuple(arg for arg in args if arg is not type(None))
        if len(args) == 1:
            type_ = args[0]
        else:
            type_ = Union[args]  # type: ignore
    else:
        is_optional = False

    # recurse over type args if it's a type with origin
    if origin is not None:
        args = tuple(
            transform_and_templatify_type(arg, vars_, links, add_union, strict)
            for arg in args
        )
        type_ = origin[args]  # type: ignore
    # special case pydantic models
    elif inspect.isclass(type_) and issubclass(type_, BaseModel):
        fields = templatify_fields(
            type_,
            vars_=vars_,
            links=links,
            add_union=add_union,
            strict=strict,
        )
        # repackage the pydantic model
        # TODO does this break anything? the module namespacing miiiight be a problem
        type_ = pydantic.create_model(
            name or type_.__name__,
            __base__=type_,
            __module__=module or __name__,
            **fields,
        )
        type_.model_rebuild()

    # resolve TransformsFrom
    if inspect.isclass(type_) and issubclass(type_, TransformsFrom):
        type_ = type_._get_config_type(
            vars_=vars_,
            links=links,
            strict=strict,
        )

    if is_optional:
        type_ = Union[type_, None]
    _transformation_cache[cache_key] = type_
    return type_


def build_type_qualified_name(type_: type, *, markdown: bool) -> str:
    if type_ is type(None):
        return "None"

    # convert unions to a string
    origin = typing.get_origin(type_)
    if origin is not None:
        if origin in [Union, types.UnionType]:
            args = typing.get_args(type_)
            return " | ".join(
                build_type_qualified_name(arg, markdown=markdown) for arg in args
            )

        # convert literal to a string
        if origin is Literal:
            args = typing.get_args(type_)
            return " | ".join(repr(arg) for arg in args)

        # handle other origins
        origin_qual_name = build_type_qualified_name(origin, markdown=markdown)
        args_qual_names = " | ".join(
            build_type_qualified_name(arg, markdown=markdown)
            for arg in typing.get_args(type_)
        )
        return f"{origin_qual_name}[{args_qual_names}]"

    # handle TransformsFrom
    if inspect.isclass(type_) and issubclass(type_, TransformsFrom):
        return build_type_qualified_name(
            type_._get_config_type(None, None), markdown=markdown
        )

    # convert string enums to a string
    if inspect.isclass(type_) and issubclass(type_, Enum):
        return " | ".join(repr(member.value) for member in type_)

    # pass through names of simple and well-known types
    if type_.__module__ in ["builtins", "typing"]:
        return type_.__qualname__

    # add markdown link to custom types
    if not markdown:
        return type_.__qualname__

    # Building the link to the source code file
    try:
        # Get the file and line number where the type is defined
        source_file = inspect.getfile(type_)
        source_line = inspect.getsourcelines(type_)[1]

        # Construct the file URL
        source_path = os.path.abspath(source_file)
        file_url = f"file://{source_path}#L{source_line}"
        return f"[{type_.__qualname__}]({file_url})"
    except Exception:
        # Fallback to just the type name if we can't get the source file
        return type_.__qualname__


def remove_optional(type_: type | None) -> tuple[type, bool]:
    if type_ is None:
        return typing.Any, True
    if typing.get_origin(type_) in [Union, types.UnionType]:
        args = typing.get_args(type_)
        if type(None) in args:
            return args[0], True
    return type_, False


def build_field_description(
    field_name: str, field_info: FieldInfo, *, markdown: bool
) -> str:
    type_, is_optional = remove_optional(field_info.annotation)
    qualified_name = build_type_qualified_name(type_, markdown=markdown)

    field_desc = f"{field_name}: {qualified_name}"
    if is_optional:
        field_desc += " (optional)"

    if field_info.description:
        field_desc += f"  \n  {field_info.description}"

    return field_desc


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
