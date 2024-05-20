# Transforming between config and action variables
import types
import typing
from typing import TypeVar, Generic, Any, Union

import pydantic
import structlog
from pydantic import BaseModel
from pydantic_core import PydanticUndefined

from asyncflows.models.primitives import HintType
from asyncflows.utils.type_utils import get_var_string, filter_none_from_type

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
        vars_: HintType | None,
        links: HintType | None,
        strict: bool = False,
    ) -> type:  # -> type[ConfigType]:
        raise NotImplementedError


# forgive me father for I have sinned
# "I have used a global variable", says copilot
# this goes beyond mere global variables
# here is a function that transforms types, and renamespaces them to this module if they're pydantic models
# some types have recursive references, so we cache their forward references

# TODO maybe use generics to avoid the need for this?


_transformation_log = {}
_transformation_cache = {}


def resolve_transforms_from(
    type_: Any,
    vars_: HintType | None,
    links: HintType | None,
    strict: bool = False,
) -> Any:  # Union[type[ConfigType], type[ImplementsTransformsInContext]]:
    # to avoid forward references when unnecessary
    var_string = get_var_string(vars_, strict)
    cache_key = str((type_, var_string))
    if cache_key in _transformation_cache:
        return _transformation_cache[cache_key]

    # to avoid infinite recursion
    if cache_key in _transformation_log:
        return _transformation_log[cache_key]
    if (
        hasattr(type_, "__name__")
        and not hasattr(type_, "__origin__")
        and type_.__module__ != "builtins"
    ):
        if isinstance(type_, type) and issubclass(type_, BaseModel):
            name = f"{type_.__name__}_{var_string}"
            module = __name__
        else:
            name = type_.__name__
            module = type_.__module__
        _transformation_log[cache_key] = typing.ForwardRef(
            arg=name,
            module=module,
        )
    else:
        name = None
        module = None

    # if it's a union with None
    if (
        # isinstance(type_, type)
        typing.get_origin(type_) is Union and type(None) in typing.get_args(type_)
    ):
        is_optional = True
        type_ = filter_none_from_type(type_)
    else:
        is_optional = False

    origin = typing.get_origin(type_)
    if origin is not None:
        args = typing.get_args(type_)
        args = tuple(resolve_transforms_from(arg, vars_, links, strict) for arg in args)
        if origin is types.UnionType:
            origin = Union
            # type_ = args[0] | args[1]
        # else:
        type_ = origin[args]  # type: ignore

    # if isinstance(type_, list):
    #     type_ = [resolve_transforms_from(v, vars_, strict) for v in type_]
    # elif isinstance(type_, dict):
    #     type_ = {k: resolve_transforms_from(v, vars_, strict) for k, v in type_.items()}
    if not isinstance(type_, type):
        if is_optional:
            type_ = Union[type_, None]
        _transformation_cache[cache_key] = type_
        return type_

    if not isinstance(type_, types.GenericAlias) and issubclass(type_, BaseModel):
        fields = {}
        for field_name, field_ in type_.model_fields.items():
            # Annotate optional fields with a default of None
            if not field_.is_required():
                default = None
            elif field_.default is not PydanticUndefined:
                default = field_.default
            else:
                default = ...
            field_type = field_.annotation
            field_type = resolve_transforms_from(field_type, vars_, links, strict)
            fields[field_name] = (field_type, default)
        # TODO does this break anything? the module namespacing miiiight be a problem
        type_ = pydantic.create_model(
            name or type_.__name__,
            __base__=type_,
            __module__=module or __name__,
            **fields,
        )  # pyright: ignore[reportGeneralTypeIssues]
        type_.model_rebuild()
    if issubclass(type_, TransformsFrom):
        type_ = type_._get_config_type(
            vars_=vars_,
            links=links,
            strict=strict,
        )

    if is_optional:
        type_ = Union[type_, None]
    _transformation_cache[cache_key] = type_
    return type_
