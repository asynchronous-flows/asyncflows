# Transforming between config and action variables
import inspect
import types
import typing
from typing import TypeVar, Generic, Any, Union

import pydantic
import structlog
from pydantic import BaseModel
from pydantic_core import PydanticUndefined

from asyncflows.models.primitives import HintLiteral
from asyncflows.utils.type_utils import get_var_string

RealType = TypeVar("RealType")
ConfigType = TypeVar("ConfigType")
ImplementsTransformsInContext = TypeVar("ImplementsTransformsInContext")


class TransformsInto(Generic[RealType]):
    """
    In the config, some IO types will have a different representation.
    """

    async def transform_from_config(
        self, log: structlog.stdlib.BoundLogger, context: dict[str, Any]
    ) -> RealType:
        """
        Transform a config variable into the type used in the action.
        """
        raise NotImplementedError


class TransformsFrom:  # (Generic[ConfigType]):
    """
    In the config, some IO types will have a different representation.
    """

    @classmethod
    def _get_config_type(
        cls,
        vars_: HintLiteral | None,
        links: HintLiteral | None,
        strict: bool = False,
    ) -> type:  # -> type[ConfigType]:
        raise NotImplementedError


# forgive me father for I have sinned
# "I have used a global variable", says copilot
# this goes beyond mere global variables
# here is a function that transforms types, and renamespaces them to this module if they're pydantic models
# some types have recursive references, so we cache their forward references

# edit: im kind of proud of this function now that it's been refactored a bit

_forward_ref_cache = {}
_transformation_cache = {}


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
